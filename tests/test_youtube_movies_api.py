import unittest
from types import SimpleNamespace
from unittest.mock import patch
import app
from services.youtube_playlist import YouTubePlaylistError
from services.youtube_movies import YouTubeMovieSearch
from tests.test_youtube_movies import MOVIE, video


class YouTubeMovieApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_route_returns_filtered_result_without_ai(self):
        with patch.object(app._youtube_service, 'api_key', 'fixture'), \
             patch.object(app._youtube_service, '_request_json', side_effect=[
                 {'items': [{'id': {'videoId': 'aaaaaa1'}}, {'id': {'videoId': 'aaaaaa2'}}]},
                 {'items': [video('aaaaaa1', 6000), video('aaaaaa2', 6301)]}]), \
             patch.object(app, '_get_chatgpt_transport') as inference:
            search = YouTubeMovieSearch(app._youtube_service, lambda identity: MOVIE)
            with patch.object(app, '_youtube_movie_search', search):
                result = self.client.post('/api/youtube/movie-search', json={'tmdb_id': '1'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual([v['video_id'] for v in result.json['candidates']], ['aaaaaa1'])
        inference.assert_not_called()

    def test_error_not_reported_as_empty_and_cross_site_rejected(self):
        with patch.object(app._youtube_movie_search, 'search', side_effect=YouTubePlaylistError('Search unavailable')):
            result = self.client.post('/api/youtube/movie-search', json={'tmdb_id': '1'})
        self.assertEqual(result.status_code, 422)
        self.assertIn('Search unavailable', result.json['error']['message'])
        self.assertEqual(self.client.post('/api/youtube/movie-search', json={'tmdb_id': '1'},
            headers={'Origin': 'https://unrelated.example'}).status_code, 403)

    def test_client_cannot_override_runtime_or_submit_arbitrary_gpt_prompt(self):
        self.assertEqual(self.client.post('/api/youtube/movie-search',
            json={'tmdb_id': '1', 'runtime': 100}).status_code, 400)
        self.assertEqual(self.client.post('/api/ai/youtube/movie-search',
            json={'search_id': 'id', 'request_key': 'key', 'prompt': 'anything'}).status_code, 400)

    def test_status_reads_partial_results_without_search_or_inference(self):
        with patch.object(app._youtube_movie_search, 'snapshot', return_value={'search_id': 'one', 'candidates': []}), \
             patch.object(app._youtube_movie_search, 'search') as search:
            result = self.client.post('/api/youtube/movie-search/status', json={'search_id': 'one'})
        self.assertEqual(result.status_code, 200)
        search.assert_not_called()

    def test_explicit_gpt_route_uses_selected_feature_and_existing_job_owner(self):
        from flask import Flask
        from unittest.mock import Mock
        from services.youtube_movie_routes import register_youtube_movie_routes
        search, provider, jobs, permission = Mock(), Mock(), Mock(), Mock()
        provider.snapshot.return_value = SimpleNamespace(provider='chatgpt')
        jobs.store.create.return_value = {'id': 'job', 'state': 'queued'}
        web = Flask(__name__)
        register_youtube_movie_routes(web, lambda: search, provider, lambda: jobs, permission)
        response = web.test_client().post('/api/ai/youtube/movie-search', json={'search_id': 'search', 'request_key': 'once'})
        self.assertEqual(response.status_code, 202)
        provider.snapshot.assert_called_once_with('F6', domain_id='search')
        permission.assert_called_once_with(provider.snapshot.return_value)
        jobs.store.create.assert_called_once_with('F6', provider.snapshot.return_value, {'search_id': 'search'}, 'once')
        jobs.start.assert_called_once_with('job')
        search.search.assert_not_called()

    def test_gpt_route_rejects_other_provider_before_starting_job(self):
        from flask import Flask
        from unittest.mock import Mock
        from services.youtube_movie_routes import register_youtube_movie_routes
        provider, jobs = Mock(), Mock()
        provider.snapshot.return_value = SimpleNamespace(provider='ollama')
        web = Flask(__name__)
        register_youtube_movie_routes(web, Mock(), provider, lambda: jobs, Mock())
        response = web.test_client().post('/api/ai/youtube/movie-search', json={'search_id': 'search', 'request_key': 'once'})
        self.assertEqual(response.status_code, 409)
        jobs.start.assert_not_called()
