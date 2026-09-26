import concurrent.futures
import time
import unittest
from unittest.mock import patch
from services.movie_relationships import MovieRelationships


class MovieRelationshipTests(unittest.TestCase):
    def test_sources_cache_and_deduplicate_by_identity(self):
        calls = []
        def fetch(movie, source, page):
            calls.append((movie, source, page))
            return {'results': [{'id': 1}, {'id': 2}, {'id': 2}, {'id': 3}], 'total_pages': 2}
        cache = MovieRelationships()
        normalize = lambda item: {'tmdb_id': str(item['id'])}
        result = cache.page('1', 'recommendations', 1, fetch, normalize)
        self.assertEqual([item['tmdb_id'] for item in result['results']], ['2', '3'])
        self.assertEqual(result['results'][0]['relationship_source'], 'recommendations')
        cache.page('1', 'recommendations', 1, fetch, normalize)
        cache.page('1', 'similar', 1, fetch, normalize)
        self.assertEqual(len(calls), 2)

    def test_concurrent_requests_share_fetch_and_failure_is_retryable(self):
        calls = []
        def fetch(*args):
            calls.append(args)
            time.sleep(.04)
            return {'results': []}
        cache = MovieRelationships()
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            list(pool.map(lambda _: cache.page('2', 'similar', 1, fetch, dict), range(4)))
        self.assertEqual(len(calls), 1)
        def fail(*args):
            raise OSError('offline')
        with self.assertRaises(OSError):
            cache.page('3', 'similar', 1, fail, dict)
        self.assertEqual(cache.page('3', 'similar', 1, fetch, dict)['results'], [])

    def test_invalid_inputs_do_not_reach_provider(self):
        for movie, source, page in [('0', 'similar', 1), ('../1', 'similar', 1), ('1', 'all', 1), ('1', 'similar', 501)]:
            with self.assertRaises(ValueError):
                MovieRelationships().page(movie, source, page, None, None)

    def test_all_is_lazy_deduplicated_and_caps_provider_pages(self):
        calls = []
        def fetch(movie, source, page):
            calls.append((source, page))
            start = 1 if source == 'recommendations' else 15
            return {
                'results': [{'id': start + page * 20 + index} for index in range(20)],
                'total_pages': 999,
                'total_results': 19980,
            }
        result = MovieRelationships().listing(
            '1', 'all', 1, fetch,
            lambda item: {'tmdb_id': str(item['id'])},
        )
        self.assertEqual(len(result['results']), 20)
        self.assertTrue(result['has_next'])
        self.assertIsNone(result['total_pages'])
        self.assertEqual(calls, [('recommendations', 1), ('recommendations', 2)])

    def test_route_contract_uses_transient_owner_and_redacts_provider_failures(self):
        import app
        with patch.object(app, '_tmdb_key', 'fixture'), patch.object(app, '_movie_relationships', MovieRelationships()), patch.object(app, '_fetch_movie_relationship_page') as fetch:
            fetch.return_value = {'results': [{'id': 88, 'title': 'Related', 'release_date': '2020-01-01', 'vote_average': 7.2}], 'total_pages': 1, 'total_results': 1}
            client = app.app.test_client()
            response = client.get('/api/tmdb/related?tmdb_id=77&source=similar&page=1')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(str(response.json['results'][0]['tmdb_id']), '88')
            self.assertEqual(response.json['source'], 'similar')
            self.assertEqual(client.get('/api/tmdb/related?tmdb_id=77&source=all').status_code, 200)
            fetch.side_effect = RuntimeError('secret URL must not be exposed')
            response = client.get('/api/tmdb/related?tmdb_id=78&source=recommendations')
            self.assertEqual(response.status_code, 502)
            self.assertNotIn('secret', response.json['error'])


if __name__ == '__main__':
    unittest.main()
