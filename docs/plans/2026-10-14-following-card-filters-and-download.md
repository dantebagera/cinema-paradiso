# Following card filters and available-movie bulk download

**Status:** Implemented and isolated compiled desktop verified, 2026-10-14. Dante approved the mockup, swapped Monitoring to gold and Awaiting release to muted gray, then said "great go". Bulk scope: "all available regardless which filter is on". Live activation remains separate.

## Problem and decision

- Home ReleasePanel scrolls the full followed set, making View all and FollowedReleasesDrawer redundant. The header has no in-card filters, counts or bulk action.
- Replace View all/the drawer with All, Available, Monitoring and Awaiting release filters, a matching-movie count, scan, total available bell badge and download-all-available icon. Exact left-to-right order: download, bell+badge, scan, filtered count, filter. Toolbar is the second header row, as reviewed.
- Header matches the approved mock: Release watchlist kicker, Followed movies and upgrade signals title. Rows and native scrolling keep their owners; no grid or unrelated UI redesign.
- Download always previews every available followed movie, regardless of filter; it reuses CP's shared source review and explicitly submitted downloads. No new automatic queueing or backend policy.
- Scope: desktop Home presentation/orchestration, obsolete drawer removal, meaningful regression updates and isolated compiled verification. No data/config changes, real downloads, live restart/rebuild, commits or publication. No open product decisions.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| Header/filter design, reviewed mock | All/Available/Monitoring/Awaiting release; matching count; total available badge | Home ReleasePanel | Implement approved mock and badge colour swap | Explicitly requested amendment | Mock approval and "great go" |
| Bulk scope, explicit clarification | All available followed movies regardless of filter | Home/source review | Pass all available movies into shared preview | Explicitly requested amendment | "all available regardless which filter is on" |
| View all and drawer, current request | Scrollable card replaces duplicate popup | Home/old drawer | Remove View all, drawer state/component and unused styles | Explicitly requested amendment | Mock approval and "great go" |
| Current release labels/date handling | Available/Owned first; future date = Awaiting release; otherwise Monitoring, including missing dates | Home existing status owner | One status classifier drives labels, filters, counts and availability | No | Preserve existing rule; Owned remains visible in All if a stale owned row survives reconciliation |
| CP source review, existing Movie/Lists/AI policy | Trusted indexers/default quality, fresh ownership/source/queue checks, blocked rows and explicit submission | previewSourceReview / SourceReviewDialog / backend acquisition owners | Reuse shared policy without overrides | No | "follow the same rules" |
| Home height/actions/scrolling | Full set fits Continue Watching row; details and source/follow actions, scan and navigation work | Home/grid/inline details | Preserve; replace drawer-only source test with existing inline Find torrent path | No | Preserve |

## Current design and ownership

- Desktop checkout C:\Users\dante\Desktop\cinema paradiso, master/be511f9, ahead 9, extensive existing dirty work. Task snapshots of HomeWorkspace.jsx, home.css, styles.css, App.jsx and affected browser tests are under OS-temp cp-following-header-45e75fa15bcb4308be15a2070cec781f/baseline.
- HomeWorkspace.jsx owns ReleasePanel, releaseStatusLabel and the obsolete FollowedReleasesDrawer. home.css owns current Home geometry; styles.css owns existing release row/icon styles. App.jsx supplies followed state, full scan and notifications.
- Shared native select: SearchModeSelect, src/features/search/SearchModeSelect.jsx and .search-mode-select CSS. Shared tooltips: Tooltip. Shared source preview: src/api/sourceReview.js. Shared review/submission: SourceReviewDialog. Shared dismissal/workspace visibility: useDismissiblePopover.
- Backend: /api/sources/review/preview uses the shared Movie default quality and effective trusted-indexer policy; _movie_acquisition.review owns eligibility/source preparation. /submit and existing acquisition owners own revalidation and jobs. No backend change.
- Runtime baseline: port 5000, Python PID 63216, parent 67180, app.py. Served index-CK8mlgj2.js and index-DjI4tCgC.css. Live data/config selection remains app.py's existing Desktop owners. Tests use a separate OS-temp root and isolated dist.

## Exact behavior contract

### Frontend

- Existing ReleasePanel remains authoritative. A single release-status classifier replaces the label-only function, returning available, owned, monitoring or awaiting; display labels remain unchanged. All includes all rows, including a transient Owned exception; Available filters available; Monitoring excludes future releases and owned/available; Awaiting release includes only future unreleased rows. Available keeps priority even if its release date is future, matching the existing label rule.
- Filter defaults to All and remains local to the mounted Home panel. Changing it resets only the inner list scroll to the top. Count always appears immediately left of the select, including zero. Bell badge always shows the whole followed set's available count, regardless of filter.
- Reuse SearchModeSelect and Tooltip rather than a duplicate dropdown or tooltip. Reuse release-sync-button styling for the download icon. Available badge stays green, Monitoring uses gold border/text/tint, Awaiting release uses muted gray. This swap affects badges only.
- Download is disabled at zero availability or while preparing review. It uses the available snapshot at click time and does not depend on the filter. Open the existing SourceReviewDialog with loading, error, ready/blocked, quality choice, select-all/none and explicit submit behavior. No source-policy or quality override is sent.
- Closing review, Escape, navigation away or unmount invalidates the pending preview so a late response cannot reopen it. Reuse useDismissiblePopover for Escape/workspace hiding and existing dialog/backdrop close behavior; restore focus to the visible trigger. Pass existing global notify into Home for shared submission notifications.
- Remove drawer component/state, JSX invocation and exclusive CSS. Preserve row selection/inline MovieInspector, follow toggle, torrent review, source actions and current scroll-height alignment.

### Backend

Existing preview input serialization: movie identities/title/year/poster, same shared endpoint/default policy as Movie Lists. Existing outputs rows/blocked/defaults and failures are presented by SourceReviewDialog. Persistence, validation, duplicate/owned/queue handling, downloads, retries and quality/indexer policy remain unchanged. No migration.

## Implementation sequence

1. Add failing compiled regressions for four filters, date/owned exceptions, counts and colour swap; bulk all-available input and explicit submission; empty/error/pending-review dismissal. Update obsolete drawer regressions to the approved in-card/inline-details behavior, retaining unrelated assertions.
2. Refactor the existing status owner and ReleasePanel. Add Home orchestration that calls the shared review API/UI; add App notify prop; remove obsolete drawer-only markup/styles.
3. Build to an isolated dist, run new Home tests, shared source-review tests, existing Home/scrollbar/navigation regression suites and relevant Node/Python checks. Inspect native-size desktop screenshots and preserve baseline dirty work.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| Mixed released/future/available/owned/missing-date follows | Select each filter | Correct mutually exclusive status membership, All retains exceptional owned row, correct count | ReleasePanel status owner | Compiled browser test |
| Available row with future date | Available/Awaiting filters | Included only in Available, consistent with existing availability priority | Status owner | Adverse-case browser assertion |
| Monitoring/Awaiting rows | Inspect badges | Monitoring gold, Awaiting muted gray; Available green | Existing row CSS | Computed colours + screenshot |
| Any filter selected | Click download | Preview input is all available followed movies; no submit request on opening | Shared preview | Browser request/output assertions |
| Preview returns ready/blocked rows | Review/submit | Existing quality/selection/blocked rules and explicit submit preserved | SourceReviewDialog/backend | Browser + existing backend tests |
| Empty/no available follows | Open Home/filter | Zero count/badge; disabled download; correct empty state; scan still usable | ReleasePanel | Browser test |
| Long list with Continue Watching | Scroll/select/filter | Equal panel height, native scrolling and last-row access; toolbar fits at 1600/1920 desktop widths | Home/native scroll | Existing and new browser checks |
| Preview pending/error | Close, Escape, navigate away, resolve late response | No reopened dialog; focus recovery; readable error and retry via reopened review | Shared dismissal/Home request guard | Browser test |
| Scan updates following statuses | Remain in selected filter | Count/list/badge update from same followed state, without stale view | App/ReleasePanel | Browser test |
| Existing individual actions/Lists/navigation | Select row/use details/Back | Existing torrent review, follow toggle, full Following list and history preserved | Home/Lists | Updated broader browser regression |

## Verification and rollout

- Baseline: new regressions run against isolated compiled pre-change source; record expected missing-filter failure. No full-green baseline claim.
- Isolation: CP_TEST_MODE=1; CP_TEST_QBT_MODE=embedded; unique OS-temp CP_TEST_ROOT above; CP_TEST_DIST_DIR below it; port 15145, independent of 5000; provider access blocked.
- Focused: new following-card.spec.js plus existing Home release watcher, source-review, scrollbar and navigation checks. Broader: all Node tests and relevant source-review/backend/shared UI suites. Report actual counts and failures; no full-suite claim from focused runs.
- Compiled UI: actual desktop render at 1600/1920, screenshot of mixed statuses/filters/header, toolbar clipping and Home height checks.
- Live activation/data/download/restart remains separate. Production dist and processes are not changed by isolated verification.
- Before completion compare implementation to every approved contract, report source/isolated/live status and any remaining gap. No backend/policy contract changes are authorized.

## Results

- Baseline compiled regression failed on the missing in-card filter before production edits.
- Final isolated Vite build passed in 2.29s. Compiled desktop regression run: 16 passed in 22.2s. This includes all six new Following tests, existing Home/individual source/Lists behavior, shared owned-upgrade/quality source review, IPTV separation and native Reveal line wheel/keyboard/drag/filter scrolling.
- Node suite: 133 passed, no failures. Relevant Python suite: 165 passed, no failures, including existing quality/trusted-indexer defaults, blocked source buckets, selected-ready-only submission and bulk-upgrade revalidation.
- The first broader Python run exposed a pre-existing source-text expectation demanding the already-replaced three-row preview and old drawer filterCounts. That expectation contradicted Dante's previously approved full scrolling list and current popup removal. The obsolete assertions were removed, manual full-scan/reconciliation assertions retained, and complete user-visible scrolling/filter behavior remains verified by compiled browser tests. This is not authority for a new product contract.
- Browser checks caught disabled-trigger focus restoration before React committed the cancelled loading state. Focus now restores on the next frame only for the same review generation and a visible, enabled trigger. Tests verify Escape and real Back/Forward navigation, await both delayed preview responses, and verify neither response reopens review.
- Native-size Monitoring/Awaiting/All screenshots inspected at 1600px desktop. Toolbar fits without overflow, control order matches the approved mock, Monitoring is gold, Awaiting gray and Available green. Existing 1920px Home alignment/full-list regression passed.
- Contract comparison: all approved filters/counts/availability priority, global available download scope, shared defaults/blocked rows/explicit submission, empty/error/cancel/navigation states, individual actions, full Following list, native scrolling and Home height preservation passed their stated checks. No known remaining implementation difference. No backend or acquisition-policy changes.
- Removed FollowedReleasesDrawer/state/markup and its 174 obsolete CSS lines; verified no remaining production references. App change is one notify prop. Other existing dirty work is preserved; scoped diff check passed.
- Evidence under docs/verification/following-card: following-header.png, following-monitoring.png, following-awaiting.png, build.log, node.log and python-final.log. Test artifacts and baseline snapshots remain under the recorded OS-temp root.
- Independent read-only code review found no actionable issues. The reviewer confirmed classifier priority, global available scope, shared review policy, cancellation generation/visibility checks and complete drawer retirement. Unrelated dirty changes, mobile work, stricter date validation and existing shared review-component behavior were outside this approved scope; no new owner or backend change was needed.
- Production frontend/process/data unchanged; currently served baseline index-CK8mlgj2.js and index-DjI4tCgC.css remains separate from the isolated test build. run.bat builds source before starting CP, so the next authorized normal launch activates this source; live rebuild/restart was not performed here.
