import json
import tempfile
import unittest
from pathlib import Path

from services.catalog_repository import CatalogRepository, catalog_database_path
from services.catalog_store import CatalogError


class CatalogRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.repositories = []

    def tearDown(self):
        for repository in reversed(self.repositories):
            repository.close(flush=False)

    def _repository(self, *args, **kwargs):
        repository = CatalogRepository(*args, **kwargs)
        self.repositories.append(repository)
        return repository

    def _user_data(self, root):
        user_data = Path(root) / "user-data"
        metadata = user_data / "app_metadata"
        metadata.mkdir(parents=True)
        (metadata / "files.json").write_text(json.dumps({"files": {
            "e:/movies/alien.mkv": {
                "path": "E:/Movies/Alien.mkv",
                "filename": "Alien.mkv",
                "identity_status": "accepted",
                "identity_title": "Alien",
                "identity_year": "1979",
                "metadata_accepted": True,
                "tmdb_id": "348",
            }
        }}), encoding="utf-8")
        (metadata / "tmdb_metadata.json").write_text(json.dumps({"movies": {
            "348": {"tmdb_id": "348", "title": "Alien", "year": "1979"}
        }}), encoding="utf-8")
        (metadata / "plex_metadata.json").write_text(json.dumps({"files": {}}), encoding="utf-8")
        (metadata / "manual_matches.json").write_text(json.dumps({"matches": {}}), encoding="utf-8")
        (metadata / "metadata_authority.json").write_text(json.dumps({"active_provider": "tmdb"}), encoding="utf-8")
        (user_data / "user_lists.json").write_text(json.dumps({"lists": [
            {"id": "watched", "name": "Watched", "system_type": "watched", "movies": []}
        ]}), encoding="utf-8")
        return user_data

    def test_activation_imports_json_once_then_sql_owns_reads(self):
        with tempfile.TemporaryDirectory() as root:
            user_data = self._user_data(root)
            database = Path(root) / "catalog.sqlite"
            repository = self._repository(user_data, database, export_delay=60)

            self.assertTrue(repository.activate_from_json())
            (user_data / "app_metadata" / "files.json").write_text('{"files": {}}', encoding="utf-8")
            restarted = self._repository(user_data, database, export_delay=60)

            self.assertFalse(restarted.activate_from_json())
            document = restarted.read_document("app_metadata/files.json", {"files": {}})

        self.assertIn("e:/movies/alien.mkv", document["files"])

    def test_file_upsert_is_row_level_and_export_is_deferred(self):
        with tempfile.TemporaryDirectory() as root:
            user_data = self._user_data(root)
            repository = self._repository(user_data, Path(root) / "catalog.sqlite", export_delay=60, auto_export=True)
            repository.activate_from_json()
            source_path = user_data / "app_metadata" / "files.json"
            before_export = source_path.read_text(encoding="utf-8")
            record = repository.read_document("app_metadata/files.json", {"files": {}})["files"]["e:/movies/alien.mkv"]

            repository.upsert_record("app_metadata/files.json", "e:/movies/alien.mkv", {
                **record,
                "resolution": "4K",
            })

            self.assertEqual(source_path.read_text(encoding="utf-8"), before_export)
            self.assertEqual(
                repository.read_document("app_metadata/files.json", {"files": {}})["files"]["e:/movies/alien.mkv"]["resolution"],
                "4K",
            )
            repository.flush_exports()
            exported = json.loads(source_path.read_text(encoding="utf-8"))

        self.assertEqual(exported["files"]["e:/movies/alien.mkv"]["resolution"], "4K")

    def test_runtime_writes_do_not_maintain_json_metadata_mirrors(self):
        with tempfile.TemporaryDirectory() as root:
            user_data = self._user_data(root)
            repository = self._repository(user_data, Path(root) / "catalog.sqlite", export_delay=0)
            repository.activate_from_json()
            source_path = user_data / "app_metadata" / "files.json"
            before = source_path.read_text(encoding="utf-8")

            repository.upsert_record("app_metadata/files.json", "e:/movies/new.mkv", {
                "path": "E:/Movies/New.mkv",
                "filename": "New.mkv",
            })
            repository.flush_exports()
            after = source_path.read_text(encoding="utf-8")

        self.assertEqual(after, before)

    def test_curation_document_replacement_updates_normalized_tables(self):
        with tempfile.TemporaryDirectory() as root:
            user_data = self._user_data(root)
            repository = self._repository(user_data, Path(root) / "catalog.sqlite", export_delay=60)
            repository.activate_from_json()
            lists = {"lists": [{
                "id": "watchlist",
                "name": "Watchlist",
                "system_type": "watchlist",
                "movies": [{"tmdb_id": "348", "title": "Alien", "year": "1979"}],
            }]}

            repository.replace_document("user_lists.json", lists)
            connection = repository.store.connect()
            try:
                counts = (
                    connection.execute("SELECT COUNT(*) FROM user_lists").fetchone()[0],
                    connection.execute("SELECT COUNT(*) FROM list_items").fetchone()[0],
                )
            finally:
                connection.close()

        self.assertEqual(counts, (1, 1))

    def test_curation_changes_do_not_invalidate_media_revision(self):
        with tempfile.TemporaryDirectory() as root:
            user_data = self._user_data(root)
            repository = self._repository(user_data, Path(root) / "catalog.sqlite", export_delay=60)
            repository.activate_from_json()
            media_before = repository.generation('media')
            curation_before = repository.generation('curation')

            repository.replace_document("user_lists.json", {"lists": []})

            self.assertEqual(repository.generation('media'), media_before)
            self.assertEqual(repository.generation('curation'), curation_before + 1)

    def test_media_changes_increment_only_media_revision(self):
        with tempfile.TemporaryDirectory() as root:
            user_data = self._user_data(root)
            repository = self._repository(user_data, Path(root) / "catalog.sqlite", export_delay=60)
            repository.activate_from_json()
            media_before = repository.generation('media')
            curation_before = repository.generation('curation')

            repository.upsert_record("app_metadata/files.json", "e:/movies/alien.mkv", {
                "path": "E:/Movies/Alien.mkv",
                "filename": "Alien.mkv",
            })

            self.assertEqual(repository.generation('media'), media_before + 1)
            self.assertEqual(repository.generation('curation'), curation_before)

    def test_catalog_paths_are_isolated_by_user_data_directory(self):
        with tempfile.TemporaryDirectory() as root:
            first = catalog_database_path(Path(root) / "one", Path(root) / "local")
            second = catalog_database_path(Path(root) / "two", Path(root) / "local")

        self.assertNotEqual(first, second)

    def test_activation_rejects_invalid_json_without_valid_backup(self):
        with tempfile.TemporaryDirectory() as root:
            user_data = Path(root) / "user-data"
            metadata = user_data / "app_metadata"
            metadata.mkdir(parents=True)
            (metadata / "files.json").write_text("{broken", encoding="utf-8")
            repository = self._repository(user_data, Path(root) / "catalog.sqlite", export_delay=0)

            with self.assertRaises(CatalogError):
                repository.activate_from_json()

    def test_path_migration_updates_owned_records_in_one_generation(self):
        with tempfile.TemporaryDirectory() as root:
            user_data = self._user_data(root)
            repository = self._repository(user_data, Path(root) / "catalog.sqlite", export_delay=60)
            repository.activate_from_json()
            repository.upsert_record("app_metadata/plex_metadata.json", "e:/movies/alien.mkv", {
                "path": "E:/Movies/Alien.mkv",
                "plex_title": "Alien",
            })
            before = repository.generation()

            changed = repository.migrate_path_records(
                "e:/movies/alien.mkv",
                "e:/movies/alien 1979.mkv",
                "E:/Movies/Alien 1979.mkv",
                {"filename": "Alien 1979.mkv"},
            )

            files = repository.read_document("app_metadata/files.json", {"files": {}})["files"]
            plex = repository.read_document("app_metadata/plex_metadata.json", {"files": {}})["files"]
            after = repository.generation()

        self.assertTrue(changed)
        self.assertEqual(after, before + 1)
        self.assertNotIn("e:/movies/alien.mkv", files)
        self.assertEqual(files["e:/movies/alien 1979.mkv"]["filename"], "Alien 1979.mkv")
        self.assertEqual(plex["e:/movies/alien 1979.mkv"]["path"], "E:/Movies/Alien 1979.mkv")

    def test_finds_cached_plex_metadata_by_poster_thumb(self):
        with tempfile.TemporaryDirectory() as root:
            user_data = self._user_data(root)
            repository = self._repository(user_data, Path(root) / "catalog.sqlite", export_delay=60)
            repository.activate_from_json()
            repository.upsert_record("app_metadata/plex_metadata.json", "e:/movies/postcards.mkv", {
                "path": "E:/Movies/Postcards.mkv",
                "plex_title": "Film Postcards: Serbia",
                "plex_thumb": "/library/metadata/1044/thumb/1777947200",
                "plex_genres": ["Short"],
            })

            records = repository.find_plex_metadata_by_thumbs([
                "/library/metadata/1044/thumb/1777947200",
            ])

        self.assertEqual(records["/library/metadata/1044/thumb/1777947200"]["plex_title"], "Film Postcards: Serbia")

    def test_full_export_is_a_verified_rollback_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            user_data = self._user_data(root)
            repository = self._repository(user_data, Path(root) / "catalog.sqlite", export_delay=60)
            repository.activate_from_json()

            names = repository.export_all()
            report = repository.verify_exports(names)

        self.assertTrue(report["passed"])
        self.assertIn("app_metadata/files.json", names)
        self.assertIn("user_lists.json", names)


if __name__ == "__main__":
    unittest.main()
