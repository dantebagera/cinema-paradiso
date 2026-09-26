import unittest
from types import SimpleNamespace

from flask import Flask

from services.tv_routes import register_tv_routes


class TVRelationshipRouteTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def request(path, **params):
            self.calls.append((path, params.get('page')))
            if path.endswith('/recommendations'):
                ids = [101, 102]
            elif path.endswith('/similar'):
                ids = [102, 103]
            else:
                raise AssertionError(f'Unexpected provider path: {path}')
            return {'results': [{'id': identity, 'name': f'Series {identity}', 'first_air_date': '2024-01-01', 'vote_average': 7.5} for identity in ids], 'total_pages': 1, 'total_results': len(ids)}

        metadata = SimpleNamespace(request=request, normalize=lambda row: {'tmdb_id': row['id'], 'title': row['name'], 'poster_url': ''})
        self.metadata = metadata
        search = SimpleNamespace(local_rows=lambda: [{'tmdb_id': 102, 'id': 42, 'available_count': 3}])
        app = Flask(__name__)
        register_tv_routes(app, lambda: {'metadata': metadata, 'search': search}, lambda: True, None)
        self.client = app.test_client()

    def test_tv_recommendations_use_tv_provider_and_local_tv_availability(self):
        response = self.client.get('/api/tv/related?tmdb_id=77&source=recommendations')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.calls, [('/tv/77/recommendations', 1)])
        self.assertEqual([row['tmdb_id'] for row in response.json['results']], [101, 102])
        self.assertEqual(response.json['results'][1]['id'], 42)
        self.assertEqual(response.json['results'][1]['available_count'], 3)
        self.assertEqual(response.json['results'][1]['media_type'], 'tv')

    def test_all_deduplicates_sources_and_invalid_source_never_calls_provider(self):
        response = self.client.get('/api/tv/related?tmdb_id=77&source=all')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['tmdb_id'] for row in response.json['results']], [101, 102, 103])
        self.assertEqual(self.calls, [('/tv/77/recommendations', 1), ('/tv/77/similar', 1)])
        self.assertEqual(self.client.get('/api/tv/related?tmdb_id=77&source=movies').status_code, 400)
        self.assertEqual(len(self.calls), 2)

    def test_provider_failure_is_redacted_and_can_retry(self):
        normal = self.metadata.request
        self.metadata.request = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('private provider address'))
        response = self.client.get('/api/tv/related?tmdb_id=78&source=similar')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private provider address', response.json['error'])
        self.metadata.request = normal
        self.assertEqual(self.client.get('/api/tv/related?tmdb_id=78&source=similar').status_code, 200)


if __name__ == '__main__':
    unittest.main()
