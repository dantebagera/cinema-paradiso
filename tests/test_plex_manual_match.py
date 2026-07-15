import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import app


class PlexManualMatchTest(unittest.TestCase):
    def setUp(self):
        self.original_dirs = app._movies_dirs
        self.original_dir = app._movies_dir
        self.original_user_data_dir = app._user_data_dir
        self.original_plex_url = app._plex_url
        self.original_plex_token = app._plex_token
        self.original_plex_cache = dict(app._plex_cache)
        self.original_plex_unmatched = dict(app._plex_unmatched)
        self.original_plex_by_fname = dict(app._plex_matched_by_fname)
        self.original_plex_unmatched_by_fname = dict(app._plex_unmatched_by_fname)
        self.original_library_cache = dict(app._library_cache)

    def tearDown(self):
        app._movies_dirs = self.original_dirs
        app._movies_dir = self.original_dir
        app._user_data_dir = self.original_user_data_dir
        app._plex_url = self.original_plex_url
        app._plex_token = self.original_plex_token
        app._plex_cache = self.original_plex_cache
        app._plex_unmatched = self.original_plex_unmatched
        app._plex_matched_by_fname = self.original_plex_by_fname
        app._plex_unmatched_by_fname = self.original_plex_unmatched_by_fname
        app._library_cache = self.original_library_cache

    def configure(self, movies_tmp, data_tmp):
        app._movies_dirs = [movies_tmp]
        app._movies_dir = movies_tmp
        app._user_data_dir = data_tmp
        app._plex_url = "http://plex.test"
        app._plex_token = "token"

    def test_matched_plex_library_entries_retain_rating_key(self):
        app._plex_url = "http://plex.test"
        app._plex_token = "token"
        payloads = [
            {"MediaContainer": {"Directory": [{"key": "1", "type": "movie"}]}},
            {"MediaContainer": {"Metadata": [{
                "ratingKey": "42",
                "guid": "plex://movie/alien",
                "title": "Alien",
                "year": 1979,
                "Media": [{"Part": [{"file": "E:/Movies/Alien.1979.mkv"}]}],
            }]}}
        ]
        responses = []
        for payload in payloads:
            response = MagicMock()
            response.__enter__.return_value.read.return_value = app._json.dumps(payload).encode()
            responses.append(response)
        with patch("app.urllib.request.urlopen", side_effect=responses):
            matched, _, by_name, _, _ = app._fetch_plex_library()

        self.assertEqual(next(iter(matched.values()))["rating_key"], "42")
        self.assertEqual(by_name["alien.1979.mkv"]["rating_key"], "42")

    def test_search_resolves_rating_key_from_path_and_returns_it(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            app._plex_cache = {
                app._norm(str(movie)): {
                    "rating_key": "42",
                    "plex_title": "Alien",
                    "plex_year": "1979",
                }
            }
            with patch("app._smart_match_plex_candidates", return_value=[{
                "guid": "plex://movie/alien",
                "name": "Alien",
                "title": "Alien",
                "year": "1979",
                "score": 100,
            }]):
                response = app.app.test_client().get("/api/plex/match-search", query_string={
                    "path": str(movie),
                    "title": "Alien",
                    "year": "1979",
                })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["rating_key"], "42")
        self.assertEqual(response.get_json()["results"][0]["guid"], "plex://movie/alien")

    def test_manual_search_returns_candidates_even_when_plex_identity_exists(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            app._plex_cache = {
                app._norm(str(movie)): {
                    "rating_key": "42",
                    "plex_title": "Alien",
                    "plex_year": "1979",
                    "plex_guid": "plex://movie/alien",
                }
            }
            alternatives = [{
                "guid": "plex://movie/alien",
                "name": "Alien",
                "title": "Alien",
                "year": "1979",
                "poster_url": "https://images.plex.tv/alien.jpg",
                "summary": "Crew encounters a hostile life-form.",
                "query_sources": ["title_year"],
                "match_reasons": ["Plex title and year search"],
                "exact_external_id": False,
            }]
            with patch("app._smart_match_plex_candidates", return_value=alternatives) as agent_search:
                response = app.app.test_client().get("/api/plex/match-search", query_string={
                    "path": str(movie),
                    "title": "Wrong filename",
                    "year": "2024",
                })

        self.assertEqual(response.status_code, 200)
        result = response.get_json()["results"][0]
        self.assertEqual(result["guid"], "plex://movie/alien")
        self.assertIn("hostile life-form", result["summary"])
        agent_search.assert_called_once()

    def test_identity_review_can_force_agent_search_for_alternatives(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            app._plex_cache = {
                app._norm(str(movie)): {
                    "rating_key": "42",
                    "plex_title": "Wrong Alien",
                    "plex_year": "1979",
                    "plex_guid": "plex://movie/wrong",
                }
            }
            alternatives = [{
                "guid": "plex://movie/alien",
                "name": "Alien",
                "title": "Alien",
                "year": "1979",
                "score": 100,
            }]
            with patch("app._smart_match_plex_candidates", return_value=alternatives) as agent_search:
                response = app.app.test_client().get("/api/plex/match-search", query_string={
                    "path": str(movie),
                    "title": "Alien",
                    "year": "1979",
                    "force_search": "1",
                })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["results"][0]["guid"], "plex://movie/alien")
        agent_search.assert_called_once()

    def test_search_uses_saved_imdb_and_tmdb_identity_hints(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "rating_key": "42",
                "tmdb_id": "348",
                "imdb_id": "tt0078748",
            })
            app._plex_cache = {
                app._norm(str(movie)): {
                    "rating_key": "42",
                    "plex_title": "Alien",
                }
            }
            with patch("app._smart_match_plex_candidates", return_value=[]) as search:
                response = app.app.test_client().get("/api/plex/match-search", query_string={
                    "path": str(movie),
                    "title": "Alien",
                    "year": "1979",
                })

        self.assertEqual(response.status_code, 200)
        search.assert_called_once_with(
            "42",
            "Alien",
            "1979",
            imdb_id="tt0078748",
            tmdb_id="348",
        )

    def test_rating_key_resolution_supports_filename_and_saved_snapshot_fallbacks(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            app._plex_matched_by_fname = {
                movie.name.lower(): {"rating_key": "42", "plex_title": "Alien"}
            }
            self.assertEqual(app._plex_rating_key_for_path(str(movie)), "42")

            app._plex_matched_by_fname = {}
            app.AppMetadataStore(Path(data_tmp)).save_plex_metadata(str(movie), {
                "rating_key": "84",
                "plex_title": "Alien",
            })
            self.assertEqual(app._plex_rating_key_for_path(str(movie)), "84")

    def test_exact_path_plex_identity_rejects_conflicting_filename_fallback(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            app._plex_unmatched = {
                app._norm(str(movie)): {
                    "rating_key": "42",
                    "plex_title": "Alien",
                }
            }
            app._plex_matched_by_fname = {
                movie.name.lower(): {
                    "rating_key": "99",
                    "plex_title": "Wrong Alien",
                    "plex_guid": "plex://movie/wrong",
                }
            }

            metadata = app._plex_metadata_for_path(str(movie))

        self.assertEqual(metadata["rating_key"], "42")
        self.assertEqual(metadata["plex_title"], "Alien")
        self.assertNotIn("plex_guid", metadata)

    def test_search_uses_rating_key_found_by_forced_sync(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            app._plex_cache = {}

            def sync(force=False):
                self.assertTrue(force)
                app._plex_cache[app._norm(str(movie))] = {
                    "rating_key": "42",
                    "plex_title": "Alien",
                }

            with patch("app._auto_sync_plex", side_effect=sync) as forced_sync, patch(
                "app._smart_match_plex_candidates",
                return_value=[],
            ):
                response = app.app.test_client().get("/api/plex/match-search", query_string={
                    "path": str(movie),
                    "title": "Alien",
                })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["rating_key"], "42")
        forced_sync.assert_called_once_with(force=True)

    def test_search_forces_one_sync_before_reporting_file_not_indexed(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Missing.2024.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            app._plex_cache = {}
            app._plex_unmatched = {}
            with patch("app._auto_sync_plex") as sync:
                response = app.app.test_client().get("/api/plex/match-search", query_string={
                    "path": str(movie),
                    "title": "Missing",
                    "year": "2024",
                })

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "plex_item_not_indexed")
        sync.assert_called_once_with(force=True)

    def test_search_rejects_paths_outside_library(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as outside_tmp, tempfile.TemporaryDirectory() as data_tmp:
            outside = Path(outside_tmp) / "Outside.mkv"
            outside.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            response = app.app.test_client().get("/api/plex/match-search", query_string={
                "path": str(outside),
                "title": "Outside",
            })

        self.assertEqual(response.status_code, 403)

    def test_search_reports_unconfigured_and_provider_failures(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            app._plex_url = ""
            unconfigured = app.app.test_client().get("/api/plex/match-search", query_string={
                "path": str(movie),
                "title": "Alien",
            })

            app._plex_url = "http://plex.test"
            app._plex_cache = {app._norm(str(movie)): {"rating_key": "42"}}
            with patch("app._smart_match_plex_candidates", side_effect=ValueError("Malformed Plex response")):
                malformed = app.app.test_client().get("/api/plex/match-search", query_string={
                    "path": str(movie),
                    "title": "Alien",
                })

        self.assertEqual(unconfigured.status_code, 400)
        self.assertEqual(malformed.status_code, 500)
        self.assertIn("Malformed Plex response", malformed.get_json()["error"])

    def test_search_returns_sanitized_plex_http_details(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            app._plex_cache = {app._norm(str(movie)): {"rating_key": "42"}}
            error = app.PlexMatchError(
                "Plex returned HTTP 400: invalid matching hints",
                status=400,
            )
            with patch("app._smart_match_plex_candidates", side_effect=error):
                response = app.app.test_client().get("/api/plex/match-search", query_string={
                    "path": str(movie),
                    "title": "Alien",
                })

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["provider_status"], 400)
        self.assertIn("invalid matching hints", response.get_json()["error"])

    def test_apply_saves_local_match_without_mutating_plex(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            self.configure(movies_tmp, data_tmp)
            with patch("app.urllib.request.urlopen") as urlopen:
                response = app.app.test_client().post("/api/plex/match-apply", json={
                    "path": str(movie),
                    "rating_key": "42",
                    "guid": "plex://movie/alien",
                    "name": "Alien",
                    "year": "1979",
                    "poster_url": "/library/metadata/42/thumb/1",
                    "summary": "In space no one can hear you scream.",
                })
            store = app.AppMetadataStore(Path(data_tmp))
            match = store.get_manual_match(str(movie))
            snapshot = store.snapshot()
            record = snapshot["files"][store._key(str(movie))]
            plex_metadata = snapshot["plex_files"][store._key(str(movie))]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(match["provider"], "plex")
        self.assertEqual(match["rating_key"], "42")
        self.assertEqual(record["display_provider"], "plex")
        self.assertEqual(record["metadata_status"], "accepted")
        self.assertEqual(record["plex_guid"], "plex://movie/alien")
        self.assertTrue(record["manual_locked"])
        self.assertEqual(plex_metadata["plex_thumb"], "/library/metadata/42/thumb/1")
        urlopen.assert_not_called()

    def test_plex_match_ui_displays_rich_unified_results(self):
        from tests.frontend_source import read_frontend_source
        source = read_frontend_source()

        self.assertIn("match.poster_url", source)
        self.assertIn("match.summary", source)
        self.assertIn("match.match_reasons", source)
        self.assertIn("Exact external ID", source)


if __name__ == "__main__":
    unittest.main()
