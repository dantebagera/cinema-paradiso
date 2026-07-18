from pathlib import Path
import unittest


class LibraryExpandedDetailsUiTest(unittest.TestCase):
    def test_expanded_library_cards_read_persisted_sql_details_before_live_tmdb(self):
        source = (
            Path(__file__).resolve().parents[1]
            / 'src'
            / 'features'
            / 'library'
            / 'LibraryWorkspace.jsx'
        ).read_text(encoding='utf-8')

        self.assertIn('async function loadLibraryDetails(item)', source)
        self.assertIn('/api/library/details?path=${encodeURIComponent(item.path)}', source)
        self.assertIn('if (next) loadLibraryDetails(item);', source)
        self.assertIn('openTrailer && !details.loading && !details.trailer_url', source)


if __name__ == '__main__':
    unittest.main()
