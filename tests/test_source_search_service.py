import json
import unittest
from unittest.mock import Mock

from services.source_search import ProwlarrClient


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class ProwlarrClientTest(unittest.TestCase):
    def test_search_encodes_repeated_indexers_through_one_transport(self):
        opener = Mock(return_value=_Response([{'title': 'Alien.1979.1080p'}]))
        client = ProwlarrClient('http://127.0.0.1:9696/', 'secret', opener=opener)

        rows = client.search(query='Alien 1979', indexer_ids=['1', '7'], limit=50)

        self.assertEqual(rows[0]['title'], 'Alien.1979.1080p')
        request = opener.call_args.args[0]
        self.assertIn('query=Alien+1979', request.full_url)
        self.assertIn('indexerIds=1', request.full_url)
        self.assertIn('indexerIds=7', request.full_url)
        self.assertEqual(request.headers['X-api-key'], 'secret')

    def test_enabled_indexers_normalizes_ids_and_ignores_disabled_rows(self):
        opener = Mock(return_value=_Response([
            {'id': 4, 'name': 'YTS', 'enable': True},
            {'id': 8, 'name': 'Disabled', 'enable': False},
        ]))
        client = ProwlarrClient('http://127.0.0.1:9696', 'secret', opener=opener)

        self.assertEqual(client.enabled_indexers(), [{'id': '4', 'name': 'YTS'}])


if __name__ == '__main__':
    unittest.main()
