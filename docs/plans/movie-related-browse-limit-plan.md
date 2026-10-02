# Movie related browse limit and totals

**Status:** Implemented and live deployed on 2026-10-01 after Dante's separate approval. Dante chose 100 Recommended and 100 Similar after comparing a 200-total browse with a 400-result browse. No commit or publication was authorized.

## Problem and decision

- **What happens now:** `View all` enters Discover with 39 results per page for the pictured desktop. Pages 1–3 for *One Last Shot* return `total_pages: null`, `total_results: null`, and `has_next: true`; the UI shows only `Page N` and `Showing X–Y`. TMDB currently reports 586 Recommended results across 30 provider pages and 20,001 Similar results across 1,001 provider pages. CP can walk up to 500 provider pages per source. Later CP pages repeatedly scan from provider page 1.
- **What Dante wants:** A finite, clearly counted related-movie browse: up to 100 Recommended and up to 100 Similar movies. The All tab keeps Recommendations first and uses later Similar movies to fill duplicate gaps, yielding up to 200 distinct movies and a real last page. Each single-source tab shows at most its first 100 distinct movies.
- **Confirmed:** The movie relationship service intentionally reports an unknown total until provider exhaustion; `Pagination.jsx` faithfully renders that unknown state. The compact shared rail is already capped at 16 posters, independently of `View all`. An early archived implementation used eight posters and an eager complete View all; the saved September snapshot already had the current lazy behavior. This 100/100 browse limit is a new approved product rule.
- **Open decisions:** None for this scope. A movie present in both rankings stays visible in each individual source tab, but appears once in All under Recommended. All may fetch beyond the first 100 Similar entries to reach 100 distinct Similar additions. Its Similar additions can therefore include lower-ranked entries not in the individual Similar tab's first 100.
- **Scope:** Movie `More Like This` View all/related Discover page and the movie relationship API. Preserve the 16-poster shared rail, TV related-series implementation, search, collection navigation, ownership actions, history, and card design. No catalog persistence or migration.

## Current design and ownership

| Responsibility | Current authoritative file/component/service | Entry point and callers | Behavior to preserve | Competing or obsolete paths |
| --- | --- | --- | --- | --- |
| TMDB movie relationship paging, ranking, identity deduplication | `services/movie_relationships.py` | `app.py` `/api/tmdb/related`, `src/api/movieRelationships.js`, shared rail and Discover | Recommendations first; Similar separate; provider errors retryable; transient cache | Replace unbounded listing scan with source quotas in this owner; do not cap in route or JSX |
| Shared preview rail | `src/components/RelatedMovieRail.jsx` | Library, Discover, Lists, AI Control movie cards | 16 compact posters, source toggle, prompt preview load, View all | Do not make preview wait for a complete 100/100 count |
| Related Discover page/history | `src/features/discover/DiscoverWorkspace.jsx` and `src/components/Pagination.jsx` | View all from every shared movie card | Source tabs, ownership filter, page/back/breadcrumb and expanded-card state | Reuse existing paginator and context; no second renderer |

Baseline: Desktop checkout `master` at `c62b3f3f153e8e22a9a862ee4b1ac1beacd64291`, ahead of `origin/master` by one commit, with substantial unrelated tracked and untracked work. Relationship service, shared rail, and relationship tests had no local diff before this task; Discover already had the prior approved collection fix plus an older language-control removal. Root `config.json` is runtime configuration, root `data` is runtime data, and Flask serves root `dist` on port 5000 (PID 27972 at investigation). The served bundle matched root `dist/index.html` SHA-256 `A3E1B5B8AC9F23B0896F127CDDC3CC0B8EDE94AC3B10B3CE94CBBE580EAC10C8`. Focused pre-edit checks passed: five Python relationship tests and four Node relationship tests. No full-suite baseline is claimed.

## Exact behavior contract

### Frontend

- Keep `RelatedMovieRail`, `DiscoverWorkspace`, `PaginatedDiscoverResults`, and `Pagination` as the visual and navigation owners. No layout redesign. The rail continues showing at most 16 posters and loading without waiting for full totals.
- View all initially renders the requested provider page. Its page controls show the current range immediately and an exact `Page N of M` / `Showing X–Y of T` when the bounded summary completes. Show a compact note beside the existing source selector explaining the first-100-per-source browse limit. If the summary fails, show that the count is unavailable while keeping already loaded cards and Next/Previous usable.
- All returns up to 100 unique Recommended titles followed by up to 100 Similar titles not already in Recommended. Recommended/Similar tabs independently return their first 100 unique titles. Ownership filtering changes visible cards on a provider page, not the provider total. Back, browser Back, source switch, and page restoration retain the appropriate count and card state.
- No mobile or responsive amendment.

### Backend

- `/api/tmdb/related?tmdb_id=<id>&source=all|recommendations|similar&page=<n>&page_size=<n>` keeps its existing page/result fields and adds `source_limit: 100`. Page requests scan only enough provider pages to fill the requested capped page plus one lookahead. Stop Next at 100 for each single source and at 200 for All. Return exact totals when a source exhausts or the cap is reached; otherwise totals remain null until the summary finishes.
- The same route with `summary=1` computes the exact bounded total and page count using the same service selection routine, returning source counts and `source_limit`. The frontend requests it independently after View all or source selection. A provider failure returns the existing redacted 502 for the summary; it must not erase a healthy page. Individual provider page requests keep their existing failure/retry behavior. The service's thread-safe provider-page cache still deduplicates concurrent calls and expires after 15 minutes.
- For example, if TMDB has at least 100 Recommended and the first 100 Similar contain 20 Recommended duplicates, All takes the next 20 distinct Similar entries and reports 200 total. Similar alone reports its first 100. If a source has fewer than 100, the exact total is correspondingly smaller.
- No SQL or file writes, migration, compatibility fallback, or movie/TV cross-domain change.

## Implementation sequence

1. Refactor `MovieRelationships.listing` to use one capped source-selection routine for ordinary pages and exact summaries. Preserve validation, ordering, identity deduplication, provider cache, and error redaction.
2. Route `summary=1` through the same service in `app.py`. Extend the existing Discover relationship context with a separately loaded count; use the existing paginator and shared toolbar to render exact totals and the limit note. Preserve fast shared rail requests and all history paths.
3. Add backend and desktop regressions for caps, duplicate backfill, short/empty sources, exact last page, count failure, source switch, ownership and Back restoration. Run isolated focused and broader suites, build to an isolated dist, and verify rendered desktop states. Do not replace the live bundle or restart without separate approval.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| *One Last Shot* has large TMDB sources | View all | All eventually reports 200 maximum and finite last page, 100 Recommended plus 100 nonoverlapping Similar when available | Service, Discover, Pagination | Python fixture plus rendered desktop fixture; live only after separate approval |
| 39-card desktop page size, 200 All members | Advance through pages | Pages 1–5 show 39 each, page 6 shows 5, Next disables | Service, Discover | Python and Playwright |
| 100-member source tab | Select Recommended or Similar | Exact count 100, page 3 contains 22 at 39/page; source ranking preserved | Service, Discover | Python and Playwright |
| 20 Similar entries overlap Recommended | Open All | Later Similar entries backfill to 100 distinct additions; each identity occurs once in All | Service | Python |
| Short or empty source | Open source and All | Exact smaller total, no fake 100/200, no unwanted Next | Service, Discover | Python and Playwright |
| Summary fails after page succeeds | Keep browsing or retry | Cards remain, count-unavailable message appears, page navigation and Retry remain available | Discover | Playwright |
| Shared rail across movie surfaces | Expand card | At most 16 quick preview tiles; View all still opens Discover | Shared rail | Existing desktop suite |
| Related page with ownership filter, expanded card, and history | Switch source/page, expand, Back | Provider count stays source-specific; owned page scope and prior page/card restored | Discover | Existing plus focused Playwright |
| TV related series | Use TV View all | Movie 100/100 rule does not affect typed TV route or cards | TV/shared | Existing TV checks |

## Verification and rollout

- **Baseline:** Live API pages 1–3 for TMDB movie `1607127` each returned 39 results with null total and Next. Pre-edit focused Python 5/5 and Node 4/4 passed. Unrelated dirty work recorded above.
- **Focused tests:** `CP_TEST_MODE=1`, unique OS-temp `CP_TEST_ROOT`, then `python -m unittest tests.test_movie_relationships`; `node --test tests/movie_relationships.test.mjs`; focused `tests/e2e/movie-relationships.spec.js` against isolated dist.
- **Broader tests:** Relevant Python tests, full Python suite, Node suite, and default desktop Playwright suite if focused gates pass. Report skips and any pre-existing or new failures distinctly.
- **Compiled UI:** Build to `CP_TEST_DIST_DIR` inside `CP_TEST_ROOT`, verify desktop 1920×1080 and 1600×1000 source tabs, page 6, count loading/failure, cards, and Back with Playwright.
- **Live work, only if separately approved:** Back up root `dist`, verify actual process/config/data/bundle, rebuild and restart through the normal launch path, then measure/render *One Last Shot* and a smaller related set. Restore prior bundle and backend if navigation, count, or source behavior regresses.
- **Reporting:** State source-only, isolated-tested, and live statuses separately; no commit, push, tag, or release without separate authorization.

## Source implementation and verification, 2026-10-01

- `MovieRelationships` now applies a 100-title quota within its existing ranking and identity owner. The same selection path serves lazy result pages and an exact bounded summary. A page that stops partway through the final TMDB provider page no longer claims its partial prefix as the exact total.
- `/api/tmdb/related?summary=1` returns the bounded total and page count. `DiscoverWorkspace` requests that count separately, shows it in the existing toolbar and paginator, retains cards if counting fails, and offers a count retry. The shared preview rail remains capped at 16 without waiting for the summary.
- Final focused service tests: 9/9 pass, including 100/100, duplicate Similar backfill, 39-card page boundaries, short sources, provider failure, and the final-provider-page boundary. Node suite: 103/103 pass. Final focused desktop relationship suite: 21/21 pass against an isolated compiled bundle.
- Default full desktop Playwright run: 87 passed, 37 TV tests skipped, 1 failed. The failing People-search test hit a dynamic Discover JavaScript import failure; that exact test passed 1/1 in a fresh isolated rerun. The full run remains red. Full Python discovery passed 1,403/1,403; it started before the final provider-page boundary edit, which the later focused 9/9 service run covered.
- Those test results cover source and isolated builds. Live deployment evidence follows.

## Approved live deployment, 2026-10-01

- Before restart, port 5000 belonged to CP PID 27972, started at 05:07:59, serving root `dist/index.html` SHA-256 `A3E1B5B8AC9F23B0896F127CDDC3CC0B8EDE94AC3B10B3CE94CBBE580EAC10C8`. Root `config.json` selected the root `data` directory. The live *One Last Shot* All page returned 39 results with null total/pages and Next available. Other dirty source files had last-write times before that process started; related-movie source edits came later.
- Preserved the 37-file old `dist` and the previous relationship service at `C:\Users\dante\AppData\Local\Temp\cinema-paradiso-related-deploy-cf2f6f91e779493eb4f21d9c76fee6d4`. The backup index hash matched the served index. A separate candidate build passed before restart.
- Used CP's power action with `action=restart`, `after_download=false`, and `close_qbittorrent=false`. New CP PID 14628 started at 06:07:28; port 5000 served the candidate index hash `982C427CE0E475AFB23A2663C047BB7E855A31CF4A4A302E117671EF49C376BF`. Embedded qBittorrent remained PID 27216 with two active downloads; CP reported the restart completed.
- Live API for TMDB 1607127 (*One Last Shot*) returned All total 200, six pages at 39/page, and source counts 100 Recommended plus 100 Similar. Page 6 returned exactly five movies with `has_next=false`. Each individual source summary reported 100 across three pages.
- A fresh 1920×1080 browser session searched *One Last Shot*, opened its expanded card and View all, observed `Page 1 of 6` / `Showing 1-39 of 200`, advanced to `Page 6 of 6` / `Showing 196-200 of 200`, observed five cards and disabled Next. No catalog or media operation was requested for this verification.
