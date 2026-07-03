import json
import unittest
from unittest.mock import patch

import app


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class UnreleasedMovieGateTest(unittest.TestCase):
    def test_discover_payload_preserves_tmdb_release_date(self):
        original_key = app._tmdb_key
        original_genres = app._tmdb_genres
        app._tmdb_key = "tmdb-key"
        app._tmdb_genres = {27: "Horror"}

        payload = {
            "total_pages": 1,
            "total_results": 1,
            "results": [
                {
                    "id": 999,
                    "title": "Future Horror",
                    "release_date": "2028-10-31",
                    "poster_path": "/future.jpg",
                    "genre_ids": [27],
                    "vote_average": 6.5,
                    "vote_count": 123,
                    "overview": "A future release.",
                    "original_language": "en",
                }
            ],
        }

        try:
            with patch("app._ensure_tmdb_genres"), patch("app.urllib.request.urlopen", return_value=FakeResponse(payload)):
                response = app.app.test_client().get("/api/tmdb/discover?list=upcoming&page=1")
        finally:
            app._tmdb_key = original_key
            app._tmdb_genres = original_genres

        self.assertEqual(response.status_code, 200)
        movie = response.get_json()["results"][0]
        self.assertEqual(movie["release_date"], "2028-10-31")

    def test_tmdb_search_payload_preserves_tmdb_release_date(self):
        original_key = app._tmdb_key
        original_genres = app._tmdb_genres
        app._tmdb_key = "tmdb-key"
        app._tmdb_genres = {878: "Sci-Fi"}

        payload = {
            "total_pages": 1,
            "total_results": 1,
            "results": [
                {
                    "id": 1001,
                    "title": "The Odyssey",
                    "release_date": "2026-07-17",
                    "poster_path": "/odyssey.jpg",
                    "genre_ids": [878],
                    "vote_average": 0,
                    "vote_count": 0,
                    "overview": "A future voyage.",
                    "original_language": "en",
                }
            ],
        }

        try:
            with patch("app._ensure_tmdb_genres"), patch("app.urllib.request.urlopen", return_value=FakeResponse(payload)):
                response = app.app.test_client().get("/api/tmdb/search?q=odyssey&page=1")
        finally:
            app._tmdb_key = original_key
            app._tmdb_genres = original_genres

        self.assertEqual(response.status_code, 200)
        movie = response.get_json()["results"][0]
        self.assertEqual(movie["release_date"], "2026-07-17")

    def test_ollama_tmdb_enrichment_preserves_release_date(self):
        original_key = app._tmdb_key
        original_genres = app._tmdb_genres
        app._tmdb_key = "tmdb-key"
        app._tmdb_genres = {53: "Thriller"}

        payload = {
            "results": [
                {
                    "id": 1000,
                    "title": "Future Thriller",
                    "release_date": "2029-04-12",
                    "poster_path": "/thriller.jpg",
                    "genre_ids": [53],
                    "vote_average": 7.1,
                    "vote_count": 55,
                    "overview": "An unreleased recommendation.",
                    "original_language": "en",
                }
            ]
        }

        try:
            with patch("app._ensure_tmdb_genres"), patch("app.urllib.request.urlopen", return_value=FakeResponse(payload)):
                movie = app._ollama_enrich_with_tmdb("Future Thriller", "2029")
        finally:
            app._tmdb_key = original_key
            app._tmdb_genres = original_genres

        self.assertEqual(movie["release_date"], "2029-04-12")


if __name__ == "__main__":
    unittest.main()
