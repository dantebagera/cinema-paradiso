# Cinema Paradiso SQL Architecture Investigation and Repair

- Investigation date: 2026-07-19
- Repair acceptance date: 2026-07-20

Status: Schema v6 repair accepted at catalog generation 298. The original read-only diagnosis is retained below as the historical baseline.

## Repair Completion Update

The fundamental defect was not SQLite itself and it was not the use of provider JSON snapshots. The defect was the absence of a relational movie-domain owner between persisted source evidence and page-specific API projections. Physical file rows, TMDB JSON, Plex JSON, manual decisions, overrides, and frontend caches could therefore assemble different versions of the same movie.

Schema v6 adds that missing domain layer. SQL is now the live catalog authority; exported JSON is rollback and shadow-comparison evidence only. Provider `source_json` remains intentionally preserved so information not yet normalized is not discarded, but no page is allowed to treat that payload as a competing canonical movie authority.

### Accepted Live State

| Property | Accepted value |
| --- | ---: |
| Catalog generation | 298 |
| Schema version | 6 |
| Canonical contract version | 2 |
| Physical file records | 3,708 |
| Accepted canonical movies | 3,707 |
| Unmatched files | 1 |
| Provider snapshots linked to movies | 7,199 |
| People | 31,206 |
| Movie credits | 43,833 |
| Genres / movie-genre links | 25 / 16,714 |
| Collections / movie-collection links | 579 / 1,108 |
| Manual metadata and poster overrides | 13 |
| Identity decisions | 3,708 |
| Explicitly incomplete accepted records | 6 |
| SQLite integrity check | OK |
| Foreign-key violations | 0 |

The six incomplete records are exposed honestly as partial persisted metadata. They are not treated as migration failures and are not silently completed through an unrelated provider request.

### Canonical Relational Tables

| Table | Rows | Responsibility |
| --- | ---: | --- |
| `canonical_movies` | 3,707 | Stable accepted identity, selected provider, identity revision, and manual-lock policy |
| `canonical_movie_files` | 3,707 | Enforced file-to-movie relationship |
| `provider_movie_snapshots` | 7,199 | Persisted TMDB and Plex facts, completeness state, and retained source evidence |
| `people` | 31,206 | Provider person identities, names, and profile images |
| `movie_credits` | 43,833 | Ordered cast/director relationships and character names |
| `genres` / `movie_genres` | 25 / 16,714 | Normalized genre vocabulary and ordered movie membership |
| `collections` / `movie_collections` | 579 / 1,108 | Provider collections and movie membership |
| `movie_overrides` / `movie_override_identity_keys` | 13 / 48 | Locked metadata/poster overrides and the identities they target |
| `identity_decisions` | 3,708 | Accepted, unmatched, corrected, and locked identity decisions |

### Current Authority Boundaries

```text
media_files and identity_decisions
    -> canonical_movies and canonical_movie_files
    -> selected persisted provider snapshot
    -> normalized people, credits, genres, and collections
    -> locked movie overrides
    -> one canonical movie projection
    -> Library, Discover-owned, Lists, Home, Maintenance, AI Control, and ownership APIs
```

- `canonical_movies` owns accepted movie identity and provider-selection policy.
- `media_files` owns physical path, file facts, quality, and ingest state.
- `provider_movie_snapshots` owns persisted TMDB/Plex evidence. Plex is a supported fallback source, not the default source.
- `people`, `movie_credits`, genres, and collections own relational expanded details.
- `movie_overrides` owns locked custom metadata and poster choices.
- `user_lists`, `list_items`, followed releases, and collection overrides remain the curation domain and use `curation_generation`.
- qBittorrent remains an operational download journal. A user-cancelled unfinished torrent is a normal terminal outcome; only a completed recoverable import enters library reconciliation.
- IPTV remains a separate product boundary and database.

### Read and Write Contract

`services/canonical_catalog.py` is the single domain owner. Catalog writes synchronize affected relational rows in the same SQLite transaction and then advance `media_generation`. `canonical_media_generation` and `canonical_contract_version` prove whether the projection is current at startup. A stale generation, contract change, or row-count mismatch causes one relational rebuild; an already-current startup does not rebuild it.

`app.py` reads the relational canonical projection first for Library, card details, ownership, statistics, Maintenance, Lists, and editing contexts. Compact APIs may defer people and collection detail, but `/api/library/details` must obtain that detail from SQL without a TMDB or Plex request. Browser detail and ownership caches observe `catalog_generation`; curation caches separately observe `curation_generation`.

### Acceptance Evidence

- Relational audit: 3,708 records checked, 3,707 accepted, zero projection or deferred-detail violations, zero provider calls.
- Literal legacy JSON shadow: all file, TMDB, Plex, manual-match, canonical, and document comparisons passed with zero violations and zero provider calls.
- Rollback export: 16 documents verified with no mismatches.
- Final rollback archive: `C:\Users\dante\AppData\Local\Cinema Paradiso\Backups\cp-catalog-migration-20260720T001304Z.zip`; 1,150 files and 324,885,647 bytes; checksum and shadow reconstruction verified.
- Automated suites: 676 Python tests, 54 JavaScript tests, production Vite build, and 19 Playwright desktop workflow tests passed.
- Direct browser checks: immediate Library/List plots, stored cast/director details, actor/director owned-work navigation, Discover person portraits, Maintenance filter reset, preserved page state, and qBittorrent without migration-only warning records.

## Historical Baseline Before Repair

The remaining sections describe the schema-v5 system as it was inspected on 2026-07-19. Statements such as “no canonical movie entity” are historical findings and no longer describe schema v6.

## Executive Finding

The SQL design is a major contributor to the post-migration regressions, but it does not explain every broken feature.

Cinema Paradiso currently uses SQLite as a storage container for much of the previous JSON document architecture. It does not yet have a stable canonical movie entity. A movie shown in the interface is assembled at read time from a physical-file row, provider snapshots, manual decisions, overrides, Python merge rules, API-specific projections, and browser state.

This architecture allows SQLite to be structurally healthy while different CP pages still show different behavior for the same movie.

A SQL schema revision alone will not repair unrelated frontend state-management or Ollama connectivity problems. Those must be tested as separate workflows.

## Live Databases Inspected

### Local Movie Catalog

Path:

`C:\Users\dante\AppData\Local\Cinema Paradiso\Catalog\catalog-read-cb30c1d963c88463.sqlite`

Live measurements:

| Property | Value |
| --- | ---: |
| Database size | 47,222,784 bytes |
| Schema version | 5 |
| Tables | 12 |
| Total rows | 28,999 |
| Total columns | 105 |
| Indexes | 22 |
| Explicit foreign keys | 2 |
| SQLite integrity check | OK |
| Foreign-key violations | 0 |
| Write authority | SQLite |
| Global generation | 22,830 |
| Media generation | 226 |
| Curation generation | 16,481 |
| Export state | Dirty |

An `integrity_check` result of `ok` proves that the SQLite file is structurally readable. It does not prove that movie identities, metadata selection, API projections, cache invalidation, or rendered behavior are correct.

### IPTV Catalog

Path:

`C:\Users\dante\Desktop\cinema paradiso\data\iptv\iptv.sqlite`

Live measurements:

| Property | Value |
| --- | ---: |
| Database size | 72,470,528 bytes |
| Tables | 7 |
| Total rows | 67,914 |
| Total columns | 51 |
| SQLite integrity check | OK |

The IPTV database is a separate product boundary and has a clearer relational model. It should not be merged into the local movie-catalog recovery.

## Catalog Table Inventory

### `catalog_meta`

- Rows: 9
- Columns: 2
- Primary key: `key`
- Columns: `key`, `value`
- Purpose: schema version, SQL authority state, import metadata, generation counters, backup manifest, and rollback-export state.

### `source_documents`

- Rows: 17
- Columns: 2
- Primary key: `name`
- Columns: `name`, `payload_json`
- Purpose: preserves complete JSON-era documents inside SQLite.

Documents currently include file records, TMDB and Plex caches, manual matches, identity audit state, migration state, inventory, poster overrides, smart-match state, lists, collections, followed releases, and an imported qBittorrent jobs document.

Some documents are normalized into dedicated tables. Others remain opaque JSON blobs and use `source_documents` as their only SQL representation.

### `media_files`

- Rows: 3,708
- Columns: 31
- Primary key: `path_key`
- Purpose: physical media files plus accepted identity and metadata policy state.

Physical-file columns:

- `path_key`
- `path`
- `filename`
- `library_root`
- `size`
- `added_time`
- `modified_time`

File-analysis columns:

- `resolution`
- `rip_source`
- `parsed_title`
- `parsed_year`

Identity columns:

- `identity_status`
- `identity_title`
- `identity_year`
- `identity_source`
- `identity_revision`
- `identity_decision_version`
- `identity_evidence_fingerprint`
- `tmdb_id`
- `imdb_id`
- `plex_guid`
- `plex_rating_key`

Metadata-policy columns:

- `display_provider`
- `metadata_status`
- `metadata_source`
- `metadata_accepted`
- `enrichment_status`
- `ingest_status`
- `manual_lock`
- `manual_locked`

Legacy payload column:

- `raw_json`

The central modeling problem is that this table represents physical files, not canonical movies. File facts, movie identity, provider policy, and ingest state are combined in one row.

### `media_identity_keys`

- Rows: 15,179
- Columns: 3
- Primary key: `(path_key, identity_key)`
- Columns: `path_key`, `identity_key`, `key_source`
- Foreign key: `path_key -> media_files.path_key ON DELETE CASCADE`
- Purpose: maps a physical file to all identities that may be used for ownership matching.

Identity keys are derived from accepted identity fields, Plex snapshots, manual matches, and parsed filenames. The same `identity_key` may belong to multiple files, which is necessary for duplicate detection.

### `tmdb_movies`

- Rows: 2,248
- Columns: 9
- Primary key: `tmdb_id`
- Columns: `tmdb_id`, `imdb_id`, `title`, `year`, `poster_url`, `release_date`, `adult`, `updated_at`, `raw_json`
- Purpose: persisted TMDB provider snapshots.

Plot, cast, directors, genres, collection, runtime, ratings, trailer, and other extended fields remain in `raw_json`.

### `plex_files`

- Rows: 3,573
- Columns: 10
- Primary key: `path_key`
- Columns: `path_key`, `path`, `plex_title`, `plex_year`, `tmdb_id`, `imdb_id`, `plex_guid`, `rating_key`, `updated_at`, `raw_json`
- Purpose: persisted Plex metadata snapshots for physical files.

Plex summaries, people, genres, language, country, poster, and other extended fields remain in `raw_json`.

Plex is a source, not the default authority. That policy is valid. The problem is that provider selection and fallback behavior live in Python merge code and can differ across projections.

### `manual_matches`

- Rows: 486
- Columns: 12
- Primary key: `path_key`
- Columns: `path_key`, `path`, `provider`, `source`, `tmdb_id`, `imdb_id`, `plex_guid`, `title`, `year`, `accepted`, `updated_at`, `raw_json`
- Purpose: durable manual identity decisions.

These records are linked to files by matching `path_key`, but SQL does not enforce that relationship.

### `identity_audit_fingerprints`

- Rows: 3,495
- Columns: 7
- Primary key: `path_key`
- Columns: `path_key`, `path`, `provider`, `provider_id`, `rule_version`, `verified_at`, `raw_json`
- Purpose: records which identity and rule version were verified for a file.

### `user_lists`

- Rows: 10
- Columns: 6
- Primary key: `list_id`
- Columns: `list_id`, `name`, `system_type`, `created_at`, `updated_at`, `raw_json`
- Purpose: list definitions.

The `raw_json` value contains the entire list, including its embedded `movies` array.

### `list_items`

- Rows: 260
- Columns: 10
- Primary key: `(list_id, position)`
- Columns: `list_id`, `position`, `identity_key`, `tmdb_id`, `imdb_id`, `path`, `title`, `year`, `poster_url`, `raw_json`
- Foreign key: `list_id -> user_lists.list_id ON DELETE CASCADE`
- Purpose: normalized list membership and ordering.

Current production reads do not reconstruct lists from this table. They decode `user_lists.raw_json`, so `list_items` is currently a shadow projection rather than the authority for list membership.

### `collection_overrides`

- Rows: 1
- Columns: 4
- Primary key: `collection_id`
- Columns: `collection_id`, `name`, `updated_at`, `raw_json`
- Purpose: manually edited collection snapshots.

There is no SQL relationship to a canonical movie or provider snapshot.

### `followed_releases`

- Rows: 13
- Columns: 9
- Primary key: `position`
- Columns: `position`, `identity_key`, `tmdb_id`, `imdb_id`, `title`, `year`, `status`, `updated_at`, `raw_json`
- Purpose: ordered followed-release snapshots.

SQL does not enforce unique movie identity in this table.

## Enforced and Logical Relationships

Only two relationships are enforced by foreign keys:

```text
media_files 1 ---- many media_identity_keys
user_lists  1 ---- many list_items
```

Important logical relationships are implemented only through matching strings:

```text
media_files.path_key -> plex_files.path_key
media_files.path_key -> manual_matches.path_key
media_files.path_key -> identity_audit_fingerprints.path_key
media_files.tmdb_id  -> tmdb_movies.tmdb_id
```

Lists, followed releases, collections, posters, downloads, and provider search results cannot reference a canonical movie because no canonical `movies` table exists.

## Current Read Contract

The effective read path is:

```text
Normalized SQL columns
    + row raw_json
    + source_documents envelope
    + opaque override documents
    -> Python canonical merge
    -> route-specific API projection
    -> browser cache and component state
    -> rendered shared movie card
```

Main implementation locations:

- SQL schema and candidate queries: `services/catalog_store.py`
- JSON-compatible SQL repository: `services/catalog_repository.py`
- Metadata store compatibility layer: `app.py`, `AppMetadataStore`
- Provider and canonical merge: `app.py`, `_canonical_provider_metadata` and `_build_canonical_metadata`
- Library row assembly: `app.py`, `_catalog_library_item`
- Library card/list/people projections: `app.py`, `_library_card_item`, `_movie_list_library_item`, `_library_people_item`
- Curation behavior: `services/curation_store.py`
- Browser catalog generation: `src/api/library.js`
- Browser curation generation: `src/api/curation.js`
- Expanded detail resolution: `src/api/movieDetails.js`

This spread of ownership explains why SQL can contain a plot or person image while one page omits it and another page displays it.

## Live Data Findings

### Healthy Findings

- SQLite integrity passes.
- Existing enforced foreign keys have no violations.
- Normalized columns agree with the corresponding fields in each row's `raw_json`.
- `media_identity_keys` has no orphaned file references.
- `list_items` has no orphaned list references.
- Current embedded list movies agree with current `list_items` rows.

### Divergent Representations

The initial `source_documents` snapshots disagree with current normalized records:

| Record type | Changed | In SQL only | In source document only |
| --- | ---: | ---: | ---: |
| Media files | 34 | 45 | 13 |
| TMDB movies | 57 | 1,512 | 0 |
| Plex files | 2 | 0 | 12 |
| Manual matches | 12 | 1 | 1 |
| Identity fingerprints | 803 | 155 | 2 |

This divergence is partly intentional because row-level SQL writes do not update the original source-document snapshot. It is still dangerous because `source_documents` remains part of document reconstruction and remains the only SQL storage for several opaque documents.

The disk rollback exports matched normalized SQL for files, TMDB, Plex, manual matches, fingerprints, lists, and collections at inspection time. `followed_releases.json` differed from SQL for at least one checked record, and `catalog_meta.export_dirty` was still `1`. Therefore the rollback export was not certified current.

### Provider Detail Coverage

- 3,702 files select TMDB as display provider.
- 5 files select Plex.
- 1 file has no display provider.
- 2,501 files have a non-empty TMDB identity but no matching `tmdb_movies` row.
- All 2,501 have a Plex snapshot.
- 2,500 of those Plex snapshots contain a stored summary.
- 76 Plex snapshots have no current `media_files` row.

Missing TMDB snapshots are not automatically data loss because Plex may contain the stored details. However, the design requires every API projection to reproduce the same fallback policy. That requirement is exactly where the plot and expanded-card regressions appeared.

### Identity and Duplicate Evidence

- Accepted files: 3,707
- Unmatched files: 1
- Files with TMDB ID: 3,704
- Distinct TMDB IDs: 3,704
- Duplicate TMDB groups: 0
- Duplicate IMDb groups: 0
- Duplicate Plex GUID groups: 0
- Duplicate accepted title/year groups: 0
- Duplicate parsed title/year groups: 0

If duplicate physical movies are known to exist, duplicate grouping is not the first failure. Their persisted identities have already made every file appear unique before the maintenance audit runs.

## Confirmed Architectural Defects

### 1. No Canonical Movie Entity

CP cannot query SQL for a single authoritative movie. It queries physical files and dynamically constructs movies. Consequently, Library, Discover ownership, Lists, Maintenance, Home, AI Control, and downloads can assemble different representations of the same identity.

### 2. Multiple Representations of the Same State

Several domains exist as normalized columns, per-row `raw_json`, original `source_documents`, and disk rollback JSON. The design depends on every write path respecting undocumented precedence rules.

Keeping provider payloads as JSON is reasonable. Keeping multiple competing representations of domain decisions is not.

### 3. Canonical Behavior Has No Dedicated Owner

Identity resolution, provider selection, enrichment, overrides, fallback behavior, and route projections are spread across `app.py`, repository code, and frontend normalization.

### 4. Existing Shadow Comparison Is Not Independent

`tools/catalog_json_shadow_compare.py` sends both legacy JSON records and SQL records through the current `_build_canonical_metadata` implementation.

If the current canonical function contains a regression, both sides can agree and the audit can pass while user-visible behavior remains wrong.

### 5. Projection Audit Compares Current Code to Itself

`tools/catalog_parity_audit.py` creates the canonical model and its route projections using the same current runtime. This tests internal consistency, not parity with pre-SQL behavior.

### 6. `list_items` Is Not the List Read Authority

The normalized list-membership table is created, indexed, and maintained, but application reads decode the movie array in `user_lists.raw_json`. There are two list representations and only code convention keeps them synchronized.

### 7. No Versioned Schema Migration Sequence

The catalog initializer uses `CREATE TABLE IF NOT EXISTS` and then writes schema version 5. No ordered version-to-version migration or `ALTER TABLE` path was found.

An older incompatible table can therefore survive initialization while being labeled with the current schema version.

### 8. Invalidation Is Broad and Observation-Dependent

Every `app_metadata/*` write invalidates the complete media domain. Lists, collections, and followed releases share one curation generation.

The backend cache keys include generations, but browser caches discover background changes only after receiving a newer generation from an API response or an explicit application event.

### 9. Physical Path Is a Domain Anchor

Rename and move operations must migrate file, Plex, manual match, fingerprint, conflict, inventory, override, and browser state correctly. Missing one path-keyed record splits the movie's history.

### 10. Domain Rules Are Not Enforced by SQL

SQL does not enforce:

- Valid provider or status values.
- One accepted canonical identity.
- Provider snapshot lifecycle.
- Unique membership identity within a list.
- Unique followed-release identity.
- Override ownership.
- Referential relationships between files and provider snapshots.

These rules currently depend on Python behavior.

## Important Non-Defects and Boundaries

- Plex being a source rather than the default source is valid.
- Full JSON provider payloads can remain when their ownership and precedence are explicit.
- A missing TMDB snapshot can be valid if a persisted Plex snapshot provides details.
- IPTV should remain separate from local movie identity, CP Movie Lists, torrent ownership, and local-library reconciliation.
- qBittorrent jobs are intentionally external to this catalog. `download_jobs` is dropped during catalog initialization, and `qbittorrent/jobs.json` is excluded from catalog exports.
- Frontend page-state loss and Ollama connectivity require separate investigation and cannot honestly be assigned to the SQL schema without evidence.

## IPTV Table Summary

| Table | Rows | Purpose |
| --- | ---: | --- |
| `items` | 67,493 | Live channels, movies, and series from the provider catalog |
| `categories` | 325 | Provider category ordering and counts |
| `details` | 80 | Cached extended item details |
| `iptv_lists` | 2 | Favorites and custom IPTV lists |
| `iptv_list_items` | 5 | IPTV list membership with snapshots |
| `watch_history` | 7 | Playback position and completion |
| `meta` | 2 | IPTV generation and synchronization metadata |

The enforced IPTV list relationship is:

```text
iptv_lists 1 ---- many iptv_list_items
```

## Required Recovery Scope

### Stage 0: Freeze and Evidence Capture

1. Stop catalog-writing background processes during capture.
2. Back up the live SQLite database using SQLite's backup API.
3. Export all SQL-backed documents to a new immutable rollback directory.
4. Include custom poster files, configuration, qBittorrent jobs, and IPTV state.
5. Record hashes, row counts, schema SQL, generations, and file timestamps.
6. Verify the backup in a separate rehearsal directory.

Completion condition: one reproducible snapshot can restore the exact captured state without touching the live installation.

### Stage 1: Independent Pre-SQL Behavior Oracle

1. Run the pre-SQL 2.7 implementation in an isolated workspace.
2. Load a frozen fixture library without current SQL canonical helpers.
3. Capture API responses and rendered desktop behavior for each required workflow.
4. Store immutable expected outputs for identity, metadata, cards, ownership, maintenance, lists, downloads, and file operations.
5. Include negative controls that deliberately remove a plot, person image, list row, or duplicate and prove the gate fails.

Completion condition: legacy expectations remain unchanged even if current SQL or canonical code is modified.

### Stage 2: Behavior-Parity Matrix

For every major workflow, record:

- Original pre-SQL source of truth.
- Current SQL source of truth.
- Every cache, projection, background process, and browser state.
- Inputs and outputs.
- Invalidation event.
- Completion condition.
- User-visible behavior that must remain identical.

Required workflows:

- Home statistics versus Maintenance audit.
- Library cards versus Discover-owned cards versus List cards.
- Summary metadata versus expanded details.
- Posters, plots, cast, genres, ratings, collections, and manual overrides.
- Identity matching, correction, conflict review, and audit.
- Duplicate groups and upgrade candidates.
- Source search, ownership checks, download submission, completed import, and library reconciliation.
- File View, deletion, rename, and metadata persistence.
- Startup reconciliation and background job updates.
- Browser page-state preservation across navigation.
- Plex refresh and fallback behavior.

Completion condition: every row has an independent executable test and an explicit expected result.

### Stage 3: Canonical Movie Contract

Define one domain-owned operation that returns the complete stored movie model:

- Stable movie identity.
- Physical files and quality facts.
- TMDB snapshot.
- Plex snapshot.
- Selected display source.
- Explicit fallback policy.
- Manual identity decision.
- Plot and summary.
- Poster and custom override.
- Genres, cast, directors, ratings, runtime, trailer, language, and country.
- Collection and user override.
- Ownership and upgrade state.
- Generation/revision information.

Every API projection must derive from this contract. A projection may intentionally defer expensive fields, but deferred details must remain available from stored SQL data without an unrelated provider call.

Completion condition: Library, Discover, Lists, Home, Maintenance, AI Control, and download ownership return the same identity and overlapping metadata fields for the same movie.

### Stage 4: Schema Revision

The target schema should separate these responsibilities:

1. Stable canonical movies.
2. Physical media files linked to movies.
3. Identity aliases linked to movies.
4. Provider snapshots linked to movies and providers.
5. Manual identity decisions and immutable audit history.
6. Metadata and poster overrides linked to movie identity.
7. Lists referencing canonical movies or explicit external snapshots.
8. Collection membership and overrides.
9. Download/import handoff state linked to stable identity.

Provider payload JSON may remain for complete snapshots, but normalized domain fields must have one documented authority.

Completion condition: a developer can identify one authoritative owner for every field without knowing the JSON-era implementation.

### Stage 5: Versioned Migration Mechanism

1. Introduce ordered schema migrations with explicit from/to versions.
2. Run each migration transactionally.
3. Check preconditions before writes.
4. Validate row counts, relationships, and canonical outputs afterward.
5. Preserve a verified rollback export.
6. Never set the new schema version unless every migration and validation succeeds.

Completion condition: upgrading an old database produces the same schema and behavior as creating a new database at the current version.

### Stage 6: Generation and Cache Contract

Define generations for:

- File inventory and quality.
- Canonical identity.
- Provider details.
- Posters and metadata overrides.
- Lists and watched/watchlist state.
- Collections.
- Maintenance projections.
- Download/import state.

Every write and background process must publish the relevant generation change. Backend and browser caches must use the same contract.

Completion condition: a mutation becomes visible on every affected mounted page without navigation, timeout-based luck, or manual refresh.

### Stage 7: Fixture-Backed Automated Tests

The fixture must include:

- A duplicate group.
- A manually corrected identity.
- A wrong provider match.
- An owned Discover result.
- A movie with TMDB plot and Plex summary.
- A newly imported download.
- An unmatched file.
- A low-quality upgrade candidate.
- A collection movie.
- A movie with a custom poster.

Tests must cover SQL rows, canonical domain output, every API projection, browser invalidation, rendered desktop cards, restart persistence, and absence of unrelated provider calls.

### Stage 8: Full Desktop Workflow Gate

Use the actual application and systematically:

1. Open every page.
2. Exercise every visible control.
3. Expand and collapse every card type.
4. Navigate actors, directors, collections, lists, and ownership links.
5. Change and reset filters, then navigate away and return.
6. Apply and reset metadata and poster overrides.
7. Test duplicates, upgrades, unmatched identities, and maintenance navigation.
8. Submit, cancel, complete, and reconcile downloads.
9. Rename and delete files.
10. Restart CP and verify persistence.

Completion condition: zero blocking mismatches against the independent pre-SQL oracle and the approved behavior matrix.

### Stage 9: Cutover

SQL becomes sole authority for a domain only after that domain's complete parity gate passes. JSON remains a generated, verified rollback artifact, not a second live authority.

## Recommended Immediate Next Step

Do not modify the schema yet.

First implement Stages 0 through 2: immutable evidence capture, an independent pre-SQL oracle, and the complete behavior-parity matrix. This prevents another round of fixes that make the current implementation internally consistent while remaining behaviorally wrong.
