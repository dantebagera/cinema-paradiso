import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app


class QueueProjectionTests(unittest.TestCase):
    def test_local_legacy_collection_member_is_playable_in_queue(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = Path(temporary) / 'First.mkv', Path(temporary) / 'Second.mkv'
            first.write_bytes(b'fixture')
            second.write_bytes(b'fixture')
            collection = {'id': '7', 'name': 'Curated saga', 'parts': [
                {'tmdb_id': '1', 'title': 'First', 'year': '2000'},
                {'imdb_id': 'tt0002', 'title': 'Second', 'year': '2001'}]}
            legacy = {'path': str(second), 'title': 'Second', 'year': '2001', 'imdb_id': 'tt0002'}
            class Store:
                def collection_lookup(self, _):
                    return [], [{'path': str(first), 'tmdb_id': '1'}], [{'path': str(second)}]
            store = SimpleNamespace(catalog=SimpleNamespace(store=Store()))
            curation = SimpleNamespace(effective_collection=lambda value: value)
            with patch.object(app, '_metadata_store', return_value=store), \
                 patch.object(app, '_catalog_library_item', return_value=legacy), \
                 patch.object(app, '_library_collection_from_catalog', return_value=collection), \
                 patch.object(app, '_tmdb_collection_cache', {'7': {'data': collection}}), \
                 patch.object(app, '_curation_store', return_value=curation):
                result = app._player_queue_projection({'collection_id': '7', 'path_key': app._norm(str(first)),
                                                       'path': str(first), 'tmdb_id': '1'})
            self.assertEqual(len(result['items']), 2)
            self.assertTrue(result['items'][1]['available'])
            self.assertEqual(result['items'][1]['path_key'], app._norm(str(second)))


if __name__ == '__main__': unittest.main()
