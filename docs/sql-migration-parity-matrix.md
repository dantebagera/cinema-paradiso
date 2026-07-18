# SQL Migration Parity Matrix

This is the release checklist for the JSON-to-SQL catalog cutover. SQL is the active catalog authority. JSON is retained only as a rollback export and read-only shadow-comparison input; it is not a second live authority.

## Rules for Every Row

- The SQL row must contain the required state.
- The canonical movie model must expose it.
- Compact projections may intentionally defer detail fields, but expanded details must read them from SQL without a provider request.
- A catalog mutation must advance `catalog_generation` and invalidate server and browser projections that depend on it.
- The user must see the same movie identity across relevant pages.

## Workflow Evidence

| Workflow | Before SQL source | Current SQL source and involved state | User-visible invariant and completion proof |
| --- | --- | --- | --- |
| Home statistics versus Maintenance audit | JSON-derived library snapshot and audit state | `media_files` and catalog generation; server library, stats, and maintenance caches | Counts refresh together after a mutation. Proven by `test_home_stats_and_maintenance_share_the_catalog_generation_and_refresh_after_mutation`. |
| Library cards versus Discover owned cards versus Movie List cards | Library JSON, Discover ownership lookup, user-list JSON | `media_files`, canonical model, `/api/library`, `/api/library/check`; browser ownership cache and user-list cache | The same accepted TMDB/IMDb/title/year identity is shown everywhere; a populated Plex identity is kept only when it is an accepted provider identity. Cards and ownership checks defer plots; the full Library read obtains persisted SQL details. Proven by `test_api_projections_defer_details_without_provider_calls_and_keep_owned_cards_consistent`, the Plex-provider catalog audit, and ownership-cache browser test. |
| Summary metadata versus expanded details | TMDB and Plex JSON snapshots | `tmdb_json`, `plex_json`, canonical model, card/list/people projections | TMDB plot is canonical when present; Plex summary remains available; compact cards omit expensive detail intentionally. Proven by catalog audit and SQL fixture tests with provider calls blocked. |
| Posters, plots, cast, genres, ratings, collections, and manual overrides | TMDB/Plex JSON plus override JSON | SQL snapshots and durable override records, projected through canonical metadata | The same accepted movie preserves metadata and custom poster without mutating provider snapshots. Proven by SQL fixture, metadata override, poster override, and collection tests. |
| Identity matching, correction, conflict review, and audit | Match JSON and provider-specific records | Accepted identity columns, manual matches, audit state, decision fingerprints | Manual corrections stay locked; conflicts remain reviewable; exact identities can be verified read-only. Proven by identity audit, repair, verification, and Plex manual-match suites. |
| Duplicate groups and upgrade candidates | JSON-derived audit grouping | SQL library candidates and maintenance audit projection | Duplicate and quality groups use the same accepted identity and change after file facts mutate. Proven by SQL fixture and duplicate identity tests. |
| Source search, ownership checks, download submission, completed import, and library reconciliation | Source result state, JSON job records, filename follow-up | Stable TMDB/IMDb/Plex identity in job metadata, SQL ownership lookup, job journal, reconcile state | Owned movies do not download; title-only sources are rejected; a completed import hands its original identity to the exact imported file before reconciliation. Proven by SQL fixture plus qBittorrent API/service tests. |
| File View, deletion, rename, and metadata persistence | File JSON plus filesystem scan state | SQL path records and canonical item projections; catalog generation and library cache | Rename/delete changes File View, Library, ownership, stats, and maintenance without a full rescan. Proven by catalog file mutation and SQL fixture tests. |
| Startup reconciliation and background job updates | Metadata checkpoints and qBittorrent job JSON | SQL persisted facts, reconciliation state, qBittorrent journal, catalog generation | Cold start reads SQL without provider calls; pending identity handoffs replay once; completed handoffs do not replay. Proven by SQL fixture and qBittorrent service tests. |

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

On 2026-07-16, the read-only active-catalog audit passed:

- 3,701 SQL records checked;
- 3,700 accepted records;
- 0 provider calls;
- 0 SQL-row, canonical-model, deferred-detail, or projection violations;
- persisted detail providers: 1,151 TMDB snapshots and 2,549 Plex snapshots.

On 2026-07-16, the historical JSON shadow comparison also passed:

- 3,699 legacy JSON file records compared directly with SQL;
- no missing legacy records, canonical differences, raw migrated-record differences, or provider calls;
- two SQL file records and one unreferenced TMDB record were created after the JSON snapshot and are explicitly reported as post-snapshot state;
- three existing file records and two existing TMDB records were refreshed after the snapshot, with no canonical behavior difference for the pre-existing movies.

The rollback archive `data/catalog-migration-backups/cp-catalog-migration-20260716T132416Z.zip` was checksum-verified and rebuilt into a temporary shadow catalog. After the backend restart, Library, Home statistics, and Maintenance all reported catalog generation `53`; the download monitor was healthy and processed no completed imports.

Desktop browser parity is also proven by the Playwright test `Library, Discover-owned, and Movie List cards render one shared movie identity`. It supplies one controlled movie through each API projection and verifies the rendered Library, owned Discover, and owned Movie List cards show the same title and year. The browser ownership-cache test also proves a catalog-generation change invalidates cached ownership results.

All required automated migration-parity checks are complete. Normal operational monitoring remains separate from this cutover evidence.
