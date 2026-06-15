import json
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import app


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class ExploreBrowseIndexerScopeTest(unittest.TestCase):
    def setUp(self):
        self.original_url = app._prowlarr_url
        self.original_key = app._prowlarr_key
        self.original_tmdb_key = app._tmdb_key
        app._prowlarr_url = "http://prowlarr.test"
        app._prowlarr_key = "prowlarr-key"
        app._tmdb_key = ""

    def tearDown(self):
        app._prowlarr_url = self.original_url
        app._prowlarr_key = self.original_key
        app._tmdb_key = self.original_tmdb_key

    def test_browse_latest_scopes_prowlarr_search_to_selected_indexer(self):
        requested_searches = []

        def fake_urlopen(request, timeout=0):
            url = request.full_url
            if url.endswith("/api/v1/indexer"):
                return FakeResponse([
                    {"id": 1, "name": "Slow Indexer", "enable": True},
                    {"id": 2, "name": "YTS", "enable": True},
                ])
            if "/api/v1/search" in url:
                requested_searches.append(url)
                return FakeResponse([])
            raise AssertionError(f"Unexpected URL: {url}")

        with patch("app.urllib.request.urlopen", side_effect=fake_urlopen):
            response = app.app.test_client().get("/api/explore/browse?latest=1&indexer_id=2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(requested_searches), 2)
        for url in requested_searches:
            query = parse_qs(urlparse(url).query)
            self.assertEqual(query.get("indexerIds"), ["2"])

    def test_indexers_endpoint_returns_enabled_indexers_before_browse_load(self):
        def fake_urlopen(request, timeout=0):
            self.assertTrue(request.full_url.endswith("/api/v1/indexer"))
            return FakeResponse([
                {"id": 1, "name": "Disabled", "enable": False},
                {"id": 2, "name": "YTS", "enable": True},
            ])

        with patch("app.urllib.request.urlopen", side_effect=fake_urlopen):
            response = app.app.test_client().get("/api/explore/indexers")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["indexers"], [{"id": "2", "name": "YTS"}])


if __name__ == "__main__":
    unittest.main()
