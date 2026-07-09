import json
import os
import tempfile
import unittest

from services import ai_control


class AiControlServiceTest(unittest.TestCase):
    def test_capabilities_schema_exposes_expected_actions_and_states(self):
        schema = ai_control.load_capabilities()

        self.assertEqual(schema["version"], 1)
        self.assertEqual(
            set(schema["actions"]),
            {"find", "create_list", "download", "delete"},
        )
        self.assertIn("needs_clarification", schema["states"])
        self.assertEqual(schema["execution"]["delete"], "preview_required")

    def test_vague_prompt_returns_clarification_without_plan(self):
        result = ai_control.preview_command(
            "clean my movies",
            config=ai_control.default_config(),
            library_items=[],
            ollama_chat=lambda messages: json.dumps({"action": "delete", "filters": []}),
        )

        self.assertEqual(result["state"], "needs_clarification")
        self.assertEqual(result["plan_id"], "")
        self.assertIn("specific action", result["message"])

    def test_broad_all_movies_by_decade_requires_scope_clarification(self):
        result = ai_control.preview_command(
            "find all movies from the 90s",
            config=ai_control.default_config(),
            library_items=[],
            ollama_chat=lambda messages: json.dumps({
                "action": "find",
                "subject": "",
                "subject_type": "genre",
                "owned": "either",
                "year_from": "1990",
                "year_to": "1999",
            }),
        )

        self.assertEqual(result["state"], "needs_clarification")
        self.assertIn("library or online", result["message"].lower())

    def test_malformed_ai_filter_returns_safe_result_without_500(self):
        result = ai_control.preview_command(
            "Find Tom Cruise movies I own",
            config=ai_control.default_config(),
            library_items=[],
            ollama_chat=lambda messages: json.dumps({"action": "find", "filters": ["Tom Cruise"]}),
        )

        self.assertEqual(result["state"], "no_matches")
        self.assertEqual(result["plan_id"], "")

    def test_malformed_ai_filter_falls_back_to_local_person_find(self):
        result = ai_control.preview_command(
            "Find Tom Cruise movies I own",
            config=ai_control.default_config(),
            library_items=[
                {
                    "title": "No Cruise Here",
                    "year": "2000",
                    "path": "E:\\Movies\\No Cruise Here.mkv",
                    "cast": [{"name": "Someone Else"}],
                },
                {
                    "title": "Mission Impossible",
                    "year": "1996",
                    "path": "E:\\Movies\\Mission Impossible.mkv",
                    "cast": [{"name": "Tom Cruise"}],
                }
            ],
            ollama_chat=lambda messages: json.dumps({"action": "find", "filters": ["Tom Cruise"]}),
        )

        self.assertEqual(result["state"], "valid_plan")
        self.assertEqual(result["action"], "find")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["title"], "Mission Impossible")

    def test_unowned_nolan_download_uses_christopher_nolan_director_filter(self):
        captured = []
        config = {**ai_control.default_config(), "trusted_indexers": ["1"]}

        result = ai_control.preview_command(
            "Download unowned Nolan movies in 1080p",
            config=config,
            library_items=[],
            ollama_chat=lambda messages: json.dumps({"action": "download", "filters": ["nolan"]}),
            person_movies=lambda name, role, settings: captured.append((name, role)) or [],
            source_search=lambda movie, settings: [],
        )

        self.assertEqual(result["state"], "no_matches")
        self.assertEqual(captured, [("Christopher Nolan", "director")])

    def test_download_skips_tmdb_movie_already_owned_by_title_and_year(self):
        searched = []
        config = {**ai_control.default_config(), "trusted_indexers": ["1"]}

        result = ai_control.preview_command(
            "Download unowned Jim Carrey movies in 1080p",
            config=config,
            library_items=[
                {"title": "Sonic the Hedgehog", "year": "2020", "path": "E:\\Movies\\Sonic.mkv"},
            ],
            ollama_chat=lambda messages: json.dumps({
                "action": "download",
                "filters": [{"field": "actor", "op": "equals", "value": "Jim Carrey"}],
            }),
            person_movies=lambda name, role, settings: [
                {"tmdb_id": "454626", "title": "Sonic the Hedgehog", "year": "2020", "source": "TMDB"},
            ],
            source_search=lambda movie, settings: searched.append(movie) or [
                {"title": "Sonic the Hedgehog 1080p", "indexer": "YTS", "indexer_id": "1", "resolution": "1080p"}
            ],
        )

        self.assertEqual(result["state"], "no_matches")
        self.assertEqual(searched, [])
        self.assertEqual(result["blocked"][0]["status"], "already_owned")
        self.assertEqual(result["blocked"][0]["reason"], "Already in library")

    def test_semantic_ollama_intent_creates_person_grounded_list(self):
        captured = []

        result = ai_control.preview_command(
            'create a list named "Alan Rickman movies" and include all alan rickman movies in the list',
            config=ai_control.default_config(),
            library_items=[],
            ollama_chat=lambda messages: json.dumps({
                "action": "create_list",
                "target": {"type": "person", "name": "Alan Rickman", "role": "actor"},
                "list_name": "Alan Rickman movies",
                "constraints": {
                    "owned": "unknown",
                    "quality": "unknown",
                    "year": "",
                    "genre": "",
                    "size_gb": "",
                    "comparison": "unknown",
                },
            }),
            person_movies=lambda name, role, settings: captured.append((name, role)) or [
                {"tmdb_id": "562", "title": "Die Hard", "year": "1988", "source": "TMDB"},
            ],
        )

        self.assertEqual(result["state"], "valid_plan")
        self.assertEqual(result["action"], "create_list")
        self.assertEqual(result["list_name"], "Alan Rickman movies")
        self.assertEqual(captured, [("Alan Rickman", "actor")])
        self.assertEqual(result["items"][0]["title"], "Die Hard")

    def test_flat_ollama_intent_compiles_top_rated_sci_fi_80s(self):
        captured = []

        result = ai_control.preview_command(
            "find me a list of all high rated sci fi movies from the 80s",
            config=ai_control.default_config(),
            library_items=[],
            ollama_chat=lambda messages: json.dumps({
                "action": "find",
                "subject": "",
                "subject_type": "genre",
                "list_name": "",
                "owned": "either",
                "quality": "",
                "genre": "Science Fiction",
                "year_from": "1980",
                "year_to": "1989",
                "sort": "top_rated",
                "size_gb": "",
                "comparison": "",
            }),
            tmdb_discover=lambda intent, settings: captured.append(intent) or [
                {"tmdb_id": "78", "title": "Blade Runner", "year": "1982", "source": "TMDB"},
            ],
        )

        self.assertEqual(result["state"], "valid_plan")
        self.assertEqual(result["source"], "tmdb")
        self.assertEqual(result["items"][0]["title"], "Blade Runner")
        self.assertEqual(captured[0]["sort"], "top_rated")
        self.assertIn({"field": "genre", "op": "equals", "value": "Science Fiction"}, captured[0]["filters"])
        self.assertIn({"field": "year", "op": "between", "value": ["1980", "1989"]}, captured[0]["filters"])

    def test_find_preview_preserves_tmdb_card_metadata(self):
        result = ai_control.preview_command(
            "find me a list of all high rated sci fi movies from the 80s",
            config=ai_control.default_config(),
            library_items=[],
            ollama_chat=lambda messages: json.dumps({
                "action": "find",
                "subject": "",
                "subject_type": "genre",
                "owned": "either",
                "genre": "Science Fiction",
                "year_from": "1980",
                "year_to": "1989",
                "sort": "top_rated",
                "list_name": "",
                "quality": "",
                "size_gb": "",
                "comparison": "",
            }),
            tmdb_discover=lambda intent, settings: [
                {
                    "tmdb_id": "78",
                    "imdb_id": "tt0083658",
                    "title": "Blade Runner",
                    "year": "1982",
                    "poster_url": "https://image.tmdb.org/t/p/w342/blade.jpg",
                    "genres": ["Science Fiction", "Drama"],
                    "tmdb_rating": "7.9",
                    "tmdb_vote_count": 14000,
                    "plot": "A blade runner hunts artificial humans.",
                    "language": "English",
                    "country": "US",
                    "country_flag": "US",
                    "release_date": "1982-06-25",
                    "source": "TMDB",
                },
            ],
        )

        item = result["items"][0]
        self.assertEqual(item["genres"], ["Science Fiction", "Drama"])
        self.assertEqual(item["tmdb_rating"], "7.9")
        self.assertEqual(item["tmdb_vote_count"], 14000)
        self.assertEqual(item["plot"], "A blade runner hunts artificial humans.")
        self.assertEqual(item["language"], "English")
        self.assertEqual(item["country_flag"], "US")
        self.assertEqual(item["release_date"], "1982-06-25")

    def test_find_preview_preserves_owned_library_card_metadata(self):
        result = ai_control.preview_command(
            "Find Tom Cruise movies I own",
            config=ai_control.default_config(),
            library_items=[
                {
                    "title": "Mission: Impossible",
                    "year": "1996",
                    "path": "E:\\Movies\\Mission Impossible.mkv",
                    "resolution": "1080p",
                    "size_human": "2.4 GB",
                    "genres": ["Action", "Thriller"],
                    "tmdb_rating": "7.0",
                    "tmdb_vote_count": 9300,
                    "plot": "Ethan Hunt races to expose a mole.",
                    "language": "English",
                    "country": "US",
                    "country_flag": "US",
                    "release_date": "1996-05-22",
                    "directors": [{"name": "Brian De Palma"}],
                    "cast": [{"name": "Tom Cruise", "character": "Ethan Hunt"}],
                    "source": "Library",
                }
            ],
            ollama_chat=lambda messages: json.dumps({"action": "find", "filters": ["Tom Cruise"]}),
        )

        item = result["items"][0]
        self.assertEqual(item["resolution"], "1080p")
        self.assertEqual(item["size_human"], "2.4 GB")
        self.assertEqual(item["genres"], ["Action", "Thriller"])
        self.assertEqual(item["tmdb_rating"], "7.0")
        self.assertEqual(item["tmdb_vote_count"], 9300)
        self.assertEqual(item["plot"], "Ethan Hunt races to expose a mole.")
        self.assertEqual(item["directors"], [{"name": "Brian De Palma"}])
        self.assertEqual(item["cast"], [{"name": "Tom Cruise", "character": "Ethan Hunt"}])

    def test_find_owned_person_results_intersect_online_matches_with_library(self):
        result = ai_control.preview_command(
            "Find Tom Cruise movies I own",
            config=ai_control.default_config(),
            library_items=[
                {
                    "title": "Mission: Impossible",
                    "year": "1996",
                    "path": "E:\\Movies\\Mission Impossible.mkv",
                    "tmdb_id": "954",
                    "resolution": "1080p",
                    "size_human": "2.4 GB",
                }
            ],
            ollama_chat=lambda messages: json.dumps({
                "action": "find",
                "subject": "Tom Cruise",
                "subject_type": "actor",
                "owned": "owned",
            }),
            person_movies=lambda name, role, settings: [
                {"tmdb_id": "954", "title": "Mission: Impossible", "year": "1996", "source": "TMDB"},
                {"tmdb_id": "744", "title": "Top Gun", "year": "1986", "source": "TMDB"},
            ],
        )

        self.assertEqual(result["state"], "valid_plan")
        self.assertEqual(result["total_matches"], 1)
        self.assertEqual([item["title"] for item in result["items"]], ["Mission: Impossible"])
        self.assertEqual(result["items"][0]["path"], "E:\\Movies\\Mission Impossible.mkv")
        self.assertEqual(result["items"][0]["source"], "Library")

    def test_find_unowned_person_results_exclude_library_matches(self):
        result = ai_control.preview_command(
            "Find Tom Cruise movies not in my library",
            config=ai_control.default_config(),
            library_items=[
                {"title": "Mission: Impossible", "year": "1996", "path": "E:\\Movies\\Mission Impossible.mkv", "tmdb_id": "954"},
            ],
            ollama_chat=lambda messages: json.dumps({
                "action": "find",
                "subject": "Tom Cruise",
                "subject_type": "actor",
                "owned": "either",
            }),
            person_movies=lambda name, role, settings: [
                {"tmdb_id": "954", "title": "Mission: Impossible", "year": "1996", "source": "TMDB"},
                {"tmdb_id": "744", "title": "Top Gun", "year": "1986", "source": "TMDB"},
            ],
        )

        self.assertEqual(result["state"], "valid_plan")
        self.assertEqual(result["total_matches"], 1)
        self.assertEqual([item["title"] for item in result["items"]], ["Top Gun"])

    def test_find_does_not_silently_crop_person_results_to_max_matched_movies(self):
        movies = [
            {"tmdb_id": str(index), "title": f"Tom Cruise Movie {index}", "year": "1996", "source": "TMDB"}
            for index in range(60)
        ]

        result = ai_control.preview_command(
            "Find all Tom Cruise movies",
            config={**ai_control.default_config(), "max_matched_movies": 25},
            library_items=[],
            ollama_chat=lambda messages: json.dumps({
                "action": "find",
                "subject": "Tom Cruise",
                "subject_type": "actor",
                "owned": "either",
            }),
            person_movies=lambda name, role, settings: movies,
        )

        self.assertEqual(result["state"], "valid_plan")
        self.assertEqual(result["total_matches"], 60)
        self.assertEqual(len(result["items"]), 60)
        self.assertEqual(result["page_size"], 50)
        self.assertIn("60 movies", result["message"])

    def test_create_list_plan_keeps_all_matched_items_and_reports_total(self):
        movies = [
            {"tmdb_id": str(index), "title": f"Alan Rickman Movie {index}", "year": "1996", "source": "TMDB"}
            for index in range(60)
        ]
        store = ai_control.PlanStore(ttl_seconds=60)

        result = ai_control.preview_command(
            'create a list named "Alan Rickman movies" and include all alan rickman movies',
            config={**ai_control.default_config(), "max_matched_movies": 25},
            library_items=[],
            plan_store=store,
            ollama_chat=lambda messages: json.dumps({
                "action": "create_list",
                "subject": "Alan Rickman",
                "subject_type": "actor",
                "owned": "either",
                "list_name": "Alan Rickman movies",
            }),
            person_movies=lambda name, role, settings: movies,
        )

        stored = store.get(result["plan_id"])
        self.assertEqual(result["state"], "valid_plan")
        self.assertEqual(result["total_matches"], 60)
        self.assertEqual(len(result["items"]), 60)
        self.assertEqual(len(stored["items"]), 60)
        self.assertIn("60 movies", result["message"])

    def test_create_list_owned_person_results_intersect_online_matches_with_library(self):
        store = ai_control.PlanStore(ttl_seconds=60)

        result = ai_control.preview_command(
            'create a list named "Owned Tom Cruise" with Tom Cruise movies I own',
            config=ai_control.default_config(),
            library_items=[
                {"title": "Top Gun", "year": "1986", "path": "E:\\Movies\\Top Gun.mkv", "tmdb_id": "744"},
            ],
            plan_store=store,
            ollama_chat=lambda messages: json.dumps({
                "action": "create_list",
                "subject": "Tom Cruise",
                "subject_type": "actor",
                "owned": "owned",
                "list_name": "Owned Tom Cruise",
            }),
            person_movies=lambda name, role, settings: [
                {"tmdb_id": "744", "title": "Top Gun", "year": "1986", "source": "TMDB"},
                {"tmdb_id": "954", "title": "Mission: Impossible", "year": "1996", "source": "TMDB"},
            ],
        )

        self.assertEqual(result["state"], "valid_plan")
        self.assertEqual(result["total_matches"], 1)
        self.assertEqual([item["title"] for item in result["items"]], ["Top Gun"])
        self.assertEqual(result["items"][0]["source"], "Library")

    def test_download_reports_total_matches_and_search_batch_cap(self):
        searched = []
        movies = [
            {"tmdb_id": str(index), "title": f"Missing Movie {index}", "year": "1996", "source": "TMDB"}
            for index in range(12)
        ]

        result = ai_control.preview_command(
            "Download unowned Tom Cruise movies in 1080p",
            config={**ai_control.default_config(), "trusted_indexers": ["1"], "max_download_searches": 3},
            library_items=[],
            ollama_chat=lambda messages: json.dumps({
                "action": "download",
                "subject": "Tom Cruise",
                "subject_type": "actor",
                "owned": "unowned",
                "quality": "1080p",
            }),
            person_movies=lambda name, role, settings: movies,
            source_search=lambda movie, settings: searched.append(movie["title"]) or [
                {"title": f"{movie['title']} 1080p", "indexer": "YTS", "indexer_id": "1", "resolution": "1080p"}
            ],
        )

        self.assertEqual(result["state"], "valid_plan")
        self.assertEqual(result["total_matches"], 12)
        self.assertEqual(len(result["items"]), 3)
        self.assertEqual(len(searched), 3)
        self.assertIn("12 movies matched", result["message"])
        self.assertIn("3 download searches planned", result["message"])

    def test_large_delete_plan_requires_extra_confirmation_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            library_items = []
            for index in range(55):
                path = os.path.join(root, f"Large Movie {index}.mkv")
                with open(path, "wb") as handle:
                    handle.write(b"x")
                library_items.append({"path": path, "title": f"Large Movie {index}", "year": "2000", "size": 12 * 1024**3})

            result = ai_control.preview_command(
                "delete movies larger than 10 GB",
                config=ai_control.default_config(),
                library_items=library_items,
                library_roots=[root],
                ollama_chat=lambda messages: json.dumps({
                    "action": "delete",
                    "filters": [{"field": "size_gb", "op": ">", "value": 10}],
                }),
            )

        self.assertEqual(result["state"], "valid_plan")
        self.assertEqual(result["total_matches"], 55)
        self.assertTrue(result["requires_extra_confirmation"])
        self.assertEqual(result["confirmation_phrase"], "DELETE 55 FILES")

    def test_malformed_ollama_filter_object_is_salvaged_to_person_list(self):
        captured = []

        result = ai_control.preview_command(
            'create a list named "Alan Rickman movies" and include all alan rickman movies in the list',
            config=ai_control.default_config(),
            library_items=[],
            ollama_chat=lambda messages: json.dumps({
                "action": "create_list",
                "filters": {"actor": {"equals": "Alan Rickman"}},
                "list_name": "Alan Rickman movies",
            }),
            person_movies=lambda name, role, settings: captured.append((name, role)) or [
                {"tmdb_id": "562", "title": "Die Hard", "year": "1988", "source": "TMDB"},
            ],
        )

        self.assertEqual(result["state"], "valid_plan")
        self.assertEqual(result["list_name"], "Alan Rickman movies")
        self.assertEqual(captured, [("Alan Rickman", "actor")])

    def test_create_list_without_grounded_target_asks_clarification(self):
        called = []

        result = ai_control.preview_command(
            "create a list",
            config=ai_control.default_config(),
            library_items=[],
            ollama_chat=lambda messages: json.dumps({
                "action": "create_list",
                "target": {"type": "unknown", "name": "", "role": "unknown"},
                "list_name": "",
                "constraints": {},
            }),
            tmdb_discover=lambda intent, settings: called.append(intent) or [
                {"tmdb_id": "1", "title": "Random Movie", "year": "2026", "source": "TMDB"},
            ],
        )

        self.assertEqual(result["state"], "needs_clarification")
        self.assertEqual(called, [])

    def test_delete_preview_matches_files_over_size_limit(self):
        with tempfile.TemporaryDirectory() as root:
            small = os.path.join(root, "Small Movie.mkv")
            large = os.path.join(root, "Large Movie.mkv")
            with open(small, "wb") as handle:
                handle.write(b"x")
            with open(large, "wb") as handle:
                handle.write(b"x")

            result = ai_control.preview_command(
                "delete movies larger than 10 GB",
                config=ai_control.default_config(),
                library_items=[
                    {"path": small, "title": "Small Movie", "year": "2001", "size": 2 * 1024**3},
                    {"path": large, "title": "Large Movie", "year": "2002", "size": 12 * 1024**3},
                ],
                library_roots=[root],
                ollama_chat=lambda messages: json.dumps(
                    {
                        "action": "delete",
                        "filters": [{"field": "size_gb", "op": ">", "value": 10}],
                    }
                ),
            )

            self.assertEqual(result["state"], "valid_plan")
            self.assertEqual(result["action"], "delete")
            self.assertEqual(len(result["items"]), 1)
            self.assertEqual(result["items"][0]["title"], "Large Movie")
            self.assertEqual(result["items"][0]["path"], large)

    def test_execute_delete_rejects_changed_file_size(self):
        with tempfile.TemporaryDirectory() as root:
            movie = os.path.join(root, "Large Movie.mkv")
            with open(movie, "wb") as handle:
                handle.write(b"x")

            store = ai_control.PlanStore(ttl_seconds=60)
            result = ai_control.preview_command(
                "delete movies larger than 10 GB",
                config=ai_control.default_config(),
                library_items=[
                    {"path": movie, "title": "Large Movie", "year": "2002", "size": 12 * 1024**3},
                ],
                library_roots=[root],
                plan_store=store,
                ollama_chat=lambda messages: json.dumps(
                    {
                        "action": "delete",
                        "filters": [{"field": "size_gb", "op": ">", "value": 10}],
                    }
                ),
            )
            with open(movie, "ab") as handle:
                handle.write(b"changed")

            executed = ai_control.execute_plan(
                result["plan_id"],
                plan_store=store,
                library_roots=[root],
                delete_file=lambda path: {"deleted": path},
            )

            self.assertEqual(executed["state"], "unsafe")
            self.assertIn("changed", executed["message"].lower())


if __name__ == "__main__":
    unittest.main()
