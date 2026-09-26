"""Characterize shared safety owners before introducing TV callers."""
import json
from pathlib import Path
import unittest

from services.qbittorrent import TorrentValidationError, validate_torrent_manifest


class NativeTVSafetyBaselineTests(unittest.TestCase):
    def test_movie_validator_rejects_unsafe_pack_members_before_transfer(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/native_tv_cases.json').read_text())
        for path in fixture['dangerous_paths']:
            with self.subTest(path=path), self.assertRaises(TorrentValidationError):
                validate_torrent_manifest({'info': {'files': [
                    {'path': 'Harbor.S01E01.mkv', 'length': 1_000_000_000},
                    {'path': path, 'length': 1000},
                ]}})

    def test_wrong_hash_and_advertised_size_cannot_be_hidden_by_valid_video(self):
        manifest = {'hash': 'a' * 40, 'info': {'files': [
            {'path': 'Harbor.S01E01.mkv', 'length': 1_000_000_000},
            {'path': 'Harbor.S01E02.mkv', 'length': 1_000_000_000},
        ]}}
        with self.assertRaises(TorrentValidationError):
            validate_torrent_manifest(manifest, expected_hash='b' * 40)
        with self.assertRaises(TorrentValidationError):
            validate_torrent_manifest(manifest, expected_size=8_000_000_000)
        result = validate_torrent_manifest(manifest, expected_hash='a' * 40)
        self.assertEqual(result['file_count'], 2)
        self.assertEqual(result['total_size'], 2_000_000_000)
