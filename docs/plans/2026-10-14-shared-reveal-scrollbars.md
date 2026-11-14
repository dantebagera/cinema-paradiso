# Shared desktop Reveal line scrollbars

**Status:** Approved for implementation, 2026-10-14. Dante selected option 3, Reveal line, then said "go" to shared desktop scrollbar implementation. Source, regression coverage and isolated compiled desktop verification are approved. Live rebuild/restart, data/config changes, commits and publication are separate actions.

## Problem and decision

- Home's Following release-list uses the browser's thick scrollbar with arrows; its visible track dominates the slim CP rows. Sidebar and IPTV have separate thin gray rules, leaving inconsistent behavior.
- Use a 2px line, transparent track, no arrow buttons, hidden when idle, visible in CP gold on hover, keyboard focus or scrolling. Preserve native wheel, keyboard and drag scrolling, using an 8px native scrollbar area around the line. Retain visibility for 900ms after the last scroll event.
- Scope: currently visible native desktop scrollbars throughout the app. Existing intentionally hidden horizontal card rails remain hidden. No card, grid, sizing, overflow or navigation redesign; no backend or persistence changes.
- Confirmed owners and baseline below. No open product decisions. Browsers without WebKit scrollbar styling use their native thin width; Chromium is the desktop visual acceptance target.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| Scrollbar appearance, current review | Reveal line option 3 | Home, sidebar, workspace, dialogs, TV, IPTV, pickers, textareas | 2px gold line during interaction; no visible idle thumb, track or arrows | Requested design amendment | Option 3 and "go", 2026-10-14 |
| Native scrolling | Wheel, keyboard, dragging and existing scroll restoration | All native scrollers | Preserve browser scrolling; change paint only | No | Preserve |
| Hidden card rails | HorizontalCardRail uses hidden native scrollbar and existing rail controls | Movie/TV/shared rails | Preserve explicit hiding | No | Explicit exclusion in approved scope |
| Home list height | Release list fills Continue Watching height and keeps all followed rows | Home ReleasePanel / FollowedReleasesDrawer | Preserve geometry, ordering, actions and scroll access | No | Preserve |

## Current design and ownership

- Checkout: C:\Users\dante\Desktop\cinema paradiso; master; be511f9. Extensive existing tracked and untracked changes, including styles.css, IPTV CSS, HomeWorkspace/home.css and app-smoke.spec.js. Baseline copies of touched existing files and Git status are in OS-temp cp-scrollbar-e3361f5642d74c2d93aa9e947f7c6ea8/baseline. Preserve those changes.
- App bootstrap: src/main.jsx loads generated playerTheme.css and shared styles.css. The generated theme's --projector-gold is authoritative for color and must not be edited.
- Existing native scrolling owners: HomeWorkspace ReleasePanel (.release-list) and FollowedReleasesDrawer (.followed-list-full); .nav-stack; .workspace; dialogs and feature overflow containers. These retain ownership of geometry and overflow.
- Competing appearance rules: .nav-stack in styles.css and IPTV sidebar rule in iptv.css. Retire their local scrollbar color/width declarations, centralize paint in src/styles/scrollbars.css, loaded by main.jsx.
- Activity owner: one document capture listener in src/utils/scrollbarActivity.js, installed by main.jsx, marks only the actual scrolling element. No wrappers, injected scrollbar UI, React state per scroll frame, observers scanning every element or feature-specific listeners. Cleanup removes the listener, pending timers and attributes; Vite hot replacement calls cleanup.
- Live baseline: HTTP 200 on 127.0.0.1:5000; Python PID 67636, parent 62380, app.py; bundle index-ClMEnn3C.js and index-Cz-Bcnef.css. Source package version 3.0.0-beta.2. Production data/config ownership remains app.py's Desktop config/data selection. Tests use only CP_TEST_ROOT; live data/process/bundle remains untouched.

## Exact behavior contract

### Frontend

- Reuse all existing elements. Native Chromium scrollbar box: 8px in either direction. Thumb: transparent 3px borders, padding-box background, leaving 2px visible ink. Transparent track/corner; display:none native scrollbar buttons. Thumb is transparent at rest, muted --projector-gold during hover/focus/scroll, brighter on direct thumb hover or active dragging.
- :hover, :focus-within and data-cp-scrolling select the same shared paint. Scroll capture works for late-mounted portals/dialogs and horizontal and vertical scrolling, without altering scroll position or canceling events. Activity expires 900ms after the latest event for each element independently. Document scroll resolves to document.scrollingElement.
- Existing selector-specific scrollbar-width:none and ::-webkit-scrollbar display:none retain precedence. Remove only competing sidebar paint declarations. Existing scrollbar-gutter rules remain.
- Reduce-motion preference disables paint transitions. Browser-native fallback has thin, transparent-idle, gold-interaction scrollbars; native control limitations determine exact thickness there.

### Backend

No inputs, outputs, persistence, provider requests or process behavior change.

## Implementation sequence

1. Add compiled desktop regressions for Home's real Following list, hover/focus/idle/scroll reveal, drawer scrolling, horizontal scrollers and preserved hidden rails; run against baseline and record missing-style failure.
2. Add shared native paint and one activity owner at bootstrap. Remove the two obsolete local paint rules; preserve every overflow, gutter and geometry rule.
3. Build to an isolated OS-temp dist, run new and existing shared desktop regressions, inspect screenshots, then run relevant broader Node and UI suites. Record any failures separately.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| 12 followed movies, Continue Watching present | Open Home with pointer outside list | All rows present; 2px ink width; transparent idle thumb and track; no arrows | ReleasePanel / shared CSS | Native-scrollbar desktop tests plus existing release watcher test |
| Populated list | Hover list, then move outside | Gold line appears then hides, without geometry movement | Home/shared CSS | Computed pseudo styles and bounding boxes |
| Keyboard user | Focus a release-row button, scroll | Bar remains visible; content remains accessible | Home/native scrolling | Focus and keyboard regression |
| Pointer outside, no focused descendant | Programmatically scroll; wait idle; scroll again | Bar appears while scroll activity is recent; hides after 900ms; reappears on second scroll | Shared activity owner | Desktop regression |
| Nested/later-mounted dialog | Open View all and scroll final row into view | Shared paint applies and all 12 rows remain reachable | FollowedReleasesDrawer | Desktop regression |
| Ordinary horizontal container / hidden card rail | Scroll horizontally | Ordinary bar is slim; rail stays hidden; both scroll normally | Shared CSS/HorizontalCardRail | Desktop regression |
| Sidebar/IPTV/TV/dialog containers | Inspect native scrollbar paint | Same shared owner applies; no legacy thick gray styles | Shared CSS | Generic and existing UI regression checks |
| Empty or short list | Open no-overflow list | Browser creates no scrollbar; unchanged empty message/content geometry | Native owner | Existing browser regressions |
| Reduced motion | Interact with scroller | Same reveal behavior without paint transitions | Shared CSS | Desktop regression |

## Verification and rollout

- Baseline: existing source is dirty; no general green-suite claim. New regression runs before implementation against isolated compiled baseline. Record the precise failure.
- Isolation: CP_TEST_MODE=1; unique OS-temp CP_TEST_ROOT; CP_TEST_QBT_MODE=embedded; CP_TEST_DIST_DIR beneath that root; free port 15144, distinct from production 5000. Provider access remains blocked by app test mode. Only test-owned processes may be stopped.
- Focused: Playwright scrollbar.spec.js and existing app-smoke release watcher regression. Evidence/screenshots under docs/verification/scrollbars.
- Broader: Node tests/*.test.mjs and relevant shared desktop/UI source suites; report actual counts and any failures, without weakening assertions or touching unrelated code.
- Compiled UI: inspect actual Home scrollbar idle/hover screenshots and dialog interactions, verify 2px visible ink / 8px native drag area, aligned Home cards and preserved hidden rails.
- Live rollout requires separate approval. No production rebuild, restart, catalog changes, commit or push in this implementation.
- Compare each acceptance row with observed evidence; retain any native-browser limitation in the report.

## Results

- Source implemented and isolated compiled desktop verified on 2026-10-14. Production frontend has not been rebuilt or restarted.
- Baseline: all four new scrollbar regressions failed on missing native styling/activity. Following and drawer ink-width checks received NaN rather than 2; actual scrolling elements had no reveal activity state.
- First implementation exposed a Chromium repaint issue: descendant hover matched the scroll container, but its thumb remained transparent. A browser probe confirmed element-level custom properties repaint correctly. Shared CSS now owns interaction color on the element and paints the native thumb from that property. No feature overrides were added.
- Final isolated build passed (Vite, 2.30s). Relevant compiled browser run: 13 passed in 22.4s, covering Home geometry and list interactions, sidebar behavior, IPTV shared surfaces and four scrollbar regressions.
- Native paint verification: headless Chromium normally suppresses scrollbar paint. The scrollbar test file now opts out of that launch flag. Its four tests passed again in 7.2s, including an actual native-thumb drag. Cropped Home hover/idle screenshots were visually inspected; hover shows the thin gold line and idle shows no thumb or track.
- Node suite: 133 passed, zero failures. Shared UI source suites: 47 passed, zero failures (workspace layout, unified cards, IPTV and watched/watchlist). This is not a claim of a full Python or complete browser suite run.
- Existing app-smoke.spec.js remains byte-identical to its task baseline; existing styles.css and IPTV CSS changes are precisely the removal of their two local scrollbar paint declarations. Scoped diff check passed. No unrelated dirty work changed.
- Contract comparison: reveal states, 2px ink/8px drag area, native wheel/keyboard/drag, late-mounted drawer scroll, Home alignment, Back navigation, reduced motion, ordinary horizontal scrollbars and intentionally hidden rails match the approved behavior in desktop Chromium. Exact fallback-browser width was not visually verified; native thin behavior is documented above.
- Evidence: docs/verification/scrollbars/following-hover.png, following-idle.png, isolated-build.log and node-suite.log. Test artifacts remain under the recorded OS-temp root. Isolated test server was stopped after verification.
- Live app still serves index-ClMEnn3C.js and index-Cz-Bcnef.css on port 5000, unchanged from baseline. A production frontend build is needed to activate the source change; no backend restart is required by this frontend-only amendment.
