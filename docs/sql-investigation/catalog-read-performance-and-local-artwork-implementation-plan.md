# Catalog Read Performance and Local Artwork Implementation Plan

Status: Approved for planning. Application implementation has not started.

## 1. Purpose

This plan addresses the performance and reliability problems that remain after the SQL migration architecture revision:

- Library startup and first-page loading still rebuild too much of the catalog.
- Opening one owned movie can reconstruct the entire Library before returning its details.
- Owned movie credits are stored in SQL, but portrait images still depend on TMDB at display time.
- Some browser projections still behave like the former JSON-era application instead of querying SQL for the exact data required.
- Existing tests prove many isolated behaviors, but they do not yet enforce the complete user-visible parity contract.

The objective is to make SQL-backed reads direct, bounded, and predictable while preserving Cinema Paradiso's established behavior. This work must not introduce a second domain authority, redesign the UI, or silently change filtering, identity, ownership, list, maintenance, or expanded-card semantics.

## 2. Decisions Already Made

### 2.1 Canonical metadata

The current relational schema remains the canonical source for owned movie metadata. It already separates the important data instead of storing one opaque JSON movie record:

- `canonical_movies` owns canonical movie identity.
- `media_files` owns physical files and file-level media facts.
- `provider_movie_snapshots` owns provider metadata such as plot, poster URL, ratings, runtime, and tagline.
- `people` owns person identity and provider profile URL.
- `movie_credits` owns movie-to-person roles, characters, and ordering.
- Genre, collection, identity, override, curation, list, duplicate, and job data remain in their existing relational owners.

Large image bytes must not be stored inside SQLite. SQLite stores asset identity and lifecycle metadata; the files live in the user's metadata directory.

### 2.2 People metadata

The owned movie detail contract must read directors and cast from SQL without contacting TMDB.

Person portrait files will be cached locally. The existing SQL profile URL remains provenance and a remote fallback while an image is pending.

Biography remains an optional live TMDB detail. It will not be persisted in SQL or as a text file in this stage. A biography can change, is not required to render an expanded movie card, and must not delay that card.

### 2.3 Artwork policy

The application metadata root will default to:

```text
%LOCALAPPDATA%\Cinema Paradiso\Metadata
```

Planned subdirectories:

```text
Metadata\posters
Metadata\people
Metadata\collections
Metadata\custom
Metadata\transformed
Metadata\temporary
```

Retention classes:

| Content | Retention |
| --- | --- |
| Selected artwork for owned movies | Persistent while owned |
| Portraits referenced by owned movie credits | Persistent while referenced |
| Custom posters | Persistent; never automatically evicted |
| Artwork for movies saved in user lists | Persistent while referenced |
| Discover-only artwork | Temporary; age and size limited |
| Biography text | Not stored; fetched only when explicitly opened |

The location and soft size limit must be configurable. Plex's approximately 13.6 GiB metadata footprint for Dante's 3,700-movie library is a sizing reference, not a storage target. Cinema Paradiso stores fewer asset classes, so an initial planning estimate of roughly 3 to 7.5 GiB is reasonable for a library of that size. Measurement after backfill will replace this estimate.

### 2.4 Historical behavior baseline

The correct pre-SQL baseline is Cinema Paradiso 2.7 behavior, not a Plex-derived fallback:

- Expanded cards could show six TMDB cast members plus directors.
- TMDB details were served from `tmdb_library_cache.json` when already populated.
- Portraits were TMDB images then as well.

The present regression is caused by inefficient current read scope and incomplete local image ownership. It is not explained by an old design that intentionally showed fewer Plex credits.

## 3. Confirmed Current Bottleneck

The current owned details request performs work proportional to the entire library:

1. `/api/library/details` calls `store.catalog.store.library_candidates()`.
2. `library_candidates()` reads and decodes all candidate rows, including JSON compatibility columns.
3. It invokes canonical projection work for paths across the library.
4. The route scans those results to find the one requested path.
5. It also calls a full `store.snapshot()`.

For a library of about 3,708 movies, measured details requests have taken approximately 1.1 to 1.6 seconds. One expanded card should require one bounded movie lookup, not a reconstruction of 3,708 candidates.

The Library page has the same shape at a larger level: it loads the complete card collection and lets the browser filter, sort, and paginate it. SQL is present, but the application still queries it as though it must first recreate the former in-memory JSON library.

## 4. Non-Negotiable Behavior Contract

All implementation stages are governed by the SQL migration parity matrix. The following workflows must remain behaviorally identical from the user's perspective:

| Workflow | Required invariant |
| --- | --- |
| Home statistics vs. Maintenance | Counts describe the same catalog generation and ownership rules. |
| Library, Discover owned cards, and List cards | The same movie identity exposes the same title, year, plot, poster choice, genres, rating, ownership, and expanded details. |
| Summary vs. expanded details | Summary fields do not disappear or change when expanded; details only add intentionally deferred data. |
| Metadata and manual overrides | Manual identity, title, plot, poster, and other supported overrides always win according to the existing precedence contract. |
| People | Owned cast/directors come from SQL; their relationship navigation returns the correct owned work. |
| Collections | Collection membership and navigation remain consistent across card and details views. |
| Identity workflows | Matching, correction, conflict review, and audit retain their existing decisions and audit trail. |
| Duplicates and upgrades | Groups, recommendations, candidate counts, and filters use the same physical-file and quality rules. |
| Download lifecycle | Search, ownership checks, submission, completion, import, and reconciliation preserve current qBittorrent behavior. User-cancelled incomplete downloads are not errors. |
| File View | Delete, rename, selection, and metadata persistence continue to operate on the intended physical files. |
| Page state | Navigating away and back preserves each mounted workspace's filters, query, page, expansion, and selection where currently promised. |
| Startup/background work | Reconciliation and jobs update the correct generation without forcing unrelated catalog rebuilding. |

No stage passes solely because the schema migrated, the server started, unit tests passed, or a page appeared quickly.

## 5. Target Read Contracts

### 5.1 Canonical movie card

The card projection is the compact read model shared by Library, owned Discover results, and Lists. It includes only fields required to render and operate the collapsed card:

- Canonical identity and provider IDs.
- Title, year, and display sort fields.
- Selected plot/summary according to precedence.
- Selected poster reference.
- Genres and rating.
- Ownership and playable file summary.
- Locale, quality, size, and upgrade state where applicable.
- List, watched, watchlist, duplicate, and selection state required by that surface.
- Catalog generation and stable movie key.

### 5.2 Canonical movie details

The detail projection extends the card contract with intentionally deferred SQL data:

- Ordered directors and cast with person IDs, names, roles, characters, and local/remote portrait references.
- Runtime, tagline, trailer, collection details, and other expanded metadata.
- Full playable-file information needed by card actions.
- Correction and provenance data needed by metadata controls.

The detail projection must not call TMDB for an owned movie. Clicking a separate person-biography action may call `/api/tmdb/person`, but the biography request must not control whether the movie details or portrait can render.

### 5.3 One owner per responsibility

There will be one internal canonical resolver for precedence and domain meaning. Card and detail projections may request different field groups, but they must not duplicate metadata-selection logic.

The production request path must stop using `library_candidates()` as a general-purpose read API. If that method remains temporarily for migration comparison or backfill, it must be named and isolated as an audit/compatibility path, with a removal condition documented in code.

## 6. Stage-by-Stage Implementation

Each stage ends with a mandatory gate. A failed gate stops progression to the next stage.

### Stage 0: Freeze the baseline and recovery path

#### Work

1. Record the current schema version, row counts, relationship counts, database size, and catalog generations.
2. Create a consistent SQLite backup and validate that it can be opened and queried.
3. Generate and validate the existing JSON rollback export.
4. Inventory custom posters, qBittorrent job state, application settings, and current metadata/cache directories.
5. Capture cold and warm timings for:
   - Server startup and health readiness.
   - First Library response and first rendered page.
   - Ten representative owned detail requests.
   - Library search, genre filter, upgrade filter, actor navigation, and list loading.
6. Record SQL query counts and outbound provider calls for those requests.
7. Build or confirm a deterministic fixture library containing:
   - A duplicate group.
   - A manually corrected identity.
   - A deliberately wrong provider match awaiting review.
   - An owned Discover result.
   - A movie with TMDB plot and Plex summary.
   - A newly imported download.
   - An unmatched file.
   - A low-quality upgrade candidate.
   - A collection movie.
   - A movie with a custom poster.

#### Gate

- Database backup restore succeeds in a temporary location.
- JSON rollback export is parseable and contains the expected record counts.
- Fixture identities and expected user-visible outputs are checked into automated test data.
- Baseline timings, query counts, and network calls are written to a reproducible report.

### Stage 1: Replace the full-library owned-details read

#### Work

1. Add a repository method that resolves exactly one owned movie by normalized path key or canonical movie key.
2. Query the required media file, canonical identity, selected provider snapshot, manual overrides, genres, collection, and curation data for that movie only.
3. Batch-load its ordered credits and people in one bounded query set.
4. Project the result through the existing canonical precedence owner.
5. Change `/api/library/details` to call this direct method.
6. Remove `library_candidates()` and `store.snapshot()` from the production details route.
7. Preserve the route's external response contract until frontend projection tests prove any intentional contract adjustment.

#### Tests

- Exact detail parity for every fixture movie against the captured legacy/previous expected result.
- Manual plot and poster overrides win.
- TMDB plot remains available when Plex summary is also present.
- Six ordered cast members and directors are returned when stored.
- Collection and custom poster are present.
- Duplicate physical files resolve to the intended canonical movie without losing file actions.
- Query count is bounded and does not increase when total library size increases.
- No TMDB or Plex HTTP request occurs for owned details.

#### Gate

- Owned details p95 is at most 100 ms on the local acceptance environment after server readiness, with a warm target below 50 ms.
- The synthetic 3,700-movie fixture does not materially change one-movie query count or latency.
- All parity fields match, including null/empty semantics and ordering.

### Stage 2: Make card and detail projections explicit

#### Work

1. Define named canonical card and canonical details contracts in the backend.
2. Centralize metadata precedence, identity resolution, ownership, and selected artwork in one resolver.
3. Make deferred fields explicit instead of accidentally absent.
4. Add schema/contract tests for every field consumed by shared movie cards.
5. Update Library, Discover-owned, and List APIs to use the same card projection for the same canonical identity.
6. Ensure frontend cards merge detail responses without replacing valid summary fields with missing values.
7. Keep browser request sequencing guards so a stale response cannot populate a newly reused card.

#### Gate

- One canonical identity renders matching summary and details across Library, Discover owned, and Lists.
- A card opened immediately after first render contains SQL details without provider hydration.
- Closing, reopening, filtering, and navigating do not change metadata content for the same generation.

### Stage 3: Move Library paging, sorting, and filtering into SQL

#### Work

1. Introduce a paged Library card query with explicit parameters for the existing UI behaviors:
   - Page and page size.
   - Text query.
   - Genre.
   - Quality and upgrade state.
   - Person and credit role.
   - Collection.
   - User list.
   - Watched/watchlist state.
   - Duplicate state where exposed.
   - Existing sort modes.
2. Return total matching count, page information, active generation, and required facets without returning all cards.
3. Implement filters through relational joins and indexed predicates, preserving the exact current filter semantics.
4. Keep File View on its own appropriate projection rather than forcing card records to carry every file field.
5. Make bulk actions operate on an explicit server-side filter specification or a stable selected-ID set. `Select all filtered` must not require loading every card into the browser.
6. Preserve mounted-workspace state when moving between Library, Discover, Lists, Maintenance, and other pages.
7. Correctly clear Maintenance deep-link filters when the user selects All or Reset, while retaining legitimate subsequent Library state.

#### Tests

- Golden tests compare every existing browser-side filter/sort result with the SQL result over the same fixture.
- Tests cover combined filters, empty results, punctuation, alternate titles, people roles, duplicate copies, custom posters, and multiple lists.
- Page boundaries do not duplicate or skip movies when titles tie.
- Generation changes invalidate the affected query cache.
- Navigation away and back preserves page state without refreshing unrelated workspaces.

#### Gate

- The Library API returns only the requested page and bounded facet data.
- First-page warm API p95 is at most 500 ms on the local acceptance environment; cold target after server readiness is at most 1 second.
- Filter/sort result identity sets exactly match the established behavior.

### Stage 4: Remove remaining catalog N+1 reads

#### Work

1. Instrument query counts per major endpoint during tests.
2. For paged cards, fetch the page's base movies/files once and batch-load genres, overrides, curation, list state, and other required relationships by movie key.
3. Load credits only for details or people-specific result sets, not for every collapsed card.
4. Use `EXPLAIN QUERY PLAN` for representative filters and sorts.
5. Add only indexes justified by measured query plans. Avoid redundant indexes and indexes on low-selectivity columns that do not improve the target query.
6. Remove JSON decoding from steady-state canonical reads. Legacy JSON columns may remain temporarily for rollback/audit but cannot be required to render production cards or details.

#### Gate

- Page query count is bounded independently of total catalog size.
- No per-card SQL loop remains in the main Library page path.
- Production card and details tests pass with legacy JSON compatibility fields removed from a copied fixture database.

### Stage 5: Make startup incremental

#### Work

1. Instrument startup phases separately:
   - Database open and schema validation.
   - Migration check.
   - Catalog generation check.
   - Startup reconciliation decision.
   - Plex and qBittorrent connectivity checks.
   - Background queue startup.
   - First Library query.
2. Skip catalog reconstruction when schema version, contract version, source generation, and reconciliation state are current.
3. Ensure no-op reconciliation and no-op background jobs do not bump catalog generation.
4. Do not perform a full filesystem scan on ordinary startup unless a source change, explicit rescan, or failed integrity condition requires it.
5. Start maintenance and artwork backfill work after the API is ready; these jobs must not block Library use.
6. Coalesce generation changes so one logical import/reconciliation operation does not invalidate caches repeatedly.

#### Gate

- Warm restart performs no full catalog rebuild or full media scan.
- Health readiness and the first Library page meet recorded targets on Dante's library.
- Starting with TMDB, Plex, or qBittorrent temporarily unavailable does not prevent owned SQL metadata from rendering.

### Stage 6: Add the local artwork subsystem

This is the only planned schema extension. It is an asset registry, not a replacement metadata model.

#### Proposed schema

`media_assets` stores one downloaded or generated file:

```text
asset_key
asset_type
provider
source_url
local_path
checksum
mime_type
byte_size
width
height
status
attempt_count
last_error
downloaded_at
last_verified_at
last_accessed_at
retention_class
created_at
updated_at
```

Relationship tables keep ownership explicit:

- `movie_assets(movie_key, asset_type, asset_key, selected)` with foreign keys to canonical movies and assets.
- `person_assets(person_key, asset_type, asset_key, selected)` with foreign keys to people and assets.
- `curated_asset_refs(curated_identity_key, asset_type, asset_key)` for saved unowned/list records that do not yet have a canonical movie row.

Do not use a polymorphic `owner_type/owner_id` relationship for canonical movies and people when enforceable foreign keys are practical.

#### Work

1. Add a forward-only migration and a migration audit proving no canonical metadata rows changed.
2. Implement one asset service that owns URL normalization, deduplication, download, validation, atomic file placement, and lookup.
3. Download to a temporary file, verify MIME type and image decoding, calculate checksum, then atomically move to the final path.
4. Deduplicate repeated person portraits and provider URLs. A person appearing in 100 movies must not create 100 files.
5. Cache one suitable portrait size that serves both expanded cards and biography dialogs; let the browser resize for smaller placements.
6. Cache a bounded selected poster size rather than every provider size or original image.
7. Serve local assets through a controlled application endpoint with immutable/checksum-based URLs and appropriate browser cache headers.
8. Retain the remote URL as provenance and temporary fallback while an asset is queued or failed.
9. Run owned artwork backfill as a bounded-concurrency, resumable background job with retry and backoff.
10. Expose backfill status and failures through the existing operational/maintenance surface without redesigning the page.
11. Enforce retention:
    - Never evict custom assets automatically.
    - Retain owned and saved-list assets while referenced.
    - Evict temporary Discover assets by age and soft size limit.
    - Delete unreferenced managed files only after a reconciliation grace period.
12. Keep biography fetch live. The biography dialog reuses the local person portrait but does not write biography text.

#### Generation design

Artwork must use a separate `asset_generation` from the canonical `catalog_generation`.

Downloading thousands of portraits must not invalidate every Library query or make Home/Maintenance counts appear to change. Canonical catalog generation changes when catalog meaning changes; asset generation changes when a selected asset becomes locally available or its binding changes. Checksum-based asset URLs allow normal browser caching without global card reloads.

#### Tests

- Offline owned Library/details render plot, credits, and already-cached portraits.
- The first uncached portrait does not block detail text or other people cards.
- Duplicate people share one physical asset.
- Custom posters survive cleanup and always retain precedence.
- Interrupted downloads resume safely without corrupt final files.
- Invalid content types and partial images are rejected.
- Discover temporary cleanup cannot remove owned or saved-list assets.
- Asset backfill does not change canonical catalog generation.
- Removing one movie does not remove a shared person portrait still referenced by another owned movie.

#### Gate

- After backfill, opening representative owned expanded cards causes zero provider metadata requests and zero provider image requests.
- Disconnecting the network still renders owned card posters and owned people portraits already present locally.
- Measured disk usage, deduplication ratio, failures, and backfill duration are recorded before choosing the default soft limit.

### Stage 7: Retire JSON-era production paths

#### Work

1. Identify every production call to full-library compatibility readers, legacy cache mergers, and raw JSON decoding.
2. Replace remaining production consumers with canonical repository queries.
3. Keep `tmdb_library_cache.json` only where explicitly required for temporary rollback comparison during the shadow period.
4. Keep unowned Discover caching as a separate external-catalog concern; it must not become an authority for owned movies.
5. Remove obsolete compatibility code after shadow comparison passes and rollback exports are validated.
6. Document any temporary adapter that cannot yet be removed with an owner, reason, and removal gate.

#### Gate

- Owned pages remain fully functional when the legacy TMDB Library cache is unavailable.
- Static search finds no production card/details dependency on legacy JSON movie payloads.
- There is one authoritative implementation for metadata precedence and one for asset storage.

### Stage 8: Final behavior-parity acceptance

#### Automated suites

1. Run the complete Python test suite.
2. Run the complete frontend unit/component suite.
3. Produce a clean production frontend build.
4. Run browser end-to-end tests against the fixture and a copy of the real catalog.
5. Run cold/warm performance and SQL query-count benchmarks.
6. Run provider-disconnected and asset-cache failure tests.
7. Run backup, restore, rollback-export, and post-restore parity tests.

#### Browser workflow audit

The acceptance script must visit every major workspace and exercise its meaningful controls, including:

- Home counts and navigation.
- Library search, all filters, sorting, paging, expansion, playback, trailer, correction, lists, people, collections, bulk actions, File View, rename, and delete confirmation boundaries.
- Discover movie and people search, owned cards, source actions, follow/list actions, people images, and owned-work navigation.
- Lists load, create/update/delete boundaries, cards, expansion, and owned/unowned consistency.
- Maintenance statistics, duplicates, identities, unmatched files, upgrade candidates, deep links, reset, and return navigation.
- Downloads search, ownership, submission, cancellation interpretation, completed import, removal, and reconciliation.
- Settings and background job status affected by this work.
- Per-page state retention while moving repeatedly between workspaces.

The test must assert resulting state and API behavior, not merely click buttons without checking outcomes.

#### Final authority gate

SQL may be declared the sole live authority for the migrated domains only when:

- There are zero blocking shadow mismatches.
- The required workflow matrix is green.
- Owned details require no provider metadata call.
- Local owned artwork passes offline tests.
- Performance targets are met without changing visible behavior.
- Backup and JSON rollback exports are verified.
- No two permanent live authorities remain.

## 7. Planned Code Ownership

The implementation should improve the existing owner wherever one already exists. Route handlers and React workspaces must not acquire duplicate domain logic.

| Area | Existing owner | Planned responsibility |
| --- | --- | --- |
| SQL schema, low-level reads, transactions | `services/catalog_store.py` | Add bounded single-movie and paged-library SQL operations; add the asset-registry migration; retain full-library decoding only for explicitly named audit work. |
| Repository generations, authority, rollback exports | `services/catalog_repository.py` | Expose domain-level read methods, catalog/curation/asset generations, backup/export coordination, and cache invalidation. |
| Canonical metadata precedence and relational projection | `services/canonical_catalog.py` | Own one canonical resolver and explicit card/details projections. It must not own HTTP behavior or filesystem image downloads. |
| Library HTTP contracts | `app.py` initially, then existing route-service boundaries where practical | Keep handlers thin: validate input, call repository/service, return projection plus generation. Do not scan candidates or merge snapshots in a route. |
| Local image download, validation, files, retention | New `services/media_assets.py` | Be the single authority for managed artwork bytes and asset bindings. Reuse existing custom-poster behavior through this service rather than adding a parallel custom path. |
| Shared details API selection | `src/api/movieDetails.js` | Select owned canonical details vs. unowned external details and enforce generation-aware request/cache keys. No metadata precedence logic. |
| Shared card/details presentation | `src/components/SharedMovieCards.jsx` and its existing shared detail components | Render the canonical contracts consistently; use local asset URLs when supplied; keep biography as an explicit action. |
| Library query and state | `src/features/library/LibraryWorkspace.jsx` | Send paging/filter/sort state to the backend and preserve workspace state. It must not reconstruct the full Library from a paged response. |
| Existing Library filter semantics | `src/utils/libraryUtils.js` | Serve as the golden reference during shadow comparison. Remove obsolete client-side full-catalog filtering only after SQL parity passes. |
| Discover and Lists consumers | `src/features/discover/DiscoverWorkspace.jsx`, `src/features/movie-lists/MovieListsWorkspace.jsx` | Consume the same owned card/details contracts without local merge exceptions. |
| Migration and canonical tests | `tests/test_canonical_catalog.py`, `tests/test_catalog_store.py`, `tests/test_catalog_repository.py`, `tests/test_sql_migration_parity.py` | Cover schema, relational rows, projections, rollback, direct reads, and generation behavior. |
| User-visible metadata parity tests | `tests/test_catalog_parity_audit.py`, `tests/test_catalog_json_shadow_compare.py`, `tests/test_library_expanded_details_ui.py`, `tests/test_unified_movie_card_ui.py` | Expand fixture parity across Library, Discover owned, Lists, people, overrides, and deferred details. |
| Performance tests | `tests/test_metadata_performance.py` | Assert bounded query count, no provider calls, cold/warm reports, and independence from total library size. |
| Browser acceptance | `tests/e2e/` | Exercise complete workflows and assert resulting UI and API state, including navigation persistence and offline owned metadata. |

Before creating any additional module, implementation must confirm that none of these existing owners can cleanly hold the responsibility. Any temporary compatibility adapter requires a removal test and removal stage.

## 8. Performance Budgets

Absolute timings are acceptance targets on the current local machine. Automated CI should primarily enforce bounded query counts and relative regressions because wall-clock timing is noisy.

| Operation | Target | Structural assertion |
| --- | --- | --- |
| Owned movie details | p95 <= 100 ms; warm goal <= 50 ms | Bounded SQL queries; independent of total library size; zero provider calls |
| Warm Library first page API | p95 <= 500 ms | Returns one page, not all movies |
| Cold Library first page after readiness | <= 1 second | No catalog rebuild in request path |
| Expanded-card text after click | <= 150 ms locally | Portrait availability cannot block text |
| Cached local image response | <= 100 ms locally | Checksum URL and browser-cache headers |
| Warm restart | Baseline measured in Stage 0, then materially faster than rebuild path | No full scan/reprojection when generations are current |

Any missed target requires a query/timing trace and an explicit decision. The target must not be relaxed simply to make the gate pass.

## 9. Cache and Generation Rules

| Event | Required invalidation |
| --- | --- |
| Identity correction or accepted provider match | Increment catalog generation; invalidate affected canonical card/details and aggregate projections |
| Plot/title/genre/rating/collection/manual metadata change | Increment catalog generation; invalidate affected movie and dependent counts/facets |
| File import/delete/rename/quality change | Increment catalog generation and relevant file/ownership/maintenance projections |
| List membership or watch state change | Increment the appropriate curation generation; invalidate affected list/card state without rebuilding canonical metadata |
| Portrait/poster downloaded locally | Increment asset generation or publish immutable asset binding; do not increment catalog generation |
| Temporary Discover image eviction | Invalidate only its asset binding/cache entry |
| No-op reconciliation/background pass | No generation change |

Every cached API response and browser cache entry must carry or be keyed by the generation of the domain it represents. A catalog generation mismatch is a completion condition for invalidation, not an invitation to rebuild unrelated domains.

## 10. Observability Required Before Optimization

Add structured timings and counters for:

- Endpoint total duration.
- SQL query count and SQL duration.
- Rows decoded/projected.
- Catalog and asset generation used.
- Cache hit/miss and invalidation reason.
- Provider request count and duration.
- Startup phase duration.
- Artwork queue depth, successes, retries, failures, and bytes.

Logs must make it possible to answer: "Why did this card take two seconds?" without watching the UI and guessing.

## 11. Primary Risks and Controls

### Filter semantic drift

Moving filters from JavaScript to SQL can subtly change case handling, title normalization, role matching, empty values, and tie ordering. Golden identity-set tests must compare old and new behavior before switching the endpoint.

### Bulk action scope

Once the browser no longer owns the full filtered library, `Select all filtered` cannot mean "select only the loaded page." Bulk APIs must receive and validate the complete filter specification or a stable server-issued selection token.

### Asset invalidation storms

Backfilling thousands of images must not bump catalog generation thousands of times. Asset state is a separate generation domain and updates should be batched where practical.

### Shared asset deletion

People and posters may be referenced by multiple movies or lists. Cleanup must be reference-aware and use a grace period. Files are removed only after database state proves they are unreferenced.

### Hidden provider dependency

An owned detail response that silently falls back to TMDB can look correct during testing while remaining broken offline. Provider-call assertions and disconnected tests are mandatory.

### Timing-only confidence

A fast endpoint can still return incomplete metadata. Every performance test must also assert the canonical result and provider-call count.

## 12. Rollback Strategy

Each stage must be independently reversible before the next stage begins:

1. Preserve the pre-stage SQLite backup and schema version.
2. Preserve a validated JSON rollback export until final authority acceptance.
3. Make asset migration additive; old remote URLs remain readable while local assets are populated.
4. Do not delete legacy compatibility fields in the same stage that introduces their replacement.
5. Remove compatibility code only after shadow parity and restore tests pass.
6. Maintain an asset manifest so managed files can be distinguished from user-owned custom files.
7. Never roll back by deleting the user's custom poster directory.

Rollback is an emergency recovery mechanism, not permission to run two permanent live metadata authorities.

## 13. Deliverables

- Baseline and final performance reports.
- Fixture library and expected parity snapshots.
- Direct canonical one-movie repository query.
- Explicit card and details contracts.
- SQL-backed paged/filterable Library endpoint.
- Query-count and provider-call test instrumentation.
- Incremental startup decision path.
- Local artwork registry, storage service, backfill, retention, and diagnostics.
- Updated SQL architecture and workflow parity documentation.
- Browser acceptance suite covering every affected workspace.
- Verified database backup and JSON rollback export.
- Removal report for obsolete JSON-era production paths.

## 14. Definition of Done

This project is complete only when all of the following are true:

- Opening one owned movie reads one bounded canonical record graph.
- Library paging and filtering are executed by SQL without loading the entire catalog into the browser.
- Owned plots, credits, genres, ratings, collections, overrides, and selected artwork are available without unrelated provider calls.
- Owned people portraits and selected posters render locally after backfill.
- Biography remains an explicit live optional action and does not affect movie-card readiness.
- Library, Discover owned cards, Lists, Home, Maintenance, Downloads, and File View pass the workflow parity matrix.
- Page state survives navigation as designed.
- Catalog and asset invalidation are separated and generation-correct.
- Startup skips unnecessary reconciliation and reprojection.
- Performance budgets, offline tests, backup restore, and rollback-export verification pass.
- Obsolete production compatibility paths have been removed, leaving one obvious authority for each responsibility.
