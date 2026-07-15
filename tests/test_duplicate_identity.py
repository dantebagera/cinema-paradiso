import unittest

from services.maintenance_audit import build_maintenance_audit


def catalog_candidate(
    path,
    *,
    title,
    year,
    tmdb_id="",
    plex_title="",
    plex_year="",
    parsed_title="",
    parsed_year="",
    decision_origin="",
):
    record = {
        "path": path,
        "filename": path.rsplit("/", 1)[-1],
        "library_root": "E:/Movies",
        "identity_status": "accepted",
        "metadata_accepted": True,
        "identity_title": title,
        "identity_year": year,
        "tmdb_id": tmdb_id,
        "parsed_title": parsed_title or title,
        "parsed_year": parsed_year or year,
        "resolution": "1080p",
        "rip_source": "WEB-DL",
        "size": 100,
        "decision_origin": decision_origin,
    }
    return {
        "path": path,
        "raw_json": record,
        "identity_status": "accepted",
        "metadata_status": "accepted",
        "metadata_accepted": True,
        "identity_title": title,
        "identity_year": year,
        "tmdb_id": tmdb_id,
        "resolution": "1080p",
        "rip_source": "WEB-DL",
        "size": 100,
        "plex_json": {"plex_title": plex_title, "plex_year": plex_year} if plex_title else {},
    }


class DuplicateIdentityTest(unittest.TestCase):
    def test_catalog_audit_merges_manual_tmdb_and_plex_title_identity(self):
        audit = build_maintenance_audit([
            catalog_candidate(
                "E:/Movies/Batteries.Not.Included.1987.1080p.mkv",
                title="",
                year="",
                plex_title="*batteries not included",
                plex_year="1987",
                parsed_title="batteries not included",
                parsed_year="1987",
            ),
            catalog_candidate(
                "E:/Movies/Batteries.Not.Included.Copy.1987.1080p.mkv",
                title="*batteries not included",
                year="1987",
                tmdb_id="11548",
                parsed_title="batteries not included",
                parsed_year="1987",
                decision_origin="user_manual",
            ),
        ])

        self.assertEqual(audit["summary"]["duplicate_groups"], 1)
        self.assertEqual(audit["summary"]["extra_copies"], 1)

    def test_bulk_plex_groups_are_rebucketed_by_filename_identity(self):
        candidates = []
        for group, tmdb_id in (("A", "1001"), ("B", "2002")):
            for index in range(5):
                candidates.append(catalog_candidate(
                    f"E:/Movies/Shared.Movie.2000.{group}.{index}.mkv",
                    title=f"Bulk {group}",
                    year="1999",
                    tmdb_id=tmdb_id,
                    plex_title=f"Bulk {group}",
                    plex_year="1999",
                    parsed_title=f"unique {group} {index}",
                    parsed_year=str(2000 + index),
                ))

        audit = build_maintenance_audit(candidates)

        self.assertEqual(audit["storage"]["groups"], [])


if __name__ == "__main__":
    unittest.main()
