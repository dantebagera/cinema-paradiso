from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DiscoverHoverUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.styles = (ROOT / "src" / "styles.css").read_text(encoding="utf-8")

    def test_discover_card_buttons_do_not_translate_on_hover(self):
        self.assertRegex(
            self.styles,
            re.compile(
                r"\.discover-movie-card\s+\.btn:hover,\s*"
                r"\.indexer-card\s+\.btn:hover\s*\{[^}]*transform:\s*none;",
                re.S,
            ),
        )

    def test_discover_cards_do_not_apply_card_level_hover_styles(self):
        self.assertNotRegex(self.styles, r"\.discover-movie-card:hover")
        self.assertNotRegex(self.styles, r"\.indexer-card:hover")
        self.assertRegex(
            self.styles,
            re.compile(
                r"\.discover-card-expanded\s*\{[^}]*border-color:\s*#d4af375a;[^}]*box-shadow:\s*var\(--shadow-card\);",
                re.S,
            ),
        )


if __name__ == "__main__":
    unittest.main()
