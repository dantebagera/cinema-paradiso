import tempfile
import unittest
from pathlib import Path

import app


class DuplicateIdentityTest(unittest.TestCase):
    def test_scan_duplicates_uses_manual_tmdb_title_against_plex_title(self):
        original_dirs = app._movies_dirs
        original_dir = app._movies_dir
        original_user_data_dir = app._user_data_dir
        original_plex_cache = dict(app._plex_cache)

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            original = Path(tmp) / "Batteries Not Included 1987 1080p.mkv"
            copied = Path(tmp) / "Batteries Not Includedbbb (1987) 1080p.mkv"
            original.write_bytes(b"original")
            copied.write_bytes(b"copy")
            try:
                app._movies_dirs = [tmp]
                app._movies_dir = tmp
                app._user_data_dir = data_tmp
                app._plex_cache = {
                    app._norm(str(original)): {
                        "plex_title": "*batteries not included",
                        "plex_year": "1987",
                    }
                }
                app.AppMetadataStore(Path(data_tmp)).apply_tmdb_match(str(copied), {
                    "tmdb_id": "11548",
                    "title": "*batteries not included",
                    "year": "1987",
                })

                duplicates, stats = app.scan_duplicates([tmp])
            finally:
                app._movies_dirs = original_dirs
                app._movies_dir = original_dir
                app._user_data_dir = original_user_data_dir
                app._plex_cache = original_plex_cache

        self.assertEqual(stats["groups"], 1)
        self.assertEqual(stats["extra_copies"], 1)
        self.assertEqual(len(duplicates[0]["files"]), 2)


if __name__ == "__main__":
    unittest.main()
