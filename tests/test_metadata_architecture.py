import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class MetadataArchitectureTest(unittest.TestCase):
    def test_filename_only_file_is_not_accepted_movie_metadata(self):
        self.assertTrue(hasattr(app, "_build_canonical_metadata"), "canonical metadata builder is required")

        canonical = app._build_canonical_metadata(
            {
                "path": "E:/Movies/Mystery.File.2001.1080p.mkv",
                "parsed_title": "mystery file",
                "parsed_year": "2001",
            }
        )

        self.assertFalse(canonical["accepted"])
        self.assertEqual(canonical["status"], "unmatched")
        self.assertEqual(canonical["title"], "")

    def test_recent_filename_only_file_is_pending_metadata_not_unmatched(self):
        self.assertTrue(hasattr(app, "_build_canonical_metadata"), "canonical metadata builder is required")

        with patch.object(app.time, "time", return_value=1_700_000_000):
            canonical = app._build_canonical_metadata(
                {
                    "path": "E:/Movies/Swapped.2026.1080p.mkv",
                    "parsed_title": "swapped",
                    "parsed_year": "2026",
                    "added_time": 1_699_999_900,
                }
            )

        self.assertFalse(canonical["accepted"])
        self.assertEqual(canonical["status"], "pending")
        self.assertEqual(canonical["title"], "")

    def test_old_filename_only_file_stays_unmatched(self):
        self.assertTrue(hasattr(app, "_build_canonical_metadata"), "canonical metadata builder is required")

        with patch.object(app.time, "time", return_value=1_700_000_000):
            canonical = app._build_canonical_metadata(
                {
                    "path": "E:/Movies/Swapped.2026.1080p.mkv",
                    "parsed_title": "swapped",
                    "parsed_year": "2026",
                    "added_time": 1_699_990_000,
                }
            )

        self.assertFalse(canonical["accepted"])
        self.assertEqual(canonical["status"], "unmatched")

    def test_manual_tmdb_match_wins_and_is_durable(self):
        self.assertTrue(hasattr(app, "AppMetadataStore"), "app metadata store is required")
        self.assertTrue(hasattr(app, "_build_canonical_metadata"), "canonical metadata builder is required")

        with tempfile.TemporaryDirectory() as tmp:
            store = app.AppMetadataStore(Path(tmp))
            stored = store.apply_tmdb_match(
                "E:/Movies/Wrong.Name.1979.mkv",
                {
                    "tmdb_id": "348",
                    "title": "Alien",
                    "year": "1979",
                    "poster_url": "poster.jpg",
                    "genres": ["Horror", "Sci-Fi"],
                    "tmdb_rating": "8.2",
                    "tmdb_vote_count": 12400,
                    "plot": "A commercial crew encounters a hostile lifeform.",
                },
            )

            reloaded = app.AppMetadataStore(Path(tmp))
            canonical = app._build_canonical_metadata(
                {
                    "path": "E:/Movies/Wrong.Name.1979.mkv",
                    "parsed_title": "wrong name",
                    "parsed_year": "1979",
                },
                plex_data={"plex_title": "Wrong Name", "plex_year": "1979"},
                tmdb_data=reloaded.get_tmdb_metadata("348"),
                manual_match=reloaded.get_manual_match("E:/Movies/Wrong.Name.1979.mkv"),
            )

        self.assertEqual(stored["tmdb_id"], "348")
        self.assertTrue(canonical["accepted"])
        self.assertEqual(canonical["source"], "manual_tmdb")
        self.assertEqual(canonical["title"], "Alien")
        self.assertEqual(canonical["tmdb_id"], "348")
        self.assertEqual(canonical["tmdb_vote_count"], 12400)

    def test_manual_tmdb_match_is_accepted_when_cached_payload_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = app.AppMetadataStore(Path(tmp))
            path = "E:/Movies/Happily.Ever.After.2004.mkv"
            store.apply_tmdb_match(path, {"tmdb_id": "14653", "title": "Happily Ever After", "year": "2004"})
            tmdb_data = store._read_json(store.tmdb_metadata_file, {"movies": {}})
            tmdb_data["movies"].pop("14653", None)
            store._write_json(store.tmdb_metadata_file, tmdb_data)
            snapshot = store.snapshot()

            file_facts = {
                "path": path,
                "filename": "Happily.Ever.After.2004.mkv",
                "parsed_title": "happily ever after",
                "parsed_year": "2004",
            }
            tmdb = app._tmdb_metadata_for_file(file_facts, store=store, snapshot=snapshot)
            canonical = app._build_canonical_metadata(
                file_facts,
                tmdb_data=tmdb,
                manual_match=store.get_manual_match_from_snapshot(path, snapshot),
            )

        self.assertEqual(tmdb["tmdb_id"], "14653")
        self.assertEqual(tmdb["title"], "Happily Ever After")
        self.assertTrue(canonical["accepted"])
        self.assertEqual(canonical["source"], "manual_tmdb")

    def test_auto_tmdb_exact_title_and_year_is_accepted(self):
        self.assertTrue(hasattr(app, "_build_canonical_metadata"), "canonical metadata builder is required")

        canonical = app._build_canonical_metadata(
            {
                "path": "E:/Movies/Alien.1979.1080p.mkv",
                "parsed_title": "alien",
                "parsed_year": "1979",
            },
            tmdb_data={
                "tmdb_id": "348",
                "title": "Alien",
                "year": "1979",
                "genres": ["Horror"],
                "plot": "A hostile lifeform stalks a ship.",
                "match_source": "auto_tmdb",
            },
        )

        self.assertTrue(canonical["accepted"])
        self.assertEqual(canonical["status"], "accepted")
        self.assertEqual(canonical["source"], "tmdb")
        self.assertEqual(canonical["title"], "Alien")

    def test_plex_tmdb_title_year_mismatch_is_conflict(self):
        self.assertTrue(hasattr(app, "_build_canonical_metadata"), "canonical metadata builder is required")

        canonical = app._build_canonical_metadata(
            {
                "path": "E:/Movies/Alien.1979.1080p.mkv",
                "parsed_title": "alien",
                "parsed_year": "1979",
            },
            plex_data={"plex_title": "Alien", "plex_year": "1979"},
            tmdb_data={
                "tmdb_id": "679",
                "title": "Aliens",
                "year": "1986",
                "match_source": "auto_tmdb",
            },
        )

        self.assertFalse(canonical["accepted"])
        self.assertEqual(canonical["status"], "conflict")


if __name__ == "__main__":
    unittest.main()
