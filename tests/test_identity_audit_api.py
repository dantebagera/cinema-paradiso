import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


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

    def test_preview_excludes_manual_locked_matches(self):
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

            preview = app.app.test_client().post("/api/metadata/identity-audit", json={"background": False})

        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.get_json()["total"], 1)

    def test_audit_preview_does_not_mutate_and_apply_locks_selected_correction(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "The Phantom Menace.mp4"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "display_provider": "tmdb",
                "metadata_accepted": True,
                "metadata_source": "tmdb_snapshot",
                "tmdb_id": "661852",
            })
            store.save_tmdb_metadata({"tmdb_id": "661852", "title": "The Phantom Menace", "year": "2020"})
            app._plex_cache = {app._norm(str(movie)): {
                "plex_title": "Star Wars: Episode I - The Phantom Menace",
                "plex_year": "1999",
            }}
            store.save_plex_metadata(str(movie), app._plex_cache[app._norm(str(movie))])
            candidates = [
                {"tmdb_id": "661852", "title": "The Phantom Menace", "year": "2020", "provider_rank": 1},
                {"tmdb_id": "1893", "title": "Star Wars: Episode I - The Phantom Menace", "year": "1999", "provider_rank": 1},
            ]
            with patch("app._identity_tmdb_candidates", return_value=candidates):
                client = app.app.test_client()
                started = client.post("/api/metadata/identity-audit", json={"background": False})
                job_id = started.get_json()["id"]
                app._get_identity_audit_coordinator().run_batch(limit=10)
                status = client.get(f"/api/metadata/identity-audit/{job_id}")
                before = store.get_manual_match(str(movie))
                proposal = status.get_json()["proposals"][0]
                with patch("app._fetch_tmdb_metadata_by_id", return_value={
                    "tmdb_id": "1893", "title": "Star Wars: Episode I - The Phantom Menace", "year": "1999",
                }):
                    applied = client.post(
                        f"/api/metadata/identity-audit/{job_id}/apply",
                        json={"proposal_ids": [proposal["id"]]},
                    )
                refreshed = client.get(f"/api/metadata/identity-audit/{job_id}").get_json()
                after = store.get_manual_match(str(movie))

        self.assertEqual(before, {})
        self.assertEqual(applied.status_code, 200)
        self.assertEqual(after["tmdb_id"], "1893")
        self.assertEqual(after["provider"], "tmdb")
        self.assertEqual(refreshed["proposals"], [])
        self.assertEqual(refreshed["applied"], 1)

    def test_exact_current_identity_is_verified_without_entering_review_queue(self):
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

        self.assertEqual(state["proposals"], [])
        self.assertEqual(state["automatically_verified"], 1)
        self.assertEqual(record["tmdb_id"], "337674")
        self.assertEqual(record["metadata_source"], "verified_tmdb")
        self.assertEqual(store.get_manual_match(str(movie)), {})

    def test_audit_auto_links_exact_current_identity_when_filename_wording_differs(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "A.Nightmare.On.Elm.Street.2.Freddys.Revenge.1985.1080p.BrRip.x264.YIFY.mp4"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            app._plex_cache = {app._norm(str(movie)): {
                "plex_title": "A Nightmare on Elm Street Part 2: Freddy's Revenge",
                "plex_year": "1985",
            }}
            app.AppMetadataStore(Path(data_tmp)).save_plex_metadata(
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

        self.assertEqual(state["proposals"], [])
        self.assertEqual(state["automatically_verified"], 1)
        self.assertEqual(len(state["automatic_fixes"]), 1)
        self.assertEqual(state["automatic_fixes"][0]["filename"], movie.name)
        self.assertEqual(state["automatic_fixes"][0]["candidate"]["tmdb_id"], "10014")
        self.assertEqual(state["automatic_fixes"][0]["evidence_score"], 100)
        self.assertEqual(record["tmdb_id"], "10014")

    def test_verified_fingerprint_skips_unchanged_movie_on_next_audit(self):
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

            with patch("app._process_identity_audit_path") as process_path:
                started = app.app.test_client().post(
                    "/api/metadata/identity-audit",
                    json={"background": False},
                )
                app._get_identity_audit_coordinator().run_batch(limit=10)

        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.get_json()["total"], 0)
        process_path.assert_not_called()

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
        self.assertEqual(state["total"], 0)
        self.assertEqual(state["proposals"], [])
        self.assertEqual(state["automatic_fixes"], [])
        self.assertIn(app._norm(str(movie)), fingerprints)

    def test_exact_identity_with_large_year_difference_creates_metadata_discrepancy(self):
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

            with patch("app._identity_tmdb_candidates") as provider_search:
                result = app._process_identity_audit_path(str(movie), "tmdb")

        self.assertEqual(result["proposal_type"], "metadata_discrepancy")
        self.assertEqual(result["candidate"]["year"], "1975")
        self.assertEqual(result["classification"], "review")
        provider_search.assert_not_called()

    def test_applying_metadata_discrepancy_saves_override_not_manual_match(self):
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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["applied"], 1)
        self.assertEqual(override["year"], "1975")
        self.assertEqual(store.get_manual_match(str(movie)), {})

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

        self.assertEqual(fingerprint["rule_version"], 4)

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
        self.assertEqual(persisted["schema_version"], 4)
        self.assertTrue(persisted["requires_refresh"])



if __name__ == "__main__":
    unittest.main()
