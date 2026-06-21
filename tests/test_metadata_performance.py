import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import app


class MetadataPerformanceTest(unittest.TestCase):
    def test_tmdb_metadata_for_file_does_not_fetch_by_plex_id_without_refresh(self):
        original_key = app._tmdb_key
        app._tmdb_key = "tmdb-key"
        try:
            store = app.AppMetadataStore(Path(tempfile.mkdtemp()))
            with patch("app.urllib.request.urlopen") as urlopen:
                result = app._tmdb_metadata_for_file(
                    {"path": "E:/Movies/Alien.mkv", "parsed_title": "alien", "parsed_year": "1979"},
                    plex_data={"tmdb_id": "348"},
                    store=store,
                    refresh=False,
                )
        finally:
            app._tmdb_key = original_key

        self.assertEqual(result, {})
        urlopen.assert_not_called()

    def test_library_read_path_does_not_write_metadata_per_file(self):
        original_dirs = app._movies_dirs
        original_dir = app._movies_dir
        original_library_cache = dict(app._library_cache)
        original_plex_cache = dict(app._plex_cache)
        original_plex_by_fname = dict(app._plex_matched_by_fname)
        original_plex_token = app._plex_token

        with tempfile.TemporaryDirectory() as tmp:
            movie_path = Path(tmp) / "Alien.1979.1080p.mkv"
            movie_path.write_bytes(b"")
            store = app.AppMetadataStore(Path(tmp) / "data")
            store.save_plex_metadata = Mock(side_effect=AssertionError("library read must not save plex metadata"))
            store.record_file = Mock(side_effect=AssertionError("library read must not persist file records"))

            try:
                app._movies_dirs = [tmp]
                app._movies_dir = tmp
                app._library_cache = {}
                app._plex_cache = {
                    app._norm(str(movie_path)): {
                        "plex_title": "Alien",
                        "plex_year": "1979",
                        "plex_genres": ["Horror"],
                    }
                }
                app._plex_matched_by_fname = {}
                app._plex_token = ""
                with patch("app._metadata_store", return_value=store):
                    response = app.app.test_client().get("/api/library")
            finally:
                app._movies_dirs = original_dirs
                app._movies_dir = original_dir
                app._library_cache = original_library_cache
                app._plex_cache = original_plex_cache
                app._plex_matched_by_fname = original_plex_by_fname
                app._plex_token = original_plex_token

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["count"], 1)
        store.save_plex_metadata.assert_not_called()
        store.record_file.assert_not_called()

    def test_library_read_path_loads_manual_matches_once(self):
        original_dirs = app._movies_dirs
        original_dir = app._movies_dir
        original_library_cache = dict(app._library_cache)
        original_plex_cache = dict(app._plex_cache)
        original_plex_by_fname = dict(app._plex_matched_by_fname)
        original_plex_token = app._plex_token

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "Alien.1979.1080p.mkv").write_bytes(b"")
            Path(tmp, "Aliens.1986.1080p.mkv").write_bytes(b"")
            store = app.AppMetadataStore(Path(tmp) / "data")
            try:
                app._movies_dirs = [tmp]
                app._movies_dir = tmp
                app._library_cache = {}
                app._plex_cache = {}
                app._plex_matched_by_fname = {}
                app._plex_token = ""
                with patch("app._metadata_store", return_value=store), \
                        patch.object(store, "_read_json", wraps=store._read_json) as read_json:
                    response = app.app.test_client().get("/api/library")
            finally:
                app._movies_dirs = original_dirs
                app._movies_dir = original_dir
                app._library_cache = original_library_cache
                app._plex_cache = original_plex_cache
                app._plex_matched_by_fname = original_plex_by_fname
                app._plex_token = original_plex_token

        manual_reads = [
            call for call in read_json.call_args_list
            if call.args and Path(call.args[0]) == store.manual_matches_file
        ]
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(manual_reads), 1)

    def test_library_cache_key_changes_when_manual_metadata_changes(self):
        original_dirs = app._movies_dirs
        original_dir = app._movies_dir

        with tempfile.TemporaryDirectory() as tmp:
            store = app.AppMetadataStore(Path(tmp) / "data")
            try:
                app._movies_dirs = [tmp]
                app._movies_dir = tmp
                with patch("app._metadata_store", return_value=store):
                    before = app._library_cache_key()
                    store.apply_tmdb_match(
                        str(Path(tmp) / "Alien.1979.1080p.mkv"),
                        {"tmdb_id": "348", "title": "Alien", "year": "1979"},
                    )
                    after = app._library_cache_key()
            finally:
                app._movies_dirs = original_dirs
                app._movies_dir = original_dir

        self.assertNotEqual(before, after)

    def test_library_cache_key_changes_when_file_is_added(self):
        original_dirs = app._movies_dirs
        original_dir = app._movies_dir

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app._movies_dirs = [tmp]
                app._movies_dir = tmp
                before = app._library_cache_key()
                Path(tmp, "Alien.1979.1080p.mkv").write_bytes(b"movie")
                after = app._library_cache_key()
            finally:
                app._movies_dirs = original_dirs
                app._movies_dir = original_dir

        self.assertNotEqual(before, after)

    def test_force_scan_bypasses_fresh_library_cache(self):
        original_dirs = app._movies_dirs
        original_dir = app._movies_dir
        original_library_cache = dict(app._library_cache)
        original_plex_token = app._plex_token
        original_user_data = app._user_data_dir

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data_tmp:
            first_movie = Path(tmp, "Alien.1979.1080p.mkv")
            first_movie.write_bytes(b"movie")
            try:
                app._movies_dirs = [tmp]
                app._movies_dir = tmp
                app._user_data_dir = data_tmp
                app._library_cache = {}
                app._plex_token = ""
                client = app.app.test_client()
                initial = client.get("/api/library")
                second_movie = Path(tmp, "Aliens.1986.1080p.mkv")
                second_movie.write_bytes(b"movie")
                refreshed = client.get("/api/library")
                third_movie = Path(tmp, "Alien.3.1992.1080p.mkv")
                third_movie.write_bytes(b"movie")
                forced = client.get("/api/library?force_scan=1")
            finally:
                app._movies_dirs = original_dirs
                app._movies_dir = original_dir
                app._user_data_dir = original_user_data
                app._library_cache = original_library_cache
                app._plex_token = original_plex_token

        self.assertEqual(initial.get_json()["count"], 1)
        self.assertEqual(refreshed.get_json()["count"], 2)
        self.assertFalse(refreshed.get_json()["cached"])
        self.assertEqual(forced.get_json()["count"], 3)
        self.assertFalse(forced.get_json()["cached"])
        self.assertEqual(forced.get_json()["new_files"], 1)


if __name__ == "__main__":
    unittest.main()
