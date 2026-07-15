import unittest

from services.identity_decision import (
    classify_audit_decision,
    decide_identity,
    evaluate_identity,
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

    def test_dominant_real_tmdb_candidate_beats_weak_duplicate_pages(self):
        decision = decide_identity(
            [{"title": "Obsession", "year": "2025", "source": "filename"}],
            [
                {
                    "tmdb_id": "1339713",
                    "title": "Obsession",
                    "year": "2026",
                    "provider_rank": 1,
                    "tmdb_vote_count": 1046,
                    "popularity": 95,
                    "poster_path": "/real.jpg",
                    "overview": "A real release with normal metadata.",
                    "runtime": 98,
                    "imdb_id": "tt3000000",
                    "query_sources": ["filename", "title_without_year"],
                },
                {
                    "tmdb_id": "1436161",
                    "title": "Obsession",
                    "year": "2025",
                    "provider_rank": 3,
                    "tmdb_vote_count": 0,
                    "popularity": 1,
                    "poster_path": "",
                    "overview": "",
                    "query_sources": ["filename", "title_with_year"],
                },
                {
                    "tmdb_id": "1502633",
                    "title": "Obsession",
                    "year": "2025",
                    "provider_rank": 5,
                    "tmdb_vote_count": 1,
                    "popularity": 1,
                    "poster_path": "",
                    "overview": "",
                    "query_sources": ["filename", "title_with_year"],
                },
            ],
        )

        self.assertEqual(decision["status"], "accepted")
        self.assertTrue(decision["automatic"])
        self.assertEqual(decision["candidate"]["tmdb_id"], "1339713")

    def test_plex_tmdb_agreement_accepts_one_year_filename_difference(self):
        decision = decide_identity(
            [
                {"title": "Obsession", "year": "2025", "source": "filename"},
                {"title": "Obsession", "year": "2026", "source": "plex_hint"},
            ],
            [
                {
                    "tmdb_id": "1339713",
                    "title": "Obsession",
                    "year": "2026",
                    "provider_rank": 1,
                    "tmdb_vote_count": 1046,
                    "popularity": 95,
                    "poster_path": "/real.jpg",
                    "overview": "A real release with normal metadata.",
                    "query_sources": ["plex_hint", "title_with_year", "title_without_year"],
                },
                {
                    "tmdb_id": "1436161",
                    "title": "Obsession",
                    "year": "2025",
                    "provider_rank": 3,
                    "tmdb_vote_count": 0,
                    "popularity": 1,
                    "poster_path": "",
                    "overview": "",
                    "query_sources": ["filename", "title_with_year"],
                },
            ],
        )

        self.assertEqual(decision["status"], "accepted")
        self.assertTrue(decision["automatic"])
        self.assertEqual(decision["candidate"]["tmdb_id"], "1339713")

    def test_plex_imdb_identity_accepts_matching_tmdb_candidate(self):
        decision = decide_identity(
            [
                {"title": "Obsession", "year": "2025", "source": "filename"},
                {"title": "Obsession", "year": "2026", "source": "plex_hint"},
            ],
            [
                {
                    "tmdb_id": "1339713",
                    "imdb_id": "tt3000000",
                    "title": "Obsession",
                    "year": "2026",
                    "provider_rank": 1,
                    "query_sources": ["plex_hint", "title_with_year"],
                },
                {
                    "tmdb_id": "1436161",
                    "title": "Obsession",
                    "year": "2025",
                    "provider_rank": 3,
                    "query_sources": ["filename", "title_with_year"],
                },
            ],
            known_identity={"imdb_id": "tt3000000"},
        )

        self.assertEqual(decision["status"], "accepted")
        self.assertTrue(decision["automatic"])
        self.assertEqual(decision["candidate"]["tmdb_id"], "1339713")

    def test_same_year_rank_one_subtitle_match_is_accepted_when_rivals_are_wrong_years(self):
        decision = decide_identity(
            [{"title": "Black Box", "year": "2026", "source": "filename"}],
            [
                {
                    "tmdb_id": "1321008",
                    "imdb_id": "tt32315584",
                    "title": "Black Box (Flight 298)",
                    "year": "2026",
                    "provider_rank": 1,
                    "tmdb_vote_count": 7,
                    "popularity": 20,
                    "poster_url": "poster",
                    "plot": "A routine domestic flight turns into the flight from hell.",
                    "runtime": 85,
                    "query_sources": ["filename", "title_with_year", "title_without_year"],
                },
                {
                    "tmdb_id": "663260",
                    "imdb_id": "tt10341034",
                    "title": "Black Box",
                    "year": "2021",
                    "provider_rank": 1,
                    "tmdb_vote_count": 1440,
                    "poster_url": "poster",
                    "plot": "A different older movie.",
                    "runtime": 130,
                    "query_sources": ["filename", "title_without_year"],
                },
            ],
        )

        self.assertEqual(decision["status"], "accepted")
        self.assertTrue(decision["automatic"])
        self.assertEqual(decision["candidate"]["tmdb_id"], "1321008")

    def test_same_year_subtitle_match_requires_review_when_same_year_rival_is_real(self):
        decision = decide_identity(
            [{"title": "Black Box", "year": "2026", "source": "filename"}],
            [
                {
                    "tmdb_id": "1321008",
                    "title": "Black Box (Flight 298)",
                    "year": "2026",
                    "provider_rank": 1,
                    "tmdb_vote_count": 7,
                    "popularity": 20,
                    "poster_url": "poster",
                    "plot": "A routine domestic flight turns into the flight from hell.",
                    "runtime": 85,
                    "query_sources": ["filename", "title_with_year", "title_without_year"],
                },
                {
                    "tmdb_id": "999999",
                    "title": "Black Box: Flight 777",
                    "year": "2026",
                    "provider_rank": 2,
                    "tmdb_vote_count": 50,
                    "poster_url": "poster",
                    "plot": "A separate real same-year movie.",
                    "runtime": 92,
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

    def test_existing_provider_id_is_not_verified_by_provider_hint_alone(self):
        result = classify_audit_decision(
            current={"title": "Wrong Movie", "year": "2016", "tmdb_id": "999"},
            queries=[
                {"title": "Correct Movie", "year": "2016", "source": "filename"},
                {"title": "Wrong Movie", "year": "2016", "source": "plex_hint"},
            ],
            ranked=[{
                "tmdb_id": "999",
                "title": "Wrong Movie",
                "year": "2016",
                "provider_rank": 1,
                "query_sources": ["plex_hint"],
            }],
            provider="tmdb",
        )

        self.assertEqual(result["classification"], "review")
        self.assertFalse(result["automatic"])
        self.assertIn("lacks filename support", result["verification_reasons"][0])

    def test_existing_provider_id_is_verified_with_rank_one_filename_support(self):
        result = classify_audit_decision(
            current={"title": "Correct Movie", "year": "2016", "tmdb_id": "999"},
            queries=[{"title": "Correct Movie", "year": "2016", "source": "filename"}],
            ranked=[{
                "tmdb_id": "999",
                "title": "Correct Movie",
                "year": "2016",
                "provider_rank": 1,
                "query_sources": ["filename", "title_with_year"],
            }],
            provider="tmdb",
        )

        self.assertEqual(result["classification"], "verified")
        self.assertFalse(result["automatic"])
        self.assertEqual(result["verification_reasons"], [])

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

    def test_splice_content_consensus_contradicts_same_title_year_short(self):
        result = evaluate_identity(
            current={"title": "SPLICE", "year": "2009", "tmdb_id": "1629337"},
            queries=[
                {"title": "Splice", "year": "2009", "source": "filename"},
                {"title": "Splice", "year": "2009", "source": "plex_hint"},
            ],
            candidates=[
                {
                    "tmdb_id": "1629337",
                    "title": "SPLICE",
                    "year": "2009",
                    "provider_rank": 2,
                    "tmdb_vote_count": 0,
                    "plot": "A detective investigates VHS tapes connected to missing persons.",
                },
                {
                    "tmdb_id": "37707",
                    "title": "Splice",
                    "year": "2010",
                    "provider_rank": 1,
                    "tmdb_vote_count": 2469,
                    "genres": ["Horror", "Science Fiction"],
                    "plot": "Two rebellious scientists splice human and animal DNA to create a new organism.",
                },
            ],
            provider="tmdb",
            mode="audit",
            independent_claims=[{
                "source": "plex",
                "title": "Splice",
                "year": "2009",
                "genres": ["Science Fiction", "Horror"],
                "plot": "Two young rebellious scientists continue work splicing organisms with human DNA.",
            }],
        )

        self.assertEqual(result["outcome"], "contradicted")
        self.assertEqual(result["classification"], "actionable")
        self.assertEqual(result["candidate"]["tmdb_id"], "37707")
        self.assertFalse(result["automatic"])
        self.assertFalse(result["preselected"])

    def test_influencer_stronger_content_consensus_beats_partial_genre_overlap(self):
        result = evaluate_identity(
            current={"title": "Influencer", "year": "2022", "tmdb_id": "1261876"},
            queries=[{"title": "Influencer", "year": "2022", "source": "filename"}],
            candidates=[
                {
                    "tmdb_id": "1261876", "title": "Influencer", "year": "2022",
                    "provider_rank": 2, "tmdb_vote_count": 1,
                    "plot": "A social media influencer changes her appearance to resemble a celebrity.",
                    "genres": ["Drama", "Horror"],
                    "directors": [{"name": "Nerea Torrijos"}],
                    "cast": [{"name": "Edurne Azkarate"}, {"name": "Heren de Lucas"}],
                },
                {
                    "tmdb_id": "1020910", "imdb_id": "tt13309170",
                    "title": "Influencer", "year": "2023", "provider_rank": 1,
                    "tmdb_vote_count": 368,
                    "plot": "A social media influencer backpacking in Thailand meets CW, whose interest turns dark.",
                    "genres": ["Horror", "Thriller"],
                    "directors": [{"name": "Kurtis David Harder"}],
                    "cast": [{"name": "Cassandra Naud"}, {"name": "Emily Tennant"}],
                },
            ],
            provider="tmdb",
            mode="audit",
            independent_claims=[{
                "title": "Influencer", "year": "2022",
                "plot": "While backpacking in Thailand, social media influencer Madison meets CW and her interest turns dark.",
                "genres": ["Thriller", "Horror"],
                "directors": [{"name": "Kurtis David Harder"}],
                "cast": [{"name": "Cassandra Naud"}, {"name": "Emily Tennant"}],
            }],
        )

        self.assertEqual(result["outcome"], "contradicted")
        self.assertEqual(result["candidate"]["tmdb_id"], "1020910")

    def test_content_consensus_tolerates_two_year_release_date_gap(self):
        result = evaluate_identity(
            current={"title": "Journey to the West", "year": "2021", "tmdb_id": "589022"},
            queries=[{"title": "Journey to the West", "year": "2021", "source": "filename"}],
            candidates=[
                {
                    "tmdb_id": "589022", "title": "Journey to the West", "year": "2021",
                    "provider_rank": 3, "tmdb_vote_count": 0,
                    "plot": "Goku travels west while the Sun threatens Earth.",
                    "genres": ["Animation", "Fantasy"],
                    "directors": [{"name": "Mirai Mizue"}],
                },
                {
                    "tmdb_id": "851977", "title": "Journey to the West", "year": "2023",
                    "provider_rank": 1, "tmdb_vote_count": 82,
                    "plot": "A science fiction magazine editor searches for an alien civilisation.",
                    "genres": ["Adventure", "Comedy", "Science Fiction"],
                    "directors": [{"name": "Kong Dashan"}],
                    "cast": [{"name": "Yang Haoyu"}, {"name": "Ai Liya"}],
                },
            ],
            provider="tmdb",
            mode="audit",
            independent_claims=[{
                "title": "Journey to the West", "year": "2021",
                "plot": "A science fiction magazine editor searches for signs of an alien civilisation.",
                "genres": ["Adventure", "Comedy"],
                "directors": [{"name": "Kong Dashan"}],
                "cast": [{"name": "Yang Haoyu"}, {"name": "Ai Liya"}],
            }],
        )

        self.assertEqual(result["outcome"], "contradicted")
        self.assertEqual(result["candidate"]["tmdb_id"], "851977")

    def test_full_content_consensus_can_recover_provider_alias(self):
        result = evaluate_identity(
            current={"title": "Leap", "year": "2016", "tmdb_id": "1032044"},
            queries=[{"title": "Leap!", "year": "2016", "source": "filename"}],
            candidates=[
                {
                    "tmdb_id": "1032044", "title": "Leap", "year": "2016",
                    "provider_rank": 4, "tmdb_vote_count": 0,
                    "plot": "A short film made for an anthology.",
                    "directors": [{"name": "Sanaa Lathan"}],
                    "cast": [{"name": "Lucy Punch"}],
                },
                {
                    "tmdb_id": "342473", "title": "Ballerina", "year": "2016",
                    "provider_rank": 3, "tmdb_vote_count": 1998,
                    "plot": "An orphan girl dreams of becoming a ballerina and flees to Paris.",
                    "genres": ["Animation", "Adventure", "Family"],
                    "directors": [{"name": "Eric Summer"}, {"name": "Eric Warin"}],
                    "cast": [{"name": "Elle Fanning"}, {"name": "Dane DeHaan"}],
                },
            ],
            provider="tmdb",
            mode="audit",
            independent_claims=[{
                "title": "Leap!", "year": "2016",
                "plot": "An orphan girl dreams of becoming a ballerina and travels to Paris.",
                "genres": ["Family", "Animation"],
                "directors": [{"name": "Eric Summer"}, {"name": "Eric Warin"}],
                "cast": [{"name": "Elle Fanning"}, {"name": "Dane DeHaan"}],
            }],
        )

        self.assertEqual(result["outcome"], "contradicted")
        self.assertEqual(result["candidate"]["tmdb_id"], "342473")

    def test_existing_imdb_anchor_survives_filename_release_year_candidate(self):
        result = evaluate_identity(
            current={
                "title": "The Witch",
                "year": "2016",
                "tmdb_id": "310131",
                "imdb_id": "tt4263482",
            },
            queries=[{"title": "The Witch", "year": "2015", "source": "filename"}],
            candidates=[
                {
                    "tmdb_id": "526667",
                    "title": "The Witch",
                    "year": "2015",
                    "provider_rank": 1,
                    "tmdb_vote_count": 6,
                },
                {
                    "tmdb_id": "310131",
                    "imdb_id": "tt4263482",
                    "title": "The Witch",
                    "year": "2016",
                    "provider_rank": 1,
                    "tmdb_vote_count": 7717,
                },
            ],
            provider="tmdb",
            mode="audit",
        )

        self.assertEqual(result["outcome"], "verified")
        self.assertEqual(result["classification"], "verified")
        self.assertEqual(result["candidate"]["tmdb_id"], "310131")
        self.assertTrue(result["date_discrepancy"])

    def test_same_provider_identity_is_verified_without_a_review_row(self):
        result = evaluate_identity(
            current={"title": "The Matrix", "year": "1999", "tmdb_id": "603"},
            queries=[{"title": "The Matrix", "year": "1999", "source": "filename"}],
            candidates=[{
                "tmdb_id": "603",
                "title": "The Matrix",
                "year": "1999",
                "provider_rank": 1,
                "tmdb_vote_count": 27000,
            }],
            provider="tmdb",
            mode="audit",
        )

        self.assertEqual(result["outcome"], "verified")
        self.assertEqual(result["classification"], "verified")

    def test_new_exact_title_year_candidate_is_blocked_by_independent_content_conflict(self):
        result = evaluate_identity(
            queries=[{"title": "Splice", "year": "2009", "source": "filename"}],
            candidates=[{
                "tmdb_id": "1629337",
                "title": "Splice",
                "year": "2009",
                "provider_rank": 1,
                "plot": "A detective studies mysterious tapes after several people disappear from a city.",
                "genres": ["Crime", "Mystery"],
                "directors": [{"name": "Dylan MacGregor"}],
                "cast": [{"name": "Cole Weinmeyer"}, {"name": "Jack McLean"}],
            }],
            independent_claims=[{
                "plot": "Two rebellious scientists combine human and animal DNA and create a dangerous organism.",
                "genres": ["Science Fiction", "Horror"],
                "directors": [{"name": "Vincenzo Natali"}],
                "cast": [{"name": "Adrien Brody"}, {"name": "Sarah Polley"}],
            }],
        )

        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["outcome"], "contradicted")
        self.assertFalse(result["automatic"])
        self.assertIn("independent provider content contradicts", result["reasons"][-1])

    def test_new_match_recovers_one_unique_content_supported_release(self):
        result = evaluate_identity(
            queries=[{"title": "Splice", "year": "2009", "source": "filename"}],
            candidates=[
                {
                    "tmdb_id": "1629337",
                    "title": "Splice",
                    "year": "2009",
                    "provider_rank": 1,
                    "tmdb_vote_count": 0,
                    "plot": "A detective studies mysterious tapes after several people disappear from a city.",
                    "genres": ["Crime", "Mystery"],
                    "directors": [{"name": "Dylan MacGregor"}],
                    "cast": [{"name": "Cole Weinmeyer"}, {"name": "Jack McLean"}],
                },
                {
                    "tmdb_id": "37707",
                    "title": "Splice",
                    "year": "2010",
                    "provider_rank": 2,
                    "tmdb_vote_count": 2469,
                    "plot": "Two rebellious scientists combine human and animal DNA and create a dangerous organism.",
                    "genres": ["Science Fiction", "Horror"],
                    "directors": [{"name": "Vincenzo Natali"}],
                    "cast": [{"name": "Adrien Brody"}, {"name": "Sarah Polley"}],
                },
            ],
            independent_claims=[{
                "plot": "Two rebellious scientists splice human and animal DNA to create a dangerous organism.",
                "genres": ["Science Fiction", "Horror"],
                "directors": [{"name": "Vincenzo Natali"}],
                "cast": [{"name": "Adrien Brody"}, {"name": "Sarah Polley"}],
            }],
        )

        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["outcome"], "accepted")
        self.assertTrue(result["automatic"])
        self.assertEqual(result["candidate"]["tmdb_id"], "37707")
        self.assertTrue(result["date_discrepancy"])

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
