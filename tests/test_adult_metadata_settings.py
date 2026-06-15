import json
import unittest
from unittest.mock import patch

import app


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class AdultMetadataSettingsTest(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        self.original_tmdb_key = app._tmdb_key
        self.original_tmdb_include_adult = getattr(app, "_tmdb_include_adult", False)
        self.original_library_show_adult = getattr(app, "_library_show_adult", True)
        self.original_movies_dirs = list(app._movies_dirs)
        self.original_movies_dir = app._movies_dir
        self.original_tmdb_genres = dict(app._tmdb_genres)

    def tearDown(self):
        app._tmdb_key = self.original_tmdb_key
        app._tmdb_include_adult = self.original_tmdb_include_adult
        app._library_show_adult = self.original_library_show_adult
        app._movies_dirs = self.original_movies_dirs
        app._movies_dir = self.original_movies_dir
        app._tmdb_genres = self.original_tmdb_genres

    def test_tmdb_config_saves_adult_metadata_search_setting(self):
        with patch.object(app, "_save_config") as save_config:
            response = self.client.post(
                "/api/tmdb/config",
                json={"key": "abc123", "include_adult": True},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(app._tmdb_include_adult)
        self.assertTrue(save_config.called)
        self.assertTrue(self.client.get("/api/tmdb/config").get_json()["include_adult"])

    def test_library_config_saves_movie_view_adult_visibility_setting(self):
        with patch.object(app.os.path, "isdir", return_value=True), patch.object(app, "_save_config") as save_config:
            response = self.client.post(
                "/api/config",
                json={"directories": [r"E:\Movies"], "show_adult_movies": False},
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(app._library_show_adult)
        self.assertTrue(save_config.called)
        self.assertFalse(self.client.get("/api/config").get_json()["show_adult_movies"])

    def test_tmdb_search_uses_saved_adult_setting_by_default(self):
        app._tmdb_key = "tmdb-key"
        app._tmdb_include_adult = True
        app._tmdb_genres = {}
        seen_urls = []

        def fake_urlopen(request, timeout=0):
            seen_urls.append(request.full_url)
            return FakeResponse({"results": [], "total_pages": 1, "total_results": 0})

        with patch.object(app, "_ensure_tmdb_genres"), patch.object(app.urllib.request, "urlopen", side_effect=fake_urlopen):
            response = self.client.get("/api/tmdb/search?q=shining+sex&page=1")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(seen_urls)
        self.assertIn("include_adult=true", seen_urls[0])

    def test_tmdb_search_can_force_discover_safe_adult_setting(self):
        app._tmdb_key = "tmdb-key"
        app._tmdb_include_adult = True
        app._tmdb_genres = {}
        seen_urls = []

        def fake_urlopen(request, timeout=0):
            seen_urls.append(request.full_url)
            return FakeResponse({"results": [], "total_pages": 1, "total_results": 0})

        with patch.object(app, "_ensure_tmdb_genres"), patch.object(app.urllib.request, "urlopen", side_effect=fake_urlopen):
            response = self.client.get("/api/tmdb/search?q=shining+sex&page=1&include_adult=false")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(seen_urls)
        self.assertIn("include_adult=false", seen_urls[0])

    def test_tmdb_search_forwards_year_as_structured_parameter(self):
        app._tmdb_key = "tmdb-key"
        app._tmdb_include_adult = True
        app._tmdb_genres = {}
        seen_urls = []

        def fake_urlopen(request, timeout=0):
            seen_urls.append(request.full_url)
            return FakeResponse({"results": [], "total_pages": 1, "total_results": 0})

        with patch.object(app, "_ensure_tmdb_genres"), patch.object(app.urllib.request, "urlopen", side_effect=fake_urlopen):
            response = self.client.get("/api/tmdb/search?q=Shining+Sex&page=1&year=1976")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(seen_urls)
        self.assertIn("query=Shining+Sex", seen_urls[0])
        self.assertIn("year=1976", seen_urls[0])
        self.assertNotIn("query=Shining+Sex+1976", seen_urls[0])

    def test_canonical_tmdb_metadata_preserves_adult_flag(self):
        canonical = app._build_canonical_metadata(
            {"parsed_title": "Shining Sex", "parsed_year": "1976"},
            tmdb_data={
                "tmdb_id": "346011",
                "title": "Shining Sex",
                "year": "1976",
                "adult": True,
                "match_source": "auto_tmdb",
            },
        )

        self.assertTrue(canonical["accepted"])
        self.assertTrue(canonical["adult"])


if __name__ == "__main__":
    unittest.main()
