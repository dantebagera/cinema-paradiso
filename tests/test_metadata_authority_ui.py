from pathlib import Path
import unittest
from tests.frontend_source import read_frontend_source


ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "src" / "components" / "MetadataAuthorityPanel.jsx"
STYLES = ROOT / "src" / "styles" / "metadataAuthority.css"
APP = ROOT / "src" / "App.jsx"
MAIN = ROOT / "src" / "main.jsx"


class MetadataAuthorityUiTest(unittest.TestCase):
    def test_settings_uses_dedicated_metadata_authority_panel(self):
        panel = PANEL.read_text(encoding="utf-8")
        app = read_frontend_source()

        self.assertIn("MetadataAuthorityPanel", app)
        self.assertIn("/api/metadata/authority", panel)
        self.assertIn("/api/metadata/authority/preview", panel)
        self.assertIn("/api/metadata/authority/migrate", panel)
        self.assertIn("/api/metadata/migration/", panel)
        self.assertIn("Metadata authority", panel)
        self.assertIn("Local movie files are never changed", panel)

    def test_migration_panel_has_progress_and_recovery_controls(self):
        panel = PANEL.read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")

        self.assertIn('role="progressbar"', panel)
        self.assertIn("Pause", panel)
        self.assertIn("Resume", panel)
        self.assertIn("Cancel", panel)
        self.assertIn("Retry failures", panel)
        self.assertIn("Review uncertain matches", panel)
        self.assertIn("metadataAuthority.css", main)
        self.assertIn("var(--projector-gold)", styles)
        self.assertIn("var(--success-green)", styles)
        self.assertIn("@media (max-width: 640px)", styles)

    def test_uncertain_match_review_uses_cleanup_unmatched_navigation(self):
        panel = PANEL.read_text(encoding="utf-8")
        app = read_frontend_source()

        self.assertIn("onReviewUnmatched", panel)
        self.assertIn("onClick={onReviewUnmatched}", panel)
        self.assertNotIn('href="/cleanup"', panel)
        self.assertIn("onReviewUnmatched={reviewUnmatchedMetadata}", app)
        self.assertIn("onReviewUnmatched={onReviewUnmatched}", app)

    def test_identity_review_routes_from_settings_to_cleanup(self):
        panel = PANEL.read_text(encoding="utf-8")
        app = read_frontend_source()

        self.assertNotIn("/api/metadata/identity-audit", panel)
        self.assertIn("Review identity corrections", panel)
        self.assertIn("onReviewIdentities", panel)
        self.assertIn("onReviewIdentities={() => openCleanupTab('identity')}", app)


if __name__ == "__main__":
    unittest.main()
