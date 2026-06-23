import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        import json
        return json.dumps(self.payload).encode("utf-8")


class UserCurationStoreTest(unittest.TestCase):
    def test_system_lists_are_created_and_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = app.UserCurationStore(Path(tmp))

            lists = store.list_all()

            self.assertEqual([item["id"] for item in lists[:2]], ["watched", "watchlist"])
            self.assertEqual(lists[0]["system_type"], "watched")
            self.assertEqual(lists[1]["system_type"], "watchlist")
            with self.assertRaises(ValueError):
                store.rename_list("watched", "Seen")
            with self.assertRaises(ValueError):
                store.delete_list("watchlist")

    def test_system_list_toggle_is_idempotent_and_states_are_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = app.UserCurationStore(Path(tmp))
            movie = {"tmdb_id": "348", "title": "Alien", "year": "1979"}

            watched = store.set_system_list_state("watched", movie, True)
            watched_again = store.set_system_list_state("watched", movie, True)
            watchlisted = store.set_system_list_state("watchlist", movie, True)

            self.assertTrue(watched["active"])
            self.assertTrue(watched_again["active"])
            self.assertTrue(watchlisted["active"])
            self.assertEqual(len(next(item for item in store.list_all() if item["id"] == "watched")["movies"]), 1)
            self.assertTrue(store.system_states_for_movie(movie)["watched"])
            self.assertTrue(store.system_states_for_movie(movie)["watchlist"])
            store.set_system_list_state("watched", movie, False)
            states = store.system_states_for_movie(movie)
            self.assertFalse(states["watched"])
            self.assertTrue(states["watchlist"])

    def test_system_state_uses_shared_provider_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = app.UserCurationStore(Path(tmp))
            store.set_system_list_state(
                "watched",
                {"tmdb_id": "348", "title": "Alien", "year": "1979", "path": "E:/Movies/Alien-a.mkv"},
                True,
            )

            states = store.system_states_for_movie({
                "tmdb_id": "348",
                "title": "Alien",
                "year": "1979",
                "path": "F:/Movies/Alien-b.mkv",
            })

            self.assertTrue(states["watched"])

    def test_system_state_falls_back_to_title_year_but_rejects_conflicting_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = app.UserCurationStore(Path(tmp))
            store.set_system_list_state(
                "watched",
                {"tmdb_id": "348", "title": "Alien", "year": "1979"},
                True,
            )

            fallback = store.system_states_for_movie({"title": "Alien", "year": "1979"})
            conflict = store.system_states_for_movie({"tmdb_id": "999", "title": "Alien", "year": "1979"})

            self.assertTrue(fallback["watched"])
            self.assertFalse(conflict["watched"])

    def test_collection_override_supersedes_tmdb_and_reset_restores_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = app.UserCurationStore(Path(tmp))
            tmdb_collection = {
                "id": "8091",
                "name": "Alien Collection",
                "parts": [
                    {"tmdb_id": "348", "title": "Alien", "year": "1979"},
                    {"tmdb_id": "679", "title": "Aliens", "year": "1986"},
                ],
            }
            romulus = {"tmdb_id": "945961", "title": "Alien: Romulus", "year": "2024"}

            edited = store.save_collection_override("8091", tmdb_collection, [tmdb_collection["parts"][0], romulus])

            self.assertEqual(edited["source"], "User")
            self.assertEqual([m["title"] for m in edited["parts"]], ["Alien", "Alien: Romulus"])
            self.assertTrue(store.reset_collection("8091"))
            restored = store.effective_collection(tmdb_collection)
            self.assertEqual(restored["source"], "TMDB")
            self.assertEqual([m["title"] for m in restored["parts"]], ["Alien", "Aliens"])

    def test_user_lists_store_movies_separately_from_collections(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = app.UserCurationStore(Path(tmp))
            movie = {"tmdb_id": "348", "title": "Alien", "year": "1979", "path": "E:/Movies/Alien.mkv"}

            created = store.create_list("My Best")
            updated = store.add_movie_to_list(created["id"], movie)

            self.assertEqual(updated["name"], "My Best")
            self.assertEqual(updated["movies"][0]["title"], "Alien")
            self.assertEqual(store.lists_for_movie(movie)[0]["name"], "My Best")
            store.remove_movie_from_list(created["id"], movie)
            self.assertEqual(store.lists_for_movie(movie), [])

    def test_bulk_add_movies_to_list_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = app.UserCurationStore(Path(tmp))
            created = store.create_list("Childhood")
            alien = {"tmdb_id": "348", "title": "Alien", "year": "1979", "path": "E:/Movies/Alien.mkv"}
            aliens = {"tmdb_id": "679", "title": "Aliens", "year": "1986", "path": "E:/Movies/Aliens.mkv"}

            updated = store.add_movies_to_list(created["id"], [alien, aliens, {**alien, "path": "F:/Copies/Alien.mkv"}])

            self.assertEqual([movie["title"] for movie in updated["movies"]], ["Alien", "Aliens"])

    def test_copy_export_job_copies_local_movies_and_skips_unsafe_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "library"
            destination = root / "usb"
            source.mkdir()
            destination.mkdir()
            alien = source / "Alien.mkv"
            aliens = source / "Aliens.mkv"
            alien.write_bytes(b"alien")
            aliens.write_bytes(b"aliens")
            (destination / "Aliens.mkv").write_bytes(b"already here")

            job = app._create_copy_export_job(
                [
                    {"title": "Alien", "year": "1979", "path": str(alien)},
                    {"title": "Aliens", "year": "1986", "path": str(aliens)},
                    {"title": "Remote only", "year": "1984", "tmdb_id": "1"},
                    {"title": "Missing", "year": "1999", "path": str(source / "Missing.mkv")},
                ],
                str(destination),
                start=False,
            )

            app._run_copy_export_job(job["id"])
            snapshot = app._copy_export_job_snapshot(job["id"])

            self.assertEqual(snapshot["status"], "completed")
            self.assertEqual(snapshot["copied_count"], 1)
            self.assertEqual(snapshot["skipped_count"], 3)
            self.assertEqual(snapshot["failed_count"], 0)
            self.assertEqual((destination / "Alien.mkv").read_bytes(), b"alien")
            self.assertEqual((destination / "Aliens.mkv").read_bytes(), b"already here")

    def test_user_lists_can_be_renamed_and_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = app.UserCurationStore(Path(tmp))
            created = store.create_list("My Best")

            renamed = store.rename_list(created["id"], "Better Picks")
            self.assertEqual(renamed["name"], "Better Picks")
            self.assertTrue(store.delete_list(created["id"]))
            self.assertEqual([item["id"] for item in store.list_all()], ["watched", "watchlist"])

    def test_followed_releases_can_be_added_updated_and_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = app.UserCurationStore(Path(tmp))
            movie = {"tmdb_id": "945961", "title": "Alien: Romulus", "year": "2024", "poster_url": "poster-a"}

            followed = store.follow_movie(movie)
            updated = store.follow_movie({**movie, "poster_url": "poster-b"})

            self.assertEqual(followed["status"], "watching")
            self.assertEqual(updated["poster_url"], "poster-b")
            self.assertEqual(len(store.followed_all()), 1)
            self.assertTrue(store.unfollow_movie(movie))
            self.assertEqual(store.followed_all(), [])

    def test_followed_release_quality_gate_rejects_camera_rips(self):
        self.assertIsNone(app._proper_release_from_title("New Movie 2026 1080p HDCAM"))
        self.assertIsNone(app._proper_release_from_title("New Movie 2026 1080p TELESYNC"))
        self.assertIsNone(app._proper_release_from_title("New Movie 2026 1080p TELE-SYNC WEBRip"))
        self.assertIsNone(app._proper_release_from_title("New Movie 2026 1080p TELE.SYNC BluRay"))
        self.assertIsNone(app._proper_release_from_title("New Movie 2026 1080p Tele Sync BDRip"))
        self.assertIsNone(app._proper_release_from_title("New Movie 2026 1080p TELESYNC265 WEBRip"))
        self.assertIsNone(app._proper_release_from_title("New Movie 2026 1080p TELESYNCx264 BluRay"))
        self.assertIsNone(app._proper_release_from_title("New Movie 2026 1080p TELE-SYNCHEVC BDRip"))
        self.assertIsNone(app._proper_release_from_title("New Movie 2026 720p WEB-DL"))

    def test_followed_release_quality_gate_accepts_only_approved_sources(self):
        self.assertIsNone(app._proper_release_from_title("New Movie 2026 1080p WEB-DL"))
        self.assertIsNone(app._proper_release_from_title("New Movie 2026 1080p Remux"))
        self.assertIsNone(app._proper_release_from_title("New Movie 2026 1080p BDRemux"))
        self.assertEqual(app._proper_release_from_title("New Movie 2026 1080p WEBRip")["source"], "WEBRip")
        self.assertEqual(app._proper_release_from_title("New Movie 2026 1080p BluRay")["source"], "Blu-ray")
        self.assertEqual(app._proper_release_from_title("New Movie 2026 1080p BDRip")["source"], "BDRip")
        self.assertEqual(app._proper_release_from_title("New Movie 2026 1080p BRRip")["source"], "BDRip")

    def test_followed_release_requires_trusted_indexer_for_availability(self):
        original = (
            app._prowlarr_url,
            app._prowlarr_key,
            app._trusted_release_indexers,
            app._trusted_release_indexers_configured,
        )
        app._prowlarr_url = "http://prowlarr.test"
        app._prowlarr_key = "key"
        app._trusted_release_indexers = []
        app._trusted_release_indexers_configured = True

        def fake_urlopen(_request, timeout=0):
            return _FakeResponse([
                {"title": "Disclosure Day 2026 1080p WEBRip LAMA", "indexer": "YTS", "seeders": 50, "size": 1000}
            ])

        try:
            with patch("app.urllib.request.urlopen", side_effect=fake_urlopen):
                self.assertIsNone(app._find_best_followed_release({"title": "Disclosure Day", "year": "2026"}))
        finally:
            (
                app._prowlarr_url,
                app._prowlarr_key,
                app._trusted_release_indexers,
                app._trusted_release_indexers_configured,
            ) = original

    def test_prowlarr_config_defaults_trusted_release_indexer_to_yts(self):
        original = (
            app._prowlarr_url,
            app._prowlarr_key,
            app._trusted_release_indexers,
            app._trusted_release_indexers_configured,
        )
        app._prowlarr_url = "http://prowlarr.test"
        app._prowlarr_key = "key"
        app._trusted_release_indexers = []
        app._trusted_release_indexers_configured = False

        def fake_urlopen(request, timeout=0):
            self.assertTrue(request.full_url.endswith("/api/v1/indexer"))
            return _FakeResponse([
                {"id": 1, "name": "NoNaMe Club", "enable": True},
                {"id": 2, "name": "YTS", "enable": True},
            ])

        try:
            with patch("app.urllib.request.urlopen", side_effect=fake_urlopen):
                response = app.app.test_client().get("/api/prowlarr/config")
        finally:
            (
                app._prowlarr_url,
                app._prowlarr_key,
                app._trusted_release_indexers,
                app._trusted_release_indexers_configured,
            ) = original

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["trusted_release_indexers"], ["2"])

    def test_followed_release_uses_only_selected_trusted_indexers(self):
        original = (
            app._prowlarr_url,
            app._prowlarr_key,
            app._trusted_release_indexers,
            app._trusted_release_indexers_configured,
        )
        app._prowlarr_url = "http://prowlarr.test"
        app._prowlarr_key = "key"
        app._trusted_release_indexers = ["1"]
        app._trusted_release_indexers_configured = True

        def fake_urlopen(request, timeout=0):
            url = request.full_url
            if url.endswith("/api/v1/indexer"):
                return _FakeResponse([
                    {"id": 1, "name": "YTS", "enable": True},
                    {"id": 2, "name": "Fake Tracker", "enable": True},
                ])
            self.assertIn("indexerIds=1", url)
            self.assertNotIn("indexerIds=2", url)
            return _FakeResponse([
                {"title": "Disclosure Day 2026 2160p WEBRip FAKE", "indexer": "Fake Tracker", "seeders": 500, "size": 4000},
                {"title": "Disclosure Day 2026 1080p WEBRip YTS", "indexer": "YTS", "seeders": 5, "size": 1000},
            ])

        try:
            with patch("app.urllib.request.urlopen", side_effect=fake_urlopen):
                release = app._find_best_followed_release({"title": "Disclosure Day", "year": "2026"})
        finally:
            (
                app._prowlarr_url,
                app._prowlarr_key,
                app._trusted_release_indexers,
                app._trusted_release_indexers_configured,
            ) = original

        self.assertIsNotNone(release)
        self.assertEqual(release["indexer"], "YTS")


if __name__ == "__main__":
    unittest.main()
