import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import app
from services.player_config import PlayerConfig
from services.plex_tv import PlexTVDiscovery
from services.tv_catalog_repository import TVCatalogRepository
from services.tv_filename_parser import parse_episode_name, resolve_episode_claim
from services.tv_ingestion import TVIngestion
from services.tv_metadata import TVMetadata
from services.tv_playback import TVPlayback, TVPlaybackHistory
from services.tv_read_model import TVReadModel
from services.streaming_templates import validate_tv_template


class TVVerticalSliceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = json.loads((Path(__file__).parent / 'fixtures/native_tv_cases.json').read_text())
        self.repo = TVCatalogRepository(self.root / 'tv-catalog.sqlite')
        self.series_id = self.repo.refresh(self.fixture['series'], self.fixture['episodes'])
        self.ingestion = TVIngestion(self.repo, lambda: [self.root], probe=lambda _: {'probe_status': 'ok', 'quality_class': '1080p'})
        self.read = TVReadModel(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def ingest(self, name):
        path = self.root / name
        path.write_bytes(b'synthetic video')
        return self.ingestion.ingest(self.series_id, path)

    def test_numbering_daily_specials_and_ambiguity(self):
        for case in self.fixture['names']:
            claim = parse_episode_name(case['name'])
            if 'episodes' in case:
                self.assertEqual(claim['episode_numbers'], case['episodes'])
            if 'scope' in case:
                self.assertEqual(claim['scope'], case['scope'])
            if 'air_date' in case:
                self.assertEqual(claim['air_date'], case['air_date'])
        ambiguous = self.ingest('Harbor.Signals.003.1080p.mkv')
        self.assertEqual(ambiguous['state'], 'needs_review')
        self.assertEqual(self.ingest('Harbor.Signals.003.1080p.mkv')['review_id'], ambiguous['review_id'])
        self.assertEqual(self.ingest('Harbor.Signals.S01E02.sample.mkv')['state'], 'ignored')
        self.assertEqual(self.ingest('Harbor.Signals.2020.01.02.mkv')['state'], 'accepted')

    def test_current_episode_does_not_skip_a_missing_episode(self):
        self.ingest('Harbor.S01E01.mkv')
        self.ingest('Harbor.S01E03.mkv')
        first = self.repo.episodes(self.series_id, 1)[0]
        self.repo.save_progress(first['id'], completed=True)
        self.assertEqual(self.read.detail(self.series_id)['primary_action']['label'], 'Start')
        self.repo.save_progress(first['id'], completed=True, player_activity=True)
        model = self.read.detail(self.series_id)
        self.assertEqual(model['primary_action']['label'], 'Play next')
        self.assertEqual(model['primary_action']['target']['episode_number'], 2)
        self.assertFalse(model['primary_action']['playable'])
        self.assertEqual(model['stream_target']['episode_number'], 2)
        self.assertEqual(model['season_count'], 2)
        self.assertTrue(model['has_specials'])
        self.assertEqual(model['episode_count'], 4)
        self.assertEqual(model['specials_count'], 1)

    def test_player_events_complete_only_the_episode_and_rewatch_survives_restart(self):
        self.ingest('Harbor.S01E01.mkv')
        first = self.repo.episodes(self.series_id, 1)[0]
        playback = TVPlayback(self.repo, lambda: [self.root])
        media = playback.resolve(playback.target(first['id']))
        history = TVPlaybackHistory(self.repo, PlayerConfig({}))
        context = history.begin_session(media)
        session = SimpleNamespace(playback_context=context)
        history.handle_event(session, {'type': 'progress', 'position_ms': 97000, 'duration_ms': 100000, 'paused': True})
        rows = self.repo.episodes(self.series_id, 1)
        self.assertTrue(rows[0]['completed'])
        self.assertFalse(rows[1]['completed'])
        history.begin_session(media, restart=True)
        history.handle_event(session, {'type': 'playback.state', 'state': 'ended'})
        self.assertFalse(TVCatalogRepository(self.root / 'tv-catalog.sqlite').episodes(self.series_id, 1)[0]['completed'])

    def test_multi_episode_playback_does_not_guess_segment_completion(self):
        self.ingest('Harbor.S01E01-E02.mkv')
        first = self.repo.episodes(self.series_id, 1)[0]
        playback = TVPlayback(self.repo, lambda: [self.root])
        history = TVPlaybackHistory(self.repo, PlayerConfig({}))
        context = history.begin_session(playback.resolve(playback.target(first['id'])))
        history.handle_event(SimpleNamespace(playback_context=context), {'type': 'playback.state', 'state': 'ended'})
        self.assertFalse(any(row['completed'] for row in self.repo.episodes(self.series_id)))

    def test_native_queue_preserves_missing_episode_and_crosses_seasons_without_specials(self):
        self.ingest('Harbor.S01E01.mkv')
        self.ingest('Harbor.S01E03.mkv')
        self.ingest('Harbor.S02E01.mkv')
        playback = TVPlayback(self.repo, lambda: [self.root])
        first = self.repo.episodes(self.series_id, 1)[0]
        media = playback.resolve(playback.target(first['id']))
        with patch.object(self.repo, 'episodes', wraps=self.repo.episodes) as listing:
            result = playback.queue(media)
            self.assertEqual(listing.call_count, 1)
        self.assertEqual([row['title'].split(' · ')[0] for row in result['items']],
                         ['S01E01', 'S01E02', 'S01E03', 'S02E01', 'S02E02'])
        self.assertFalse(result['items'][1]['available'])
        self.assertTrue(result['items'][2]['available'])
        self.assertEqual(result['items'][-1]['section'], 'Season 2')
        self.assertFalse(result['items'][-1]['available'])
        self.assertEqual(result['items'][-1]['reason'], 'Episode has not aired')

    def test_tv_routes_are_off_by_default_and_movie_progress_store_is_unchanged(self):
        client = app.app.test_client()
        with patch.object(app, '_tv_enabled', False):
            self.assertEqual(client.get('/api/tv/series').status_code, 404)
            self.assertEqual(client.get('/api/tv/config').status_code, 200)
        services = {'repository': self.repo, 'read': self.read, 'ingestion': self.ingestion}
        with patch.object(app, '_tv_enabled', True), patch.dict(app._tv_services._instances, {Path(app._user_data_dir).resolve() / 'tv-catalog.sqlite': services}):
            result = client.get(f'/api/tv/series/{self.series_id}')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json['media_type'], 'tv')
            self.assertEqual(client.get(f'/api/tv/series/{self.series_id}/seasons/1').json['total'], 3)

    def test_tv_settings_require_existing_roots_before_enabling(self):
        client = app.app.test_client()
        with patch.object(app, '_tv_enabled', False), patch.object(app, '_tv_roots', []), patch.object(app, '_save_config'):
            missing = client.post('/api/tv/config', json={'enabled':True, 'roots':[str(self.root/'missing')]})
            self.assertEqual(missing.status_code, 400)
            saved = client.post('/api/tv/config', json={'enabled':True, 'roots':[str(self.root)]})
            self.assertEqual(saved.status_code, 200)
            self.assertTrue(saved.json['enabled'])
            self.assertEqual(saved.json['roots'], [str(self.root.resolve())])

    def test_stream_template_requires_typed_episode_fields(self):
        self.assertEqual(validate_tv_template(self.fixture['streaming_template']), self.fixture['streaming_template'])
        for template in ('javascript:alert(1)', 'https://example.invalid/{tmdb_id}', 'https://{tmdb_id}/tv/{season_number}/{episode_number}', 'https://example.invalid/{tmdb_id.__class__}/{season_number}/{episode_number}'):
            with self.assertRaises(ValueError):
                validate_tv_template(template)

    def test_library_filters_and_pagination_hydrate_only_requested_cards(self):
        harbor_folder = self.root / 'Harbor Signals'; harbor_folder.mkdir()
        self.repo.approve_path(harbor_folder, 'folder', self.series_id)
        for number in range(10):
            identity = self.repo.refresh({**self.fixture['series'], 'tmdb_id':910000+number, 'title':f'Other {number}'}, [])
            folder = self.root / f'Other {number}'; folder.mkdir()
            self.repo.approve_path(folder, 'folder', identity)
        with patch.object(self.read, 'detail', wraps=self.read.detail) as detail:
            result = self.read.library(page_size=2)
            self.assertEqual(result['total'], 11)
            self.assertEqual(detail.call_count, 2)
        self.assertEqual(self.read.library(query='Harbor', genre='Drama', minimum_rating=8)['total'], 1)
        self.assertEqual(self.read.library(query='Harbor', minimum_rating=9)['total'], 0)
        self.assertEqual(self.read.library(query='Harbor', availability='available')['total'], 0)
        self.assertEqual(self.read.library(monitoring='monitored', monitored_ids={900001})['total'], 1)
        self.assertEqual(self.read.library(monitoring='unmonitored', monitored_ids={900001})['total'], 10)
        for sort in ('year', 'rating', 'recently_added', 'recently_aired', 'recently_played', 'progress', 'missing'):
            self.assertEqual(self.read.library(sort=sort, page_size=2)['total'], 11)
        self.ingest('Harbor.Signals.S01E01.1080p.WEB-DL.mkv')
        self.assertEqual(self.read.library(query='Harbor', availability='available')['total'], 1)

    def test_new_playback_session_and_manual_completion_reject_stale_events(self):
        from services.tv_playback import TVHistoryStore
        result = self.ingest('Harbor.Signals.S01E01.1080p.WEB-DL.mkv')
        episode = self.repo.episodes(self.series_id, 1)[0]
        history = TVHistoryStore(self.repo)
        key = f"tv:episode:{episode['id']}:file:{result['file_id']}"
        first = history.begin_session(key)
        second = history.begin_session(key)
        self.assertGreater(second['revision'], first['revision'])
        self.repo.save_progress(episode['id'], completed=True)
        stale = history.save(key, second['revision'], position_ms=100, duration_ms=10000, completion_threshold=.9)
        self.assertFalse(stale['accepted'])
        self.assertTrue(self.repo.episodes(self.series_id,1)[0]['completed'])

    def test_plex_discovery_uses_typed_tmdb_identity_and_paginates(self):
        calls = []
        class Response:
            def __init__(self, payload): self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return json.dumps(self.payload).encode()
        def opener(request, timeout):
            calls.append((request.full_url, request.headers, timeout))
            url = request.full_url
            if url.endswith('/library/sections'):
                return Response({'MediaContainer': {'Directory': [{'key':'1', 'type':'movie'}, {'key':'2', 'type':'show'}]}})
            if '/library/sections/2/all' in url:
                return Response({'MediaContainer': {'Metadata': [
                    {'ratingKey':'wrong', 'title':'Harbor Signals', 'Guid':[{'id':'tmdb://12'}]},
                    {'ratingKey':'right', 'title':'A renamed series', 'Guid':[{'id':'tmdb://900001'}]},
                ]}})
            return Response({'MediaContainer': {'totalSize':1, 'Metadata': [{
                'ratingKey':'episode', 'parentIndex':1, 'index':1, 'Guid':[{'id':'tmdb://800001'}],
                'Media':[{'Part':[{'file':str(self.root/'Harbor.Signals.003.mkv')}]}],
            }]}})
        rows = PlexTVDiscovery(lambda:'http://plex.test', lambda:'secret', opener=opener).entries(900001)
        self.assertEqual(rows[0]['tmdb_episode_id'], 800001)
        self.assertIn('/library/metadata/right/allLeaves', calls[-1][0])
        self.assertEqual(calls[0][1]['X-plex-token'], 'secret')
        self.assertNotIn('secret', calls[0][0])

    def test_plex_episode_identity_resolves_an_ambiguous_filename(self):
        episodes = [{**row, 'provider_id': str(800000 + index)} for index, row in enumerate(self.fixture['episodes'], 1)]
        self.repo.refresh(self.fixture['series'], episodes)
        path = self.root/'Harbor.Signals.003.mkv'
        path.write_bytes(b'synthetic video')
        result = self.ingestion.ingest_plex(self.series_id, [{'path':str(path), 'tmdb_episode_id':800003}])[0]
        self.assertEqual(result['state'], 'accepted')
        self.assertEqual(result['episode_ids'], [self.repo.episodes(self.series_id, 1)[1]['id']])

    def test_metadata_refresh_bounds_season_concurrency(self):
        active = [0]
        peak = [0]
        lock = threading.Lock()
        metadata = TVMetadata(self.repo, lambda:'key', max_workers=2)
        def request(path, **_params):
            if path == '/tv/900100':
                return {'id':900100, 'name':'Bounded', 'seasons':[{'season_number':number} for number in range(6)], 'credits':{}}
            number = int(path.rsplit('/', 1)[1])
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(.01)
            with lock:
                active[0] -= 1
            return {'episodes':[{'id':910000+number, 'season_number':number, 'episode_number':1, 'name':f'Episode {number}'}]}
        metadata.request = request
        series_id = metadata.refresh(900100)
        self.assertEqual(len(self.repo.episodes(series_id)), 6)
        self.assertGreater(peak[0], 1)
        self.assertLessEqual(peak[0], 2)

    def test_metadata_rate_limit_backoff_and_cache(self):
        calls, sleeps = [0], []
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return b'{"results": []}'
        def opener(_url, timeout):
            calls[0] += 1
            if calls[0] == 1:
                raise HTTPError('http://tmdb.test', 429, 'limited', {'Retry-After':'2'}, None)
            return Response()
        metadata = TVMetadata(self.repo, lambda:'key', opener=opener, sleeper=sleeps.append)
        self.assertEqual(metadata.request('/discover/tv', page=1), {'results':[]})
        self.assertEqual(metadata.request('/discover/tv', page=1), {'results':[]})
        self.assertEqual(calls[0], 2)
        self.assertEqual(sleeps, [2])

    def test_integrity_audit_reports_each_orphan_category(self):
        audit = self.repo.store.audit()
        self.assertEqual(audit['integrity'], 'ok')
        self.assertEqual(audit['foreign_keys'], [])
        self.assertEqual(audit['orphans'], {'episodes':0, 'files':0, 'bindings':0, 'identities':0, 'progress':0})
