import argparse
import concurrent.futures
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app
from tools.catalog_migration_backup import resolve_backup_sources


def _fetch_tmdb_details(tmdb_id, attempts=3):
    tmdb_id = str(tmdb_id or "").strip()
    if not tmdb_id or not app._tmdb_key:
        raise ValueError("TMDB ID and configured API key are required")
    safe_id = urllib.parse.quote(tmdb_id)
    url = (
        f"https://api.themoviedb.org/3/movie/{safe_id}"
        f"?api_key={urllib.parse.quote(app._tmdb_key)}&language=en-US"
        f"&append_to_response=credits,videos,release_dates"
    )
    error = None
    for attempt in range(max(1, int(attempts))):
        try:
            request = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = json.loads(response.read().decode("utf-8"))
            metadata = app._normalize_tmdb_metadata(raw)
            metadata.update(app._normalize_tmdb_details_payload(raw))
            metadata.update({
                "tmdb_id": tmdb_id,
                "match_source": "catalog_relational_backfill",
                "updated_at": time.time(),
            })
            return metadata
        except (OSError, ValueError, urllib.error.HTTPError) as caught:
            error = caught
            if isinstance(caught, urllib.error.HTTPError) and caught.code == 404:
                break
            if attempt + 1 < attempts:
                time.sleep(min(2 ** attempt, 4))
    raise RuntimeError(str(error or "TMDB request failed"))


def _missing_tmdb_ids(store):
    connection = store.catalog.store.connect()
    try:
        return [
            str(row[0])
            for row in connection.execute("""
                SELECT DISTINCT cm.tmdb_id
                FROM canonical_movies cm
                WHERE cm.selected_provider = 'tmdb'
                  AND cm.tmdb_id <> ''
                  AND NOT EXISTS (
                      SELECT 1 FROM provider_movie_snapshots ps
                      WHERE ps.snapshot_key = 'tmdb:' || cm.tmdb_id
                  )
                ORDER BY CAST(cm.tmdb_id AS INTEGER), cm.tmdb_id
            """).fetchall()
        ]
    finally:
        connection.close()


def backfill_catalog(user_data_dir, max_workers=6, batch_size=50, limit=0, dry_run=False):
    store = app.AppMetadataStore(Path(user_data_dir))
    missing = _missing_tmdb_ids(store)
    if limit:
        missing = missing[:max(0, int(limit))]
    report = {
        "requested": len(missing),
        "saved": 0,
        "failed": [],
        "catalog_generation_before": store.catalog.generation("media"),
        "catalog_generation_after": store.catalog.generation("media"),
        "dry_run": bool(dry_run),
    }
    if dry_run or not missing:
        return report

    batch = {}
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(int(max_workers), 12))) as executor:
        futures = {executor.submit(_fetch_tmdb_details, tmdb_id): tmdb_id for tmdb_id in missing}
        for future in concurrent.futures.as_completed(futures):
            tmdb_id = futures[future]
            completed += 1
            try:
                batch[tmdb_id] = future.result()
            except Exception as error:
                report["failed"].append({"tmdb_id": tmdb_id, "error": str(error)})
            if len(batch) >= max(1, int(batch_size)):
                store.catalog.upsert_records("app_metadata/tmdb_metadata.json", batch)
                report["saved"] += len(batch)
                batch = {}
            if completed % 100 == 0 or completed == len(missing):
                print(json.dumps({
                    "completed": completed,
                    "requested": len(missing),
                    "saved": report["saved"] + len(batch),
                    "failed": len(report["failed"]),
                }), flush=True)
    if batch:
        store.catalog.upsert_records("app_metadata/tmdb_metadata.json", batch)
        report["saved"] += len(batch)
    report["catalog_generation_after"] = store.catalog.generation("media")
    report["remaining"] = len(_missing_tmdb_ids(store))
    report["strict_report"] = store.catalog.store.canonical_report(max_errors=20)
    return report


def main():
    parser = argparse.ArgumentParser(description="Deterministically backfill missing selected-provider TMDB details into SQL.")
    parser.add_argument("--project-root", default=PROJECT_ROOT)
    parser.add_argument("--max-workers", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sources = resolve_backup_sources(args.project_root)
    report = backfill_catalog(
        sources["user_data_dir"],
        max_workers=args.max_workers,
        batch_size=args.batch_size,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, indent=2))
    return 0 if not report.get("failed") and not report.get("remaining", 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
