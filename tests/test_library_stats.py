import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class LibraryStatsTest(unittest.TestCase):
    def test_stats_counts_plex_filename_fallback_as_matched(self):
        original_dirs = app._movies_dirs
        original_dir = app._movies_dir
        original_plex_cache = dict(app._plex_cache)
        original_plex_by_fname = dict(app._plex_matched_by_fname)
        original_plex_token = app._plex_token
        original_stats_cache = dict(app._stats_cache)
        original_user_data = app._user_data_dir

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(tmp) / "Movie.2000.1080p.mkv"
            movie.write_bytes(b"")
            app.AppMetadataStore(Path(data_tmp)).update_file_record(str(movie), {
                "filename": movie.name,
                "parsed_title": "Movie",
                "parsed_year": "2000",
                "identity_status": "accepted",
                "identity_title": "Movie",
                "identity_year": "2000",
                "metadata_status": "accepted",
                "metadata_accepted": True,
                "resolution": "1080p",
            })
            try:
                app._movies_dirs = [tmp]
                app._movies_dir = tmp
                app._user_data_dir = data_tmp
                app._plex_cache = {}
                app._plex_matched_by_fname = {
                    movie.name.lower(): {"plex_title": "Movie", "plex_year": "2000"}
                }
                app._plex_token = "token"
                app._stats_cache = {}

                response = app.app.test_client().get("/api/stats")
            finally:
                app._movies_dirs = original_dirs
                app._movies_dir = original_dir
                app._user_data_dir = original_user_data
                app._plex_cache = original_plex_cache
                app._plex_matched_by_fname = original_plex_by_fname
                app._plex_token = original_plex_token
                app._stats_cache = original_stats_cache

        payload = response.get_json()
        self.assertEqual(payload["plex_matched"], 1)
        self.assertEqual(payload["plex_unmatched"], 0)

    def test_stats_reuses_short_lived_cached_payload(self):
        original_dirs = app._movies_dirs
        original_dir = app._movies_dir
        original_plex_cache = dict(app._plex_cache)
        original_plex_by_fname = dict(app._plex_matched_by_fname)
        original_plex_token = app._plex_token
        original_stats_cache = dict(app._stats_cache)
        original_user_data = app._user_data_dir

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(tmp) / "Movie.2000.1080p.mkv"
            movie.write_bytes(b"")
            app.AppMetadataStore(Path(data_tmp)).update_file_record(str(movie), {
                "filename": movie.name,
                "parsed_title": "Movie",
                "parsed_year": "2000",
                "metadata_status": "unmatched",
                "resolution": "1080p",
            })
            try:
                app._movies_dirs = [tmp]
                app._movies_dir = tmp
                app._user_data_dir = data_tmp
                app._plex_cache = {}
                app._plex_matched_by_fname = {}
                app._plex_token = ""
                app._stats_cache = {}

                first = app.app.test_client().get("/api/stats")
                with patch("app._maintenance_audit_from_catalog", side_effect=AssertionError("stats should come from cache")):
                    second = app.app.test_client().get("/api/stats")
            finally:
                app._movies_dirs = original_dirs
                app._movies_dir = original_dir
                app._user_data_dir = original_user_data
                app._plex_cache = original_plex_cache
                app._plex_matched_by_fname = original_plex_by_fname
                app._plex_token = original_plex_token
                app._stats_cache = original_stats_cache

        self.assertFalse(first.get_json()["cached"])
        self.assertTrue(second.get_json()["cached"])


if __name__ == "__main__":
    unittest.main()
