import tempfile
import unittest
from pathlib import Path


class PortableReleasePackagingTests(unittest.TestCase):
    def test_release_plan_excludes_qbittorrent_debug_symbols(self):
        from tools.build_portable_release import should_include_qbt_file

        self.assertFalse(should_include_qbt_file("qbittorrent.pdb"))
        self.assertTrue(should_include_qbt_file("qbittorrent.exe"))

    def test_release_runtime_manifest_names_bundled_qbt_version(self):
        from tools.build_portable_release import build_qbt_manifest

        manifest = build_qbt_manifest("5.2.2")

        self.assertEqual(manifest["name"], "qBittorrent")
        self.assertEqual(manifest["version"], "5.2.2")
        self.assertEqual(manifest["source"], "official qBittorrent Windows x64 release")
        self.assertEqual(manifest["bundled_for"], "Cinema Paradiso 2.6.4")

    def test_copy_qbt_runtime_excludes_profile_user_data_and_requires_exe(self):
        from tools.build_portable_release import copy_qbt_runtime

        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "qbt-source"
            destination = Path(root) / "release" / "runtime" / "qbittorrent"
            source.mkdir()
            (source / "qbittorrent.exe").write_bytes(b"exe")
            (source / "qbittorrent.pdb").write_bytes(b"debug")
            (source / "profile").mkdir()
            (source / "profile" / "qBittorrent.ini").write_text("user", encoding="utf-8")
            (source / "BT_backup").mkdir()
            (source / "BT_backup" / "queue").write_text("user", encoding="utf-8")

            manifest = copy_qbt_runtime(source, destination, version="5.2.2")

            self.assertTrue((destination / "qbittorrent.exe").exists())
            self.assertFalse((destination / "qbittorrent.pdb").exists())
            self.assertFalse((destination / "profile").exists())
            self.assertFalse((destination / "BT_backup").exists())
            self.assertEqual(manifest["version"], "5.2.2")


if __name__ == "__main__":
    unittest.main()
