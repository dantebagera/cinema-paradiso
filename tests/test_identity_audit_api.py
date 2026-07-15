import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from services.identity_audit import IDENTITY_AUDIT_SCHEMA_VERSION
from services.identity_decision import (
    DECISION_ORIGIN_IDENTITY_AUDIT,
    IDENTITY_AUDIT_RULE_VERSION,
)


class IdentityAuditApiTest(unittest.TestCase):
    def setUp(self):
        self.original_dirs = app._movies_dirs
        self.original_dir = app._movies_dir
        self.original_user_data_dir = app._user_data_dir
        self.original_tmdb_key = app._tmdb_key
        self.original_plex_cache = dict(app._plex_cache)
        self.original_audit = getattr(app, "_identity_audit_coordinator", None)
        self.original_audit_dir = getattr(app, "_identity_audit_store_dir", "")
        self.original_library_cache = dict(app._library_cache)

    def tearDown(self):
        app._movies_dirs = self.original_dirs
        app._movies_dir = self.original_dir
        app._user_data_dir = self.original_user_data_dir
        app._tmdb_key = self.original_tmdb_key
        app._plex_cache = self.original_plex_cache
        app._identity_audit_coordinator = self.original_audit
        app._identity_audit_store_dir = self.original_audit_dir
        app._library_cache = self.original_library_cache

    def configure(self, movies_tmp, data_tmp):
        app._movies_dirs = [movies_tmp]
        app._movies_dir = movies_tmp
        app._user_data_dir = data_tmp
        app._tmdb_key = "tmdb-key"
        app._identity_audit_coordinator = None
        app._identity_audit_store_dir = ""
        app.AppMetadataStore(Path(data_tmp)).save_authority_state({"active_provider": "tmdb"})

    def test_full_preview_counts_manual_locked_matches_without_reviewing_them(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            automatic = Path(movies_tmp) / "The Phantom Menace.mp4"
            manual = Path(movies_tmp) / "Alien.1979.mkv"
            automatic.write_bytes(b"a")
            manual.write_bytes(b"b")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(automatic), {
                "display_provider": "tmdb",
                "metadata_accepted": True,
                "metadata_source": "tmdb_snapshot",
                "tmdb_id": "661852",
            })
            store.apply_tmdb_match(str(manual), {"tmdb_id": "348", "title": "Alien", "year": "1979"})

            client = app.app.test_client()
            preview = client.post("/api/metadata/identity-audit", json={"background": False})
            app._get_identity_audit_coordinator().run_batch(limit=10)
            state = client.get(f"/api/metadata/identity-audit/{preview.get_json()['id']}").get_json()

        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.get_json()["total"], 2)
        self.assertEqual(state["outcome_counts"]["manual"], 1)
        self.assertEqual(state["proposals"], [])

    def test_preview_rechecks_legacy_bulk_match_that_was_stored_as_manual(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            manual = store.apply_tmdb_match(
                str(movie),
                {"tmdb_id": "348", "title": "Alien", "year": "1979"},
            )
            store.update_file_record(str(movie), {
                "decision_origin": "",
                "decision_actor": "",
            })
            legacy_manual = {
                key: value
                for key, value in manual.items()
                if key not in {"decision_origin", "decision_actor"}
            }
            store.catalog.upsert_record(
                "app_metadata/manual_matches.json",
                store._key(str(movie)),
                legacy_manual,
            )
            fingerprint = store.save_identity_audit_fingerprint(str(movie), {
                "rule_version": IDENTITY_AUDIT_RULE_VERSION - 1,
                "provider": "tmdb",
                "provider_id": "348",
            })

            with patch("app._auto_sync_plex", return_value=None):
                paths = app._identity_audit_paths()

        self.assertLessEqual(fingerprint["verified_at"] - manual["updated_at"], 5)
        self.assertEqual(paths, [str(movie)])

    def test_shadow_audit_reports_splice_conflict_without_mutating_or_applying(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Splice.2009.mp4"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "display_provider": "tmdb",
                "identity_status": "accepted",
                "metadata_accepted": True,
                "metadata_status": "accepted",
                "decision_origin": DECISION_ORIGIN_IDENTITY_AUDIT,
                "tmdb_id": "1629337",
            })
            store.save_tmdb_metadata({
                "tmdb_id": "1629337",
                "title": "SPLICE",
                "year": "2009",
                "overview": "A detective investigates VHS tapes connected to missing persons.",
                "genres": ["Mystery"],
                "directors": [{"name": "Dylan MacGregor"}],
                "cast": [{"name": "Cole Weinmeyer"}],
            })
            app._plex_cache = {app._norm(str(movie)): {
                "plex_title": "Splice",
                "plex_year": "2009",
                "plex_summary": "Two rebellious scientists splice human and animal DNA to create a new organism.",
                "plex_genres": ["Science Fiction", "Horror"],
                "plex_directors": [{"name": "Vincenzo Natali"}],
                "plex_cast": [{"name": "Adrien Brody"}, {"name": "Sarah Polley"}],
            }}
            store.save_plex_metadata(str(movie), app._plex_cache[app._norm(str(movie))])
            candidates = [
                {
                    "tmdb_id": "1629337", "title": "SPLICE", "year": "2009",
                    "provider_rank": 2, "tmdb_vote_count": 0,
                },
                {
                    "tmdb_id": "37707", "title": "Splice", "year": "2010",
                    "provider_rank": 1, "tmdb_vote_count": 2469,
                    "overview": "Two rebellious scientists splice human and animal DNA to create a new organism.",
                    "genres": ["Horror", "Science Fiction"],
                },
            ]
            with patch("app._identity_tmdb_candidates", return_value=candidates), \
                    patch("app._fetch_tmdb_metadata_by_id", return_value={}):
                client = app.app.test_client()
                started = client.post("/api/metadata/identity-audit", json={"background": False})
                job_id = started.get_json()["id"]
                app._get_identity_audit_coordinator().run_batch(limit=10)
                status = client.get(f"/api/metadata/identity-audit/{job_id}")
                proposal = status.get_json()["proposals"][0]
                applied = client.post(
                    f"/api/metadata/identity-audit/{job_id}/apply",
                    json={"proposal_ids": [proposal["id"]]},
                )
                record = store.snapshot()["files"][app._norm(str(movie))]

        self.assertEqual(status.status_code, 200)
        self.assertEqual(proposal["classification"], "actionable")
        self.assertEqual(proposal["candidate"]["tmdb_id"], "37707")
        self.assertEqual(applied.status_code, 409)
        self.assertEqual(record["tmdb_id"], "1629337")
        self.assertEqual(status.get_json()["applied"], 0)

    def test_exact_current_identity_is_verified_read_only_without_entering_review_queue(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Elle.2016.720p.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "display_provider": "plex",
                "metadata_accepted": True,
                "metadata_source": "plex_snapshot",
                "metadata_title": "Elle",
                "metadata_year": "2016",
            })
            store.save_plex_metadata(str(movie), {
                "plex_title": "Elle",
                "plex_year": "2016",
            })
            candidates = [
                {
                    "tmdb_id": "337674",
                    "title": "Elle",
                    "year": "2016",
                    "provider_rank": 1,
                    "tmdb_vote_count": 2100,
                },
                {
                    "tmdb_id": "1018714",
                    "title": "Elle",
                    "year": "2016",
                    "provider_rank": 2,
                    "tmdb_vote_count": 20,
                },
            ]
            with patch("app._identity_tmdb_candidates", return_value=candidates):
                with patch("app._fetch_tmdb_metadata_by_id", return_value={
                    "tmdb_id": "337674",
                    "title": "Elle",
                    "year": "2016",
                }):
                    client = app.app.test_client()
                    started = client.post("/api/metadata/identity-audit", json={"background": False})
                    job_id = started.get_json()["id"]
                    app._get_identity_audit_coordinator().run_batch(limit=10)
                    state = client.get(f"/api/metadata/identity-audit/{job_id}").get_json()
                    record = store.snapshot()["files"][app._norm(str(movie))]
                    manual_match = store.get_manual_match(str(movie))
                    fingerprint = store.get_identity_audit_fingerprint(str(movie))

        self.assertEqual(state["proposals"], [])
        self.assertEqual(state["outcome_counts"]["verified"], 1)
        self.assertEqual(state["automatically_verified"], 0)
        self.assertEqual(record.get("tmdb_id", ""), "")
        self.assertEqual(record["metadata_source"], "plex_snapshot")
        self.assertEqual(manual_match, {})
        self.assertEqual(fingerprint, {})

    def test_audit_verifies_exact_current_identity_without_linking_provider_id(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "A.Nightmare.On.Elm.Street.2.Freddys.Revenge.1985.1080p.BrRip.x264.YIFY.mp4"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            app._plex_cache = {app._norm(str(movie)): {
                "plex_title": "A Nightmare on Elm Street Part 2: Freddy's Revenge",
                "plex_year": "1985",
            }}
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "display_provider": "plex",
                "identity_status": "accepted",
                "metadata_status": "accepted",
                "metadata_accepted": True,
                "identity_title": "A Nightmare on Elm Street Part 2: Freddy's Revenge",
                "identity_year": "1985",
                "metadata_source": "plex_snapshot",
            })
            store.save_plex_metadata(
                str(movie),
                app._plex_cache[app._norm(str(movie))],
            )
            candidates = [{
                "tmdb_id": "10014",
                "title": "A Nightmare on Elm Street Part 2: Freddy's Revenge",
                "year": "1985",
                "provider_rank": 1,
                "tmdb_vote_count": 2115,
                "query_sources": ["filename", "plex_hint"],
            }]
            with patch("app._identity_tmdb_candidates", return_value=candidates), \
                    patch("app._fetch_tmdb_metadata_by_id", return_value={
                        "tmdb_id": "10014",
                        "title": "A Nightmare on Elm Street Part 2: Freddy's Revenge",
                        "year": "1985",
                    }):
                client = app.app.test_client()
                started = client.post("/api/metadata/identity-audit", json={"background": False})
                app._get_identity_audit_coordinator().run_batch(limit=10)
                state = client.get(
                    f"/api/metadata/identity-audit/{started.get_json()['id']}"
                ).get_json()
                record = app.AppMetadataStore(Path(data_tmp)).snapshot()["files"][app._norm(str(movie))]
                fingerprint = app.AppMetadataStore(Path(data_tmp)).get_identity_audit_fingerprint(str(movie))

        self.assertEqual(state["proposals"], [])
        self.assertEqual(state["outcome_counts"]["tolerated"], 1)
        self.assertEqual(state["automatically_verified"], 0)
        self.assertEqual(state["automatic_fixes"], [])
        self.assertEqual(record.get("tmdb_id", ""), "")
        self.assertEqual(fingerprint, {})

    def test_full_audit_rechecks_unchanged_fingerprinted_movie_locally(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Elle.2016.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "display_provider": "tmdb",
                "metadata_status": "accepted",
                "metadata_accepted": True,
                "tmdb_id": "337674",
            })
            store.save_tmdb_metadata({"tmdb_id": "337674", "title": "Elle", "year": "2016"})
            fingerprint = app._identity_audit_fingerprint(
                str(movie), "tmdb", store=store, snapshot=store.snapshot()
            )
            store.save_identity_audit_fingerprint(str(movie), fingerprint)

            with patch("app._process_identity_audit_path", return_value={"outcome": "verified"}) as process_path:
                started = app.app.test_client().post(
                    "/api/metadata/identity-audit",
                    json={"background": False},
                )
                app._get_identity_audit_coordinator().run_batch(limit=10)

        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.get_json()["total"], 1)
        process_path.assert_called_once_with(str(movie), "tmdb")

    def test_previous_rule_fingerprint_is_rechecked_for_metadata_discrepancies(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Elle.2016.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "display_provider": "tmdb",
                "metadata_status": "accepted",
                "metadata_accepted": True,
                "metadata_source": "verified_tmdb",
                "tmdb_id": "337674",
            })
            store.save_tmdb_metadata({"tmdb_id": "337674", "title": "Elle", "year": "2016"})

            with patch("app._auto_sync_plex", return_value=None):
                paths = app._identity_audit_paths()
            fingerprints = store.get_identity_audit_fingerprints()

        self.assertEqual(paths, [str(movie)])
        self.assertEqual(fingerprints, {})

    def test_independently_verified_identity_is_not_added_to_provider_audit_backlog(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Elle.2016.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "filename": movie.name,
                "parsed_title": "Elle",
                "parsed_year": "2016",
                "identity_status": "accepted",
                "metadata_status": "accepted",
                "metadata_accepted": True,
                "identity_title": "Elle",
                "identity_year": "2016",
                "tmdb_id": "337674",
                "decision_origin": DECISION_ORIGIN_IDENTITY_AUDIT,
            })
            store.save_tmdb_metadata({"tmdb_id": "337674", "title": "Elle", "year": "2016"})
            store.save_plex_metadata(str(movie), {
                "plex_title": "Elle",
                "plex_year": "2016",
                "tmdb_id": "337674",
            })

            with patch("app._auto_sync_plex", return_value=None):
                paths = app._identity_audit_paths()

        self.assertEqual(paths, [str(movie)])

    def test_pause_and_resume_endpoints_preserve_partial_job_state(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Elle.2016.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_identity_audit_state({
                "schema_version": 4,
                "id": "audit-job",
                "status": "running",
                "provider": "tmdb",
                "paths": [str(movie)],
                "processed": 0,
                "remaining": 1,
                "total": 1,
                "proposals": [{"id": "proposal-1", "path": str(movie)}],
                "automatic_fixes": [{"id": "automatic-1", "path": str(movie)}],
            })
            client = app.app.test_client()
            initial = client.get("/api/metadata/identity-audit").get_json()

            with patch.object(app._get_identity_audit_coordinator(), "_ensure_thread"):
                resumed = client.post("/api/metadata/identity-audit/audit-job/resume")

        self.assertEqual(initial["status"], "paused")
        self.assertEqual(resumed.status_code, 200)
        state = resumed.get_json()
        self.assertEqual(state["status"], "running")
        self.assertEqual(state["processed"], 0)
        self.assertEqual(len(state["proposals"]), 1)
        self.assertEqual(len(state["automatic_fixes"]), 1)

    def test_start_new_scan_replaces_paused_job_but_keeps_verified_fingerprints(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Elle.2016.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "display_provider": "tmdb",
                "metadata_status": "accepted",
                "metadata_accepted": True,
                "tmdb_id": "337674",
            })
            store.save_tmdb_metadata({"tmdb_id": "337674", "title": "Elle", "year": "2016"})
            fingerprint = app._identity_audit_fingerprint(
                str(movie), "tmdb", store=store, snapshot=store.snapshot()
            )
            store.save_identity_audit_fingerprint(str(movie), fingerprint)
            store.save_identity_audit_state({
                "schema_version": 4,
                "id": "paused-job",
                "status": "paused",
                "paths": [str(movie)],
                "processed": 0,
                "remaining": 1,
                "total": 1,
                "proposals": [{"id": "proposal-1", "path": str(movie)}],
                "automatic_fixes": [{"id": "automatic-1", "path": str(movie)}],
            })

            started = app.app.test_client().post(
                "/api/metadata/identity-audit",
                json={"background": False},
            )
            fingerprints = store.get_identity_audit_fingerprints()

        self.assertEqual(started.status_code, 200)
        state = started.get_json()
        self.assertNotEqual(state["id"], "paused-job")
        self.assertEqual(state["total"], 1)
        self.assertEqual(state["proposals"], [])
        self.assertEqual(state["automatic_fixes"], [])
        self.assertIn(app._norm(str(movie)), fingerprints)

    def test_filename_year_difference_does_not_create_identity_correction(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "The.Amusement.Park.1975.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "display_provider": "tmdb",
                "metadata_status": "accepted",
                "metadata_accepted": True,
                "tmdb_id": "560981",
                "imdb_id": "tt0061781",
            })
            store.save_tmdb_metadata({
                "tmdb_id": "560981",
                "imdb_id": "tt0061781",
                "title": "The Amusement Park",
                "year": "2021",
            })

            with patch("app._identity_tmdb_candidates", return_value=[{
                "tmdb_id": "560981",
                "imdb_id": "tt0061781",
                "title": "The Amusement Park",
                "year": "2021",
                "provider_rank": 1,
            }]) as provider_search, patch("app._fetch_tmdb_metadata_by_id", return_value={}):
                result = app._process_identity_audit_path(str(movie), "tmdb")

        self.assertEqual(result["outcome"], "verified")
        self.assertNotIn("proposal_type", result)
        provider_search.assert_called_once()

    def test_shadow_report_rejects_apply_without_saving_override(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "The.Amusement.Park.1975.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "display_provider": "tmdb",
                "metadata_status": "accepted",
                "metadata_accepted": True,
                "tmdb_id": "560981",
                "imdb_id": "tt0061781",
            })
            store.save_tmdb_metadata({
                "tmdb_id": "560981",
                "imdb_id": "tt0061781",
                "title": "The Amusement Park",
                "year": "2021",
            })
            store.save_identity_audit_state({
                "schema_version": 4,
                "id": "audit-job",
                "status": "completed",
                "provider": "tmdb",
                "proposals": [{
                    "id": "discrepancy-1",
                    "path": str(movie),
                    "filename": movie.name,
                    "proposal_type": "metadata_discrepancy",
                    "classification": "review",
                    "current": {
                        "tmdb_id": "560981",
                        "imdb_id": "tt0061781",
                        "title": "The Amusement Park",
                        "year": "2021",
                    },
                    "candidate": {
                        "tmdb_id": "560981",
                        "imdb_id": "tt0061781",
                        "title": "The Amusement Park",
                        "year": "1975",
                    },
                }],
                "review_count": 1,
            })

            response = app.app.test_client().post(
                "/api/metadata/identity-audit/audit-job/apply",
                json={"proposal_ids": ["discrepancy-1"]},
            )
            override = store.get_metadata_override({
                "tmdb_id": "560981",
                "imdb_id": "tt0061781",
                "title": "The Amusement Park",
                "year": "2021",
            })
            manual_match = store.get_manual_match(str(movie))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(override, {})
        self.assertEqual(manual_match, {})

    def test_identity_fingerprint_rule_version_rechecks_metadata_discrepancies(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "tmdb_id": "348",
                "metadata_accepted": True,
            })
            store.save_tmdb_metadata({"tmdb_id": "348", "title": "Alien", "year": "1979"})

            fingerprint = app._identity_audit_fingerprint(
                str(movie),
                "tmdb",
                store=store,
                snapshot=store.snapshot(),
            )

        self.assertEqual(fingerprint["rule_version"], IDENTITY_AUDIT_RULE_VERSION)

    def test_manual_tmdb_match_removes_path_from_persisted_identity_review(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Love.2011.mp4"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_identity_audit_state({
                "schema_version": 4,
                "id": "audit-job",
                "status": "completed",
                "provider": "tmdb",
                "proposals": [{
                    "id": "proposal-1",
                    "path": str(movie),
                    "classification": "review",
                    "candidate": {"tmdb_id": "999", "title": "Money or Love", "year": "2011"},
                }],
                "automatic_fixes": [{
                    "id": "automatic-1",
                    "path": str(movie),
                    "candidate": {"tmdb_id": "999", "title": "Money or Love", "year": "2011"},
                }],
                "recommended_count": 0,
                "review_count": 1,
            })

            with patch("app._fetch_tmdb_metadata_by_id", return_value={
                "tmdb_id": "123",
                "title": "Love",
                "year": "2011",
            }):
                response = app.app.test_client().post("/api/tmdb/match-apply", json={
                    "path": str(movie),
                    "tmdb_id": "123",
                    "movie": {"tmdb_id": "123", "title": "Love", "year": "2011"},
                })
            audit = store.get_identity_audit_state()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(audit["proposals"], [])
        self.assertEqual(audit["automatic_fixes"], [])
        self.assertEqual(audit["review_count"], 0)

    def test_legacy_audit_results_require_refresh_instead_of_being_shown(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_identity_audit_state({
                "id": "legacy-audit",
                "status": "completed",
                "processed": 1,
                "total": 1,
                "proposals": [{
                    "id": "legacy-proposal",
                    "path": str(Path(movies_tmp) / "Elle.2016.mkv"),
                    "candidate": {"title": "Elle", "year": "2016"},
                }],
                "completed_at": 123,
            })

            response = app.app.test_client().get("/api/metadata/identity-audit")
            state = response.get_json()
            persisted = store.get_identity_audit_state()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(state["status"], "completed")
        self.assertTrue(state["requires_refresh"])
        self.assertEqual(len(state["proposals"]), 1)
        self.assertEqual(state["review_count"], 1)
        self.assertEqual(state["automatic_fixes"], [])
        self.assertEqual(persisted["schema_version"], IDENTITY_AUDIT_SCHEMA_VERSION)
        self.assertTrue(persisted["requires_refresh"])



if __name__ == "__main__":
    unittest.main()
