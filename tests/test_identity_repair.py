import unittest

from services.identity_repair import build_identity_repair


class IdentityRepairTest(unittest.TestCase):
    def test_preserves_accepted_id_and_backfills_title_from_manual_match(self):
        result = build_identity_repair(
            files={"movie": {
                "path": "E:/Movies/Alien.mkv",
                "metadata_status": "accepted",
                "tmdb_id": "348",
                "parsed_title": "Wrong fallback",
                "parsed_year": "1979",
            }},
            manual_matches={"movie": {"title": "Alien", "year": "1979", "tmdb_id": "348"}},
            tmdb_movies={},
            plex_files={},
        )

        repaired = result["files"]["movie"]
        self.assertEqual(repaired["identity_status"], "accepted")
        self.assertEqual(repaired["identity_title"], "Alien")
        self.assertEqual(repaired["identity_year"], "1979")
        self.assertEqual(repaired["tmdb_id"], "348")
        self.assertEqual(result["report"]["preserved"], 1)
        self.assertEqual(result["report"]["backfilled"], 1)

    def test_missing_provider_details_marks_enrichment_incomplete_not_unmatched(self):
        result = build_identity_repair(
            files={"movie": {
                "metadata_status": "accepted",
                "display_provider": "tmdb",
                "tmdb_id": "348",
                "parsed_title": "Alien",
                "parsed_year": "1979",
            }},
            manual_matches={},
            tmdb_movies={},
            plex_files={},
        )

        repaired = result["files"]["movie"]
        self.assertEqual(repaired["identity_status"], "accepted")
        self.assertEqual(repaired["enrichment_status"], "incomplete")
        self.assertEqual(result["report"]["unmatched"], 0)

    def test_genuinely_unmatched_record_stays_unmatched(self):
        result = build_identity_repair(
            files={"movie": {"metadata_status": "unmatched", "parsed_title": "Unknown"}},
            manual_matches={},
            tmdb_movies={},
            plex_files={},
        )

        self.assertEqual(result["files"]["movie"]["identity_status"], "unmatched")
        self.assertEqual(result["report"]["unmatched"], 1)


if __name__ == "__main__":
    unittest.main()
