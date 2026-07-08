from pathlib import Path
import re
import unittest


APP_JSX = Path(__file__).resolve().parents[1] / "src" / "App.jsx"
LIBRARY_UTILS = Path(__file__).resolve().parents[1] / "src" / "utils" / "libraryUtils.js"
CLEANUP_UTILS = Path(__file__).resolve().parents[1] / "src" / "utils" / "cleanupUtils.js"


class LibraryActionUxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP_JSX.read_text(encoding="utf-8")
        cls.library_utils_source = LIBRARY_UTILS.read_text(encoding="utf-8")
        cls.cleanup_utils_source = CLEANUP_UTILS.read_text(encoding="utf-8")

    def test_library_daily_actions_are_file_scan_and_unmatched_review(self):
        self.assertIn("Rescan Files", self.source)
        self.assertIn("Review Unmatched", self.source)
        self.assertIn("/api/library?force_scan=1", self.source)
        self.assertIn("/api/library/reconcile", self.source)
        self.assertIn("cp-library-reconciled", self.source)
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
        self.assertIn("mode === 'movie' && !showAdultMovies && canonical.adult", self.library_utils_source)
        self.assertNotIn("mode === 'file' && !showAdultMovies && canonical.adult", self.library_utils_source)

    def test_library_view_model_safe_page_is_bound_for_pagination(self):
        self.assertRegex(
            self.source,
            r"const \{\s*filteredItems,\s*totalPages,\s*safePage,\s*pageStart,\s*pageEnd,\s*visibleItems,\s*stats\s*\} = useMemo\(\(\) => buildLibraryViewModel",
        )
        self.assertIn("page={safePage}", self.source)

    def test_discover_search_forces_adult_titles_off(self):
        self.assertIn("include_adult=false", self.source)
        self.assertIn("metadata_context: 'unmatched'", self.source)

    def test_unmatched_tmdb_search_sends_title_and_year_separately(self):
        self.assertIn("tmdbParams.set('q', query || matchModal.item.filename)", self.source)
        self.assertIn("tmdbParams.set('year', matchModal.year.trim())", self.source)
        self.assertNotIn("`${matchModal.title || ''} ${matchModal.year || ''}`", self.source)

    def test_plex_search_resolves_missing_keys_and_offers_scan_retry(self):
        self.assertIn("path: matchModal.item.path", self.source)
        self.assertIn("plex_item_not_indexed", self.source)
        self.assertIn("Request Plex scan", self.source)
        self.assertIn("Retry Plex lookup", self.source)
        self.assertNotIn("No Plex rating key for this file", self.source)

    def test_pending_metadata_is_separate_from_unmatched_count(self):
        self.assertIn("label=\"Metadata pending\"", self.source)
        self.assertIn("metadata_status === 'pending'", self.source)
        self.assertIn("item.metadata_status !== 'pending'", self.source)
        self.assertIn('<option value="pending">Pending metadata</option>', self.source)
        self.assertIn("if (item.metadata_status === 'pending') return 'Pending metadata';", self.cleanup_utils_source)

    def test_home_health_uses_backend_cleanup_counts(self):
        self.assertIn("value: stats?.duplicate_groups", self.source)
        self.assertIn("value: stats?.unmatched_count", self.source)
        self.assertIn("value: stats?.identity_review_count", self.source)
        self.assertNotIn("label: 'Plex matched'", self.source)
        self.assertNotIn("value: stats?.dup_groups", self.source)

    def test_movie_view_exposes_local_metadata_correction(self):
        self.assertIn("Correct metadata", self.source)
        self.assertIn("MetadataCorrectionModal", self.source)
        self.assertIn("Reset to provider metadata", self.source)

    def test_library_and_discover_expose_bulk_add_to_list_selection(self):
        self.assertIn("library-selection-checkbox", self.source)
        self.assertIn("Select all filtered", self.source)
        self.assertIn("discover-selection-checkbox", self.source)
        self.assertIn("addMoviesToList", self.source)
        self.assertIn("/movies/bulk", self.source)

    def test_library_list_filter_warns_when_list_movies_are_missing(self):
        self.assertIn("listLibraryCoverage", self.source)
        self.assertIn("listMissingCoverage", self.source)
        self.assertIn("list-missing-warning", self.source)
        self.assertIn("list movies found in Library", self.source)
        self.assertIn("Missing:", self.source)

    def test_lists_popup_exposes_select_all_and_copy_export(self):
        self.assertIn("list-select-all", self.source)
        self.assertIn("Copy selected to", self.source)
        self.assertIn("/api/library/export-jobs", self.source)
        self.assertIn("ExportCopyDialog", self.source)

    def test_bulk_add_to_list_falls_back_when_backend_route_is_missing(self):
        self.assertIn("bulkError.status === 404", self.source)
        self.assertIn("addMoviePayloadsIndividually", self.source)
        self.assertIn("selectedPayloads.length", self.source)
        self.assertIn("list-editor-error", self.source)

    def test_fetch_json_preserves_status_for_non_json_errors(self):
        self.assertIn("response.text()", self.source)
        self.assertIn("Request failed: ${response.status}", self.source)
        self.assertIn("Failed to parse response JSON", self.source)

    def test_copy_dialog_has_folder_browser_and_library_has_reset_filters(self):
        self.assertIn("FolderBrowserDialog", self.source)
        self.assertIn("/api/system/folders", self.source)
        self.assertIn("Browse...", self.source)
        self.assertIn("Reset filters", self.source)
        self.assertIn("resetAllLibraryFilters", self.source)

    def test_library_chrome_is_condensed_without_removing_second_header(self):
        library_source = self.source[
            self.source.index("function LibraryWorkspace"):
            self.source.index("function LibraryPagination")
        ]
        self.assertIn("activeSection !== 'home' && activeSection !== 'library'", self.source)
        self.assertIn('className="library-header"', library_source)
        self.assertNotIn('className="library-stat-strip"', library_source)
        self.assertIn('className="library-search-panel"', library_source)
        self.assertIn("filtersOpen", library_source)
        self.assertIn("Open Filters", library_source)
        self.assertNotIn('className="library-results-meta"', library_source)

    def test_cleanup_help_and_settings_do_not_render_shared_topbar(self):
        topbar_condition = self.source[:self.source.index("function TopBar")]
        self.assertIn("activeSection !== 'cleanup'", topbar_condition)
        self.assertIn("activeSection !== 'help'", topbar_condition)
        self.assertIn("activeSection !== 'settings'", topbar_condition)

    def test_downloads_keeps_topbar_without_search_or_file_badge(self):
        topbar_source = self.source[
            self.source.index("function TopBar"):
            self.source.index("function DownloadsWorkspace")
        ]
        self.assertIn("const isDownloads = activeSection === 'downloads';", topbar_source)
        self.assertIn("!isDownloads && (", topbar_source)
        self.assertIn("downloads-title-credit", topbar_source)
        self.assertNotIn("activeSection !== 'downloads'", self.source[:self.source.index("function TopBar")])

    def test_discover_moves_search_below_tabs_without_shared_topbar(self):
        discover_source = self.source[
            self.source.index("function DiscoverWorkspace"):
            self.source.index("function DiscoverResultGrid")
        ]
        self.assertIn("activeSection !== 'discover'", self.source[:self.source.index("function TopBar")])
        self.assertIn('className="discover-search-panel"', discover_source)
        self.assertIn("activeTab !== 'pick'", discover_source)
        self.assertIn("activeTab === 'browse' ? browseQuery : tmdbQuery", discover_source)
        self.assertIn("activeTab === 'browse' ? setBrowseQuery", discover_source)
        self.assertIn("loadBrowse({ query: browseQuery })", discover_source)
        self.assertIn("loadDiscover({ append: false, search: tmdbQuery, page: 1 })", discover_source)
        self.assertIn("Search", discover_source)

    def test_settings_prowlarr_exposes_trusted_release_indexers(self):
        self.assertIn("trusted_release_indexers", self.source)
        self.assertIn("TrustedIndexerDialog", self.source)
        self.assertIn("trusted-indexer-summary", self.source)
        self.assertIn('label="Trusted indexers"', self.source)
        self.assertIn("const saved = await onSave();", self.source)
        self.assertIn("if (saved) onClose();", self.source)
        self.assertIn("Trusted release watchlist indexers", self.source)
        self.assertIn("No trusted indexers selected", self.source)

    def test_source_search_loading_warns_that_prowlarr_indexers_can_take_time(self):
        self.assertIn("Connecting to Prowlarr indexers", self.source)
        self.assertIn("This may take some time", self.source)
        self.assertIn("/api/explore/search/jobs", self.source)
        self.assertIn("Still searching", self.source)


if __name__ == "__main__":
    unittest.main()
