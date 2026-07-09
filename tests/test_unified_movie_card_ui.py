from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "App.jsx").read_text(encoding="utf-8")
MAIN = (ROOT / "src" / "main.jsx").read_text(encoding="utf-8")
COMPONENT = ROOT / "src" / "components" / "movie-card" / "MovieCard.jsx"
STYLES = ROOT / "src" / "components" / "movie-card" / "movieCard.css"
APP_STYLES = ROOT / "src" / "styles.css"


class UnifiedMovieCardUiTest(unittest.TestCase):
    def test_shared_movie_card_component_exists_and_is_imported(self):
        self.assertTrue(COMPONENT.exists())
        self.assertTrue(STYLES.exists())
        component_source = COMPONENT.read_text(encoding="utf-8")
        self.assertIn("export function UnifiedMovieCard", component_source)
        self.assertIn("export function UnifiedMoviePoster", component_source)
        self.assertIn("import './components/movie-card/movieCard.css';", MAIN)
        self.assertIn("UnifiedMovieCard", APP)

    def test_standard_card_contract_is_minimal_and_ownership_gated(self):
        component_source = COMPONENT.read_text(encoding="utf-8")
        self.assertIn("showPlayOverlay", component_source)
        self.assertIn("ownedBadge", component_source)
        self.assertIn("cornerControls", component_source)
        self.assertIn("movie-card-play-overlay", component_source)
        self.assertIn("unified-rating-row", component_source)
        self.assertIn("unified-title-long", component_source)
        self.assertNotIn("Find sources", component_source)
        self.assertNotIn("Correct metadata", component_source)

    def test_standard_poster_uses_uncropped_contain_framing(self):
        styles_source = STYLES.read_text(encoding="utf-8")
        self.assertIn(".unified-movie-poster img", styles_source)
        self.assertIn("object-fit: contain", styles_source)
        self.assertIn("grid-template-columns: var(--movie-card-poster-width) minmax(0, 1fr)", styles_source)
        self.assertIn("width: var(--movie-card-poster-width)", styles_source)
        self.assertIn("min-height: var(--movie-card-poster-height)", styles_source)
        self.assertIn(".movie-card-play-overlay:hover", styles_source)
        self.assertIn("var(--projector-gold)", styles_source)
        self.assertNotIn("overflow-wrap: anywhere", styles_source)

    def test_discover_unowned_cards_keep_owned_only_controls_gated(self):
        self.assertIn("showPlayOverlay={Boolean(owned)}", APP)
        self.assertIn("ownedBadge={Boolean(owned)}", APP)
        self.assertIn("onEditPoster={owned ? onEditPoster : undefined}", APP)
        self.assertIn("onToggleWatched={owned ? onToggleWatched : undefined}", APP)

    def test_unreleased_gate_applies_to_discover_and_home_but_not_indexer(self):
        self.assertIn("function isUnreleasedMovie(movie)", APP)
        self.assertIn("function formatReleaseDateLabel(value)", APP)
        self.assertIn("const unreleased = !owned && isUnreleasedMovie(movie);", APP)
        self.assertIn("statusLabel={owned ? (lowQuality ? 'Upgrade candidate' : '') : (unreleased ? 'Unreleased' : (followed ? 'Following' : 'Not in library'))}", APP)
        self.assertIn("{!unreleased && streamingAvailable && (", APP)
        self.assertIn("{!unreleased && (", APP)

        discover_card = APP[APP.index("function DiscoverMovieCard({"):APP.index("function MovieFactChips", APP.index("function DiscoverMovieCard({"))]
        self.assertIn("const unreleased = !owned && isUnreleasedMovie(movie);", discover_card)
        self.assertIn("!unreleased", discover_card)

        smart_card = APP[APP.index("function SmartMovieCard(props)"):APP.index("function MovieInspector", APP.index("function SmartMovieCard(props)"))]
        self.assertIn("const unreleased = !owned && isUnreleasedMovie(movie);", smart_card)

        inspector = APP[APP.index("function MovieInspector({"):APP.index("function PosterEditButton", APP.index("function MovieInspector({"))]
        self.assertIn("const unreleased = !owned && isUnreleasedMovie(movie);", inspector)
        self.assertIn("const releaseDateLabel = unreleased ? formatReleaseDateLabel(movie.release_date) : '';", inspector)
        self.assertIn("{releaseDateLabel && <span>Releases {releaseDateLabel}</span>}", inspector)
        self.assertIn("{!unreleased && streamingAvailable && (", inspector)
        self.assertIn("const selectedMovieWithDetails = selectedMovie ? { ...selectedMovie, release_date: selectedMovie.release_date || selectedDetails?.release_date || '' } : null;", APP)
        self.assertIn("selectedMovie={selectedMovieWithDetails}", APP)

        indexer_card = APP[APP.index("function IndexerMovieCard({"):APP.index("function MovieExpandedDetails", APP.index("function IndexerMovieCard({"))]
        self.assertNotIn("isUnreleasedMovie", indexer_card)
        self.assertIn("onFindTorrent(movie)", indexer_card)

    def test_expanded_details_show_release_date_only_for_unreleased_movies(self):
        expanded_details = APP[APP.index("function MovieExpandedDetails({"):APP.index("function PersonAvatar", APP.index("function MovieExpandedDetails({"))]
        self.assertIn("const releaseDate = movie?.release_date || details?.release_date || '';", expanded_details)
        self.assertIn("const releaseDateLabel = isUnreleasedMovie({ release_date: releaseDate }) ? formatReleaseDateLabel(releaseDate) : '';", expanded_details)
        self.assertIn("(details?.tagline || details?.runtime || releaseDateLabel)", expanded_details)
        self.assertIn("{releaseDateLabel && <div><span>Release date</span><strong>Releases {releaseDateLabel}</strong></div>}", expanded_details)

    def test_library_cards_keep_owned_badge_without_owned_status_label(self):
        library_card_start = APP.index("className={cx('library-movie-card'")
        library_card_end = APP.index("cornerControls={(", library_card_start)
        library_card_props = APP[library_card_start:library_card_end]
        self.assertIn("ownedBadge", library_card_props)
        self.assertNotIn("statusLabel={lowQuality ? 'Upgrade candidate' : 'Owned'}", library_card_props)

    def test_card_grids_keep_multiple_cards_without_too_narrow_cards(self):
        styles_source = STYLES.read_text(encoding="utf-8")
        self.assertIn("--movie-card-min-width: 460px", styles_source)
        self.assertIn("repeat(auto-fill, minmax(min(100%, var(--movie-card-min-width)), 1fr))", styles_source)

    def test_expanded_cards_move_rating_to_top_right(self):
        component_source = COMPONENT.read_text(encoding="utf-8")
        styles_source = STYLES.read_text(encoding="utf-8")
        self.assertIn("unified-expanded-rating", component_source)
        self.assertIn("{rating && expanded ? (", component_source)
        self.assertIn("{rating && !expanded ? (", component_source)
        self.assertIn(".unified-expanded-rating", styles_source)
        self.assertIn(".unified-movie-card-expanded", styles_source)
        self.assertIn("grid-column: 1 / -1", styles_source)

    def test_expanded_details_are_shared_and_include_runtime(self):
        self.assertIn("function MovieExpandedDetails", APP)
        self.assertNotIn("function DiscoverExpandedDetails", APP)
        self.assertGreaterEqual(APP.count("<MovieExpandedDetails"), 3)
        self.assertIn("details?.runtime", APP)
        self.assertIn("<span>Runtime</span>", APP)

    def test_library_expanded_card_removes_duplicate_metadata_strip(self):
        library_card_start = APP.index("function LibraryMovieCard")
        library_card_end = APP.index("function CollectionEditorModal", library_card_start)
        library_card_source = APP[library_card_start:library_card_end]
        self.assertNotIn('className="movie-expanded-meta"', library_card_source)
        self.assertNotIn("<span>Country</span>", library_card_source)
        self.assertNotIn("<span>Language</span>", library_card_source)
        self.assertNotIn("<span>Resolution</span>", library_card_source)
        self.assertNotIn("<span>Source</span>", library_card_source)

    def test_expanded_people_photos_use_approved_large_scale(self):
        styles_source = STYLES.read_text(encoding="utf-8") + APP_STYLES.read_text(encoding="utf-8")
        self.assertIn("--expanded-director-avatar-size: 96px", styles_source)
        self.assertIn("--expanded-cast-avatar-size: 90px", styles_source)
        self.assertIn("minmax(160px, 1fr)", styles_source)

    def test_expanded_people_photos_use_rectangular_portrait_framing(self):
        styles_source = APP_STYLES.read_text(encoding="utf-8")
        self.assertIn("--expanded-director-avatar-width: 96px", styles_source)
        self.assertIn("--expanded-director-avatar-height: 118px", styles_source)
        self.assertIn("--expanded-cast-avatar-width: 90px", styles_source)
        self.assertIn("--expanded-cast-avatar-height: 112px", styles_source)
        self.assertIn("border-radius: 10px", styles_source)

        expanded_avatar_styles = styles_source[
            styles_source.index(".movie-expanded-people-panel .director-person .person-avatar"):
            styles_source.index(".movie-expanded-people-panel .person-grid")
        ]
        self.assertIn("width: var(--expanded-director-avatar-width)", expanded_avatar_styles)
        self.assertIn("height: var(--expanded-director-avatar-height)", expanded_avatar_styles)
        self.assertIn("border-radius: 10px", expanded_avatar_styles)

        expanded_cast_avatar_styles = styles_source[
            styles_source.index(".movie-expanded-people-panel .person-card .person-avatar"):
            styles_source.index(".movie-expanded-people-panel .person-card strong")
        ]
        self.assertIn("width: var(--expanded-cast-avatar-width)", expanded_cast_avatar_styles)
        self.assertIn("height: var(--expanded-cast-avatar-height)", expanded_cast_avatar_styles)
        self.assertIn("border-radius: 10px", expanded_cast_avatar_styles)

    def test_indexer_expanded_card_uses_shared_content_width_and_action_row(self):
        styles_source = APP_STYLES.read_text(encoding="utf-8")
        self.assertIn(".indexer-card:has(.movie-expanded-details)", styles_source)
        indexer_expanded_styles = styles_source[
            styles_source.index(".indexer-card:has(.movie-expanded-details)"):
            styles_source.index(".indexer-poster-wrap", styles_source.index(".indexer-card:has(.movie-expanded-details)"))
        ]
        self.assertIn("grid-template-columns: 220px minmax(0, 1fr)", indexer_expanded_styles)
        self.assertNotIn("190px", indexer_expanded_styles)

        self.assertIn("indexer-action-row indexer-action-row-expanded", APP)
        self.assertNotIn("indexer-action-rail indexer-action-rail-expanded", APP)
        self.assertIn(".indexer-action-row-expanded", styles_source)
        action_row_styles = styles_source[
            styles_source.index(".indexer-action-row-expanded"):
            styles_source.index(".indexer-selected-meta", styles_source.index(".indexer-action-row-expanded"))
        ]
        self.assertIn("display: flex", action_row_styles)
        self.assertIn("flex-wrap: wrap", action_row_styles)


if __name__ == "__main__":
    unittest.main()
