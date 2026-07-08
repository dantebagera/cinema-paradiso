import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.qbittorrent import (
    BUNDLED_QBT_VERSION,
    QBittorrentJobStore,
    QBittorrentManager,
    bundled_runtime_root,
    build_downloads_html,
    is_allowed_prowlarr_url,
    is_path_within,
    normalize_architecture,
    process_launch_kwargs,
    select_release_asset,
    validate_magnet_url,
)


class QBittorrentPlatformTests(unittest.TestCase):
    def test_normalizes_supported_architectures(self):
        self.assertEqual(normalize_architecture("AMD64"), "x86_64")
        self.assertEqual(normalize_architecture("x86_64"), "x86_64")
        self.assertEqual(normalize_architecture("arm64"), "arm64")

    def test_selects_official_assets_by_platform(self):
        assets = [
            {"name": "qbittorrent_5.2.2_x64_setup.exe", "browser_download_url": "win"},
            {"name": "qbittorrent-5.2.2.dmg", "browser_download_url": "mac"},
            {"name": "qbittorrent-5.2.2_x86_64.AppImage", "browser_download_url": "linux"},
        ]
        self.assertEqual(select_release_asset(assets, "windows", "x86_64")["browser_download_url"], "win")
        self.assertEqual(select_release_asset(assets, "darwin", "x86_64")["browser_download_url"], "mac")
        self.assertEqual(select_release_asset(assets, "linux", "x86_64")["browser_download_url"], "linux")
        self.assertIsNone(select_release_asset(assets, "linux", "arm64"))

    def test_status_remains_available_when_github_is_offline(self):
        with tempfile.TemporaryDirectory() as root:
            manager = QBittorrentManager(root, {}, [])
            manager._github_release = lambda _url: (_ for _ in ()).throw(OSError("offline"))

            status = manager.status()

            self.assertFalse(status["installed"])
            self.assertIn("supported", status)

    @unittest.skipUnless(os.name == "nt", "Windows bundled runtime path")
    def test_manager_detects_bundled_runtime_when_runtime_state_is_missing(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            bundled = bundled_runtime_root(root_path) / "qbittorrent.exe"
            bundled.parent.mkdir(parents=True)
            bundled.touch()
            manager = QBittorrentManager(root_path / "data", {}, [], app_root=root_path)

            self.assertEqual(manager.active_executable(), bundled)
            self.assertEqual(manager.status()["version"], BUNDLED_QBT_VERSION)

    def test_status_does_not_query_github_for_updates_in_frozen_runtime_mode(self):
        with tempfile.TemporaryDirectory() as root:
            manager = QBittorrentManager(root, {}, [])
            manager._github_release = lambda _url: (_ for _ in ()).throw(AssertionError("network update check should not run"))

            status = manager.status()

            self.assertFalse(status["update_available"])
            self.assertEqual(status["update_policy"], "bundled")

    @unittest.skipUnless(os.name == "nt", "Windows-specific process startup behavior")
    def test_windows_launch_hides_native_qbittorrent_window(self):
        import subprocess

        kwargs = process_launch_kwargs("nt")

        self.assertEqual(kwargs["startupinfo"].wShowWindow, subprocess.SW_HIDE)
        self.assertTrue(kwargs["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW)
        self.assertTrue(kwargs["creationflags"] & subprocess.CREATE_NEW_PROCESS_GROUP)
        self.assertTrue(kwargs["creationflags"] & subprocess.DETACHED_PROCESS)

    @unittest.skipUnless(os.name == "nt", "Windows-specific process window behavior")
    def test_manager_hides_qbittorrent_window_after_webui_is_ready(self):
        with tempfile.TemporaryDirectory() as root:
            manager = QBittorrentManager(root, {}, [])
            executable = Path(root) / "qbittorrent.exe"
            executable.touch()
            manager._save_runtime_state({"version": "test", "executable": str(executable)})
            manager.client.version = MagicMock(side_effect=[OSError("stopped"), "v5.2.2"])
            process = MagicMock(pid=1234)

            with (
                patch.object(manager, "_write_profile"),
                patch("services.qbittorrent.subprocess.Popen", return_value=process),
                patch("services.qbittorrent.hide_process_windows") as hide,
                patch("services.qbittorrent.time.sleep"),
            ):
                self.assertTrue(manager.ensure_running())

            hide.assert_called_once_with(1234)


class QBittorrentSafetyTests(unittest.TestCase):
    def test_validates_only_btih_or_btmh_magnets(self):
        self.assertTrue(validate_magnet_url("magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"))
        self.assertTrue(validate_magnet_url("magnet:?xt=urn:btmh:1220" + ("a" * 64)))
        self.assertFalse(validate_magnet_url("https://example.test/file.torrent"))
        self.assertFalse(validate_magnet_url("magnet:?dn=missing-hash"))

    def test_constrains_torrent_fetch_to_configured_prowlarr_origin(self):
        self.assertTrue(is_allowed_prowlarr_url(
            "http://127.0.0.1:9696/download?id=5",
            "http://127.0.0.1:9696",
        ))
        self.assertFalse(is_allowed_prowlarr_url(
            "http://127.0.0.1:9697/download?id=5",
            "http://127.0.0.1:9696",
        ))
        self.assertFalse(is_allowed_prowlarr_url(
            "http://127.0.0.1:9696.evil.test/download",
            "http://127.0.0.1:9696",
        ))

    def test_path_containment_uses_real_path_boundaries(self):
        with tempfile.TemporaryDirectory() as root:
            child = Path(root) / "child"
            sibling = Path(f"{root}-other")
            self.assertTrue(is_path_within(child, root))
            self.assertFalse(is_path_within(sibling, root))


class QBittorrentJobStoreTests(unittest.TestCase):
    def test_persists_jobs_atomically(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "jobs.json"
            store = QBittorrentJobStore(path)
            store.upsert("ABC", {"title": "Movie", "state": "downloading"})

            reopened = QBittorrentJobStore(path)
            self.assertEqual(reopened.get("abc")["title"], "Movie")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["jobs"]["abc"]["state"], "downloading")

    def test_import_moves_payload_unchanged_and_marks_job(self):
        with tempfile.TemporaryDirectory() as root:
            staging = Path(root) / "incomplete"
            destination = Path(root) / "library"
            source = staging / "Movie.2026.1080p-GROUP"
            source.mkdir(parents=True)
            (source / "Movie.2026.1080p-GROUP.mkv").write_bytes(b"movie")
            store = QBittorrentJobStore(Path(root) / "jobs.json")
            store.upsert("abc", {
                "title": "Movie",
                "state": "completed",
                "payload_paths": [str(source)],
                "destination": str(destination),
            })

            result = store.move_completed_payload("abc", allowed_staging_root=staging)

            moved = destination / source.name
            self.assertEqual(result["state"], "imported")
            self.assertTrue((moved / "Movie.2026.1080p-GROUP.mkv").exists())
            self.assertFalse(source.exists())

    def test_import_resumes_after_one_payload_was_already_moved(self):
        with tempfile.TemporaryDirectory() as root:
            staging = Path(root) / "incomplete"
            destination = Path(root) / "library"
            first = staging / "Movie.CD1"
            second = staging / "Movie.CD2"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            (first / "part1.mkv").write_bytes(b"one")
            (second / "part2.mkv").write_bytes(b"two")
            destination.mkdir()
            os.replace(first, destination / first.name)
            store = QBittorrentJobStore(Path(root) / "jobs.json")
            store.upsert("abc", {
                "state": "finalizing",
                "payload_paths": [str(first), str(second)],
                "destination": str(destination),
            })

            result = store.move_completed_payload("abc", allowed_staging_root=staging)

            self.assertEqual(result["state"], "imported")
            self.assertTrue((destination / first.name / "part1.mkv").exists())
            self.assertTrue((destination / second.name / "part2.mkv").exists())

    def test_manager_recovers_finalizing_job_after_torrent_was_removed(self):
        with tempfile.TemporaryDirectory() as root:
            staging = Path(root) / "incomplete"
            destination = Path(root) / "library"
            payload = staging / "Movie.2026.1080p-GROUP"
            payload.mkdir(parents=True)
            (payload / "movie.mkv").write_bytes(b"movie")
            manager = QBittorrentManager(
                root,
                {"incomplete_dir": str(staging), "download_dir": str(destination)},
                [str(destination)],
            )
            manager.jobs.upsert("abc", {
                "state": "finalizing",
                "payload_paths": [str(payload)],
                "destination": str(destination),
            })
            manager.ensure_running = lambda: True
            manager.client.torrents = lambda: []

            results = manager.process_completed()

            self.assertEqual(results[0]["state"], "imported")
            self.assertTrue((destination / payload.name / "movie.mkv").exists())

    def test_manager_does_not_resubmit_already_imported_magnet(self):
        with tempfile.TemporaryDirectory() as root:
            staging = Path(root) / "incomplete"
            destination = Path(root) / "library"
            manager = QBittorrentManager(
                root,
                {"incomplete_dir": str(staging), "download_dir": str(destination)},
                [str(destination)],
            )
            magnet = "magnet:?xt=urn:btih:48373C3569751AA5C51072E826DD43FFB350BA84&dn=Movie"
            manager.jobs.upsert("48373c3569751aa5c51072e826dd43ffb350ba84", {
                "title": "Movie",
                "state": "imported",
                "imported_paths": [str(destination / "Movie.mkv")],
            })
            manager.ensure_running = MagicMock(return_value=True)
            manager.client.add_magnet = MagicMock()

            result = manager.submit_magnet(magnet, {"title": "Movie", "year": "2026"})

            self.assertEqual(result["state"], "imported")
            self.assertTrue(result["already_exists"])
            self.assertEqual(result["imported_paths"], [str(destination / "Movie.mkv")])
            manager.ensure_running.assert_not_called()
            manager.client.add_magnet.assert_not_called()


class QBittorrentProxyTests(unittest.TestCase):
    def test_embedded_html_preserves_qbt_without_copying_cp_navigation(self):
        original = "<html><head><title>qBittorrent WebUI</title></head><body><main>QBT</main></body></html>"

        rendered = build_downloads_html(original)

        self.assertIn('id="cp-qbt-frame-bridge"', rendered)
        self.assertIn('Object.defineProperty(window.parent, "qBittorrent"', rendered)
        self.assertIn("<main>QBT</main>", rendered)
        self.assertNotIn('id="cp-qbt-sidebar"', rendered)
        self.assertNotIn("<iframe", rendered)


if __name__ == "__main__":
    unittest.main()
