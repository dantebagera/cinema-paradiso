"""Compare the paged SQL Library query with the previous browser-side oracle."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app


def _cases(items, people_items, lists):
    first_genre = next((item.get("canonical_metadata", {}).get("genres", [None])[0]
                        for item in items if item.get("canonical_metadata", {}).get("genres")), None)
    first_language = next((item.get("canonical_metadata", {}).get("language")
                           for item in items if item.get("canonical_metadata", {}).get("language")), None)
    first_country = next((item.get("canonical_metadata", {}).get("country_flag")
                          or item.get("canonical_metadata", {}).get("country")
                          for item in items if item.get("canonical_metadata", {}).get("country_flag")
                          or item.get("canonical_metadata", {}).get("country")), None)
    first_person = next((person for item in people_items
                         for person in item.get("canonical_metadata", {}).get("cast", []) if person.get("name")), None)
    first_list = next((value for value in lists if value.get("movies")), None)
    cases = [
        {"name": "added", "view": {"sortMode": "added"}, "sql": {"sort": "added"}},
        {"name": "title", "view": {"sortMode": "title"}, "sql": {"sort": "title"}},
        {"name": "rating", "view": {"sortMode": "rating"}, "sql": {"sort": "rating"}},
        {"name": "year_desc", "view": {"sortMode": "year-desc"}, "sql": {"sort": "year-desc"}},
        {"name": "year_asc", "view": {"sortMode": "year-asc"}, "sql": {"sort": "year-asc"}},
        {"name": "quality", "view": {"sortMode": "quality"}, "sql": {"sort": "quality"}},
        {"name": "punctuation_query", "view": {"query": "'"}, "sql": {"query": "'", "sort": "added"}},
        {"name": "year_range", "view": {"yearFrom": "1990", "yearTo": "2010"},
         "sql": {"year_from": "1990", "year_to": "2010", "sort": "added"}},
        {"name": "rating_filter", "view": {"minRating": "7"},
         "sql": {"min_rating": "7", "sort": "added"}},
        {"name": "resolution", "view": {"resolutionFilter": "1080p"},
         "sql": {"resolution": "1080p", "sort": "added"}},
    ]
    if first_genre:
        cases.append({"name": "genre", "view": {"genreFilter": first_genre},
                      "sql": {"genre": first_genre, "sort": "added"}})
    if first_language:
        cases.append({"name": "language", "view": {"languageFilter": first_language},
                      "sql": {"language": first_language, "sort": "added"}})
    if first_country:
        cases.append({"name": "country", "view": {"countryFilter": first_country},
                      "sql": {"country": first_country, "sort": "added"}})
    if first_person:
        cases.append({"name": "stored_cast", "people": True,
                      "view": {"roleFilter": {"role": "cast", "id": first_person.get("id", ""),
                                                "name": first_person["name"], "localOnly": True}},
                      "sql": {"role": "cast", "person_id": first_person.get("id", ""),
                              "person_name": first_person["name"], "sort": "added"}})
    if first_list:
        cases.append({"name": "list", "view": {"listFilter": first_list},
                      "sql": {"list_id": first_list["id"], "sort": "added"}})
    return cases


def main():
    store = app._metadata_store()
    candidates = store.catalog.store.audit_library_candidates()
    upgrade_paths = app._maintenance_upgrade_path_keys()
    full_items = [app._catalog_library_item(candidate, store, None) for candidate in candidates]
    items = []
    people_items = []
    for candidate, full_item in zip(candidates, full_items):
        card = app._library_card_item(full_item, upgrade_paths=upgrade_paths)
        card["shadow_path_key"] = candidate["path_key"]
        items.append(card)
        people = app._library_people_item(full_item)
        people_items.append({
            **card,
            "canonical_metadata": {**card.get("canonical_metadata", {}), **people.get("canonical_metadata", {})},
            "plex_cast": people.get("plex_cast", []),
            "plex_directors": people.get("plex_directors", []),
        })
    lists = app._catalog_repository().read_document("user_lists.json", {"lists": []}).get("lists", [])
    cases = _cases(items, people_items, lists)
    completed = subprocess.run(
        ["node", str(ROOT / "tools" / "library_filter_shadow.mjs")],
        input=json.dumps({"items": items, "peopleItems": people_items, "lists": lists, "cases": cases}),
        text=True, encoding="utf-8", capture_output=True, check=True, cwd=ROOT,
    )
    expected = json.loads(completed.stdout)
    connection = store.catalog.store.connect()
    try:
        path_keys = {
            os.path.normcase(os.path.normpath(row["path"])): row["path_key"]
            for row in connection.execute("SELECT path_key, path FROM media_files")
        }
    finally:
        connection.close()
    mismatches = {}
    for test_case in cases:
        actual = [path_keys[os.path.normcase(os.path.normpath(path))]
                  for path in store.catalog.library_selection_paths(test_case["sql"])]
        if actual != expected[test_case["name"]]:
            mismatch_at = next((index for index, pair in enumerate(zip(actual, expected[test_case["name"]]))
                                if pair[0] != pair[1]), min(len(actual), len(expected[test_case["name"]])))
            mismatches[test_case["name"]] = {
                "expected_count": len(expected[test_case["name"]]), "actual_count": len(actual),
                "first_mismatch": mismatch_at,
                "expected": expected[test_case["name"]][mismatch_at:mismatch_at + 3],
                "actual": actual[mismatch_at:mismatch_at + 3],
            }
    report = {"passed": not mismatches, "cases": len(cases), "mismatches": mismatches}
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
