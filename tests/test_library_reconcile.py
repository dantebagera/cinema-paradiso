import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class LibraryReconcileTest(unittest.TestCase):
    def setUp(self):
        self.original_dirs = app._movies_dirs
        self.original_dir = app._movies_dir
        self.original_user_data = app._user_data_dir
        self.original_tmdb_key = app._tmdb_key
        self.original_library_cache = dict(app._library_cache)
        self.original_plex_cache = dict(app._plex_cache)

    def tearDown(self):
        app._movies_dirs = self.original_dirs
        app._movies_dir = self.original_dir
        app._user_data_dir = self.original_user_data
        app._tmdb_key = self.original_tmdb_key
        app._library_cache = self.original_library_cache
        app._plex_cache = self.original_plex_cache

    def configure(self, movies_dir, data_dir):
        app._movies_dirs = [movies_dir]
        app._movies_dir = movies_dir
        app._user_data_dir = data_dir
        app._tmdb_key = "tmdb-key"
        app._library_cache = {}

    def test_stable_scent_of_a_woman_is_matched_during_reconcile(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Scent.of.a.Woman.1992.1080p.BluRay.x264.YIFY.mp4"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_authority_state({"active_provider": "tmdb"})
            candidate = {
                "tmdb_id": "9475",
                "title": "Scent of a Woman",
                "year": "1992",
                "match_source": "auto_tmdb",
            }

            with patch("app._file_copy_is_stable", return_value=True), \
                    patch("app._accepted_tmdb_migration_metadata", return_value=(candidate, False)):
                result = app._reconcile_library_files()
            record = store.snapshot()["files"][app._norm(str(movie))]

        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["pending"], 0)
        self.assertEqual(record["metadata_status"], "accepted")
        self.assertEqual(record["tmdb_id"], "9475")
        self.assertEqual(record["parsed_title"], "scent of a woman")
        self.assertEqual(record["parsed_year"], "1992")

    def test_changing_new_file_stays_pending_until_later_recheck(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Copying.Movie.2026.1080p.mkv"
            movie.write_bytes(b"partial")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_authority_state({"active_provider": "tmdb"})

            with patch("app._file_copy_is_stable", return_value=False):
                result = app._reconcile_library_files()
            record = store.snapshot()["files"][app._norm(str(movie))]

        self.assertEqual(result["pending"], 1)
        self.assertEqual(record["metadata_status"], "pending")
        self.assertEqual(record["ingest_status"], "pending")

    def test_reconcile_skips_already_accepted_files(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.1080p.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "metadata_status": "accepted",
                "metadata_accepted": True,
                "size": movie.stat().st_size,
                "modified_time": movie.stat().st_mtime,
            })

            with patch("app._reconcile_library_path") as reconcile_path:
                result = app._reconcile_library_files()

        self.assertEqual(result["checked"], 0)
        reconcile_path.assert_not_called()

    def test_filename_authority_does_not_report_unmatched_file_as_identified(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Unknown.Movie.2026.1080p.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_authority_state({"active_provider": "filename"})

            with patch("app._file_copy_is_stable", return_value=True):
                result = app._reconcile_library_files()
            record = store.snapshot()["files"][app._norm(str(movie))]

        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["review"], 1)
        self.assertEqual(record["metadata_status"], "unmatched")

    def test_plex_authority_falls_back_to_tmdb_when_plex_has_not_indexed_file(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.1080p.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_authority_state({"active_provider": "plex"})
            candidate = {
                "tmdb_id": "348",
                "title": "Alien",
                "year": "1979",
                "match_source": "auto_tmdb",
            }

            with patch("app._file_copy_is_stable", return_value=True), \
                    patch("app._accepted_tmdb_migration_metadata", return_value=(candidate, False)):
                outcome = app._reconcile_library_path(str(movie), "plex", store=store)
            record = store.snapshot()["files"][app._norm(str(movie))]

        self.assertEqual(outcome, "matched")
        self.assertEqual(record["identity_status"], "accepted")
        self.assertEqual(record["tmdb_id"], "348")
        self.assertEqual(record["display_provider"], "tmdb")

    def test_inventory_bootstrap_processes_historical_unrecorded_files(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Historical.Movie.1990.1080p.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_authority_state({"active_provider": "tmdb"})

            with patch("app._library_inventory_bootstrap_cutoff", return_value=1000), \
                    patch("app.os.path.getctime", return_value=500), \
                    patch("app._reconcile_library_path") as reconcile_path:
                result = app._reconcile_library_files()
            inventory = store.get_library_inventory()

        self.assertEqual(result["checked"], 1)
        reconcile_path.assert_called_once()
        self.assertIn(app._norm(str(movie)), inventory)

    def test_inventory_entry_without_authoritative_record_is_reconciled(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Recovered.Movie.1998.1080p.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_authority_state({"active_provider": "tmdb"})
            store.save_library_inventory({
                app._norm(str(movie)): {
                    "path": str(movie),
                    "size": movie.stat().st_size,
                    "modified_time": movie.stat().st_mtime,
                },
            })

            with patch("app._reconcile_library_path", return_value="matched") as reconcile_path:
                result = app._reconcile_library_files()

        self.assertEqual(result["checked"], 1)
        reconcile_path.assert_called_once()

    def test_stale_review_record_is_retried_after_decision_rule_upgrade(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Cujo.1983.1080p.BluRay.x264.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_authority_state({"active_provider": "tmdb"})
            fingerprint = {
                "path": str(movie),
                "size": movie.stat().st_size,
                "modified_time": movie.stat().st_mtime,
            }
            store.save_library_inventory({app._norm(str(movie)): fingerprint})
            store.update_file_record(str(movie), {
                "metadata_status": "needs_review",
                "identity_status": "review",
                "metadata_accepted": False,
                "candidate_tmdb_id": "10489",
                "candidate_title": "Cujo",
                "candidate_year": "1983",
                "size": fingerprint["size"],
                "modified_time": fingerprint["modified_time"],
            })
            candidate = {
                "tmdb_id": "10489",
                "title": "Cujo",
                "year": "1983",
                "match_source": "auto_tmdb",
            }

            with patch("app._file_copy_is_stable", return_value=True), \
                    patch("app._accepted_tmdb_migration_metadata", return_value=(candidate, False)):
                result = app._reconcile_library_files()
            record = store.snapshot()["files"][app._norm(str(movie))]

        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(record["metadata_status"], "accepted")
        self.assertEqual(record["tmdb_id"], "10489")
        self.assertEqual(record["identity_decision_version"], app.IDENTITY_DECISION_VERSION)

    def test_current_review_record_is_not_retried_on_every_normal_reconcile(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Actually.Ambiguous.2026.1080p.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_authority_state({"active_provider": "tmdb"})
            fingerprint = {
                "path": str(movie),
                "size": movie.stat().st_size,
                "modified_time": movie.stat().st_mtime,
            }
            store.save_library_inventory({app._norm(str(movie)): fingerprint})
            store.update_file_record(str(movie), {
                "metadata_status": "needs_review",
                "identity_status": "review",
                "metadata_accepted": False,
                "identity_decision_version": app.IDENTITY_DECISION_VERSION,
                "candidate_tmdb_id": "123",
                "candidate_title": "Actually Ambiguous",
                "candidate_year": "2026",
                "size": fingerprint["size"],
                "modified_time": fingerprint["modified_time"],
            })

            with patch("app._reconcile_library_path") as reconcile_path:
                result = app._reconcile_library_files()

        self.assertEqual(result["checked"], 0)
        reconcile_path.assert_not_called()

    def test_current_review_record_is_retried_when_provider_evidence_changes(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Obsession.2025.1080p.WEBRip.x264.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_authority_state({"active_provider": "tmdb"})
            fingerprint = {
                "path": str(movie),
                "size": movie.stat().st_size,
                "modified_time": movie.stat().st_mtime,
            }
            store.save_library_inventory({app._norm(str(movie)): fingerprint})
            store.update_file_record(str(movie), {
                "metadata_status": "needs_review",
                "identity_status": "review",
                "metadata_accepted": False,
                "identity_decision_version": app.IDENTITY_DECISION_VERSION,
                "identity_evidence_fingerprint": "filename:obsession:2025",
                "candidate_tmdb_id": "1436161",
                "candidate_title": "Obsession",
                "candidate_year": "2025",
                "size": fingerprint["size"],
                "modified_time": fingerprint["modified_time"],
            })
            app._plex_cache[app._norm(str(movie))] = {
                "plex_title": "Obsession",
                "plex_year": "2026",
                "tmdb_id": "1339713",
                "imdb_id": "tt3000000",
                "plex_guid": "plex://movie/obsession",
            }

            with patch("app._reconcile_library_path", return_value="matched") as reconcile_path:
                result = app._reconcile_library_files()

        self.assertEqual(result["checked"], 1)
        reconcile_path.assert_called_once()

    def test_inventory_bootstrap_processes_files_newer_than_metadata_checkpoint(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "New.Movie.2026.1080p.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_authority_state({"active_provider": "tmdb"})

            with patch("app._library_inventory_bootstrap_cutoff", return_value=1000), \
                    patch("app.os.path.getctime", return_value=1500), \
                    patch("app._reconcile_library_path", return_value="matched") as reconcile_path:
                result = app._reconcile_library_files()

        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["matched"], 1)
        reconcile_path.assert_called_once()

    def test_manual_rescan_runs_reconcile_before_returning_library(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Scent.of.a.Woman.1992.1080p.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            with patch("app._reconcile_library_files", return_value={
                "checked": 1, "matched": 1, "review": 0, "pending": 0, "failed": 0
            }) as reconcile:
                response = app.app.test_client().get("/api/library?force_scan=1")

        self.assertEqual(response.status_code, 200)
        reconcile.assert_called_once_with(force_unresolved=True)
        self.assertEqual(response.get_json()["metadata_matched"], 1)


if __name__ == "__main__":
    unittest.main()
