import tempfile
import time
import unittest
import json
from pathlib import Path
from unittest.mock import patch

import app


class SmartMatchApiTest(unittest.TestCase):
    def setUp(self):
        self.original_dirs = app._movies_dirs
        self.original_dir = app._movies_dir
        self.original_user_data_dir = app._user_data_dir
        self.original_tmdb_key = app._tmdb_key
        self.original_ollama_url = app._ollama_url
        self.original_ollama_model = app._ollama_model
        self.original_plex_cache = dict(app._plex_cache)
        self.original_plex_unmatched = dict(app._plex_unmatched)
        self.original_library_cache = dict(app._library_cache)
        self.original_coordinator = getattr(app, "_smart_match_coordinator", None)
        self.original_coordinator_dir = getattr(app, "_smart_match_store_dir", "")

    def tearDown(self):
        app._movies_dirs = self.original_dirs
        app._movies_dir = self.original_dir
        app._user_data_dir = self.original_user_data_dir
        app._tmdb_key = self.original_tmdb_key
        app._ollama_url = self.original_ollama_url
        app._ollama_model = self.original_ollama_model
        app._plex_cache = self.original_plex_cache
        app._plex_unmatched = self.original_plex_unmatched
        app._library_cache = self.original_library_cache
        app._smart_match_coordinator = self.original_coordinator
        app._smart_match_store_dir = self.original_coordinator_dir

    def test_preview_requires_authorized_library_paths_and_does_not_apply_match(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as outside_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            outside = Path(outside_tmp) / "Outside.2024.mkv"
            movie.write_bytes(b"movie")
            outside.write_bytes(b"outside")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            app._smart_match_coordinator = None
            app._smart_match_store_dir = ""
            client = app.app.test_client()

            rejected = client.post("/api/metadata/smart-match", json={
                "paths": [str(outside)],
                "provider": "tmdb",
                "method": "classic",
            })
            with patch("app._smart_match_tmdb_candidates", return_value=[{
                "tmdb_id": "348",
                "title": "Alien",
                "year": "1979",
            }]):
                started = client.post("/api/metadata/smart-match", json={
                    "paths": [str(movie)],
                    "provider": "tmdb",
                    "method": "classic",
                    "background": False,
                })
                app._get_smart_match_coordinator().run_batch(limit=10)
                status = client.get(f"/api/metadata/smart-match/{started.get_json()['id']}")

            store = app.AppMetadataStore(Path(data_tmp))

        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(started.status_code, 200)
        self.assertEqual(status.get_json()["status"], "completed")
        self.assertEqual(len(status.get_json()["proposals"]), 1)
        self.assertEqual(store.get_manual_match(str(movie)), {})

    def test_apply_uses_explicit_proposal_ids_only(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            first = Path(movies_tmp) / "Alien.1979.mkv"
            second = Path(movies_tmp) / "Aliens.1986.mkv"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            app._smart_match_coordinator = None
            app._smart_match_store_dir = ""
            candidates = {
                "Alien": [{"tmdb_id": "348", "title": "Alien", "year": "1979"}],
                "Aliens": [{"tmdb_id": "679", "title": "Aliens", "year": "1986"}],
            }
            with patch("app._smart_match_tmdb_candidates", side_effect=lambda title, year: candidates[title]):
                client = app.app.test_client()
                started = client.post("/api/metadata/smart-match", json={
                    "paths": [str(first), str(second)],
                    "provider": "tmdb",
                    "method": "classic",
                    "background": False,
                })
                app._get_smart_match_coordinator().run_batch(limit=10)
                proposals = app._get_smart_match_coordinator().status()["proposals"]
                applied = client.post(
                    f"/api/metadata/smart-match/{started.get_json()['id']}/apply",
                    json={"proposal_ids": [proposals[0]["id"]]},
                )
            store = app.AppMetadataStore(Path(data_tmp))
            first_match = store.get_manual_match(str(first))
            second_match = store.get_manual_match(str(second))

        self.assertEqual(applied.status_code, 200)
        self.assertEqual(applied.get_json()["applied"], 1)
        self.assertTrue(first_match)
        self.assertEqual(second_match, {})

    def test_preview_rejects_an_already_accepted_identity(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            app._smart_match_coordinator = None
            app._smart_match_store_dir = ""
            app.AppMetadataStore(Path(data_tmp)).update_file_record(str(movie), {
                "identity_status": "accepted",
                "metadata_status": "accepted",
                "identity_title": "Alien",
                "identity_year": "1979",
                "tmdb_id": "348",
                "identity_revision": 3,
            })

            response = app.app.test_client().post("/api/metadata/smart-match", json={
                "paths": [str(movie)],
                "provider": "tmdb",
                "method": "classic",
                "background": False,
            })

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "smart_match_ineligible")
        self.assertEqual(response.get_json()["items"][0]["code"], "accepted")

    def test_apply_rejects_a_proposal_after_identity_revision_changes(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            app._smart_match_coordinator = None
            app._smart_match_store_dir = ""
            store = app.AppMetadataStore(Path(data_tmp))
            store.update_file_record(str(movie), {
                "identity_status": "unmatched",
                "identity_revision": 4,
            })
            with patch("app._smart_match_tmdb_candidates", return_value=[{
                "tmdb_id": "348", "title": "Alien", "year": "1979",
            }]):
                client = app.app.test_client()
                started = client.post("/api/metadata/smart-match", json={
                    "paths": [str(movie)],
                    "provider": "tmdb",
                    "method": "classic",
                    "background": False,
                })
                app._get_smart_match_coordinator().run_batch(limit=10)
                proposal = app._get_smart_match_coordinator().status()["proposals"][0]
                store.update_file_record(str(movie), {"identity_revision": 5})
                applied = client.post(
                    f"/api/metadata/smart-match/{started.get_json()['id']}/apply",
                    json={"proposal_ids": [proposal["id"]]},
                )

        self.assertEqual(applied.get_json()["applied"], 0)
        self.assertIn("changed after preview", applied.get_json()["results"][0]["error"])

    def test_plex_apply_persists_local_choice_without_mutating_plex(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            proposal = {
                "path": str(movie),
                "rating_key": "42",
                "candidate": {
                    "guid": "plex://movie/alien",
                    "title": "Alien",
                    "year": "1979",
                },
            }
            with patch("app.urllib.request.urlopen") as urlopen:
                result = app._apply_plex_smart_match(proposal)

        urlopen.assert_not_called()
        self.assertEqual(result["provider"], "plex")
        self.assertEqual(result["rating_key"], "42")

    def test_ai_mode_sends_basename_not_full_path_and_validates_provider_result(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "01 Alien VS Predator AVP Unrated 2004 1080p.mp4"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            app._ollama_url = "http://ollama.test"
            app._ollama_model = "gemma"
            app._smart_match_coordinator = None
            app._smart_match_store_dir = ""
            captured = []
            with patch("app._smart_match_ai_batch", side_effect=lambda items: captured.extend(items) or {
                "matches": {
                    items[0]["id"]: {
                        "title": "Alien vs. Predator",
                        "year": "2004",
                        "alternatives": [],
                    }
                },
                "errors": {},
            }), patch(
                "app._smart_match_tmdb_candidates",
                return_value=[{"tmdb_id": "395", "title": "AVP: Alien vs. Predator", "year": "2004"}],
            ):
                client = app.app.test_client()
                started = client.post("/api/metadata/smart-match", json={
                    "paths": [str(movie)],
                    "provider": "tmdb",
                    "method": "ai",
                    "background": False,
                })
                app._get_smart_match_coordinator().run_batch(limit=10)
                proposal = app._get_smart_match_coordinator().status()["proposals"][0]

        self.assertEqual(started.status_code, 200)
        self.assertEqual(captured[0]["filename"], movie.name)
        self.assertEqual(captured[0]["folder_name"], movie.parent.name)
        self.assertNotIn(str(movie.parent.parent), str(captured[0]))
        self.assertTrue(proposal["preselected"])

    def test_tmdb_candidates_merge_year_and_unconstrained_searches_with_aliases(self):
        calls = []
        with patch("app._smart_match_tmdb_search", side_effect=lambda title, year="": calls.append((title, year)) or [{
            "id": 9369,
            "title": "Asterix Conquers America",
            "original_title": "Asterix in Amerika",
            "release_date": "1994-09-29",
        }]), patch("app._smart_match_tmdb_alternative_titles", return_value=["Asterix in America"]):
            candidates = app._smart_match_tmdb_candidates("Asterix In America", "1994")

        self.assertEqual(calls, [("Asterix In America", "1994"), ("Asterix In America", "")])
        self.assertEqual(candidates[0]["original_title"], "Asterix in Amerika")
        self.assertIn("Asterix in America", candidates[0]["alternative_titles"])
        self.assertEqual(
            set(candidates[0]["query_sources"]),
            {"title_with_year", "title_without_year"},
        )

    def test_plex_candidates_preserve_provider_result_rank(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({
                    "MediaContainer": {
                        "SearchResult": [
                            {"guid": "plex://one", "name": "Alien", "year": 1979},
                            {"guid": "plex://two", "name": "Aliens", "year": 1986},
                        ]
                    }
                }).encode()

        original_url = app._plex_url
        original_token = app._plex_token
        app._plex_url = "http://plex.test"
        app._plex_token = "token"
        try:
            with patch("app.urllib.request.urlopen", return_value=FakeResponse()):
                candidates = app._smart_match_plex_candidates("42", "Alien", "1979")
        finally:
            app._plex_url = original_url
            app._plex_token = original_token

        self.assertEqual([candidate["provider_rank"] for candidate in candidates], [1, 2])

    def test_ai_batch_strips_fences_and_sends_only_safe_basenames(self):
        captured = []
        with patch("app._ollama_chat_content", side_effect=lambda messages: captured.append(messages) or (
            "```json\n"
            '{"matches":[{"id":"item-1","canonical":"Audition","year":1999,'
            '"alternatives":[{"title":"Odishon","year":"1999"}]}]}'
            "\n```"
        )):
            result = app._smart_match_ai_batch([{
                "id": "item-1",
                "filename": "Audition [Odishon] (1999).mp4",
                "folder_name": "Audition 1999 720p BDRip",
                "title_hint": "Audition (",
                "year_hint": "1999",
            }])

        prompt = json.dumps(captured)
        self.assertIn("Audition [Odishon] (1999).mp4", prompt)
        self.assertIn("Audition 1999 720p BDRip", prompt)
        self.assertNotIn("E:\\\\Movies", prompt)
        self.assertEqual(result["matches"]["item-1"]["title"], "Audition")
        self.assertEqual(result["errors"], {})

    def test_ai_batch_repairs_missing_entries_once(self):
        responses = [
            '{"matches":[]}',
            '{"matches":[{"id":"item-1","title":"Alien","year":"1979","alternatives":[]}]}',
        ]
        with patch("app._ollama_chat_content", side_effect=responses) as chat:
            result = app._smart_match_ai_batch([{
                "id": "item-1",
                "filename": "Alien.1979.mkv",
                "folder_name": "Alien",
                "title_hint": "Alien",
                "year_hint": "1979",
            }])

        self.assertEqual(chat.call_count, 2)
        self.assertEqual(result["matches"]["item-1"]["title"], "Alien")
        self.assertEqual(result["errors"], {})

    def test_ai_failure_falls_back_to_classic_with_visible_warning(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            folder = Path(movies_tmp) / "Audition 1999"
            folder.mkdir()
            movie = folder / "Audition [Odishon] (1999).mp4"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            with patch("app._smart_match_ai_batch", return_value={
                "matches": {},
                "errors": {"item-0": "AI response invalid after repair"},
            }), patch("app._smart_match_tmdb_candidates", return_value=[{
                "tmdb_id": "11075",
                "title": "Audition",
                "alternative_titles": ["Oodishon"],
                "year": "2000",
                "provider_rank": 1,
                "query_sources": ["title_without_year"],
            }]):
                results = app._process_smart_match_batch([str(movie)], "tmdb", "ai")

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["candidate"])
        self.assertEqual(results[0]["ai_status"], "classic_fallback")
        self.assertIn("AI response invalid", results[0]["ai_warning"])

    def test_ai_invalid_json_becomes_visible_fallback_warning_without_metadata_mutation(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({"message": {"content": "not-json"}}).encode()

        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Ambiguous.Release.2024.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp
            app._tmdb_key = "tmdb-key"
            app._ollama_url = "http://ollama.test"
            app._ollama_model = "gemma"
            app._smart_match_coordinator = None
            app._smart_match_store_dir = ""
            with patch("app.urllib.request.urlopen", return_value=FakeResponse()):
                started = app.app.test_client().post("/api/metadata/smart-match", json={
                    "paths": [str(movie)],
                    "provider": "tmdb",
                    "method": "ai",
                    "background": False,
                })
                state = app._get_smart_match_coordinator().run_batch(limit=10)
            match = app.AppMetadataStore(Path(data_tmp)).get_manual_match(str(movie))

        self.assertEqual(started.status_code, 200)
        self.assertEqual(state["errors"], [])
        self.assertEqual(len(state["unresolved"]), 1)
        self.assertEqual(state["unresolved"][0]["ai_status"], "classic_fallback")
        self.assertIn("AI response invalid after repair", state["unresolved"][0]["ai_warning"])
        self.assertEqual(match, {})

    def test_rename_preview_blocks_existing_destination(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.bad-name.mkv"
            destination = Path(movies_tmp) / "Alien (1979) [1080p].mkv"
            movie.write_bytes(b"movie")
            destination.write_bytes(b"existing")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp

            response = app.app.test_client().post("/api/metadata/smart-rename/preview", json={
                "items": [{
                    "path": str(movie),
                    "title": "Alien",
                    "year": "1979",
                    "release": {"resolution": "1080p"},
                }]
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["items"][0]["blocked"], "Destination file already exists")

    def test_rename_preview_rejects_invalid_empty_filename(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Unknown.mkv"
            movie.write_bytes(b"movie")
            app._movies_dirs = [movies_tmp]
            app._movies_dir = movies_tmp
            app._user_data_dir = data_tmp

            response = app.app.test_client().post("/api/metadata/smart-rename/preview", json={
                "items": [{"path": str(movie), "title": "<>:\"/\\|?*", "year": "", "release": {}}]
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["items"][0]["blocked"], "Generated filename is invalid")

    def test_rename_preview_and_apply_migrate_path_keyed_metadata(self):
        with tempfile.TemporaryDirectory() as movies_tmp, tempfile.TemporaryDirectory() as data_tmp:
            movie = Path(movies_tmp) / "Alien.1979.1080p.WEBRip.mkv"
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
            preview = client.post("/api/metadata/smart-rename/preview", json={
                "items": [{
                    "path": str(movie),
                    "title": "Alien",
                    "year": "1979",
                    "release": {"resolution": "1080p", "source": "WEBRip"},
                }]
            })
            body = preview.get_json()
            with patch("app._plex_rescan") as rescan:
                applied = client.post("/api/metadata/smart-rename/apply", json={
                    "token": body["token"],
                    "paths": [str(movie)],
                })
            result = applied.get_json()["results"][0]
            new_path = Path(result["new_path"])
            reloaded = app.AppMetadataStore(Path(data_tmp))
            new_exists = new_path.is_file()
            old_exists = movie.exists()
            new_match = reloaded.get_manual_match(str(new_path))
            old_match = reloaded.get_manual_match(str(movie))

        self.assertEqual(preview.status_code, 200)
        self.assertFalse(body["items"][0]["blocked"])
        self.assertEqual(applied.status_code, 200)
        self.assertTrue(new_exists)
        self.assertFalse(old_exists)
        self.assertTrue(new_match)
        self.assertEqual(old_match, {})
        rescan.assert_called_once()


if __name__ == "__main__":
    unittest.main()
