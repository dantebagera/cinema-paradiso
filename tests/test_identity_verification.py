import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from services.identity_decision import (
    DECISION_ORIGIN_IDENTITY_AUDIT,
    DECISION_ORIGIN_USER_MANUAL,
    IDENTITY_AUDIT_RULE_VERSION,
)
from services.identity_verification import (
    build_identity_verification_audit,
    verify_catalog_identity,
)


def catalog_candidate(**overrides):
    record = {
        "path": "E:/Movies/It.Ends.2025.mkv",
        "filename": "It.Ends.2025.mkv",
        "parsed_title": "It Ends",
        "parsed_year": "2025",
        "identity_status": "accepted",
        "metadata_status": "accepted",
        "metadata_accepted": True,
        "identity_title": "It Ends",
        "identity_year": "2026",
        "identity_source": "manual_tmdb",
        "tmdb_id": "1422011",
        "imdb_id": "tt35519455",
        "manual_lock": True,
    }
    record.update(overrides.pop("raw_json", {}))
    candidate = {
        **record,
        "raw_json": record,
        "manual_json": {"accepted": True, "tmdb_id": "1422011"},
        "tmdb_json": {
            "tmdb_id": "1422011",
            "imdb_id": "tt35519455",
            "title": "It Ends",
            "year": "2026",
        },
        "plex_json": {"plex_title": "It Ends", "plex_year": "2025"},
    }
    candidate.update(overrides)
    return candidate


class CatalogIdentityVerificationTest(unittest.TestCase):
    def test_it_ends_is_verified_drift_not_conflict(self):
        result = verify_catalog_identity(catalog_candidate())

        self.assertEqual(result["classification"], "verified")
        self.assertTrue(result["metadata_drift"])
        self.assertEqual(result["drift_reasons"], ["plex_year_difference"])

    def test_provider_content_disagreement_requeues_wrong_same_title_identity(self):
        result = verify_catalog_identity(catalog_candidate(
            raw_json={
                "path": "E:/Movies/Splice.2009.mkv",
                "filename": "Splice.2009.mkv",
                "parsed_title": "Splice",
                "parsed_year": "2009",
                "identity_status": "accepted",
                "metadata_status": "accepted",
                "metadata_accepted": True,
                "identity_title": "SPLICE",
                "identity_year": "2009",
                "identity_source": "identity_audit",
                "tmdb_id": "1629337",
                "imdb_id": "",
                "manual_lock": False,
            },
            manual_json={},
            tmdb_json={
                "tmdb_id": "1629337",
                "title": "SPLICE",
                "year": "2009",
                "overview": "A detective investigates VHS tapes connected to missing persons.",
                "genres": ["Mystery"],
                "directors": [{"name": "Dylan MacGregor"}],
                "cast": [{"name": "Cole Weinmeyer"}],
            },
            plex_json={
                "plex_title": "Splice",
                "plex_year": "2009",
                "plex_summary": "Two rebellious scientists splice human and animal DNA to create a new organism.",
                "plex_genres": ["Science Fiction", "Horror"],
                "plex_directors": [{"name": "Vincenzo Natali"}],
                "plex_cast": [{"name": "Adrien Brody"}, {"name": "Sarah Polley"}],
            },
        ))

        self.assertEqual(result["classification"], "unverified")
        self.assertTrue(result["metadata_drift"])
        self.assertIn("provider_content_conflict", result["drift_reasons"])

    def test_title_and_year_drift_with_matching_ids_is_not_a_conflict(self):
        result = verify_catalog_identity(catalog_candidate(
            manual_json={},
            plex_json={
                "plex_title": "It Ends: The Highway",
                "plex_year": "2025",
                "tmdb_id": "1422011",
                "imdb_id": "tt35519455",
            },
        ))

        self.assertEqual(result["classification"], "verified")
        self.assertCountEqual(
            result["drift_reasons"],
            ["plex_title_difference", "plex_year_difference"],
        )

    def test_large_filename_year_difference_remains_provider_audit_drift(self):
        result = verify_catalog_identity(catalog_candidate(
            raw_json={"parsed_title": "It Ends", "parsed_year": "2020"},
            plex_json={
                "plex_title": "It Ends",
                "plex_year": "2026",
                "tmdb_id": "1422011",
            },
        ))

        self.assertEqual(result["classification"], "verified")
        self.assertTrue(result["metadata_drift"])
        self.assertIn("filename_year_difference", result["drift_reasons"])

    def test_conflicting_public_id_is_the_hard_conflict_boundary(self):
        result = verify_catalog_identity(catalog_candidate(
            plex_json={"plex_title": "It Ends", "plex_year": "2025", "tmdb_id": "999999"},
        ))

        self.assertEqual(result["classification"], "hard_conflict")
        self.assertIn("plex_tmdb_id_conflict", result["reasons"])

    def test_frailty_style_consensus_is_unverified_and_not_auto_changed(self):
        result = verify_catalog_identity(catalog_candidate(
            raw_json={
                "filename": "Frailty.2001.1080p.mkv",
                "parsed_title": "Frailty",
                "parsed_year": "2001",
                "identity_title": "Temptation's Hour",
                "identity_year": "2001",
                "tmdb_id": "1387467",
                "imdb_id": "tt0343073",
            },
            identity_title="Temptation's Hour",
            identity_year="2001",
            tmdb_id="1387467",
            imdb_id="tt0343073",
            manual_json={"accepted": True, "tmdb_id": "1387467", "imdb_id": "tt0343073"},
            tmdb_json={
                "title": "Temptation's Hour",
                "tmdb_id": "1387467",
                "imdb_id": "tt0343073",
                "alternative_titles": ["Frailty"],
                "alternative_titles_checked_at": 1,
            },
            plex_json={"plex_title": "Frailty", "plex_year": "2001"},
        ))

        self.assertEqual(result["classification"], "unverified")
        self.assertEqual(result["reasons"], ["independent_title_consensus_unresolved"])
        self.assertFalse(result["enrichment_needed"])

    def test_unrelated_accepted_title_stays_unverified_when_local_years_disagree(self):
        result = verify_catalog_identity(catalog_candidate(
            raw_json={
                "parsed_title": "Kill Bill The Whole Bloody Affair",
                "parsed_year": "2006",
                "identity_title": "The Lost Chapter: Yuki's Revenge",
                "identity_year": "2025",
                "tmdb_id": "1588237",
            },
            identity_title="The Lost Chapter: Yuki's Revenge",
            identity_year="2025",
            tmdb_id="1588237",
            imdb_id="tt39075285",
            manual_json={"accepted": True, "tmdb_id": "1588237", "imdb_id": "tt39075285"},
            tmdb_json={
                "tmdb_id": "1588237",
                "imdb_id": "tt39075285",
                "title": "The Lost Chapter: Yuki's Revenge",
                "year": "2025",
                "alternative_titles": [],
                "alternative_titles_checked_at": 1,
            },
            plex_json={"plex_title": "Kill Bill: The Whole Bloody Affair", "plex_year": "2025"},
        ))

        self.assertEqual(result["classification"], "unverified")
        self.assertEqual(result["reasons"], ["independent_title_consensus_unresolved"])

    def test_alias_only_verifies_consensus_with_compatible_provider_year(self):
        result = verify_catalog_identity(catalog_candidate(
            raw_json={
                "parsed_title": "The She-Butterfly",
                "parsed_year": "1973",
                "identity_title": "Leptirica",
                "identity_year": "1973",
                "tmdb_id": "220638",
            },
            identity_title="Leptirica",
            identity_year="1973",
            tmdb_id="220638",
            imdb_id="",
            manual_json={"accepted": True, "tmdb_id": "220638"},
            tmdb_json={
                "tmdb_id": "220638",
                "title": "Leptirica",
                "year": "1973",
                "alternative_titles": ["The She-Butterfly"],
                "alternative_titles_checked_at": 1,
            },
            plex_json={"plex_title": "The She-Butterfly", "plex_year": "1973"},
        ))

        self.assertEqual(result["classification"], "verified")
        self.assertIn("tmdb_alias_and_year_match_local_consensus", result["reasons"])

    def test_related_title_variants_do_not_become_identity_conflicts(self):
        cases = [
            ("Undisputed II: Last Man Standing", "Undisputed 2 Last Man Standing"),
            ("Burke & Hare", "Burke and Hare"),
            ("The Toxic Avenger Unrated", "The Toxic Avenger"),
            ("Cry_Wolf", "Cry Wolf"),
        ]
        for canonical, observed in cases:
            with self.subTest(canonical=canonical):
                result = verify_catalog_identity(catalog_candidate(
                    raw_json={"identity_title": canonical, "parsed_title": observed, "parsed_year": "2001"},
                    identity_title=canonical,
                    plex_json={"plex_title": observed, "plex_year": "2001"},
                ))
                self.assertEqual(result["classification"], "verified")

    def test_accepted_identity_without_stable_or_manual_evidence_is_unverified(self):
        result = verify_catalog_identity(catalog_candidate(
            raw_json={"identity_source": "legacy", "tmdb_id": "", "imdb_id": "", "manual_lock": False},
            tmdb_id="",
            imdb_id="",
            identity_source="legacy",
            manual_lock=False,
            manual_json={},
            tmdb_json={},
            plex_json={},
        ))

        self.assertEqual(result["classification"], "unverified")

    def test_stable_id_without_independent_evidence_waits_for_provider_audit(self):
        result = verify_catalog_identity(catalog_candidate(
            raw_json={
                "identity_source": "tmdb_snapshot",
                "decision_origin": DECISION_ORIGIN_IDENTITY_AUDIT,
                "manual_lock": False,
            },
            identity_source="tmdb_snapshot",
            manual_lock=False,
            manual_json={},
            plex_json={},
        ))

        self.assertEqual(result["classification"], "audit_pending")
        self.assertEqual(result["reasons"], ["accepted_identity_requires_provider_audit"])

    def test_legacy_bulk_manual_row_waits_for_current_provider_audit(self):
        result = verify_catalog_identity(catalog_candidate(
            raw_json={"identity_source": "manual_tmdb", "manual_lock": True},
            manual_json={"accepted": True, "tmdb_id": "1422011", "updated_at": 100.0},
            audit_fingerprint_json={
                "rule_version": IDENTITY_AUDIT_RULE_VERSION - 1,
                "provider_id": "1422011",
                "verified_at": 100.2,
            },
        ))

        self.assertEqual(result["decision_origin"], "legacy_identity_audit")
        self.assertEqual(result["classification"], "audit_pending")

    def test_refreshed_legacy_fingerprint_does_not_become_user_manual(self):
        result = verify_catalog_identity(catalog_candidate(
            raw_json={"identity_source": "manual_tmdb", "manual_lock": True},
            manual_json={"accepted": True, "tmdb_id": "1422011", "updated_at": 100.0},
            audit_fingerprint_json={
                "rule_version": IDENTITY_AUDIT_RULE_VERSION - 1,
                "provider_id": "1422011",
                "verified_at": 1000.0,
            },
        ))

        self.assertEqual(result["decision_origin"], "legacy_identity_audit")
        self.assertEqual(result["classification"], "audit_pending")

    def test_explicit_fingerprint_origin_survives_future_rule_versions(self):
        result = verify_catalog_identity(catalog_candidate(
            raw_json={"identity_source": "manual_tmdb", "manual_lock": True},
            manual_json={"accepted": True, "tmdb_id": "1422011", "updated_at": 100.0},
            audit_fingerprint_json={
                "rule_version": IDENTITY_AUDIT_RULE_VERSION,
                "provider_id": "1422011",
                "verified_at": 1000.0,
                "decision_origin": "legacy_identity_audit",
            },
        ))

        self.assertEqual(result["decision_origin"], "legacy_identity_audit")
        self.assertEqual(result["classification"], "verified")

    def test_current_provider_audit_verifies_legacy_bulk_decision(self):
        result = verify_catalog_identity(catalog_candidate(
            raw_json={"identity_source": "manual_tmdb", "manual_lock": True},
            manual_json={"accepted": True, "tmdb_id": "1422011", "updated_at": 100.0},
            audit_fingerprint_json={
                "rule_version": IDENTITY_AUDIT_RULE_VERSION,
                "provider_id": "1422011",
                "verified_at": 100.2,
            },
        ))

        self.assertEqual(result["classification"], "verified")
        self.assertIn("current_provider_audit", result["reasons"])

    def test_explicit_user_match_is_authoritative_without_provider_audit(self):
        result = verify_catalog_identity(catalog_candidate(
            raw_json={"decision_origin": DECISION_ORIGIN_USER_MANUAL},
            plex_json={},
        ))

        self.assertEqual(result["classification"], "verified")
        self.assertIn("explicit_user_acceptance", result["reasons"])

    def test_unaccepted_record_is_unmatched(self):
        result = verify_catalog_identity(catalog_candidate(
            raw_json={"identity_status": "review", "metadata_status": "review", "metadata_accepted": False},
            identity_status="review",
            metadata_status="review",
            metadata_accepted=False,
            manual_json={},
        ))

        self.assertEqual(result["classification"], "unmatched")

    def test_report_categories_cover_every_accepted_record_once(self):
        hard_conflict = catalog_candidate(path="E:/Movies/Conflict.mkv", plex_json={"tmdb_id": "999999"})
        unmatched = catalog_candidate(
            path="E:/Movies/Unknown.mkv",
            identity_status="unmatched",
            metadata_status="unmatched",
            metadata_accepted=False,
            manual_json={},
        )
        report = build_identity_verification_audit([catalog_candidate(), hard_conflict, unmatched], generation=12)

        summary = report["summary"]
        self.assertEqual(summary["total_files"], 3)
        self.assertEqual(summary["accepted"], 2)
        self.assertEqual(
            summary["verified"]
            + summary["unverified"]
            + summary["audit_pending"]
            + summary["hard_conflicts"],
            summary["accepted"],
        )
        self.assertEqual(summary["unmatched"], 1)
        self.assertFalse(report["mutates_metadata"])


class IdentityVerificationApiTest(unittest.TestCase):
    def setUp(self):
        self.original_user_data = app._user_data_dir
        self.original_tmdb_key = app._tmdb_key
        self.original_cache = dict(app._identity_verification_audit_cache)

    def tearDown(self):
        app._user_data_dir = self.original_user_data
        app._tmdb_key = self.original_tmdb_key
        app._identity_verification_audit_cache = self.original_cache

    @staticmethod
    def seed_candidate(store):
        path = "E:/Movies/The.She-Butterfly.1973.mkv"
        store.save_tmdb_metadata({
            "tmdb_id": "220638",
            "title": "Leptirica",
            "year": "1973",
            "imdb_id": "tt0200800",
        })
        store.update_file_record(path, {
            "filename": "The.She-Butterfly.1973.mkv",
            "parsed_title": "The She-Butterfly",
            "parsed_year": "1973",
            "display_provider": "tmdb",
            "identity_status": "accepted",
            "metadata_status": "accepted",
            "metadata_accepted": True,
            "identity_title": "Leptirica",
            "identity_year": "1973",
            "tmdb_id": "220638",
            "imdb_id": "tt0200800",
            "identity_source": "identity_audit_tmdb",
            "decision_origin": DECISION_ORIGIN_IDENTITY_AUDIT,
            "manual_lock": False,
        })
        store.save_plex_metadata(path, {
            "plex_title": "The She-Butterfly",
            "plex_year": "1973",
        })
        return path

    def test_get_endpoint_is_read_only(self):
        with tempfile.TemporaryDirectory() as data_tmp:
            app._user_data_dir = data_tmp
            app._identity_verification_audit_cache = {"revision": None, "audit": None}
            store = app.AppMetadataStore(Path(data_tmp))
            self.seed_candidate(store)
            repository = app._catalog_repository_for(data_tmp)
            generation_before = repository.generation()

            response = app.app.test_client().get("/api/metadata/identity-verification")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["summary"]["unverified"], 1)
            self.assertEqual(repository.generation(), generation_before)

    def test_enrichment_merges_aliases_without_changing_accepted_identity(self):
        with tempfile.TemporaryDirectory() as data_tmp:
            app._user_data_dir = data_tmp
            app._tmdb_key = "test-key"
            app._identity_verification_audit_cache = {"revision": None, "audit": None}
            store = app.AppMetadataStore(Path(data_tmp))
            path = self.seed_candidate(store)
            before_record = store.snapshot()["files"][app._norm(path)]

            with patch("app._fetch_tmdb_alternative_titles", return_value=["The She-Butterfly"]):
                response = app.app.test_client().post(
                    "/api/metadata/identity-verification/enrich",
                    json={"limit": 25},
                )

            after_record = store.snapshot()["files"][app._norm(path)]
            metadata = store.get_tmdb_metadata("220638")
            payload = response.get_json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload["enrichment"]["updated"], 1)
            self.assertEqual(payload["verification"]["summary"]["unverified"], 0)
            self.assertEqual(before_record["tmdb_id"], after_record["tmdb_id"])
            self.assertEqual(store.get_manual_match(path), {})
            self.assertEqual(metadata["alternative_titles"], ["The She-Butterfly"])
            self.assertTrue(metadata["alternative_titles_checked_at"])


if __name__ == "__main__":
    unittest.main()
