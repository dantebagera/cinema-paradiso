# Catalog Read Performance and Local Artwork Stage Report

## Stage 0 - Baseline and recovery path

Status: Passed on 2026-07-20 before production read-path changes.

### Existing behavior measured

- Active branch and commit: `master` at `2d6e4c693a8c95f93f5d0eadd112d8b94351b461`; the initial worktree was clean.
- Schema version 6, canonical contract version 2, catalog generation 306, curation generation 16,558.
- Catalog size: 117,063,680 bytes.
- Catalog rows: 3,708 physical files, 3,707 canonical movies, 7,199 provider snapshots, 31,206 people, 43,833 credits, 16,714 movie-genre links, 1,108 movie-collection links, and 13 overrides.
- SQLite integrity: `ok`; foreign-key violations: 0.
- Ten representative owned detail requests: p95 2,423.293 ms in-process and 2,372.211 ms over the running local server.
- Owned detail SQL statements: 29,659 to 29,670 per request.
- Uncached Library cards response: 6,875.211 ms, 59,321 SQL statements, 3,708 returned cards, and 6,540,419 HTTP response bytes.
- Warm cached Library response: 127.394 ms, 3 SQL statements, and still 3,708 returned cards.
- Fresh backend import plus SQL catalog readiness: 363.7 to 390.3 ms across five processes. An already-running health request completed in 54.706 ms end to end.
- Provider requests during owned details and Library probes: 0.
- Existing local storage: 13 custom poster files / 1,082,222 bytes; legacy TMDB cache 2 files / 1,703,047 bytes; app metadata 51 files / 80,764,513 bytes.
- qBittorrent journal: 159 jobs (145 imported, 12 cancelled, 1 abandoned, 1 downloading). Embedded qBittorrent remained running during the online SQLite snapshot.

The machine showed two Python process entries, but only one listened on port 5000; this is consistent with a parent/child or stale non-listening process and remains an operational observation for Stage 5 rather than a parity failure.

The machine-readable measurements are in `catalog-read-performance-baseline-2026-07-20.json` and can be regenerated with `tools/catalog_read_performance.py`.

### Recovery validation

- Created an online SQLite/user-data backup at `data/catalog-performance-baseline/backups/cp-catalog-migration-20260720T191243Z.zip`.
- Backup manifest: 1,157 files and 335,911,961 bytes.
- Restored all 1,157 files into an isolated rehearsal directory.
- The restored SQLite catalog opened successfully and its rollback shadow reconstruction passed.
- Semantic counts after restore: 3,708 files, 4,749 TMDB snapshots, 3,572 Plex snapshots, 486 manual matches, 10 lists / 260 list items, 1 collection override, 13 followed releases, and 159 qBittorrent jobs.
- All 16 generated JSON rollback documents were parseable and matched the SQL authority.
- The immutable cutover archive checksum and literal legacy comparison remained valid.

### Code ownership changed

- Added `tools/catalog_read_performance.py` as non-production measurement tooling.
- Added `tests/fixtures/catalog_performance_expected.json` as the independent, checked-in expected-output manifest for the deterministic parity fixture.
- Extended the existing SQL migration fixture with six ordered cast members, two directors, and a deliberately wrong provider candidate awaiting review. No production catalog owner changed in Stage 0.

### Tests and parity checks

- Python: 677 passed before the fixture extension.
- Frontend Node: 54 passed.
- Playwright desktop: 19 passed.
- Production Vite build: passed.
- Active relational parity audit: 3,708 records checked, 0 violations, 0 provider calls.
- Literal JSON shadow comparison: passed with 0 blocking mismatches.
- JSON rollback export verification: 16 documents, 0 mismatches.

### Gate

Passed. Backup restore, rollback export, deterministic fixture coverage, timings, query counts, response sizes, and provider-call counts are recorded. Stage 1 may replace the production owned-details lookup.

### Next stage

Stage 1 replaces the full-library `library_candidates()` scan and route-level `snapshot()` with a bounded direct SQL lookup by normalized path or canonical movie key, while preserving the exact detail response and proving query-count independence from total library size.

## Stage 1 - Bounded owned-details read

Status: Passed on 2026-07-20.

### Existing behavior measured

- Before: owned detail p95 2,423.293 ms and 29,659 to 29,670 SQL statements per request.
- After: owned detail p95 6.649 ms and exactly 10 SQL statements per request.
- Provider calls remained 0.
- Adding 3,700 unrelated fixture rows did not change the query count.

### Code ownership changed

- `CatalogStore.owned_movie_candidate()` now owns the bounded low-level lookup by normalized path key or canonical movie key.
- `CatalogRepository.owned_movie()` owns path normalization and exposes the domain read.
- `/api/library/details` now calls the repository method and no longer calls `library_candidates()` or `AppMetadataStore.snapshot()`.
- The existing canonical relational projection remains the sole metadata-precedence owner.

### Tests and parity checks

- Added a bounded-query-count test with 3,700 unrelated rows.
- Added a route guard that fails if owned details call the full-library reader, document snapshot, TMDB, or Plex.
- Verified exact plot, six ordered cast members, two ordered directors, collection/custom-poster behavior, and provider-free details through the fixture.
- Stage catalog/parity subset: 60 passed.
- Live catalog parity audit: 3,708 checked, 0 violations, 0 provider calls.
- Stage 0 backup checksum/semantic verification passed again.

### Gate

Passed. The p95 target of 100 ms and warm target of 50 ms were both exceeded comfortably, query count is bounded, and detail parity remains green.

### Next stage

Stage 2 names and enforces canonical card and canonical details contracts so Library, Discover-owned, and List surfaces cannot drift or erase valid summary fields when deferred details arrive.

## Stage 2 - Explicit card and details projections

Status: Passed on 2026-07-20.

### Existing behavior measured

- Collapsed cards already deferred people in practice, but the omission was implicit and the backend exposed a loosely filtered dictionary.
- Shared Discover/List rendering merged card metadata after detail metadata, allowing an empty or stale card field to overwrite a valid detail field.

### Code ownership changed

- `services/canonical_catalog.py` now defines named `canonical_movie_card` and `canonical_movie_details` contracts, typed defaults, stable movie keys, and an explicit deferred-field list.
- `app.py` projects Library, Discover-owned, and List card metadata through the same canonical card projection. The compatibility `include_items` response is explicitly a details projection.
- `src/api/movieDetails.js` owns summary/detail merging and preserves valid summary values when a deferred detail is empty.
- `SharedMovieCards.jsx` consumes that merge owner instead of reimplementing spread precedence.

### Tests and parity checks

- Added backend contract-field, default, deferred-field, and overlapping-value equality coverage.
- Added frontend merge coverage for plots, summaries, posters, genres, ratings, and deferred cast.
- Existing API parity now asserts matching card contracts for Library, Discover ownership, and Lists plus a details contract for expansion.
- Production Vite build passed.
- Playwright Stage 2 gate: 3 passed, covering all stateful workspace navigation, three-surface canonical cards, immediate SQL expansion, close/reopen stability, and curation-generation refresh with the card still expanded.
- Provider detail requests for the owned parity movie: 0.

### Gate

Passed. One identity renders matching summary metadata on Library, Discover-owned, and List cards; expansion adds stored SQL details without erasing the summary or calling TMDB/Plex.

### Next stage

Stage 3 moves Library movie paging, filters, sorts, facets, and filtered selection identity sets into SQL under shadow comparison with the existing JavaScript semantics.

## Stage 3 - SQL-owned Library query semantics

Status: Passed on 2026-07-20.

### Existing behavior measured

- The old Library endpoint materialized all 3,708 cards and left paging, filtering, sorting, facets, and selection identity construction to the browser.
- Fifteen live-catalog shadow cases captured the existing title, year, genre, quality, path, owned-state, and locale-aware ordering semantics before the browser implementation was replaced.

### Code ownership changed

- `CatalogStore.library_page()` now owns bounded filtering, sorting, paging, facets, and filtered identity selection in SQL.
- `CatalogRepository.library_page()` exposes that query as the authoritative Library read model.
- SQLite receives the same `cp_sort_key` collation key used by the former JavaScript ordering.
- `LibraryWorkspace.jsx` requests server pages and consumes server facets and selection identities; it no longer computes a second full-library implementation.

### Tests and parity checks

- Added SQL query-contract tests for every filter and sort mode, empty results, pagination boundaries, facets, and selection identity sets.
- `tools/library_sql_shadow_compare.py` passed all 15 live cases with no item, order, facet, count, or selection mismatch.
- Playwright asserts a filtered page result, a page transition, filtered selection behavior, and preservation of Library state after navigation.
- Provider calls remained 0.

### Gate

Passed. Exact legacy semantics were preserved by shadow comparison before the browser-side implementation was retired.

### Next stage

Stage 4 bounds the remaining projection work and proves query-count independence from catalog size.

## Stage 4 - Bounded relational projections

Status: Passed on 2026-07-20.

### Existing behavior measured

- Before the work, an uncached Library response took 6,875.211 ms, executed 59,321 SQL statements, serialized 3,708 cards, and returned 6,540,419 bytes.
- Owned details executed 29,659 to 29,670 SQL statements because relational facts were repeatedly decoded while scanning the full library.

### Code ownership changed

- `canonical_catalog.py` owns raw-free card and detail projection contracts.
- `CatalogRepository` batches canonical rows, overrides, genres, collections, credits, people, and local asset relationships for only the requested page or movie.
- Production routes no longer decode provider JSON to build Library cards or owned details.

### Tests and parity checks

- Query-count tests prove constant statement counts after thousands of unrelated rows are added.
- Raw-decoder route guards fail if Library, details, File View, Home statistics, collections, or people projections fall back to provider-document decoding.
- Final live measurements: owned details use 11 statements; cold Library uses 21 statements for 40 cards; warm Library uses 13 statements for 40 cards.
- `EXPLAIN QUERY PLAN` evidence is recorded in `catalog-read-performance-final-2026-07-20.json`; the accepted plans use persisted snapshot/override indexes and bounded correlated lookups.

### Gate

Passed. Work now scales with the requested page/detail projection rather than the 3,708-row catalog.

### Next stage

Stage 5 removes ordinary startup scans from readiness and proves SQL-only startup behavior.

## Stage 5 - Startup and background-job boundaries

Status: Passed on 2026-07-20.

### Existing behavior measured

- Baseline backend import plus catalog readiness took 363.7 to 390.3 ms.
- Startup ownership was implicit: callers could not distinguish SQL readiness from an explicit reconciliation request.

### Code ownership changed

- Operational catalog metadata records readiness and reconciliation state.
- Ordinary startup opens the SQL authority without scanning the movie roots or contacting providers; explicit/background reconciliation remains a separately scheduled operation.
- Background work consumes generation/state checkpoints instead of forcing a route-triggered full scan.

### Tests and parity checks

- A fresh-process live probe reached catalog readiness in 258.838 ms and served its first bounded Library page in 476.793 ms.
- Startup guards prove no TMDB/Plex request and no ordinary root scan.
- Pending download identity handoffs replay once; completed handoffs remain idempotent through the existing qBittorrent reconciliation suite.

### Gate

Passed. The app is usable from persisted SQL before optional reconciliation begins.

### Next stage

Stage 6 adds SQL-related local artwork with a separate generation and a bounded resumable backfill.

## Stage 6 - Local artwork assets

Status: Passed on 2026-07-20.

### Existing behavior measured

- The existing app had 13 custom posters totaling 1,082,222 bytes, while selected provider posters and portraits were still remote URLs.
- Owned metadata and credits were already provider-free after Stages 1-4, but their images were not yet locally durable.

### Code ownership changed

- Schema version 7 adds `media_assets`, `movie_assets`, `person_assets`, curated artwork references, and `asset_generation`; SQL stores metadata and relationships, never image bytes.
- `services/media_assets.py` owns validation, decoding, content checksums, atomic writes, deduplication, bounded scheduling, retry/backoff, retention, and custom-poster protection.
- Files are stored under `%LOCALAPPDATA%\Cinema Paradiso\Metadata` and served by an immutable checksum route.
- Biography remains live and optional; no biography column or persisted biography text was introduced.
- Artwork work increments `asset_generation` only. `catalog_generation` remained 306 throughout the backfill.

### Tests and parity checks

- Full live backfill produced 19,173 ready logical assets and 19,169 unique checksum files: 422,048,227 logical bytes versus 417,436,287 physical bytes.
- Relationships covered 19,321 references; 148 were relationship deduplications and 4 were physical checksum-file deduplications. All 13 custom posters remained protected.
- The initial pass took 1,195.509 seconds; saved-list acceptance took 20.695 seconds.
- A second pass downloaded nothing and changed neither `catalog_generation` nor `asset_generation`.
- Tests cover invalid payloads, resumability, retry/backoff, bounded work, atomic writes, deduplication, retention, custom-poster non-eviction, and generation separation.
- Playwright loads an actual local immutable poster, expands an owned card, and asserts stored plot/cast/directors with no provider detail request.

### Gate

Passed. Selected owned artwork is durable, deduplicated, resumable, non-blocking, and independent of catalog invalidation.

### Next stage

Stage 7 retires remaining production compatibility reads and consolidates statistics, file, people, collection, and maintenance projections on SQL.

## Stage 7 - Authority consolidation

Status: Passed on 2026-07-20.

### Existing behavior measured

- The low-level `library_candidates()` API still allowed accidental full-library/provider-document reads outside explicit audits.
- Home and Maintenance could derive duplicate/upgrade facts through different projection paths; a missing file fingerprint was exposed by the live equality audit.

### Code ownership changed

- Removed the production `library_candidates()` compatibility method. The raw decoder is now named `audit_library_candidates()` and is confined to audit/export tooling.
- File View, People, collections, Home statistics, and Maintenance use normalized `library_projection`, `file_inventory`, and SQL audit owners.
- Restored the omitted fingerprint in the authoritative file projection instead of patching either statistics route.

### Tests and parity checks

- Live Home and Maintenance results match exactly: 0 duplicate groups, 0 extra files, 0 reclaimable bytes, and 732 upgrade candidates.
- Route guards assert that production reads cannot enter the audit decoder.
- Identity correction/conflict/audit, downloads/import/reconciliation, rename/delete/persistence, curation, and navigation suites remained green.

### Gate

Passed. SQL is the sole live catalog authority; JSON/provider decoding remains only in named audits and rollback exports.

### Next stage

Stage 8 performs the complete performance, parity, browser, artwork, and rollback acceptance audit.

## Stage 8 - Full acceptance and rollback rehearsal

Status: Passed on 2026-07-21.

### Existing behavior measured

- Owned detail p95 improved from 2,423.293 ms to 7.376 ms; statement count fell from about 29,659 to 11.
- Cold Library improved from 6,875.211 ms / 59,321 statements / 3,708 cards to 521.165 ms / 21 statements / 40 cards.
- Warm Library is 145.753 ms / 13 statements / 40 cards. The old 127.394 ms warm response used 3 statements but still serialized all 3,708 cards, so it was not a bounded equivalent.
- Provider calls remained 0 before and after owned catalog reads.

### Code ownership changed

- Backup format version 3 now includes every SQL-registered ready checksum asset, excludes temporary/unregistered files, and prevents recursive inclusion of performance-rehearsal directories.
- No route-specific metadata hotfix or second live authority was retained.

### Tests and parity checks

- Live relational audit: 3,708 checked files, 3,707 accepted canonical movies, 31,206 people, 43,833 ordered credits, 0 violations, and 0 provider calls.
- Literal JSON rollback shadow: exact 3,708 file-record parity and no legacy-only, SQL-only, canonical, document, or provider-call violation.
- SQL Library shadow: all 15 filter/sort/page/facet/selection cases passed.
- Final archive: `data/catalog-performance-final/backups/cp-catalog-migration-20260720T211804Z.zip`, with 20,336 manifest files and 773,645,396 logical bytes.
- The archive contains all 19,169 unique registered asset files / 417,436,287 bytes. Isolated restore reported SQLite integrity `ok`, 0 foreign-key violations, 0 missing checksums, 0 unexpected checksum files, schema 7, catalog generation 306, and asset generation 19,110.
- Final clean suites: 697 Python tests, 55 frontend Node tests, 21 desktop Playwright tests, and the production Vite build all passed.
- The Browser plugin could not initialize its own browser-control runtime because its kernel-assets path was unavailable. This occurred before navigation and is not an application failure; the required result-based browser audit passed through Playwright against the real desktop app and artwork store.

### Gate

Passed. Performance budgets, workflow parity, provider-free owned reads, artwork durability, and a complete isolated rollback restore all passed with no blocking mismatch.

### Next stage

None. Future work is operational monitoring of cache size, failed artwork retries, and query-plan drift; it is not another migration authority.
