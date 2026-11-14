# First TV-tab load: bounded live capture

2026-10-23, Africa/Cairo. Capture window **15:34:57.620–15:36:24.326**,86.706 seconds. This is a new, expressly approved live observation after the earlier isolated implementation. It does not reset or extend that implementation's600-second ledger. No implementation/build change was made for this capture.

## Authorization and startup

Dante clarified the symptom is mainly the first switch to TV Shows: loaded Movie/TV pages are retained afterward. He approved the proposed90-second live capture with “ok go”, then instructed lam3y to do what was necessary rather than stop for routine permission. CP was not running: no app.py process or port5000 listener; a browser navigation returned connection refused. Started the existing app using this checkout's `.venv\Scripts\python.exe app.py`, with existing built dist, without dependency installation or rebuilding. No other backend was killed/restarted.

Runtime: `C:\Users\dante\Desktop\cinema paradiso`, backend PID31584, launcher PID40980,127.0.0.1:5000. App remains running. Startup/route output is retained under:

`C:\Users\dante\AppData\Local\Temp\cp-tv-first-load-13b6976d-0697-402e-a13c-d97961a97cdc`

Files: `server.log`, `server-error.log`. No scan, download, import, edit or delete command was issued. Normal application startup/background services were not disabled; this is not a claim of zero incidental cache/metadata writes. The initial UI displayed “1 new movie identified”, so normal background startup work is a possible confounder.

## Procedure and cache states

One new agent browser tab opened `/library`, initially Movies. After initial Movie cards were visible, switched to TV once. Next opened Discover (initially Movies), waited for its cards, then switched to TV once. Finally checked Movies→TV returns for each surface, separately labeled as cached returns. Closed only the agent tab at capture end. No further page load/probe followed.

Rendered counts observed: Movie Library40 cards/3953 total; TV Library33 cards; Movie Discover40 cards; TV Discover40 cards. These are DOM/rendered observations, not counts inferred solely from JSON.

`MediaWorkspace.jsx` confirms the cache mechanism: Movie children mount with the parent; TVWorkspace is lazy-imported/mounted only when selected, then retained under a hidden panel on later Movie switches. `App.jsx` likewise retains visited sections. Thus the first TV switch pays initial TV setup while switching back does not.

This was a **fresh backend startup and first frontend visit** to each surface. TV Library was visited before TV Discover, so Discover's first frontend visit may reuse backend/local metadata state initialized by Library; it is not an independently cold backend Discover measurement. No cache was cleared to manufacture another cold sample.

## Server timings

Existing production `X-CP-Route-MS`/`Server-Timing` hook prints routes above250ms. Timings below come from that existing log, include request handling/serialization/eligible gzip preparation, and exclude browser/network/render/image time. They are single observations, not medians or an instrumented function breakdown.

| Request / stage | Server duration |
| --- | ---: |
| Movie Library search |2751.5ms |
| First TV Library search |1221.1ms |
| TV Library options |848.2ms |
| Movie Discover search |1026.7ms |
| First TV Discover search |1258.6ms |
| TV Discover options |480.6ms |
| Discover card enrichment batch1 |1679.1ms |
| Discover card enrichment batch2 |2162.7ms |

Other concurrent first-TV requests included TV Lists777.2ms and TV Maintenance298.4ms. Routes may overlap; their durations must not be added as if sequential. Discover enrichment begins after the initial card response; its two batches run concurrently. The later metadata-completion stage is confirmed, but its entire visible critical path was not independently measured.

The request log contains one TV Library search and one TV Discover search. Cached Movie/TV returns generated no additional catalog searches. This confirms the retained-page behavior Dante described. It does not prove a cold-load speedup.

## Browser observations and measurement limits

Supported browser evaluation exposes read-only DOM state but not the Performance API. Attempting `performance.now()`/resource timing returned an undefined API; no browser request timings, wire/body sizes, transfer encoding, parse/paint timing or trace were obtained. Do not fill these gaps from the earlier synthetic probe or historical warm measurements.

- Initial browser document/UI observation at946ms still showed Movie Library loading;40 Movie cards were confirmed later.946ms is **not** Movie load completion.
- First TV Library click timestamp15:35:17.506.33 cards confirmed15.421seconds later, but the controller was not continuously observing during that interval. This is a loose upper bound contaminated by orchestration gaps, **not** a measured15-second Library delay.
- First TV Discover click15:35:47.011; click plus visible-card wait in one tool call completed in1635ms, with40 rendered cards. This includes automation overhead and is not a first-paint metric.
- Cached Movie→TV round trips took620ms for Discover and1025ms for Library, including both clicks/automation/wait. They are cache checks only, not cold-load measurements.

## What is established

1. The backend was genuinely started from the current checkout for the capture, and the page-retention cache works. No repeated warm return was presented as a fresh load.
2. TV Library's server request was faster than Movie Library's server request in this sample. The complaint cannot be attributed to a larger TV server duration from these data; it also is not disproved by that comparison because Movie work had already happened before the TV click.
3. TV Discover's initial request was modestly slower than Movie Discover and has an additional confirmed enrichment stage lasting up to2162.7ms per observed concurrent batch.
4. TV first-mount/lazy module setup differs from already-mounted Movie setup. Static source also confirms Discover still prepares local TV state before requesting provider results, and Library still serializes full detail records. These mechanisms exist; this capture does not individually quantify their costs.

## Unresolved and next owner-level rule

Actual TV Library click-to-visible critical-path attribution remains unresolved; the upper-bound observation cannot settle it. Discover's late enrichment is measured at the server, but whether the user means initial cards, fully populated labels or artwork must be distinguished in any subsequent claim. No new performance fix is declared complete and no before/after improvement is asserted from this one capture.

Any next change should address the first selected-tab initialization/metadata path in its existing owners while preserving retained pages, complete results/actions and fresh physical availability. Do not use warm tab returns or reduced SQL counts as proof that the initial visible wait is fixed. No additional live capture/restart or source change was performed after this86.706-second observation.
