"""Movie Follow contract through real routes, persistence and source matching."""
from contextlib import ExitStack
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import app
from tests.test_yts_option2 import FakeResponse


class MovieFollowContractTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = self.stack.enter_context(tempfile.TemporaryDirectory(prefix='cp-movie-follow-route-'))
        for name, value in {
            '_user_data_dir': root, '_curation_store_cache': {},
            '_prowlarr_url': 'http://prowlarr.test', '_prowlarr_key': 'fixture',
            '_trusted_release_indexers': ['1'], '_trusted_release_indexers_configured': True,
            '_tmdb_key': '', '_yts_source_identity_cache': {},
        }.items():
            self.stack.enter_context(patch.object(app, name, value))
        self.stack.enter_context(patch('app._find_owned_movies', side_effect=lambda rows: [None] * len(rows)))
        self.stack.enter_context(patch('app._movie_tmdb_metadata_for_source_search', return_value={}))
        self.stack.enter_context(patch('app._smart_match_tmdb_alternative_titles', return_value=[]))
        self.results = []
        self.page_imdb = 'tt36983905'
        self.page_error = False
        self.search_error = False
        self.rss = '<rss><channel/></rss>'
        self.stack.enter_context(patch('app.urllib.request.urlopen', side_effect=self.provider))
        self.store = app._curation_store()
        self.client = app.app.test_client()

    def provider(self, request, timeout=0):
        url = request.full_url
        if url.endswith('/api/v1/indexer'):
            return FakeResponse([{'id': 1, 'name': 'YTS', 'enable': True}])
        if urlparse(url).path == '/rss':
            return FakeResponse(self.rss, raw=True)
        if '/api/v1/search?' in url:
            if self.search_error:
                raise OSError('Fixture source unavailable')
            # Exercise the real query planner; a provider is not allowed to
            # return a title lookup disguised as an IMDb lookup.
            query = parse_qs(urlparse(url).query)['query'][0]
            rows = self.results if query.startswith('tt') else []
            return FakeResponse(rows)
        if url.startswith('https://yts.gg/movies/'):
            if self.page_error:
                raise OSError('Fixture identity page unavailable')
            return FakeResponse(f'<a href="https://www.imdb.com/title/{self.page_imdb}/">IMDb</a>', raw=True)
        raise AssertionError(f'Unconfigured provider request: {url}')

    def follow(self, title='The Uprising', year='2026', imdb='tt36983905', release_date='2026-09-10'):
        return self.store.follow_movie({'title': title, 'year': year, 'imdb_id': imdb,
                                        'tmdb_id': '977942', 'release_date': release_date})

    def test_ownership_reconciliation_runs_during_full_scan_and_late_scan_returns_current_list(self):
        movie = self.follow()
        entered = threading.Event()
        release = threading.Event()
        responses = []
        def slow_scan():
            entered.set()
            if not release.wait(10):
                raise RuntimeError('Test scan gate timed out')
            return {'movies': [movie], 'newly_available': [movie], 'removed_owned': []}
        def scan_request():
            with app.app.test_client() as client:
                responses.append(client.post('/api/user/followed-releases/check').get_json())
        with patch('app._check_followed_releases', side_effect=slow_scan), \
                patch('app._find_owned_movies', side_effect=lambda rows: [{'path': 'fixture-owned'}] * len(rows)):
            worker = threading.Thread(target=scan_request)
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                reconciled = self.client.post('/api/user/followed-releases/reconcile-owned').get_json()
                self.assertEqual(reconciled['movies'], [])
                self.assertEqual(len(reconciled['removed_owned']), 1)
                self.assertNotIn('scan_in_progress', reconciled)
                self.assertTrue(worker.is_alive())
            finally:
                release.set()
                worker.join(5)
        self.assertEqual(responses[0]['movies'], [])
        self.assertEqual(responses[0]['newly_available'], [])
        self.assertGreaterEqual(responses[0]['curation_generation'], reconciled['curation_generation'])

    def test_following_response_does_not_stamp_stale_movies_with_current_generation(self):
        movie = self.follow()
        stale_result = {'movies': [movie], 'newly_available': [movie], 'removed_owned': []}
        self.store.unfollow_movie(movie)
        with patch('app._check_followed_releases', return_value=stale_result):
            result = self.client.post('/api/user/followed-releases/check').get_json()
        self.assertEqual(result['movies'], [])
        self.assertEqual(result['newly_available'], [])
        self.assertEqual(result['curation_generation'], self.store.catalog.generation('curation'))

    def release(self, title='The Rage (2026) 1080p WEBRip 5.1 x264 -YTS', indexer='YTS'):
        return {'title': title, 'indexer': indexer, 'seeders': 10, 'size': 2000000000,
                'infoUrl': 'https://yts.gg/movies/fixture-2026',
                'magnetUrl': 'magnet:?xt=urn:btih:' + 'a' * 40,
                'downloadUrl': 'http://prowlarr.test/download/fixture'}

    def scan(self):
        response = self.client.post('/api/user/followed-releases/check')
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def assert_available(self, payload):
        self.assertEqual(payload['movies'][0]['status'], 'available')
        self.assertEqual(payload['movies'][0]['best_release']['info_hash'], 'a' * 40)
        self.assertEqual(len(payload['newly_available']), 1)
        self.assertEqual(self.store.followed_all()[0]['status'], 'available')

    def test_scan_ignores_saved_retry_date_and_uses_verified_imdb(self):
        movie = self.follow()
        movie['next_check_at'] = app.time.time() + 7 * 86400
        self.store.save_followed_all([movie])
        self.results = [self.release()]
        self.assert_available(self.scan())

    def test_second_scan_searches_immediately_after_a_miss(self):
        self.follow(title='Practical Magic 2', imdb='tt32588798')
        self.page_imdb = 'tt32588798'
        first = self.scan()
        self.assertEqual(first['movies'][0]['status'], 'watching')
        self.results = [self.release('Practical Magic 2 (2026) 1080p WEBRip -YTS')]
        self.assert_available(self.scan())

    def test_verified_identity_accepts_all_confirmed_title_and_year_variants(self):
        cases = [
            ('Northspur', '2021', 'tt8709312', 'Northspur (2022) 1080p BRRip -YTS'),
            ('The Uprising', '2026', 'tt36983905', 'The Rage (2026) 1080p WEBRip -YTS'),
            ('Hope', '2026', 'tt27369017', 'Hopeu (2026) 1080p WEBRip -YTS'),
            ('Sheep in the Box', '2026', 'tt38551209', 'Hako no naka no hitsuji (2026) 1080p WEBRip -YTS'),
        ]
        for title, year, imdb, release_title in cases:
            with self.subTest(title=title):
                self.store.save_followed_all([])
                app._yts_source_identity_cache.clear()
                self.follow(title=title, year=year, imdb=imdb)
                self.page_imdb = imdb
                self.results = [self.release(release_title)]
                self.assert_available(self.scan())

    def test_future_metadata_date_does_not_hide_a_verified_existing_release(self):
        self.follow(release_date='2035-01-01')
        self.results = [self.release()]
        self.assert_available(self.scan())

    def test_rss_accepts_verified_identity_despite_an_alternate_title(self):
        movie = self.follow()
        movie['next_check_at'] = app.time.time() + 7 * 86400
        self.store.save_followed_all([movie])
        self.rss = ('<rss><channel><item><title>The Rage (2026) [1080p] [WEBRip] [YTS.GG]</title>'
                    '<link>https://yts.gg/movies/fixture-2026</link>'
                    '<enclosure url="https://yts.gg/torrent/download/' + 'a' * 40 + '"/>'
                    '</item></channel></rss>')
        result = self.scan()
        self.assert_available(result)
        self.assertEqual(result['scan_stats']['rss_matches'], 1)

    def test_matching_title_cannot_override_a_confirmed_wrong_imdb(self):
        self.follow()
        self.page_imdb = 'tt00000001'
        self.results = [self.release('The Uprising (2026) 1080p WEBRip -YTS')]
        result = self.scan()
        self.assertEqual(result['movies'][0]['status'], 'watching')
        self.assertEqual(result['movies'][0]['best_release'], {})
        self.assertEqual(result['newly_available'], [])

    def test_unreadable_yts_identity_cannot_mark_a_movie_available(self):
        self.follow()
        self.page_error = True
        self.results = [self.release('The Uprising (2026) 1080p WEBRip -YTS')]
        self.assertEqual(self.scan()['movies'][0]['status'], 'watching')

    def test_second_scan_retries_an_identity_page_that_previously_failed(self):
        self.follow(title='Practical Magic 2', imdb='tt32588798')
        self.page_imdb = 'tt32588798'
        self.results = [self.release('Practical Magic 2 (2026) 1080p WEBRip -YTS')]
        self.page_error = True
        self.assertEqual(self.scan()['movies'][0]['status'], 'watching')
        self.page_error = False
        self.assert_available(self.scan())

    def test_unverified_target_cannot_mark_a_movie_available(self):
        self.follow(imdb='')
        self.results = [self.release()]
        result = self.scan()
        self.assertEqual(result['movies'][0]['status'], 'watching')
        self.assertEqual(result['scan_stats']['skipped']['unverified_identity'], 1)

    def test_quality_and_source_trust_still_reject_ineligible_releases(self):
        self.follow()
        for title, indexer in [
            ('The Rage (2026) 720p WEBRip -YTS', 'YTS'),
            ('The Rage (2026) 1080p HDCAM -YTS', 'YTS'),
            ('The Rage (2026) 1080p WEB-DL -YTS', 'YTS'),
            ('The Uprising (2026) 1080p WEBRip', 'Untrusted'),
        ]:
            with self.subTest(title=title, indexer=indexer):
                self.results = [self.release(title, indexer)]
                self.assertEqual(self.scan()['movies'][0]['status'], 'watching')

    def test_provider_failure_does_not_block_the_next_scan(self):
        self.follow(title='Practical Magic 2', imdb='tt32588798')
        self.page_imdb = 'tt32588798'
        self.search_error = True
        first = self.scan()
        self.assertEqual(first['movies'][0]['last_checked'], 0)
        self.assertEqual(first['scan_stats']['failed_searches'], 1)
        self.search_error = False
        self.results = [self.release('Practical Magic 2 (2026) 1080p WEBRip -YTS')]
        self.assert_available(self.scan())

    def test_rss_identity_outage_is_bounded_and_still_reaches_movie_search(self):
        self.follow(title='Practical Magic 2', imdb='tt32588798')
        self.page_imdb = 'tt32588798'
        self.results = [self.release('Practical Magic 2 (2026) 1080p WEBRip -YTS')]
        self.rss = '<rss><channel>' + ''.join(
            f'<item><title>Unrelated {i} (2026) [1080p] [WEBRip]</title>'
            f'<link>https://yts.gg/movies/rss-outage-{i}</link>'
            '<enclosure url="https://yts.gg/torrent/download/' + 'b' * 40 + '"/></item>'
            for i in range(100)) + '</channel></rss>'
        clock, spent = [100.0], [0.0]

        def outage(request, timeout=0):
            if '/movies/rss-outage-' in request.full_url:
                clock[0] += timeout
                spent[0] += timeout
                raise TimeoutError('Fixture page timeout')
            return self.provider(request, timeout)

        with patch('app.time.monotonic', side_effect=lambda: clock[0]), \
             patch('app.urllib.request.urlopen', side_effect=outage):
            result = self.scan()
        self.assert_available(result)
        self.assertLessEqual(spent[0], 3)
        self.assertEqual(result['scan_stats']['prowlarr_searches'], 1)

    def test_result_identity_reads_respect_the_movie_search_deadline(self):
        self.follow()
        self.results = [{**self.release(f'Unrelated {i} (2026) 1080p WEBRip -YTS'),
                         'infoUrl': f'https://yts.gg/movies/search-outage-{i}'} for i in range(100)]
        clock, spent = [100.0], [0.0]

        def outage(request, timeout=0):
            if '/movies/search-outage-' in request.full_url:
                clock[0] += timeout
                spent[0] += timeout
                raise TimeoutError('Fixture page timeout')
            return self.provider(request, timeout)

        with patch('app.time.monotonic', side_effect=lambda: clock[0]), \
             patch('app.urllib.request.urlopen', side_effect=outage):
            result = self.scan()
        self.assertEqual(result['movies'][0]['status'], 'watching')
        self.assertLessEqual(spent[0], 25)

    def test_short_rss_timeout_does_not_poison_longer_movie_search_verification(self):
        self.follow(title='Practical Magic 2', imdb='tt32588798')
        self.page_imdb = 'tt32588798'
        self.results = [self.release('Practical Magic 2 (2026) 1080p WEBRip -YTS')]
        self.rss = ('<rss><channel><item><title>Practical Magic 2 (2026) [1080p] [WEBRip]</title>'
                    '<link>https://yts.gg/movies/fixture-2026</link>'
                    '<enclosure url="https://yts.gg/torrent/download/' + 'a' * 40 + '"/>'
                    '</item></channel></rss>')
        clock = [100.0]

        def slow_identity(request, timeout=0):
            if '/movies/fixture-' in request.full_url:
                if timeout < 4:
                    clock[0] += timeout
                    raise TimeoutError('Fixture page needs four seconds')
                clock[0] += 4
            return self.provider(request, timeout)

        with patch('app.time.monotonic', side_effect=lambda: clock[0]), \
             patch('app.urllib.request.urlopen', side_effect=slow_identity):
            result = self.scan()
        self.assert_available(result)
        self.assertEqual(result['scan_stats']['rss_matches'], 0)
        self.assertEqual(result['scan_stats']['prowlarr_searches'], 1)


if __name__ == '__main__':
    unittest.main()
