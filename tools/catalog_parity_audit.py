import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app
from tools.catalog_migration_backup import resolve_backup_sources


def _violation(bucket, candidate, message, limit):
    if len(bucket) >= limit:
        return
    bucket.append({
        "path": str(candidate.get("path") or ""),
        "path_key": str(candidate.get("path_key") or ""),
        "message": message,
    })


def audit_catalog(user_data_dir, max_errors=100):
    """Read the active SQL catalog through the same canonical projections as the app."""
    store = app.AppMetadataStore(Path(user_data_dir))
    snapshot = store.snapshot()
    candidates = store.catalog.store.library_candidates()
    violations = {
        "sql_rows": [],
        "canonical": [],
        "deferred_details": [],
        "projections": [],
    }
    accepted = 0
    active_detail_providers = {}

    with patch("app.urllib.request.urlopen", side_effect=AssertionError("Catalog parity audit must not call providers")):
        for candidate in candidates:
            record = app._catalog_file_record(candidate)
            if not candidate.get("path_key") or not candidate.get("path") or not record.get("filename"):
                _violation(violations["sql_rows"], candidate, "Missing required SQL path or filename fields", max_errors)
                continue
            if str(record.get("path") or "") != str(candidate.get("path") or ""):
                _violation(violations["sql_rows"], candidate, "Raw file record path disagrees with normalized SQL row", max_errors)

            item = app._catalog_library_item(candidate, store, snapshot)
            canonical = item.get("canonical_metadata") or {}
            card = app._library_card_item(item)
            list_item = app._movie_list_library_item(item)
            people = app._library_people_item(item)

            if canonical.get("accepted"):
                accepted += 1
                if not canonical.get("title") or not canonical.get("year"):
                    _violation(violations["canonical"], candidate, "Accepted canonical identity is missing title or year", max_errors)
                if not any(canonical.get(field) for field in ("tmdb_id", "imdb_id", "plex_guid")):
                    _violation(violations["canonical"], candidate, "Accepted canonical identity has no stable provider ID", max_errors)

            tmdb = candidate.get("tmdb_json") or {}
            plex = candidate.get("plex_json") or {}
            detail_provider = canonical.get("detail_provider", "")
            if detail_provider:
                active_detail_providers[detail_provider] = active_detail_providers.get(detail_provider, 0) + 1
            if record.get("display_provider") == "tmdb" and record.get("tmdb_id") and not tmdb:
                if detail_provider != "plex_snapshot" or not plex:
                    _violation(violations["deferred_details"], candidate, "TMDB display identity has no persisted SQL detail snapshot", max_errors)
            if detail_provider == "tmdb_snapshot" and not tmdb:
                _violation(violations["deferred_details"], candidate, "Canonical TMDB detail provider has no SQL snapshot", max_errors)
            if detail_provider == "plex_snapshot" and not plex:
                _violation(violations["deferred_details"], candidate, "Canonical Plex detail provider has no SQL snapshot", max_errors)
            if tmdb.get("plot") and canonical.get("source", "").startswith("tmdb"):
                if canonical.get("plot") != tmdb.get("plot") or canonical.get("summary") != tmdb.get("plot"):
                    _violation(violations["deferred_details"], candidate, "TMDB plot is not preserved by the canonical detail read", max_errors)
            if plex.get("plex_summary") and item.get("plex_summary") != plex.get("plex_summary"):
                _violation(violations["deferred_details"], candidate, "Plex summary is not preserved by the canonical detail read", max_errors)

            for projection in (card, list_item):
                projected = projection.get("canonical_metadata") or {}
                for field in ("tmdb_id", "imdb_id", "plex_guid", "title", "year"):
                    if projected.get(field) and projected.get(field) != canonical.get(field):
                        _violation(violations["projections"], candidate, f"Projection disagrees on canonical {field}", max_errors)
            if any(canonical.get(field) for field in ("plot", "cast", "directors")):
                if any((card.get("canonical_metadata") or {}).get(field) for field in ("plot", "cast", "directors")):
                    _violation(violations["projections"], candidate, "Card projection includes deferred detail fields", max_errors)
            if canonical.get("cast") and not (people.get("canonical_metadata") or {}).get("cast"):
                _violation(violations["projections"], candidate, "People projection lost canonical cast", max_errors)

    error_count = sum(len(rows) for rows in violations.values())
    return {
        "source": "catalog",
        "database": str(store.catalog.database_path),
        "catalog_generation": store.catalog.generation("media"),
        "checked_records": len(candidates),
        "accepted_records": accepted,
        "provider_calls": 0,
        "active_detail_providers": dict(sorted(active_detail_providers.items())),
        "passed": error_count == 0,
        "violations": violations,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit active SQL catalog rows and app projections without provider calls.")
    parser.add_argument("--project-root", default=PROJECT_ROOT)
    parser.add_argument("--max-errors", type=int, default=100)
    args = parser.parse_args()
    sources = resolve_backup_sources(args.project_root)
    report = audit_catalog(sources["user_data_dir"], max_errors=max(1, args.max_errors))
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
