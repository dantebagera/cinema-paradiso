# IPTV bulk launch readiness and desktop layout

**Status:** Implemented and verified in isolation, with the broader-suite timing limitation recorded below. Dante said “ok go” to the investigated launch/readiness and layout fixes on 2026-11-06. Live activation remains separate.

## Problem and decision

The Start form ignores provider preparation and sits above an old completed job in the same panel. The backend correctly rejects an unstable provider generation with `iptv_projection_in_progress`. Catalog review only refreshes while its tab is open, so a selected queue may remain stale on Bulk matching. An earlier preparation error remains visible after readiness recovers.

Approved outcome: dedicated launch panel with selection and batch size on the left, primary Start action on the right; preparation progress and readiness gating; refresh selected sources after preparation; previous job in a separate panel below. Desktop only. No new matching algorithms, automatic application, budget changes, backend guard bypass, production rebuild/restart, or live job launch. Earlier decisions on automatic recovery/application remain pending separate work.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| Launch readiness, reported failure | Start only against a stable provider generation | Metadata bulk launch | Reflect backend readiness and refresh selection before enabling Start | No; repair frontend to honor backend guard | “ok go” |
| Desktop layout, screenshot and proposal | Clear launch action and old-job results | IPTV Metadata | Separate launch and job sections, right-aligned Start | Approved presentation change | “ok go” |
| Batch budget, selected-source confirmation, locked/manual results | Preserve backend validation and existing controls | Bulk API and saved jobs | Unchanged | No | Preserve |
| Other shared hook consumers | Preserve status/phase recovery and errors | Maintenance and AI features | Add explicit freshness and guarded error dismissal, retain existing data | No | Preserve |

## Current design and ownership

| Responsibility | Current authoritative file/component/service | Entry point and callers | Behavior to preserve | Competing or obsolete paths |
| --- | --- | --- | --- | --- |
| Provider status and polling | `useIPTVMovieStatus.js` | IPTV workspace, Maintenance | Poll preparation and worker states; ignore superseded requests | Add freshness to the existing owner |
| Selected queue and launch | `IPTVWorkspace.jsx` | Metadata tabs | Provider/filter scope, count checks, no duplicate launch | Remove catalog-tab-only refresh restriction when selection exists |
| Launch/job presentation | `IPTVBulkMetadataJob.jsx`, `iptv.css` | Bulk matching tab | Review, Apply, Pause/Resume, Cancel, errors | Replace mixed launch/results layout |
| Request error state | `useAIJob.js` | AI consumers | Lost-response protection and error visibility | Guarded dismissal of only the handled preparation error |
| Stable generation guard | `IPTVMovieStore._resolve_bulk_selection` | Bulk-start API | Reject preparation races, preserve data | No change |

Checkout `master`, `be511f9`, substantial existing dirty/untracked work; preserve it in place. Current backend PID 36428 (parent 23996), data under the checkout's `data`; served bundle previously verified as `index-BR6h-hEp.js`. Source changes are not live activation. Knowledge index covers TV Follow only; no mapped IPTV guide exists.

## Exact behavior contract

### Frontend

- Retain outer `ChatGPT bulk IPTV metadata` region. Use existing `iptv-enrichment-progress` card style independently for a `New bulk matching` form and a saved-job section below.
- Launch card uses a two-column desktop row: selected-source count/request estimate and existing numeric input on the left; `Start matching` primary button on the right. Use existing button styling, 18px card padding and spacing, not a new design system.
- Existing `IPTVMetadataProgress` renders provider preparation progress in the launch card. Unknown/stale status, preparation running/failed/not-started, failed or refreshing selection, unavailable GPT/TMDB, active jobs/application, and invalid batch size cannot launch.
- While selected sources exist, refresh their queue on Bulk matching as well as Catalog review. Include provider projection generation and explicit refresh revision in the loaded-selection key. A refresh error shows an explicit retry action. No automatic GPT launch after recovery.
- An API preparation race triggers status/selection refresh. Clear only that exact recorded error once a fresh completed preparation response and fresh successful selection arrive; preserve unrelated errors. Provider changes discard this local recovery marker.
- Completed/cancelled/failed jobs are labeled `Previous bulk job`; running/resumable/applying jobs remain `Current bulk job`. Preserve all review/apply/control functionality. Empty selection directs the user to Catalog review.
- Maintenance keeps existing status data and controls. No mobile changes.

### Backend

No production backend or persistence changes. The existing API remains authoritative for generation, count, provider, consent, locks and budget. Offline fixtures may expose completed saved-job state for realistic UI tests. No migration or catalogue writes outside isolated test roots.

## Implementation sequence

1. Add compiled desktop tests for preparation gating, selection refresh, retry recovery and separated layout; observe failure on existing source.
2. Extend status freshness and guarded error dismissal in existing hooks; correct selected-queue refresh in its owner.
3. Restructure the existing bulk component and narrowly scoped CSS.
4. Run targeted tests, all bulk desktop scenarios and shared AI desktop regressions; inspect compiled desktop screenshots.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| Previous completed job, selected queue, preparation running | Open Bulk matching | Separate previous-job card, visible preparation counts, Start disabled, zero POSTs | Bulk desktop | Playwright |
| Preparation completes on bulk tab | Poll and refresh queue | Start remains disabled until refreshed queue arrives, then enabled; no auto-start | Workspace/status | Playwright with delayed queue response |
| Readiness changes between check and POST | Server returns preparation error | Refresh readiness, block while preparing, clear only handled error after recovery, explicit retry launches once | Hook/workspace/API | Playwright race fixture |
| Selected queue refresh fails | Retry selection | Actionable error; Start disabled until successful retry | Workspace | Playwright |
| Initial/new selection and invalid size | Launch | Existing size/count budgeting and validation retained | Bulk form/API | Existing desktop suite |
| Paused/running/applying/saved jobs | Use controls/review | Existing actions, status recovery, receipts and lock protection retained | Bulk component | Existing desktop suite |
| Provider switch or stale in-flight response | Change provider | Old readiness/selection/error cannot enable new provider | Shared hooks | Existing provider-switch regression plus scoped readiness checks |
| Desktop geometry | Render populated and preparing states | Start right of selection/settings, job section below launch, no overlap | CSS | Bounding boxes and screenshots |

## Verification and rollout

Use `tools/run_playwright_e2e.ps1 -AIProviderOffline` to build into a unique OS-temp directory and run the compiled desktop UI with synthetic providers only. Test screenshots and reports go to the isolated root and then task evidence. Preserve production `dist`. Run relevant Python UI contract checks and node IPTV tests. Inspect screenshots before completion. Document initial failures and final results separately. No live matching, source application, app restart, commit, push or release is included.

## Execution record

Implemented in the existing owners listed above. Provider status exposes freshness while retaining cached display data; disabling/reopening invalidates readiness, and switching between Movies and Metadata requests fresh status. Selected queues refresh on the bulk tab and after provider preparation. Only a handled preparation error is cleared after both status and queue recover. Launch and previous/current-job cards are separate, with the primary action right-aligned.

Regression sequence: the original compiled UI left Start enabled during preparation. The first test attempt used the wrong intercepted status URL; the corrected `/movies/metadata/status` test reproduced the real failure. After implementation the preparation test passed. Test-fixture account uniqueness and cancellation request metadata were corrected so scenarios could share an isolated server. Five bulk tests then passed. Fresh review identified a cached-ready return-to-Metadata gap; the new held-response test reproduced it (after narrowing an ambiguous Home locator), and the status owner was corrected.

Final compiled bulk suite: **6/6 passed** with the initial readiness-error retry and Home/Movies revisit coverage included. Evidence root: `C:/Users/dante/AppData/Local/Temp/cinema-paradiso-playwright-5013d978fe9545c391cb840b99d79131`. Compiled entry: `index-Cok6xiDI.js`. Desktop screenshots inspected at 1600x1000 and copied to `docs/verification/chatgpt/iptv-bulk-launch-readiness-2026-11-06/`. New launch geometry, preparation progress, previous-job separation and retained Apply/review controls are visible without overlap.

Python UI contracts: **35/35 passed** (`tests.test_iptv_movie_ui`, `tests.test_iptv_ui`, `tests.test_ai_control_ui`). Node IPTV/AI client checks: **11/11 passed** (`iptv_sync_policy`, `iptv_movie_filters`, `ai_provider_client`, `ai_pick_status`). Scoped fresh review is clean after the return-to-Metadata correction.

Shared AI desktop suite (`tests/e2e/ai-provider.spec.js`): **14 passed, 1 timed out, 3 skipped** in root `C:/Users/dante/AppData/Local/Temp/cinema-paradiso-playwright-9ae3914f4c9346b0adb5f9adfb6bce5c`. The 500-movie recommendation budget scenario exceeded its 15-second completion wait; job-status reads took up to 1.65 seconds. The unchanged compiled frontend passed that scenario alone in root `cinema-paradiso-playwright-ec61276420a34cff8366f4c3fe8b5ef5`. The final compiled frontend then passed the failed scenario and all three skipped scenarios (**4/4**) in root `C:/Users/dante/AppData/Local/Temp/cinema-paradiso-playwright-3870f7b574ae4780a2283259c00f66c4`. No assertion or timeout was relaxed. This establishes focused success for all 18 shared scenarios across the runs, not a green full shared-suite run; the full-run timing sensitivity remains unresolved and outside this IPTV launch change.

Final checks: compiled build succeeded, scoped tracked-file `git diff --check` passed, and production listener still belongs to PID 36428. No remaining difference was found against the approved launch/readiness and desktop-layout contract. No full backend-suite or live-provider claim is made.

Production remains on `index-BR6h-hEp.js`; production `dist/index.html` SHA256 is `61088AAC67B93889EA48F9D3393ABB019363481B607B3F6FDF057289E92CDCAC`. No production bundle replacement, restart, GPT request, catalogue edit, commit or push was performed for this task. No backend matching, auto-apply or budget contract changed.
