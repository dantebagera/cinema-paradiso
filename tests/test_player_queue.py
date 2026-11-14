import unittest
import sqlite3

from services.player_queue import PlayerQueue, collection_queue


class PlayerQueueTests(unittest.TestCase):
    def test_movie_order_deduplicates_versions_and_retains_missing_members(self):
        result = collection_queue({'name': 'Saga', 'parts': [
            {'tmdb_id': '3', 'title': 'Third', 'release_date': '2001-12-01'},
            {'tmdb_id': '1', 'title': 'First', 'release_date': '2001-01-01'},
            {'tmdb_id': '2', 'title': 'Second', 'year': '2001'},
        ]}, [
            {'path_key': 'a', 'tmdb_id': '1'},
            {'path_key': 'a2', 'tmdb_id': '1'},
            {'path_key': 'c', 'tmdb_id': '3'},
        ], current={'path_key': 'a2', 'tmdb_id': '1'})
        self.assertEqual([r['title'] for r in result['items']], ['Second', 'First', 'Third'])
        self.assertEqual(result['items'][1]['path_key'], 'a2')
        self.assertFalse(result['items'][0]['available'])
        self.assertIn('not available', result['items'][0]['reason'])

    def test_snapshot_names_current_item_and_keeps_unavailable_neighbor(self):
        owner = PlayerQueue(lambda media: {'title': 'Show', 'items': [
            {'path_key': 'e3', 'title': 'E3', 'available': True},
            {'path_key': 'e4', 'title': 'E4', 'available': False, 'reason': 'Missing'},
            {'path_key': 'e5', 'title': 'E5', 'available': True},
        ]})
        snapshot = owner.snapshot({'path_key': 'e3', 'title': 'E3'})
        self.assertEqual(snapshot['current_index'], 0)
        self.assertEqual(snapshot['items'][1]['reason'], 'Missing')
        self.assertEqual(len(snapshot['items']), 3)

    def test_metadata_failure_preserves_single_file_and_explains_failure(self):
        def fail(media):
            raise LookupError('metadata unavailable')
        snapshot = PlayerQueue(fail).snapshot({'path_key': 'movie', 'title': 'Film'})
        self.assertEqual(snapshot['items'][0]['path_key'], 'movie')
        self.assertTrue(snapshot['error'])

    def test_unknown_collection_date_follows_dated_movies(self):
        result = collection_queue({'parts': [
            {'tmdb_id': '2', 'title': 'Unknown'},
            {'tmdb_id': '1', 'title': 'Dated', 'year': '2000'},
        ]}, [], current={})
        self.assertEqual([r['title'] for r in result['items']], ['Dated', 'Unknown'])

    def test_oversized_queue_fails_visibly_without_partial_order(self):
        owner = PlayerQueue(lambda _: {'items': [
            {'path_key': str(i), 'title': 'x' * 500, 'available': True}
            for i in range(2000)]})
        result = owner.snapshot({'path_key': '0', 'title': 'Film'})
        self.assertEqual(len(result['items']), 1)
        self.assertIn('too large', result['error'])

    def test_curated_imdb_and_title_year_members_use_existing_identity_rules(self):
        result = collection_queue({'parts': [
            {'tmdb_id': '1', 'title': 'First', 'year': '2000'},
            {'imdb_id': 'tt0002', 'title': 'Second', 'year': '2001'},
            {'title': 'Third Film', 'year': '2002'},
            {'imdb_id': 'tt0004', 'title': 'Missing', 'year': '2003'},
        ]}, [{'path_key': 'a', 'tmdb_id': '1'},
             {'path_key': 'b', 'imdb_id': 'tt0002'},
             {'path_key': 'c', 'title': 'Third Film', 'year': '2002'}], current={'path_key': 'a'})
        self.assertEqual([row['path_key'] for row in result['items']][:3], ['a', 'b', 'c'])
        self.assertEqual(len(result['items']), 4)
        self.assertFalse(result['items'][-1]['available'])

    def test_queue_database_error_does_not_prevent_chosen_file_playback(self):
        def fail(media): raise sqlite3.OperationalError('database is locked')
        result = PlayerQueue(fail).snapshot({'path_key': 'a', 'title': 'Film'})
        self.assertEqual(result['items'][0]['path_key'], 'a')
        self.assertTrue(result['error'])


if __name__ == '__main__':
    unittest.main()
