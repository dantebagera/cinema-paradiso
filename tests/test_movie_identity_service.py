import unittest

from services.movie_identity import (
    group_identity_records,
    normalize_movie_title,
    ownership_keys,
    same_public_identity,
)


class MovieIdentityServiceTest(unittest.TestCase):
    def test_normalize_movie_title_preserves_existing_matching_rules(self):
        self.assertEqual(normalize_movie_title("The E.T. Movie"), "et movie")
        self.assertEqual(normalize_movie_title("  A   Quiet Place  "), "quiet place")
        self.assertEqual(normalize_movie_title("Spider-Man: Homecoming"), "spider man homecoming")
        self.assertEqual(normalize_movie_title("E. T. the Extra-Terrestrial"), "et the extra terrestrial")
        self.assertEqual(normalize_movie_title(""), "")

    def test_same_public_identity_requires_matching_normalized_title_and_compatible_year(self):
        self.assertTrue(same_public_identity("The Thing", "1982", "Thing", "1982"))
        self.assertTrue(same_public_identity("Alien", "", "Alien", "1979"))
        self.assertFalse(same_public_identity("Alien", "1979", "Aliens", "1986"))
        self.assertFalse(same_public_identity("The Thing", "1982", "Thing", "2011"))

    def test_ownership_keys_preserve_stable_id_then_title_order(self):
        self.assertEqual(
            ownership_keys({
                "tmdb_id": 601,
                "imdb_id": "TT0083866",
                "plex_guid": "plex://movie/123",
                "title": "E.T.",
                "year": 1982,
            }),
            [
                "tmdb:601",
                "imdb:tt0083866",
                "plex:plex://movie/123",
                "title:et|1982",
            ],
        )

    def test_group_identity_records_connects_manual_tmdb_and_plex_title_identity(self):
        records = [
            {
                "path": "E:/Movies/Batteries Original.mkv",
                "plex_title": "*batteries not included",
                "plex_year": "1987",
            },
            {
                "path": "E:/Movies/Batteries Copy.mkv",
                "tmdb_id": "11548",
                "title": "*batteries not included",
                "year": "1987",
            },
        ]

        groups = group_identity_records(records)

        self.assertEqual(len(groups), 1)
        self.assertEqual({item["path"] for item in groups[0]}, {
            "E:/Movies/Batteries Original.mkv",
            "E:/Movies/Batteries Copy.mkv",
        })

    def test_group_identity_records_does_not_merge_conflicting_strong_ids(self):
        records = [
            {"path": "one.mkv", "tmdb_id": "1", "title": "Same Title", "year": "2000"},
            {"path": "two.mkv", "tmdb_id": "2", "title": "Same Title", "year": "2000"},
        ]

        groups = group_identity_records(records)

        self.assertEqual(len(groups), 2)


if __name__ == "__main__":
    unittest.main()
