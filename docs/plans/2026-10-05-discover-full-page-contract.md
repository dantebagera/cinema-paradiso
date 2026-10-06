# Restore Discover full-page card counts

**Status:** Implemented and verified in isolation on 2026-10-05. Dante approved: "go fix and dont stop untill u finish" after the proposed normal/Advanced Discover repair. No live deployment, restart, commit, push, or release is authorized.

## Problem and decision

- Discover currently slices provider results before removing duplicates. Both GET Discover and provider-native Advanced Discover can return short nonfinal pages. The existing overlap test requests 40 but accepts 39.
- At Dante's fullscreen desktop size, the main movie grid has three columns/39 cards with the sidebar expanded and four columns/40 cards with it collapsed. Successive nonfinal pages must be full, unique, and complete rows.
- Dante explicitly decided that finite single-page results and the final page display every remaining matching movie, including incomplete rows. Three matching Lord of the Rings movies must all display.
- Scope: existing Movie Discover GET and Advanced POST paging, including title/local-filter scans, shared paging regression coverage and compiled desktop proof. Other catalog domains, card styling, Home previews and different target sizes are outside this repair.
- Confirmed baseline: clean Desktop checkout, master at 7e7cda5; 39 focused Python tests and 3 card-grid Node tests pass before changes. Production listens at 127.0.0.1:5000 (PID 38404 when investigated); served index matches local dist and references index-vJjXGZME.js. Source/runtime/served build remain distinct. Normal runtime config is config.json next to app.py; isolated tests use unique OS-temp CP_TEST_ROOT.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior | Affected surfaces | Proposed behavior | Changes contract? | Decision |
| --- | --- | --- | --- | --- | --- |
| Full pages; Dante's earlier discussion and current clarification | 39/3 expanded, 40/4 collapsed; consistent nonfinal counts | Main Discover movie grid | Deduplicate/filter before slicing; continue fetching to fill | No, restores it | Approved |
| Finite/final results; Dante on 2026-10-05 | Display every remaining movie | Discover title, feed, Advanced results | Short page only when source exhausted | No | Explicitly approved |
| Existing provider limits and filtered scan recovery | Provider pages capped at 500; bounded local-filter scans remain retryable | Discover APIs and existing retry UI | Preserve cap and bounded-scan error, do not publish an unfinished scan as a completed page | No | Preserve |
| Additional requests to fill/reconstruct unique pages | May require more provider requests | Discover provider access | Cached ordered stream; direct deep pages may need preceding provider pages | Implementation cost of approved repair | Approved scope includes extra provider requests |

## Current design and ownership

| Responsibility | Authoritative owner | Callers | Preserve | Retire |
| --- | --- | --- | --- | --- |
| Grid geometry | movieCard.css; useCardGridMetrics.js; cardGrid.js | Discover and other card grids | Existing sizing and measured full-row counts | None |
| Discover page construction | app.py sequential filtered-window code | advanced_tmdb_discover; tmdb_discover | Provider parameters, title/local predicates, adult settings, identity, sorting, transient cache, limits | Slice-then-deduplicate helper and separate native seen-page cache |
| Presentation/navigation | DiscoverWorkspace.jsx; DiscoverResultGrid.jsx; Pagination.jsx | Movie and Advanced tabs | Sidebar-triggered reload, Next/Previous, history, loading/error/empty, bounded retry | None unless regression requires correction |

## Exact behavior contract

### Frontend

Reuse all existing components and geometry. Do not add padding cards or hide final results. A sidebar layout change repaginates the same cached unique native result order at the newly measured size. Verify multiple pages and return navigation, not just first-page mocked results. Existing boundedScanError prevents incomplete filtered scans from replacing the displayed page.

### Backend

Use one existing Discover accumulation owner in app.py, renamed `_tmdb_discover_window(plan, page, page_size, people_ids=None, *, first_url=None)`. Native GET supplies first_url; Advanced supplies its existing plan. Accumulate unique TMDB IDs in source order before page slicing; title/local/people predicates run before accumulation. Preserve existing filtered sorting and provider-native order.

One query-specific transient cache stores ordered matches and next provider page, independent of requested page size. Native query keys remove API key and provider page; filtered keys include the normalized query/adult setting. Protect each entry with its own lock so overlapping requests cannot append/fetch the same provider page twice. Cache expiry and eviction stay bounded. Provider-fetch failure leaves completed prior batches reusable and retries the failed batch.

Fill through the requested boundary with one-item lookahead, or prove the source exhausted. Stop at the existing provider page limit. Native pages retain provider-total metadata before exhaustion; final known totals/page counts use actual unique results. Filtered queries retain the existing 10-provider-page per-request budget and retryable marker when unfinished. Never mistake a budget or provider failure for the last page. No database migration or persisted result cache.

Explicit sorting of filtered results must finish its bounded source scan before publishing a sorted page: sorting a growing prefix otherwise repeats/omits movies. Preserve the requested sort and existing tie rules. An unfinished sorted scan returns no publishable results and the existing retryable budget marker; it can need additional retries for large result sets. Active/queued cache users pin an entry until their requests finish; cache capacity evicts only idle entries and waits when all entries are in use.

## Implementation sequence

1. Add API contract regressions for GET/native Advanced/title-filter paths, 39/40 sizes, overlapping provider pages, small/empty/final results, exact multiples, reverse page order, layout repagination, concurrent requests, failures/retry and the provider limit. Watch the motivating count tests fail.
2. Unify accumulation at the existing owner, retire native slice-then-deduplicate cache/helper and update callers. Correct the old overlap assertion and replace unrealistic sparse provider fixtures used to test logical page indexing with realistic batches; preserve their actual reachability assertions.
3. Add isolated provider fixture plus compiled desktop tests exercising the real Flask paging output, Next/Previous, sidebar collapse/expand and finite title search. Run focused suites, full Python/Node suites, relevant desktop E2E and independent review. Record results here.

## Acceptance matrix

| Scenario | Action | Expected result | Evidence |
| --- | --- | --- | --- |
| Overlapping provider batches, 81 unique movies | Pages 1,2,3 at size39 | 39,39,3; complete union, no repeats | GET and POST API; real compiled desktop |
| Same stream at size40 | Pages 1,2,3 | 40,40,1 | API and collapsed desktop |
| Three finite matches | Search title | All 3; no Next page | API and desktop |
| Empty/exact multiple | Fetch pages | Empty state or last full page; no phantom Next | API |
| Jump ahead/back/reverse order | Fetch page2 before page1; revisit | Same slices and unique identities | API |
| Sidebar layout transition | Expand/collapse/expand and navigate | Correct measured count, finite remainder preserved | Desktop |
| Filter removes summaries or local matches | Request size39/40 | Full page or genuine final remainder | API |
| Filtered budget stops early | Fetch then retry | Retryable unfinished scan, not terminal success | Existing/new API + existing UI behavior |
| Two requests for same stream | Concurrent calls | Stable slices, no lost IDs or duplicate fetching | API |
| Provider throws then recovers | Retry requested page | Same completed prefix; no skipped failed batch | API |
| Provider exceeds 500 pages | Request reachable last boundary | No provider page501; remaining reachable results shown | API |

## Verification and rollout

- Python tests: `.venv/Scripts/python.exe -m unittest ...` with CP_TEST_MODE=1 and a unique OS-temp CP_TEST_ROOT; full `unittest discover -s tests` after focused checks.
- Node: `node --test tests/*.test.mjs` (PowerShell expands files explicitly).
- Compiled desktop: `tools/run_playwright_e2e.ps1` builds to isolated CP_TEST_DIST_DIR, serves on 5117, never touches production dist or data. Run provider-fixture contract tests plus normal Movie/Discover and relationship regression suites.
- No live catalog/config changes, restart, dist install, commit or publication. Rollback is source diff reversal only after review; preserve test evidence.
- Final reporting distinguishes source/isolated compiled result from live. Compare output to each approved full-page/final-page rule.

## Execution record

- Baseline: focused Python 39/39 and Node 3/3 passed.
- Execution in the clean current checkout; no worktree, branch or commits created because Dante requested continuous scoped implementation and no such extra action.
- RED: new overlap tests returned 38/37 rather than 39/39, and 39/38 rather than 40/40. Reverse-order and concurrent requests also failed. GREEN: 45 focused Python tests passed after owner repair and realistic existing provider-fixture corrections; full Node suite 119/119 passed.
- Ruling: desktop proof uses the original investigation's recorded fullscreen viewport 3345x1084. The initial 1920px browser test expected a fourth column where existing 460px card geometry only fits three; keep 1920px as a separate measured-full-row regression, preserve source CSS. Cost if wrong: a test viewport mismatch, not altered product styling.
- Ruling: native query snapshots now use the existing filtered cache's 120-second TTL and 64-entry bound, replacing the obsolete separate native cache. This preserves a single accumulation owner and lets layout changes repaginate the same results. Cost: native snapshots can remain stable for 60 seconds longer than previously.
- Independent review found two Important gaps: explicit filtered sorting re-sorted a growing prefix (a pre-existing violation exposed by this owner), and expiry/eviction could replace active query entries. Both reproduced with failing API tests before correction. The repair pins cache users and requires complete order before publishing explicitly sorted filtered pages.
- Ruling: retain the 10-page filtered scan budget and Retry UI while collecting a globally sorted result set, rather than showing unstable pages or silently changing requested sorting. Cost: large explicitly sorted filtered searches can require additional retries; source-order/default and ordinary native browsing still fill only the requested boundary.
- Full Python run before review fixes: 1572 tests, one existing failure in test_streaming_modal_shows_loading_feedback_until_iframe_loads. That unchanged test asserts obsolete streamLoaded source text; unchanged source uses streamStatusVisible. Isolated rerun confirmed the same failure. No unrelated stream implementation or assertion was edited.
- Final focused Python: 52/52 passed. Final full Python: 1576 tests in 187.981 seconds, the same single unrelated stream-overlay failure; full suite is not green. Node: 119/119 passed.
- Final compiled desktop contract run: 7/7 passed. Normal desktop smoke, movie relationships and awards regression run: 110/110 passed. Both builds used unique temporary dist/data roots and port 5117. Initial Advanced-test selector failures were corrected against the existing rendered Sort control; one intervening run stalled at initial app bootstrap, while the focused rerun and final complete run passed without timeout changes.
- Final contract comparison: 81 unique matches render 39/39/3 expanded and 40/40/1 collapsed; all three finite title matches show in both layouts. Repeated sidebar toggles, Next/Previous, browser Back/Forward, explicit title sorting, narrower measured desktop rows, local filtering, concurrency, failed-batch retry and provider-limit cases pass. No remaining difference from the approved card-count/final-page contract was observed in isolation.
- Final live boundary: production port 5000 still belongs to PID 38404; served index matches existing production dist. No restart, frontend install, live configuration/catalog edits or Git publication. The running process has not loaded the repaired Python code. Detailed evidence: docs/verification/discover-paging/2026-10-05/verification.md.
