# Followed releases fills the Home activity row

**Status:** Implemented and compiled desktop verified, 2026-10-14. Dante: "show as much to fit the card to align with the continue watching on the left" and "go fix easy no need for over testing".

## Problem and decision

- HomeWorkspace ReleasePanel sorts the full followed array, then discards all but three entries. The taller Continue Watching card leaves unused space on the right.
- Show the sorted list in a scrolling area that fills the existing panel. Continue Watching determines the row height; the long list must not increase it.
- Scope: existing desktop Home panel, its CSS, and one existing browser regression. No backend, data, restart, or unrelated UI changes. No open decisions.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| Home preview length, current request | Display as many movies as fit beside Continue Watching | Home ReleasePanel | Remove three-row truncation, scroll remaining entries | Requested amendment | Approved above |
| Existing follow interactions | Sorting, status, details, scan, View all and Following list | Home and Lists | Preserve | No | Preserve |

## Current design and ownership

- Checkout: Desktop cinema paradiso, master, be511f98846a67a182e5b371ad087938e9344362. Many pre-existing dirty and untracked files, including HomeWorkspace, home.css and app-smoke.spec.js; preserve their contents.
- Source owner: src/features/home/HomeWorkspace.jsx ReleasePanel. Layout owner: src/features/home/home.css with shared Home grid in src/styles.css.
- Follow data comes from App's existing followed-releases endpoints and sorting helper. No persistence change.
- Live baseline: port 5000, Python PID 55580 running app.py; main data owner is Desktop/data (current integration plan). Served index uses index-BOxSXlU5.js and index-Cz-Bcnef.css.

## Exact behavior contract

### Frontend

Reuse existing release-item buttons, panel heading and actions. Make the panel a column with a bounded scrolling list. With playback and no expanded details, prevent list content from sizing the shared grid row; match Continue Watching top and bottom. Without playback or with expanded details, cap list height at 360px so a long list cannot dominate Home. Expanded details retain their natural height below the panel. Preserve natural short/empty states, details placement, keyboard access and View all.

### Backend

Unchanged inputs, outputs, persistence and follow orchestration.

## Implementation sequence

1. Update the existing release watcher browser regression to assert full list availability, more than three visible rows, matching panel heights, and scrolling to the last row.
2. Remove the slice in ReleasePanel and bound its list in the existing home.css owner.
3. Run the single compiled browser regression, inspect its desktop screenshot, build the frontend. No backend restart.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| 12 follows with playback | Open Home | More than three full rows; aligned top/bottom; all entries scrollable | ReleasePanel/Home CSS | Existing browser regression |
| Available and monitoring movies | Select rows, open View all/Following | Existing actions and statuses; 12 complete entries | Home/Lists | Same regression |
| No playback | Open Home | Bounded list, maximum 360px | Home CSS | Desktop geometry check |
| Empty follows | Open Home | Existing empty message, no View all | ReleasePanel | Desktop geometry check |

## Verification and rollout

- Baseline: updated single regression fails on three-row truncation before the fix.
- Isolation: unique OS-temp CP_TEST_ROOT, CP_TEST_MODE=1, embedded fixture mode, port 15114, isolated dist. Production data and processes untouched by tests.
- Focused/compiled gate: build and the one release watcher browser test; screenshot inspection. No broad suite for this small change, per Dante.
- Rollout: build the approved frontend amendment for browser refresh; no restart, download, catalog change, commit or push.
- Report source/build/browser evidence and any remaining mismatch.

## Results

- Updated regression first failed because only 3 of 12 entries were rendered.
- Final compiled Playwright regression: 1 passed (7.3s). It verifies more than three fully visible rows, equal panel heights, scroll access to the last movie, details/streaming, View all, scan orchestration and the complete Following list.
- Desktop screenshot inspected: five full rows at 1920x1080, with aligned cards. More/less available height determines visible content naturally.
- Additional small desktop checks: no-playback list height 360px with all 12 entries scrollable; empty panel retains its message and hides View all.
- The check exposed panel collapse when details were expanded; containment now applies only while details are closed. Geometry assertions read all rectangles together to avoid Home's existing automatic details scrolling between measurements.
- No broad test suite, production data changes or backend restart. Served frontend rebuilt; users load it by refreshing.
