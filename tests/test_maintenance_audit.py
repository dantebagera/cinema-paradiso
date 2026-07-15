import unittest

from services.maintenance_audit import build_maintenance_audit


def candidate(path, **record):
    raw = {
        "path": path,
        "filename": path.rsplit("/", 1)[-1],
        "library_root": "E:/Movies",
        "resolution": "1080p",
        "rip_source": "WEB-DL",
        "size": 100,
        "identity_status": "accepted",
        "metadata_accepted": True,
        "identity_title": "Alien",
        "identity_year": "1979",
        "tmdb_id": "348",
        "decision_origin": "user_manual",
        **record,
    }
    result = {
        "path": path,
        "raw_json": raw,
        "resolution": raw["resolution"],
        "rip_source": raw["rip_source"],
        "size": raw["size"],
        "identity_status": raw["identity_status"],
        "metadata_status": raw.get("metadata_status", raw["identity_status"]),
        "metadata_accepted": raw["metadata_accepted"],
        "identity_title": raw.get("identity_title", ""),
        "identity_year": raw.get("identity_year", ""),
        "tmdb_id": raw.get("tmdb_id", ""),
        "imdb_id": raw.get("imdb_id", ""),
        "plex_guid": raw.get("plex_guid", ""),
        "library_root": raw["library_root"],
        "plex_json": {},
        "manual_json": {},
        "tmdb_json": {
            "tmdb_id": raw.get("tmdb_id", ""),
            "imdb_id": raw.get("imdb_id", ""),
            "title": raw.get("identity_title", ""),
            "year": raw.get("identity_year", ""),
        } if raw.get("tmdb_id") else {},
    }
    return result


class MaintenanceAuditTest(unittest.TestCase):
    def test_projects_storage_upgrades_and_identity_from_one_catalog_snapshot(self):
        audit = build_maintenance_audit([
            candidate("E:/Movies/Alien.1979.4K.Remux.mkv", resolution="4K", rip_source="Remux", size=400),
            candidate("E:/Movies/Alien.1979.1080p.WEB-DL.mkv", size=100),
            candidate(
                "E:/Movies/Heat.1995.720p.WEB-DL.mkv",
                identity_title="Heat",
                identity_year="1995",
                tmdb_id="949",
                resolution="720p",
            ),
            candidate(
                "E:/Movies/Unsorted/Deep/Unknown.2025.mkv",
                identity_status="review",
                metadata_status="review",
                metadata_accepted=False,
                identity_title="",
                identity_year="",
                tmdb_id="",
            ),
        ], generation=42)

        self.assertEqual(audit["source"], "catalog")
        self.assertEqual(audit["generation"], 42)
        self.assertEqual(audit["summary"]["duplicate_groups"], 1)
        self.assertEqual(audit["summary"]["recommended_removals"], 1)
        self.assertEqual(audit["summary"]["upgrade_candidates"], 1)
        self.assertEqual(audit["upgrades"]["items"][0]["title"], "Heat")
        self.assertEqual(audit["summary"]["identity_issues"], 1)
        self.assertEqual(audit["summary"]["unmatched_files"], 1)
        self.assertEqual(audit["summary"]["verification_gaps"], 0)
        self.assertTrue(audit["identity"]["items"][0]["fixable_path"])

    def test_conflicting_strong_ids_never_become_a_duplicate_group(self):
        audit = build_maintenance_audit([
            candidate("E:/Movies/Shared.2000.One.mkv", identity_title="Shared", identity_year="2000", tmdb_id="100"),
            candidate("E:/Movies/Shared.2000.Two.mkv", identity_title="Shared", identity_year="2000", tmdb_id="200"),
        ])

        self.assertEqual(audit["storage"]["groups"], [])

    def test_title_and_year_drift_is_not_a_conflict(self):
        drift = candidate(
            "E:/Movies/Conflict.One.mkv",
            identity_title="The Lost Chapter",
            identity_year="2025",
            tmdb_id="100",
        )
        drift["plex_json"] = {"plex_title": "The Lost Chapter Extended", "plex_year": "2024", "tmdb_id": "100"}

        audit = build_maintenance_audit([drift])

        self.assertEqual(audit["summary"]["hard_conflicts"], 0)
        self.assertEqual(audit["summary"]["verification_gaps"], 0)
        self.assertEqual(audit["identity"]["verification"], [])

    def test_public_id_conflict_is_separate_from_unmatched_repair(self):
        conflict = candidate("E:/Movies/Conflict.mkv", tmdb_id="100")
        conflict["plex_json"] = {"plex_title": "Other Movie", "plex_year": "2025", "tmdb_id": "999"}

        audit = build_maintenance_audit([conflict])

        self.assertEqual(audit["summary"]["hard_conflicts"], 1)
        self.assertEqual(audit["summary"]["verification_gaps"], 1)
        self.assertEqual(audit["identity"]["items"], [])
        self.assertEqual(audit["identity"]["verification"][0]["metadata_status"], "conflict")

    def test_unverified_accepted_identity_is_excluded_from_duplicate_and_upgrade_automation(self):
        first = candidate(
            "E:/Movies/Frailty.2001.One.mkv",
            identity_title="Temptation's Hour",
            identity_year="2001",
            tmdb_id="1387467",
            parsed_title="Frailty",
            parsed_year="2001",
            resolution="720p",
        )
        second = candidate(
            "E:/Movies/Frailty.2001.Two.mkv",
            identity_title="Temptation's Hour",
            identity_year="2001",
            tmdb_id="1387467",
            parsed_title="Frailty",
            parsed_year="2001",
            resolution="720p",
        )
        for item in (first, second):
            item["plex_json"] = {"plex_title": "Frailty", "plex_year": "2001"}

        audit = build_maintenance_audit([first, second])

        self.assertEqual(audit["storage"]["groups"], [])
        self.assertEqual(audit["upgrades"]["items"], [])
        self.assertEqual(audit["summary"]["verification_gaps"], 2)

    def test_provider_audit_backlog_is_separate_from_manual_identity_review(self):
        pending = candidate(
            "E:/Movies/Elle.2016.mkv",
            identity_title="Elle",
            identity_year="2016",
            tmdb_id="337674",
            decision_origin="identity_audit",
        )

        audit = build_maintenance_audit([pending])

        self.assertEqual(audit["summary"]["automated_identity_checks"], 1)
        self.assertEqual(audit["summary"]["verification_gaps"], 0)
        self.assertEqual(audit["identity"]["verification"], [])


if __name__ == "__main__":
    unittest.main()
