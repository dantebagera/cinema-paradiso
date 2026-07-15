from pathlib import Path
import unittest
from tests.frontend_source import read_frontend_source


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "App.jsx"
PANEL = ROOT / "src" / "components" / "SmartMatchPanel.jsx"
MAIN = ROOT / "src" / "main.jsx"
STYLES = ROOT / "src" / "styles" / "smartMatch.css"


class SmartMatchUiTest(unittest.TestCase):
    def test_unmatched_tab_exposes_provider_method_and_selected_action(self):
        app = read_frontend_source()
        panel = PANEL.read_text(encoding="utf-8")

        self.assertIn("<SmartMatchControls", app)
        self.assertIn("Smart Match Selected", panel)
        self.assertIn('value="tmdb"', panel)
        self.assertIn('value="plex"', panel)
        self.assertIn('value="classic"', panel)
        self.assertIn('value="ai"', panel)
        self.assertIn("disabled={!ollamaAvailable}", panel)
        self.assertIn("providers?.tmdb === false && providers?.plex !== false", panel)
        self.assertIn("!providers?.[provider]", panel)

    def test_review_requires_explicit_confirmation_and_supports_manual_fallback(self):
        panel = PANEL.read_text(encoding="utf-8")

        self.assertIn("/api/metadata/smart-match/", panel)
        self.assertIn("Confirm apply matches", panel)
        self.assertIn("Search TMDB manually", panel)
        self.assertIn("Search Plex manually", panel)
        self.assertNotIn("disabled={!item?.rating_key}", panel)
        self.assertIn("Preview rename approved files", panel)

    def test_review_supports_recommended_all_clear_and_indeterminate_selection(self):
        panel = PANEL.read_text(encoding="utf-8")

        self.assertIn("Select recommended", panel)
        self.assertIn("Select all proposals", panel)
        self.assertIn(">Clear<", panel)
        self.assertIn(".indeterminate =", panel)
        self.assertIn("recommendation === 'recommended'", panel)

    def test_review_displays_evidence_gap_queries_and_ai_fallback(self):
        panel = PANEL.read_text(encoding="utf-8")

        self.assertIn("Evidence score", panel)
        self.assertIn("Runner-up gap", panel)
        self.assertIn("AI query", panel)
        self.assertIn("proposal.parsed.title", panel)
        self.assertIn("Classic fallback", panel)
        self.assertIn("proposal.ai_warning", panel)

    def test_rename_is_separate_and_requires_preview_token(self):
        panel = PANEL.read_text(encoding="utf-8")

        self.assertIn("/api/metadata/smart-rename/preview", panel)
        self.assertIn("/api/metadata/smart-rename/apply", panel)
        self.assertIn("Confirm rename selected files", panel)
        self.assertIn("token: renamePreview.token", panel)

    def test_smart_match_styles_are_loaded_and_responsive(self):
        main = MAIN.read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")

        self.assertIn("smartMatch.css", main)
        self.assertIn("var(--projector-gold)", styles)
        self.assertIn("@media (max-width: 640px)", styles)


if __name__ == "__main__":
    unittest.main()
