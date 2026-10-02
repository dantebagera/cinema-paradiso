# Continue Watching menu and View card

**Status:** Live verified on 2026-10-03. Dante approved implementation with "go", then separately approved frontend deployment and the backend restart with "go", and a local commit with "commit". Pushes, tags, and releases remain outside this scope.

## Problem and decision

- Each `ContinueMovieCard` owns an independent native details menu; opening another leaves the first open.
- Dante wants the selected menu to stay open, with opening another menu closing the previous one, and a View card action opening that movie alone in Discover.
- Confirmed: `PlaybackHistoryService.continue_watching` computes canonical TMDB/IMDb IDs but omits them from the response. Discover already supports an expanded single-movie request.
- Scope: desktop Continue Watching menu, movie identity response fields, existing single-movie navigation, and media selection needed for that navigation. No redesign or movie/TV catalog changes.
- Missing movie identity produces a clear explanation without title matching. View card applies to movie entries; TV keeps its existing actions.
- No unresolved product decisions.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior | Affected callers | Proposed behavior | Changes the contract? | Dante's decision |
| --- | --- | --- | --- | --- | --- |
| Menu exclusivity, current request | One menu remains open; selecting another closes it | Home rail, shared ContinueMovieCard | Shared native details group | Requested change | go, 2026-10-03 |
| Single movie, current request | View card shows only the selected movie, expanded in Discover Movies | App, Discover, MediaWorkspace | Reuse single-movie request and saved identity | Requested addition | go, 2026-10-03 |
| Resume/Restart/Remove, existing behavior | Existing player and history endpoints/actions remain | Movie and TV rail entries | Preserve | No | Preserve |

## Current design and ownership

| Responsibility | Owner | Behavior to preserve | Obsolete paths |
| --- | --- | --- | --- |
| Continue menu rendering | src/components/movie-card/MovieCard.jsx | Native mouse/keyboard toggle, appearance, action dismissal | Independent menus replaced by shared rail group |
| Rail grouping and item callbacks | src/features/home/HomeWorkspace.jsx | Geometry, scroll, movie/TV presentation | None |
| Canonical continue identity | services/playback_history.py | Existing saved progress and canonical projection | None; expose computed identity |
| Single movie navigation | src/App.jsx, src/features/discover/DiscoverWorkspace.jsx | Expanded shared card, ownership/details, existing history | None; reuse existing request |
| Movie/TV selection | src/features/tv/MediaWorkspace.jsx | Manual media selection and separate state | None; observe explicit movie request |

Baseline: Desktop checkout, master at c62b3f3, extensive tracked/untracked existing work. Relevant Home/App/shared-card files are already dirty; preserve all prior edits. Port 5000 is PID 48560 (`Python312/python.exe app.py`), config.json selects Desktop data and cache. Served/local dist index is index-BucYOZpk.js. These are separate from the isolated verification build.

## Exact behavior contract

### Frontend

Reuse the existing native details menu, shared ContinueMovieCard, and menu CSS. One generated rail group is passed to its cards; browser details grouping closes the previous menu immediately for mouse/keyboard opening. Clicking unrelated content leaves it open; toggling the same summary closes it. Existing actions and View card close their own menu before invoking callbacks. View card is a third movie action with existing button styling and a Film icon.

App passes the selected item's canonical identity and path to `openMovieInDiscover` with source Continue Watching. Discover's existing `openRequestedMovie` shows one expanded card and loads its details/ownership. Explicit movie requests also select Movies through the existing MediaWorkspace owner, including when already mounted in TV. A missing TMDB ID explains the unavailable action and keeps Home visible; no title search or guessed match.

### Backend

Add `tmdb_id` and `imdb_id` from the already computed canonical movie to each `/api/player/continue-watching` item. No new requests, persistence, migration, retry, transaction, or progress changes. Existing limit/deduplication/order remain.

## Implementation sequence

1. Add failing browser assertions for exclusivity, action navigation, repeat selection, prior TV selection, and missing identity; extend canonical service result assertion.
2. Expose existing canonical IDs; group rail menus; add optional View card callback; wire existing navigation and media selection.
3. Run focused Python/browser checks, broader relevant suites, isolated compiled desktop verification, and review only the task's diff.

## Acceptance matrix

| Scenario | Action | Expected result | Check |
| --- | --- | --- | --- |
| Two menus | Open first, then second | Only second open | Browser, mouse and keyboard |
| Same menu/unrelated click | Toggle same/click heading | Closes on toggle, stays on unrelated click | Browser |
| View card | Choose first, return Home, choose second | One correct expanded card each time; menu dismissed | Browser |
| Prior TV state | View movie card | Explore Movies selected, exact movie visible | Browser |
| Missing identity | View card | Clear explanation, no search, Home visible | Browser |
| Canonical replacement of stale history key | Get continue items | Current saved identity and presentation | Python service |
| Resume/Restart/Remove and geometry | Existing actions | Existing requests and dimensions | Existing app-smoke test |
| TV consuming shared card | TV Home playback | Existing target/action behavior | Native TV focused test |

## Verification and rollout

- Red baseline: tests must reproduce multiple open menus, missing View card, and absent canonical response IDs before product edits.
- Python: CP_TEST_MODE=1 and unique OS-temp CP_TEST_ROOT; playback history, mutations, player API, Continue Watching UI and shared card suites.
- Browser: `npm.cmd run test:e2e -- tests/e2e/continue-watching.spec.js`, then relevant broader suites, using runner-created isolated data/dist on port 5117.
- Compiled UI: runner Vite build and browser assertions, desktop only; retain a screenshot when needed for visual review.
- Live remains unchanged unless separately approved. Rollout needs backup, build, backend restart for the added response fields, and live process/config/bundle/UI proof.
- Report source/isolated/live distinctly, including failures and remaining contract differences.

### Verification results, 2026-10-03

- Before product edits: canonical-ID assertion failed because the response omitted tmdb_id; browser baseline reproduced two open menus and the missing View card action (4 failures).
- Focused Python suites: 54 passed. All Node `.test.mjs` suites: 110 passed.
- Full default `npm.cmd run test:e2e`: 118 passed, 37 TV fixture-dependent tests skipped, zero failures, 1.8 minutes. This includes all four new Continue Watching scenarios, existing player actions/card geometry, Home trailer single-movie navigation, and shared Discover relationship behavior.
- Native-TV fixture run (`CP_TV_E2E=1`, `native-tv.spec.js`, grep `TV Home|TV library uses`): 2 passed. The remaining specialized TV tests were not run.
- Isolated Vite builds passed; desktop menu screenshot inspected at C:/Users/dante/AppData/Local/Temp/cp-continue-menu-20261003.png. Only the second menu is open, with Restart, Remove and View card using existing styling.
- Scoped `git diff --check` passed. Independent read-only reviewer found no actionable findings and excluded all prior dirty changes.
- Full browser log: C:/Users/dante/AppData/Local/Temp/cp-continue-browser-c88f531bc9834ab7a9b730c1c2d2a62e.log. Native TV log: C:/Users/dante/AppData/Local/Temp/cp-continue-tv-3f4f206ff3fa48e7bfe54ae607590519.log.
- Approved behavior is implemented and verified in isolated compiled UI. No known remaining difference in that environment. Live port 5000 remained PID 48560 and the existing Desktop bundle; the new backend IDs and frontend actions are not deployed. Deployment requires the separately approved backend restart and frontend bundle replacement.

### Approved live deployment and verification, 2026-10-03

- Fresh staged build passed and produced index-nL2MhvZw.js. Verified all 37 files in the prior dist backup, copied staged assets before index.html, and retained recovery files at C:/Users/dante/AppData/Local/Temp/cp-continue-deploy-9015d6d56aff4431bde9d14dcede02d8 (dist-before, config-before.json, playback_history-before.py).
- Used CP's authoritative POST /api/power/actions restart with after_download=false and close_qbittorrent=false. Existing launcher restarted the backend: port 5000 changed from PID 48560 to PID 32976, Python312/python.exe app.py. Desktop config still owns Desktop data/cache.
- Served index and main asset HTTP 200; live index references index-nL2MhvZw.js. Live continue API now returns saved TMDB/IMDb IDs, including The Egyptian (24973/tt0046949) and The Disappearance of Eleanor Rigby: Them (157829/tt3729920).
- Live browser, actual data: opened The Egyptian menu then Eleanor Rigby menu. Exactly Eleanor Rigby's menu remained open; first menu open attribute absent; Restart, Remove, View card visible.
- Selected View card: Discover displayed exactly one expanded Eleanor Rigby card, with owned badge and full saved movie details; Home menu dismissed.
- Selected Explore Shows, returned Home, and chose The Egyptian's View card: Movies automatically selected, exactly The Egyptian expanded, owned badge confirmed after ownership loaded. Returned Home with no menu open.
- qBittorrent PID 7784 remained unchanged through restart. No playback, restart-from-beginning, removal, or download action was invoked during UI verification.
- Screenshots retained beside the backup: live-menu.png and live-view-card.png. No remaining difference between the approved contracts and the observed live result.
