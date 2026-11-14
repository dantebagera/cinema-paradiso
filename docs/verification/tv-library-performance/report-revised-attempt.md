# Revised TV Library plan — stopped at probe setup gate

2026-10-23, Africa/Cairo. **The compact retention design has not been implemented.** The first baseline observation under the revised harness was invalidated by late URL-codec imports. The plan expressly requires stopping on this setup defect without automatic retries.

## Authorization and preserved state

Dante: "go implement the revised tv library performance plan and run the isolated checks within the remaining budget. dont restart the live app or change production data."

Run ID: `f5369bde-015b-4c34-acaa-016573a590e0`. Actual checkout remains master at be511f98846a67a182e5b371ad087938e9344362, with 213 porcelain status entries containing extensive prior tracked/untracked work. Full status, scoped pre-edit source/harness copies and hashes are in the run's baseline directory. Those copies are from the current dirty source, not HEAD or the rejected candidate.

No application owner was edited. Final SHA256 comparisons show repository, read model, search and playback exactly match this run's baseline, including pre-existing changes. The live application and production data/config/dist were untouched.

## Changes retained for review

- `probe.py`: separate `prepare_probe` / `measure_single_request`, client creation before tracing, explicit Flask/Werkzeug client imports, fixed-clock setup, repository/Flask weakref evidence, late-import detection and per-pair bounds.
- `run_check.py`: per-run logs/results with collision protection, unchanged cumulative ledger, fresh GUID test root, embedded qBittorrent and run/source identity environment. It no longer overwrites historical observation logs.
- `tests/test_tv_library_read_performance.py`: fake-client/tracer setup tests, missing-context evidence rejection, compact-state/lifetime/metadata-error/concurrency/order assertions; optional adversarial insertion order for separate full-output checks. Default 6/24 memory fixtures remain unchanged.
- `tests/test_tv_catalog.py`: future supplied-context proxy now uses the planned compact interface; queue assertions cover the entire queue, retaining prior concrete keys/ordering.
- Plan authorization/stop records, `active-run.json`, execution ledger and this report.

The compact-owner tests are prospective and unrun. They cannot pass against the unchanged application source. The existing behavioral tests that actually ran are listed below; no candidate implementation or full-suite success is claimed.

## Checks actually run

| Phase | Result | Active seconds including process overhead |
| --- | --- | ---: |
| Probe interface RED against the preserved old harness | One expected failure: old file has only `dispatch`, no separated prepare/measure helpers | 0.219 |
| Current probe contract + baseline characterization/catalog | **15 passed**, zero failures/errors/skips | 3.625 |
| First revised baseline memory request: six series/cards | **Invalid setup**: late imports `encodings.idna`, `stringprep`; gate stopped | 1.625 |

The 15 passing checks include three probe tests, membership/detail/options characterization, paging/error expectations, existing catalog tests and all four physical-version tests using standalone source. The corrected full-queue assertion passed on standalone source. There is no compact-context implementation to exercise yet.

## Failure and cause

The probe correctly created the Flask client before tracing and explicitly imported `flask.testing` and `werkzeug.test`, but did not preload Python's IDNA hostname codec. Werkzeug's URL conversion calls `hostname.encode('idna')`; the first real test request therefore imported `encodings.idna` and its `stringprep` dependency inside the recorded region. This is another incomplete harness setup, not an application regression or a result about the new retention design.

The fake-client/tracer ordering test passed because it replaced the client and did not execute real URL normalization. The actual late-import gate caught the omitted setup.

The trace reaches `measure_single_request`'s late-import assertion after its response/context assertions. However, the helper raises before main writes the JSON record. **No valid numerical peak/residual result file was recorded for this attempt; those numbers are unavailable.** Only the raw failure traceback is retained. Do not reconstruct or substitute old values.

This run made **one invalid baseline request, zero valid new memory observations**, no remaining baseline requests and no candidate observations. The previous eight observations remain historical and invalid for the revised protocol. There was no retry, warm-up or automatic continuation after this failed gate.

## What a separately authorized correction needs

Before another real observation, explicitly preload `encodings.idna` and `stringprep` during preparation; assert both are in the pre-trace setup manifest. Keep client construction outside tracing and zero endpoint dispatches during preparation. Add the setup dependency assertion to the non-request contract tests without warming a TV endpoint.

Also preserve an invalid observation's available record before raising its gate error, for example by attaching the record to the raised gate exception and writing it in main's failure handler. Preserve failure status and all assertions; do not suppress late imports or move the trace start past first-request work.

These corrections and a replacement observation require authorization under the current no-retry stop boundary. No such corrective edits or rerun were performed after the failure. Existing evidence must remain intact and budget consumption must continue from the current ledger.

## Remaining gates and limits

Tasks 2–4 are unstarted. No application refactor, full-output baseline artifact, structural candidate check, compact/snapshot/concurrent-reader verification, corrected memory comparison, affected-owner broader suite, Node test, build, compiled desktop Versions/Play, navigation or latency comparison was performed in this run. No performance improvement is established.

Active cumulative budget: **71.0909602 / 600 seconds**, remaining **528.9090398 seconds**. This attempt consumed 5.469 seconds; the previous 65.6219602 seconds were retained. One sequential worker, no affinity, no retries. Temporary footprint at final inspection: **50769289 bytes**, below 1 GiB.

All Python checks ran under CP_TEST_MODE=1, GUID OS-temp CP_TEST_ROOT, CP_TEST_DIST_DIR inside it and embedded qBittorrent mode, with synthetic fixture data/media and deterministic metadata display. The real probe routes had no acquisition/monitoring callbacks. No production database/media copied/opened for tests; no system media clients or external providers contacted by the exercised paths. No storage/hardware test or polling.

No temporary server started. Read-only listener inspection still showed port 5000 owned by PID 5264, port 5127 unused. No live requests/restart/stop/reload, production dist overwrite, catalog/config changes, scans/downloads/imports/deletions, worktree/delegation/commit/push/package/tag/release or activation.

Evidence is under the run directory in `active-run.json`, within the original evidence root in `task-root.txt`. `budget.json` remains at that original root. The prior reports describe prior attempts only; this report is the current stop status.
