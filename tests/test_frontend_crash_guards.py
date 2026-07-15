from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FrontendCrashGuardsTest(unittest.TestCase):
    def test_library_uses_the_authoritative_pagination_component(self):
        source = (
            ROOT / "src" / "features" / "library" / "LibraryWorkspace.jsx"
        ).read_text(encoding="utf-8")

        self.assertIn("import Pagination from '../../components/Pagination.jsx'", source)
        self.assertGreaterEqual(source.count("<Pagination"), 2)
        self.assertNotIn("LibraryPagination", source)

    def test_react_root_catches_workspace_render_errors(self):
        main = (ROOT / "src" / "main.jsx").read_text(encoding="utf-8")
        boundary = (
            ROOT / "src" / "components" / "AppErrorBoundary.jsx"
        ).read_text(encoding="utf-8")

        self.assertIn("<AppErrorBoundary>", main)
        self.assertIn("<App />", main)
        self.assertIn("getDerivedStateFromError", boundary)
        self.assertIn("window.location.reload()", boundary)
        self.assertIn("window.location.assign('/')", boundary)


if __name__ == "__main__":
    unittest.main()
