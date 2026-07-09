from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "src" / "App.jsx").read_text(encoding="utf-8")
STYLES_SOURCE = (ROOT / "src" / "styles.css").read_text(encoding="utf-8")


class AiControlUiTest(unittest.TestCase):
    def test_sidebar_and_workspace_show_experimental_badge(self):
        self.assertIn("id: 'ai-control'", APP_SOURCE)
        self.assertIn("AI Control", APP_SOURCE)
        self.assertIn("ExperimentalBadge", APP_SOURCE)
        self.assertIn("ai-control-nav-badge", APP_SOURCE)

    def test_prompting_guide_renders_under_command_box(self):
        for text in [
            "Find Tom Cruise movies I own",
            "Create a list of top rated sci-fi from 2010",
            "Download unowned Nolan movies in 1080p",
            "Delete files larger than 10 GB",
            "No action runs automatically. Every result is reviewed before you confirm it.",
        ]:
            self.assertIn(text, APP_SOURCE)

    def test_execute_button_depends_on_reviewed_plan_id(self):
        self.assertIn("executeAiControlPlan", APP_SOURCE)
        self.assertIn("disabled={!aiControlPlan?.plan_id", APP_SOURCE)
        self.assertIn("/api/ai-control/preview", APP_SOURCE)
        self.assertIn("/api/ai-control/execute", APP_SOURCE)

    def test_ai_control_trusted_indexers_use_dialog_not_inline_long_list(self):
        self.assertIn("aiControlIndexerDialogOpen", APP_SOURCE)
        self.assertIn("AIControlIndexerDialog", APP_SOURCE)
        self.assertIn("AI Control download trust", APP_SOURCE)
        self.assertIn("AI Control trusted indexers", APP_SOURCE)
        self.assertNotIn("ai-control-indexer-list", APP_SOURCE)

    def test_ai_control_defaults_to_yts_copy_is_visible(self):
        self.assertIn("YTS/YIFY default", APP_SOURCE)
        self.assertIn("Default AI Control download source.", APP_SOURCE)

    def test_ai_control_styles_exist(self):
        self.assertIn(".ai-control-workspace", STYLES_SOURCE)
        self.assertIn(".experimental-badge", STYLES_SOURCE)
        self.assertIn(".ai-control-guide", STYLES_SOURCE)

    def test_ai_control_blocked_rows_show_reason_column(self):
        self.assertIn("Reason", APP_SOURCE)
        self.assertIn("row.reason", APP_SOURCE)

    def test_ai_control_preview_loading_shows_staged_messages(self):
        for text in [
            "Understanding request with Ollama...",
            "Contacting TMDB...",
            "Checking your library...",
            "Searching trusted indexers...",
            "Preparing review...",
        ]:
            self.assertIn(text, APP_SOURCE)

    def test_ai_control_find_results_can_replace_table_with_card_view(self):
        for text in [
            "Display as cards",
            "Back to table",
            "ai-control-card-results",
            "setAiControlCardView(true)",
            "plan.action === 'find'",
        ]:
            self.assertIn(text, APP_SOURCE)

    def test_ai_control_card_view_reuses_discover_cards_and_bulk_lists(self):
        result_source = APP_SOURCE[
            APP_SOURCE.index("function AIControlResult"):
            APP_SOURCE.index("function AIControlTable")
        ]
        for text in [
            "AIControlCardResults",
            "DiscoverMovieCard",
            "selectedAiControlMovies",
            "Add selected to list",
            "onAddBulk={addAiControlMoviesToList}",
        ]:
            self.assertIn(text, APP_SOURCE)
        self.assertIn("!aiControlCardView && visibleRows.length > 0 && <AIControlTable", result_source)

    def test_ai_control_card_view_can_surface_preserved_cast_and_directors(self):
        discover_card_source = APP_SOURCE[
            APP_SOURCE.index("function DiscoverMovieCard"):
            APP_SOURCE.index("function MovieFactChips")
        ]
        self.assertIn("directors={movie.directors}", discover_card_source)
        self.assertIn("cast={movie.cast}", discover_card_source)

    def test_ai_control_results_render_pagination_and_total_count(self):
        for text in [
            "ai-control-pagination",
            "total_matches",
            "currentPage",
            "Previous page",
            "Next page",
        ]:
            self.assertIn(text, APP_SOURCE)

    def test_ai_control_large_delete_requires_confirmation_phrase(self):
        for text in [
            "requires_extra_confirmation",
            "confirmation_phrase",
            "Type the confirmation phrase",
            "setAiControlDangerPhrase",
        ]:
            self.assertIn(text, APP_SOURCE)


if __name__ == "__main__":
    unittest.main()
