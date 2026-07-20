# SQL Migration Parity Matrix

This is the release checklist for the JSON-to-SQL catalog cutover. SQL is the active catalog authority. JSON is retained only as a rollback export and read-only shadow-comparison input; it is not a second live authority.

## Rules for Every Row

- The SQL row must contain the required state.
- The canonical movie model must expose it.
- Compact projections may intentionally defer detail fields, but expanded details must read them from SQL without a provider request.
- A catalog mutation must advance `catalog_generation` and invalidate server and browser projections that depend on it.
- A list, collection, or followed-release mutation must advance `curation_generation` and invalidate every browser projection that depends on curation state.
- The user must see the same movie identity across relevant pages.

## Workflow Evidence

| Workflow | Before SQL source | Current SQL source and involved state | User-visible invariant and completion proof |
| --- | --- | --- | --- |
| Home statistics versus Maintenance audit | JSON-derived library snapshot and audit state | `media_files` and catalog generation; server library, stats, and maintenance caches | Counts refresh together after a mutation. Proven by `test_home_stats_and_maintenance_share_the_catalog_generation_and_refresh_after_mutation`. |
| Library cards versus Discover owned cards versus Movie List cards | Library JSON, Discover ownership lookup, user-list JSON | `media_files`, canonical model, `/api/library`, `/api/library/check`, `/api/library/details`; browser ownership and source-aware detail caches | The same accepted TMDB/IMDb/title/year identity and plot are shown everywhere. Expanded owned cards on Library, Discover, Movie Lists, Home, and AI Control fetch deferred people, collection, and trailer data from SQL. Only unowned cards may call TMDB. Proven by `test_api_projections_include_canonical_card_metadata_without_provider_calls`, the five-surface Playwright parity test, and the ownership-cache browser test. |
| Summary metadata versus expanded details | TMDB and Plex JSON snapshots | `tmdb_json`, `plex_json`, canonical model, card/list/people projections | TMDB is the default enrichment source when its persisted snapshot exists; Plex remains an intentional fallback source. Compact cards preserve canonical plot and identity while people may be deferred; expanded details resolve those deferred fields from SQL. Proven by catalog audit, SQL fixture tests with provider calls blocked, and the shared `fetchCanonicalMovieDetails` contract. |
| Posters, plots, cast, genres, ratings, collections, and manual overrides | TMDB/Plex JSON plus override JSON | SQL snapshots and durable override records, projected through canonical metadata | The same accepted movie preserves metadata and custom poster without mutating provider snapshots. Proven by SQL fixture, metadata override, poster override, and collection tests. |
| Identity matching, correction, conflict review, and audit | Match JSON and provider-specific records | Accepted identity columns, manual matches, audit state, decision fingerprints | Manual corrections stay locked; conflicts remain reviewable; exact identities can be verified read-only. Proven by identity audit, repair, verification, and Plex manual-match suites. |
| Duplicate groups and upgrade candidates | JSON-derived audit grouping | SQL library candidates and maintenance audit projection | Duplicate and quality groups use the same accepted identity and change after file facts mutate. Proven by SQL fixture and duplicate identity tests. |
| Source search, ownership checks, download submission, cancellation, completed import, and library reconciliation | Source result state, JSON job records, filename follow-up | Stable TMDB/IMDb/Plex identity in job metadata, SQL ownership lookup, job journal, reconcile state | Owned movies do not download; title-only sources are rejected; a user-removed unfinished torrent becomes a normal terminal cancellation without moving files or touching SQL; a completed import hands its original identity to the exact imported file before reconciliation. Recoverable completed payloads always take precedence over cancellation. Proven by SQL fixture plus qBittorrent API/service tests. |
| File View, deletion, rename, and metadata persistence | File JSON plus filesystem scan state | SQL path records and canonical item projections; catalog generation and library cache | Rename/delete changes File View, Library, ownership, stats, and maintenance without a full rescan. Proven by catalog file mutation and SQL fixture tests. |
| Startup reconciliation and background job updates | Metadata checkpoints and qBittorrent job JSON | SQL persisted facts, reconciliation state, qBittorrent journal, catalog generation | Cold start reads SQL without provider calls; pending identity handoffs replay once; completed handoffs do not replay. Proven by SQL fixture and qBittorrent service tests. |
| Navigation and page-local state | Mounted React workspace state and browser scroll | One mounted instance per visited workspace; active workspace visibility and per-workspace scroll positions | Moving between Library, Discover, Movie Lists, Maintenance, AI Control, IPTV, Downloads, and Settings preserves filters, queries, tabs, unsaved form edits, iframe state, and scroll for the session. Proven by the all-stateful-workspaces Playwright navigation test. |
| Lists, collections, followed releases, and curation caches | User-list JSON and browser-local followed-release state | SQL curation tables, `curation_generation`, list cache, collection caches, and browser invalidation events | Every successful curation read exposes its generation; mutations advance it; a newly observed generation clears dependent caches without requiring a catalog rescan. Proven by curation route/API tests and the browser curation-cache test. |

## Fixture Library

`tests/test_sql_migration_parity.py` seeds and exercises:

- a duplicate group and low-quality upgrade candidate;
- a manually corrected identity with a wrong Plex provider match;
- an owned Discover result;
- TMDB plot with a distinct Plex summary;
- a newly imported download and an unmatched file;
- a collection movie and custom poster;
- stable TMDB and IMDb download identity handoff.

## Current Acceptance Evidence

On 2026-07-20, the schema-v6 active-catalog audit passed at catalog generation 298:

- 3,708 SQL records checked and 3,707 accepted canonical movies;
- 7,199 provider snapshots, 31,206 people, and 43,833 ordered credits exposed relationally;
- 3,702 selected TMDB detail providers and 5 selected Plex fallback providers;
- 6 explicitly partial records, with no false provider completion;
- 0 provider calls;
- 0 SQL-row, canonical-model, deferred-detail, projection, or relational-shadow violations;
- SQLite integrity `ok` and 0 foreign-key violations.

The literal legacy JSON comparison was refreshed from the current SQL rollback export and independently passed:

- file records: 3,708 JSON / 3,708 expected / 3,708 SQL;
- TMDB snapshots: 4,749 / 4,749 / 4,749;
- Plex snapshots: 3,572 / 3,572 / 3,572;
- manual matches: 486 / 486 / 486;
- no legacy-only, SQL-only, canonical, document, or provider-call violations.

The immutable cutover archive `data/catalog-migration-backups/cp-catalog-migration-20260716T132416Z.zip` remains pinned by `docs/sql-migration-cutover.json` for historical evidence. The accepted current-state rollback package is `C:\Users\dante\AppData\Local\Cinema Paradiso\Backups\cp-catalog-migration-20260720T001304Z.zip`; it contains 1,150 files and was checksum-verified and rebuilt into a passing shadow catalog.

Desktop browser parity is proven by the Playwright test `Library, Discover-owned, and Movie List cards render one canonical movie contract`. Its compact fixture intentionally omits people, supplies them only through SQL deferred details, forces TMDB details to fail, and verifies Library, owned Discover, owned Movie List, Home, and AI Control render the persisted plot and people without a provider request. The browser ownership-cache test also proves a catalog-generation change invalidates cached ownership results.

Final verification passed: 54 JavaScript tests, 19 desktop Playwright workflow tests, the production frontend build, and all 676 Python tests. Normal operational monitoring remains separate from this cutover evidence.
