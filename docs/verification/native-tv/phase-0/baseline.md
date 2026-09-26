# Native TV / acquisition Phase 0 baseline — 2026-09-18

## Gate outcome

**Historical snapshot, superseded by the approved repair.** Dante authorized continuation and repair of this gate. The catalog factory is now serialized, eight cold concurrent requests pass, and the repaired baseline passed all 1,254 Python tests (`python-fixed.log`). The original observations below are preserved as evidence of the defect.


**BLOCKED: existing cold catalog initialization fails concurrent requests.**
Phases 1–8 have not been implemented. No application, service, frontend, or
existing test source was changed. The four revised approval documents were the
first repository changes and have identical SHA256 hashes to their originals.

The movie plan's Gate M0 says: "Stop if: the baseline is red for a touched
surface, runtime ownership is unclear, or current source and served bundle
differ." The executive plan also requires stopping and reporting a failed gate.
This is a measured baseline startup/catalog defect, not a TV regression.

## Checkout and authorization

- Actual assigned worktree: `C:\Users\dante\.codex\worktrees\0870\cinema paradiso`.
- Starting HEAD: `adfa90a2e984f59585c7635e839f0c594b74b4cc`, detached; initially clean.
- App version: 2.8.5. Source movie schema: 11.
- The handoff explicitly authorizes this assigned worktree, superseding the
  planning worktree location and earlier documentation-only status in the
  verbatim approval documents. The planning worktree was read only.
- No commits, branches, pushes, tags, releases, packaging, live provider
  searches, torrent submissions, or production operations were performed.
- npm dependencies installed with `npm ci --ignore-scripts --no-audit --no-fund`.
  Existing Python 3.12 dependencies were available. No production virtual
  environment was used.

## Current ownership verified from source

| Responsibility | Owner |
|---|---|
| Movie schema, persistence, publication | `services/catalog_store.py`, `services/catalog_repository.py`, `services/canonical_catalog.py` |
| Catalog creation/cache and process lease acquisition | `app.py:_catalog_repository_for`, `services/catalog_writer_lease.py` |
| Prowlarr transport | `services/source_search.py:ProwlarrClient` |
| Movie search / Follow policy | `app.py:_prowlarr_search_movie`, `_torrent_variants_from_prowlarr_results`, `_check_followed_releases` |
| Transfer, manifest validation, jobs.json, recovery | `services/qbittorrent.py:QBittorrentManager`, `QBittorrentJobStore` |
| Completed-download scheduling | `services/download_monitor.py:DownloadImportMonitor` |
| Measured file facts / targeted ingestion | `services/media_file_facts.py`, `services/library_ingestion.py` |
| Playback and progress | `services/player_routes.py`, `services/playback_history.py`, player manager/runtime |
| Streaming configuration | `app.py:/api/streaming/config` |
| Streaming URL validation and modal | `src/utils/appUtils.js`, `src/App.jsx` |
| Movie UI / source review | `src/components/SharedMovieCards.jsx`, `SourceReviewDialog.jsx`, `TorrentActions.jsx` |
| Served frontend | `services/frontend_routes.py`, assigned worktree `dist` |

Under CP test mode configuration, movie roots, caches, catalog, leases, and
qBittorrent job data resolve into OS-temporary storage. The disposable movie
database is named `.catalog-test.sqlite`. Background services are not started
by the app's test-mode entry point. External urllib provider calls are blocked.
No native TV authority exists yet.

## Evidence

| Check | Result |
|---|---|
| Node utilities (`node --test tests/*.test.mjs`) | 95/95 pass |
| Full Python discovery | 1,252 tests, 210.564 seconds; 3 failures caused by selecting system qBittorrent mode for tests expecting embedded mode |
| Affected modules rerun with mocked embedded mode | 8/8 pass: `tests.test_power_api`, `tests.test_react_routes` |
| Vite production build | Pass, 1,660 modules |
| Desktop Playwright | 63/63 pass, 1600×1000, Chromium, port 5117 |
| Served HTML | SHA256 `97D589F0BB7E5B8F509A7436D682F8068A6B75E427C507725EB2C94F5B62FF59` matches dist |
| Served assets | All 33 match dist; `served-hashes.json` records each hash |
| Real cold served runtime | Catalog lock errors produce HTTP 500 on catalog-dependent endpoints, including `/api/library/reconcile` and `/api/player/continue-watching` |
| Independent concurrent reproduction | Two runs, each 1 success / 7 failures; checked-in reproduction result from second run |

Do not describe the full Python suite as green: the complete run used the wrong
mode for three tests, followed by a focused correction. The passing Playwright
suite is also insufficient evidence of a clean real startup: many interactions
use mocked API responses, and cold concurrent catalog requests failed outside
those assertions.

The unconfigured Discover API returns expected HTTP 400 responses. The disabled
embedded Downloads frame returns HTTP 409. Its icon URL still attempts a proxy
request, blocked by test-mode network protection, resulting in HTTP 500. No
network block was relaxed and no real qBittorrent client was started.

Temporary evidence roots:

- Python: `C:\Users\dante\AppData\Local\Temp\cp-tv-phase0-5432d78b4631433ea4aebd0e4445421d`
- Browser: `C:\Users\dante\AppData\Local\Temp\cp-tv-browser0-9379880c7b904fc4a249811c66d750a6`

The browser root contains desktop Library, Discover, and Downloads screenshots,
served HTML, assets, and console observations. The Library screenshot was
visually inspected. This is an empty disposable movie library, not a TV UI
acceptance result. No production screenshot or production API was used.
The isolated server (PID 38448) was stopped after verification; port 5117 no
longer had a listener. No other server process was stopped.

## Reproduction and repair decision

Run `python docs/verification/native-tv/phase-0/reproduce_catalog_startup.py`
from this worktree. It creates its own unique OS-temp root, enables test mode,
starts no server or client, and issues eight simultaneous calls to the existing
catalog owner. It exits nonzero if any call fails. Data is retained for review.

Confirmed cause: `app.py:_catalog_repository_for` reads an empty repository cache
and acquires an exclusive process lease before publishing the repository in the
cache, without synchronizing concurrent initialization. Other threads in the
same process then attempt independent leases for the same catalog and fail with
Windows sharing error 32. The lease itself correctly rejects duplicate owners.

Recommended prerequisite repair: serialize initialization in the existing
catalog factory, checking the cache again inside the lock. Preserve independent
process exclusion, exception cleanup, and path-based ownership. Add coverage for
simultaneous first requests, failed initialization followed by retry, and genuine
second-process exclusion. Do not weaken or bypass the writer lease.

Decision requested: authorize this prerequisite catalog-startup repair, then
rerun Phase 0 and resume the already-approved TV/acquisition sequence. This is a
specific response to the mandatory failed-gate stop, not a request to reapprove
Phases 0–8. No repair has been applied.
