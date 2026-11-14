# Library database and query performance plan

**Status:** Draft, 2026-10-14, Africa/Cairo. Dante requested a separate saved plan: “write a plan for fixing this separete form the above plan saved.” This authorizes this Markdown document only. Product implementation, database changes, tests that launch services, builds, restarts, commits and publication remain unapproved.

**Goal:** Reduce the work needed to open and paginate Movie Library while preserving the exact movies, filtering, order, counts, corrections and current desktop interface.

**Architecture:** Improve the existing SQLite query owner first. Evaluate bounded reuse of unchanged results next. Introduce a persistent prepared browsing representation only if the measured remaining cost justifies a separately reviewed design. Keep existing records and canonical selection rules authoritative.

**Tech stack:** Existing Python/Flask, SQLite, React/Vite. No new database server, cache service, dependency upgrade or custom query engine is proposed.

**Specification:** This document records the database-specific proposal arising from Dante's discussion. It follows [CP's plan template](_template.md). The [broader performance plan](2026-10-14-cp-performance-plan.md) and [findings record](2026-10-14-cp-performance-findings.md) remain unchanged. This is the detailed proposal for the Library-query portion; it does not authorize or replace the other performance packages. An approval must identify which stages below it covers.

## Problem and decision

- **What happens now:** `CatalogStore.library_page` runs a matching-count query and an ordered page-selection query for each request. The effective-data query resolves selected/fallback provider records and metadata overrides. The database performs collection-wide work before returning a small page. Facets/statistics already have a generation-aware summary cache; do not describe them as universally uncached.
- **User impact:** Cached posters do not remove the wait for page data. Repeated Next/Previous can still wait for database preparation even when no images are requested.
- **What Dante wants:** Apply established database engineering techniques rather than invent a new engine. Make first-use and repeated browsing cheaper while retaining correctness and immediate relevant updates.
- **Confirmed evidence, from the earlier investigation:** A warm page revisit made zero image requests but waited roughly 471 ms for data. Separate unprofiled read-only catalog-owner calls took approximately 186–193 ms; initial uncached summary work increased the first call to about 483 ms. These are different measurements, not additive stages or promised savings. F6/F8/F10 in the findings record describe the methods and limitations.
- **Database condition:** The earlier bounded quick check passed, freelist was zero, and indexes existed. RAM-only statistics and one additional index yielded modest improvements. There is no demonstrated need for a vacuum, repair, record deletion or database replacement.
- **Unknown:** How much of the remaining route wait is projection, scheduling, concurrent activity or other work. The historical old/new UI speed difference is unresolved: relevant backend functions in the old copy were identical. Optimizing this path must not be reported as proof of that historical cause.
- **Scope:** Movie Library SQL selection/counting, canonical metadata resolution used by that selection, repository generation dependencies, and API/card verification. Both advanced and legacy Library callers are included, along with full-selection callers exposed by shared helpers.
- **Excluded:** Wallpaper caching, image variants, Home rails, hidden-page rendering, list-render CPU optimization, expansion layout, prefetch, mobile work, changing TV/IPTV stores, Follow schedules, downloads and live media operations. Those belong to other work or separate approval.

### Proposed decisions and gates

| ID | Proposed decision | Status / gate |
| --- | --- | --- |
| Q1 | Preserve SQLite, current public API and existing authoritative ownership. | Recommended; implementation pending. |
| Q2 | First deliver a measured query improvement without a persistent schema change or result cache. | Recommended Stage 1 scope. If no worthwhile safe improvement is demonstrated, report that result rather than forcing a rewrite. |
| Q3 | Add bounded result reuse only after mapping every dependency and measuring its benefit. | Stage 2 design gate. The exact retained representation and resource limits must be recorded before cache implementation. |
| Q4 | Consider a persistent prepared browsing representation only if Stages 1/2 leave a material measured cost. | Separate design and approval; not part of the initial implementation scope. |
| Q5 | Preserve exact page totals, immediate post-edit freshness and existing numbered navigation. | Required preservation constraint. No approximate counts, stale-time allowance or cursor-only navigation is proposed. |
| Q6 | Judge speed against a saved, matched baseline; record numerical acceptance thresholds before implementation. | Open measurement gate. The broader plan's provisional 500 ms target is not an approved guarantee here. |

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| Current Library filtering and pagination; advanced-search model and paging tests | Apply all criteria before pagination; retain exact totals, page clamping, valid final pages and deterministic ordering. | Advanced Library, legacy cards, full selection | Identical results with less preparation. | No intended change. | Preserve; implementation pending. |
| Canonical metadata authority; `canonical_catalog.py` and override/provider tests | Preserve selected provider, path-specific preference, fallback priority, override identity matching, title/year precedence and publication eligibility. | Query results, cards, details, shared effective-query callers | Reuse or simplify calculations without changing precedence. | No intended change. | Preserve; implementation pending. |
| Freshness; catalog/curation writers and events | A completed relevant edit/import must be reflected by subsequent reads; old in-flight work must not become a current cached answer. | Library membership, ordering, lists, badges and totals | Dependency-aware invalidation and consistent reads. | No intended weakening. | Preserve; dependency audit required. |
| API compatibility; `app.py` and advanced API tests | Existing validation, response fields, error statuses, signatures and page-size limits remain. | Library workspace and existing clients | Internal optimization only. | No intended change. | Preserve. |
| Desktop interface and backgrounds; Dante's explicit decision | Same shared cards, artwork, controls, loading/error/empty states and navigation. | Library workspace | Faster data preparation with current UI. | No. | Keep backgrounds required. |
| Domain and action boundaries; AGENTS.md and existing design | Movie, TV, IPTV, acquisition and transfer remain separate owners; existing operational schedules remain. | Shared callers and regression surfaces | No new cross-domain cache or operational behavior. | No. | Preserve. |

Current code is evidence of implementation, not automatic authority to weaken a user contract. Review existing test expectations against these rules before editing them. The current statement-count test proves bounded SQL statement count, not bounded rows examined or cheap sorting; retain useful coverage and add measurements of actual expensive operations.

If a stage requires a genuine contract change, pause that stage and issue the separate user-facing notice required by AGENTS.md, headed `## ⚠️ CONTRACT CHANGE — DANTE'S DECISION REQUIRED`, with CURRENT RULE, PROPOSED RULE, WHAT DANTE WILL SEE, AFFECTED AREAS, REASON, COST OR RISK, ALTERNATIVE and RECOMMENDATION. This document is neither that notice nor approval.

## Current design and ownership

### Baseline at document preparation

- Checkout: `C:\Users\dante\Desktop\cinema paradiso`; branch `master`; HEAD `be511f98846a67a182e5b371ad087938e9344362`; package version `3.0.0-beta.2`.
- Existing dirty state before this file: 80 tracked modified files and 387 untracked files, including the two earlier discussion documents. Preserve them. The working tree is not equivalent to HEAD.
- Port 5000 listener: PID 46012, parent 27276, command `"C:\Program Files\Python312\python.exe" app.py`; observed creation time 2026-10-14 23:35:51 local. No service was started or restarted for this plan. Command line alone does not prove its working directory or loaded-source identity.
- Read-only HTTP GET `/` matched the current checkout's `dist/index.html` bytes. Served entry: `index-B51l7aON.js`; stylesheet: `index-DFMDe_8_.css`. This confirms served HTML/bundle references, not that dirty frontend source was compiled into them.
- Current config names this checkout's `data` root and `cache` directory. Earlier investigation identified Movie SQLite at `C:\Users\dante\AppData\Local\Cinema Paradiso\Catalog\catalog-read-cb30c1d963c88463.sqlite`; existence was rechecked, but this document did not reopen it or freshly prove the process's database connection. Reconfirm effective ownership before implementation/live claims.
- The old copy's config was previously found to point at main's data. Never launch it as an independent benchmark without first establishing safe isolation.
- No product suite was run for this documentation task. Earlier test results and timings are historical evidence, not fresh checkout verification.

### Request and dependency path

`LibraryWorkspace.jsx` → POST `/api/library/search/advanced` → `normalize_advanced_search_query` → `CatalogRepository.library_page` → `CatalogStore.library_page` → effective metadata/count/ordered keys → page-only candidate projection → `_library_cards_payload` → existing shared cards.

Legacy GET `/api/library?view=cards` reaches the same owner through `_paged_library_cards`. Full selection reaches `library_selection_paths` through `app.py`'s selection path. Collection/keyword helpers also use effective metadata machinery and need regression verification if it changes.

| Responsibility | Current authoritative file/component/service | Entry point and callers | Behavior to preserve | Competing or obsolete paths |
| --- | --- | --- | --- | --- |
| Query validation/signature | `services/advanced_search.py` | Advanced Library API | Supported groups/operators/limits and stable meaning | Do not create a second query normalizer for caching. |
| Page and selection queries | `services/catalog_store.py` | `library_page`, `library_selection_paths`, effective/filter/sort helpers | Eligibility, all criteria, tie breakers, counts and selected paths | Replace redundant calculations inside this owner; avoid route-specific SQL. |
| Repository and change generations | `services/catalog_repository.py` | `library_page`, `_bump_generation`, writer transactions | Persisted changes and correct media/curation/catalog generations | Audit every relevant writer; do not assume media generation covers all inputs. |
| Effective metadata and card projection | `services/canonical_catalog.py` plus existing store SQL | Canonical provider/override selection and `project_paths` | Same canonical answer; cards defer details | Query optimization must not introduce a competing precedence rule. |
| API response and operational decorations | `app.py` | Advanced route, legacy cards, `_library_cards_payload`, maintenance-upgrade paths | Existing fields, current decorations, validation and error behavior | No second response cache containing stale complete card JSON. |
| Curation/filter inputs | `services/curation_store.py`, repository curation data, upgrade-path inputs | Watched/watchlist/movie-list filters and badges | Immediate correct membership and current display | Explicit query dependencies, not a guessed TTL. |
| Request lifecycle and rendering | `src/features/library/LibraryWorkspace.jsx` and shared cards | Next/Previous, criteria, history and events | Existing stale-response protection, selection, page sizing and backgrounds | No frontend rewrite proposed; touch only if complete-path verification reveals a required scoped integration. |

## Exact behavior contract

### Frontend, if affected

Use current desktop Library as the reference. Keep `LibraryWorkspace` and the existing shared `MovieCard` path; add no component, performance setting or alternate loading screen. Preserve grid density, geometry, typography, backgrounds, expanded details, selection, scroll/focus and Back/Forward behavior. Loading, empty and error states must describe the active request; a late older response must not replace a newer query. No frontend source changes are planned initially, but compiled UI verification is required for the backend-to-screen result.

### Backend, if affected

**Inputs and outputs:** Preserve `library_page(filters=None, *, query=None, page=1, page_size=40, upgrade_path_keys=())` and the repository delegation. Advanced POST accepts only `query`, `page`, `page_size`, with current validation and limits. Legacy normalization and defaults remain distinct where currently specified. Preserve `candidates`, `total`, `page`, `page_size`, `total_pages`, `page_start`, `page_end`, `facets`, `stats`; preserve API `items`, counts, source, query signature and current operational fields. Card projection stays limited to selected page entries; do not fetch complete details or remote providers to paginate.

**Stage 1 query work:** Resolve a winning override record once when its fields are needed, rather than independently repeating equivalent title/year searches. Evaluate resolving the chosen snapshot once per eligible file instead of repeating correlated preference searches. Preserve all four existing selected/fallback and path-specific preference branches and their tie breaking. Build count queries from the exact membership dependencies; omit display/sort-only work only where proven unnecessary. Reuse the existing criteria interpretation for count, page and full selection. Never filter an already limited page. Compare alternatives on isolated fixtures before selecting a rewrite; do not ship speculative indexes or an unmeasured SQL replacement.

**Consistent reads:** Count, ordered keys, generation and page projection must describe one coherent database snapshot. Establish transaction boundaries in the existing read owner without using the write transaction helper's `BEGIN IMMEDIATE` for ordinary browsing. Account for `_library_cards_payload` reading generation/decorations after selection; document which version those fields describe and prevent a result from being mislabeled as a newer generation. Preserve public field meaning rather than silently repurposing it. Concurrent writes may produce a coherent before-or-after result, never a mixed result; a subsequent read after a committed edit must be fresh.

**Stage 2 reuse design, before implementation:** Retain only derived selection/count data, not authoritative movie records or whole decorated response payloads. Evaluate (a) count plus bounded requested-page keys and (b) a bounded ordered identity result shared by page sizes. Measure first-request cost as well as reuse: do not build all ordered keys blindly if it makes initial use worse. Record the chosen representation, exact entry/byte bounds, eviction policy, oversize bypass and concurrency method in this document before coding Stage 2. Process restart must safely discard the cache; no persistent cache or migration is planned here.

The reuse key must include database/store identity, validated query or complete legacy-filter meaning, all relevant committed generations, and external membership inputs such as normalized upgrade-path sets. Page/page size belong in the key if the retained representation depends on them. Derive dependency coverage from actual SQL and writer paths: media, metadata overrides, canonical/provider selection, publication state, curation and lists, plus any membership-affecting input not represented by a generation. An existing advanced query signature alone is insufficient.

Generation must be read consistently with computation. Do not attach a newly read generation to older computed data. Audit all writers, including direct canonical/asset updates, before assuming existing generation bumps are sufficient. Card artwork/badges remain freshly projected; cached selection still invalidates when changed data affects criteria or order. Avoid caching failures. Concurrent identical misses must not serialize unrelated queries or hold a global lock during SQL; select and test a bounded sharing strategy if needed. A cache miss/eviction takes the same correct query path. A committed writer must not be blocked for speculative prefetch; prefetch is excluded.

**Failures and retries:** Preserve validation errors and database-error reporting. Do not hide a database error with an old cached response. No retry loop or new user-facing retry policy is proposed. If dependency or freshness guarantees cannot be established for a query, bypass reuse for it until resolved; do not introduce a time-based stale-result allowance.

**Persistence and recovery:** Stage 1 is intended to require no schema change; Stage 2 is process-local derived reuse. No production ANALYZE, VACUUM, index creation, cleanup, migration or repair is approved. A selected persistent index/read model requires an amended schema plan, migration tests, backup/restore procedure and applicable production authorization. Do not leave an old and new effective-metadata implementation competing indefinitely. Diagnostic reference comparisons belong in fixtures/tools, not a permanent production switch.

**Concrete example:** With unchanged “year 2020, title order,” Next must return the same next 39 entries and exact count with less repeated preparation. Correcting a movie's year or title must invalidate affected selection/count reuse; the next request reflects the correction. Cached posters and backgrounds remain unaffected by this query change.

## Implementation sequence

These tasks describe future work, not permission to execute it. Use inline execution after approval unless Dante requests another method. Do not create commits as an automatic task step.

### Stage 0 — reproducible baseline and correctness contract

**Files:** Proposed `tools/library_query_benchmark.py`, `tests/test_library_query_performance.py`; reuse fixtures in `tests/test_catalog_store.py` and `tests/catalog_schema_fixtures.py`. Save sanitized results under `docs/verification/library-query-performance/` only during approved execution.

- [ ] Recheck checkout, dirty files, process/config/database and served bundle. Preserve existing failures before modifying owners.
- [ ] Build isolated fixtures at 4,000 and 20,000 entries, with both provider sources, selected-source misses, multiple snapshots, overrides, publication exclusions, tied titles/dates, missing values and curation changes. No production paths as writable fixtures.
- [ ] Save expected ordered identities/counts for representative queries before rewriting. Independently assert named precedence/adverse cases; old output alone cannot authorize a contract violation.
- [ ] Record first cold call, warm distinct pages and revisits for default added, title, year/rating/quality, text, relational criteria and list/viewing-state queries. Separate count, selection, projection, summaries, whole API and screen readiness. Record EXPLAIN plans and sort-key call counts outside wall-time samples; no profiler in timing runs.
- [ ] Choose numerical Stage 1/2 acceptance thresholds from saved repeated runs, including a first-request non-regression allowance. Report median and p95 from at least 30 warmed samples per chosen case, with environment and warmup stated. Do not choose thresholds after seeing the implementation's results.

### Stage 1 — improve the existing query owner

**Files:** `services/catalog_store.py`; `services/canonical_catalog.py` only where canonical ownership requires it; `tests/test_catalog_store.py`, `tests/test_canonical_catalog.py`, `tests/test_library_query_performance.py`. Repository/API files only if required to preserve coherent version reporting.

- [ ] Add failing regressions for duplicated expensive resolution and any demonstrated count-only unnecessary work, alongside exact semantic assertions. Retain bounded statement/projection coverage; do not mistake low statement count for low query cost.
- [ ] Compare SQL alternatives implementing the Stage 1 rules above. Select the simplest measured improvement that preserves precedence. Do not introduce cached results in this stage.
- [ ] Refactor existing helpers and callers to use the selected authoritative resolution. Preserve full-selection/collection/keyword semantics exposed by shared helpers; remove the replaced duplicate calculations.
- [ ] Add and pass coherent-read tests with a committed writer overlapping a page read. Verify API generation reporting as well as store results.
- [ ] Run focused correctness and benchmark gates. If gains are insignificant or shift cost to another important query, record that result and revisit design before expanding scope.

### Stage 2 — bounded reuse, subject to the design gate

**Files:** Existing cache/read ownership in `services/catalog_store.py`, generation ownership in `services/catalog_repository.py` where audit proves necessary; `tests/test_catalog_repository.py`, `tests/test_catalog_events.py`, `tests/test_library_query_performance.py`, `tests/test_advanced_library_api.py`.

- [ ] Complete the writer/dependency inventory and fill Q3's representation, bounds, eviction and concurrency decisions. Review any writer fix as part of the exact approved scope.
- [ ] Add failing tests proving unchanged query reuse and freshness after every inventoried relevant mutation. Cover simultaneous requests, overlapping writes, process/store replacement, oversized results, eviction and errors.
- [ ] Implement reuse inside the existing read owner. Reproject requested page cards and decorations; never return a previously mutated `candidates` container after `_library_cards_payload` pops it.
- [ ] Prove revisits avoid the intended expensive work; prove fresh distinct pages also improve where the selected design claims that benefit. Check memory limits and first-use cost, not just cache-hit latency.
- [ ] Run the same correctness and performance matrix against Stage 1 and Stage 2. Keep Stage 2 only if its benefit justifies its complexity with preserved freshness.

### Stage 3 — complete-path proof and report

**Files:** `tests/e2e/library-query-performance.spec.js` proposed; existing `tests/e2e/discover-paging.spec.js` and its fixture server; API/store regression suites; saved benchmark evidence.

- [ ] Verify actual Library API responses and compiled cards together: Next/Previous, filters/sort, page-size changes, final/empty pages, rapid requests and Back/Forward. Include corrections and curation updates followed by navigation.
- [ ] Compare against the saved baseline with identical entry identities, page size, viewport/zoom and image-cache conditions. Preserve artwork and current layout. Save raw samples, commands, plans and screenshots where relevant.
- [ ] Report correctness, cold/warm/revisit latency, memory, failures and remaining route/render cost separately. Historical old/new regression diagnosis remains separate unless actually reproduced.
- [ ] If worthwhile remaining cost requires a persistent read model, stop at a written proposal: exact derived fields, writer ownership, transactional maintenance, rebuild/migration/recovery and dependency removal. Do not add it under Stage 1/2 approval.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| Unchanged warm Library, 39 entries/page | Next, Next, Previous, Previous, Next | Same ordered identities, counts and labels; chosen repeated work reduced; no wallpaper removal. | Store/API/desktop | Benchmark plus compiled Library assertions. |
| First request, summaries cold | Open Library with empty process cache | Same correct data; no unbounded preparatory work or breach of the agreed first-use budget. | Store/API | Separate cold benchmark and summary assertions. |
| Filters, sort or page size changes | Change each independently and revisit | Correct distinct selection; filter-before-pagination; no incompatible cached result. | Both query entry points | Query-key and API tests; compiled controls. |
| Final page, empty result, out-of-range page | Navigate/request pages | Exact total, existing clamping and empty-page behavior; no duplicates or omissions. | Store/API | Existing paging tests plus new reuse cases. |
| Multiple provider/path snapshots and overrides | Select/fallback, edit title/year | Current preference order/tie breaking; card and query agree. | Canonical/store | Explicit adverse fixtures and canonical assertions. |
| Movie accepted, published, removed or imported | Commit fixture change, then request | Immediate correct eligibility/count/order; no old reuse. | Repository/writers | Mutation-by-mutation invalidation tests. |
| Watched, watchlist, custom list, upgrade inputs change | Edit while a relevant query is retained | Correct filtered membership and fresh badges; unrelated query meaning preserved. | Curation/store/API | Relevant generations and external-input tests. |
| Writer commits during count/selection/projection | Overlap read and write | Coherent before-or-after response with truthful version; next post-commit read fresh. | Store/repository/API | Controlled concurrency/barrier tests. |
| Identical and unrelated concurrent misses | Request in parallel | Correct independent results, bounded sharing, no cross-query data or global SQL lock. | Cache owner | Concurrency and failure-release tests. |
| Cache eviction, limit or new store/database | Repeat after eviction/replacement | Correct recomputation, bounded memory, no identity leakage or reliance on process history. | Store | Resource and store-identity tests. |
| Validation failure or database error | Submit malformed input / inject read failure | Existing status/error semantics; failure not cached; no stale success substitute. | API/store | API validation and injected-failure tests. |
| Existing full-selection/collection/keyword callers | Run after shared helper changes | Same complete selected paths and relational semantics. | Shared query helpers | Store/parity suites. |
| Rapid Next/Previous and changed query responses | Deliver responses out of order, use Back/Forward | Latest intended screen, existing selection/focus/scroll and expansion behavior. | Library workspace | Compiled delayed-response scenarios. |
| TV/IPTV/Discover and operational schedules | Run affected isolation suites | No Movie cache leakage or altered domain behavior; Follow unchanged. | Shared regression consumers | Relevant existing suites; no live downloads/scans. |

## Verification and rollout

- **Baseline:** Documentation preparation included read-only source/status/process/served-HTML inspection. It did not run product tests or repeat the earlier database benchmarks. Record fresh existing failures before implementation.
- **Isolation:** Before imports that initialize CP, set `CP_TEST_MODE=1`, a unique `CP_TEST_ROOT` beneath the OS temporary directory and `CP_TEST_QBT_MODE=embedded` for appropriate Python API fixtures. Set `PYTHONDONTWRITEBYTECODE=1`. Use synthetic media/provider fixtures. Never run the ordinary live `CatalogStore.connect` against production as a supposedly read-only benchmark: it configures WAL and creates paths. Any separately authorized production read probe must use SQLite read-only URI/query-only handling.
- **Focused commands, after approval:** `.venv\Scripts\python.exe -B -m unittest tests.test_catalog_store tests.test_canonical_catalog tests.test_catalog_repository tests.test_catalog_events tests.test_advanced_library_api tests.test_final_card_publication tests.test_library_query_performance`. The last module is proposed and must be created during approved execution. Expect exact correctness and operation-reuse assertions, not merely elapsed-time unit assertions.
- **Benchmark command, after its tool exists:** `.venv\Scripts\python.exe -B tools\library_query_benchmark.py --sizes 4000 20000 --samples 30 --output docs\verification\library-query-performance\after.json`; define the tool to create only isolated fixtures and sanitized artifacts. Save a before result using the same tool/options and unchanged fixture identities. Do not compare RAM-copy timings with production-file timings as a promised gain.
- **Broader backend checks:** Run `tests.test_catalog_file_mutations`, `tests.test_user_curation_store`, `tests.test_sql_migration_parity`, `tests.test_catalog_parity_audit`, `tests.test_library_reconcile`, `tests.test_library_ingestion_stability` under the isolated environment, then the relevant full backend gate. Existing failures block a clean-suite claim and must be reported without weakened assertions. Any selected schema change additionally requires the actual schema/migration/backup tests for that change.
- **Frontend regression:** `node --test tests/catalogEvents.test.mjs tests/browser_ownership_cache.test.mjs tests/libraryUtils.test.mjs tests/list-catalog-filters.test.mjs`. Keep existing distinct identity/list semantics.
- **Compiled UI:** Use `tools/run_playwright_e2e.ps1` with the paging scenario (`CP_DISCOVER_PAGING_E2E=1`) for `tests/e2e/discover-paging.spec.js` and the proposed `tests/e2e/library-query-performance.spec.js`; extend the isolated fixture scenario only within approved scope. The wrapper builds into a unique temp dist and selects system qBittorrent explicitly: review its prerequisites rather than assume the Python embedded setup overrides it. Verify its fixtures exercise the real SQL owner, not mocked responses, for database performance claims. Never start a production service to satisfy a failing fixture.
- **Desktop checks:** Preserve actual desktop geometry/zoom for matched comparisons; document differences from the headless 1600×1000 test viewport. Measure request arrival, changed cards and visible-image readiness separately. Screenshot/API identity assertions substantiate appearance/content; a changed title alone does not prove all pixels are ready.
- **Live work, only if separately approved:** Reconfirm process working directory, effective catalog, configuration and served bytes. Establish a consistent SQLite backup if any live schema/data action is selected; copying only the main file while WAL is active is insufficient. Activation/restart and any production schema action need applicable authorization. Roll back on wrong membership/order/counts, stale post-edit results, errors or meaningful latency regression. A cache-only rollback discards derived memory; a future migration requires its own tested recovery.
- **Reporting:** Separate documentation, source implementation, isolated API/store proof, compiled desktop proof and installed-window/live proof. State exact failures/skips and unresolved latency. No global percentage or claim that every CP symptom is fixed.
- **Contract comparison:** Compare every accepted result with the contracts table. Correctness/freshness failures block delivery even if timings improve.

### Established techniques used as references

- [SQLite query planning](https://www.sqlite.org/queryplanner.html): use measured query plans and appropriate searching/sorting indexes.
- [Microsoft cache-aside guidance](https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside): bounded reuse needs explicit consistency/invalidation; a timer alone does not establish freshness.
- [PostgreSQL materialized views](https://www.postgresql.org/docs/16/rules-materializedviews.html): an example of persistently prepared query results, not a proposal to replace SQLite or assume SQLite supports this exact feature.
- [Plex API pagination](https://developer.plex.tv/pms/): batches and exact-total work are separate concerns. Public documentation does not establish Plex's private SQL or result-cache design.

**Approval record:** Planning document requested; no product implementation stage approved. Q3/Q6 and any genuine contract uncertainty must be resolved for the affected stage before coding. The earlier broad performance plan remains untouched.
