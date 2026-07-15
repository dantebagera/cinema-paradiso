import tempfile
import unittest
import os
import time
from pathlib import Path
from unittest.mock import patch

import app


class MetadataAuthorityTest(unittest.TestCase):
    def setUp(self):
        self.original_dirs = app._movies_dirs
        self.original_dir = app._movies_dir
        self.original_user_data_dir = app._user_data_dir
        self.original_tmdb_key = app._tmdb_key
        self.original_plex_url = app._plex_url
        self.original_plex_token = app._plex_token
        self.original_plex_cache = dict(app._plex_cache)
        self.original_plex_by_fname = dict(app._plex_matched_by_fname)
        self.original_library_cache = dict(app._library_cache)
        self.original_coordinator = app._metadata_migration_coordinator
        self.original_coordinator_dir = app._metadata_migration_store_dir
        app._tmdb_key = "tmdb-key"

    def tearDown(self):
        app._movies_dirs = self.original_dirs
        app._movies_dir = self.original_dir
        app._user_data_dir = self.original_user_data_dir
        app._tmdb_key = self.original_tmdb_key
        app._plex_url = self.original_plex_url
        app._plex_token = self.original_plex_token
        app._plex_cache = self.original_plex_cache
        app._plex_matched_by_fname = self.original_plex_by_fname
        app._library_cache = self.original_library_cache
        app._metadata_migration_coordinator = self.original_coordinator
        app._metadata_migration_store_dir = self.original_coordinator_dir

    def test_store_persists_authority_and_migration_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = app.AppMetadataStore(Path(tmp))
            store.save_authority_state({"active_provider": "tmdb"})
            store.save_migration_state({"status": "paused", "processed": 12})

            reloaded = app.AppMetadataStore(Path(tmp))

            self.assertEqual(reloaded.get_authority_state()["active_provider"], "tmdb")
            self.assertEqual(reloaded.get_migration_state()["status"], "paused")
            self.assertEqual(reloaded.get_migration_state()["processed"], 12)

    def test_authority_endpoint_reports_available_providers_and_preview(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            Path(tmp, "Alien.1979.mkv").write_bytes(b"")
            app._movies_dirs = [tmp]
            app._movies_dir = tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            app._plex_url = "http://localhost:32400"
            app._plex_token = "plex-token"
            app._metadata_migration_coordinator = None

            client = app.app.test_client()
            status = client.get("/api/metadata/authority")
            preview = client.post("/api/metadata/authority/preview", json={"target": "tmdb"})

        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()["active_provider"], "plex")
        self.assertTrue(status.get_json()["providers"]["tmdb"]["available"])
        self.assertTrue(status.get_json()["providers"]["plex"]["available"])
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.get_json()["total"], 1)

    def test_starting_second_active_migration_returns_conflict_and_preserves_progress(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [tmp]
            app._movies_dir = tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            app._plex_url = "http://localhost:32400"
            app._plex_token = "plex-token"
            app._metadata_migration_coordinator = None
            app._metadata_migration_store_dir = ""
            coordinator = app._get_metadata_migration_coordinator()
            coordinator.start("tmdb", source="plex", background=False)
            before = coordinator.status()

            response = app.app.test_client().post(
                "/api/metadata/authority/migrate",
                json={"target": "plex"},
            )
            after = coordinator.status()

        self.assertEqual(response.status_code, 409)
        self.assertIn("already active", response.get_json()["error"])
        self.assertEqual(after["target"], "tmdb")
        self.assertEqual(after["processed"], before["processed"])
        self.assertEqual(after["remaining"], before["remaining"])

    def test_tmdb_migration_uses_trusted_plex_id_and_persists_file_authority(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(tmp) / "ET.1982.mkv"
            movie.write_bytes(b"controlled movie bytes")
            app._movies_dirs = [tmp]
            app._movies_dir = tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            app._plex_cache = {
                app._norm(str(movie)): {
                    "plex_title": "E.T.",
                    "plex_year": "1982",
                    "tmdb_id": "601",
                }
            }

            metadata = {
                "tmdb_id": "601",
                "imdb_id": "tt0083866",
                "title": "E.T. the Extra-Terrestrial",
                "year": "1982",
                "alternative_titles": ["E.T."],
                "poster_url": "poster.jpg",
                "match_source": "plex_tmdb_id",
            }
            with patch("app._identity_tmdb_candidates", return_value=[]), \
                    patch("app._fetch_tmdb_metadata_by_id", return_value=metadata):
                outcome = app._migrate_metadata_path(str(movie), "tmdb")

            record = app.AppMetadataStore(Path(data_tmp)).snapshot()["files"][app._norm(str(movie))]

        self.assertEqual(outcome, "matched")
        self.assertEqual(record["display_provider"], "tmdb")
        self.assertEqual(record["tmdb_id"], "601")
        self.assertTrue(record["metadata_accepted"])

    def test_tmdb_target_does_not_trust_a_plex_external_id_without_filename_support(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(tmp) / "Splice.2009.1080p.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [tmp]
            app._movies_dir = tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            app._plex_cache = {
                app._norm(str(movie)): {
                    "plex_title": "Temptation's Hour",
                    "plex_year": "2001",
                    "tmdb_id": "1629337",
                    "imdb_id": "tt0000001",
                }
            }
            wrong = {
                "tmdb_id": "1629337",
                "title": "Temptation's Hour",
                "year": "2001",
                "match_source": "plex_tmdb_id",
            }

            with patch("app._identity_tmdb_candidates", return_value=[]), \
                    patch("app._fetch_tmdb_metadata_by_id", return_value=wrong):
                outcome = app._migrate_metadata_path(str(movie), "tmdb")
            record = app.AppMetadataStore(Path(data_tmp)).snapshot()["files"][app._norm(str(movie))]

        self.assertEqual(outcome, "review")
        self.assertEqual(record["identity_status"], "unmatched")
        self.assertEqual(record["metadata_status"], "unmatched")
        self.assertFalse(record["metadata_accepted"])
        self.assertEqual(record["candidate_tmdb_id"], "1629337")

    def test_plex_stable_ids_do_not_override_a_filename_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(tmp) / "Splice.2009.1080p.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [tmp]
            app._movies_dir = tmp
            app._user_data_dir = data_tmp
            app._plex_cache = {
                app._norm(str(movie)): {
                    "plex_title": "Temptation's Hour",
                    "plex_year": "2001",
                    "tmdb_id": "1629337",
                    "imdb_id": "tt0000001",
                    "plex_guid": "plex://movie/wrong",
                    "rating_key": "44",
                }
            }

            outcome = app._migrate_metadata_path(str(movie), "plex")
            record = app.AppMetadataStore(Path(data_tmp)).snapshot()["files"][app._norm(str(movie))]

        self.assertEqual(outcome, "review")
        self.assertEqual(record["identity_status"], "unmatched")
        self.assertEqual(record["metadata_status"], "unmatched")
        self.assertFalse(record["metadata_accepted"])
        self.assertEqual(record["candidate_title"], "Temptation's Hour")

    def test_provider_migrations_never_modify_local_movie_bytes_or_timestamp(self):
        cases = (
            ("filename", {}),
            ("plex", {"plex_title": "Alien", "plex_year": "1979", "rating_key": "44"}),
            ("tmdb", {"plex_title": "Alien", "plex_year": "1979", "tmdb_id": "348"}),
        )
        for target, plex_data in cases:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
                movie = Path(tmp) / "Alien.1979.mkv"
                payload = b"controlled immutable movie payload"
                movie.write_bytes(payload)
                fixed_mtime_ns = 1_700_000_000_123_456_700
                os.utime(movie, ns=(fixed_mtime_ns, fixed_mtime_ns))
                before = movie.stat()

                app._movies_dirs = [tmp]
                app._movies_dir = tmp
                app._user_data_dir = data_tmp
                app._tmdb_key = "tmdb-key"
                app._plex_cache = {app._norm(str(movie)): plex_data} if plex_data else {}

                metadata = {
                    "tmdb_id": "348",
                    "imdb_id": "tt0078748",
                    "title": "Alien",
                    "year": "1979",
                    "poster_url": "poster.jpg",
                    "match_source": "plex_tmdb_id",
                }
                with patch("app._identity_tmdb_candidates", return_value=[]), \
                        patch("app._fetch_tmdb_metadata_by_id", return_value=metadata):
                    outcome = app._migrate_metadata_path(str(movie), target)

                after = movie.stat()
                store = app.AppMetadataStore(Path(data_tmp))
                record = store.snapshot()["files"][app._norm(str(movie))]
                self.assertEqual(outcome, "matched")
                self.assertEqual(record["display_provider"], target)
                self.assertEqual(movie.read_bytes(), payload)
                self.assertEqual(after.st_size, before.st_size)
                self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)
                self.assertTrue(movie.exists())
                if target == "plex":
                    self.assertEqual(store.get_plex_metadata(str(movie))["plex_title"], "Alien")

    def test_uncertain_tmdb_match_keeps_existing_snapshot_until_completion(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(tmp) / "Ambiguous.Movie.2024.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [tmp]
            app._movies_dir = tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "display_provider": "plex",
                "metadata_status": "accepted",
                "metadata_source": "plex_snapshot",
                "metadata_accepted": True,
            })
            candidate = {
                "tmdb_id": "999",
                "title": "A Different Movie",
                "year": "2024",
                "match_source": "candidate_tmdb",
            }

            with patch("app._resolve_tmdb_identity", return_value=app._identity_resolution(
                "ambiguous", candidate, {"status": "review", "outcome": "ambiguous"}, source="candidate_tmdb"
            )):
                outcome = app._migrate_metadata_path(str(movie), "tmdb")

            pending = store.snapshot()["files"][app._norm(str(movie))]
            self.assertEqual(outcome, "review")
            self.assertEqual(pending["display_provider"], "plex")
            self.assertEqual(pending["metadata_status"], "accepted")

            app._complete_metadata_migration({
                "target": "tmdb",
                "source": "plex",
                "matched": 0,
                "review": 1,
                "failed": 0,
                "review_paths": [str(movie)],
                "completed_at": 100,
            })
            reviewed = store.snapshot()["files"][app._norm(str(movie))]

        self.assertEqual(reviewed["display_provider"], "tmdb")
        self.assertEqual(reviewed["metadata_status"], "accepted")
        self.assertEqual(reviewed["enrichment_status"], "incomplete")

    def test_provider_failure_is_recorded_without_modifying_movie_file(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(tmp) / "Provider.Failure.2024.mkv"
            payload = b"provider failure must not touch this file"
            movie.write_bytes(payload)
            fixed_mtime_ns = 1_700_000_100_123_456_700
            os.utime(movie, ns=(fixed_mtime_ns, fixed_mtime_ns))
            before = movie.stat()
            app._movies_dirs = [tmp]
            app._movies_dir = tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            store = app.AppMetadataStore(Path(data_tmp))
            coordinator = app.MetadataMigrationCoordinator(
                load_state=store.get_migration_state,
                save_state=store.save_migration_state,
                list_paths=lambda: [str(movie)],
                process_path=app._migrate_metadata_path,
            )

            with patch("app._resolve_tmdb_identity", side_effect=OSError("provider unavailable")):
                coordinator.start("tmdb", background=False)
                result = coordinator.run_batch(limit=1)

            after = movie.stat()
            after_payload = movie.read_bytes()

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["failed_paths"], [str(movie)])
        self.assertEqual(after_payload, payload)
        self.assertEqual(after.st_size, before.st_size)
        self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)

    def test_running_migration_pauses_after_coordinator_restart(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            first = Path(tmp) / "First.Movie.2023.mkv"
            second = Path(tmp) / "Second.Movie.2024.mkv"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            app._movies_dirs = [tmp]
            app._movies_dir = tmp
            app._user_data_dir = data_tmp
            app._metadata_migration_coordinator = None
            app._metadata_migration_store_dir = ""
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_migration_state({
                "status": "running",
                "source": "plex",
                "target": "filename",
                "paths": [str(first), str(second)],
                "processed": 1,
                "matched": 1,
                "review": 0,
                "failed": 0,
                "remaining": 1,
                "total": 2,
                "current_path": "",
                "review_paths": [],
                "failed_paths": [],
                "started_at": 100,
                "updated_at": 101,
                "completed_at": 0,
            })

            coordinator = app._get_metadata_migration_coordinator()
            state = coordinator.status()

        self.assertEqual(state["status"], "paused")
        self.assertEqual(state["processed"], 1)
        self.assertEqual(state["remaining"], 1)

    def test_unavailable_target_marks_migration_failed_and_retains_previous_authority(self):
        with tempfile.TemporaryDirectory() as data_tmp:
            app._user_data_dir = data_tmp
            app._tmdb_key = ""
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_authority_state({"active_provider": "plex"})
            store.save_migration_state({
                "status": "completed",
                "source": "plex",
                "target": "tmdb",
                "processed": 2,
                "matched": 0,
                "review": 0,
                "failed": 2,
                "remaining": 0,
                "total": 2,
                "review_paths": [],
                "failed_paths": ["one", "two"],
                "completed_at": 100,
            })
            state = store.get_migration_state()

            app._complete_metadata_migration(state)

            migration = store.get_migration_state()
            authority = store.get_authority_state()

        self.assertEqual(migration["status"], "failed")
        self.assertEqual(authority["active_provider"], "plex")

    def test_manual_tmdb_match_stays_locked_during_other_provider_migrations(self):
        for target in ("plex", "filename"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
                movie = Path(tmp) / "Wrong.Name.1979.mkv"
                movie.write_bytes(b"movie")
                app._movies_dirs = [tmp]
                app._movies_dir = tmp
                app._user_data_dir = data_tmp
                store = app.AppMetadataStore(Path(data_tmp))
                store.apply_tmdb_match(str(movie), {
                    "tmdb_id": "348",
                    "imdb_id": "tt0078748",
                    "title": "Alien",
                    "year": "1979",
                    "poster_url": "manual-tmdb.jpg",
                })
                app._plex_cache = {
                    app._norm(str(movie)): {
                        "plex_title": "Wrong Name",
                        "plex_year": "1979",
                        "rating_key": "44",
                    }
                }

                outcome = app._migrate_metadata_path(str(movie), target)
                record = store.snapshot()["files"][app._norm(str(movie))]

                self.assertEqual(outcome, "matched")
                self.assertEqual(record["display_provider"], "tmdb")
                self.assertEqual(record["metadata_source"], "manual_tmdb")
                self.assertEqual(record["tmdb_id"], "348")
                self.assertTrue(record["manual_locked"])

    def test_manual_plex_match_stays_locked_during_tmdb_target_migration(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(tmp) / "Wrong.Name.1982.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [tmp]
            app._movies_dir = tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            store = app.AppMetadataStore(Path(data_tmp))
            plex_metadata = {
                "plex_title": "E.T.",
                "plex_year": "1982",
                "plex_poster": "manual-plex.jpg",
                "rating_key": "55",
            }
            store.apply_plex_match(str(movie), plex_metadata)
            app._plex_cache = {app._norm(str(movie)): plex_metadata}

            outcome = app._migrate_metadata_path(str(movie), "tmdb")
            record = store.snapshot()["files"][app._norm(str(movie))]

        self.assertEqual(outcome, "matched")
        self.assertEqual(record["display_provider"], "plex")
        self.assertEqual(record["metadata_source"], "manual_plex")
        self.assertEqual(record["rating_key"], "55")
        self.assertTrue(record["manual_locked"])

    def test_completed_migration_moves_uncertain_files_to_filename_review(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(tmp) / "Unknown.Movie.mkv"
            movie.write_bytes(b"")
            app._movies_dirs = [tmp]
            app._movies_dir = tmp
            app._user_data_dir = data_tmp

            app._complete_metadata_migration({
                "target": "tmdb",
                "source": "plex",
                "matched": 0,
                "review": 1,
                "failed": 0,
                "review_paths": [str(movie)],
                "completed_at": 100,
            })

            store = app.AppMetadataStore(Path(data_tmp))
            record = store.snapshot()["files"][app._norm(str(movie))]
            authority = store.get_authority_state()

        self.assertEqual(record["display_provider"], "filename")
        self.assertEqual(record["metadata_status"], "needs_review")
        self.assertEqual(authority["active_provider"], "tmdb")

    def test_completed_provider_migration_marks_identity_audit_for_manual_refresh(self):
        with tempfile.TemporaryDirectory() as data_tmp:
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_identity_audit_state({
                "schema_version": 4,
                "id": "previous-job",
                "status": "completed",
                "proposals": [{"id": "proposal-1"}],
            })

            with patch("app._get_identity_audit_coordinator") as get_coordinator:
                app._complete_metadata_migration({
                    "status": "completed",
                    "target": "tmdb",
                    "source": "plex",
                    "processed": 1,
                    "total": 1,
                    "matched": 1,
                    "review": 0,
                    "failed": 0,
                    "review_paths": [],
                    "completed_at": 100,
                })
            state = store.get_identity_audit_state()

        get_coordinator.assert_not_called()
        self.assertEqual(state["status"], "completed")
        self.assertTrue(state["requires_refresh"])


if __name__ == "__main__":
    unittest.main()
