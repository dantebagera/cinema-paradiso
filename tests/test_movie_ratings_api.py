import tempfile
import threading
import time
import unittest
import urllib.error
from pathlib import Path
from flask import Flask

from services.movie_ratings import MovieRatingsService
from services.movie_ratings_routes import register_movie_ratings_routes
from services.movie_ratings_store import MovieRatingsStore


GUID = 'plex://movie/' + 'a' * 24
IDENTITY = {'tmdb_id': '44012'}
KEY = 'movie:tmdb:44012'
LOCAL = {'type': 'movie', 'guid': GUID, 'ratingKey': '42', 'Guid': [{'id': 'tmdb://44012'}],
         'rating': 9.5, 'ratingImage': 'rottentomatoes://image.rating.ripe',
         'audienceRating': 7.7, 'audienceRatingImage': 'rottentomatoes://image.rating.upright'}


class RatingsApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MovieRatingsStore(Path(self.temp.name) / 'ratings.sqlite')
        self.config = {'url': 'http://plex.test', 'token': 'secret-token'}
        self.owned = {}
        self.calls = []
        self.hold = None
        self.failure = None
        self.payload = LOCAL
        self.clock = 1000.
        def transport(base, token, path, **options):
            self.calls.append((base, path, options.get('params')))
            if self.hold: self.hold.wait(5)
            if self.failure: raise self.failure
            if path == '/library/sections': return {'MediaContainer': {'Directory': []}}
            return {'MediaContainer': {'Metadata': [self.payload]}}
        self.service = MovieRatingsService(self.store, config=lambda: self.config,
            ownership=lambda ids: self.owned, transport=transport, clock=lambda: self.clock)
        self.app = Flask(__name__)
        register_movie_ratings_routes(self.app, lambda: self.service)
        self.client = self.app.test_client()

    def tearDown(self):
        if self.hold: self.hold.set()
        self.service.stop()
        self.temp.cleanup()

    def post(self, route='read', items=None):
        return self.client.post('/api/movie-ratings/'+route, json={'items': items or [IDENTITY]})

    def wait_for(self, predicate):
        deadline = time.monotonic()+3
        while time.monotonic()<deadline:
            value = self.post().get_json()
            if predicate(value): return value
            time.sleep(.01)
        self.fail('ratings state did not settle: '+str(value))

    def seed_local(self):
        self.service.offer_local_snapshot([LOCAL], ['1'])
        self.wait_for(lambda b: b['items'][KEY].get('critics') == 95)

    def test_unconfigured_returns_quiet_200_and_zero_provider_calls(self):
        self.config = {'url': '', 'token': ''}
        for route in ['read', 'resolve']:
            response = self.post(route)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('error', response.get_json())
            self.assertFalse(response.get_json()['items'][KEY]['display_allowed'])
        self.assertEqual(self.calls, [])

    def test_read_and_resolve_return_while_provider_is_held(self):
        self.hold = threading.Event()
        start = time.monotonic()
        response = self.post('resolve')
        self.assertEqual(response.status_code, 202)
        self.assertLess(time.monotonic()-start, .1)
        self.assertFalse(self.post().get_json()['items'][KEY]['display_allowed'])

    def test_unowned_exact_tmdb_match_returns_both_scores(self):
        self.post('resolve')
        body = self.wait_for(lambda b: b['items'][KEY].get('critics') == 95)
        self.assertEqual(body['items'][KEY]['audience'], 77)
        self.assertFalse(body['items'][KEY]['owned'])
        self.assertEqual(self.calls[-1][2], {'guid': 'tmdb://44012', 'type': 1})
        self.assertNotIn('secret-token', str(body))

    def test_plex_only_identity_uses_exact_catalog_metadata_path(self):
        from services.movie_ratings import movie_identity
        identity = movie_identity({'plex_guid': GUID})
        self.service.request([identity])
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            item = self.service.read([identity])['items'][identity['key']]
            if item['display_allowed']: break
            time.sleep(.01)
        self.assertEqual((item['critics'], item['audience']), (95, 77))
        self.assertEqual(self.calls[-1], ('https://metadata.provider.plex.tv', '/library/metadata/' + 'a'*24, None))

    def test_owned_saved_scores_display_offline_without_probe(self):
        self.owned[KEY] = {'rating_key': '42'}
        self.seed_local()
        self.config = {'url': '', 'token': ''}
        self.service.invalidate_config()
        result = self.post('resolve').get_json()['items'][KEY]
        self.assertEqual((result['critics'], result['audience']), (95, 77))
        self.assertTrue(result['display_allowed'])
        self.assertEqual(self.calls, [])

    def test_partial_and_missing_observations_retry_after_one_day(self):
        self.owned[KEY] = {'rating_key': '42'}
        for payload in [{**LOCAL, 'audienceRating': None}, {**LOCAL, 'rating': None, 'audienceRating': None}]:
            with self.subTest(payload=payload):
                record = self.service._record(payload, 'local_saved')
                self.assertEqual(record['expires_at'], self.clock + 86400)
        self.assertEqual(self.service._record(LOCAL, 'local_saved')['expires_at'], self.clock + 604800)

    def test_empty_refresh_preserves_saved_pair_without_repeated_provider_work_after_restart(self):
        self.owned[KEY] = {'rating_key': '42'}
        self.seed_local()
        self.clock += 604801
        self.payload = {**LOCAL, 'rating': None, 'audienceRating': None}
        self.post('resolve')
        self.wait_for(lambda b: bool(self.calls) and not self.service._active and not self.service._queue)
        saved = self.post().json['items'][KEY]
        self.assertEqual((saved['critics'], saved['audience'], saved['retrieved_at']), (95, 77, 1000))
        self.assertTrue(saved['stale'])
        self.assertEqual(saved['retry_at'], self.clock + 86400)
        transport = self.service.transport
        self.service.stop()
        self.service = MovieRatingsService(self.store, config=lambda: self.config,
            ownership=lambda ids: self.owned, transport=transport, clock=lambda: self.clock)
        before = len(self.calls)
        for _ in range(5): self.post('resolve')
        time.sleep(.05)
        self.assertEqual(len(self.calls), before)

    def test_cached_unowned_scores_suppressed_after_disconnect(self):
        self.post('resolve')
        self.wait_for(lambda b: b['items'][KEY]['display_allowed'])
        self.config = {'url': '', 'token': ''}
        self.service.invalidate_config()
        item = self.post().get_json()['items'][KEY]
        self.assertFalse(item['display_allowed'])
        self.assertIsNone(item['critics'])

    def test_removed_ownership_revokes_offline_exception(self):
        self.owned[KEY] = {'rating_key': '42'}
        self.seed_local()
        self.config = {'url': '', 'token': ''}
        self.owned.clear()
        item = self.post().get_json()['items'][KEY]
        self.assertFalse(item['display_allowed'])
        self.assertIsNone(item['critics'])

    def test_visible_owned_metadata_fetch_is_targeted_and_identity_checked(self):
        self.owned[KEY] = {'rating_key': '42'}
        self.post('resolve')
        self.wait_for(lambda b: b['items'][KEY].get('critics') == 95)
        self.assertEqual([c[1] for c in self.calls], ['/library/metadata/42'])

    def test_local_unavailable_does_not_bypass_to_online(self):
        self.failure = OSError('cannot reach secret-token')
        self.post('resolve')
        body = self.wait_for(lambda b: b['plex']['state'] == 'unavailable')
        self.assertEqual([c[0] for c in self.calls], ['http://plex.test'])
        self.assertNotIn('secret-token', str(body))
        self.assertFalse(body['items'][KEY]['display_allowed'])

    def test_duplicate_demand_is_single_flight(self):
        self.hold = threading.Event()
        for _ in range(10): self.post('resolve')
        self.hold.set()
        self.wait_for(lambda b: b['items'][KEY]['display_allowed'])
        self.assertEqual(sum(c[1].endswith('/matches') for c in self.calls), 1)

    def test_wrong_identity_cannot_publish(self):
        self.payload = {**LOCAL, 'Guid': [{'id': 'tmdb://123'}]}
        self.post('resolve')
        body = self.wait_for(lambda b: b['items'][KEY]['state'] == 'identity_mismatch')
        self.assertFalse(body['items'][KEY]['display_allowed'])
        self.assertEqual(self.store.read_many([KEY]), {})

    def test_old_completion_rejected_after_config_invalidation(self):
        self.hold = threading.Event()
        self.post('resolve')
        time.sleep(.03)
        self.config = {'url': '', 'token': ''}
        self.service.invalidate_config()
        self.hold.set()
        time.sleep(.04)
        self.assertEqual(self.store.read_many([KEY]), {})

    def test_validation_rejects_abuse_without_network(self):
        for body in [{'items': [{}]}, {'items': [{'tmdb_id': i} for i in range(1, 42)]}, {'items': 'bad'}]:
            self.assertEqual(self.client.post('/api/movie-ratings/resolve', json=body).status_code, 400)
        self.assertEqual(self.calls, [])

    def test_restart_keeps_owned_saved_but_revokes_online_availability(self):
        self.owned[KEY] = {'rating_key': '42'}
        self.seed_local()
        self.service.stop()
        self.config = {}
        self.service = MovieRatingsService(MovieRatingsStore(self.store.path), config=lambda:self.config,
            ownership=lambda ids:self.owned, transport=lambda *a,**k:self.fail('offline probe'))
        item=self.post().get_json()['items'][KEY]
        self.assertEqual(item['critics'],95)
        self.assertTrue(item['owned'])

    def test_partial_library_sync_retains_verified_ids_and_saved_scores(self):
        self.owned[KEY] = {'rating_key':'42'}
        self.seed_local()
        self.clock += 1
        self.service.offer_local_snapshot([{'guid':GUID,'rating':8,'ratingImage':'imdb://image.rating'}])
        time.sleep(.05)
        self.config={}
        self.assertEqual(self.post().get_json()['items'][KEY]['critics'],95)

    def test_429_honors_long_retry_after_and_does_not_loop(self):
        self.failure=urllib.error.HTTPError('http://plex.test',429,'rate limited',{'Retry-After':'7200'},None)
        self.post('resolve')
        body=self.wait_for(lambda b:b['plex']['state']=='unavailable')
        self.assertEqual(body['items'][KEY]['retry_at'],8200)
        for _ in range(10):self.post('resolve')
        self.assertEqual(len(self.calls),1)

    def test_401_pauses_until_config_changes(self):
        self.failure=urllib.error.HTTPError('http://plex.test',401,'auth',{},None)
        self.post('resolve');self.wait_for(lambda b:b['plex']['state']=='unavailable')
        self.clock+=100000
        self.post('resolve');self.assertEqual(len(self.calls),1)
        self.failure=None;self.service.invalidate_config();self.post('resolve')
        self.wait_for(lambda b:b['items'][KEY]['display_allowed'])

    def test_cache_corruption_is_quiet_and_read_never_calls_provider(self):
        self.store.path.write_bytes(b'not a database')
        response=self.post()
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.get_json()['items'][KEY]['display_allowed'])
        self.assertEqual(self.calls,[])
        self.assertEqual(response.headers['Cache-Control'],'private, no-store')

    def test_expired_lease_hides_cached_unowned_until_revalidation(self):
        self.post('resolve');self.wait_for(lambda b:b['items'][KEY]['display_allowed'])
        self.clock+=301
        self.assertFalse(self.post().get_json()['items'][KEY]['display_allowed'])
        self.post('resolve');self.wait_for(lambda b:b['items'][KEY]['display_allowed'])
        self.assertEqual(sum(c[1]=='/library/sections' for c in self.calls),2)

    def test_fresh_online_cache_does_not_repeat_title_lookup(self):
        self.post('resolve');self.wait_for(lambda b:b['items'][KEY]['display_allowed'])
        for _ in range(5):self.post('resolve')
        self.assertEqual(len(self.calls),2)

    def test_local_sync_alone_cannot_reauthorize_old_online_scores(self):
        self.post('resolve');self.wait_for(lambda b:b['items'][KEY]['display_allowed'])
        self.clock+=301
        self.service.offer_local_snapshot([LOCAL])
        self.assertFalse(self.post().get_json()['items'][KEY]['display_allowed'])

    def test_online_traffic_does_not_extend_local_server_health_lease(self):
        self.post('resolve');self.wait_for(lambda b:b['items'][KEY]['display_allowed'])
        self.clock+=200
        self.post('resolve',items=[{'tmdb_id':'123'}])
        time.sleep(.04)
        self.clock+=101
        self.post('resolve')
        self.wait_for(lambda b:b['items'][KEY]['display_allowed'])
        self.assertEqual(sum(c[1]=='/library/sections' for c in self.calls),2)

    def test_online_starts_are_spaced_and_pending_demand_can_be_renewed(self):
        self.hold=threading.Event()
        self.post('resolve',items=[IDENTITY,{'tmdb_id':'123'}])
        time.sleep(.02)
        self.clock+=20
        self.post('resolve',items=[{'tmdb_id':'123'}])
        starts=[]
        original=self.service.transport
        def measured(*args,**kwargs):
            if args[1] and args[2].endswith('/matches'):starts.append(time.monotonic())
            return original(*args,**kwargs)
        self.service.transport=measured
        self.hold.set()
        deadline=time.monotonic()+3
        while len(starts)<2 and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(len(starts),2)
        self.assertGreaterEqual(starts[1]-starts[0],.49)

    def test_corrected_identity_does_not_inherit_prior_negative_cache(self):
        self.payload={**LOCAL,'Guid':[{'id':'tmdb://44012'},{'id':'imdb://tt11111'}]}
        self.post('resolve',items=[{'tmdb_id':'44012','imdb_id':'tt22222'}])
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            item=self.post(items=[{'tmdb_id':'44012','imdb_id':'tt22222'}]).json['items'][KEY]
            if item['state']=='identity_mismatch':break
            time.sleep(.01)
        self.assertEqual(item['state'],'identity_mismatch')
        self.post('resolve',items=[{'tmdb_id':'44012','imdb_id':'tt11111'}])
        self.wait_for(lambda b:b['items'][KEY]['display_allowed'])

    def test_compatible_cross_tab_demands_share_one_confirmed_provider_result(self):
        self.payload={**LOCAL,'Guid':[{'id':'tmdb://44012'},{'id':'imdb://tt11111'}]}
        self.hold=threading.Event()
        self.post('resolve')
        self.post('resolve',items=[{'tmdb_id':'44012','imdb_id':'tt11111'}])
        self.hold.set()
        self.wait_for(lambda b:b['items'][KEY]['display_allowed'])
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            with self.service._condition:
                if not self.service._queue and self.service._active is None:break
            time.sleep(.01)
        self.assertFalse(self.service._queue)
        self.assertIsNone(self.service._active)
        self.assertEqual(sum(c[1].endswith('/matches') for c in self.calls),1)

    def test_older_deferred_sync_cannot_overwrite_newer_targeted_observation(self):
        self.owned[KEY]={'rating_key':'42'}
        with self.service._condition:
            self.service.offer_local_snapshot([LOCAL])
            self.clock+=10
            self.payload={**LOCAL,'rating':9.8}
            self.post('resolve')
        self.wait_for(lambda b:b['items'][KEY]['critics']==98)
        time.sleep(.05)
        self.assertEqual(self.post().json['items'][KEY]['critics'],98)

    def test_partial_browser_identity_cannot_bypass_canonical_manual_correction(self):
        self.owned[KEY]={'rating_key':'42'}
        self.seed_local()
        plex_key='movie:plex:'+'a'*24
        self.owned[plex_key]={'rating_key':'42','identity':{'tmdb_id':'123','plex_guid':GUID}}
        self.config={}
        item=self.post(items=[{'plex_guid':GUID}]).json['items'][plex_key]
        self.assertTrue(item['owned'])
        self.assertFalse(item['display_allowed'])
        self.assertIsNone(item['critics'])

    def test_conflicting_submitted_ids_cannot_read_cached_other_movie(self):
        self.post('resolve');self.wait_for(lambda b:b['items'][KEY]['display_allowed'])
        value=self.post(items=[{'tmdb_id':'44012','imdb_id':'tt99999'}]).get_json()['items'][KEY]
        self.assertFalse(value['display_allowed'])

    def test_10k_cache_40_identity_routes_remain_bounded_with_held_provider(self):
        import statistics
        records=[]
        for number in range(1,10001):
            key='movie:tmdb:'+str(number)
            records.append({'key':key,'aliases':[key],'identity':{'tmdb_id':str(number)},'source':'local_saved',
                'critics':70,'audience':80,'retrieved_at':1000,'sequence':1000})
        self.store.publish(records)
        self.hold=threading.Event()
        self.post('resolve')
        times=[]
        items=[{'tmdb_id':str(n)} for n in range(1,41)]
        for _ in range(40):
            start=time.perf_counter();self.post(items=items);times.append((time.perf_counter()-start)*1000)
        p95=sorted(times)[37]
        print('RT 10k cache / 40 IDs read p95 ms:',round(p95,3))
        self.assertLess(p95,50)
        times=[]
        for _ in range(40):
            start=time.perf_counter();self.post('resolve',items=items);times.append((time.perf_counter()-start)*1000)
        p95=sorted(times)[37]
        print('RT 10k cache / 40 IDs resolve p95 ms:',round(p95,3))
        self.assertLess(p95,50)


if __name__ == '__main__': unittest.main()
