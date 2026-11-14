# Library view actions inside the filter header

**Status:** Implemented; isolated verification recorded below. Dante approved the displayed desktop mockup with “ok go” on 2026-10-14. Source, isolated builds and desktop verification only; activation, restart, commit and publication are separate actions.

## Problem and decision

- **What happens now:** `WorkspaceChrome` renders a separate `workspace-view-actions` row above `WorkspaceControls`. The screenshot and current Movie/TV Library callers confirm wasted vertical space.
- **What Dante wants:** Media View, File View and scan/refresh on the same always-visible row as the collapsed search/filter heading; remove the separate row completely.
- **Confirmed / suspected / unknown:** Source ownership and the screenshot are confirmed. The live backend's loaded source revision is unknown; this change has no backend work.
- **Open decisions:** None for the approved layout. Keep current callbacks, accessible names, selected state, TV Maintenance action and independently remembered Movie/File disclosure states.
- **Scope:** Movie and TV Library, Media and File views. Shared control-header presentation; preserve Discover and Lists. Desktop only. No data/configuration changes or production bundle replacement.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| Library layout, displayed mockup | View tabs and scan remain visible alongside the filter heading | Movie/TV Library and File views | Merge the two rows | Approved presentation change | “ok go”, 2026-10-14 |
| Existing controls and callbacks | Clicking view/scan does not toggle filters; disclosure retains current per-view rules | WorkspaceControls, LibraryWorkspace, TVWorkspace, TVFileView | Preserve | No | Preservation within approved scope |
| Movie scan and TV refresh | Existing domain owners retain scan/refresh behavior; no new scans on disclosure | Library callbacks, TV revision callbacks | Preserve | No | Preservation within approved scope |
| TV Maintenance action | Retain identity-review entry point and pending count | TV Library Media/File | Place beside view and refresh actions | No | Preservation within approved scope |

No tests redefine scan, refresh, selection, filtering or disclosure behavior.

## Current design and ownership

Baseline checkout: `C:\Users\dante\Desktop\cinema paradiso`, `master`, HEAD `be511f9`. Extensive pre-existing tracked and untracked edits include all affected callers and styles; preserve them with narrow patches. Production port 5000 is owned by PID 45076, Python312 running `app.py`. Current served entry is `index-kgvXGbPC.js` with `index-CQEVD-Zn.css`; production serves checkout `dist`, and configuration belongs to checkout `config.json` (TV root `G:\TV`). No production data is used for tests.

| Responsibility | Current authoritative file/component/service | Entry point and callers | Behavior to preserve | Competing or obsolete paths |
| --- | --- | --- | --- | --- |
| Sticky navigation and containment | WorkspaceChrome.jsx | Movie Library, TV Workspace/File View, Discover and Lists | Navigation, sticky position and background | Remove obsolete actions prop/standalone row |
| Disclosure and summary | WorkspaceControls.jsx | Shared catalog surfaces, directly or through TVSearchControls | Toggle label, summary click, focus, notice and body, temporary card collapse | Add optional sibling actions inside header |
| View and scan buttons | WorkspaceViewActions.jsx | LibraryWorkspace and TVWorkspace | Existing JSX, labels, callbacks, loading and selected states | Reuse directly; no cloned controls |
| TV disclosure inputs | TVSearchControls.jsx, TVFileView.jsx | TVWorkspace | Existing search, filters and disclosure lifetime | Pass existing actions to shared header |

## Exact behavior contract

### Frontend, if affected

Use the approved screenshot arrangement: unchanged Movies/TV Shows navigation, then one full-width control panel. Heading/chevron left; muted loaded/filter/selection summary right within the disclosure button; 12px gap and subtle divider before actions; view tabs then scan, followed by the existing TV Maintenance button when applicable. Reuse `WorkspaceViewActions`. Actions are sibling buttons, never nested in the disclosure button. Header padding stays at existing spacing tokens; embedded controls use 36px height, view group 280px wide, 8px action gaps. One line at desktop widths 1280, 1600, 2048 with no clipping or horizontal overflow. Body expands below the same header. All non-action callers retain their current 44px minimum header and disclosure interactions. No new mobile rules.

Long query/active-filter summaries in action headers stay on one line with ellipsis as needed. Full summary remains in the DOM and a native hover title, and the search input retains the complete query. Keep loaded and selected counts readable. Non-action headers keep their existing wrapping summary layout.

### Backend, if affected

No backend change, migration or new persistence. Keep exact existing Movie scan and TV refresh requests, failure behavior and disabled/loading presentation.

## Implementation sequence

1. Add desktop acceptance tests to the existing compiled-UI suite; show the shared-row assertions fail against the current build. Run existing sticky Library/disclosure checks as the baseline.
2. Extend WorkspaceControls with optional sibling actions; move current actions there in all three callers and remove WorkspaceChrome's obsolete standalone actions path. Update only the corresponding shared CSS.
3. Build to a unique OS-temp test root; run focused desktop tests, then the existing shared-controls suite. Inspect rendered desktop screenshots. Record results here.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| Collapsed library, populated | Inspect at 1280/1600/2048 | Heading/count/tabs/scan in one <=60px header; actions inside panel; no horizontal overflow | Movie/TV | Added rendered geometry tests |
| Expanded filters | Toggle by keyboard; scan/refresh | Actions remain aligned/visible, callback runs once, disclosure remains open | Movie/TV | Added interaction tests |
| File View | Switch from Media and back | Same merged header, correct pressed tab, controls independent | Movie/TV | Added tests plus existing per-mode test |
| Sticky behavior | Scroll with filters closed/open | Tabs/header/actions remain pinned | All four Library views | Existing sticky tests |
| Empty/error/loading | Existing fixtures and delayed/failed rescan | Header remains usable; existing disabled scan and error behavior preserved | Movie/shared | Existing empty cases plus scan test |
| Shared callers without view actions | Navigate Discover/Lists, collapse/expand, select | Existing query/draft/selection and summary-click behavior preserved | Shared controls | Full existing suite |
| TV identity review | Inspect Media/File header | Maintenance action visible and remains reachable | TV | Existing sticky test and new geometry |

## Verification and rollout

- **Baseline:** The three existing sticky/disclosure checks passed. All seven initial regression checks failed on the old build, showing actions 55px above the heading. A later long-query regression failed with a 120px header before summary containment was corrected.
- **Focused tests:** `playwright test tests/e2e/workspace-controls-empty-layout.spec.js --grep 'combined Library header|Library remembers|Movie Library removes|TV Library retains'` against isolated compiled assets.
- **Broader tests:** Full `workspace-controls-empty-layout.spec.js`; focused Python workspace/library presentation checks if relevant. Report baseline failures without weakening assertions.
- **Compiled UI:** Build with `npm.cmd run build -- --outDir <CP_TEST_ROOT>/dist`. `CP_TEST_MODE=1`, unique OS-temp `CP_TEST_ROOT`, `CP_TEST_QBT_MODE=embedded`, `CP_TEST_DIST_DIR` inside it. Isolated fixture server on a free nonproduction port; browser API fixtures prevent live requests.
- **Live work, only if approved:** No activation in this scope. Preserve production dist and process. A future approved frontend activation uses a recoverable dist snapshot and verified staged assets; no backend restart is necessary for this source-only layout change.
- **Reporting:** Record build/test counts, screenshots, baseline exceptions and source-only status.
- **Contract comparison:** Verify merged row and existing callbacks/disclosure against each row above.

## Verification results, 2026-10-14

- Isolated root: `C:\Users\dante\AppData\Local\Temp\cp-combined-header-094ed49f323c420298d3e35588eec032`; test-mode server on port 5138, with embedded qBittorrent test mode. Production port 5000 remains PID 45076; checkout dist still points to index-kgvXGbPC.js and index-CQEVD-Zn.css.
- Build passed. Initial focused browser gate: 10/10. Initial full shared-controls suite: 71/71. Python `tests.test_workspace_layout_ui` and `tests.test_library_action_ux`: 70/70.
- Independent review reproduced the long-query problem at 1280px and found no changed callbacks, state ownership or missed callers. It is covered by an additional regression for both normal spaced text and a filename with no spaces. Corrected focused combined-header tests: 8/8. Final full shared-controls rerun: 72/72. Final focused Python rerun: 70/70. Build and diff whitespace checks passed. Reviewer verified the corrected filename-query header stays 52px, has no overlap/toggle overflow, and has no remaining findings.
- Rendered Movie 2048px and TV 1280px screenshots inspected: integrated row, count before tabs, scan within panel, TV Maintenance retained. Screenshots and logs saved under `docs/verification/library-combined-header/`.
- No backend/data/configuration edit, live scan, production bundle replacement, app restart, commit or publication. Source-only changes and isolated compiled-UI proof.
