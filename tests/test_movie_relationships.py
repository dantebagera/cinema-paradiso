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

    def test_bounded_sources_and_all_backfill_duplicate_similar_movies(self):
        calls = []
        def fetch(movie, source, page):
            calls.append((source, page))
            identities = range(1, 151) if source == 'recommendations' else range(50, 250)
            identities = list(identities)
            start = (page - 1) * 20
            return {
                'results': [{'id': identity} for identity in identities[start:start + 20]],
                'total_pages': (len(identities) + 19) // 20,
                'total_results': len(identities),
            }
        relationships = MovieRelationships()
        normalize = lambda item: {'tmdb_id': str(item['id'])}
        first = relationships.listing('9999', 'all', 1, fetch, normalize, page_size=39)
        self.assertEqual(len(first['results']), 39)
        self.assertEqual(first['results'][0]['tmdb_id'], '1')
        self.assertEqual(first['source_limit'], 100)
        self.assertIsNone(first['total_results'])
        self.assertEqual(calls, [('recommendations', 1), ('recommendations', 2)])

        summary = relationships.summary('9999', 'all', fetch, normalize, page_size=39)
        self.assertEqual(summary['total_results'], 200)
        self.assertEqual(summary['total_pages'], 6)
        self.assertEqual(summary['source_counts'], {'recommendations': 100, 'similar': 100})
        last = relationships.listing('9999', 'all', 6, fetch, normalize, page_size=39)
        self.assertEqual(len(last['results']), 5)
        self.assertFalse(last['has_next'])
        self.assertEqual(last['total_results'], 200)
        self.assertEqual(last['results'][-1]['tmdb_id'], '200')
        self.assertEqual(
            len({item['tmdb_id'] for page in range(1, 7)
                 for item in relationships.listing('9999', 'all', page, fetch, normalize, page_size=39)['results']}),
            200,
        )

        for source, first_id in [('recommendations', '1'), ('similar', '50')]:
            source_summary = relationships.summary('9999', source, fetch, normalize, page_size=39)
            self.assertEqual(source_summary['total_results'], 100)
            self.assertEqual(source_summary['total_pages'], 3)
            source_first = relationships.listing('9999', source, 1, fetch, normalize, page_size=39)
            source_last = relationships.listing('9999', source, 3, fetch, normalize, page_size=39)
            self.assertEqual(source_first['results'][0]['tmdb_id'], first_id)
            self.assertEqual(len(source_last['results']), 22)
            self.assertFalse(source_last['has_next'])

    def test_short_sources_have_exact_smaller_total(self):
        def fetch(movie, source, page):
            ids = [1, 2, 3, 4, 5] if source == 'recommendations' else [4, 5, 6, 7]
            return {'results': [{'id': identity} for identity in ids], 'total_pages': 1}
        relationships = MovieRelationships()
        normalize = lambda item: {'tmdb_id': str(item['id'])}
        summary = relationships.summary('1', 'all', fetch, normalize, page_size=3)
        self.assertEqual(summary['source_counts'], {'recommendations': 4, 'similar': 2})
        self.assertEqual(summary['total_results'], 6)
        self.assertEqual(summary['total_pages'], 2)
        last = relationships.listing('1', 'all', 2, fetch, normalize, page_size=3)
        self.assertEqual([item['tmdb_id'] for item in last['results']], ['5', '6', '7'])
        self.assertFalse(last['has_next'])

    def test_page_boundary_inside_final_provider_page_does_not_claim_partial_total(self):
        def fetch(movie, source, page):
            return {'results': [{'id': identity} for identity in range(2, 22)], 'total_pages': 1}
        relationships = MovieRelationships()
        normalize = lambda item: {'tmdb_id': str(item['id'])}
        first = relationships.listing('1', 'recommendations', 1, fetch, normalize, page_size=10)
        self.assertEqual(len(first['results']), 10)
        self.assertTrue(first['has_next'])
        self.assertIsNone(first['total_results'])
        self.assertEqual(relationships.summary('1', 'recommendations', fetch, normalize, page_size=10)['total_results'], 20)

    def test_summary_failure_does_not_block_healthy_first_page(self):
        def fetch(movie, source, page):
            if source == 'similar':
                raise OSError('similar offline')
            return {'results': [{'id': (page - 1) * 20 + index} for index in range(2, 22)], 'total_pages': 10}
        relationships = MovieRelationships()
        normalize = lambda item: {'tmdb_id': str(item['id'])}
        first = relationships.listing('9999', 'all', 1, fetch, normalize)
        self.assertEqual(len(first['results']), 20)
        with self.assertRaises(OSError):
            relationships.summary('9999', 'all', fetch, normalize)
        self.assertEqual(len(relationships.listing('9999', 'all', 1, fetch, normalize)['results']), 20)

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
            summary = client.get('/api/tmdb/related?tmdb_id=77&source=all&page_size=39&summary=1')
            self.assertEqual(summary.status_code, 200)
            self.assertEqual(summary.json['total_results'], 1)
            self.assertEqual(summary.json['source_counts'], {'recommendations': 1, 'similar': 0})
            fetch.side_effect = RuntimeError('secret URL must not be exposed')
            response = client.get('/api/tmdb/related?tmdb_id=78&source=recommendations')
            self.assertEqual(response.status_code, 502)
            self.assertNotIn('secret', response.json['error'])


if __name__ == '__main__':
    unittest.main()
