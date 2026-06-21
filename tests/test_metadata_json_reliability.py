import json
import tempfile
import unittest
from pathlib import Path

from app import AppMetadataStore, MetadataStoreError


class MetadataJsonReliabilityTest(unittest.TestCase):
    def test_write_keeps_a_last_known_good_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AppMetadataStore(Path(tmp))
            store._write_json(store.files_file, {"files": {"first": {"title": "Alien"}}})
            store._write_json(store.files_file, {"files": {"second": {"title": "Aliens"}}})

            backup = json.loads(Path(f"{store.files_file}.bak").read_text(encoding="utf-8"))
            self.assertIn("first", backup["files"])

    def test_malformed_current_file_recovers_from_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AppMetadataStore(Path(tmp))
            store._write_json(store.files_file, {"files": {"first": {"title": "Alien"}}})
            store._write_json(store.files_file, {"files": {"second": {"title": "Aliens"}}})
            store.files_file.write_text("{broken", encoding="utf-8")

            recovered = store._read_json(store.files_file, {"files": {}})

            self.assertIn("first", recovered["files"])

    def test_malformed_store_without_backup_is_not_treated_as_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AppMetadataStore(Path(tmp))
            store.base_dir.mkdir(parents=True)
            store.files_file.write_text("{broken", encoding="utf-8")

            with self.assertRaises(MetadataStoreError):
                store._read_json(store.files_file, {"files": {}})


if __name__ == "__main__":
    unittest.main()
