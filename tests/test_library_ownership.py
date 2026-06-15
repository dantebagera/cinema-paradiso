import tempfile
import unittest
from pathlib import Path

import app


class LibraryOwnershipTest(unittest.TestCase):
    def test_library_check_matches_by_tmdb_id_before_title(self):
        original_dirs = app._movies_dirs
        original_dir = app._movies_dir
        original_user_data_dir = app._user_data_dir
        original_library_cache = dict(app._library_cache)
        original_plex_cache = dict(app._plex_cache)
        original_plex_by_fname = dict(app._plex_matched_by_fname)
        original_plex_token = app._plex_token

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie_path = Path(tmp) / "ET.1982.1080p.mkv"
            movie_path.write_bytes(b"")
            try:
                app._movies_dirs = [tmp]
                app._movies_dir = tmp
                app._user_data_dir = data_tmp
                app._library_cache = {}
                app._plex_cache = {}
                app._plex_matched_by_fname = {}
                app._plex_token = ""
                app.AppMetadataStore(Path(data_tmp)).apply_tmdb_match(str(movie_path), {
                    "tmdb_id": "601",
                    "title": "E.T.",
                    "year": "1982",
                })

                response = app.app.test_client().post("/api/library/check", json={
                    "movies": [{
                        "tmdb_id": "601",
                        "title": "E.T. the Extra-Terrestrial",
                        "year": "1982",
                    }]
                })
            finally:
                app._movies_dirs = original_dirs
                app._movies_dir = original_dir
                app._user_data_dir = original_user_data_dir
                app._library_cache = original_library_cache
                app._plex_cache = original_plex_cache
                app._plex_matched_by_fname = original_plex_by_fname
                app._plex_token = original_plex_token

        self.assertEqual(response.status_code, 200)
        result = response.get_json()["results"][0]
        self.assertTrue(result["found"])
        self.assertEqual(result["tmdb_id"], "601")
        self.assertEqual(result["path"], str(movie_path))


if __name__ == "__main__":
    unittest.main()
