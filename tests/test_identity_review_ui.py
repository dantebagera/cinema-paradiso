from pathlib import Path
import unittest
from tests.frontend_source import read_frontend_source


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "App.jsx"
AUTHORITY = ROOT / "src" / "components" / "MetadataAuthorityPanel.jsx"
REVIEW = ROOT / "src" / "components" / "IdentityReviewPanel.jsx"


class IdentityReviewUiTest(unittest.TestCase):
    def test_identity_review_is_a_cleanup_tab_not_a_settings_list(self):
        app = read_frontend_source()
        authority = AUTHORITY.read_text(encoding="utf-8")
        review = REVIEW.read_text(encoding="utf-8")

        self.assertIn("Identity Review", app)
        self.assertIn("The full library check is read-only", review)
        self.assertIn("Only identities contradicted by independent provider evidence", review)
        self.assertNotIn("metadata-audit-proposal", authority)
        self.assertIn("Review identity corrections", authority)

    def test_home_health_cards_route_to_exact_cleanup_tabs(self):
        app = read_frontend_source()

        self.assertIn("identity_review_count", app)
        self.assertIn("unmatched_count", app)
        self.assertIn("onOpenCleanup", app)
        self.assertIn("Identity Review", app)
        self.assertNotIn("label: 'Plex matched'", app)

    def test_identity_and_unmatched_rows_offer_play_and_manual_matching(self):
        app = read_frontend_source()
        review = REVIEW.read_text(encoding="utf-8")

        self.assertIn("Play file", app)
        self.assertIn("Search TMDB manually", review)
        self.assertIn("Search Plex manually", review)
        self.assertIn("Preview rename corrected files", review)

    def test_completed_smart_match_does_not_open_automatically(self):
        app = read_frontend_source()

        self.assertNotIn("['running', 'paused', 'completed'].includes(smart.value.status)", app)
        self.assertIn("Open last Smart Match review", app)

    def test_identity_scan_uses_manual_pause_resume_and_new_scan_controls(self):
        app = read_frontend_source()
        review = REVIEW.read_text(encoding="utf-8")

        self.assertIn("/pause", app)
        self.assertIn("/resume", app)
        self.assertIn("Pause scan", review)
        self.assertIn("Resume scan", review)
        self.assertIn("Recheck all identities", review)
        self.assertNotIn("Cancel audit", review)
        self.assertIn("window.confirm", app)

    def test_shadow_identity_results_show_outcome_counts_and_actionable_rows(self):
        app = read_frontend_source()
        review = REVIEW.read_text(encoding="utf-8")

        self.assertIn("manual identities protected", review)
        self.assertIn("uncertain, no action", review)
        self.assertIn("Actionable contradictions", review)
        self.assertIn("Evidence score", review)
        self.assertNotIn("Evidence {", review)
        self.assertIn("shadowMode", review)

    def test_shadow_mode_hides_bulk_selection_and_apply_controls(self):
        review = REVIEW.read_text(encoding="utf-8")

        self.assertIn("!shadowMode && visibleIds.length > 0", review)
        self.assertIn("!shadowMode && selected.size > 0", review)
        self.assertIn("!shadowMode && <footer", review)
        self.assertIn("selectable={false}", review)

    def test_new_audit_never_preselects_identity_changes(self):
        review = REVIEW.read_text(encoding="utf-8")

        self.assertIn("setSelected(new Set());", review)
        self.assertIn("preselected", review)
        self.assertNotIn("setSelected(new Set(recommendedIds))", review)

    def test_identity_review_supports_metadata_discrepancies_and_manual_correction(self):
        review = REVIEW.read_text(encoding="utf-8")

        self.assertIn("Actionable contradiction", review)
        self.assertIn("Correct metadata", review)


if __name__ == "__main__":
    unittest.main()
