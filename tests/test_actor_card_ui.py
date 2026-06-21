from pathlib import Path
import re
import unittest


STYLES = Path(__file__).resolve().parents[1] / "src" / "styles.css"


class ActorCardUiTest(unittest.TestCase):
    def test_actor_cards_are_wide_enough_and_show_complete_names(self):
        styles = STYLES.read_text(encoding="utf-8")

        self.assertIn("grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));", styles)
        rule = re.search(r"\.person-card strong \{(.*?)\}", styles, flags=re.S)
        self.assertIsNotNone(rule)
        self.assertIn("overflow: visible", rule.group(1))
        self.assertIn("overflow-wrap: anywhere", rule.group(1))
        self.assertIn("text-overflow: clip", rule.group(1))
        self.assertIn("white-space: normal", rule.group(1))


if __name__ == "__main__":
    unittest.main()
