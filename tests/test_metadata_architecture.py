import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class MetadataArchitectureTest(unittest.TestCase):
    def setUp(self):
        self.original_tmdb_key = app._tmdb_key
        app._tmdb_key = "tmdb-key"

    def tearDown(self):
        app._tmdb_key = self.original_tmdb_key

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

    def test_recent_filename_only_file_is_not_pending_when_copy_is_stable(self):
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
        self.assertEqual(canonical["status"], "unmatched")

    def test_explicit_copying_state_is_pending(self):
        canonical = app._build_canonical_metadata({
            "path": "E:/Movies/Swapped.2026.1080p.mkv",
            "parsed_title": "swapped",
            "parsed_year": "2026",
            "ingest_status": "pending",
        })

        self.assertFalse(canonical["accepted"])
        self.assertEqual(canonical["status"], "pending")

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

    def test_refresh_auto_accepts_a_unique_yearless_exact_title(self):
        file_facts = {
            "path": "E:/Movies/The Phantom Menace.mp4",
            "filename": "The Phantom Menace.mp4",
            "parsed_title": "The Phantom Menace",
            "parsed_year": "",
        }
        candidates = [{
            "tmdb_id": "661852",
            "title": "The Phantom Menace",
            "year": "2020",
            "provider_rank": 1,
        }]

        with tempfile.TemporaryDirectory() as tmp:
            with patch("app._identity_tmdb_candidates", return_value=candidates):
                result = app._tmdb_metadata_for_file(
                    file_facts,
                    store=app.AppMetadataStore(Path(tmp)),
                    refresh=True,
                )

        self.assertEqual(result["tmdb_id"], "661852")
        self.assertEqual(result["match_source"], "auto_tmdb")

    def test_refresh_uses_plex_title_and_year_as_corroborating_evidence(self):
        file_facts = {
            "path": "E:/Movies/The Phantom Menace.mp4",
            "filename": "The Phantom Menace.mp4",
            "parsed_title": "The Phantom Menace",
            "parsed_year": "",
        }
        candidates = [
            {"tmdb_id": "661852", "title": "The Phantom Menace", "year": "2020", "provider_rank": 1},
            {
                "tmdb_id": "1893",
                "title": "Star Wars: Episode I - The Phantom Menace",
                "year": "1999",
                "provider_rank": 1,
            },
        ]
        accepted = {
            "tmdb_id": "1893",
            "title": "Star Wars: Episode I - The Phantom Menace",
            "year": "1999",
            "match_source": "auto_tmdb",
        }

        with tempfile.TemporaryDirectory() as tmp:
            with patch("app._identity_tmdb_candidates", return_value=candidates):
                with patch("app._fetch_tmdb_metadata_by_id", return_value=accepted):
                    result = app._tmdb_metadata_for_file(
                        file_facts,
                        plex_data={
                            "plex_title": "Star Wars: Episode I - The Phantom Menace",
                            "plex_year": "1999",
                        },
                        store=app.AppMetadataStore(Path(tmp)),
                        refresh=True,
                    )

        self.assertEqual(result["tmdb_id"], "1893")
        self.assertEqual(result["match_source"], "auto_tmdb")

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

    def test_tmdb_display_provider_never_falls_back_to_plex_metadata(self):
        canonical = app._build_canonical_metadata(
            {
                "path": "E:/Movies/ET.1982.mkv",
                "parsed_title": "et",
                "parsed_year": "1982",
            },
            plex_data={
                "plex_title": "E.T.",
                "plex_year": "1982",
                "plex_poster": "wrong-plex-poster.jpg",
            },
            display_provider="tmdb",
        )

        self.assertFalse(canonical["accepted"])
        self.assertEqual(canonical["status"], "unmatched")
        self.assertEqual(canonical["poster_url"], "")

    def test_plex_display_provider_uses_frozen_plex_snapshot(self):
        canonical = app._build_canonical_metadata(
            {
                "path": "E:/Movies/ET.1982.mkv",
                "parsed_title": "et",
                "parsed_year": "1982",
            },
            plex_data={
                "plex_title": "E.T.",
                "plex_year": "1982",
                "plex_poster": "saved-plex-poster.jpg",
            },
            tmdb_data={
                "tmdb_id": "601",
                "title": "E.T. the Extra-Terrestrial",
                "year": "1982",
                "poster_url": "tmdb-poster.jpg",
            },
            display_provider="plex",
        )

        self.assertTrue(canonical["accepted"])
        self.assertEqual(canonical["source"], "plex_snapshot")
        self.assertEqual(canonical["title"], "E.T.")
        self.assertEqual(canonical["poster_url"], "saved-plex-poster.jpg")


if __name__ == "__main__":
    unittest.main()
