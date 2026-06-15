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
        browser_position = self.script.index('start "" powershell')

        self.assertLess(build_position, browser_position)
        self.assertIn("start-sleep -seconds 2", self.script)

    def test_launcher_reports_and_runs_flask_after_build(self):
        build_position = self.script.index("npm.cmd run build")
        flask_position = self.script.index('".venv\\scripts\\python.exe" app.py')

        self.assertLess(build_position, flask_position)
        self.assertIn("launching flask backend", self.script)
        self.assertIn("flask stopped with exit code", self.script)


class FlaskStartupTest(unittest.TestCase):
    def setUp(self):
        app_py = Path(__file__).resolve().parents[1] / "app.py"
        self.source = app_py.read_text(encoding="utf-8").lower()

    def test_flask_reloader_is_disabled_for_batch_launcher(self):
        self.assertIn("use_reloader=false", self.source)
        self.assertNotIn("use_reloader=true", self.source)


if __name__ == "__main__":
    unittest.main()
