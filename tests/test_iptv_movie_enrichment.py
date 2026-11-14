import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from services.iptv_enrichment_worker import run_worker
from services.iptv_metadata_settings import IPTVMetadataSettings
from services.iptv_movie_service import IPTVMovieService
from services.iptv_movie_store import IPTVMovieStore, source_key
from services.iptv_provider_manager import IPTVProviderManager
from services.iptv_routes import register_iptv_routes
from services.iptv_tmdb import (
    IPTVTMDBClient,
    IPTVTMDBError,
    choose_automatic_match,
    clean_provider_title,
    normalize_tmdb_movie,
    provider_id_matches,
)
from tests.iptv_movie_fixtures import (
    FakeHTTPResponse,
    FakeTMDBClient,
    create_raw_service,
    tmdb_payload,
)


PROVIDER_A = "a" * 32
PROVIDER_B = "b" * 32


class IPTVMetadataSettingsTests(unittest.TestCase):
    def test_settings_are_lazy_atomic_blank_preserving_and_redacted(self):
        with tempfile.TemporaryDirectory() as temporary:
            settings = IPTVMetadataSettings(temporary)
            self.assertFalse(settings.path.exists())
            self.assertEqual(settings.public(), {
                "tmdb_configured": False,
                "credential_type": "bearer",
                "ollama_enabled": False,
                "ollama_url": "http://127.0.0.1:11434",
                "ollama_model": "",
            })

            saved = settings.save("fixture-secret-value", "bearer")
            before = settings.path.read_bytes()
            preserved = settings.save("", "bearer")
            redacted = settings.redact(
                "Authorization: Bearer fixture-secret-value api_key=fixture-secret-value"
            )

            self.assertEqual(saved, {
                "tmdb_configured": True,
                "credential_type": "bearer",
                "ollama_enabled": False,
                "ollama_url": "http://127.0.0.1:11434",
                "ollama_model": "",
            })
            self.assertEqual(preserved, saved)
            self.assertEqual(settings.path.read_bytes(), before)
            self.assertNotIn("fixture-secret-value", redacted)
            self.assertNotIn('"credential":', json.dumps(saved))
            self.assertEqual(settings.save(clear=True)["tmdb_configured"], False)


class IPTVMovieStoreTests(unittest.TestCase):
    def test_leftover_selection_excludes_pending_classification_and_accepted_matches(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = IPTVMovieStore(Path(temporary) / PROVIDER_A, PROVIDER_A)
            store.project_sources([{"item_id": str(i), "name": f"Fixture {i}"} for i in range(1, 5)], 1)
            pending, review, ambiguous, accepted = [source_key(str(i)) for i in range(1, 5)]
            store.apply_classification([review], "unclassified", method="fixture", confidence=0)
            store.apply_classification([ambiguous, accepted], "film", method="fixture", confidence=1)
            store.set_match_state([ambiguous], "ambiguous")
            store.set_match_state([accepted], "matched-auto", tmdb_id=550, matcher_version=1)
            store.mark_stale_automatic_results()
            filters = {"review_scope": "leftovers", "review_view": "classification-review"}
            displayed = store.review_queue("classification-review", filters=filters)
            self.assertEqual([row["source_key"] for row in displayed["items"]], [review])
            for bulk in (False, True):
                selected = store.resolve_selection(mode="all-filtered", filters=filters, bulk=bulk)
                self.assertEqual(selected["source_keys"], [review])
            with self.assertRaisesRegex(ValueError, "no longer in the review queue"):
                store.resolve_selection(mode="explicit", selected_keys=[pending], filters=filters, bulk=True)
            uncertain = store.review_queue("needs-review", filters=filters)
            self.assertEqual([row["source_key"] for row in uncertain["items"]], [ambiguous])
            self.assertEqual(store.review_queue("classification-review")["total"], 2)

    def test_maintenance_unmatched_displays_and_selects_all_settled_leftovers(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = IPTVMovieStore(Path(temporary) / PROVIDER_A, PROVIDER_A)
            store.project_sources([{"item_id": str(i), "name": f"Fixture {i}"} for i in range(1, 8)], 1)
            unmatched, uncertain, unknown, pending, failed, locked, matched = [source_key(str(i)) for i in range(1, 8)]
            store.apply_classification([unmatched, uncertain, failed, locked, matched], "film", method="fixture", confidence=1)
            store.apply_classification([unknown], "unclassified", method="fixture", confidence=0)
            store.set_match_state([unmatched], "unmatched")
            store.set_match_state([uncertain], "ambiguous")
            store.set_match_state([failed], "error-terminal")
            store.set_match_state([locked], "unmatched", manual_lock=True)
            store.set_match_state([matched], "matched-auto", tmdb_id=550)
            expected = {unmatched, uncertain, unknown}
            filters = {"review_scope": "leftovers", "review_view": "unmatched"}
            review = store.review_queue("unmatched", filters=filters)
            self.assertEqual(review["total"], 3)
            self.assertEqual({row["source_key"] for row in review["items"]}, expected)
            for bulk in (False, True):
                resolved = store.resolve_selection(mode="all-filtered", filters=filters, bulk=bulk)
                self.assertEqual(set(resolved["source_keys"]), expected)
                resolved = store.resolve_selection(mode="explicit", selected_keys=list(expected), filters=filters, bulk=bulk)
                self.assertEqual(set(resolved["source_keys"]), expected)
            for key in (pending, failed, locked, matched):
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, "no longer in the review queue"):
                    store.resolve_selection(mode="explicit", selected_keys=[key], filters=filters, bulk=True)
            self.assertEqual(store.review_queue("unmatched")["total"], 2)

    def test_maintenance_explicit_selection_rejects_a_disappeared_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = IPTVMovieStore(Path(temporary) / PROVIDER_A, PROVIDER_A)
            row = {"item_id": "1", "name": "Fixture 1"}
            store.project_sources([row, {"item_id": "2", "name": "Fixture 2"}], 1)
            kept, gone = source_key("1"), source_key("2")
            store.set_match_state([kept, gone], "unmatched")
            store.project_sources([row], 2)
            filters = {"review_scope": "leftovers", "review_view": "unmatched"}
            for bulk in (False, True):
                with self.subTest(bulk=bulk), self.assertRaisesRegex(ValueError, "no longer in the review queue"):
                    store.resolve_selection(mode="explicit", selected_keys=[f"source:{kept}", gone], filters=filters, bulk=bulk)

    def test_movie_store_is_lazy_and_live_or_series_access_never_creates_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            settings = IPTVMetadataSettings(temporary)
            movie_service = IPTVMovieService(raw.root, PROVIDER_A, raw, settings)
            try:
                self.assertFalse(movie_service.database_path.exists())
                self.assertEqual(raw.list_items("live")["total"], 1)
                self.assertEqual(raw.list_items("series")["total"], 1)
                self.assertFalse(movie_service.database_path.exists())
                first = movie_service.list_movies()
                self.assertEqual(first["total"], 0)
                self.assertIn(first["projection"]["state"], {"not-started", "running"})
                movie_service.start_projection(wait=True)
                self.assertEqual(movie_service.list_movies()["total"], 1)
                self.assertTrue(movie_service.database_path.exists())
            finally:
                raw.close()

    def test_raw_projection_uses_bounded_batches(self):
        rows = [
            {"stream_id": str(index), "category_id": "movies-a", "name": f"Movie {index}"}
            for index in range(1, 8)
        ]
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A, movie_rows=rows)
            settings = IPTVMetadataSettings(temporary)
            movie_service = IPTVMovieService(raw.root, PROVIDER_A, raw, settings)
            movie_service.PROJECTION_BATCH_SIZE = 2
            store = movie_service.store
            try:
                with patch.object(store, "project_source_batch", wraps=store.project_source_batch) as batches:
                    movie_service.start_projection(wait=True)
                    result = movie_service.list_movies(page_size=20)
                self.assertEqual(result["total"], 7)
                self.assertEqual([len(call.args[0]) for call in batches.call_args_list], [2, 2, 2, 1])
            finally:
                raw.close()

    def test_same_generation_projection_completion_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = IPTVMovieStore(Path(temporary) / PROVIDER_A, PROVIDER_A)
            store.begin_projection(7)
            store.project_source_batch([{"item_id": "1", "name": "Race-safe Movie"}], 7)
            store.finish_projection(7)
            store.finish_projection(7)
            self.assertEqual(store.source_generation(), 7)

    def test_projection_derives_provider_year_from_spaced_title_suffix(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = IPTVMovieStore(Path(temporary) / PROVIDER_A, PROVIDER_A)
            store.project_sources([{"item_id": "1", "name": "ssss ( 2026 )"}], 1)
            card = store.list_movies()["items"][0]
            self.assertEqual(card["provider_year"], 2026)

    def test_projection_reopens_changed_unresolved_evidence_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = IPTVMovieStore(Path(temporary) / PROVIDER_A, PROVIDER_A)
            rows = [{"item_id": str(i), "name": f"Fixture Film {i}", "year": 2024,
                     "playlist_name": "Films"} for i in range(1, 5)]
            rows[0].update(tmdb_id=123, raw={"tmdb": "123"})
            keys = [source_key(str(i)) for i in range(1, 5)]
            store.project_sources(rows, 1)
            store.apply_classification(keys, "film", method="fixture", confidence=1)
            token = store.prepare_enrichment(consent=True)
            while claimed := store.claim_next(token):
                store.finish_job(claimed)
            store.set_match_state(keys[:2], "unmatched")
            store.set_match_state([keys[2]], "matched-auto", tmdb_id=550)
            store.set_match_state([keys[3]], "unmatched", manual_lock=True)
            store.update_provider_detail(keys[0], {"name": "Old cached detail", "year": 2024, "tmdb_id": 991})

            # A different provider generation and artwork alone carry the same matching evidence.
            store.project_sources([{**row, "image_url": "https://fixture.invalid/poster.jpg"} for row in rows], 2)
            self.assertEqual(store.stage_enrichment_batch(), 0)
            self.assertEqual(store.source(keys[0])["detail_title"], "Old cached detail")

            store.project_sources([{**row, "name": row["name"] + " corrected"} if i != 1 else row
                                   for i, row in enumerate(rows)], 3)
            self.assertEqual(store.source(keys[0])["classification_status"], "pending")
            self.assertEqual(store.source(keys[0])["detail_title"], "")
            self.assertEqual(store.source(keys[0])["provider_tmdb_id"], 123)
            store.apply_classification([keys[0]], "film", method="fixture", confidence=1)
            self.assertEqual(store.stage_enrichment_batch(), 1)
            with store.connection() as connection:
                matches = [tuple(row) for row in connection.execute(
                    "SELECT state,tmdb_id,manual_lock FROM source_matches ORDER BY rowid")]
            self.assertEqual(matches, [("unprocessed", None, 0), ("unmatched", None, 0),
                                       ("matched-auto", 550, 0), ("unmatched", None, 1)])

    def test_provider_path_confinement_and_independent_same_tmdb_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / "iptv" / "providers"
            first = IPTVMovieStore(base / PROVIDER_A, PROVIDER_A)
            second = IPTVMovieStore(base / PROVIDER_B, PROVIDER_B)
            with self.assertRaisesRegex(ValueError, "provider root"):
                IPTVMovieStore(base / PROVIDER_A, PROVIDER_B)
            first.project_sources([{"item_id": "1", "name": "First Movie", "year": 2024}], 1)
            second.project_sources([{"item_id": "1", "name": "Second Movie", "year": 2024}], 1)
            first.apply_classification([source_key("1")], "film", method="test-fixture", confidence=1)
            second.apply_classification([source_key("1")], "film", method="test-fixture", confidence=1)
            snapshot = normalize_tmdb_movie(tmdb_payload(550, "Shared Identity", 2024))
            first.apply_match(f"source:{source_key('1')}", snapshot)
            second.apply_match(f"source:{source_key('1')}", snapshot)

            self.assertEqual(first.list_movies({"view": "cp"})["items"][0]["movie_key"], "tmdb:550")
            self.assertEqual(second.list_movies({"view": "cp"})["items"][0]["movie_key"], "tmdb:550")
            self.assertNotEqual(first.database_path, second.database_path)
            self.assertEqual(first.integrity(), "ok")
            self.assertEqual(second.integrity(), "ok")

    def test_arabic_localization_repair_preserves_the_accepted_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            settings = IPTVMetadataSettings(temporary)
            movie_service = IPTVMovieService(raw.root, PROVIDER_A, raw, settings)
            try:
                movie_service.start_projection(wait=True)
                base_payload = tmdb_payload(550, "Arabic transliteration", 2024)
                base_payload.update({
                    "original_language": "ar",
                    "original_title": "\u0639\u0646\u0648\u0627\u0646 \u0639\u0631\u0628\u064a",
                    "overview": "English fallback plot",
                    "credits": {
                        "crew": [{"id": 1, "name": "English Director", "job": "Director", "profile_path": "/director.jpg"}],
                        "cast": [{"id": 3, "name": "English Actor", "character": "Lead", "profile_path": "/actor.jpg"}],
                    },
                })
                movie_service.store.apply_match(
                    f"source:{source_key('10')}",
                    normalize_tmdb_movie(base_payload),
                    manual=True,
                )
                localized_payload = {
                    **base_payload,
                    "title": "\u0639\u0646\u0648\u0627\u0646 \u0639\u0631\u0628\u064a",
                    "overview": "",
                    "credits": {
                        "crew": [{"id": 1, "name": "\u0645\u062e\u0631\u062c \u0639\u0631\u0628\u064a", "job": "Director"}],
                        "cast": [{"id": 3, "name": "\u0645\u0645\u062b\u0644 \u0639\u0631\u0628\u064a", "character": "\u0627\u0644\u0628\u0637\u0644"}],
                    },
                }
                client = FakeTMDBClient(movies={550: localized_payload})
                movie_service.tmdb_client_factory = lambda: client
                transient = movie_service.localization("tmdb:550", "ar-SA")
                self.assertEqual(transient["directors"][0]["name"], "\u0645\u062e\u0631\u062c \u0639\u0631\u0628\u064a")
                self.assertTrue(transient["directors"][0]["profile_url"].endswith("/director.jpg"))
                self.assertEqual(transient["cast"][0]["name"], "\u0645\u0645\u062b\u0644 \u0639\u0631\u0628\u064a")
                self.assertTrue(transient["cast"][0]["profile_url"].endswith("/actor.jpg"))
                self.assertEqual(movie_service.store.missing_arabic_localizations(), [550])
                result = movie_service.repair_missing_arabic_localizations(
                    tmdb_client=client
                )

                self.assertEqual(result, {"requested": 1, "saved": [550], "failed": []})
                self.assertEqual(movie_service.store.missing_arabic_localizations(), [])
                detail = movie_service.movie("tmdb:550")
                self.assertEqual(detail["name"], "\u0639\u0646\u0648\u0627\u0646 \u0639\u0631\u0628\u064a")
                self.assertEqual(detail["plot"], "English fallback plot")
                with movie_service.store.connection() as connection:
                    match = connection.execute(
                        "SELECT state,manual_lock,tmdb_id FROM source_matches WHERE source_key=?",
                        (source_key("10"),),
                    ).fetchone()
                self.assertEqual(tuple(match), ("matched-manual", 1, 550))
            finally:
                raw.close()

    def test_raw_fallback_grouping_filters_paging_and_list_membership_survive_merge(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "iptv" / "providers" / PROVIDER_A
            store = IPTVMovieStore(root, PROVIDER_A)
            rows = [
                {"item_id": "1", "category_id": "a", "playlist_name": "Playlist A", "name": "Same Movie (2024) 1080p", "year": 2024, "position": 1},
                {"item_id": "2", "category_id": "b", "playlist_name": "Playlist B", "name": "Same Movie (2024) 4K", "year": 2024, "position": 2},
                {"item_id": "3", "category_id": "a", "playlist_name": "Playlist A", "name": "Other Movie", "position": 3},
            ]
            store.project_sources(rows, 1, memberships=[
                {"list_id": "list-a", "source_id": "1", "position": 2, "added_at": 20},
                {"list_id": "list-a", "source_id": "2", "position": 1, "added_at": 10},
            ])
            fallback = store.list_movies({"playlist_id": "a"}, page=1, page_size=1)
            self.assertEqual(fallback["total"], 2)
            self.assertEqual(len(fallback["items"]), 1)
            self.assertFalse(fallback["items"][0]["matched"])

            snapshot = normalize_tmdb_movie(tmdb_payload(550, "Same Movie", 2024))
            store.apply_classification(
                [source_key("1"), source_key("2")],
                "film",
                method="test-fixture",
                confidence=1,
            )
            store.apply_match(f"source:{source_key('1')}", snapshot)
            store.apply_match(f"source:{source_key('2')}", snapshot)
            grouped = store.list_movies({"view": "cp", "list_id": "list-a", "genre_id": 18})

            self.assertEqual(grouped["total"], 1)
            self.assertEqual(grouped["items"][0]["source_count"], 2)
            self.assertEqual(grouped["items"][0]["movie_key"], "tmdb:550")
            with store.connection() as connection:
                membership = connection.execute(
                    "SELECT position,added_at FROM movie_list_memberships WHERE list_id='list-a'"
                ).fetchall()
            self.assertEqual([(row[0], row[1]) for row in membership], [(1, 10.0)])

            store.project_sources(rows[:1] + rows[2:], 2)
            retained = store.list_movies({"view": "cp", "list_id": "list-a"})
            self.assertEqual(retained["items"][0]["source_count"], 1)

    def test_manual_match_lock_correction_and_remove_are_transactional(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = IPTVMovieStore(Path(temporary) / PROVIDER_A, PROVIDER_A)
            store.project_sources([{"item_id": "1", "name": "Manual Movie"}], 1)
            first = normalize_tmdb_movie(tmdb_payload(100, "First Match", 2020))
            second = normalize_tmdb_movie(tmdb_payload(200, "Corrected Match", 2021))
            key = f"source:{source_key('1')}"
            matched = store.apply_match(key, first, manual=True)
            corrected = store.apply_match(matched, second, manual=True)
            with store.connection() as connection:
                row = connection.execute("SELECT state,tmdb_id,manual_lock FROM source_matches").fetchone()
            self.assertEqual((row[0], row[1], row[2]), ("matched-manual", 200, 1))
            store.remove_match(corrected)
            with store.connection() as connection:
                row = connection.execute("SELECT state,tmdb_id,manual_lock FROM source_matches").fetchone()
            self.assertEqual((row[0], row[1], row[2]), ("unmatched", None, 1))
            store.remove_match(key, reprocess=True)
            with store.connection() as connection:
                row = connection.execute("SELECT state,manual_lock FROM source_matches").fetchone()
            self.assertEqual((row[0], row[1]), ("unprocessed", 0))


class IPTVMatchEngineTests(unittest.TestCase):
    def test_missing_provider_id_lookup_falls_back_to_title_year(self):
        candidate = tmdb_payload(550, "Fixture Movie", 2024)
        for search_results, expected in (([candidate], "matched-auto"), ([], "unmatched")):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                raw = create_raw_service(temporary, PROVIDER_A)
                service = IPTVMovieService(raw.root, PROVIDER_A, raw, IPTVMetadataSettings(temporary))
                client = FakeTMDBClient({550: candidate}, search_results=search_results)
                fetch = client.movie

                def movie(tmdb_id, *args, **kwargs):
                    if tmdb_id == 999:
                        raise IPTVTMDBError("Missing movie", status=404)
                    return fetch(tmdb_id, *args, **kwargs)

                try:
                    service.ensure_projected()
                    key = source_key("10")
                    service.store.apply_classification([key], "film", method="fixture", confidence=1)
                    with patch.object(raw, "enrichment_movie_detail", return_value={"tmdb_id": 999}), \
                            patch.object(client, "movie", side_effect=movie):
                        self.assertEqual(service.enrich_source(key, tmdb_client=client), expected)
                    with service.store.connection() as connection:
                        row = connection.execute("SELECT state,method,evidence_json FROM source_matches WHERE source_key=?", (key,)).fetchone()
                    self.assertEqual((row["state"], row["method"]), (expected, "strict-title-year"))
                    self.assertEqual(json.loads(row["evidence_json"])["provider_id_validation"]["lookup"], "not-found")
                finally:
                    raw.close()

    def test_title_candidate_details_distinguish_404_from_technical_errors(self):
        candidate = tmdb_payload(550, "Fixture Movie", 2024)
        for status in (404, 503):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temporary:
                raw = create_raw_service(temporary, PROVIDER_A)
                service = IPTVMovieService(raw.root, PROVIDER_A, raw, IPTVMetadataSettings(temporary))
                client = FakeTMDBClient({550: candidate}, search_results=[candidate])
                try:
                    service.ensure_projected()
                    key = source_key("10")
                    service.store.apply_classification([key], "film", method="fixture", confidence=1)
                    with patch.object(raw, "enrichment_movie_detail", return_value={}), \
                            patch.object(client, "normalized_movie", side_effect=IPTVTMDBError("Fixture error", status=status)):
                        if status == 404:
                            self.assertEqual(service.enrich_source(key, tmdb_client=client), "unmatched")
                        else:
                            with self.assertRaises(IPTVTMDBError) as failure:
                                service.enrich_source(key, tmdb_client=client)
                            self.assertEqual(failure.exception.status, 503)
                finally:
                    raw.close()

    def test_disappeared_search_result_does_not_block_valid_title_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, IPTVMetadataSettings(temporary))
            valid, missing = tmdb_payload(550, "Fixture Movie", 2024), tmdb_payload(999, "Fixture Movie", 2024)
            client = FakeTMDBClient({550: valid}, search_results=[missing, valid])

            def movie(tmdb_id, **_options):
                if tmdb_id == 999:
                    raise IPTVTMDBError("Missing search result", status=404)
                return valid

            try:
                service.ensure_projected()
                key = source_key("10")
                service.store.apply_classification([key], "film", method="fixture", confidence=1)
                with patch.object(raw, "enrichment_movie_detail", return_value={}), patch.object(client, "movie", side_effect=movie):
                    self.assertEqual(service.enrich_source(key, tmdb_client=client), "matched-auto")
                self.assertEqual(service.list_movies({"view": "cp"})["items"][0]["movie_key"], "tmdb:550")
            finally:
                raw.close()

    def test_blank_detail_id_uses_current_listing_id_instead_of_old_detail(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A, movie_rows=[
                {"stream_id": "10", "name": "Fixture Movie (2024)", "category_id": "movies-a", "tmdb": "550"},
            ])
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, IPTVMetadataSettings(temporary))
            client = FakeTMDBClient({550: tmdb_payload(550, "Fixture Movie", 2024)}, search_results=[])
            try:
                service.ensure_projected()
                key = source_key("10")
                service.store.apply_classification([key], "film", method="fixture", confidence=1)
                service.store.update_provider_detail(key, {"tmdb_id": 999})
                with patch.object(raw, "client") as provider, patch.object(client, "movie", wraps=client.movie) as lookup:
                    provider.return_value.movie_info.return_value = {"info": {"tmdb_id": " ", "tmdb": "0"}}
                    self.assertEqual(service.enrich_source(key, tmdb_client=client), "matched-auto")
                    lookup.assert_called_once_with(550)
            finally:
                raw.close()

    def test_provider_id_validation_strict_matching_and_credible_rival_rejection(self):
        candidate = tmdb_payload(550, "The Exact Movie", 2024)
        valid, score = provider_id_matches("The Exact Movie (2024)", 2024, candidate)
        invalid, _ = provider_id_matches("A Different Movie (2024)", 2024, candidate)
        accepted = choose_automatic_match("The Exact Movie (2024)", 2024, [candidate])
        rival = tmdb_payload(551, "The Exact Movie", 2024)
        ambiguous = choose_automatic_match("The Exact Movie (2024)", 2024, [candidate, rival])

        self.assertTrue(valid)
        self.assertGreaterEqual(score, 94)
        self.assertFalse(invalid)
        self.assertEqual(accepted["state"], "matched-auto")
        self.assertEqual(ambiguous["state"], "ambiguous")

    def test_spaced_year_alternative_titles_and_provider_translation_suffixes_are_validated(self):
        self.assertEqual(clean_provider_title("ssss ( 2026 ) 4K"), "ssss")
        alternative = tmdb_payload(700, "International Title", 2026)
        alternative["alternative_titles"] = {
            "titles": [{"iso_3166_1": "US", "title": "ssss", "type": ""}]
        }
        translated = tmdb_payload(701, "A Loud House Christmas: The Movie", 2025)

        alternative_valid, alternative_score = provider_id_matches(
            "ssss ( 2026 )", 2026, alternative
        )
        translated_valid, translated_score = provider_id_matches(
            "A Loud House Christmas: The Movie (2025) مدبلج عربي", 2025, translated
        )
        unsafe_prefix, _ = provider_id_matches(
            "A Loud House Christmas: The Movie Part Two (2025)", 2025, translated
        )

        self.assertTrue(alternative_valid)
        self.assertGreaterEqual(alternative_score, 94)
        self.assertTrue(translated_valid)
        self.assertGreaterEqual(translated_score, 94)
        self.assertFalse(unsafe_prefix)

    def test_manual_search_separates_title_year_before_tmdb_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(
                temporary,
                PROVIDER_A,
                movie_rows=[{"stream_id": "10", "category_id": "movies-a", "name": "ssss ( 2026 )"}],
            )
            settings = IPTVMetadataSettings(temporary)
            captured = {}

            class CapturingClient(FakeTMDBClient):
                def search_movies(self, title, year=0, page=1):
                    captured.update({"title": title, "year": year, "page": page})
                    return [tmdb_payload(700, "ssss", 2026)]

            service = IPTVMovieService(
                raw.root, PROVIDER_A, raw, settings,
                tmdb_client_factory=lambda: CapturingClient(),
            )
            try:
                service.start_projection(wait=True)
                card = service.list_movies({"view": "cp"})["items"][0]
                result = service.manual_search(card["movie_key"], "ssss ( 2026 )", "")
                self.assertEqual(captured, {"title": "ssss", "year": 2026, "page": 1})
                self.assertEqual(result["year"], 2026)
            finally:
                raw.close()

    def test_automatic_enrichment_prefers_valid_provider_id_and_preserves_raw_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            settings = IPTVMetadataSettings(temporary)
            settings.save("fixture-token", "bearer")
            client = FakeTMDBClient({550: tmdb_payload(550, "Fixture Movie", 2024)})
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, settings, tmdb_client_factory=lambda: client)
            def detail(kind, item_id):
                value = raw.store.get_item(kind, item_id, provider_key=raw.provider_key())
                value.update({"name": "Fixture Movie", "year": 2024, "tmdb_id": 550})
                return value

            try:
                service.ensure_projected()
                service.store.apply_classification(
                    [source_key("10")], "film", method="test-fixture", confidence=1
                )
                with patch.object(raw, "enrichment_movie_detail", side_effect=lambda item_id: detail("movie", item_id)):
                    state = service.enrich_source(source_key("10"))
                card = service.list_movies({"view": "cp"})["items"][0]
                self.assertEqual(state, "matched-auto")
                self.assertEqual(card["movie_key"], "tmdb:550")
                self.assertEqual(card["item_id"], "10")
                self.assertEqual(card["title"], "Fixture Movie")
            finally:
                raw.close()

    def test_full_provider_release_date_is_normalized_before_recording_match_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            settings = IPTVMetadataSettings(temporary)
            settings.save("fixture-token", "bearer")
            candidate = tmdb_payload(550, "Fixture Movie", 2024)
            candidate["genres"] *= 2
            client = FakeTMDBClient(search_results=[candidate])
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, settings)
            detail = raw.store.get_item("movie", "10", provider_key=raw.provider_key())
            detail.update({"name": "Fixture Movie", "year": "2024-02-03", "tmdb_id": " "})
            try:
                service.ensure_projected()
                service.store.apply_classification(
                    [source_key("10")], "film", method="test-fixture", confidence=1
                )
                with patch.object(raw, "enrichment_movie_detail", return_value=detail):
                    self.assertEqual(
                        service.enrich_source(source_key("10"), tmdb_client=client),
                        "matched-auto",
                    )
                with service.store.connection() as connection:
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM movie_genres").fetchone()[0], 1)
                    evidence = json.loads(
                        connection.execute("SELECT evidence_json FROM source_matches").fetchone()[0]
                    )
                self.assertEqual(evidence["fallback_search"]["parsed"]["year"], 2024)
            finally:
                raw.close()


class IPTVTMDBClientTests(unittest.TestCase):
    def test_bearer_validation_keeps_secret_out_of_url_and_public_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            settings = IPTVMetadataSettings(temporary)
            settings.save("fixture-bearer-secret", "bearer")
            captured = {}

            def open_url(request, timeout=0):
                captured["url"] = request.full_url
                captured["authorization"] = request.headers.get("Authorization")
                captured["timeout"] = timeout
                return FakeHTTPResponse({"images": {"base_url": "https://images.example"}})

            client = IPTVTMDBClient(settings, open_url=open_url)
            self.assertTrue(client.validate())
            self.assertNotIn("fixture-bearer-secret", captured["url"])
            self.assertEqual(captured["authorization"], "Bearer fixture-bearer-secret")

    def test_401_429_timeout_and_5xx_are_typed_without_secret_exposure(self):
        with tempfile.TemporaryDirectory() as temporary:
            settings = IPTVMetadataSettings(temporary)
            settings.save("fixture-api-secret", "api_key")

            def failure(status, headers=None):
                def open_url(request, timeout=0):
                    raise urllib.error.HTTPError(request.full_url, status, "failed", headers or {}, None)
                return open_url

            for status, retryable in ((401, False), (429, True), (500, True)):
                client = IPTVTMDBClient(settings, open_url=failure(status, {"Retry-After": "3"}))
                with self.assertRaises(IPTVTMDBError) as raised:
                    client.validate()
                self.assertEqual(raised.exception.status, status)
                self.assertEqual(raised.exception.retryable, retryable)
                self.assertNotIn("fixture-api-secret", str(raised.exception))

            client = IPTVTMDBClient(settings, open_url=lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()))
            with self.assertRaises(IPTVTMDBError) as raised:
                client.validate()
            self.assertTrue(raised.exception.retryable)


class IPTVWorkerTests(unittest.TestCase):
    def test_continue_reclaims_scheduler_capacity_from_an_exited_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, IPTVMetadataSettings(temporary))
            try:
                with subprocess.Popen([sys.executable, "-B", "-c", "pass"],
                                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
                    process.wait(timeout=5)
                    service._scheduler_path.write_text(json.dumps({
                        "provider_id": PROVIDER_A, "pid": process.pid, "token": "old",
                    }), encoding="utf-8")
                    self.assertTrue(service._claim_global_capacity("new"))
                    self.assertEqual(json.loads(service._scheduler_path.read_text(encoding="utf-8"))["token"], "new")
            finally:
                service.close()
                raw.close()

    def test_enrichment_status_keeps_projection_and_counts_on_one_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, IPTVMetadataSettings(temporary))
            try:
                service.ensure_projected()
                store = service.store
                generation = store.source_generation()
                status_payload = store._worker_status_payload

                def publish(*args, **kwargs):
                    store.project_sources([{"item_id": "11", "name": "New Movie"},
                                           {"item_id": "12", "name": "Other Movie"}], generation + 1)
                    return status_payload(*args, **kwargs)

                with patch.object(store, "_worker_status_payload", side_effect=publish):
                    status = service.enrichment_status()
                self.assertEqual(status["sources"], 1)
                self.assertEqual(status["projection"]["published"], 1)
                self.assertEqual(status["projection"]["source_generation"], generation)
                self.assertEqual(service.enrichment_status()["automatic_remaining"], 2)
            finally:
                service.close()
                raw.close()

    def test_continue_waits_for_provider_sync_and_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, IPTVMetadataSettings(temporary))
            try:
                service.ensure_projected()
                store = service.store
                token = store.prepare_enrichment(consent=True)
                store.worker_finished("complete", token=token)
                with patch.dict(raw._sync_state, state="running"):
                    with self.assertRaisesRegex(RuntimeError, "Finish preparing provider movies"):
                        service.resume_enrichment()
                store.begin_projection(store.source_generation() + 1, total=2)
                with self.assertRaisesRegex(RuntimeError, "Finish preparing provider movies"):
                    service.resume_enrichment()
                self.assertEqual(store.current_worker_token(), token)
            finally:
                service.close()
                raw.close()

    def test_a_second_store_cannot_replace_a_live_worker_lease(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / PROVIDER_A
            first = IPTVMovieStore(root, PROVIDER_A)
            second = IPTVMovieStore(root, PROVIDER_A)
            token = first.schedule_enrichment(consent=True)
            with self.assertRaisesRegex(RuntimeError, "worker already owns this provider"):
                second.resume_worker()
            with self.assertRaisesRegex(RuntimeError, "worker already owns this provider"):
                second.schedule_enrichment(consent=True)
            self.assertEqual(first.current_worker_token(), token)

    def test_concurrent_continue_requests_share_one_worker_lease(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            settings = IPTVMetadataSettings(temporary)
            settings.save("fixture-token", "bearer")
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, settings)
            started = threading.Event()
            second_requested = threading.Event()
            release = threading.Event()
            duplicate_spawn = threading.Event()
            launches = []
            process = type("RunningWorker", (), {"poll": lambda self: None})()

            def spawn(token, **_options):
                launches.append(token)
                if len(launches) == 1:
                    started.set()
                    self.assertTrue(release.wait(5))
                else:
                    duplicate_spawn.set()
                service._processes[PROVIDER_A] = process

            def request_again():
                second_requested.set()
                return service.resume_enrichment()

            try:
                service.ensure_projected()
                token = service.store.prepare_enrichment(consent=True)
                service.store.worker_finished("complete", token=token)
                with patch.object(service, "_spawn_worker", side_effect=spawn), ThreadPoolExecutor(2) as executor:
                    first = executor.submit(service.resume_enrichment)
                    try:
                        self.assertTrue(started.wait(5))
                        second = executor.submit(request_again)
                        self.assertTrue(second_requested.wait(5))
                        self.assertFalse(duplicate_spawn.wait(.2))
                    finally:
                        release.set()
                    self.assertEqual(first.result(timeout=5)["state"], "starting")
                    self.assertEqual(second.result(timeout=5)["state"], "starting")
                self.assertEqual(launches, [service.store.current_worker_token()])
            finally:
                with service._process_lock:
                    service._processes.pop(PROVIDER_A, None)
                service.close()
                raw.close()

    def test_continue_records_a_launch_failure_and_remains_retryable(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            settings = IPTVMetadataSettings(temporary)
            settings.save("fixture-token", "bearer")
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, settings)
            try:
                service.ensure_projected()
                store = service.store
                token = store.prepare_enrichment(consent=True)
                store.worker_finished("complete", token=token)
                for method in ("process_factory", "_claim_global_capacity"):
                    with self.subTest(method=method), patch.object(service, method, side_effect=OSError("fixture launch failed")):
                        with self.assertRaisesRegex(RuntimeError, "fixture launch failed"):
                            service.resume_enrichment()
                    status = service.enrichment_status()
                    self.assertEqual(status["state"], "crashed")
                    self.assertIn("fixture launch failed", status["worker_error"])
                    self.assertEqual(status["automatic_remaining"], 1)
            finally:
                service.close()
                raw.close()

    def test_continue_reports_a_worker_that_exits_before_starting(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, IPTVMetadataSettings(temporary))
            try:
                service.ensure_projected()
                token = service.store.prepare_enrichment(consent=True)
                process = type("ExitedWorker", (), {"wait": lambda self: 7, "poll": lambda self: 7})()
                service._monitor_worker(process, token)
                status = service.enrichment_status()
                self.assertEqual(status["state"], "crashed")
                self.assertIn("exit code 7", status["worker_error"])
            finally:
                service.close()
                raw.close()

    def test_continue_after_projection_reopens_a_full_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, IPTVMetadataSettings(temporary),
                                       tmdb_client_factory=lambda: FakeTMDBClient(search_results=[]))
            try:
                service.ensure_projected()
                store = service.store
                old_key = source_key("10")
                store.apply_classification([old_key], "film", method="fixture", confidence=1)
                store.set_match_state([old_key], "unmatched")
                token = store.prepare_enrichment(consent=True, diagnostic_limit=1)
                store.worker_finished("complete", token=token)
                store.project_sources([
                    {"item_id": "10", "name": "Fixture Movie (2024) 1080p", "playlist_id": "movies-a",
                     "playlist_name": "Exact Provider Playlist", "year": 2024},
                    {"item_id": "11", "name": "New Movie (2024)", "playlist_name": "Films"},
                    {"item_id": "12", "name": "Other Movie (2024)", "playlist_name": "Films"},
                ], store.source_generation() + 1)
                self.assertEqual(store.worker_control_status()["automatic_remaining"], 2)
                token = store.resume_worker()
                limit = store.worker_control_status()["diagnostic_limit"]
                self.assertEqual(limit, 0)
                with patch.object(raw, "enrichment_movie_detail", return_value={}) as detail:
                    self.assertEqual(run_worker(service, max_jobs=limit, lease_token=token), "complete")
                self.assertEqual([call.args[0] for call in detail.call_args_list], ["11", "12"])
                self.assertEqual(store.worker_control_status()["automatic_remaining"], 0)
                self.assertEqual(store.worker_control_status()["matches"]["unmatched"], 3)
            finally:
                service.close()
                raw.close()

    def test_repeated_start_cannot_replace_a_live_or_exiting_worker_lease(self):
        class ProcessFixture:
            return_code = None

            def poll(self):
                return self.return_code

        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            settings = IPTVMetadataSettings(temporary)
            settings.save("fixture-token", "bearer")
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, settings)
            process = ProcessFixture()
            try:
                service.ensure_projected()
                first_token = service.store.prepare_enrichment(consent=True)
                service.store.worker_started(12345, first_token)
                with service._process_lock:
                    service._processes[PROVIDER_A] = process

                repeated = service.start_enrichment(consent=True)
                self.assertEqual(repeated["state"], "running")
                self.assertEqual(service.store.current_worker_token(), first_token)

                service.store.cancel_enrichment()
                with self.assertRaisesRegex(RuntimeError, "still shutting down"):
                    service.start_enrichment(consent=True)
                self.assertEqual(service.store.current_worker_token(), first_token)
            finally:
                process.return_code = 0
                with service._process_lock:
                    service._processes.pop(PROVIDER_A, None)
                service.close()
                raw.close()

    def test_worker_has_a_hard_source_budget_and_does_not_requeue_uncertain_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            rows = [
                {"stream_id": str(index), "category_id": "movies-a", "name": f"Movie {index}"}
                for index in range(1, 5)
            ]
            raw = create_raw_service(temporary, PROVIDER_A, movie_rows=rows)
            settings = IPTVMetadataSettings(temporary)
            settings.save("fixture-token", "bearer")
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, settings)
            try:
                service.ensure_projected()
                service.store.apply_classification(
                    [source_key(str(index)) for index in range(1, 5)],
                    "film",
                    method="test-fixture",
                    confidence=1,
                )
                service.store.prepare_enrichment(consent=True, diagnostic_limit=2)
                with patch.object(service, "enrich_source", return_value="unmatched") as enrich:
                    self.assertEqual(run_worker(service, max_jobs=2), "paused")
                self.assertEqual(enrich.call_count, 2)
                self.assertEqual(service.enrichment_status()["queue"]["pending"], 2)

                with service.store.connection(immediate=True) as connection:
                    connection.execute("UPDATE source_matches SET state='ambiguous'")
                    connection.execute("DELETE FROM enrichment_queue")
                service.store.prepare_enrichment(consent=True)
                with service.store.connection() as connection:
                    self.assertEqual(
                        connection.execute("SELECT COUNT(*) FROM enrichment_queue").fetchone()[0],
                        0,
                    )
            finally:
                raw.close()

    def test_provider_refresh_supersedes_an_in_flight_enrichment_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            settings = IPTVMetadataSettings(temporary)
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, settings,
                                       tmdb_client_factory=lambda: FakeTMDBClient(search_results=[]))
            try:
                service.ensure_projected()
                store = service.store
                key = source_key("10")
                store.apply_classification([key], "film", method="test-fixture", confidence=1)
                store.prepare_enrichment(consent=True)

                def refresh_during_detail(_source_id):
                    store.project_sources([{"item_id": "10", "name": "Corrected Movie (2024)",
                                            "playlist_name": "Films"}], store.source_generation() + 1)
                    return {"name": "Outdated Movie (2024)", "year": 2024}

                with patch.object(raw, "enrichment_movie_detail", side_effect=refresh_during_detail):
                    self.assertEqual(run_worker(service, max_jobs=1), "paused")
                source = store.source(key)
                self.assertEqual(source["provider_title"], "Corrected Movie (2024)")
                self.assertEqual(source["detail_title"], "")
                self.assertEqual(source["classification_status"], "pending")
                with store.connection() as connection:
                    self.assertEqual(connection.execute("SELECT state FROM source_matches").fetchone()[0], "unprocessed")
                    self.assertEqual(connection.execute("SELECT status FROM enrichment_queue").fetchone()[0], "cancelled")

                store.apply_classification([key], "film", method="test-fixture", confidence=1)
                store.worker_command("run")
                with patch.object(raw, "enrichment_movie_detail", return_value={}):
                    self.assertEqual(run_worker(service), "complete")
                with store.connection() as connection:
                    self.assertEqual(connection.execute("SELECT state FROM source_matches").fetchone()[0], "unmatched")
                    self.assertEqual(connection.execute("SELECT attempts FROM enrichment_queue").fetchone()[0], 1)
            finally:
                raw.close()

    def test_provider_refresh_preserves_new_classification_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, IPTVMetadataSettings(temporary))
            try:
                service.ensure_projected()
                store = service.store

                def refresh_during_classification(*_args, **_kwargs):
                    store.project_sources([{"item_id": "10", "name": "Corrected Movie (2024)",
                                            "playlist_name": "Films"}], store.source_generation() + 1)
                    return {"category": "sports", "confidence": 1}

                with patch("services.iptv_movie_service.classify_source", side_effect=refresh_during_classification):
                    service.classify_catalog_batch()
                self.assertEqual(store.source(source_key("10"))["classification_status"], "pending")
            finally:
                raw.close()

    def test_worker_pause_resume_cancel_and_crash_recovery_state_are_provider_local(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            settings = IPTVMetadataSettings(temporary)
            settings.save("fixture-token", "bearer")
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, settings, tmdb_client_factory=lambda: FakeTMDBClient())
            try:
                service.ensure_projected()
                service.store.prepare_enrichment(consent=True)
                service.store.worker_command("pause")
                self.assertEqual(run_worker(service), "paused")
                service.store.worker_command("run")
                with patch.object(service, "enrich_source", return_value="unmatched"):
                    self.assertEqual(run_worker(service, max_jobs=1), "paused")
                service.store.worker_command("cancel")
                self.assertEqual(service.enrichment_status()["state"], "cancelled")
                service.store.prepare_enrichment(consent=True)
                service.store.worker_started(999999)
                with service.store.connection(immediate=True) as connection:
                    connection.execute("UPDATE worker_lease SET lease_expires_at=0")
                recovered = service.enrichment_status()
                self.assertEqual(recovered["state"], "awaiting-continuation")
                self.assertTrue(recovered["restart_confirmation_required"])
            finally:
                raw.close()

    def test_inactive_cancel_finishes_immediately_and_preserves_pending_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = create_raw_service(temporary, PROVIDER_A)
            settings = IPTVMetadataSettings(temporary)
            settings.save("fixture-token", "bearer")
            service = IPTVMovieService(raw.root, PROVIDER_A, raw, settings)
            try:
                service.ensure_projected()
                service.store.apply_classification(
                    [source_key("10")], "film", method="test-fixture", confidence=1
                )
                service.store.prepare_enrichment(consent=True)
                service.store.worker_finished("paused")
                cancelled = service.cancel_enrichment()
                self.assertEqual(cancelled["state"], "cancelled")
                self.assertEqual(cancelled["command"], "idle")
                self.assertEqual(cancelled["queue"]["cancelled"], 0)
                self.assertEqual(cancelled["queue"]["pending"], 1)

                service.store.prepare_enrichment(consent=True)
                with service.store.connection() as connection:
                    queue_state = connection.execute(
                        "SELECT status FROM enrichment_queue"
                    ).fetchone()[0]
                self.assertEqual(queue_state, "pending")

                service.store.worker_command("cancel")
                self.assertEqual(service.enrichment_status()["state"], "cancelled")
            finally:
                raw.close()


class IPTVMovieRouteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.manager = IPTVProviderManager(self.temporary.name, migrate_legacy=False)
        created = self.manager.create_provider(
            "Fixture Provider", "https://provider.example", "fixture-user", "fixture-password"
        )
        self.provider_id = created["provider_id"]
        self.raw = self.manager.service(self.provider_id)
        from tests.iptv_movie_fixtures import provider_catalog
        self.raw.store.replace_catalog(provider_catalog())
        app = Flask(__name__)
        register_iptv_routes(app, lambda: self.manager)
        self.client = app.test_client()

    def tearDown(self):
        self.manager.close()
        self.temporary.cleanup()

    def test_metadata_settings_api_is_redacted_and_validates_with_one_bounded_call(self):
        initial = self.client.get("/api/iptv/metadata/settings")
        saved = self.client.patch("/api/iptv/metadata/settings", json={
            "credential_type": "bearer", "credential": "fixture-route-secret"
        })
        with patch("services.iptv_routes.IPTVTMDBClient.validate", return_value=True) as validate:
            tested = self.client.post("/api/iptv/metadata/test")
        body = json.dumps([initial.get_json(), saved.get_json(), tested.get_json()])

        self.assertEqual(initial.get_json()["tmdb_configured"], False)
        self.assertEqual(saved.get_json()["tmdb_configured"], True)
        self.assertEqual(tested.get_json(), {"tmdb_configured": True, "valid": True})
        self.assertNotIn("fixture-route-secret", body)
        self.assertNotIn('"credential":', body)
        validate.assert_called_once_with()

    def test_movies_are_provider_scoped_lazy_and_raw_fallback_needs_no_tmdb(self):
        path = self.raw.root / "movies.sqlite"
        self.assertFalse(path.exists())
        self.assertEqual(self.client.get("/api/iptv/providers").status_code, 200)
        self.assertEqual(
            self.client.get(f"/api/iptv/providers/{self.provider_id}/items?kind=live").status_code,
            200,
        )
        self.assertEqual(
            self.client.get(f"/api/iptv/providers/{self.provider_id}/items?kind=series").status_code,
            200,
        )
        self.assertFalse(path.exists())

        response = self.client.get(
            f"/api/iptv/providers/{self.provider_id}/movies?playlist_id=movies-a&page=1&page_size=10"
        )
        payload = response.get_json()
        self.manager.movie_service(self.provider_id).start_projection(wait=True)
        payload = self.client.get(
            f"/api/iptv/providers/{self.provider_id}/movies?playlist_id=movies-a&page=1&page_size=10"
        ).get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["metadata_status"], "unprocessed")
        self.assertEqual(payload["items"][0]["playlist_name"], "Exact Provider Playlist")
        self.assertTrue(path.exists())
        self.assertEqual(
            self.client.get("/api/iptv/providers/not-a-provider/movies").status_code,
            404,
        )

    def test_startup_is_lazy_missing_tmdb_blocks_only_enrichment_and_provider_delete_is_confined(self):
        movie_path = self.raw.root / "movies.sqlite"
        self.assertEqual(self.manager._movie_services, {})
        self.assertFalse(movie_path.exists())
        self.assertEqual(
            self.client.post(
                f"/api/iptv/providers/{self.provider_id}/movies/enrichment/start"
            ).status_code,
            400,
        )
        fallback = self.client.get(
            f"/api/iptv/providers/{self.provider_id}/movies"
        ).get_json()
        self.manager.movie_service(self.provider_id).start_projection(wait=True)
        fallback = self.client.get(
            f"/api/iptv/providers/{self.provider_id}/movies"
        ).get_json()
        self.assertEqual(fallback["total"], 1)
        self.assertEqual(fallback["items"][0]["metadata_status"], "unprocessed")
        self.assertEqual(self.manager.movie_service(self.provider_id).enrichment_status()["state"], "idle")

        provider_root = self.raw.root
        outside = Path(self.temporary.name) / "outside-sentinel.txt"
        outside.write_text("preserve", encoding="utf-8")
        self.manager.remove_provider(self.provider_id, "Fixture Provider")
        self.assertFalse(provider_root.exists())
        self.assertEqual(outside.read_text(encoding="utf-8"), "preserve")

    def test_manual_match_favorite_and_custom_list_use_provider_local_owners(self):
        movie_service = self.manager.movie_service(self.provider_id)
        movie_service.tmdb_client_factory = lambda: FakeTMDBClient()
        movie_service.start_projection(wait=True)
        card = self.client.get(
            f"/api/iptv/providers/{self.provider_id}/movies"
        ).get_json()["items"][0]
        key = card["movie_key"]
        matched = self.client.post(
            f"/api/iptv/providers/{self.provider_id}/movies/{key}/match", json={"tmdb_id": 550}
        )
        matched_key = matched.get_json()["movie_key"]
        favorited = self.client.post(
            f"/api/iptv/providers/{self.provider_id}/movies/{matched_key}/favorite",
            json={"favorite": True},
        )
        custom = self.raw.create_list("Movie Picks")
        listed = self.client.post(
            f"/api/iptv/providers/{self.provider_id}/movies/{matched_key}/lists/{custom['list_id']}"
        )
        filtered = self.client.get(
            f"/api/iptv/providers/{self.provider_id}/movies?list_id={custom['list_id']}"
        ).get_json()

        self.assertEqual(matched.status_code, 200)
        self.assertTrue(favorited.get_json()["favorite"])
        self.assertTrue(listed.get_json()["included"])
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["items"][0]["source_count"], 1)
        self.assertEqual(self.raw.list_favorites(kind="movie")["total"], 1)


if __name__ == "__main__":
    unittest.main()
