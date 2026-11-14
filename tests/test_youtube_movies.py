import unittest
from unittest.mock import Mock

from services.youtube_playlist import YouTubePlaylistError
from services.youtube_movies import YouTubeMovieSearch


MOVIE = {'id': 1, 'title': 'The Example', 'original_title': 'The Example',
         'original_language': 'en', 'runtime': 100, 'release_date': '2001-01-01'}


def video(identity, seconds, title='The Example full movie', **extra):
    return {'id': identity, 'snippet': {'title': title, 'channelTitle': extra.get('channel', 'Anyone'),
                                     'description': ''},
            'contentDetails': {'duration': f'PT{seconds}S', **extra.get('content', {})},
            'status': {'embeddable': extra.get('embeddable', True)}}


class MovieSearchTests(unittest.TestCase):
    def setUp(self):
        self.youtube = Mock(api_key='configured', trailer_region='EG')
        self.details = Mock(return_value=MOVIE)
        self.owner = YouTubeMovieSearch(self.youtube, self.details)

    def pages(self, videos, token=''):
        self.youtube._request_json.side_effect = [
            {'items': [{'id': {'videoId': v['id']}} for v in videos], 'nextPageToken': token},
            {'items': videos}]

    def test_inclusive_five_percent_uses_actual_duration_not_title(self):
        self.pages([video('aaaaaa1', 5699), video('aaaaaa2', 5700), video('aaaaaa3', 6300),
                    video('aaaaaa4', 6301), video('aaaaaa5', 120, 'The Example 100 minutes')])
        result = self.owner.search(tmdb_id='1')
        self.assertEqual({v['video_id'] for v in result['candidates']}, {'aaaaaa2', 'aaaaaa3'})
        self.assertEqual(result['runtime_seconds'], 6000)
        self.assertEqual(result['duration_range'], [5700, 6300])

    def test_arabic_original_and_aliases_never_search_english(self):
        self.details.return_value = {**MOVIE, 'title': 'Terrorism and Kebab', 'original_title': 'الإرهاب والكباب',
            'original_language': 'ar', 'alternative_titles': {'titles': [{'title': 'الارهاب والكباب'}]}}
        self.youtube._request_json.return_value = {'items': []}
        result = self.owner.search(tmdb_id='1')
        while result['has_more']:
            result = self.owner.search(search_id=result['search_id'])
        queries = [c.args[1]['q'] for c in self.youtube._request_json.call_args_list]
        self.assertTrue(queries)
        self.assertTrue(all('كباب' in q and 'Terrorism' not in q for q in queries))

    def test_arabic_translation_used_when_original_is_romanized(self):
        self.details.return_value = {**MOVIE, 'original_title': 'El Example', 'original_language': 'ar',
            'translations': {'translations': [{'iso_639_1': 'ar', 'data': {'title': 'الفيلم'}}]}}
        self.youtube._request_json.return_value = {'items': []}
        self.owner.search(tmdb_id='1')
        self.assertIn('الفيلم', self.youtube._request_json.call_args.args[1]['q'])

    def test_missing_arabic_title_or_runtime_never_relaxes_filter(self):
        for changes in ({'runtime': None}, {'runtime': float('nan')}, {'runtime': 0},
                        {'original_language': 'ar', 'original_title': 'Romanized'}):
            with self.subTest(changes=changes):
                self.details.return_value = {**MOVIE, **changes}
                with self.assertRaises(YouTubePlaylistError):
                    self.owner.search(tmdb_id='1')
        self.youtube._request_json.assert_not_called()

    def test_unknown_duration_excluded_but_uploader_and_embedding_do_not_filter(self):
        missing = video('aaaaaa3', 6000)
        missing['contentDetails'] = {}
        self.pages([video('aaaaaa1', 6000, channel='Official Studio'),
                    video('aaaaaa2', 6000, channel='Unknown uploader', embeddable=False), missing])
        result = self.owner.search(tmdb_id='1')
        self.assertEqual([v['video_id'] for v in result['candidates']], ['aaaaaa1', 'aaaaaa2'])
        self.assertFalse(result['candidates'][1]['embeddable'])
        params = self.youtube._request_json.call_args_list[0].args[1]
        for key in ('channelId', 'videoLicense', 'videoEmbeddable', 'regionCode'):
            self.assertNotIn(key, params)

    def test_more_appends_deduplicates_and_uses_real_page_tokens(self):
        self.pages([video('aaaaaa1', 6000)], 'page-two')
        first = self.owner.search(tmdb_id='1')
        self.pages([video('aaaaaa1', 6000), video('aaaaaa2', 6000)])
        second = self.owner.search(search_id=first['search_id'])
        self.assertEqual(len(second['candidates']), 2)
        self.assertTrue(any(c.args[1].get('pageToken') == 'page-two'
                            for c in self.youtube._request_json.call_args_list))
        self.details.assert_called_once_with('1')

    def test_failure_keeps_page_pending_and_previous_results(self):
        self.pages([video('aaaaaa1', 6000)], 'page-two')
        first = self.owner.search(tmdb_id='1')
        self.youtube._request_json.side_effect = YouTubePlaylistError('Unavailable')
        with self.assertRaises(YouTubePlaylistError):
            self.owner.search(search_id=first['search_id'])
        self.assertEqual(len(self.owner.snapshot(first['search_id'])['candidates']), 1)
        self.pages([video('aaaaaa2', 6000)])
        result = self.owner.search(search_id=first['search_id'])
        self.assertEqual(len(result['candidates']), 2)
        self.assertEqual(self.youtube._request_json.call_args_list[-2].args[1]['pageToken'], 'page-two')

    def test_missing_key_expired_session_and_invalid_id_are_errors(self):
        self.youtube.api_key = ''
        with self.assertRaisesRegex(YouTubePlaylistError, 'Settings'):
            self.owner.search(tmdb_id='1')
        self.youtube.api_key = 'key'
        with self.assertRaises(YouTubePlaylistError):
            self.owner.search(tmdb_id='../bad')
        with self.assertRaisesRegex(YouTubePlaylistError, 'expired'):
            self.owner.snapshot('missing')

    def test_assisted_queries_still_enforce_duration_and_arabic(self):
        self.details.return_value = {**MOVIE, 'original_language': 'ar', 'original_title': 'الفيلم'}
        self.youtube._request_json.return_value = {'items': []}
        first = self.owner.search(tmdb_id='1')
        with self.assertRaisesRegex(YouTubePlaylistError, 'Arabic'):
            self.owner.search_queries(first['search_id'], ['English title'], lambda: False)
        self.pages([video('aaaaaa1', 6000, 'الفيلم'), video('aaaaaa2', 7000, 'الفيلم')])
        result = self.owner.search_queries(first['search_id'], ['الفيلم كامل قديم'], lambda: False)
        self.assertEqual([v['video_id'] for v in result['candidates']], ['aaaaaa1'])

    def test_cancelled_assisted_search_makes_no_requests(self):
        self.youtube._request_json.return_value = {'items': []}
        first = self.owner.search(tmdb_id='1')
        self.youtube._request_json.reset_mock()
        self.owner.search_queries(first['search_id'], ['The Example movie'], lambda: True)
        self.youtube._request_json.assert_not_called()

    def test_mixed_arabic_title_does_not_include_english_translation_in_queries(self):
        self.details.return_value = {**MOVIE, 'original_language': 'ar', 'original_title': 'الفيلم (The Example)'}
        self.youtube._request_json.return_value = {'items': []}
        result = self.owner.search(tmdb_id='1')
        self.assertNotIn('Example', result['queries'][0])
        self.assertIn('الفيلم', result['queries'][0])

    def test_failed_assisted_query_and_unattempted_queries_are_retryable_without_more_gpt(self):
        self.youtube._request_json.return_value = {'items': []}
        first = self.owner.search(tmdb_id='1')
        self.youtube._request_json.side_effect = [
            {'items': [{'id': {'videoId': 'aaaaaa1'}}]}, {'items': [video('aaaaaa1', 6000)]},
            YouTubePlaylistError('Unavailable')]
        with self.assertRaises(YouTubePlaylistError):
            self.owner.search_queries(first['search_id'], ['alternate one', 'alternate two', 'alternate three'], lambda: False)
        self.assertEqual(len(self.owner.snapshot(first['search_id'])['candidates']), 1)
        self.youtube._request_json.side_effect = None
        self.youtube._request_json.return_value = {'items': []}
        self.owner.search(search_id=first['search_id'])
        self.assertEqual(self.youtube._request_json.call_args.args[1]['q'], 'alternate two')
        self.owner.search(search_id=first['search_id'])
        self.assertEqual(self.youtube._request_json.call_args.args[1]['q'], 'alternate three')

    def test_cancel_during_upstream_response_does_not_commit_a_late_result(self):
        self.youtube._request_json.return_value = {'items': []}
        first = self.owner.search(tmdb_id='1')
        cancelled = [False]
        def response(path, params):
            if path == 'search':
                return {'items': [{'id': {'videoId': 'aaaaaa1'}}]}
            cancelled[0] = True
            return {'items': [video('aaaaaa1', 6000)]}
        self.youtube._request_json.side_effect = response
        result = self.owner.search_queries(first['search_id'], ['alternate one'], lambda: cancelled[0])
        self.assertEqual(result['candidates'], [])


if __name__ == '__main__':
    unittest.main()
