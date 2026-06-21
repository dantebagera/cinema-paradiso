from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "App.jsx"
AUTHORITY = ROOT / "src" / "components" / "MetadataAuthorityPanel.jsx"
REVIEW = ROOT / "src" / "components" / "IdentityReviewPanel.jsx"


class IdentityReviewUiTest(unittest.TestCase):
    def test_identity_review_is_a_cleanup_tab_not_a_settings_list(self):
        app = APP.read_text(encoding="utf-8")
        authority = AUTHORITY.read_text(encoding="utf-8")
        review = REVIEW.read_text(encoding="utf-8")

        self.assertIn("Identity Review", app)
        self.assertIn("These movies are already matched", review)
        self.assertIn("Unmatched files are handled separately", review)
        self.assertNotIn("metadata-audit-proposal", authority)
        self.assertIn("Review identity corrections", authority)

    def test_home_health_cards_route_to_exact_cleanup_tabs(self):
        app = APP.read_text(encoding="utf-8")

        self.assertIn("identity_review_count", app)
        self.assertIn("unmatched_count", app)
        self.assertIn("onOpenCleanup", app)
        self.assertIn("Identity Review", app)
        self.assertNotIn("label: 'Plex matched'", app)

    def test_identity_and_unmatched_rows_offer_play_and_manual_matching(self):
        app = APP.read_text(encoding="utf-8")
        review = REVIEW.read_text(encoding="utf-8")

        self.assertIn("Play file", app)
        self.assertIn("Search TMDB manually", review)
        self.assertIn("Search Plex manually", review)
        self.assertIn("Preview rename corrected files", review)

    def test_completed_smart_match_does_not_open_automatically(self):
        app = APP.read_text(encoding="utf-8")

        self.assertNotIn("['running', 'paused', 'completed'].includes(smart.value.status)", app)
        self.assertIn("Open last Smart Match review", app)

    def test_identity_scan_uses_manual_pause_resume_and_new_scan_controls(self):
        app = APP.read_text(encoding="utf-8")
        review = REVIEW.read_text(encoding="utf-8")

        self.assertIn("/pause", app)
        self.assertIn("/resume", app)
        self.assertIn("Pause scan", review)
        self.assertIn("Resume scan", review)
        self.assertIn("Start new scan", review)
        self.assertNotIn("Cancel audit", review)
        self.assertIn("window.confirm", app)

    def test_identity_results_are_grouped_and_scores_are_not_percentages(self):
        app = APP.read_text(encoding="utf-8")
        review = REVIEW.read_text(encoding="utf-8")

        self.assertIn("Automatic fixes", review)
        self.assertIn("Recommended corrections", review)
        self.assertIn("Needs review", review)
        self.assertIn("Weak matches", review)
        self.assertIn('<option value="weak">Weak matches</option>', app)
        self.assertIn("Evidence score", review)
        self.assertNotIn("Evidence {", review)
        self.assertIn("Automatically applied", review)

    def test_identity_selection_persists_across_filters_and_apply_is_available_twice(self):
        review = REVIEW.read_text(encoding="utf-8")

        self.assertNotIn("filter((id) => visible.has(id))", review)
        self.assertIn("hiddenSelectedCount", review)
        self.assertIn("addSelected", review)
        self.assertIn("selected.size - visibleSelectedCount", review)
        self.assertGreaterEqual(review.count("Apply selected corrections"), 2)
        self.assertIn("hidden by this filter", review)

    def test_identity_review_supports_metadata_discrepancies_and_manual_correction(self):
        review = REVIEW.read_text(encoding="utf-8")

        self.assertIn("Metadata discrepancies", review)
        self.assertIn("proposal.proposal_type === 'metadata_discrepancy'", review)
        self.assertIn("Correct metadata", review)


if __name__ == "__main__":
    unittest.main()
