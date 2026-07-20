from pathlib import Path
import unittest


class LibraryExpandedDetailsUiTest(unittest.TestCase):
    def test_library_cards_render_the_canonical_plot_before_deferred_details(self):
        library_source = (
            Path(__file__).resolve().parents[1]
            / 'src'
            / 'features'
            / 'library'
            / 'LibraryWorkspace.jsx'
        ).read_text(encoding='utf-8')

        shared_cards = (
            Path(__file__).resolve().parents[1]
            / 'src'
            / 'components'
            / 'SharedMovieCards.jsx'
        ).read_text(encoding='utf-8')
        details_api = (
            Path(__file__).resolve().parents[1]
            / 'src'
            / 'api'
            / 'movieDetails.js'
        ).read_text(encoding='utf-8')

        self.assertIn('canonical.summary || canonical.plot || details?.summary || details?.plot', shared_cards)
        self.assertIn('async function loadLibraryDetails(item)', library_source)
        self.assertIn('fetchCanonicalMovieDetails(item, item)', library_source)
        self.assertIn('/api/library/details?path=${encodeURIComponent(path)}', details_api)
        self.assertIn('if (next) loadLibraryDetails(item);', library_source)

    def test_owned_cards_fetch_deferred_details_through_the_shared_sql_contract(self):
        root = Path(__file__).resolve().parents[1] / 'src' / 'features'
        movie_lists = (root / 'movie-lists' / 'MovieListsWorkspace.jsx').read_text(encoding='utf-8')
        discover = (root / 'discover' / 'DiscoverWorkspace.jsx').read_text(encoding='utf-8')
        ai_control = (root / 'ai-control' / 'AIControlWorkspace.jsx').read_text(encoding='utf-8')

        self.assertIn('if (nextKey) loadMovieListDetails(row);', movie_lists)
        self.assertIn('fetchCanonicalMovieDetails(movie, owned)', movie_lists)
        self.assertIn('if (nextKey) loadDiscoverDetails(movie, owned);', discover)
        self.assertIn('fetchCanonicalMovieDetails(movie, owned)', discover)
        self.assertIn('if (nextKey) loadAiControlDetails(movie, owned);', ai_control)
        self.assertIn('fetchCanonicalMovieDetails(movie, owned)', ai_control)

    def test_every_movie_detail_cache_subscribes_to_catalog_generation_changes(self):
        root = Path(__file__).resolve().parents[1]
        sources = [
            root / 'src' / 'App.jsx',
            root / 'src' / 'features' / 'library' / 'LibraryWorkspace.jsx',
            root / 'src' / 'features' / 'discover' / 'DiscoverWorkspace.jsx',
            root / 'src' / 'features' / 'movie-lists' / 'MovieListsWorkspace.jsx',
            root / 'src' / 'features' / 'ai-control' / 'AIControlWorkspace.jsx',
        ]
        for source_path in sources:
            with self.subTest(source=source_path.name):
                source = source_path.read_text(encoding='utf-8')
                self.assertIn('CATALOG_GENERATION_CHANGED_EVENT', source)
                self.assertIn('window.addEventListener(CATALOG_GENERATION_CHANGED_EVENT', source)


if __name__ == '__main__':
    unittest.main()
