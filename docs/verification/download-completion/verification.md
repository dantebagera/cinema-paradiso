# Automatic movie completion refresh verification

2026-10-14. Source implementation only. Approved plan: ../../plans/2026-10-14-automatic-download-library-following-refresh.md.

## Result and preserved contracts

Successful import publication now emits the catalog event on both the already-ready path and the path requiring reconciliation. Strict final-card validation remains authoritative. Following ownership reconciliation runs independently of a full provider scan, accepts reconnect sync, coalesces events during an active ownership request, and cannot replace newer rows with an older response. Current rows and curation generation are captured together by the curation store. Availability alerts survive overlapping ownership updates only for the same currently available follow instance; removed/refollowed instances do not receive stale alerts, and duplicate candidates produce one alert/sound. Cold Library startup still defers unrelated requests. Download review/quality rules, filter scope and separate TV retry behavior are unchanged.

## Tests

All Python commands used `.venv/Scripts/python.exe -m unittest`, `CP_TEST_MODE=1`, a fresh OS-temp `CP_TEST_ROOT`, and `CP_TEST_QBT_MODE=embedded`.

| Check | Final result |
| --- | --- |
| SQL migration parity, Movie Follow contract, user curation, catalog events, ingestion ownership, qBT API and service | 168 passed |
| Ingestion stability, queue, paths, API, Library ownership, acquisition decisions, Library action UX | 102 passed |
| `node --test` all `tests/*.test.mjs` discovered with rg | 133 passed |
| Compiled Following card, completion/ordering/alerts, scrollbars, four targeted app smoke scenarios | 20 passed |
| Real Movie Follow startup, consecutive Scan and reload against separate fixture | 2 passed |
| Real completion scenario rerun after fixture reset and screenshot assertions | Passed twice consecutively |
| Vite build to OS-temp/dist; `git diff --check` | Passed |

Before fixes, the import fast-path subscriber had no event; ownership during a gated full scan returned the unremoved movie; a stale full scan response contained removed movies. All three new Python regressions failed before changes and passed afterward. The compiled reconnect test failed with zero ownership requests before changes. The existing cold-Library startup test caught an early request, and passed after preserving the startup gate. Independent review reproduced a lost availability alert; the new retained-instance regression failed before correction and all retained/removed/refollowed cases passed afterward.

During combined UI verification, an earlier unrelated fixture request occupied the deliberately gated scan. The test server now arms the gate explicitly for the real completion test and releases/reset state between runs. The final combined 20-test run passed; no product assertion was weakened.

## Full visible path

The disposable `tests.download_completion_server` runs actual Flask import handling, strict SQLite publication, the real event broker and native browser EventSource. Media probe and external metadata boundaries use explicit local fixtures; no real torrent or provider is contacted. A completed imported fixture becomes visible in the mounted Library without Force scan, disappears from Following before the gated source scan finishes, and stays absent after its delayed response. Reconnect with an actually missed media generation invokes ownership reconciliation and removes the test refollow. The test asserts no `force_scan=1` request. Screenshots: [Library](automatic-library.png), [Following](automatic-following.png).

## Review and activation

One fresh read-only reviewer examined task-specific changes against saved dirty-work baselines. One important finding (availability alert ordering) was corrected with a failing-then-passing browser regression; no other critical, important or minor findings, and no declined behaviors. No second review was substituted for regression proof.

Baseline and task diff retained at `C:/Users/dante/AppData/Local/Temp/cp-download-refresh-ee5b1e85550f48d99b48449e43bfa18a`. Checkout is Desktop/master at be511f98846a67a182e5b371ad087938e9344362 with unrelated dirty work preserved. Isolated compiled bundle is index-kgvXGbPC.js. At final read-only production check, PID39180 still served index-Bl7Ln0Vt.js / index-CQEVD-Zn.css. No production build, restart, scan, download, data repair, commit or push was performed. Activation requires restarting through run.bat so it rebuilds the frontend and starts the changed backend. Historical incident attribution remains uncertain; these tests prove the repaired mechanisms and current intended outcome in isolation.
