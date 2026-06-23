import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class FakeManager:
    def __init__(self):
        self.submitted = []
        self.installed = False

    def configuration(self):
        return {
            "mode": app._qbt_mode,
            "download_dir": app._qbt_download_dir,
            "effective_download_dir": app._qbt_download_dir or app._movies_dirs[0],
            "download_dir_in_library": not bool(app._qbt_download_dir),
            "incomplete_dir": app._qbt_incomplete_dir,
            "effective_incomplete_dir": app._qbt_incomplete_dir or "data/qbittorrent/incomplete",
            "incomplete_dir_in_library": False,
            "webui_port": app._qbt_webui_port,
        }

    def status(self):
        return {**self.configuration(), "installed": self.installed, "running": self.installed, "supported": True}

    def install_latest(self):
        self.installed = True
        return self.status()

    def submit_magnet(self, magnet, metadata):
        self.submitted.append(("magnet", magnet, metadata))
        return {"hash": "abc", "state": "downloading", **metadata}

    def submit_torrent(self, content, filename, metadata):
        self.submitted.append(("torrent", content, filename, metadata))
        return {"hash": "def", "state": "downloading", **metadata}

    def process_completed(self):
        return [{"hash": "abc", "state": "imported"}]

    @property
    def jobs(self):
        return type("Jobs", (), {"all": lambda self: {"abc": {"state": "downloading"}}})()


class QBittorrentApiTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "mode": app._qbt_mode,
            "download": app._qbt_download_dir,
            "incomplete": app._qbt_incomplete_dir,
            "port": app._qbt_webui_port,
            "dirs": list(app._movies_dirs),
            "dir": app._movies_dir,
        }
        self.temp = tempfile.TemporaryDirectory()
        app._movies_dirs = [self.temp.name]
        app._movies_dir = self.temp.name
        app._qbt_mode = "embedded"
        app._qbt_download_dir = ""
        app._qbt_incomplete_dir = ""
        app._qbt_webui_port = 8686
        self.manager = FakeManager()
        self.client = app.app.test_client()
        self.manager_patch = patch.object(app, "_get_qbittorrent_manager", return_value=self.manager)
        self.save_patch = patch.object(app, "_save_config")
        self.manager_patch.start()
        self.save_patch.start()

    def tearDown(self):
        self.manager_patch.stop()
        self.save_patch.stop()
        app._qbt_mode = self.original["mode"]
        app._qbt_download_dir = self.original["download"]
        app._qbt_incomplete_dir = self.original["incomplete"]
        app._qbt_webui_port = self.original["port"]
        app._movies_dirs = self.original["dirs"]
        app._movies_dir = self.original["dir"]
        self.temp.cleanup()

    def test_config_defaults_to_embedded_and_primary_library(self):
        response = self.client.get("/api/qbittorrent/config")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["mode"], "embedded")
        self.assertEqual(data["effective_download_dir"], self.temp.name)

    def test_config_allows_external_destination_with_warning(self):
        external = str(Path(self.temp.name).parent / "external-downloads")
        response = self.client.post("/api/qbittorrent/config", json={
            "mode": "embedded",
            "download_dir": external,
            "incomplete_dir": str(Path(self.temp.name).parent / "incomplete"),
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["download_dir_in_library"])

    def test_config_rejects_incomplete_folder_inside_library(self):
        response = self.client.post("/api/qbittorrent/config", json={
            "mode": "embedded",
            "incomplete_dir": str(Path(self.temp.name) / "incomplete"),
        })

        self.assertEqual(response.status_code, 400)

    def test_submit_magnet_uses_embedded_manager(self):
        magnet = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"
        response = self.client.post("/api/qbittorrent/submit", json={
            "magnet_url": magnet,
            "title": "Movie",
            "year": "2026",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.manager.submitted[0][0], "magnet")
        self.assertEqual(self.manager.submitted[0][2]["title"], "Movie")

    def test_submit_rejects_arbitrary_download_url(self):
        response = self.client.post("/api/qbittorrent/submit", json={
            "download_url": "https://evil.test/file.torrent",
            "title": "Movie",
        })

        self.assertEqual(response.status_code, 400)

    def test_install_and_update_routes_are_disabled_for_bundled_runtime(self):
        installed = self.client.post("/api/qbittorrent/install")
        updated = self.client.post("/api/qbittorrent/update")

        self.assertEqual(installed.status_code, 410)
        self.assertEqual(updated.status_code, 410)
        self.assertIn("disabled", installed.get_json()["error"])

    def test_finalize_route_remains_available(self):
        finalized = self.client.post("/api/qbittorrent/finalize")

        self.assertEqual(finalized.get_json()["results"][0]["state"], "imported")


if __name__ == "__main__":
    unittest.main()
