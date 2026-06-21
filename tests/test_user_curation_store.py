import tempfile
import unittest
from pathlib import Path

import app


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
        self.assertIsNone(app._proper_release_from_title("New Movie 2026 720p WEB-DL"))
        self.assertEqual(
            app._proper_release_from_title("New Movie 2026 1080p WEB-DL")["source"],
            "WEB-DL",
        )


if __name__ == "__main__":
    unittest.main()
