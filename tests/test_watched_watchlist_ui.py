from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = (
    (ROOT / "src" / "App.jsx").read_text(encoding="utf-8")
    + (ROOT / "src" / "components" / "SharedMovieCards.jsx").read_text(encoding="utf-8")
)
STYLES = (ROOT / "src" / "styles.css").read_text(encoding="utf-8")


class WatchedWatchlistUiTest(unittest.TestCase):
    def test_poster_controls_and_visibility_contract_exist(self):
        self.assertIn("function PosterStateControls", APP)
        self.assertIn("Mark as watched", APP)
        self.assertIn("Add to watchlist", APP)
        self.assertIn("poster-state-watched", APP)
        self.assertIn("poster-state-watchlist", APP)
        self.assertIn("owned ? onToggleWatched : undefined", APP)
        self.assertIn("onToggleWatchlist", APP)

    def test_library_exposes_viewing_state_filter(self):
        self.assertIn("All viewing states", APP)
        self.assertIn("Watched", APP)
        self.assertIn("Unwatched", APP)
        self.assertIn("Watchlist", APP)
        self.assertIn("viewingStateFilter", APP)

    def test_system_lists_are_protected_in_manager(self):
        self.assertIn("selectedList?.system_type", APP)
        self.assertIn("System list", APP)
        self.assertIn("Search TMDB to add to Watchlist", APP)

    def test_overlay_css_keeps_active_and_touch_controls_visible(self):
        self.assertIn(".poster-state-control", STYLES)
        self.assertIn(".poster-state-control-active", STYLES)
        self.assertIn("@media (hover: none)", STYLES)


if __name__ == "__main__":
    unittest.main()
