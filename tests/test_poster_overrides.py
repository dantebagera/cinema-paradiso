import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"controlled-poster" + b"\xff\xd9"
INVALID_IMAGE_BYTES = b"not-an-image"


class PosterOverrideTest(unittest.TestCase):
    def setUp(self):
        self.original_dirs = app._movies_dirs
        self.original_dir = app._movies_dir
        self.original_user_data_dir = app._user_data_dir
        self.original_tmdb_key = app._tmdb_key
        self.original_plex_cache = dict(app._plex_cache)
        self.original_plex_by_fname = dict(app._plex_matched_by_fname)
        self.original_library_cache = dict(app._library_cache)

    def tearDown(self):
        app._movies_dirs = self.original_dirs
        app._movies_dir = self.original_dir
        app._user_data_dir = self.original_user_data_dir
        app._tmdb_key = self.original_tmdb_key
        app._plex_cache = self.original_plex_cache
        app._plex_matched_by_fname = self.original_plex_by_fname
        app._library_cache = self.original_library_cache

    def test_override_persists_and_resolves_for_duplicate_shared_identity(self):
        with tempfile.TemporaryDirectory() as data_tmp:
            store = app.AppMetadataStore(Path(data_tmp))
            saved = store.save_poster_override(
                {
                    "tmdb_id": "348",
                    "imdb_id": "tt0078748",
                    "title": "Alien",
                    "year": "1979",
                },
                source="local",
                image_bytes=JPEG_BYTES,
                extension=".jpg",
            )

            reloaded = app.AppMetadataStore(Path(data_tmp))
            duplicate = reloaded.get_poster_override({
                "tmdb_id": "348",
                "title": "Alien",
                "year": "1979",
            })

        self.assertEqual(duplicate["id"], saved["id"])
        self.assertEqual(duplicate["source"], "local")
        self.assertTrue(duplicate["poster_url"].startswith("/api/library/posters/image/"))

    def test_conflicting_strong_ids_do_not_share_title_year_override(self):
        with tempfile.TemporaryDirectory() as data_tmp:
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_poster_override(
                {"tmdb_id": "348", "title": "Alien", "year": "1979"},
                source="tmdb",
                image_bytes=JPEG_BYTES,
                extension=".jpg",
            )

            override = store.get_poster_override({
                "tmdb_id": "999",
                "title": "Alien",
                "year": "1979",
            })

        self.assertEqual(override, {})

    def test_library_canonical_metadata_uses_override_without_changing_snapshot(self):
        with tempfile.TemporaryDirectory() as data_tmp:
            store = app.AppMetadataStore(Path(data_tmp))
            store.save_poster_override(
                {"tmdb_id": "348", "title": "Alien", "year": "1979"},
                source="plex",
                image_bytes=JPEG_BYTES,
                extension=".jpg",
            )
            canonical = {
                "accepted": True,
                "tmdb_id": "348",
                "title": "Alien",
                "year": "1979",
                "poster_url": "tmdb-original.jpg",
            }

            displayed = app._apply_poster_override(
                canonical,
                {"tmdb_id": "348", "title": "Alien", "year": "1979"},
                store=store,
            )

        self.assertEqual(canonical["poster_url"], "tmdb-original.jpg")
        self.assertNotEqual(displayed["poster_url"], canonical["poster_url"])
        self.assertTrue(displayed["poster_override"])
        self.assertEqual(displayed["poster_override_source"], "plex")

    def test_poster_options_require_owned_accepted_library_movie(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Unknown.Movie.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = ""
            app._plex_cache = {}

            response = app.app.test_client().get(
                "/api/library/posters",
                query_string={"path": str(movie)},
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("accepted Library movie", response.get_json()["error"])

    def test_remote_selection_copies_image_to_durable_storage_and_reset_removes_override(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            store = app.AppMetadataStore(Path(data_tmp))
            store.apply_tmdb_match(str(movie), {
                "tmdb_id": "348",
                "imdb_id": "tt0078748",
                "title": "Alien",
                "year": "1979",
                "poster_url": "https://image.tmdb.org/original.jpg",
            })

            option = {"source": "tmdb", "url": "https://image.tmdb.org/selected.jpg", "label": "TMDB poster"}
            with patch("app._poster_options_for_path", return_value=([option], {"tmdb_id": "348", "title": "Alien", "year": "1979"})), patch(
                "app._download_poster_image",
                return_value=(JPEG_BYTES, ".jpg"),
            ):
                selected = app.app.test_client().post(
                    "/api/library/posters/select",
                    json={"path": str(movie), "source": "tmdb", "url": option["url"]},
                )

            self.assertEqual(selected.status_code, 200)
            saved = selected.get_json()["override"]
            filename = Path(saved["poster_url"]).name
            self.assertTrue((store.posters_dir / filename).is_file())

            image = app.app.test_client().get(saved["poster_url"])
            self.assertEqual(image.status_code, 200)
            self.assertEqual(image.data, JPEG_BYTES)
            image.close()

            reset = app.app.test_client().post(
                "/api/library/posters/reset",
                json={"path": str(movie)},
            )

        self.assertEqual(reset.status_code, 200)
        self.assertFalse(reset.get_json()["override"])

    def test_poster_options_search_tmdb_by_exact_accepted_title_and_year_when_id_missing(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            app._plex_cache = {
                app._norm(str(movie)): {
                    "rating_key": "42",
                    "plex_title": "Alien",
                    "plex_year": "1979",
                    "plex_guid": "plex://movie/alien",
                }
            }
            store = app.AppMetadataStore(Path(data_tmp))
            store.apply_plex_match(str(movie), {
                "rating_key": "42",
                "plex_title": "Alien",
                "plex_year": "1979",
                "plex_guid": "plex://movie/alien",
            })

            with patch("app._smart_match_tmdb_search", return_value=[{
                "id": 348,
                "title": "Alien",
                "release_date": "1979-05-25",
            }]) as search, patch(
                "app._tmdb_poster_options",
                return_value=[{"source": "tmdb", "url": "https://image.tmdb.org/alien.jpg", "label": "TMDB poster"}],
            ) as posters:
                response = app.app.test_client().get(
                    "/api/library/posters",
                    query_string={"path": str(movie)},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["options"][0]["source"], "tmdb")
        self.assertTrue(payload["providers"]["tmdb"]["available"])
        search.assert_called_once_with("Alien", "1979")
        posters.assert_called_once_with("348")

    def test_poster_options_reject_ambiguous_or_wrong_year_tmdb_fallback(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            app._plex_cache = {
                app._norm(str(movie)): {
                    "rating_key": "42",
                    "plex_title": "Alien",
                    "plex_year": "1979",
                    "plex_guid": "plex://movie/alien",
                }
            }
            store = app.AppMetadataStore(Path(data_tmp))
            store.apply_plex_match(str(movie), {
                "rating_key": "42",
                "plex_title": "Alien",
                "plex_year": "1979",
                "plex_guid": "plex://movie/alien",
            })

            with patch("app._smart_match_tmdb_search", return_value=[
                {"id": 999, "title": "Alien Nation", "release_date": "1988-10-07"},
                {"id": 1000, "title": "Alien", "release_date": "2003-01-01"},
            ]), patch("app._tmdb_poster_options") as posters:
                response = app.app.test_client().get(
                    "/api/library/posters",
                    query_string={"path": str(movie)},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["providers"]["tmdb"]["available"])
        self.assertIn("exact TMDB identity", payload["providers"]["tmdb"]["message"])
        posters.assert_not_called()

    def test_poster_options_report_tmdb_failure_without_hiding_plex_choice(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            app._plex_cache = {
                app._norm(str(movie)): {
                    "rating_key": "42",
                    "plex_title": "Alien",
                    "plex_year": "1979",
                    "plex_guid": "plex://movie/alien",
                    "plex_poster": "http://plex.test/alien.jpg",
                }
            }
            app.AppMetadataStore(Path(data_tmp)).apply_plex_match(str(movie), {
                "rating_key": "42",
                "plex_title": "Alien",
                "plex_year": "1979",
                "plex_guid": "plex://movie/alien",
            })

            with patch("app._smart_match_tmdb_search", side_effect=OSError("TMDB offline")):
                response = app.app.test_client().get(
                    "/api/library/posters",
                    query_string={"path": str(movie)},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual([option["source"] for option in payload["options"]], ["plex"])
        self.assertFalse(payload["providers"]["tmdb"]["available"])
        self.assertIn("TMDB offline", payload["providers"]["tmdb"]["message"])
        self.assertTrue(payload["providers"]["plex"]["available"])

    def test_local_upload_is_stored_as_local_override(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            store = app.AppMetadataStore(Path(data_tmp))
            store.apply_tmdb_match(str(movie), {
                "tmdb_id": "348",
                "title": "Alien",
                "year": "1979",
            })

            response = app.app.test_client().post(
                "/api/library/posters/upload",
                data={
                    "path": str(movie),
                    "poster": (io.BytesIO(JPEG_BYTES), "alien.jpg"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["override"]["source"], "local")

    def test_upload_rejects_invalid_and_oversized_images_without_saving_override(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            store = app.AppMetadataStore(Path(data_tmp))
            store.apply_tmdb_match(str(movie), {
                "tmdb_id": "348",
                "title": "Alien",
                "year": "1979",
            })
            client = app.app.test_client()

            invalid = client.post(
                "/api/library/posters/upload",
                data={
                    "path": str(movie),
                    "poster": (io.BytesIO(INVALID_IMAGE_BYTES), "alien.gif"),
                },
                content_type="multipart/form-data",
            )
            oversized = client.post(
                "/api/library/posters/upload",
                data={
                    "path": str(movie),
                    "poster": (io.BytesIO(JPEG_BYTES + b"x" * app._MAX_POSTER_BYTES), "alien.jpg"),
                },
                content_type="multipart/form-data",
            )

            override = store.get_poster_override({
                "tmdb_id": "348",
                "title": "Alien",
                "year": "1979",
            })

        self.assertEqual(invalid.status_code, 400)
        self.assertIn("JPEG, PNG, or WebP", invalid.get_json()["error"])
        self.assertEqual(oversized.status_code, 400)
        self.assertIn("exceeds 10 MB", oversized.get_json()["error"])
        self.assertEqual(override, {})

    def test_poster_endpoints_reject_paths_outside_library_roots(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as outside_tmp, tempfile.TemporaryDirectory() as data_tmp:
            outside_movie = Path(outside_tmp) / "Alien.1979.mkv"
            outside_movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            client = app.app.test_client()

            options = client.get("/api/library/posters", query_string={"path": str(outside_movie)})
            upload = client.post(
                "/api/library/posters/upload",
                data={
                    "path": str(outside_movie),
                    "poster": (io.BytesIO(JPEG_BYTES), "alien.jpg"),
                },
                content_type="multipart/form-data",
            )
            reset = client.post("/api/library/posters/reset", json={"path": str(outside_movie)})

        self.assertEqual(options.status_code, 403)
        self.assertEqual(upload.status_code, 403)
        self.assertEqual(reset.status_code, 403)

    def test_remote_download_rejects_invalid_and_oversized_images(self):
        class FakeResponse:
            def __init__(self, data):
                self.data = data

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, limit):
                return self.data[:limit]

        with patch("app.urllib.request.urlopen", return_value=FakeResponse(INVALID_IMAGE_BYTES)):
            with self.assertRaisesRegex(ValueError, "JPEG, PNG, or WebP"):
                app._download_poster_image("https://images.example/alien.gif")

        oversized = JPEG_BYTES + b"x" * app._MAX_POSTER_BYTES
        with patch("app.urllib.request.urlopen", return_value=FakeResponse(oversized)):
            with self.assertRaisesRegex(ValueError, "exceeds 10 MB"):
                app._download_poster_image("https://images.example/alien.jpg")

    def test_metadata_refresh_keeps_the_durable_poster_override(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            store = app.AppMetadataStore(Path(data_tmp))
            store.apply_tmdb_match(str(movie), {
                "tmdb_id": "348",
                "title": "Alien",
                "year": "1979",
                "poster_url": "https://image.tmdb.org/provider.jpg",
            })
            override = store.save_poster_override(
                {"tmdb_id": "348", "title": "Alien", "year": "1979"},
                source="local",
                image_bytes=JPEG_BYTES,
                extension=".jpg",
            )

            with patch("app._auto_sync_plex"), patch(
                "app._tmdb_metadata_for_file",
                return_value={
                    "tmdb_id": "348",
                    "title": "Alien",
                    "year": "1979",
                    "poster_url": "https://image.tmdb.org/refreshed-provider.jpg",
                    "accepted": True,
                },
            ):
                response = app.app.test_client().post(
                    "/api/metadata/refresh",
                    json={"path": str(movie)},
                )

        self.assertEqual(response.status_code, 200)
        canonical = response.get_json()["canonical_metadata"]
        self.assertEqual(canonical["poster_url"], override["poster_url"])
        self.assertTrue(canonical["poster_override"])


if __name__ == "__main__":
    unittest.main()
