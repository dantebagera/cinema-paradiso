# Automatic download completion updates in Library and Following

**Status:** Implemented and verified in isolation, 2026-10-14. Dante answered “go” after the investigation proposed fixing import notification, reconnect reconciliation, and ownership cleanup blocked by a full source scan. No live scan, downloads, catalog repair, restart, production build, commit, or push is authorized.

## Problem and decision

- **What happens now:** Completed downloaded movies may require Force scan to appear in Library; Following removal is delayed. An executable probe confirmed that an already publishable import skips its catalog event, App ignores catalog-sync, and both App and the ownership endpoint wait behind the full source scan.
- **What Dante wants:** After verified import publication, Library refreshes automatically and confirmed owned films leave Following promptly, including during a slow provider search and after reconnect.
- **Confirmed / suspected / unknown:** The three mechanisms are reproduced. Current four completed jobs are published and unfollowed. Historical incident attribution is unknown because usable incident logs are unavailable and CP was restarted externally.
- **Open decisions:** None. Preserve final-card validation and catalog-confirmed ownership.
- **Scope:** Shared movie completion handler, Following response/store consistency and App lifecycle, isolated regression coverage. No visual redesign, TV retry changes, download policy changes or production operations.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and exceptions | Callers | Proposed behavior | Change? | Decision |
| --- | --- | --- | --- | --- | --- |
| Finalized Library truth; catalog repository | Stable probed file, accepted complete identity and ready artwork before Movie View publication | Import, Library, ownership | Preserve predicate; publish notification on either successful import path | No | Approved repair |
| Movie Following; Dante's clarification | Remove only confirmed catalog-owned movies; startup and Scan search pending movies afresh | Home, Lists, card indicators | Reconcile ownership during source search and on reconnect | No | Approved repair |
| Download all available; earlier explicit decision | Available films across all filters, existing CP review/submit rules | Home download | Unchanged | No | Preserve |
| TV Follow | Separate five-hour retry owner | TV | Unchanged | No | Preserve |

The existing smoke assertion requiring zero ownership requests during full scan accepts the motivating delay. Replace it with immediate ownership reconciliation while preserving the full scan's busy state.

## Current design and ownership

| Responsibility | Owner | Entry/callers | Preserve | Retire |
| --- | --- | --- | --- | --- |
| Import publication | app._handle_completed_qbittorrent_imports / CatalogRepository.final_card_publication | qBT completion monitor and recovery | Strict final-card boundary; pending retry journal | Success notification nested only in slow path |
| Event transport | CatalogEventBroker / src/api/catalogEvents.js | SSE, Library, App | Monotonic generations and reconnect sync | App ready-only restriction |
| Following persistence | UserCurationStore.apply_followed_scan | Scan, ownership, follow mutation | Locked merge, followed_at protects refollow | Source scan lock on ownership route |
| Following state | App.executeFollowedOperation | Startup, Scan, catalog event | No duplicate same-mode work; notices, scan busy | One shared operation gate for both responsibilities |

Baseline: Desktop master be511f98846a67a182e5b371ad087938e9344362, extensive pre-existing dirty work. Exact files saved under OS-temp cp-download-refresh-ee5b1e85550f48d99b48449e43bfa18a/baseline. Runtime PID 39180, served index-Bl7Ln0Vt.js/index-CQEVD-Zn.css at baseline. Live roots remain Desktop/data, E:\Movies and finalized catalog under LocalAppData/Cinema Paradiso/Catalog. Source and runtime are separate.

## Exact behavior contract

### Frontend

Reuse App's Following state and existing HomeWorkspace, Lists, LibraryWorkspace and catalog event client. No markup/styles change. Separate full-search and ownership promises. Coalesce repeat ownership events into one subsequent reconciliation so an event arriving during a read is not lost. Full scan busy indicator remains active until full search finishes. Accept both catalog-ready and catalog-sync. Apply returned Following snapshots only when their curation generation is at least the last applied generation; use the same response application for initial load and follow mutations.

### Backend

After final_card_publication confirms every imported video, emit the existing qbittorrent catalog-ready event before journal completion regardless of which branch made it ready. Pending, failed and outside-library imports emit no successful-publication event. Retain existing coordinator retry and jobs.json fields. Ownership POST runs without the long provider-scan lock and continues to use catalog ownership plus locked store merges. Return a current Following list and its generation together under the store lock at the response boundary; stale scan result movies cannot be labeled with a newer generation. No migration. Rollback is task-specific source restoration, preserving baseline dirty work.

## Implementation sequence

1. Write failing tests for import fast path, ownership while full scan is running, current response snapshot, reconnect and stale response ordering.
2. Move successful import notification to common completion branch. Separate source-search and ownership execution, retain event coalescing, and make current Following snapshot generation authoritative in responses.
3. Prove import -> real catalog publication -> SSE -> Library refresh -> Following removal in disposable desktop server, with full source search gated. Also verify reconnect sync and late full response cannot restore removed films.
4. Run focused then broader related suites and compiled desktop tests; one fresh independent review. Record results here. Do not activate production.

## Acceptance matrix

| Scenario | Action | Expected result | Owner | Check |
| --- | --- | --- | --- | --- |
| Already publishable import | Completion handler | Event delivered, job applied, Library refresh | Import/broker | Python real-catalog fast-path test + browser |
| Needs reconciliation | Complete import | Same notification after strict publication | Import | Existing/new Python regression |
| Failed / unready / outside | Completion handler | No premature ready event, correct pending/deferred journal | Import | Python regressions |
| Slow full search | Publish completed movie | Ownership removes it before search finishes; scan stays busy | Routes/App/store | Concurrent Python and desktop tests |
| Event during ownership request | Another commit | Coalesced follow-up observes latest catalog | App | Desktop test |
| Reconnect with missed event | Broker sync | Library refresh and ownership reconciliation | SSE/App | Real transport desktop test |
| Older delayed response | Deliver scan after newer ownership | Movie stays absent | Store/response/App | Python response + desktop ordering test |
| Explicit unfollow/refollow during scan | Merge old updates/removals | User mutation survives; old follow instance not restored/removed | Store | Existing curation tests |
| Startup / repeated Scan | Source lookup | Fresh eligible searches, existing quality and trusted identity rules | Acquisition | Movie Follow tests |
| Shared UI consumers | Home/Library/Lists navigation | Current rows/counts and existing toolbar controls | Desktop | Following card + smoke tests |

## Verification and rollout

- **Baseline:** Investigation probes failed the three proposed assertions. Historical completion tests missed notification/visible lifecycle; preserve unrelated baseline failures and report them.
- **Focused tests:** Python unittest import/migration, movie Follow, curation, event/ingestion suites with CP_TEST_MODE=1, unique OS-temp CP_TEST_ROOT, embedded qBT. Node catalog-event/curation suites. Tests must fail before fixes.
- **Broader tests:** All directly affected Python owners; desktop Following, scrollbar, Movie Follow and targeted app smoke scenarios. Report exact suite scope/counts.
- **Compiled UI:** Vite outDir exclusively below isolated root. Serve disposable Flask fixture on non-production port; real SSE and real catalog queries. No production dist build.
- **Live work:** Requires separate approval; none performed in this scope.
- **Reporting / contract comparison:** Distinguish source, compiled isolated proof and live activation. Preserve strict ownership/publication and Movie/TV boundaries.

## Execution ledger

- Setup: approved scope recorded, baseline preserved. Inline execution on Dante's current approved checkout avoids copying or discarding unrelated work. No commits; retain verification record and temporary baseline because Git history cannot record this uncommitted task.
- Backend RED -> GREEN: missing fast-path event, ownership blocked by scan, stale scan response; 3 regressions now pass. Existing owner suites 168/168 and broader ingestion/ownership/acquisition suites 102/102 passed.
- Compiled desktop: reconnect/stale response, repeat completion during ownership, and real import -> catalog -> SSE -> Library -> Following -> missed-event reconnect passed 3/3. Following/scrollbar/smoke regressions passed 12/12; Node cache/event checks passed 5/5.
- Cold Library regression exposed an unnecessary early ownership request on initial sync. Preserve the existing startup gate: while the initial Library load defers startup work, the later mandatory full startup scan performs its catalog ownership phase. Once startup is allowed, both sync and ready reconcile immediately. Existing cold-load test failed before this correction; rerun pending. This preserves the established startup contract rather than weakening its assertion.
- Cold-load and committed Library refresh checks now pass 2/2. Independent review found one important availability-alert race: stale scan rows were rejected together with their first alert even when a newer ownership response retained that available movie. Browser regression failed before correction. Preserve alerts only for the same currently available follow instance (identity + followed_at), deduplicate, and suppress alerts for removed/refollowed instances. This keeps existing notification behavior under the newly concurrent operations; no contract change.
- Final: review finding fixed, retained alert regression RED -> GREEN; removed/refollowed and duplicate candidate coverage passes. Final compiled desktop suite 20/20, separate real Movie Follow suite 2/2, all Node tests 133/133, backend owner suites 270/270. Real completion test also passed twice after explicit fixture reset; no Force scan request. Compiled screenshots and exact results: ../verification/download-completion/verification.md.
- Source-only finish: leave approved current checkout and unrelated dirty work intact, retain baseline/evidence; no branch integration or production operations. Final live read-only check still sees PID39180 serving the original bundle. No unresolved contract differences in isolated verification; live activation remains separate.
