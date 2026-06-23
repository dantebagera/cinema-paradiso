import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

import app


class FolderBrowserApiTest(unittest.TestCase):
    def test_folder_browser_lists_child_directories_without_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Movies").mkdir()
            (root / "Exports").mkdir()
            (root / "movie.mkv").write_bytes(b"video")

            response = app.app.test_client().get(f"/api/system/folders?path={quote(str(root))}")

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["current_path"], str(root.resolve()))
            self.assertIn("parent", payload)
            self.assertEqual([entry["name"] for entry in payload["entries"]], ["Exports", "Movies"])
            self.assertTrue(all(entry["type"] == "folder" for entry in payload["entries"]))

    def test_folder_browser_reports_invalid_path(self):
        response = app.app.test_client().get("/api/system/folders?path=Z:/definitely/not/here")

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())


if __name__ == "__main__":
    unittest.main()
