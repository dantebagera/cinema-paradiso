from pathlib import Path
import unittest


class WindowsLauncherTest(unittest.TestCase):
    def setUp(self):
        self.run_bat = Path(__file__).resolve().parents[1] / "run.bat"
        self.script = self.run_bat.read_text(encoding="utf-8").lower()

    def test_launcher_bootstraps_source_zip_before_starting_flask(self):
        self.assertIn("dist\\index.html", self.script)
        self.assertIn("npm.cmd install", self.script)
        self.assertIn("npm.cmd run build", self.script)
        self.assertIn("python -m venv .venv", self.script)
        self.assertIn("pip install -r requirements.txt", self.script)

    def test_launcher_opens_browser_after_frontend_build(self):
        build_position = self.script.index("npm.cmd run build")
        browser_position = self.script.index('start "" "http://localhost:5000"')

        self.assertLess(build_position, browser_position)


if __name__ == "__main__":
    unittest.main()
