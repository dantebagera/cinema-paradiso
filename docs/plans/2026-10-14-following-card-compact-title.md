# Following card title and controls on one row

**Status:** Implemented and isolated compiled desktop verified, 2026-10-14. Dante explicitly requested removal of “and upgrade signals” and moving the followed-movie title onto the download/bell/filter row. Source changes and isolated desktop verification; live activation remains separate.

## Problem and decision

- **What happens now:** HomeWorkspace.jsx's ReleasePanel displays “Followed movies and upgrade signals”; home.css forces its section heading into a column with a 16px gap, giving actions their own row.
- **What Dante wants:** “Followed movies” beside the existing controls, with list content higher.
- **Confirmed / suspected / unknown:** Confirmed in the current JSX/CSS and existing 1600px screenshot. Production backend's loaded source revision is unknown and irrelevant to this frontend-only amendment.
- **Open decisions:** None. Preserve the unrequested “Release watchlist” kicker above the combined title/actions row.
- **Scope:** Home's Following card only, desktop. Preserve download/filter/scan/status rules, scrolling, card height and other Home sections. No library/config/data changes, restart, deployment or publication.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| Header text/layout, current explicit request | Followed-movie title shares action row | Home ReleasePanel | Remove suffix and combine title/actions | Explicit presentation amendment | Dante's request, 2026-10-14 |
| Following status/filter/source-review plan | Four existing filters; count reflects filter, bell all available, download all available regardless of filter through explicit shared review | ReleasePanel and Home orchestration | Preserve | No | Existing approved behavior retained |
| Following height/native scrolling | Continue Watching sets card height, all followed rows accessible; no-playback list stays bounded | Home grid, ReleasePanel list | More vertical room within same card | No | Existing approved behavior retained |

## Current design and ownership

Desktop checkout `C:\Users\dante\Desktop\cinema paradiso`, branch master, HEAD be511f9. HomeWorkspace.jsx, home.css and tests/e2e/following-card.spec.js already contain unrelated dirty/untracked work; apply narrow edits and preserve snapshots. Fresh live read: port 5000 PID 47748; served index-B0cho5l8.js / index-DFMDe_8_.css. Configuration/data remain the existing Desktop app.py/config.json owners. Do not use live catalogs in tests.

| Responsibility | Current authoritative file/component/service | Entry point and callers | Behavior to preserve | Competing or obsolete paths |
| --- | --- | --- | --- | --- |
| Following header/content/actions | HomeWorkspace.jsx::ReleasePanel | Home | Existing buttons/select and callbacks | Remove long title suffix and title wrapper |
| Header geometry/list containment | src/features/home/home.css | Home grid | Equal card heights, native scrolling, other section headers | Replace explicit column rule with row; no override stack |
| Dropdown/tooltips/source review | SearchModeSelect, Tooltip, Home/source review owners | Existing ReleasePanel actions | Native select, all-available preview and explicit submit | Reuse unchanged |

## Exact behavior contract

### Frontend, if affected

Move the existing kicker immediately above `.section-heading`. Its gold 11px typography and 8px bottom gap remain. Header contains the existing h3 with exact text “Followed movies” on the left and unchanged action nodes in existing order on the right: download, bell, scan, count, filter. One center-aligned row at 1600/1920 desktop widths. Compact existing toolbar gaps and dropdown width only as necessary to fit the narrow 2:1 Home grid, keeping full option labels readable. Keep 32px icon controls, 34px dropdown height, typography, colors and 16px gap before the list. No new mobile rules or unrelated grid redesign.

Final spacing: 8px between title/action group; 4px between actions; filter count minimum 18px. Dropdown is 136px wide, with 8px left/24px right padding; options inherit its existing .76rem font size so the complete “Awaiting release” label stays on one line. Other shared select surfaces are unaffected.

### Backend, if affected

None. No new inputs/outputs, persisted state, scans, retries or source policies.

## Implementation sequence

1. Add rendered desktop regression checks to following-card.spec.js and verify the current column header fails alignment. Record existing Following tests as baseline.
2. Update ReleasePanel's header markup/title and change existing Home header CSS. Preserve controls/components/callbacks and list ownership.
3. Compile into an isolated temporary dist; run Following tests plus existing scrolling and Home height checks; inspect screenshots.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| Populated Following with Continue Watching | Inspect 1600/1920 desktop | Short title and all controls center-aligned inside card; list starts below combined row | Home header | New geometry tests and screenshots |
| Each filter, including Awaiting release | Change selection | Full filter labels usable, toolbar remains in row; existing counts/statuses unchanged | ReleasePanel | Geometry + existing filter test |
| Empty/no playback | Open Home | Same compact title/header, zero counts, disabled download, bounded list | Home | New desktop case + existing empty test |
| Available follows under any filter | Open source review | All available movies previewed; no automatic queueing | Existing shared source review | Existing Following suite |
| Long list/inline details | Scroll/select/open details | Card-height/last-row/native scrollbar rules preserved | Home grid/list | Existing scrollbar and release-watcher regression |
| Error/pending preview | Close/navigate/retry | Existing review lifecycle preserved | Home orchestration | Existing Following suite |

## Verification and rollout

- **Baseline:** Six existing Following checks passed. Three new desktop regressions failed before edits, confirming about 44px between title and control centerlines. A separate label-fit regression caught wrapping in the narrowed filter before its final padding was corrected.
- **Focused tests:** Entire following-card.spec.js, including new rendered header regressions.
- **Broader tests:** Existing scrollbar tests and app-smoke's “release watcher fills” regression; no backend suite for a markup/CSS-only amendment.
- **Compiled UI:** CP_TEST_MODE=1, unique OS-temp CP_TEST_ROOT, embedded qBittorrent test mode, CP_TEST_DIST_DIR under test root. Build with npm.cmd run build -- --outDir <test-root>/dist; test on a free nonproduction port.
- **Live work, only if approved:** No production dist replacement or restart in this scope.
- **Reporting:** Record test counts, screenshots, source-only status and any remaining mismatch.
- **Contract comparison:** Exact shortened title/aligned controls; existing filter/download/scroll/height contracts remain unchanged.

## Results

- Final Vite build passed. Complete Following browser file: 9 passed (3 new desktop geometry/full-label cases plus 6 existing filter/download/scan/empty/error/navigation cases).
- Relevant broader browser regression gate: 3 passed, covering Home/Continue Watching height, full followed set, scrollbar reveal and wheel/keyboard/native dragging/filter scrolling.
- Screenshots inspected at 1600px and recorded at 1600/1920: shortened title, center-aligned unchanged controls, complete Awaiting release label on one line, list higher, card-height unchanged.
- Targeted diff whitespace check passed. Independent read-only review found no introduced issues in the two-file source amendment; controls, ordering, accessible names, callbacks, rules, scrolling and containment remain intact. Viewports outside the existing 1600/1920 desktop gate were excluded; no mobile work or broader grid redesign was performed.
- Evidence: `docs/verification/following-card-compact-title/`. Source snapshots/test artifacts retained under `C:\Users\dante\AppData\Local\Temp\cp-following-compact-b9b8805671644d0192b983a869cb5e3c`. Server used CP_TEST_MODE=1, embedded qBittorrent mode, port 5139, isolated dist under its test root and browser response fixtures.
- Contract comparison: explicit title/layout amendment implemented; existing filters, global available download scope, scan, empty/error/navigation behavior and full-list scrolling contracts passed. No backend behavior change or backend suite was included.
- Production port 5000 still belongs to PID 47748; checkout dist retains index-B0cho5l8.js / index-DFMDe_8_.css. Source-only, compiled/tested in isolation; no production activation, data/config change, restart, commit or publication.
