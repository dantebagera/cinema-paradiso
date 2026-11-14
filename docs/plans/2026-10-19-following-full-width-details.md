# Home Following full-width movie details

**Status:** Implemented and verified in isolation on 2026-10-19; not live. Dante approved the in-chat scope with “go”: move the existing Following expansion beneath the whole Health/Following row, preserve the shared card and its behavior, and verify desktop geometry and related expansions. Live activation, restart, commit and push are separate actions.

## Problem and decision

- Following details render inside the right-hand `.home-followed-section`, leaving the Health column empty beside the expanded card. Evidence: HomeWorkspace.jsx and Dante's first screenshot.
- Dante wants the existing full-width expanded card used by Trending/Upcoming, with the same elements and actions (second screenshot).
- Confirmed: all three paths already call `detailsFor`, `MovieInspector` and `UnifiedMovieCard`; the container placement causes the width difference.
- No open product decisions. Scope is desktop Home placement, regression tests and isolated verification.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and exceptions | Affected callers | Proposed behavior | Changes contract? | Dante's decision |
| --- | --- | --- | --- | --- | --- |
| Current request and screenshots | Following expands across Home like Trending/Upcoming | Home followed selection | Existing details span both status columns | Implements explicit requested amendment | “go”, 2026-10-19 |
| Current Home design | Status panels keep their geometry; one details owner; selection/close restores focus and scroll | Following, Trending, Upcoming | Preserve | No | Included in approved scope |
| Shared movie card | Existing content and eligible actions | MovieInspector / UnifiedMovieCard | Preserve without changes to card internals | No | Included in approved scope |

## Current design and ownership

- Checkout: `C:\Users\dante\Desktop\cinema paradiso`, `master`, HEAD `be511f98846a67a182e5b371ad087938e9344362`. Extensive existing tracked/untracked work, including HomeWorkspace.jsx, home.css and Home tests; preserve all pre-existing edits.
- HomeWorkspace owns selection, details placement and close/scroll/focus; home.css owns the two-column status layout. Shared `UnifiedMovieCard` owns expanded-card rendering.
- Production observed before implementation: PID 22168 listens on 127.0.0.1:5000; served `/assets/index-_qTFeFca.js` and `/assets/index-C4xx5e9F.css` match current dist/index.html. Config owns data/cache under this checkout. Source and served build are separate; production will remain unchanged.
- Existing Home hybrid test expects details inside Following's narrow wrapper. Replace that obsolete placement assertion while retaining panel-size checks.

## Exact behavior contract

### Frontend

Render `detailsFor('followed')` as a third child of the existing status grid, after Health and Following, spanning all columns. Remove its old render inside Following. Use the same `.home-inline-details`, heading, Close button, MovieInspector, UnifiedMovieCard and callbacks. The grid's existing 18px gap separates the status row and details; remove the details' additive top margin only in this placement. The shared 16px rail details margin remains untouched. Details push Trailers and later sections down. Keep status-panel and list dimensions, selected movie identity, single-details behavior, repeat-click collapse and close focus/scroll recovery. At narrower desktop widths where status cards already stack, details follow both cards at full available width. No mobile changes.

### Backend

No API, persistence, configuration, acquisition, provider, concurrency or migration changes.

## Implementation sequence

1. Strengthen the compiled UI regression to measure full-width Following details and preserve panel dimensions; observe failure before source edits.
2. Move the existing details render and add the grid-spanning placement rule. Remove the obsolete narrow placement, with no new card implementation.
3. Verify repeated selection, Close, section switching, adverse detail responses and existing Following/Home suites using an OS-temp test root and isolated compiled bundle.

## Acceptance matrix

| Scenario | Action | Expected result | Owner | Evidence |
| --- | --- | --- | --- | --- |
| Following selection, 1280/1600/1920 desktop | Select row | Details width/left edge match Home; below both panels; panels unchanged; no horizontal overflow | Home status grid | Browser geometry and screenshots |
| Long title and count 9999 | Select long row | Toolbar fits; title remains available; list 190px; details full width | ReleasePanel / shared details | Existing strengthened test |
| Repeat click / Close | Open and collapse | No details remain; original row focus and scroll restored | selectMovie / closeDetails | Browser assertions |
| Switch Following, Trending, Upcoming | Select in each surface | Exactly one details card in current section; existing metadata/actions preserved | detailsFor | Browser assertions |
| Details loading/error | Select followed row with delayed/failed response | Full-width card remains; existing status and summary behavior preserved | MovieInspector | Browser assertions |
| Empty/short/populated list and controls | Run existing Home/Following suites | Existing geometry, membership and controls preserved | ReleasePanel | Existing suites |

## Verification and rollout

- Before source edits run the new width regression against an isolated baseline build and record the expected narrow-width failure.
- Build with `npm.cmd run build -- --outDir <unique OS-temp root>/dist`; do not overwrite served dist.
- Run Playwright directly against a dedicated test-mode server with CP_TEST_ROOT/CP_TEST_DIST_DIR inside that root, external providers blocked and qBittorrent external access disabled. Do not use the wrapper that forces system qBittorrent.
- Focused: new Following geometry/lifecycle cases. Broader: Home hybrid and Following suites, plus relevant existing Home expansion/scroll cases.
- Inspect rendered desktop screenshots, run whitespace checks scoped to changed files, and report test counts and any failures accurately.
- Production is not rebuilt/restarted. Report source plus isolated compiled verification, with live activation outstanding.

### Verification results

- Pre-fix compiled desktop regression failed as intended at 1600px: details left edge was 817px to the right of Home's left edge.
- After the source change: isolated Vite build passed. Existing outDir-outside-project warning only; production dist was not overwritten.
- Home hybrid plus Following suites: 32 passed, 0 failed. Newly added delayed/error test run separately: 1 passed, 0 failed.
- Four relevant Home app-smoke cases (layout without history, canonical rating/votes, individual torrent review, release watcher/filter/streaming): 4 passed, 0 failed. The release-watcher test's obsolete containment assertion now requires details below Following.
- Python layout/Continue Watching/watched-watchlist checks: 11 passed. Node Home movie/trailer model checks: 4 passed.
- Focused checks separately confirmed all three desktop widths, shared summary/cast/actions, repeat-click/Close, scroll/focus recovery, section switching and Back/Forward. Rendered screenshots inspected at 1280, 1600 and 1920px; status dimensions remain unchanged and details span the full grid.
- Saved screenshots, build log and broader browser log: `docs/verification/following-full-width-details/`. Unique disposable data/build/artifacts: `C:\Users\dante\AppData\Local\Temp\cp-following-width-a116401e7a504923b573d95eed5f28a2`.
- Changed tracked files passed `git diff --check`; new CSS/plan passed whitespace checks. Playwright emitted its environment NO_COLOR/FORCE_COLOR warning; no browser application errors were captured by the new geometry cases.
- Isolated server PID 23140 stopped. Production remains PID 22168 on port 5000, serving unchanged `/assets/index-_qTFeFca.js`. No production restart, data/config change, download, commit or push.
- Approved-contract comparison: requested full-width placement achieved in compiled isolated UI; no observed difference in preserved card/actions, status geometry, selection or navigation. Live app still has the old bundle pending separate activation approval.
- Independent scoped code review: no findings after reviewing source, tests, build/test logs and the 1600px screenshot.
