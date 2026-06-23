import unittest

from services.identity_decision import (
    classify_audit_decision,
    decide_identity,
    resolve_collection_membership,
)
from services.smart_match import parse_release_filename


class IdentityDecisionServiceTest(unittest.TestCase):
    def test_parser_handles_year_joined_to_release_source(self):
        parsed = parse_release_filename("Monsters Inc 2001BluRay 1080p DD5.1 H265-d3g.mkv")

        self.assertEqual(parsed["title"], "Monsters Inc")
        self.assertEqual(parsed["year"], "2001")

    def test_parser_removes_alternate_ending_release_qualifier(self):
        parsed = parse_release_filename("I.Am.Legend.ALTERNATE.ENDING.2007.1080p.BrRip.x264.YIFY.mp4")

        self.assertEqual(parsed["title"], "I Am Legend")
        self.assertEqual(parsed["year"], "2007")

    def test_unique_yearless_exact_title_is_accepted(self):
        decision = decide_identity(
            [{"title": "The Phantom Menace", "year": "", "source": "filename"}],
            [{"tmdb_id": "661852", "title": "The Phantom Menace", "year": "2020", "provider_rank": 1}],
        )

        self.assertEqual(decision["status"], "accepted")
        self.assertTrue(decision["automatic"])

    def test_plex_title_and_exact_year_can_corroborate_tmdb_identity(self):
        decision = decide_identity(
            [
                {"title": "The Phantom Menace", "year": "", "source": "filename"},
                {"title": "Star Wars: Episode I - The Phantom Menace", "year": "1999", "source": "plex_hint"},
            ],
            [
                {"tmdb_id": "661852", "title": "The Phantom Menace", "year": "2020", "provider_rank": 1},
                {"tmdb_id": "1893", "title": "Star Wars: Episode I - The Phantom Menace", "year": "1999", "provider_rank": 1},
            ],
        )

        self.assertEqual(decision["status"], "accepted")
        self.assertEqual(decision["candidate"]["tmdb_id"], "1893")
        self.assertTrue(decision["automatic"])

    def test_one_year_difference_is_accepted_without_a_competing_release(self):
        decision = decide_identity(
            [{"title": "Audition", "year": "1999", "source": "filename"}],
            [{"tmdb_id": "11075", "title": "Audition", "year": "2000", "provider_rank": 1}],
        )

        self.assertEqual(decision["status"], "accepted")
        self.assertTrue(decision["automatic"])
        self.assertTrue(decision["date_discrepancy"])

    def test_official_alternative_title_has_equal_identity_weight(self):
        decision = decide_identity(
            [{"title": "Asterix in America", "year": "1994", "source": "filename"}],
            [{
                "tmdb_id": "9361",
                "title": "Asterix Conquers America",
                "original_title": "Asterix in Amerika",
                "alternative_titles": ["Asterix in America"],
                "year": "1994",
                "provider_rank": 1,
            }],
        )

        self.assertEqual(decision["status"], "accepted")
        self.assertEqual(decision["candidate"]["tmdb_id"], "9361")

    def test_yearless_exact_title_with_multiple_releases_requires_review(self):
        decision = decide_identity(
            [{"title": "Crash", "year": "", "source": "filename"}],
            [
                {"tmdb_id": "884", "title": "Crash", "year": "1996", "provider_rank": 1},
                {"tmdb_id": "1640", "title": "Crash", "year": "2004", "provider_rank": 2},
            ],
        )

        self.assertEqual(decision["status"], "review")
        self.assertFalse(decision["automatic"])

    def test_dominant_exact_title_year_accepts_popular_movie_over_zero_vote_duplicate(self):
        decision = decide_identity(
            [{"title": "Misery", "year": "1990", "source": "filename"}],
            [
                {
                    "tmdb_id": "1700",
                    "title": "Misery",
                    "year": "1990",
                    "provider_rank": 1,
                    "tmdb_vote_count": 5262,
                    "query_sources": ["filename", "title_with_year", "title_without_year"],
                },
                {
                    "tmdb_id": "536304",
                    "title": "Misery",
                    "year": "1990",
                    "provider_rank": 8,
                    "tmdb_vote_count": 0,
                    "query_sources": ["filename", "title_without_year"],
                },
            ],
        )

        self.assertEqual(decision["status"], "accepted")
        self.assertTrue(decision["automatic"])
        self.assertEqual(decision["candidate"]["tmdb_id"], "1700")

    def test_dominant_exact_title_year_accepts_rank_one_movie_with_modest_votes(self):
        decision = decide_identity(
            [{"title": "Pressure", "year": "2026", "source": "filename"}],
            [
                {
                    "tmdb_id": "1318413",
                    "title": "Pressure",
                    "year": "2026",
                    "provider_rank": 1,
                    "tmdb_vote_count": 78,
                    "query_sources": ["filename", "title_with_year", "title_without_year"],
                },
                {
                    "tmdb_id": "1701077",
                    "title": "Pressure",
                    "year": "2026",
                    "provider_rank": 6,
                    "tmdb_vote_count": 0,
                    "query_sources": ["filename", "title_with_year"],
                },
                {
                    "tmdb_id": "1687571",
                    "title": "A Pressure",
                    "year": "2026",
                    "provider_rank": 8,
                    "tmdb_vote_count": 0,
                    "query_sources": ["filename", "title_with_year"],
                },
            ],
        )

        self.assertEqual(decision["status"], "accepted")
        self.assertTrue(decision["automatic"])
        self.assertEqual(decision["candidate"]["tmdb_id"], "1318413")

    def test_dominant_exact_title_year_accepts_rank_one_theatrical_movie(self):
        decision = decide_identity(
            [{"title": "The Dark Tower", "year": "2017", "source": "filename"}],
            [
                {
                    "tmdb_id": "353491",
                    "title": "The Dark Tower",
                    "year": "2017",
                    "provider_rank": 1,
                    "tmdb_vote_count": 5541,
                    "query_sources": ["filename", "title_with_year", "title_without_year"],
                },
                {
                    "tmdb_id": "1694198",
                    "title": "The Dark Tower",
                    "year": "2017",
                    "provider_rank": 5,
                    "tmdb_vote_count": 0,
                    "query_sources": ["filename", "title_without_year"],
                },
            ],
        )

        self.assertEqual(decision["status"], "accepted")
        self.assertTrue(decision["automatic"])
        self.assertEqual(decision["candidate"]["tmdb_id"], "353491")

    def test_exact_title_year_with_meaningful_competing_votes_requires_review(self):
        decision = decide_identity(
            [{"title": "Pressure", "year": "2026", "source": "filename"}],
            [
                {
                    "tmdb_id": "1318413",
                    "title": "Pressure",
                    "year": "2026",
                    "provider_rank": 1,
                    "tmdb_vote_count": 78,
                    "query_sources": ["filename", "title_with_year", "title_without_year"],
                },
                {
                    "tmdb_id": "1701077",
                    "title": "Pressure",
                    "year": "2026",
                    "provider_rank": 2,
                    "tmdb_vote_count": 40,
                    "query_sources": ["filename", "title_with_year"],
                },
            ],
        )

        self.assertEqual(decision["status"], "review")
        self.assertFalse(decision["automatic"])

    def test_plex_and_filename_agreement_accepts_rank_one_over_low_vote_duplicate(self):
        decision = decide_identity(
            [
                {"title": "Pressure", "year": "2026", "source": "filename"},
                {"title": "Pressure", "year": "2026", "source": "plex_hint"},
            ],
            [
                {
                    "tmdb_id": "1318413",
                    "title": "Pressure",
                    "year": "2026",
                    "provider_rank": 1,
                    "tmdb_vote_count": 78,
                    "query_sources": ["filename", "title_with_year", "title_without_year"],
                },
                {
                    "tmdb_id": "1701077",
                    "title": "Pressure",
                    "year": "2026",
                    "provider_rank": 2,
                    "tmdb_vote_count": 40,
                    "query_sources": ["filename", "title_with_year"],
                },
            ],
        )

        self.assertEqual(decision["status"], "accepted")
        self.assertTrue(decision["automatic"])
        self.assertIn("filename and Plex agree", decision["reasons"])

    def test_similarity_does_not_turn_love_into_money_or_love(self):
        decision = decide_identity(
            [{"title": "Love", "year": "2011", "source": "filename"}],
            [{"tmdb_id": "777", "title": "Money or Love", "year": "2011", "provider_rank": 1}],
        )

        self.assertEqual(decision["status"], "unmatched")
        self.assertFalse(decision["automatic"])

    def test_conflicting_strong_id_is_never_accepted(self):
        decision = decide_identity(
            [{"title": "Alien", "year": "1979", "source": "filename"}],
            [{"tmdb_id": "679", "title": "Alien", "year": "1979", "provider_rank": 1}],
            known_identity={"tmdb_id": "348"},
        )

        self.assertEqual(decision["status"], "conflict")

    def test_missing_tmdb_id_exact_identity_with_dominant_result_is_automatically_verified(self):
        result = classify_audit_decision(
            current={"title": "Elle", "year": "2016", "tmdb_id": ""},
            queries=[{"title": "Elle", "year": "2016", "source": "filename"}],
            ranked=[
                {
                    "tmdb_id": "337674",
                    "title": "Elle",
                    "year": "2016",
                    "provider_rank": 1,
                    "tmdb_vote_count": 2100,
                    "evidence_score": 100,
                    "runner_up_gap": 4,
                },
                {
                    "tmdb_id": "1018714",
                    "title": "Elle",
                    "year": "2016",
                    "provider_rank": 2,
                    "tmdb_vote_count": 20,
                    "evidence_score": 96,
                },
            ],
            provider="tmdb",
        )

        self.assertEqual(result["classification"], "automatically_verified")
        self.assertTrue(result["automatic"])

    def test_same_title_year_without_provider_dominance_requires_review(self):
        result = classify_audit_decision(
            current={"title": "Elle", "year": "2016", "tmdb_id": ""},
            queries=[{"title": "Elle", "year": "2016", "source": "filename"}],
            ranked=[
                {
                    "tmdb_id": "337674",
                    "title": "Elle",
                    "year": "2016",
                    "provider_rank": 1,
                    "tmdb_vote_count": 80,
                    "evidence_score": 100,
                    "runner_up_gap": 4,
                },
                {
                    "tmdb_id": "1018714",
                    "title": "Elle",
                    "year": "2016",
                    "provider_rank": 2,
                    "tmdb_vote_count": 40,
                    "evidence_score": 96,
                },
            ],
            provider="tmdb",
        )

        self.assertEqual(result["classification"], "review")
        self.assertFalse(result["automatic"])

    def test_provider_title_without_filename_or_folder_corroboration_is_not_auto_linked(self):
        result = classify_audit_decision(
            current={"title": "Wrong Movie", "year": "2016", "tmdb_id": ""},
            queries=[
                {"title": "Correct Movie", "year": "2016", "source": "filename"},
                {"title": "Wrong Movie", "year": "2016", "source": "plex_hint"},
            ],
            ranked=[{
                "tmdb_id": "999",
                "title": "Wrong Movie",
                "year": "2016",
                "provider_rank": 1,
                "tmdb_vote_count": 500,
                "evidence_score": 100,
            }],
            provider="tmdb",
        )

        self.assertEqual(result["classification"], "review")
        self.assertFalse(result["automatic"])

    def test_identity_conflict_is_never_automatically_verified(self):
        result = classify_audit_decision(
            current={"title": "Elle", "year": "2016", "tmdb_id": ""},
            queries=[{"title": "Elle", "year": "2016", "source": "filename"}],
            ranked=[{
                "tmdb_id": "337674",
                "title": "Elle",
                "year": "2016",
                "provider_rank": 1,
                "tmdb_vote_count": 2100,
                "evidence_score": 100,
                "runner_up_gap": 100,
                "identity_conflict": True,
            }],
            provider="tmdb",
        )

        self.assertNotEqual(result["classification"], "automatically_verified")
        self.assertFalse(result["automatic"])

    def test_current_identity_exactly_matching_dominant_candidate_auto_links_despite_filename_wording(self):
        result = classify_audit_decision(
            current={
                "title": "A Nightmare on Elm Street Part 2: Freddy's Revenge",
                "year": "1985",
                "tmdb_id": "",
            },
            queries=[{
                "title": "a nightmare on elm street 2 freddys revenge",
                "year": "1985",
                "source": "filename",
            }],
            ranked=[{
                "tmdb_id": "10014",
                "title": "A Nightmare on Elm Street Part 2: Freddy's Revenge",
                "year": "1985",
                "provider_rank": 1,
                "tmdb_vote_count": 2115,
                "evidence_score": 100,
                "runner_up_gap": 100,
            }],
            provider="tmdb",
        )

        self.assertEqual(result["classification"], "automatically_verified")
        self.assertTrue(result["automatic"])

    def test_strong_identity_change_is_recommended_but_not_automatic(self):
        result = classify_audit_decision(
            current={"title": "The Ick", "year": "2024", "tmdb_id": "111"},
            queries=[{"title": "Ick", "year": "2025", "source": "filename"}],
            ranked=[{
                "tmdb_id": "222",
                "title": "Ick",
                "year": "2025",
                "provider_rank": 1,
                "tmdb_vote_count": 500,
                "evidence_score": 100,
                "runner_up_gap": 20,
            }],
            provider="tmdb",
        )

        self.assertEqual(result["classification"], "recommended")
        self.assertFalse(result["automatic"])
        self.assertTrue(result["preselected"])

    def test_strong_identity_change_with_small_gap_requires_review(self):
        result = classify_audit_decision(
            current={"title": "The Ick", "year": "2024", "tmdb_id": "111"},
            queries=[{"title": "Ick", "year": "2025", "source": "filename"}],
            ranked=[{
                "tmdb_id": "222",
                "title": "Ick",
                "year": "2025",
                "provider_rank": 1,
                "tmdb_vote_count": 500,
                "evidence_score": 100,
                "runner_up_gap": 4,
            }],
            provider="tmdb",
        )

        self.assertEqual(result["classification"], "review")
        self.assertFalse(result["preselected"])

    def test_provider_hint_alone_cannot_recommend_identity_replacement(self):
        result = classify_audit_decision(
            current={"title": "Wrong Movie", "year": "2024", "tmdb_id": "111"},
            queries=[{"title": "Correct Movie", "year": "2024", "source": "plex_hint"}],
            ranked=[{
                "tmdb_id": "222",
                "title": "Correct Movie",
                "year": "2024",
                "provider_rank": 1,
                "evidence_score": 100,
                "runner_up_gap": 30,
            }],
            provider="tmdb",
        )

        self.assertEqual(result["classification"], "review")
        self.assertFalse(result["preselected"])

    def test_low_evidence_identity_change_is_weak(self):
        result = classify_audit_decision(
            current={"title": "Love", "year": "2011", "tmdb_id": "111"},
            queries=[{"title": "Love", "year": "2011", "source": "filename"}],
            ranked=[{
                "tmdb_id": "222",
                "title": "Money or Love",
                "year": "2011",
                "provider_rank": 1,
                "evidence_score": 65,
                "runner_up_gap": 14,
            }],
            provider="tmdb",
        )

        self.assertEqual(result["classification"], "weak")
        self.assertFalse(result["preselected"])

    def test_moderate_identity_change_below_seventy_is_weak(self):
        result = classify_audit_decision(
            current={"title": "Love", "year": "2011", "tmdb_id": "111"},
            queries=[{"title": "Love", "year": "2011", "source": "filename"}],
            ranked=[{
                "tmdb_id": "222",
                "title": "Money or Love",
                "year": "2011",
                "provider_rank": 1,
                "tmdb_vote_count": 50,
                "evidence_score": 65,
                "runner_up_gap": 14,
            }],
            provider="tmdb",
        )

        self.assertEqual(result["classification"], "weak")
        self.assertFalse(result["preselected"])

    def test_collection_resolution_prefers_path_then_ids_then_exact_title_year(self):
        collection = {
            "id": "10",
            "parts": [
                {"tmdb_id": "11", "title": "Star Wars", "year": "1977"},
                {"tmdb_id": "181808", "title": "Star Wars: The Last Jedi", "year": "2017"},
                {"tmdb_id": "", "title": "Custom Film", "year": "2024", "path": "E:/Movies/Custom.mkv"},
            ],
        }
        library = [
            {"path": "E:/Movies/Star Wars.mkv", "tmdb_id": "11", "title": "Different", "year": "1977"},
            {"path": "E:/Movies/Last Jedi.mkv", "title": "Star Wars: The Last Jedi", "year": "2017"},
            {"path": "E:/Movies/Custom.mkv", "tmdb_id": "999", "title": "Wrong", "year": "2000"},
        ]

        result = resolve_collection_membership(collection, library)

        self.assertEqual(len(result["owned_paths"]), 3)
        self.assertEqual(result["unresolved_parts"], [])


if __name__ == "__main__":
    unittest.main()
