import tempfile
import time
import unittest
from pathlib import Path

from services.smart_match import (
    SmartMatchCoordinator,
    build_rename_filename,
    parse_ai_match_response,
    parse_release_filename,
    rank_candidates,
    score_candidate,
)


class MemoryStore:
    def __init__(self):
        self.state = {}

    def load(self):
        return dict(self.state)

    def save(self, state):
        self.state = dict(state)


class SmartMatchServiceTest(unittest.TestCase):
    def test_parses_fenced_ai_json_with_canonical_key_numeric_year_and_alternatives(self):
        parsed = parse_ai_match_response(
            """Some text
```json
{"matches":[
  {"id":"one","canonical":"Audition","year":1999,
   "alternatives":[{"title":"Odishon","year":"1999"}]},
  {"id":"one","title":"duplicate","year":"2000"}
]}
```""",
            expected_ids=["one", "two"],
        )

        self.assertEqual(parsed["matches"]["one"]["title"], "Audition")
        self.assertEqual(parsed["matches"]["one"]["year"], "1999")
        self.assertEqual(parsed["matches"]["one"]["alternatives"][0]["title"], "Odishon")
        self.assertEqual(parsed["missing_ids"], ["two"])
        self.assertEqual(parsed["duplicate_ids"], ["one"])

    def test_parses_noisy_avp_filename(self):
        parsed = parse_release_filename(
            "01 Alien VS Predator AVP Unrated - Sci-Fi 2004 Eng Subs 1080p [H264-mp4].mp4"
        )

        self.assertEqual(parsed["title"], "Alien vs. Predator")
        self.assertEqual(parsed["year"], "2004")
        self.assertEqual(parsed["edition"], "Unrated")
        self.assertEqual(parsed["resolution"], "1080p")
        self.assertEqual(parsed["source"], "")

    def test_parser_preserves_known_edition_and_source(self):
        parsed = parse_release_filename(
            "Blade.Runner.Final.Cut.1982.2160p.BluRay.x265-GROUP.mkv"
        )

        self.assertEqual(parsed["title"], "Blade Runner")
        self.assertEqual(parsed["year"], "1982")
        self.assertEqual(parsed["edition"], "Final Cut")
        self.assertEqual(parsed["resolution"], "4K")
        self.assertEqual(parsed["source"], "Blu-ray")

    def test_parser_handles_unicode_separators_and_release_group(self):
        parsed = parse_release_filename("Amélie—2001—1080p—WEB-DL-GROUP.mkv")

        self.assertEqual(parsed["title"], "Amélie")
        self.assertEqual(parsed["year"], "2001")
        self.assertEqual(parsed["resolution"], "1080p")
        self.assertEqual(parsed["source"], "WEB-DL")

    def test_candidate_scoring_requires_title_and_year_without_conflicting_ids(self):
        parsed = {"title": "Alien vs. Predator", "year": "2004"}
        strong = score_candidate(
            parsed,
            {"tmdb_id": "395", "title": "AVP: Alien vs. Predator", "year": "2004"},
        )
        wrong_year = score_candidate(
            parsed,
            {"tmdb_id": "395", "title": "AVP: Alien vs. Predator", "year": "2007"},
        )
        conflicting = score_candidate(
            parsed,
            {"tmdb_id": "999", "title": "Alien vs. Predator", "year": "2004"},
            known_identity={"tmdb_id": "395"},
        )

        self.assertTrue(strong["preselected"])
        self.assertGreaterEqual(strong["confidence"], 90)
        self.assertFalse(wrong_year["preselected"])
        self.assertEqual(wrong_year["recommendation"], "weak")
        self.assertIn("release year differs by more than one year", wrong_year["reasons"])
        self.assertFalse(conflicting["preselected"])
        self.assertIn("conflicting TMDB ID", conflicting["reasons"])

    def test_candidate_scoring_rejects_conflicting_plex_guid(self):
        result = score_candidate(
            {"title": "Alien", "year": "1979"},
            {"title": "Alien", "year": "1979", "guid": "plex://movie/new"},
            known_identity={"plex_guid": "plex://movie/existing"},
        )

        self.assertEqual(result["confidence"], 0)
        self.assertFalse(result["preselected"])
        self.assertIn("conflicting Plex GUID", result["reasons"])

    def test_comparative_ranking_recognizes_tmdb_alias_and_clear_lead(self):
        ranked = rank_candidates(
            [{"title": "Asterix In America", "year": "1994", "source": "filename"}],
            [
                {
                    "tmdb_id": "9369",
                    "title": "Asterix Conquers America",
                    "original_title": "Asterix in Amerika",
                    "alternative_titles": ["Asterix in America"],
                    "year": "1994",
                    "provider_rank": 1,
                    "query_sources": ["filename", "folder"],
                },
                {
                    "tmdb_id": "999",
                    "title": "Asterix at the Olympic Games",
                    "year": "2008",
                    "provider_rank": 2,
                    "query_sources": ["filename"],
                },
            ],
        )

        self.assertEqual(ranked[0]["tmdb_id"], "9369")
        self.assertEqual(ranked[0]["recommendation"], "recommended")
        self.assertGreaterEqual(ranked[0]["evidence_score"], 80)
        self.assertGreaterEqual(ranked[0]["runner_up_gap"], 15)

    def test_comparative_ranking_prefers_real_film_over_same_year_making_of(self):
        ranked = rank_candidates(
            [{"title": "Antiporno", "year": "2016", "source": "filename"}],
            [
                {
                    "tmdb_id": "414770",
                    "title": "Antiporno",
                    "original_title": "アンチポルノ",
                    "alternative_titles": ["Anti-Porno"],
                    "year": "2017",
                    "provider_rank": 1,
                    "query_sources": ["title_without_year"],
                },
                {
                    "tmdb_id": "959305",
                    "title": "Making of Antiporno",
                    "year": "2016",
                    "provider_rank": 2,
                    "query_sources": ["title_with_year"],
                },
            ],
        )

        self.assertEqual(ranked[0]["tmdb_id"], "414770")
        self.assertEqual(ranked[0]["recommendation"], "recommended")
        self.assertIn("release year is within one year", ranked[0]["reasons"])
        self.assertIn("unrequested making-of qualifier", ranked[1]["reasons"])

    def test_comparative_ranking_tolerates_audition_release_year_difference(self):
        ranked = rank_candidates(
            [{"title": "Audition", "year": "1999", "source": "filename"}],
            [
                {
                    "tmdb_id": "11075",
                    "title": "Audition",
                    "alternative_titles": ["Oodishon"],
                    "year": "2000",
                    "provider_rank": 1,
                    "query_sources": ["title_without_year", "ai_primary"],
                },
                {
                    "tmdb_id": "29545",
                    "title": "Auditions from Beyond",
                    "year": "1999",
                    "provider_rank": 2,
                    "query_sources": ["title_with_year"],
                },
            ],
        )

        self.assertEqual(ranked[0]["tmdb_id"], "11075")
        self.assertEqual(ranked[0]["recommendation"], "recommended")

    def test_best_bad_candidate_remains_weak_without_absolute_evidence(self):
        ranked = rank_candidates(
            [{"title": "Completely Different Film", "year": "2020", "source": "filename"}],
            [
                {
                    "tmdb_id": "1",
                    "title": "Unrelated Documentary",
                    "year": "2020",
                    "provider_rank": 1,
                    "query_sources": ["filename"],
                },
                {
                    "tmdb_id": "2",
                    "title": "Another Unrelated Movie",
                    "year": "2019",
                    "provider_rank": 2,
                    "query_sources": ["filename"],
                },
            ],
        )

        self.assertEqual(ranked[0]["recommendation"], "weak")
        self.assertFalse(ranked[0]["preselected"])

    def test_rename_filename_uses_only_known_structured_tags(self):
        filename = build_rename_filename(
            "Alien vs. Predator",
            "2004",
            {
                "edition": "Unrated",
                "resolution": "1080p",
                "source": "WEBRip",
            },
            ".mp4",
        )

        self.assertEqual(
            filename,
            "Alien vs. Predator (2004) [Unrated] [1080p WEBRip].mp4",
        )

    def test_coordinator_persists_preview_progress_and_proposals(self):
        store = MemoryStore()
        coordinator = SmartMatchCoordinator(
            load_state=store.load,
            save_state=store.save,
            process_path=lambda path, provider, method: {
                "id": f"proposal-{path}",
                "path": path,
                "provider": provider,
                "method": method,
                "preselected": path == "one",
            },
        )

        started = coordinator.start(["one", "two"], "tmdb", "classic", background=False)
        self.assertEqual(started["status"], "running")
        coordinator.run_batch(limit=1)

        restarted = SmartMatchCoordinator(
            load_state=store.load,
            save_state=store.save,
            process_path=lambda path, provider, method: {
                "id": f"proposal-{path}",
                "path": path,
                "provider": provider,
                "method": method,
                "preselected": False,
            },
        )
        self.assertEqual(restarted.status()["status"], "paused")
        restarted.resume(background=False)
        restarted.run_batch(limit=10)
        state = restarted.status()

        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["processed"], 2)
        self.assertEqual(len(state["proposals"]), 2)
        self.assertEqual(state["preselected"], 1)

    def test_coordinator_rejects_competing_job_and_cancels_without_applying(self):
        store = MemoryStore()
        coordinator = SmartMatchCoordinator(
            load_state=store.load,
            save_state=store.save,
            process_path=lambda path, provider, method: {"path": path},
        )
        coordinator.start(["one", "two"], "tmdb", "classic", background=False)

        with self.assertRaisesRegex(RuntimeError, "already active"):
            coordinator.start(["three"], "plex", "ai", background=False)

        cancelled = coordinator.cancel()
        coordinator.run_batch(limit=10)
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(coordinator.status()["processed"], 0)

    def test_coordinator_processes_ai_paths_in_one_bounded_batch(self):
        store = MemoryStore()
        batches = []
        coordinator = SmartMatchCoordinator(
            load_state=store.load,
            save_state=store.save,
            process_path=lambda path, provider, method: self.fail("single path processor used"),
            process_batch=lambda paths, provider, method: batches.append(list(paths)) or [
                {"path": path, "candidate": {"title": path}, "preselected": False}
                for path in paths
            ],
            batch_size=8,
        )
        paths = [f"movie-{index}" for index in range(10)]
        coordinator.start(paths, "tmdb", "ai", background=False)

        coordinator.run_batch()
        coordinator.run_batch()

        self.assertEqual([len(batch) for batch in batches], [8, 2])
        self.assertEqual(coordinator.status()["processed"], 10)


if __name__ == "__main__":
    unittest.main()
