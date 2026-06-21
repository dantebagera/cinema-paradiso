import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class CollectionResolutionApiTest(unittest.TestCase):
    def setUp(self):
        self.original_dirs = app._movies_dirs
        self.original_dir = app._movies_dir
        self.original_user_data_dir = app._user_data_dir
        self.original_library_cache = dict(app._library_cache)

    def tearDown(self):
        app._movies_dirs = self.original_dirs
        app._movies_dir = self.original_dir
        app._user_data_dir = self.original_user_data_dir
        app._library_cache = self.original_library_cache

    def test_library_collection_returns_owned_paths_and_unresolved_parts(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            owned = Path(movies_tmp) / "Star Wars.1977.mkv"
            owned.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            collection = {
                "id": "10",
                "name": "Star Wars Collection",
                "parts": [
                    {"tmdb_id": "11", "title": "Star Wars", "year": "1977"},
                    {"tmdb_id": "181808", "title": "Star Wars: The Last Jedi", "year": "2017"},
                ],
            }
            app._library_cache = {"items": [{
                "path": str(owned),
                "tmdb_id": "11",
                "canonical_metadata": {"accepted": True, "tmdb_id": "11", "title": "Star Wars", "year": "1977"},
            }], "dir": app._library_cache_key(), "time": app.time.time()}
            with patch("app._effective_tmdb_collection", return_value=collection):
                response = app.app.test_client().get("/api/library/collection/10")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["owned_paths"], [str(owned)])
        self.assertEqual(payload["unresolved_parts"][0]["tmdb_id"], "181808")


if __name__ == "__main__":
    unittest.main()
