# Database browse performance with zero accepted regressions

**Status:** Draft for Dante's review, 2026-10-15, Africa/Cairo. Dante requested a cautious implementation plan with zero tolerance for regression or side effects affecting functionality, precision, or performance. This request authorizes this planning document only. No implementation, migration, maintenance, live database copying, restart, commit, push, or deployment is approved.

**Goal:** Reduce repeated database work when browsing owned Movies, native TV, and provider-local IPTV, while preserving exact results, metadata, availability, freshness, errors, and operational behavior.

**Architecture:** Keep SQLite and the existing domain/provider databases. Improve the existing query and projection owners in independently verified slices. The first implementation scope uses existing schemas and no new cross-request result cache; indexes, persistent summaries, migration, and production activation remain separate proposals.

**Tech stack:** Current Python/SQLite services, unittest, Node tests, Vite, and desktop Playwright. Keep installed versions; no dependency upgrade is part of this work.

**Execution:** After explicit implementation approval, follow this document task by task, using `superpowers:executing-plans` for inline execution or `superpowers:subagent-driven-development` if Dante selects delegation. No execution method has been selected. The CP template and Dante's action boundaries take precedence over generic skill instructions, including suggestions to commit.

**References:** `AGENTS.md`; `docs/plans/_template.md`; `docs/handoffs/2026-10-15-database-performance-discussion.md`; the repair update in `docs/sql-investigation/current-sql-architecture-audit.md`; `docs/sql-investigation/catalog-read-performance-stage-report.md`; `docs/tv-contracts.md`; database investigation and discussion in this chat. The earlier `2026-10-14-library-database-query-plan.md` remains an unapproved Movie-only draft. This document is the all-domain planning reference for this request; neither document authorizes execution.

## Problem and decision

### What happens now

The investigation found different costs in different owners:

| Domain | Confirmed mechanism | Evidence and limitation |
| --- | --- | --- |
| Owned Movies | `CatalogStore.library_page` runs effective-metadata queries for count and ordered keys, then projects the page. Query and projection independently interpret provider/override rules. | Read-only SQL probes: default count 80–83 ms; title page selection 108–113 ms; added page selection 110–116 ms for 39 entries. These exclude projection and API work. All 3,946 eligible live entries matched the examined canonical title/year/snapshot rules; adverse-case equivalence is unproved. |
| Native TV | `TVSearch.local_rows` reads all series/episodes/bindings, then rereads episodes per series for coverage. `library` reconstructs detail again for selected rows. | Source-confirmed repeated reads, decoding, and physical availability checks. Complete route time has not been measured under matched conditions. |
| IPTV raw Live/Series | `IPTVStore.list_items` counts and selects separately; inspected orderings require temporary sorts. `list_entries` loads membership before pagination. | Subsequent core page probes were approximately 10 ms Live / 63 ms Series for selected provider; initial reads were substantially slower. Largest current list had 41 members, so list reconstruction is a lower-priority opportunity. Favorites and full API work were not benchmarked end to end. |
| IPTV enriched Movies | `IPTVMovieStore.list_movies` builds source/grouped card rows, exact totals and ordering before returning a page. `_public_card` performs per-card genre queries. | Selected-provider full page SQL exceeded a two-second diagnostic limit for provider/recent, CP/recent and CP/title reads. Narrower probes completed faster, but the exact root-cost split and attainable improvement remain unproved. |
| Freshness | Several readers assemble count, rows, related metadata and generation using separate snapshots. IPTV `movie_generation` does not cover every visible update. | Source-confirmed concurrency/invalidation gaps. No production mixed-response incident was reproduced. No new result cache is permitted in this scope. |

The old absence of a relational Movie identity owner was repaired. Current Movie schema 11 and canonical contract 4 must not be replaced with the historical schema-v5 document assembly. Provider evidence JSON remains valid stored evidence; it is not a second canonical authority.

### What Dante wants

- Faster first browse requests, distinct page changes, and revisits, with the same database/domain boundaries.
- Zero accepted differences in membership, duplicates, ordered identities, exact totals, selected provider, overrides, card/detail values, TV coverage and progress, availability, freshness, or errors.
- No loss of precision, features, operational schedules, or failure truthfulness to achieve speed.
- Extensive meaningful automated coverage and real compiled desktop verification, before any live activation is considered.

**Zero accepted regressions is a release rule, not a claim that testing can prove the absence of every possible bug.** One unexplained mismatch, new failure, forbidden side effect, or reproducible slowdown blocks the affected slice. Do not weaken tests, omit inconvenient cases, or advertise partial verification as a full pass.

### Confirmed, suspected, and unknown

Confirmed: repeated reads, duplicated Movie interpretation, temporary ordering, compatibility/readiness failure for the second provider's schema-3 enriched store, and incomplete generation coverage for potential caching.

Unproved: production lock contention, the exact cause of every enriched-query delay, full TV time, the role of database costs in the historical UI slowdown, and an attainable overall percentage gain.

The earlier conversational suggestion of database preparation in tens of milliseconds is an **unvalidated aspiration**, not an approved acceptance threshold or promise. Derive measured budgets from matched baseline/candidate results. Do not subtract independent SQL samples from old HTTP timings.

### Scope and open decisions

The proposed first scope is source/test/tool changes for Tasks 0–5 below, against disposable data only. Task 6 is a whole-scope acceptance gate, not deployment.

Excluded: production writes; production backup/snapshot creation; new schema or index deployment; ANALYZE/VACUUM/REINDEX/checkpoint changes; schema-3 provider migration; persistent browse summaries; new process-wide query/result caching; new TTL freshness policy; provider calls, actual scans/downloads/playback; operational schedule changes; UI redesign or mobile work; unrelated cleanup; source promotion/restart/commit/push/tag/package/release.

Open gate A: Dante must approve the written scope and select execution before implementation.

Open gate B: overlapping partial overrides and conflicting selected-provider snapshots have divergent existing implementations. Stage 0 must recover the intended contract from current design, tests, and writer invariants. If evidence does not settle it, or any intended result differs from an agreed contract, STOP that Movie resolver change and request Dante's decision with the required separate contract notice. Unaffected domain tasks may proceed only within their approved scope. The old output is not an independent correctness oracle for disputed cases.

Open gate C: if source-only rewrites cannot deliver a verified improvement, report that result. Do not automatically progress to an index, persistent summary, caching, migration, or broader writer change. A concrete amendment and applicable approval are required first.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected callers | Proposed behavior | Contract change? | Decision |
| --- | --- | --- | --- | --- | --- |
| Exact browse results; current Library/search/API tests | Filter before pagination; exact totals; current page clamping, limits and tie breakers; current full-selection semantics. Domain-specific empty/out-of-range rules stay distinct. | Movie Library legacy/advanced/selection; TV Library; IPTV browse/lists | Same results with less preparation | No intended change | Implementation pending |
| Canonical Movie identity/metadata; repair contract and canonical tests | Accepted identity, selected-source/path preference, legitimate fallback, locked overrides, publication eligibility; bounded stored card/detail projection | Library, owned Discover, Lists, collection/keyword/people queries and details | One effective-rule implementation, consumed by query and projection | Uncertain for disputed adverse cases; gate B applies | No new precedence decision approved |
| Metadata and curation freshness; current writers and events | A request starting after a relevant committed edit sees it; concurrent reads may see a coherent before or after state; no stale result presented with a newer generation | Counts, cards, filters, badges, summaries, lists, ownership | Short coherent reads and truthful version reporting | No intended weakening; explain any revised version-field behavior before changing public output | Pending validation |
| Movie publication and quality | Preserve ready eligibility, deferred enrichment truth, quality fields, upgrade annotations, manual identity locks | Library and shared card/detail consumers | Same persisted rules | No | Preserve |
| Native TV coverage; `TVReadModel.coverage`, `docs/tv-contracts.md`, coverage tests | Released regular episodes, Specials, unknown dates, hydration/reconciliation completeness, missing/available/watched counts, ended-series policy | TV Library/detail/search/options/lists/Continue Watching | Batch facts; retain one coverage policy | No | Preserve |
| TV file existence and progress | Missing physical files must not remain available; multi-version/multi-episode files and independent episode progress remain correct; current resume/next behavior | TV browse, detail, files, playback | Deduplicate checks within one request only; retain revision/cursor rules | No stale availability allowance | Preserve |
| IPTV provider and classification boundaries; provider/Movies tests | No cross-provider data leakage; provider view source identities distinct from CP grouped identities; existing classification, source filters, manual matches/locks and missing-item snapshots | Raw browse/favorites/lists; enriched browse/detail/sources | Same view identities and source membership | No | Preserve; disputed adverse semantics stop affected work |
| IPTV language and search | Current normalization, substring semantics, Arabic/English display fallback, base-title ordering, genre order and metadata state | Search/filter/order/card/detail/localization | Same results; no prefix-only or FTS replacement | No | Preserve |
| Failures/readiness | Current validation/status/error semantics; migration-required stays migration-required; no cached success concealing an error | All APIs | Same truth and status | No | Preserve |
| Follow/acquisition and awards boundaries | Movie Follow checks startup and Scan; TV unsuccessful-source retry stays five hours; lower downloads stay manual release review; acquisition/awards retain independent authority | Background services and affected regression paths | No writer/schedule/acquisition/award change | No | Preserve |

Use the exact `AGENTS.md` notice `## ⚠️ CONTRACT CHANGE — DANTE'S DECISION REQUIRED` for a genuine proposed contract change, with CURRENT RULE, PROPOSED RULE, WHAT DANTE WILL SEE, AFFECTED AREAS, REASON, COST OR RISK, ALTERNATIVE and RECOMMENDATION. A row here, a passing test, or a broader implementation approval cannot substitute for that decision.

## Current design and ownership

### Baseline and configured stores

Planning checkout: `C:\Users\dante\Desktop\cinema paradiso`; `master`; HEAD `be511f98846a67a182e5b371ad087938e9344362`; package `3.0.0-beta.2`. At planning refresh: 80 tracked modifications, 389 untracked files with `--untracked-files=all`. Preserve this working tree, including unrelated TV, IPTV, acquisition, and frontend work. A fresh HEAD worktree alone is not the current source baseline.

Earlier in this chat, the app on port 5000/PID 46012 reported Desktop `data` and served HTML matching `dist/index.html`, with `index-B51l7aON.js` and `index-DFMDe_8_.css`. Recheck before any later live claim. Exact loaded Python-file revisions were not established.

| Responsibility | Owner / current entry path | State and dependencies to preserve |
| --- | --- | --- |
| Owned Movie identity/projection | `services/canonical_catalog.py` -> `project_paths`; `catalog_repository.py` writer transactions | AppData `Catalog\catalog-read-cb30c1d963c88463.sqlite`; schema 11, canonical contract 4; media/curation/asset generations distinct |
| Movie browse selection | `app.py` advanced/legacy Library -> repository `library_page` -> `catalog_store.py`; `library_selection_paths`, collections and keywords also use effective rules | 3,948 file records; 3,946 eligible entries; no provider fetch; maintained summaries and upgrade decorations are dependencies |
| Native TV | `tv_routes.py` -> `TVSearch.library/local_rows` -> repository/read model | Desktop `data\tv-catalog.sqlite`, schema 6; 42 series/3,883 episodes/1,168 files observed; acquisition profile and monitored IDs remain external dependencies |
| Raw IPTV | Provider manager -> `IPTVService` -> `IPTVStore.list_items/list_entries` | Provider-local `iptv.sqlite`; catalog generation separate from list/history writes; raw Live/Series never depend on enriched Movie readiness |
| Enriched IPTV Movies | Provider manager -> `IPTVMovieService.list_movies` -> `IPTVMovieStore.list_movies/_public_card` | Provider-local `movies.sqlite`; matched/classified sources, raw membership/history projection, localization, Movie/source generations |
| Acquisition | `app.py` acquisition composition, `acquisition_store.py`, `tv_monitoring.py` | `data\acquisition.sqlite`; relevant dependency is profiles/monitoring and possible shared storage load, not cross-database SQL joins |
| Awards | `movie_awards_routes.py`, `movie_awards_store.py` | `data\awards\awards.sqlite`; short explicit read transaction already exists; no ordinary Movie paging dependency demonstrated |

Provider A `2d44d898e1284947b8eb1a64df18af28` is selected: raw generation 40; enriched schema 4/completed source generation 40. Provider B `55219f5721c44255aeff300451a404b4`: raw generation 20; enriched schema 3/completed source generation 13. Current code rejects the latter as a ready enriched Movie store. Preserve that boundary; do not silently initialize or migrate it while testing browse changes.

Movie, TV, and both raw IPTV databases passed bounded quick checks in this chat. Enriched/auxiliary full integrity, all writer timings and runtime contention remain unverified. Few free pages and absent planner statistics are not a reason to maintain production databases.

## Exact behavior contract

### Frontend

No frontend product-source amendment. Existing desktop controls, page sizes, cards, loading/empty/error states, details, selection, layout and Back/Forward behavior stay unchanged. Compile and drive the existing interfaces solely to verify real backend-to-screen results. No mobile viewport or redesign work. Network route assertions must prove tests hit the real query owners; browser mocks alone cannot establish database correctness or speed.

### Backend inputs, outputs and persistence

Preserve these existing interfaces:

- Movies: `CatalogStore.library_page(filters=None, *, query=None, page=1, page_size=40, upgrade_path_keys=())`, repository delegation and `library_selection_paths`. Preserve existing result/API fields, query validation, canonical card/detail contracts, exact facets/stats and order. A private captured-generation field may be added between store and API only; do not leak it or redefine public `catalog_generation` without review.
- TV: `TVSearch.library(query, page=1, page_size=24, extras=None)`, `local_rows()`, legacy `TVReadModel.library`, `coverage(series, rows)`, `detail(series_id)`, repository `episodes(series_id, season=None, *, limit=None, offset=0, today=None)`. Existing public callers keep working without new required parameters.
- Raw IPTV: `list_items(kind, category_id='', query='', page=1, page_size=30, favorites_only=False, provider_key='default')` and `list_entries(provider_key, list_id, kind='', query='', page=1, page_size=60)`. Preserve snapshots of missing list members and current ordering/ties, including ties whose order requires contract recovery before a rewrite.
- Enriched IPTV: `list_movies(filters=None, *, page=1, page_size=30, favorite_list_id='')`, service readiness wrapper, `_cards_cte(view)` shared by list/detail, `_public_card`, `movie`, and `sources`. Preserve distinct provider/CP identity and all current filter combinations, fallback fields, localized display, source counts and metadata status.

No database schema/version, persistent table, journal/synchronous/checkpoint policy, production index, or authoritative record changes are included. Reads must introduce no new DML. Existing initialization and raw Favorites-list setup are characterized separately; do not pretend current first-use setup is already read-only or broaden it during this work.

### Consistency, failures and request lifetime

Use a short deferred read transaction for related SELECTs, not the writer helper's `BEGIN IMMEDIATE`. Read generation and data inside that snapshot. End the transaction before HTTP serialization or external/filesystem work where feasible. For TV, collect all needed database facts in one short snapshot, then perform current physical existence checks once per unique path for that request. A filesystem and a database cannot be made atomic merely by opening a SQLite transaction; document and preserve the existing file-race behavior rather than promising stronger atomicity.

TV monitored IDs and profiles live in acquisition, and some Movie annotations are obtained outside the page query. Audit and describe their independent snapshots. Do not claim one atomic transaction across separate databases. If those inputs affect membership/order, capture their applicable values before selection and use the same values throughout that request. No cross-database ATTACH or SQL join is permitted.

Keep database/validation errors visible. No swallowed error, retry loop, partial-success substitution, or stale response fallback. Connections close on success, exceptions and cancellation; cursors/read transactions do not escape the owner. Existing summary caches must never label old data with a later generation; concurrent older work cannot publish an apparently current cache result.

Concrete preservation example: the same year-2020 query, title order and page size 39 returns the same ordered identities and exact total before and after optimization. After an approved fixture edit changes a movie's year, the next request after commit reflects it. A writer overlapping an already-started read may produce coherent old data; it must not produce old cards with a new catalog generation.

### Design choices and alternatives

1. **Selected first scope: request-local batching, narrower SQL, one rule owner, coherent reads.** Smallest persistence footprint; no migration. It may leave unavoidable whole-match sorting, so benefits must be measured rather than assumed.
2. **Later alternative: targeted indexes/statistics.** May improve specific plans, but increases writer cost/storage and requires migration/recovery scope. Compare on disposable copies only under a later approved amendment; do not turn a read-plan observation into a live maintenance action.
3. **Later alternative: persistent browsing summaries or bounded cross-request reuse.** Can remove repeated grouping/sorting but requires complete writer invalidation, clock/file/profile dependencies and migration or memory-bound decisions. Not selected now. A cache would improve hits while retaining miss cost and could conceal stale or incorrect interpretation.

## Implementation sequence

Each task is independently rejectable. Complete its focused correctness, no-side-effect and performance gate before the next owner is changed. Do not batch all domain edits and diagnose failures afterward. New tests and diagnostic extensions are implementation actions and await approval.

### Task 0 — reproduce the exact baseline safely and establish the oracle

**Files:** Extend `tools/catalog_read_performance.py`; add `tests/test_database_browse_contracts.py`; reuse `tests/catalog_schema_fixtures.py`, `tests/iptv_movie_fixtures.py`, native-TV fixtures and existing test servers. Future evidence goes in `docs/verification/database-browse-performance/` within the isolated checkout, with no credentials or copied raw provider payloads.

- [ ] Create protected-baseline and candidate isolated source copies/worktrees from the same current reviewed working-tree content. Include relevant dirty/untracked source dependencies; exclude production config, databases, credentials and media roots. Record source hashes, exact dependencies and runtime/library versions. Do not reset, clean or promote Desktop.
- [ ] Assert test isolation before importing app or calling any constructor. Fixtures must live beneath a unique OS temporary root. Block real provider/network access and use fake acquisition/player/metadata owners. Existing audit tools import `app` or instantiate stores; execute only against the validated fixture environment.
- [ ] Extend the existing performance tool with fixture-only domain measurements: Movie, TV, IPTV raw and IPTV Movies. Add `--fixture-root <absolute OS-temp path>`, `--domain movies|tv|iptv-raw|iptv-movies|all`, `--samples <positive integer>` and `--seed <integer>`; retain `--output` and reject a fixture root inconsistent with `CP_TEST_ROOT`. Validate root/env before importing app or initializing an owner. Retain existing tool responsibility and useful timings instead of creating a competing benchmark system.
- [ ] Seed deterministic small/adverse, current-scale and growth-scale databases: Movies 4,000/20,000 files; TV 50/250 series with mixed 3,883/25,000 episodes; each raw provider 70,000 mixed items; enriched providers 45,000/90,000 sources including grouping and unmatched records. Fixtures contain no production credentials or production paths as writable media roots.
- [ ] Record baseline test failures and skip reasons before edits. Run all relevant focused suites unchanged. Reproduce a disputed failure on the protected isolated baseline before calling it pre-existing. A known baseline contract violation remains a release blocker unless separately resolved; it cannot be accepted by copying its output.
- [ ] Establish independent expected outputs from agreed contracts and deterministic fixtures, then record baseline JSON/ordered IDs. Fixed timestamps and known fixture-root substitution are allowed; do not normalize away titles, ordering, totals, generations, availability, errors or missing fields.
- [ ] Add named adverse tests for overlapping empty/nonempty overrides, conflicting TMDB identity and selected-source misses. Resolve gate B from evidence; otherwise present the separate contract notice and stop the affected resolver work.
- [ ] Build differential/property coverage: 50 deterministic seeds, each exercising 25 supported filter/sort/page cases per domain, plus the named acceptance cases below. Save seed/query and minimized failing input for every mismatch. Randomized tests supplement independent assertions; they do not replace them.

**Gate:** fixture-only access proven; baseline and oracle recorded; contracts settled for the next slice; no implementation performance claim yet.

### Task 1 — Movie read consistency and effective-rule ownership

**Files:** `services/canonical_catalog.py`, `services/catalog_store.py`, `services/catalog_repository.py`, `app.py`; extend `tests/test_canonical_catalog.py`, `test_catalog_store.py`, `test_catalog_repository.py`, `test_catalog_events.py`, `test_advanced_library_api.py`, and the shared contract suite.

**Interfaces:** Preserve the public signatures above. The existing `CanonicalCatalog` becomes the sole provider/override interpretation owner for both effective query facts and canonical projection. Any new private SQL helper lives there and must return the same settled selected-snapshot/override facts consumed by both paths; no route-owned precedence helper or second persistent representation.

- [ ] Write failing tests for mixed count/page/projection generations using a two-connection barrier: writer commits after count, after selected keys, and before API decoration. Assert coherent before-or-after membership, card values and reported media generation; a subsequent post-commit read must be fresh.
- [ ] Capture query data and applicable generations in one short read scope; pass captured information through repository/API rather than rereading a newer generation to label older cards. Characterize upgrade annotations, curation and assets independently and test their actual dependencies.
- [ ] After gate B is settled, add query/card/details equality tests for every supported provider/fallback and override case; move duplicate interpretation into the existing canonical owner. Remove the retired implementation only after all callers are accounted for. Existing audit/shadow reference logic is test tooling, not a permanent alternate live owner.
- [ ] Make default count depend only on exact eligibility when no metadata-dependent predicate exists. Filtered counts still use every required provider/relational/list input. Share eligibility with ordered selection; never omit publication/acceptance checks or filter after LIMIT.
- [ ] Reduce repeated winning-snapshot/override preparation in the query only where the independent tests prove equivalence. Keep `cp_sort_key`, tie breakers, search ranking, all sort modes, full selection, keyword/collection dependencies and page-only card projection intact.
- [ ] Rerun focused parity, all Movie schema/writer/identity/curation/download tests affected by shared ownership, and matched performance cases. Older summary computation overlapping a newer edit must not become a current cache answer.

**Gate:** zero unexplained semantic differences, no new read DML/provider calls/schema changes, bounded page projection and verified target improvement without regressions. If the rewrite improves correctness but not performance, report those results separately; do not mark the performance goal achieved.

### Task 2 — selected-provider enriched IPTV Movie selection and projection

**Files:** `services/iptv_movie_store.py`, `services/iptv_movie_service.py` only where connection/response composition requires it; extend `tests/test_iptv_movie_gates_0_5.py`, `test_iptv_movie_enrichment.py`, `test_iptv_provider_manager.py`, `test_iptv_routes.py`, and the shared contract suite.

**Interfaces:** Keep `list_movies`, `_cards_cte`, `_public_card`, `movie` and `sources` behavior. Refactor existing card preparation into selection facts required by membership/sort/grouping and bounded post-selection display preparation. Both are derived from the same source/match/classification owners; neither becomes a second authority.

- [ ] Add independent tests for source versus grouped identities, representative selection, exact source counts, manual lock/status aggregation, unclassified/non-film records, source-level playlist/quality/dubbed/subtitled filters and every sort/search/list combination. Include empty and stale out-of-range pages.
- [ ] Instrument isolated timings for source joins, grouping, exact total, window calculation, ordering, page projection and genre reads. Record rows/callbacks, SQLite VM work, selected columns, plans and temp-sort indicators separately from unprofiled timings. Identify the actual costly operation before changing it.
- [ ] Narrow pre-pagination rows to facts genuinely required for the requested filters/order and card identity. Load plot/images/provider display/error detail/localized display after limiting the ordered identities. Preserve classification/status fields needed before LIMIT; do not drop them just because a default query is faster.
- [ ] Preserve one membership/grouping rule across selection, display, detail and source callers. Batch selected-page genre reads by unique TMDB ID; route `_public_card` through the same genre ordering with optional preloaded facts instead of copying its formatting logic.
- [ ] Keep count/selected rows/genre facts/Movie generation in one short read snapshot. Characterize raw-provider dependencies separately. Assert no changed `movie_generation` assumptions or cached result introduction.
- [ ] Verify rejected schema-3 fixtures continue reporting migration-required, and raw Live/Series remain usable. Do not migrate provider B or use its incompatible schema as an optimization fixture.
- [ ] Rerun all enrichment, classification/matching, localization, worker lease/status, provider isolation, filter and list tests; benchmark both provider and CP views. A small first-page win cannot conceal a slower selective query or growth-scale grouping path.

**Gate:** same exact identities and complete responses; no cross-provider leakage; no new write/network behavior; measured improvement in the motivating enriched paths; no reproduced performance regression elsewhere.

### Task 3 — Native TV request-local facts and coverage reuse

**Files:** `services/tv_catalog_repository.py`, `services/tv_read_model.py`, `services/tv_search.py`; route composition only if needed to capture existing external inputs. Extend `tests/test_tv_catalog.py`, `test_tv_coverage_contract.py`, `test_tv_stabilization.py`, `test_tv_list_filters.py`, `test_tv_vertical_slice.py`, and the shared contract suite.

**Interfaces:** Keep existing public methods. Add an internal request-local facts context under the existing TV repository/read-model owners: series, episode/progress facts, bindings/file facts, hydration, review counts, watched actions, cursors and curation. It has no global cache, persistent table or cross-request lifetime. `coverage` stays the only episode-count/completeness policy; any internal optional preload is backward compatible.

- [ ] Add exact assertions for regular/Special/future/unknown-date episodes, incomplete hydration, reconciliation, ended versus continuing/cancelled shows, multi-episode files, multiple versions, missing files and independent progress.
- [ ] Batch required database facts into a coherent snapshot instead of rereading episodes/hydration/reviews for each show. Perform one physical existence check per unique path within that request. A new request checks current physical existence again.
- [ ] Reuse the context for coverage, filtering, sort, exact totals and selected-series detail. Load guest-star/credit/episode detail for the requested detail/page where required rather than all unrelated shows. Do not claim that all collection scanning is eliminated when progress/quality sorting still requires collection facts.
- [ ] Preserve the current filter and sort owners, title normalization, availability-based Library inclusion, assigned/review-only show inclusion, legacy adapter, profiles and monitored IDs. Capture profile/monitor inputs once where applicable; no acquisition schedule or writer change.
- [ ] Reuse the same facts path for local options/identities, Lists and Continue Watching where they already consume it; verify Discover owned overlays without contacting providers. Do not implement a separate fast path with different coverage.
- [ ] Use barriers to test overlapping progress, hydration, curation, file-binding and metadata commits. Exercise day rollover without a cache, file deletion/recreation between requests, and failed file checks. Preserve truthful partial/unknown coverage.
- [ ] Run all native-TV catalog/search/list/progress/import/acquisition/Follow safety suites and matched performance cases. Record database time separately from physical checks and decoding.

**Gate:** all counts, completeness flags, selected episodes, progress, availability and sort order match independent contracts; repeated per-series database work is removed without a new stale-data allowance; measured improvement and no new writes/provider calls.

### Task 4 — Raw IPTV projection and consistent browse reads

**Files:** `services/iptv_store.py`; service/routes only where required to preserve response/version composition. Extend `tests/test_iptv_service.py`, `test_iptv_routes.py`, `test_iptv_provider_manager.py`, and the shared contract suite.

- [ ] Pin Live channel-number ordering, Series provider-position ordering and ties, category filters, substring matching, Favorites membership and missing-list-member snapshots, page limits and exact totals for two providers with overlapping item IDs.
- [ ] Use a coherent count/page/favorite-read snapshot after existing first-use list setup. Keep first-use Favorites creation and legacy migration explicit and unchanged; ordinary populated browse must introduce no new writes.
- [ ] Retrieve only columns actually consumed by the public projection, preserving every API field; omit discarded `raw_json` from ordinary populated-page reads. Keep detail/provider payload owners intact.
- [ ] Retain whole-list membership preparation unless a measured current/growth fixture demonstrates a meaningful need to change it. If changed, preserve unavailable snapshots, mixed kinds, current query semantics and list positions with exact differential coverage.
- [ ] Measure default/category/search/favorite pages separately. If the remaining temporary sorts need new indexes for a meaningful improvement, stop this task at its verified source-only result and prepare a separately approved index amendment; do not create one in production or revise schema in this scope.
- [ ] Verify raw browse stays independent from enriched schema/readiness/errors; run sync/history/list/provider tests after the source-only change.

**Gate:** no result or field drift, consistent totals/pages, no new read writes, preserved provider ordering/search and independently measured effect. Do not call an unmeasured micro-optimization a performance fix.

### Task 5 — adverse conditions, concurrency and side-effect protection

**Files:** Existing affected tests plus `tests/test_database_browse_contracts.py`, `tools/catalog_read_performance.py`; extend `tests/discover_paging_server.py`, `tests/native_tv_server.py`, `tests/seed_iptv_e2e.py` only for deterministic data served through real owners; add `tests/e2e/database-browse-contracts.spec.js` for the combined desktop result cases. `tools/run_playwright_e2e.ps1` may be amended only to make the isolated test runtime selection explicit and fail closed on an unsafe runtime; no production launcher changes.

- [ ] Add deterministic reader/writer barriers for all edited owners, including failed writes/rollback and two concurrent readers with different criteria. Exercise 20 named scheduling/seed combinations per overlap class; retain the exact failing schedule. Do not simulate concurrency with arbitrary sleeps alone.
- [ ] Fault-inject malformed filters, missing rows, locked/busy connections, interrupted SQL, database read errors and projection failures. Assert existing status/body meaning, no partial successful response, no stale success substitute and prompt resource release. Faults affect disposable fixtures only.
- [ ] Trace SQL after fixture initialization and assert no new INSERT/UPDATE/DELETE/DDL from ordinary populated browse. Compare schema version, indexes and logical authoritative rows before/after each read-only scenario. Account separately for existing first-use setup and approved fixture writes.
- [ ] Count fake provider/player/qBittorrent calls and fail unexpected access. Attempt dangerous path overrides against test guards and assert rejection before construction or service launch. Never use `E:\Movies`, `G:\TV`, real provider credentials or port 5000 as test targets.
- [ ] Verify writer results after concurrent reads: edits/import fixture publication/progress/classification remain durable; rolled-back writes stay absent; reads have not lost/reordered data or changed writer generation/event behavior. Measure writer completion/lock duration as well as reader speed.
- [ ] Drive compiled desktop Movie, TV, raw IPTV and enriched Movie pages with real fixture owners: first page, Next/Next/Previous, query/sort change, details close/reopen, selection, Back/Forward and post-edit reload. Compare screen identities/counts/metadata to the backend and independent expected fixture result.
- [ ] Verify empty/loading/error/migration-required states, older overlapping requests, and provider switching. Do not redesign frontend behavior or hide a pre-existing contract conflict; raise it if an existing test accepts a violation.

**Gate:** no forbidden side effect, data corruption, resource leak, hidden error, stale result or complete-path contract difference. A failing writer/desktop gate blocks release even if a query benchmark passes.

### Task 6 — full acceptance and review, source-only

- [ ] Run the complete Python and Node suites against candidate and compare new/unexplained failures with the exact isolated baseline. Run all applicable desktop suites with their required fixtures; required suites cannot count as passed while skipped.
- [ ] Complete the matched performance protocol below at current and growth scales. Retain a change only when the motivating path improves without a reproduced regression in other relevant reads, cold preparation, writer latency, resource use or error recovery. Otherwise revise/revert that slice in the candidate checkout only and rerun affected gates.
- [ ] Review the diff against every contract row and affected caller. Use an independent reviewer only if Dante selects that execution method; otherwise perform an explicit self-review and report that review limitation.
- [ ] Verify protected Desktop source/config/runtime/served-dist manifests were not changed by the implementation. Production workers may legitimately change their own data; do not demand byte-identical live SQLite/WAL files or overwrite them to satisfy a protection check. Use fixture evidence and access guards to establish no test write path targeted production.
- [ ] Produce a result report with exact tests/pass/fail/skip counts, fixture seeds, runtime/build identity, benchmark distributions, SQL plans/work counts, before/after semantics, writer/connection evidence, every gate, known limitations and remaining approval boundaries. Explicitly state source-only, isolated tested, and not live.

**Gate:** Dante receives a concrete reviewable implementation and evidence. No promotion, commit, restart or deployment follows automatically.

## Acceptance matrix

Every row is required wherever the edited owner exposes that behavior. Prefer independent named assertions plus full baseline/candidate equality; do not validate only submitted inputs or SQL statement counts.

| Scenario and starting state | Action | Exact expected result | Owner / automated evidence |
| --- | --- | --- | --- |
| Movie default and advanced/legacy criteria | Read first/middle/last/out-of-range pages and full selection | Exact eligible identities, order, totals/pages, facets/stats and field types; correct owner-specific clamping | Store/repository/API independent and differential assertions |
| Provider/path preference, absent source, TMDB conflict | Filter/sort, project cards and request details | Same settled selected snapshot, fallback flags and metadata across queries/cards/details; uncertain cases blocked by gate B | Canonical/store/API adversarial fixtures |
| Partial overlapping metadata/poster overrides | Older nonempty, newer empty fields; matching aliases/paths | Exact settled field precedence and lock behavior; tests cannot settle an unresolved contract by accepting whichever output is faster | Named override tests and contract record |
| Movie publication, identity, quality, people/keywords/collections | Pending/ready/removed records; relational filters and selection | No premature publication or lost match; stable metadata/deferred fields and quality annotations; correct related callers | Catalog/identity/advanced API suites |
| Tied/empty/Unicode titles, years/ratings absent | Every existing sort and search ranking | Current locale/key semantics, null ordering and tie breakers; no new nondeterministic ordering | Fixed expected ordered IDs plus seeded cases |
| Movie writer overlaps page | Commit at count/key/projection/decoration boundaries; repeat after commit | One truthful snapshot; next newly started read reflects commit; rollback invisible | Barrier tests including API generation |
| Curation/assets/upgrade inputs change | Change watched/watchlist/custom list, poster asset, quality/profile inputs | Exact membership/order/badges and separate domain versions; unchanged queries remain correct | Writer/event/curation plus complete API assertions |
| TV released/Special/future/unknown/incomplete | Browse and compare detail, options, list and search | Exact coverage counts, unknown percentages, hydration/reconciliation flags and watch policy | TV coverage and search/list tests |
| TV files/progress/cursors | Multiple versions, multi-episode binding, delete/recreate synthetic file, resume/restart/mark watched | Immediate next-request physical availability; independent episode progress; same current/default season and action | TV repository/read-model/progress tests |
| TV clock/profile/monitor input | Date rollover, profile change, monitor state commit, title/progress/quality sorting | Fresh current released membership and matching results; no cross-request availability cache; five-hour retry unchanged | Frozen-clock fixtures, fake acquisition dependency, Follow suites |
| IPTV raw Live/Series/category/search | Mixed providers, channel numbers/ties, categories, substring query | Exact current order, total and page; all public fields preserved; no provider leakage | Raw store/routes/provider tests |
| IPTV raw Favorites/custom/missing list entries | Add/remove/reorder fixture membership; deleted catalog item remains saved | Same available/unavailable snapshot, kind/query filtering and position semantics | Lists/history/provider tests |
| IPTV provider and CP views | Same TMDB IDs across multiple sources/providers and classifications | Same grouped/source identities, representative, source count, metadata state and membership filter meaning | Enriched store/service independent assertions |
| IPTV localized/search/match lifecycle | Arabic/English overlays, missing localization, manual/auto/unmatched/error states, classification edits | Same displayed metadata, search aliases, base sort behavior, genre order and manual locks; next request fresh | Enrichment/localization/classification tests |
| Schema-3 enriched provider | Raw reads and enriched browse/detail requests | Raw domain usable; exact migration-required/unavailable meaning; schema remains 3; no migration/start worker | Provider/readiness/schema fingerprint tests |
| Empty/invalid/busy/interrupted/failed read | Inject fault with cold and populated fixture state | Existing error/validation truth, no stale success or success with missing fields; connection/transaction released | Fault injection and API/desktop checks |
| Repeated readers and overlapping writer | Two criteria streams, cancellation and rollback schedules | No cross-query or cross-provider result leak, no lost writer data, no reproduced writer-latency/lock regression under matched loads; truthful versions | Deterministic barriers, SQL trace and writer timing |
| Domain isolation and auxiliary dependencies | Shared IDs/labels across Movies, TV, two providers, acquisition and awards | Independent owners/files/versions; no cross-domain joins; unchanged Follow/download/awards contracts | Isolation assertions plus broad regression suites |
| Compiled desktop motivating path | Next/Next/Previous, sort/query, details, selection, Back/Forward, post-edit refresh | Backend exact results appear correctly using existing controls; no layout/source redesign | Real-owner desktop Playwright and response assertions |
| Cold/warm/current/growth scale | Matched baseline/candidate protocol | Real measured improvement on target paths; no reproduced regression elsewhere; correct outputs in every sample | Unprofiled samples plus separate SQL/work/resource diagnostics |

## Verification and rollout

### Isolation and baseline commands

Commands below are for a future approved isolated implementation checkout, **not Desktop production**. They must not run during this planning request. Use a new temporary root for independent suites or benchmark cohorts and seed before importing production constructors. Review test/tool imports and fixture prerequisites first.

```powershell
$taskTestRoot = Join-Path ([IO.Path]::GetTempPath()) ('cp-database-browse-' + [guid]::NewGuid().ToString('N'))
$resolvedTaskRoot = [IO.Path]::GetFullPath($taskTestRoot)
$resolvedTempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
if (-not $resolvedTaskRoot.StartsWith($resolvedTempRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe test root' }
$env:CP_TEST_MODE = '1'
$env:CP_TEST_ROOT = $resolvedTaskRoot
$env:CP_TEST_QBT_MODE = 'embedded'
$env:CP_TEST_DIST_DIR = Join-Path $resolvedTaskRoot 'dist'
$env:PYTHONDONTWRITEBYTECODE = '1'
```

No provider connections, production roots, production ports or runtime workers. Fake transports must reject unexpected external calls including paths beyond `urllib`'s existing test guard. Capture baseline failures before changing assertions or implementation.

### Focused Python commands

Use the isolated checkout's existing `.venv\Scripts\python.exe`. New shared test module is created in Task 0. Each command must exit 0; record actual case counts and skips. Individual schema/acquisition/Follow suites supplement these groups where touched; whole-suite acceptance covers all discovered tests.

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_database_browse_contracts -v
& .\.venv\Scripts\python.exe -m unittest tests.test_canonical_catalog tests.test_catalog_store tests.test_catalog_repository tests.test_catalog_events tests.test_advanced_library_api tests.test_curation_routes -v
& .\.venv\Scripts\python.exe -m unittest tests.test_tv_catalog tests.test_tv_coverage_contract tests.test_tv_stabilization tests.test_tv_list_filters tests.test_tv_vertical_slice tests.test_native_tv_safety_baseline -v
& .\.venv\Scripts\python.exe -m unittest tests.test_iptv_service tests.test_iptv_routes tests.test_iptv_provider_manager tests.test_iptv_movie_gates_0_5 tests.test_iptv_movie_enrichment -v
```

Existing `tools/catalog_parity_audit.py`, `tools/library_sql_shadow_compare.py` and `tools/catalog_read_performance.py` must run against the validated isolated fixture configuration, never their default production-root assumptions. Extend their isolation guards if needed under Task 0. `--project-root` is not alone a proof of isolation. Preserve raw-decoder guards and independent expected fixtures; zero provider calls and zero semantic mismatches are required.

### Whole suites and compiled desktop

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
$nodeTestFiles = @(Get-ChildItem -LiteralPath tests -Filter '*.test.mjs' -File | ForEach-Object { $_.FullName })
& node --test @nodeTestFiles
& npm.cmd run build -- --outDir $env:CP_TEST_DIST_DIR
```

Run Node tests only after the isolated dependency/runtime inventory confirms `node` resolves to the intended version. The scripts above have no cleanup/deletion step.

The existing `tools/run_playwright_e2e.ps1` builds isolated dist but explicitly sets `CP_TEST_QBT_MODE=system` and port 5117. Do not assume the preceding embedded setting overrides it. Review system-mode prerequisites before use and prove all acquisition transports are fake/isolated; absence of the required test runtime blocks the suite, never authorizes using production qBittorrent. If that proof is unavailable, amend only the test harness under Task 5: add an explicit `-TestQbtMode embedded|system` parameter, default to `embedded`, assign runtime data and transfer ports beneath/to the isolated test context, and refuse external system-mode connectivity without fixture proof. Preserve system-mode scenarios only where their fixture semantics require them. Validate process descendants, ports and roots before launch. This testing amendment does not authorize any real scan, provider call, torrent submission or download.

Required desktop gates: `app-smoke`, `discover-paging`, the new `database-browse-contracts`, `cross-page-selection`, `movie-scroll-return`, `continue-watching`, `native-tv`, `tv-parity`, `tv-expanded-parity`, `tv-stabilization`, `tv-download-contracts`, `tv-normal-import`, `tv-follow-season-packs`, `movie-follow`, `following-refresh`, `movie-awards`, and applicable IPTV cases in existing smoke/stream tests. Run each with its actual seeded fixture prerequisites: `CP_DISCOVER_PAGING_E2E=1` for paging, `CP_TV_E2E=1` for the native-TV server and any additional flags required by that spec. Capture a manifest of required cases/flags and executed cases; discovery with skipped tests is not acceptance.

Example approved-future paging command after the explicit-mode harness amendment and isolation validation:

```powershell
$env:CP_DISCOVER_PAGING_E2E = '1'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/run_playwright_e2e.ps1 -TestQbtMode embedded tests/e2e/discover-paging.spec.js
Remove-Item Env:CP_DISCOVER_PAGING_E2E
```

The environment-variable removal is local test-process configuration, not production configuration. Launch only recorded isolated process descendants; use hidden helper windows. Test fake scans/imports/downloads/playback, never real ones. All browser gates use desktop 1600 x 1000 unless a specific existing desktop test requires another desktop size.

### Performance proof

- Same working-tree baseline, runtime versions, fixture bytes/identities, query, page size, clock, fake dependencies, storage location and workload. No comparison of RAM-copy candidate timings with production-file baseline.
- Required query classes: Movie default added/title, selective year/genre/person/keyword/list/viewing/quality queries and full selection; TV default/title/progress/quality/filter/options; IPTV raw Live/Series/category/substring/favorites; enriched provider/CP recent/title/year/rating/selective/list/quality/localized-search and out-of-range pages. Include first/middle/last pages at current and growth scales.
- Separate new-process/connection first requests from steady-state samples. Do not call an OS-cache-warm new process a cold-disk test. Record any storage cache limits and active load.
- For each targeted steady-state case, collect 50 unprofiled samples per baseline/candidate, in five alternating blocks of ten, with fresh isolated cohorts for mutations. Record all raw samples, median/p95/range and paired variation. Wall-time runs have no tracing/profiler overhead; plans/SQL counts/VM work/decoding/stat calls are separate probes.
- Functional equality is asserted in every benchmark sample. Count rows examined, sorting/grouping work, callbacks, filesystem checks, peak memory/temp growth and writer latency where relevant; low SQL statement counts alone do not demonstrate bounded work.
- Candidate improvement must exceed observed run-to-run noise and recur across the interleaved blocks. A slower relevant median or p95 is a stop-and-investigate signal; do not hide a tail regression behind average improvement. Reproduce a suspected slowdown in matched baseline/candidate conditions. If evidence remains ambiguous, report performance unverified and keep that gate closed; do not claim zero slowdown.
- Concurrency cases include idle and controlled fake-writer load. Read transactions must finish/close; overlapping writers must commit durable results. No long production soak or benchmark is included.
- There is no universal millisecond or percentage guarantee. Report improvement per case and remaining cost. If an optimization cannot improve its target without functional or performance regression, do not ship it to satisfy an aspirational target.

### Recovery and later live work

Initial recovery is source-only: discard or revert only this slice in the isolated candidate, preserve fixture evidence, and restore the previous isolated source version. No production rollback is needed because production has not been changed. Do not archive/delete evidence or worktrees automatically.

Any later live action requires a separate reviewed scope identifying exact checkout/branch, dirty work preservation, data roots/stores, process owner, bundle, backup destination, downtime, smoke checks, rollout order and rollback trigger. Database backup must be WAL-aware through SQLite's online backup mechanism, never a main-file-only copy. Rehearse restore against a disposable destination, verify integrity/relationships/versions/logical counts and relevant exact results, and verify no missing retained assets if included. Production workers may keep writing; define how their new writes are preserved. Do not restore an old database merely to roll back a source-only query change.

Provider B migration, new indexes, persistent summaries or writer changes need their own concrete migration/backup/recovery plan and approval. No approved schema 11/TV 6/IPTV Movie 4 store may be silently downgraded or rebuilt from an outdated JSON export.

### Reporting and final contract comparison

Report changed files/owners, reason, exact verification counts and commands, all skipped/failed cases, benchmark distributions and methodological limits, no-side-effect evidence, what remains unverified, and whether anything is live. Compare the observed result with each approved contract, including generation, precision, failure behavior, operational schedules and post-edit freshness. Do not use a passing suite to erase a known contract difference.

**Approval record:** Planning requested on 2026-10-15. This draft has not been approved for implementation. No product code, test, tool, schema, index, configuration, data, service, or deployment action has been performed by this planning turn.
