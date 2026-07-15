import tempfile
import unittest
from pathlib import Path

from app import AppMetadataStore
from services.catalog_repository import CatalogRepository


class MetadataJsonReliabilityTest(unittest.TestCase):
    def test_write_is_durable_in_sqlite_without_a_json_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AppMetadataStore(Path(tmp))
            store._write_json(store.files_file, {"files": {"first": {"title": "Alien"}}})
            store._write_json(store.files_file, {"files": {"second": {"title": "Aliens"}}})
            restarted = CatalogRepository(Path(tmp), database_path=store.catalog.database_path)
            try:
                persisted = restarted.read_document("app_metadata/files.json", {"files": {}})
            finally:
                restarted.close(flush=False)

            self.assertIn("second", persisted["files"])
            self.assertFalse(store.files_file.exists())

    def test_malformed_export_cannot_override_catalog_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AppMetadataStore(Path(tmp))
            store._write_json(store.files_file, {"files": {"first": {"title": "Alien"}}})
            store._write_json(store.files_file, {"files": {"second": {"title": "Aliens"}}})
            store.base_dir.mkdir(parents=True, exist_ok=True)
            store.files_file.write_text("{broken", encoding="utf-8")

            recovered = store._read_json(store.files_file, {"files": {}})

            self.assertIn("second", recovered["files"])

    def test_malformed_legacy_file_is_ignored_after_catalog_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AppMetadataStore(Path(tmp))
            store.base_dir.mkdir(parents=True)
            store.files_file.write_text("{broken", encoding="utf-8")

            recovered = store._read_json(store.files_file, {"files": {}})

            self.assertEqual(recovered, {"files": {}})


if __name__ == "__main__":
    unittest.main()
