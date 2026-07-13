from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "App.jsx"
SHARED_CARDS = ROOT / "src" / "components" / "SharedMovieCards.jsx"
EDITOR = ROOT / "src" / "components" / "PosterEditorModal.jsx"
MAIN = ROOT / "src" / "main.jsx"
STYLES = ROOT / "src" / "styles" / "posterEditor.css"


class PosterEditorUiTest(unittest.TestCase):
    def test_editor_uses_durable_poster_apis(self):
        editor = EDITOR.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")

        self.assertIn("/api/library/posters?path=", editor)
        self.assertIn("/api/library/posters/select", editor)
        self.assertIn("/api/library/posters/upload", editor)
        self.assertIn("/api/library/posters/reset", editor)
        self.assertIn('accept="image/jpeg,image/png,image/webp"', editor)
        self.assertIn("posterEditor.css", main)

    def test_editor_presents_tmdb_first_and_upload_as_secondary(self):
        editor = EDITOR.read_text(encoding="utf-8")

        self.assertIn("Choose from TMDB", editor)
        self.assertIn("tmdbOptions", editor)
        self.assertIn("plexOptions", editor)
        self.assertLess(editor.index("Choose from TMDB"), editor.index("Plex poster"))
        self.assertIn("Or use your own image", editor)
        self.assertIn("data.providers?.tmdb?.message", editor)

    def test_library_editor_is_wired_only_to_movie_cards(self):
        app = APP.read_text(encoding="utf-8")

        self.assertIn("onEditPoster", app)
        self.assertIn("<PosterEditorModal", app)
        self.assertIn("mode === 'movie' ? (", app)
        self.assertNotIn("function LibraryFileRow({ item, expanded, onToggle, onPlay, onFindTorrent, onRename, onDelete, onEditPoster", app)
        self.assertNotIn("function CleanupFileRow({ item, selected, selectable, badge, onToggle, onDelete, actions, onEditPoster", app)

    def test_owned_home_and_discover_movies_get_editor_but_unowned_movies_do_not(self):
        app = APP.read_text(encoding="utf-8")

        self.assertIn("onEditPoster={owned ? onEditPoster : undefined}", app)
        self.assertIn("onEditPoster={owned ? () => onEditPoster(owned, movie) : undefined}", app)
        self.assertIn("onEditPoster={selectedOwnership ? () => onEditPoster(selectedOwnership, selectedMovie) : undefined}", app)
        self.assertIn("owned?.poster_url", app)
        self.assertIn("updateOwnedPoster", app)
        self.assertEqual(
            app.count("onEditPoster={owned ? () => setPosterEditor({ path: owned.path, title: movie.title }) : undefined}"),
            3,
        )
        self.assertIn("activeTab === 'explore'", app)
        self.assertIn("activeTab === 'browse'", app)
        self.assertIn("activeTab === 'pick'", app)

    def test_editing_uses_poster_pencil_overlays_instead_of_full_card_buttons(self):
        app = APP.read_text(encoding="utf-8") + SHARED_CARDS.read_text(encoding="utf-8")
        styles = (ROOT / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("function PosterEditButton", app)
        self.assertIn("<Pencil size={17}", app)
        self.assertIn("aria-label={`Edit poster for ${title || 'movie'}`}", app)
        self.assertIn("event.stopPropagation()", app)
        self.assertIn("onEditPoster={owned ? () =>", app)
        self.assertIn("<PosterEditButton title={identity.title}", app)
        self.assertNotIn("<Film size={15} /> Edit poster", app)
        self.assertIn(".poster-edit-trigger", styles)
        self.assertIn("@media (hover: none)", styles)
        self.assertIn("@media (max-width: 640px)", styles)
        self.assertIn(".poster:hover .poster-edit-trigger", styles)

    def test_library_duplicate_updates_use_conflict_safe_shared_identity_helper(self):
        app = APP.read_text(encoding="utf-8")

        self.assertIn("applyPosterOverrideToLibraryItems", app)
        self.assertNotIn("const selectedKeys = new Set(movieIdentityKeys(moviePayload(item)))", app)

    def test_editor_styles_preserve_black_gold_and_mobile_layout(self):
        styles = STYLES.read_text(encoding="utf-8")

        self.assertIn("var(--projector-gold)", styles)
        self.assertIn("var(--border)", styles)
        self.assertIn("@media (max-width: 640px)", styles)


if __name__ == "__main__":
    unittest.main()
