import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from tools.catalog_migration_backup import (
    BackupError,
    create_backup,
    restore_backup,
    verify_backup,
)


class CatalogMigrationBackupTest(unittest.TestCase):
    def _project(self, root, external_user_data=True):
        project = Path(root) / "project"
        project.mkdir()
        user_data = Path(root) / "user-data" if external_user_data else project / "data"
        metadata = user_data / "app_metadata"
        metadata.mkdir(parents=True)
        (project / "package.json").write_text(json.dumps({"version": "2.7.0"}), encoding="utf-8")
        (project / "config.json").write_text(json.dumps({
            "user_data_dir": str(user_data),
            "tmdb_key": "secret-key",
        }), encoding="utf-8")
        (metadata / "files.json").write_text(json.dumps({"files": {"one": {}, "two": {}}}), encoding="utf-8")
        (metadata / "tmdb_metadata.json").write_text(json.dumps({"movies": {"1": {}}}), encoding="utf-8")
        (metadata / "plex_metadata.json").write_text(json.dumps({"files": {"one": {}}}), encoding="utf-8")
        (metadata / "manual_matches.json").write_text(json.dumps({"matches": {"one": {}}}), encoding="utf-8")
        (user_data / "user_lists.json").write_text(json.dumps({
            "lists": [{"id": "watched", "movies": [{"tmdb_id": "1"}]}],
        }), encoding="utf-8")
        (user_data / "user_collections.json").write_text(json.dumps({"overrides": {"10": {}}}), encoding="utf-8")
        (user_data / "followed_releases.json").write_text(json.dumps({"movies": [{"tmdb_id": "2"}]}), encoding="utf-8")
        qbt = user_data / "qbittorrent"
        qbt.mkdir()
        (qbt / "jobs.json").write_text(json.dumps({"jobs": {"hash": {}}}), encoding="utf-8")
        (qbt / "runtime.json").write_text(json.dumps({"version": "5.2.2"}), encoding="utf-8")
        (qbt / "versions").mkdir()
        (qbt / "versions" / "qbittorrent.exe").write_bytes(b"large runtime")
        return project, user_data

    def test_backup_uses_configured_user_data_and_records_counts(self):
        with tempfile.TemporaryDirectory() as root:
            project, _ = self._project(root)
            archive, manifest = create_backup(
                project,
                Path(root) / "backups",
                now=datetime(2026, 7, 13, 10, 0, tzinfo=timezone.utc),
            )

            names = {item["archive_path"] for item in manifest["files"]}

        self.assertEqual(archive.name, "cp-catalog-migration-20260713T100000Z.zip")
        self.assertIn("project/config.json", names)
        self.assertIn("user-data/app_metadata/files.json", names)
        self.assertIn("user-data/qbittorrent/jobs.json", names)
        self.assertNotIn("user-data/qbittorrent/versions/qbittorrent.exe", names)
        self.assertEqual(manifest["semantic_counts"]["file_records"], 2)
        self.assertEqual(manifest["semantic_counts"]["manual_matches"], 1)
        self.assertEqual(manifest["semantic_counts"]["list_movies"], 1)
        self.assertEqual(manifest["semantic_counts"]["qbittorrent_jobs"], 1)

    def test_verify_checks_hashes_and_semantic_counts(self):
        with tempfile.TemporaryDirectory() as root:
            project, _ = self._project(root)
            archive, expected = create_backup(project, Path(root) / "backups")

            verified = verify_backup(archive)

        self.assertEqual(verified["totals"], expected["totals"])
        self.assertEqual(verified["semantic_counts"], expected["semantic_counts"])

    def test_verify_rejects_modified_archived_state(self):
        with tempfile.TemporaryDirectory() as root:
            project, _ = self._project(root)
            archive, _ = create_backup(project, Path(root) / "backups")
            tampered = Path(root) / "tampered.zip"
            with zipfile.ZipFile(archive, "r") as source, zipfile.ZipFile(tampered, "w") as target:
                for info in source.infolist():
                    payload = source.read(info.filename)
                    if info.filename == "user-data/app_metadata/files.json":
                        payload = b'{"files": {}}'
                    target.writestr(info, payload)

            with self.assertRaisesRegex(BackupError, "size mismatch|hash mismatch"):
                verify_backup(tampered)

    def test_restore_writes_only_to_empty_rehearsal_directory(self):
        with tempfile.TemporaryDirectory() as root:
            project, _ = self._project(root)
            archive, manifest = create_backup(project, Path(root) / "backups")
            destination = Path(root) / "restore"

            restored, restored_manifest = restore_backup(archive, destination)

            self.assertEqual(restored, destination.resolve())
            self.assertEqual(restored_manifest["semantic_counts"], manifest["semantic_counts"])
            self.assertTrue((destination / "project" / "config.json").is_file())
            self.assertTrue((destination / "user-data" / "app_metadata" / "files.json").is_file())
            with self.assertRaisesRegex(BackupError, "not empty"):
                restore_backup(archive, destination)


if __name__ == "__main__":
    unittest.main()
