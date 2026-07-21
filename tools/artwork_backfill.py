"""Run and measure the resumable owned artwork backfill."""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-batches", type=int, default=0)
    parser.add_argument("--output")
    parser.add_argument("--skip-queue", action="store_true")
    args = parser.parse_args()
    service = app._media_asset_service()
    started = time.time()
    catalog_generation = app._catalog_repository().generation("media")
    examined_relationships = 0
    if not args.skip_queue:
        service.migrate_custom_posters(app._metadata_store().posters_dir)
        examined_relationships = service.queue_owned_artwork()
    initial = service.status()
    batches = []
    while True:
        before = service.status()
        queued = int(before.get("counts", {}).get("queued", 0))
        retryable_failed = int(before.get("counts", {}).get("failed", 0))
        if not queued and not retryable_failed:
            break
        batch_started = time.perf_counter()
        result = service.run_backfill(limit=args.batch_size, workers=args.workers)
        batch = {
            "batch": len(batches) + 1,
            "seconds": round(time.perf_counter() - batch_started, 3),
            "attempted": result.get("queued", 0),
            "completed": result.get("completed", 0),
            "failed": result.get("failed", 0),
            "counts": result.get("counts", {}),
            "physical_bytes": result.get("physical_bytes", 0),
        }
        batches.append(batch)
        print(json.dumps(batch), flush=True)
        if not result.get("queued"):
            break
        if args.max_batches and len(batches) >= args.max_batches:
            break
    final = service.status()
    report = {
        "started_at": started,
        "duration_seconds": round(time.time() - started, 3),
        "initial": initial,
        "batches": batches,
        "final": final,
        "catalog_generation_before": catalog_generation,
        "catalog_generation_after": app._catalog_repository().generation("media"),
        "examined_relationships": examined_relationships,
        "deduplicated_files": int(final.get("checksum_deduplications", 0)),
        "deduplicated_relationships": int(final.get("relationship_deduplications", 0)),
    }
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
