from pathlib import Path
import re
import unittest


APP_JSX = Path(__file__).resolve().parents[1] / "src" / "App.jsx"


class LibraryActionUxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP_JSX.read_text(encoding="utf-8")

    def test_library_daily_actions_are_file_scan_and_unmatched_review(self):
        self.assertIn("Rescan Files", self.source)
        self.assertIn("Review Unmatched", self.source)
        self.assertNotIn("Fetch Metadata", self.source)
        self.assertNotIn("need metadata", self.source)

    def test_library_action_row_does_not_expose_plex_sync(self):
        match = re.search(
            r'<div className="library-action-row">(.*?)<button type="button" className="btn btn-secondary" onClick=\{\(\) => setListEditor',
            self.source,
            flags=re.S,
        )
        self.assertIsNotNone(match, "Library action row should be present")
        self.assertNotIn("Sync Plex", match.group(1))
        self.assertNotIn("force_plex", match.group(1))
        self.assertNotIn("Fetch Metadata", match.group(1))

    def test_unmatched_shortcut_targets_cleanup_unmatched_tab(self):
        self.assertIn("reviewUnmatchedMetadata", self.source)
        self.assertIn("setCleanupInitialTab('unmatched')", self.source)
        self.assertIn("initialTab = 'duplicates'", self.source)

    def test_settings_uses_clear_plex_cache_language(self):
        self.assertIn('label="Refresh Plex Cache"', self.source)
        self.assertIn('label="Force Plex Scan"', self.source)
        self.assertIn("Plex cache refreshed.", self.source)

    def test_match_modal_submit_buttons_have_aligned_action_class(self):
        styles = (APP_JSX.parents[0] / "styles.css").read_text(encoding="utf-8")

        self.assertIn("cleanup-match-submit", self.source)
        self.assertIn(".cleanup-match-submit", styles)
        self.assertIn("grid-column: 1 / -1", styles)
        self.assertIn(".cleanup-match-form .dialog-field", styles)
        self.assertIn("min-width: 0", styles)

    def test_settings_exposes_separate_adult_metadata_and_library_controls(self):
        self.assertIn("showAdultMovies: true", self.source)
        self.assertIn("includeAdult: false", self.source)
        self.assertIn("Show adult movies in Movie View", self.source)
        self.assertIn("Include adult titles in metadata search", self.source)
        self.assertIn("show_adult_movies", self.source)
        self.assertIn("include_adult", self.source)

    def test_movie_view_hides_adult_titles_without_affecting_file_view(self):
        self.assertIn("showAdultMovies", self.source)
        self.assertIn("mode === 'movie' && !showAdultMovies && canonical.adult", self.source)
        self.assertNotIn("mode === 'file' && !showAdultMovies && canonical.adult", self.source)

    def test_discover_search_forces_adult_titles_off(self):
        self.assertIn("include_adult=false", self.source)
        self.assertIn("metadata_context: 'unmatched'", self.source)

    def test_unmatched_tmdb_search_sends_title_and_year_separately(self):
        self.assertIn("tmdbParams.set('q', query || matchModal.item.filename)", self.source)
        self.assertIn("tmdbParams.set('year', matchModal.year.trim())", self.source)
        self.assertNotIn("`${matchModal.title || ''} ${matchModal.year || ''}`", self.source)

    def test_pending_metadata_is_separate_from_unmatched_count(self):
        self.assertIn("label=\"Metadata pending\"", self.source)
        self.assertIn("metadata_status === 'pending'", self.source)
        self.assertIn("item.metadata_status !== 'pending'", self.source)
        self.assertIn('<option value="pending">Pending metadata</option>', self.source)
        self.assertIn("if (item.metadata_status === 'pending') return 'Pending metadata';", self.source)


if __name__ == "__main__":
    unittest.main()
