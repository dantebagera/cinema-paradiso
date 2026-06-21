import tempfile
import unittest
from pathlib import Path

import app


class LibraryStatsTest(unittest.TestCase):
    def test_stats_counts_plex_filename_fallback_as_matched(self):
        original_dirs = app._movies_dirs
        original_dir = app._movies_dir
        original_plex_cache = dict(app._plex_cache)
        original_plex_by_fname = dict(app._plex_matched_by_fname)
        original_plex_token = app._plex_token

        with tempfile.TemporaryDirectory() as tmp:
            movie = Path(tmp) / "Movie.2000.1080p.mkv"
            movie.write_bytes(b"")
            try:
                app._movies_dirs = [tmp]
                app._movies_dir = tmp
                app._plex_cache = {}
                app._plex_matched_by_fname = {
                    movie.name.lower(): {"plex_title": "Movie", "plex_year": "2000"}
                }
                app._plex_token = "token"

                response = app.app.test_client().get("/api/stats")
            finally:
                app._movies_dirs = original_dirs
                app._movies_dir = original_dir
                app._plex_cache = original_plex_cache
                app._plex_matched_by_fname = original_plex_by_fname
                app._plex_token = original_plex_token

        payload = response.get_json()
        self.assertEqual(payload["plex_matched"], 1)
        self.assertEqual(payload["plex_unmatched"], 0)


if __name__ == "__main__":
    unittest.main()
