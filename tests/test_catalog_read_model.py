import tempfile
import unittest
from pathlib import Path

from services.catalog_read_model import CatalogReadModel


class CatalogReadModelTest(unittest.TestCase):
    def _documents(self, title="Alien"):
        return {
            "app_metadata/files.json": {"files": {
                "e:/movies/alien.mkv": {
                    "path": "E:/Movies/Alien.mkv",
                    "identity_status": "accepted",
                    "identity_title": title,
                    "identity_year": "1979",
                    "tmdb_id": "348",
                    "metadata_accepted": True,
                }
            }},
            "app_metadata/tmdb_metadata.json": {"movies": {
                "348": {"tmdb_id": "348", "title": title, "year": "1979"}
            }},
        }

    def test_reuses_current_database_without_loading_json_again(self):
        with tempfile.TemporaryDirectory() as root:
            model = CatalogReadModel(Path(root) / "catalog.sqlite")
            calls = []
            model.ensure_current(["revision-1"], lambda: calls.append(1) or self._documents())
            model.ensure_current(["revision-1"], lambda: calls.append(2) or self._documents())

        self.assertEqual(calls, [1])

    def test_revision_change_atomically_rebuilds_read_model(self):
        with tempfile.TemporaryDirectory() as root:
            model = CatalogReadModel(Path(root) / "catalog.sqlite")
            model.ensure_current(["revision-1"], lambda: self._documents())
            store = model.ensure_current(["revision-2"], lambda: self._documents("Alien Director's Cut"))

            candidates = store.ownership_candidates(["tmdb:348"])

        self.assertEqual(candidates[0]["tmdb_json"]["title"], "Alien Director's Cut")


if __name__ == "__main__":
    unittest.main()
