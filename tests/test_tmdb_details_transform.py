import unittest
from unittest.mock import patch

import app


class TmdbDetailsTransformTest(unittest.TestCase):
    def test_extracts_director_cast_and_collection(self):
        payload = {
            "runtime": 117,
            "tagline": "In space no one can hear you scream.",
            "release_date": "1979-05-25",
            "belongs_to_collection": {
                "id": 8091,
                "name": "Alien Collection",
                "poster_path": "/alien-poster.jpg",
                "backdrop_path": "/alien-backdrop.jpg",
            },
            "credits": {
                "crew": [
                    {"id": 1, "name": "Editor Person", "job": "Editor", "profile_path": "/editor.jpg"},
                    {"id": 2, "name": "Ridley Scott", "job": "Director", "profile_path": "/ridley.jpg"},
                ],
                "cast": [
                    {"id": idx, "name": f"Actor {idx}", "character": f"Role {idx}", "profile_path": f"/actor-{idx}.jpg"}
                    for idx in range(1, 9)
                ],
            },
            "videos": {
                "results": [
                    {"site": "YouTube", "type": "Trailer", "key": "official-key", "official": True},
                ]
            },
        }

        result = app._normalize_tmdb_details_payload(payload)

        self.assertEqual(result["director"]["name"], "Ridley Scott")
        self.assertEqual(result["director"]["profile_url"], "https://image.tmdb.org/t/p/w185/ridley.jpg")
        self.assertEqual(len(result["cast"]), 7)
        self.assertEqual(result["cast"][0]["character"], "Role 1")
        self.assertEqual(result["collection"]["name"], "Alien Collection")
        self.assertEqual(result["collection"]["poster_url"], "https://image.tmdb.org/t/p/w185/alien-poster.jpg")
        self.assertEqual(result["trailer_url"], "https://www.youtube.com/watch?v=official-key")
        self.assertEqual(result["release_date"], "1979-05-25")

    def test_collection_parts_keep_movie_card_metadata(self):
        app._tmdb_genres = {28: "Action", 878: "Sci-Fi"}
        payload = {
            "id": 123,
            "name": "Future Collection",
            "poster_path": "/collection.jpg",
            "backdrop_path": "/collection-bg.jpg",
            "parts": [
                {
                    "id": 10,
                    "title": "Future One",
                    "release_date": "2020-05-01",
                    "poster_path": "/future-one.jpg",
                    "genre_ids": [28, 878],
                    "vote_average": 7.25,
                    "vote_count": 3200,
                    "overview": "A future starts here.",
                    "original_language": "en",
                }
            ],
        }

        result = app._normalize_tmdb_collection_payload(payload)

        self.assertEqual(result["parts"][0]["tmdb_id"], "10")
        self.assertEqual(result["parts"][0]["genres"], ["Action", "Sci-Fi"])
        self.assertEqual(result["parts"][0]["tmdb_rating"], "7.2")
        self.assertEqual(result["parts"][0]["tmdb_vote_count"], 3200)
        self.assertEqual(result["parts"][0]["plot"], "A future starts here.")
        self.assertEqual(result["parts"][0]["language"], "English")

    def test_person_movies_endpoint_filters_directed_movies(self):
        original_key = app._tmdb_key
        original_genres = app._tmdb_genres
        app._tmdb_key = "tmdb-key"
        app._tmdb_genres = {80: "Crime"}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return app._json.dumps({
                    "crew": [
                        {
                            "id": 1,
                            "title": "Directed Movie",
                            "release_date": "2001-01-01",
                            "poster_path": "/directed.jpg",
                            "genre_ids": [80],
                            "vote_average": 8.44,
                            "overview": "A directed movie.",
                            "original_language": "en",
                            "job": "Director",
                        },
                        {
                            "id": 2,
                            "title": "Produced Movie",
                            "release_date": "2002-01-01",
                            "job": "Producer",
                        },
                    ],
                    "cast": []
                }).encode()

        requested_urls = []

        def fake_urlopen(request, timeout=0):
            requested_urls.append(request.full_url)
            return FakeResponse()

        try:
            with patch("app._ensure_tmdb_genres"), patch("app.urllib.request.urlopen", side_effect=fake_urlopen):
                response = app.app.test_client().get("/api/tmdb/person_movies?person_id=55&role=director&page=1")
        finally:
            app._tmdb_key = original_key
            app._tmdb_genres = original_genres

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("/person/55/movie_credits", requested_urls[0])
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["title"], "Directed Movie")
        self.assertEqual(data["results"][0]["genres"], ["Crime"])

    def test_fetch_tmdb_metadata_refetches_cached_movie_without_release_date(self):
        original_key = app._tmdb_key
        app._tmdb_key = "tmdb-key"

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return app._json.dumps({
                    "id": 1368337,
                    "title": "The Odyssey",
                    "release_date": "2026-07-15",
                    "credits": {"crew": [], "cast": []},
                    "videos": {"results": []},
                }).encode()

        try:
            with self.subTest("metadata store cache"):
                import tempfile
                from pathlib import Path

                with tempfile.TemporaryDirectory() as tmp:
                    store = app.AppMetadataStore(Path(tmp))
                    store.save_tmdb_metadata({"tmdb_id": "1368337", "title": "The Odyssey"})
                    with patch("app.urllib.request.urlopen", return_value=FakeResponse()) as urlopen:
                        result = app._fetch_tmdb_metadata_by_id("1368337", store=store)
                    self.assertTrue(urlopen.called)
                    self.assertEqual(result["release_date"], "2026-07-15")
        finally:
            app._tmdb_key = original_key

    def test_tmdb_details_endpoint_refetches_cached_payload_without_release_date(self):
        original_key = app._tmdb_key
        original_cache = app._tmdb_library_cache
        app._tmdb_key = "tmdb-key"
        app._tmdb_library_cache = {
            "1368337": {
                "fetched_at": 1,
                "data": {"tmdb_id": "1368337", "runtime": 100},
            }
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return app._json.dumps({
                    "id": 1368337,
                    "title": "The Odyssey",
                    "release_date": "2026-07-15",
                    "runtime": 100,
                    "credits": {"crew": [], "cast": []},
                    "videos": {"results": []},
                }).encode()

        try:
            with patch("app.urllib.request.urlopen", return_value=FakeResponse()) as urlopen, \
                 patch("app._save_tmdb_library_cache"):
                response = app.app.test_client().get("/api/tmdb/details?tmdb_id=1368337")
        finally:
            app._tmdb_key = original_key
            app._tmdb_library_cache = original_cache

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(urlopen.called)
        self.assertFalse(payload["cached"])
        self.assertEqual(payload["release_date"], "2026-07-15")


if __name__ == "__main__":
    unittest.main()
