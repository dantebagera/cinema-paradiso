import tempfile
import unittest
from pathlib import Path

import app
from tools.catalog_parity_audit import audit_catalog


class CatalogParityAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_user_data_dir = app._user_data_dir
        self.original_repositories = dict(app._catalog_repository_cache)
        app._user_data_dir = self.tmp.name
        app._catalog_repository_cache.clear()
        self.store = app.AppMetadataStore(Path(self.tmp.name))

    def tearDown(self):
        app._catalog_repository_cache.clear()
        app._catalog_repository_cache.update(self.original_repositories)
        app._user_data_dir = self.original_user_data_dir
        self.tmp.cleanup()

    def test_audit_accepts_sql_canonical_details_and_deferred_projections(self):
        path = "E:/Movies/Parity Movie.2024.1080p.mkv"
        self.store.apply_tmdb_match(path, {
            "tmdb_id": "42",
            "imdb_id": "tt0000042",
            "title": "Parity Movie",
            "year": "2024",
            "plot": "Stored detail.",
            "cast": [{"name": "Actor"}],
        })
        self.store.update_file_record(path, {"filename": "Parity Movie.2024.1080p.mkv", "resolution": "1080p"})
        self.store.save_plex_metadata(path, {"plex_title": "Parity Movie", "plex_year": "2024", "plex_summary": "Plex detail."})

        report = audit_catalog(self.tmp.name)

        self.assertTrue(report["passed"])
        self.assertEqual(report["checked_records"], 1)
        self.assertEqual(report["accepted_records"], 1)
        self.assertEqual(report["provider_calls"], 0)

    def test_audit_accepts_plex_as_the_active_persisted_detail_provider(self):
        path = "E:/Movies/Plex Fallback.2024.1080p.mkv"
        self.store.update_file_record(path, {
            "filename": "Plex Fallback.2024.1080p.mkv",
            "identity_status": "accepted",
            "identity_title": "Plex Fallback",
            "identity_year": "2024",
            "identity_source": "verified_tmdb",
            "display_provider": "tmdb",
            "metadata_status": "accepted",
            "metadata_accepted": True,
            "tmdb_id": "99",
        })
        self.store.save_plex_metadata(path, {
            "plex_title": "Plex Fallback",
            "plex_year": "2024",
            "plex_summary": "Persisted fallback detail.",
        })

        report = audit_catalog(self.tmp.name)

        self.assertTrue(report["passed"])
        self.assertEqual(report["active_detail_providers"], {"plex_snapshot": 1})

    def test_audit_rejects_tmdb_display_rows_without_a_sql_snapshot(self):
        path = "E:/Movies/Missing Snapshot.2024.mkv"
        self.store.update_file_record(path, {
            "filename": "Missing Snapshot.2024.mkv",
            "identity_status": "accepted",
            "identity_title": "Missing Snapshot",
            "identity_year": "2024",
            "identity_source": "manual_tmdb",
            "display_provider": "tmdb",
            "metadata_status": "accepted",
            "metadata_accepted": True,
            "tmdb_id": "404",
        })

        report = audit_catalog(self.tmp.name)

        self.assertFalse(report["passed"])
        self.assertEqual(len(report["violations"]["deferred_details"]), 1)


if __name__ == "__main__":
    unittest.main()
