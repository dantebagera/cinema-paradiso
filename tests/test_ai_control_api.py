import json
import os
import tempfile
import unittest
from unittest.mock import patch

import app


class AiControlApiTest(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_config_endpoint_returns_experimental_policy_defaults(self):
        response = self.client.get("/api/ai-control/config")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["download_quality"], "1080p")
        self.assertEqual(data["delete_mode"], "recycle_bin")
        self.assertFalse(data["ollama_curated_lists"])
        self.assertEqual(data["max_matched_movies"], 25)

    def test_config_defaults_ai_control_trusted_indexers_to_yts_when_unconfigured(self):
        previous_configured = app._ai_control_trusted_indexers_configured
        previous_config = dict(app._ai_control_config)
        app._ai_control_trusted_indexers_configured = False
        app._ai_control_config = app.ai_control.coerce_config({
            **previous_config,
            "trusted_indexers": [],
        })
        try:
            with patch("app._ai_control_available_indexers", return_value=[
                {"id": "1", "name": "YTS"},
                {"id": "2", "name": "1337x"},
            ]):
                response = self.client.get("/api/ai-control/config")
        finally:
            app._ai_control_trusted_indexers_configured = previous_configured
            app._ai_control_config = previous_config

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["trusted_indexers"], ["1"])
        self.assertFalse(data["trusted_indexers_configured"])

    def test_preview_delete_uses_ollama_intent_and_returns_review_plan(self):
        with tempfile.TemporaryDirectory() as root:
            movie = os.path.join(root, "Huge Movie.mkv")
            with open(movie, "wb") as handle:
                handle.write(b"x")

            with patch("app._ai_control_library_items", return_value=[
                {"path": movie, "title": "Huge Movie", "year": "2009", "size": 14 * 1024**3}
            ]), patch("app.get_movies_dirs", return_value=[root]), patch(
                "app._ollama_chat_content",
                return_value=json.dumps({"action": "delete", "filters": [{"field": "size_gb", "op": ">", "value": 10}]}),
            ):
                response = self.client.post("/api/ai-control/preview", json={"prompt": "delete files over 10 GB"})

            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["state"], "valid_plan")
            self.assertEqual(data["action"], "delete")
            self.assertTrue(data["plan_id"])
            self.assertEqual(data["items"][0]["title"], "Huge Movie")

    def test_execute_rejects_delete_plan_when_file_changed_after_preview(self):
        with tempfile.TemporaryDirectory() as root:
            movie = os.path.join(root, "Huge Movie.mkv")
            with open(movie, "wb") as handle:
                handle.write(b"x")

            with patch("app._ai_control_library_items", return_value=[
                {"path": movie, "title": "Huge Movie", "year": "2009", "size": 14 * 1024**3}
            ]), patch("app.get_movies_dirs", return_value=[root]), patch(
                "app._ollama_chat_content",
                return_value=json.dumps({"action": "delete", "filters": [{"field": "size_gb", "op": ">", "value": 10}]}),
            ):
                preview = self.client.post("/api/ai-control/preview", json={"prompt": "delete files over 10 GB"}).get_json()

            with open(movie, "ab") as handle:
                handle.write(b"changed")

            with patch("app.get_movies_dirs", return_value=[root]):
                response = self.client.post("/api/ai-control/execute", json={"plan_id": preview["plan_id"]})

            self.assertEqual(response.status_code, 409)
            data = response.get_json()
            self.assertEqual(data["state"], "unsafe")
            self.assertIn("changed", data["message"].lower())

    def test_execute_create_list_returns_receipt_and_rejects_replay(self):
        plan = app._ai_control_plan_store.put({
            "state": "valid_plan",
            "action": "create_list",
            "list_name": "AI Sci-Fi",
            "items": [{"tmdb_id": "348", "title": "Alien", "year": "1979"}],
        })
        created = {
            "id": "ai-sci-fi",
            "name": "AI Sci-Fi",
            "movies": plan["items"],
            "count": 1,
        }

        with patch("app._ai_control_create_list", return_value=created) as create_list:
            first = self.client.post("/api/ai-control/execute", json={"plan_id": plan["plan_id"]})
            second = self.client.post("/api/ai-control/execute", json={"plan_id": plan["plan_id"]})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["state"], "executed")
        self.assertEqual(first.get_json()["total_matches"], 1)
        self.assertEqual(second.status_code, 409)
        create_list.assert_called_once()

    def test_preview_nonsense_prompt_returns_clarification(self):
        response = self.client.post("/api/ai-control/preview", json={"prompt": "clean my movies"})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["state"], "needs_clarification")
        self.assertEqual(data["plan_id"], "")

    def test_ai_control_library_items_include_card_ready_plex_metadata(self):
        previous_cache = dict(app._library_cache)
        previous_plex_cache = dict(app._plex_cache)
        path = "E:\\Movies\\Mission Impossible 1996.mkv"
        app._library_cache = {}
        app._plex_cache = {
            app._norm(path): {
                "plex_title": "Mission: Impossible",
                "plex_year": "1996",
                "plex_genres": ["Action", "Thriller"],
                "plex_summary": "Ethan Hunt races to expose a mole.",
                "plex_rating": "7.0",
                "plex_language": "English",
                "plex_country": "United States",
                "plex_country_flag": "US",
                "plex_directors": [{"name": "Brian De Palma"}],
                "plex_cast": [{"name": "Tom Cruise", "character": "Ethan Hunt"}],
                "tmdb_id": "954",
                "imdb_id": "tt0117060",
                "plex_guid": "plex://movie/1",
                "plex_poster": "/api/plex/image?path=poster",
            }
        }

        try:
            with patch("app._iter_video_files", return_value=[("", "", os.path.basename(path), path)]), patch(
                "app.os.path.getsize", return_value=2_400_000_000
            ):
                item = app._ai_control_library_items()[0]
        finally:
            app._library_cache = previous_cache
            app._plex_cache = previous_plex_cache

        self.assertEqual(item["title"], "Mission: Impossible")
        self.assertEqual(item["year"], "1996")
        self.assertEqual(item["genres"], ["Action", "Thriller"])
        self.assertEqual(item["plot"], "Ethan Hunt races to expose a mole.")
        self.assertEqual(item["tmdb_rating"], "7.0")
        self.assertEqual(item["language"], "English")
        self.assertEqual(item["country_flag"], "US")
        self.assertEqual(item["directors"], [{"name": "Brian De Palma"}])
        self.assertEqual(item["cast"], [{"name": "Tom Cruise", "character": "Ethan Hunt"}])
        self.assertEqual(item["poster_url"], "/api/plex/image?path=poster")
        self.assertEqual(item["resolution"], app.get_resolution(os.path.basename(path)))
        self.assertTrue(item["size_human"])

    def test_person_credit_filter_keeps_released_feature_roles_only(self):
        previous_genres = dict(app._tmdb_genres)
        app._tmdb_genres = {
            16: "Animation",
            35: "Comedy",
            99: "Documentary",
        }
        try:
            rows = app._ai_control_filter_person_credit_rows([
                {
                    "id": 1,
                    "title": "Sonic the Hedgehog 4",
                    "release_date": "2027-03-19",
                    "genre_ids": [16],
                    "character": "Dr. Robotnik",
                    "popularity": 100,
                },
                {
                    "id": 2,
                    "title": "The Many Faces of Jim Carrey",
                    "release_date": "2023-01-01",
                    "genre_ids": [99],
                    "character": "Self",
                    "popularity": 90,
                },
                {
                    "id": 3,
                    "title": "Behind the Scenes of Kidding",
                    "release_date": "2018-01-01",
                    "genre_ids": [99],
                    "character": "Self",
                    "popularity": 80,
                },
                {
                    "id": 4,
                    "title": "Liar Liar",
                    "release_date": "1997-03-21",
                    "genre_ids": [35],
                    "character": "Fletcher Reede",
                    "popularity": 30,
                },
                {
                    "id": 5,
                    "title": "Sonic the Hedgehog",
                    "release_date": "2020-02-12",
                    "genre_ids": [16, 35],
                    "character": "Dr. Robotnik",
                    "popularity": 50,
                },
            ], "actor")
        finally:
            app._tmdb_genres = previous_genres

        self.assertEqual([row["title"] for row in rows], ["Sonic the Hedgehog", "Liar Liar"])

    def test_tmdb_discover_uses_genre_year_range_and_top_rated_sort(self):
        previous_key = app._tmdb_key
        previous_genres = dict(app._tmdb_genres)
        captured_urls = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({
                    "results": [
                        {
                            "id": 78,
                            "title": "Blade Runner",
                            "release_date": "1982-06-25",
                            "poster_path": "/blade.jpg",
                        }
                    ]
                }).encode()

        def fake_urlopen(req, timeout=10):
            captured_urls.append(req.full_url)
            return FakeResponse()

        app._tmdb_key = "test-key"
        app._tmdb_genres = {878: "Science Fiction"}
        try:
            with patch("app.urllib.request.urlopen", side_effect=fake_urlopen):
                result = app._ai_control_tmdb_discover({
                    "filters": [
                        {"field": "genre", "op": "equals", "value": "Science Fiction"},
                        {"field": "year", "op": "between", "value": ["1980", "1989"]},
                    ],
                    "sort": "top_rated",
                }, app.ai_control.default_config())
        finally:
            app._tmdb_key = previous_key
            app._tmdb_genres = previous_genres

        self.assertEqual(result[0]["title"], "Blade Runner")
        self.assertIn("with_genres=878", captured_urls[0])
        self.assertIn("primary_release_date.gte=1980-01-01", captured_urls[0])
        self.assertIn("primary_release_date.lte=1989-12-31", captured_urls[0])
        self.assertIn("sort_by=vote_average.desc", captured_urls[0])
        self.assertIn("vote_count.gte=500", captured_urls[0])


if __name__ == "__main__":
    unittest.main()
