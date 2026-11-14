import tempfile
import unittest
from unittest.mock import Mock

from services.ai_jobs import AIJobStore
from services.ai_provider import AISelection, AIProviderError
from services.chatgpt_skills import load
from services.chatgpt_transport import CompletedResponse, ToolCall
from services.chatgpt_youtube import YouTubeSearchJob
from services.youtube_movies import YouTubeMovieSearch
from tests.test_youtube_movies import MOVIE, video


class YouTubeJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = AIJobStore(self.temp.name)
        skill = load('F6')
        self.selection = AISelection('chatgpt', 1, 'account', 'fixture', skill['id'], '1', skill['hash'], 'F6')
        self.youtube = Mock(api_key='key', trailer_region='EG')
        self.youtube._request_json.return_value = {'items': []}
        self.search = YouTubeMovieSearch(self.youtube, lambda identity: MOVIE)
        self.session = self.search.search(tmdb_id='1')
        self.transport = Mock()
        self.transport.run.return_value = CompletedResponse('response', '', (),
            (ToolCall('one', 'cp_result.submit', {'queries': ['The Example cinema'], 'explanation': 'Try the alternate wording.'}),))
        self.permission = Mock()
        self.worker = YouTubeSearchJob(self.store, lambda selection, job_id: self.transport,
                                      self.search, check_permission=self.permission)

    def create(self):
        return self.store.create('F6', self.selection, {'search_id': self.session['search_id']}, 'request')

    def test_explicit_job_runs_one_model_call_and_returns_only_real_duration_matches(self):
        self.youtube._request_json.side_effect = [
            {'items': [{'id': {'videoId': 'aaaaaa1'}}, {'id': {'videoId': 'aaaaaa2'}}]},
            {'items': [video('aaaaaa1', 6000), video('aaaaaa2', 9000)]}]
        result = self.worker.run(self.create()['id'])
        self.assertEqual(result['state'], 'completed')
        self.assertEqual([v['video_id'] for v in result['output']['candidates']], ['aaaaaa1'])
        self.transport.run.assert_called_once()
        self.assertGreaterEqual(self.permission.call_count, 2)

    def test_malformed_output_never_searches_or_retries_inference(self):
        self.transport.run.return_value = CompletedResponse('response', 'made-up link', ())
        self.youtube._request_json.reset_mock()
        result = self.worker.run(self.create()['id'])
        self.assertEqual(result['state'], 'failed')
        self.assertEqual(result['message'], 'invalid_feature_result')
        self.youtube._request_json.assert_not_called()
        self.transport.run.assert_called_once()

    def test_permission_revocation_and_cancelled_job_make_no_inference(self):
        self.permission.side_effect = AIProviderError('consent_required')
        result = self.worker.run(self.create()['id'])
        self.assertEqual(result['message'], 'consent_required')
        self.transport.run.assert_not_called()

    def test_cancelled_before_start(self):
        job = self.create()
        self.store.cancel(job['id'], job['revision'])
        self.assertEqual(self.worker.run(job['id'])['state'], 'cancelled')
        self.transport.run.assert_not_called()

    def test_failed_second_query_returns_partial_real_results_and_keeps_error(self):
        from services.youtube_playlist import YouTubePlaylistError
        self.transport.run.return_value = CompletedResponse('response', '', (),
            (ToolCall('one', 'cp_result.submit', {'queries': ['first new query', 'second new query'], 'explanation': 'Try these.'}),))
        self.youtube._request_json.side_effect = [
            {'items': [{'id': {'videoId': 'aaaaaa1'}}]}, {'items': [video('aaaaaa1', 6000)]},
            YouTubePlaylistError('Search failed')]
        result = self.worker.run(self.create()['id'])
        self.assertEqual(result['state'], 'failed')
        self.assertEqual(result['message'], 'Search failed')
        self.assertEqual([v['video_id'] for v in result['output']['candidates']], ['aaaaaa1'])
