import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class HomeHealthStatsTest(unittest.TestCase):
    def setUp(self):
        self.original_dirs = app._movies_dirs
        self.original_dir = app._movies_dir
        self.original_user_data_dir = app._user_data_dir
        self.original_plex_cache = dict(app._plex_cache)
        self.original_plex_matched = dict(app._plex_matched_by_fname)

    def tearDown(self):
        app._movies_dirs = self.original_dirs
        app._movies_dir = self.original_dir
        app._user_data_dir = self.original_user_data_dir
        app._plex_cache = self.original_plex_cache
        app._plex_matched_by_fname = self.original_plex_matched

    def test_stats_exposes_unmatched_and_identity_review_counts(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            accepted = Path(movies_tmp) / "Alien.1979.mkv"
            unmatched = Path(movies_tmp) / "Unknown.Movie.2024.mkv"
            accepted.write_bytes(b"a")
            unmatched.write_bytes(b"b")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            app._plex_cache = {}
            app._plex_matched_by_fname = {}
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(accepted), {
                "display_provider": "tmdb",
                "metadata_status": "accepted",
                "metadata_accepted": True,
                "tmdb_id": "348",
            })
            store.save_tmdb_metadata({"tmdb_id": "348", "title": "Alien", "year": "1979"})
            store.update_file_record(str(unmatched), {
                "metadata_status": "unmatched",
                "metadata_accepted": False,
            })
            store.save_identity_audit_state({
                "schema_version": 3,
                "status": "completed",
                "last_checked_at": 123,
                "automatically_verified": 4,
                "proposals": [
                    {"id": "r1", "classification": "recommended"},
                    {"id": "r2", "classification": "review"},
                ],
            })
            with patch("app.scan_duplicates", return_value=([], {
                "groups": 0,
                "extra_copies": 0,
                "wasted_bytes": 0,
                "wasted_human": "0 B",
            })):
                response = app.app.test_client().get("/api/stats")

        payload = response.get_json()
        self.assertEqual(payload["unmatched_count"], 1)
        self.assertEqual(payload["identity_review_count"], 2)
        self.assertEqual(payload["identity_review_recommended"], 1)
        self.assertEqual(payload["identity_review_last_checked_at"], 123)


if __name__ == "__main__":
    unittest.main()
