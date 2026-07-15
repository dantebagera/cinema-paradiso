from pathlib import Path
import unittest
from tests.frontend_source import read_frontend_source


APP_JSX = Path(__file__).resolve().parents[1] / "src" / "App.jsx"


class DiscoverIndexerScopeUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = read_frontend_source()

    def test_browse_indexer_dropdown_is_backend_scope(self):
        self.assertIn("/api/explore/indexers", self.source)
        self.assertIn("params.set('indexer_id', browseIndexer)", self.source)
        self.assertIn("Indexer source", self.source)
        self.assertIn("selectedBrowseIndexerName", self.source)


if __name__ == "__main__":
    unittest.main()
