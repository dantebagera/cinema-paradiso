# TV Library performance execution — stopped before owner changes

**Historical report of the first stop.** Dante subsequently approved resumption. Current outcome and all eight memory observations are in [report-resumed.md](report-resumed.md): candidate failed the memory gate and its application-source changes were rolled back.

2026-10-23, Africa/Cairo. This is an incomplete implementation attempt, not a performance result.

Dante approved implementing the updated plan and isolated checks, with no live restart or production data change. The exact approval is recorded in the plan. The approved no-retry / failed-gate stop boundary was reached during baseline characterization.

## What changed

- Added `tests/test_tv_library_read_performance.py`: deterministic 6/24-series fixture factory (36 regular episodes and two Specials, 2 KiB overview, eight reused guest people, four tiny files per series), structural counters, full-field service expectations and freshness/slice/error assertions.
- Added four named physical-version/queue tests to `tests/test_tv_catalog.py`; no existing tests were removed or altered.
- Added `run_check.py`, `probe.py`, `progress.md` and `task-root.txt` under this verification folder. The probe has not run. Its correctness and its full HTTP/memory behavior are unverified.
- Recorded authorization and stopped status in the plan. Preserved scoped pre-change source, hashes, checkout status, logs and the cumulative budget under the GUID OS-temp directory named in `task-root.txt`.
- **No application source changed.** SHA256 comparison confirms `tv_catalog_repository.py`, `tv_read_model.py`, `tv_search.py` and `tv_playback.py` equal the captured dirty baseline, including pre-existing edits.

## Tests and the failed gate

First command: `python -m unittest tests.test_tv_stabilization.TVSearchTests tests.test_tv_coverage_contract tests.test_tv_catalog -v`.
Result: **29 passed**, no failures/skips/errors, 3.542 active seconds including process overhead.

Second command: `python -m unittest tests.test_tv_library_read_performance tests.test_tv_catalog -v`.
Result: **15 tests, 11 passed, three expected pre-implementation failures, one unexpected error, zero skips**. 3.828 active seconds including process overhead.

Expected failures:

| Test | Baseline result | Required candidate result |
| --- | --- | --- |
| `test_context_full_episode_detail_and_slice_parity` | `library_read_context` absent | Full standalone/context parity |
| `test_search_structural_bound_and_fresh_availability` | 113 SELECTs, 50 connections, each bound path checked three times | At most 14 SELECTs, one path check |
| `test_options_structural_bound_and_no_detail_work` | 40 SELECTs, 19 connections, each bound path checked twice | At most two SELECTs, one path check |

Unexpected error: `test_exact_membership_full_fields_and_options` called `repository.review({'series_id': ...}, ...)` without `path`; `review()` reads `payload['path']` at line 590. It raised `KeyError: 'path'` before exercising pending-only membership. This is an incorrectly constructed new fixture input. It establishes no production bug or contract difference. The fixture remains as observed, with evidence preserved; it was not silently corrected and retried.

The no-retry rule prevents rerunning this failed characterization gate under the present pass. Task 1 is incomplete and owner implementation has not started.

## Physical playback identities actually verified

All four named new tests passed against the real standalone repository and TVPlayback adapter. Synthetic regular episode IDs were 2 and 3; file IDs were exactly `[1, 2]` and `[3, 4]`, with low-quality `z-low` inserted before high-quality `a-high`.

- Default keys: `tv:episode:2:file:1` and `tv:episode:3:file:3`.
- Saved available nonfirst version: `tv:episode:2:file:2`; explicit available file 1 overrides it.
- Saved version 2 removed: fallback `tv:episode:2:file:1`; explicitly requesting removed file 2 raises `Episode file is missing`. Removing both versions causes the same missing-file error.
- Queue retains supplied current key `tv:episode:2:file:2`; successor key is `tv:episode:3:file:3`. Removing both successor versions yields `missing:tv:3`, unavailable, reason `Episode is missing locally`. Tests also assert exact titles and Season 1 sections for those entries.

Supplied-context assembly does not exist yet and was not verified. Real-backend Versions/Play desktop checks were not run. These standalone passes do not satisfy the complete physical-version gate.

## Remaining gates and contracts

No candidate exists. None of the acceptance matrix rows is claimed complete. Existing focused suites establish only their tested pre-change behavior; the new pending-membership fixture did not reach its assertions.

Full response/detail baseline capture: unrun. Coherent snapshot/concurrent reads and writer checks: unrun. Freshness/adverse files under a candidate: unrun. Shared-caller and domain-boundary candidate checks: unrun. Affected-owner broader suites and Node tests: unrun. Compiled desktop build/render/navigation/selection/credits: unrun.

**Memory: zero of eight observations recorded**, no baseline/candidate peaks, residuals, bounds or collection results available. The drafted probe uses tracemalloc, which would cover Python-managed allocations only, not total process/native memory. No memory claim is made.

**Latency: zero of sixteen optional requests performed.** No median/range/body/encoding comparison or speedup claim is available.

## Limits and live boundary

One sequential worker, no affinity, no retries. Active verification consumed **7.370 / 600 seconds**, leaving **592.630 seconds** if resumption is authorized; the budget must not reset. Final retained temporary footprint: **267262 bytes**, below 1 GiB. No hardware polling/stress/storage benchmark. All tests used CP_TEST_MODE=1, GUID OS-temp roots, embedded qBittorrent mode and synthetic media. No app import or provider/player transport was exercised by the tests actually run.

No production database/media copied or opened for testing. No production source owner edits, dist overwrite, app restart/reload, live request, catalog/config mutation, system media-client action, delegation, worktree, commit, push or publication. No temporary server started. Read-only listener inspection still showed port 5000 owned by PID 5264; port 5127 unused. Live activation was not performed.
