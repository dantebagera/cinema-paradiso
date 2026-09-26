"""Reproduce cold catalog initialization using disposable data only.

Run from the assigned worktree with Python. No server, client, or provider is
started. This diagnostic deliberately reports failures without repairing them.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import sys
import tempfile
import threading

project = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project))
root = Path(tempfile.mkdtemp(prefix="cp-tv-cold-catalog-"))
os.environ.update(CP_TEST_MODE="1", CP_TEST_ROOT=str(root), CP_TEST_QBT_MODE="system")

import app

barrier = threading.Barrier(8)


def read_catalog(_):
    barrier.wait(timeout=10)
    try:
        repository = app._catalog_repository()
        return {"ok": True, "database": str(repository.database_path)}
    except Exception as error:
        return {"ok": False, "type": type(error).__name__, "error": str(error)}


with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(read_catalog, range(8)))
report = {"test_root": str(root), "requests": results,
          "successes": sum(row["ok"] for row in results)}
print(json.dumps(report, indent=2))
for lease in app._catalog_writer_lease_cache.values():
    lease.close()
sys.exit(0 if report["successes"] == 8 else 1)
