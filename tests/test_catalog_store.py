import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from services.catalog_store import CATALOG_SCHEMA_VERSION, CatalogStore
from tools.build_shadow_catalog import _load_documents
from tools.catalog_migration_backup import BackupError


class CatalogStoreTest(unittest.TestCase):
    def _documents(self):
        return {
            "app_metadata/files.json": {
                "files": {
                    "e:/movies/alien.mkv": {
                        "path": "E:/Movies/Alien.mkv",
                        "filename": "Alien.mkv",
                        "library_root": "E:/Movies",
                        "size": 100,
                        "resolution": "1080p",
                        "rip_source": "Blu-ray",
                        "identity_status": "accepted",
                        "identity_title": "Alien",
                        "identity_year": "1979",
                        "identity_source": "manual_tmdb",
                        "identity_revision": 3,
                        "tmdb_id": "348",
                        "imdb_id": "tt0078748",
                        "display_provider": "tmdb",
                        "metadata_status": "accepted",
                        "metadata_accepted": True,
                        "manual_lock": True,
                    }
                }
            },
            "app_metadata/tmdb_metadata.json": {
                "movies": {"348": {"tmdb_id": "348", "imdb_id": "tt0078748", "title": "Alien", "year": "1979"}}
            },
            "app_metadata/plex_metadata.json": {
                "files": {"e:/movies/alien.mkv": {"path": "E:/Movies/Alien.mkv", "plex_title": "Alien", "plex_year": "1979"}}
            },
            "app_metadata/manual_matches.json": {
                "matches": {"e:/movies/alien.mkv": {"path": "E:/Movies/Alien.mkv", "provider": "tmdb", "tmdb_id": "348", "accepted": True}}
            },
            "user_lists.json": {
                "lists": [{"id": "watched", "name": "Watched", "system_type": "watched", "movies": [{"tmdb_id": "348", "title": "Alien", "year": "1979"}]}]
            },
            "user_collections.json": {"overrides": {"10": {"name": "Alien Collection"}}},
            "followed_releases.json": {"movies": [{"tmdb_id": "679", "title": "Aliens", "year": "1986"}]},
        }

    def _expected(self):
        return {
            "file_records": 1,
            "tmdb_movies": 1,
            "plex_files": 1,
            "manual_matches": 1,
            "user_lists": 1,
            "list_movies": 1,
            "collection_overrides": 1,
            "followed_releases": 1,
        }

    def test_import_preserves_identity_provider_and_user_state(self):
        with tempfile.TemporaryDirectory() as root:
            store = CatalogStore(Path(root) / "catalog.sqlite")
            store.import_documents(self._documents(), {"semantic_counts": self._expected()})
            report = store.parity_report(self._expected())
            connection = store.connect()
            try:
                media = dict(connection.execute("SELECT * FROM media_files").fetchone())
                list_item = dict(connection.execute("SELECT * FROM list_items").fetchone())
            finally:
                connection.close()

        self.assertTrue(report["passed"])
        self.assertEqual(report["schema_version"], CATALOG_SCHEMA_VERSION)
        self.assertEqual(media["tmdb_id"], "348")
        self.assertEqual(media["identity_revision"], 3)
        self.assertEqual(media["manual_lock"], 1)
        self.assertEqual(list_item["identity_key"], "tmdb:348")

    def test_parity_detects_missing_imported_rows(self):
        with tempfile.TemporaryDirectory() as root:
            store = CatalogStore(Path(root) / "catalog.sqlite")
            store.import_documents(self._documents(), {})
            connection = store.connect()
            try:
                connection.execute("DELETE FROM tmdb_movies")
                connection.commit()
            finally:
                connection.close()

            report = store.parity_report(self._expected())

        self.assertFalse(report["passed"])
        self.assertEqual(report["mismatches"]["tmdb_movies"], {"expected": 1, "actual": 0})

    def test_schema_uses_identity_and_quality_indexes(self):
        with tempfile.TemporaryDirectory() as root:
            store = CatalogStore(Path(root) / "catalog.sqlite")
            store.initialize()
            connection = store.connect()
            try:
                indexes = {
                    row["name"]
                    for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")
                }
            finally:
                connection.close()

        self.assertIn("idx_media_files_tmdb_id", indexes)
        self.assertIn("idx_media_files_title_year", indexes)
        self.assertIn("idx_media_files_quality", indexes)
        self.assertIn("idx_media_identity_key", indexes)

    def test_ownership_candidates_support_all_existing_identity_aliases(self):
        with tempfile.TemporaryDirectory() as root:
            store = CatalogStore(Path(root) / "catalog.sqlite")
            store.import_documents(self._documents(), {})

            by_tmdb = store.ownership_candidates(["tmdb:348"])
            by_imdb = store.ownership_candidates(["imdb:tt0078748"])
            by_title = store.ownership_candidates(["title:alien|1979"])

        self.assertEqual([row["path"] for row in by_tmdb], ["E:/Movies/Alien.mkv"])
        self.assertEqual([row["path"] for row in by_imdb], ["E:/Movies/Alien.mkv"])
        self.assertEqual([row["path"] for row in by_title], ["E:/Movies/Alien.mkv"])
        self.assertEqual(by_tmdb[0]["tmdb_json"]["title"], "Alien")

    def test_library_candidates_return_provider_snapshots_without_filesystem_scan(self):
        with tempfile.TemporaryDirectory() as root:
            store = CatalogStore(Path(root) / "catalog.sqlite")
            store.import_documents(self._documents(), {})

            rows = store.library_candidates()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["path"], "E:/Movies/Alien.mkv")
        self.assertEqual(rows[0]["tmdb_json"]["title"], "Alien")
        self.assertEqual(rows[0]["plex_json"]["plex_title"], "Alien")

    def test_import_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            store = CatalogStore(Path(root) / "catalog.sqlite")
            store.import_documents(self._documents(), {})
            store.import_documents(self._documents(), {})

            report = store.parity_report(self._expected())

        self.assertTrue(report["passed"])

    def test_loader_ignores_historical_json_not_owned_by_catalog(self):
        with tempfile.TemporaryDirectory() as root:
            archive_path = Path(root) / "backup.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("user-data/app_metadata/files.json", json.dumps({"files": {}}))
                archive.writestr("user-data/app_metadata/backups/old/smart_match.json", "{broken")
            manifest = {
                "files": [
                    {"archive_path": "user-data/app_metadata/files.json"},
                    {"archive_path": "user-data/app_metadata/backups/old/smart_match.json"},
                ]
            }

            documents = _load_documents(archive_path, manifest)

        self.assertEqual(documents, {"app_metadata/files.json": {"files": {}}})

    def test_loader_rejects_corrupted_authoritative_document(self):
        with tempfile.TemporaryDirectory() as root:
            archive_path = Path(root) / "backup.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("user-data/app_metadata/files.json", "{broken")
            manifest = {"files": [{"archive_path": "user-data/app_metadata/files.json"}]}

            with self.assertRaises(BackupError):
                _load_documents(archive_path, manifest)


if __name__ == "__main__":
    unittest.main()
