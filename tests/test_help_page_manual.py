from pathlib import Path
import unittest


APP_SOURCE = (Path(__file__).resolve().parents[1] / "src" / "App.jsx").read_text(encoding="utf-8")
MANUAL_SOURCE = APP_SOURCE.split("const manualSections = [", 1)[1].split("const cardLabMovies = [", 1)[0]
HELP_SOURCE = APP_SOURCE.split("const helpSections = [", 1)[1].split("function HelpWorkspace()", 1)[0]


class HelpPageManualTests(unittest.TestCase):
    def test_manual_documents_current_top_level_and_daily_workflows(self):
        for text in [
            "Movie Lists workspace",
            "AI Control workspace",
            "bulk selection",
            "Watched",
            "Watchlist",
            "in-app trailer modal",
            "Streaming Link",
            "unreleased",
            "trusted release indexers",
            "IMDb-first",
            "alternative-title fallback",
            "progressive per-indexer",
        ]:
            self.assertIn(text, MANUAL_SOURCE)

    def test_dependency_setup_documents_new_optional_surfaces(self):
        for text in [
            "Streaming Link",
            "AI Control",
            "Experimental",
            "{tmdb_id}",
            "{imdb_id}",
            "Ollama-curated lists",
            "AI Control trusted indexers",
        ]:
            self.assertIn(text, HELP_SOURCE)


if __name__ == "__main__":
    unittest.main()
