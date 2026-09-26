# Local TV Backend: Sonarr-Informed Zero-Regression Plan

**Status:** Proposed for review. Documentation only; implementation is not approved.

**Prepared:** 2026-09-14

**Revised:** 2026-09-18 after Dante approved the shared quality-profile and worktree-isolation decisions

**Repository:** Cinema Paradiso (CP)

**Implementation worktree:** `C:\Users\dante\.codex\worktrees\tv-acquisition-20260918\cinema paradiso` on branch `codex/native-tv-acquisition`

**Reference snapshots:** CP commit `adfa90a2e984f59585c7635e839f0c594b74b4cc`; Sonarr `main` commit `4ff1b780010d3d9ec76a4864dce96b6494e9caea`

## 1. Executive finding

TV acquisition cannot be implemented as movie acquisition with a different poster. A movie normally has one title-level search target and one primary video. A series contains seasons and episodes; a release can contain one episode, several episodes, a season pack, or a complete-series pack; a physical file can represent more than one episode; numbering can differ between providers; and new episodes arrive over time.

CP should learn Sonarr's strongest techniques: hierarchical monitoring, episode-aware parsing, structured release decisions, quality profiles, custom formats, missing/cutoff searches, per-file import decisions, seeding-aware imports, failure history, and automatic retry. CP should implement those techniques within its own architecture and user experience. Sonarr is a research reference, not a runtime service or required dependency.

The safest design is a new `tv-catalog.sqlite` for canonical TV, season, episode, people, credit, file, binding, and playback data; an optional acquisition database for CP-level intent and decision history; and the existing qBittorrent `jobs.json` for operational transfer and crash-recovery state. These owners must not duplicate each other.

TV launches behind explicit gates. The movie catalog, movie routes, movie playback, existing acquisition flow, IPTV stores, and current navigation remain unchanged until TV contracts are proven in isolation and then enabled deliberately.

## 2. Authorization boundary

Dante authorized this report. That authorization covers documentation only. It does not authorize:

- creating or migrating a production database;
- editing application code, configuration, or media files;
- performing live metadata, Prowlarr, torrent, qBittorrent, or Plex operations;
- building or restarting CP;
- staging, committing, pushing, tagging, packaging, or publishing.

Implementation begins only after Dante approves the executive summary or a named subset of this plan.

All implementation must remain in the dedicated worktree above and use disposable configuration, databases, qBittorrent profiles, and media roots. The current-use checkout and runtime are outside this plan.

## 3. Meaning of zero regression for a new subsystem

No plan can guarantee the absence of every defect. For this project, zero regression means that TV is additive and isolated until its behavior is proven:

1. Existing movie behavior is captured before shared components are touched.
2. TV schema and migrations operate only on disposable `tv-catalog.sqlite` fixtures until an approved live-data gate.
3. The existing movie `catalog.sqlite` is not converted into a mixed media database.
4. qBittorrent transport remains owned by `services/qbittorrent.py` and its atomic `jobs.json` journal.
5. IPTV remains provider-local and cannot write native TV, movie, or frontend source data.
6. Every shared API, playback, navigation, card, search, and download change has explicit movie regression coverage.
7. Each rollout gate has a rollback that does not require reconstructing user data.
8. Production bundle hashes and visible desktop behavior are verified before completion is claimed.
9. Any unexplained change in movie results, movie database contents, watched state, playback, downloads, or startup stops the rollout.

## 4. Confirmed current owners and constraints

Gate T0 must refresh exact line numbers and runtime state. The current ownership map is:

| Responsibility | Current owner | TV disposition |
|---|---|---|
| Movie canonical data and files | `services/catalog_store.py`, `services/catalog_repository.py`, `services/canonical_catalog.py` | Preserve. TV uses a separate store and cannot silently expand movie table semantics. |
| Movie ingestion and final-card publication | `services/library_ingestion.py`, `CatalogRepository.final_card_publication` | Reuse the pipeline pattern, not its movie-shaped records. Create an authoritative TV ingestion owner. |
| Prowlarr transport | `services/source_search.py` | Keep as the only network transport owner; extend with typed TV search inputs and outputs. |
| Search, release projection, and followed releases | Mostly `app.py` | Do not add TV policy to `app.py`. Move shared acquisition concepts behind services after movie parity fixtures exist. |
| qBittorrent runtime and recovery | `services/qbittorrent.py`, `user-data/qbittorrent/jobs.json` | Preserve. Add typed TV job metadata without moving transfer progress into SQLite. |
| Playback progress | `services/playback_history.py` | Generalize through a media-target contract only after movie behavior is locked. Episode progress becomes authoritative for TV. |
| Movie curation | `services/curation_store.py` and movie catalog tables | Preserve. TV monitoring is a different concept and belongs to TV/acquisition ownership. |
| Frontend movie state | Movie-specific pages and cards | Preserve through a typed media boundary; TV must not enter movie selectors accidentally. |
| IPTV series | Provider-local IPTV data and routes | Keep isolated. It may supply presentation/player lessons but cannot become native TV storage. |

The current qBittorrent import path pauses a completed torrent, moves its payload, and removes the torrent. That is acceptable for today's movie behavior but generally ends seeding. TV season packs make this weakness more costly because one torrent may be useful for a long time and may contain files that arrive or import together.

## 5. Research and licensing boundary

Sonarr is GPL-3.0. CP may study its public source to understand responsibilities, ordering, state machines, and failure cases. CP should not copy source code or create a runtime dependency on Sonarr unless Dante separately chooses a compatible licensing and product strategy.

For each adopted technique, the engineering record must capture:

- the behavior observed in Sonarr;
- the CP requirement derived from it;
- CP's independently designed implementation;
- tests proving CP behavior without importing Sonarr fixtures or code.

## 6. What CP should adopt from Sonarr

| Technique | Why TV needs it | CP adaptation |
|---|---|---|
| Series, season, and episode monitoring | Users may want all episodes, future episodes, one season, or selected episodes. | A hierarchy with explicit states and inherited effective monitoring. No copied booleans that drift. |
| Episode-aware release parsing | Names such as `S02E03`, `S02E03-E04`, daily dates, absolute numbers, and season packs mean different targets. | A parser returns structured claims plus confidence and evidence; it never mutates the catalog. |
| Structured release decisions and rejections | Users need to know why a result is allowed or rejected. | One decision engine returns machine codes and plain explanations for identity, episode coverage, quality, language, size, seeders, blocks, and policy. |
| Deterministic candidate ordering | Search and automation must choose the same candidate from the same inputs. | Compare approval, coverage, quality score, custom-format score, protocol/seed health, indexer priority, age, size, and stable tie-breaker in a documented order. |
| Quality profiles and cutoffs | A 720p episode may be acceptable now but still eligible for a later 1080p upgrade. | Store desired quality, acceptable floor, cutoff, upgrade permission, and size limits per monitored series with inheritance from a default profile. |
| Custom formats | Release groups, codecs, HDR, audio, language, source, and unwanted markers affect suitability. | Declarative rules produce scores and explanations. Measured file facts replace release claims after import. |
| Missing and cutoff-unmet searches | TV is continuous; newly aired or low-quality episodes need later action. | A scheduler creates bounded work from monitored episode state. It must not scrape every series on every tick. |
| Delay and availability policy | The first release may be poor; air times and provider dates are imperfect. | Per-profile delay windows, minimum age, and availability time with explicit override. Store why a search became eligible. |
| History, blocklist, and retry | Failed or corrupt releases should not be chosen repeatedly. | Immutable acquisition events plus scoped block entries; retries rerun selection with the failed candidate excluded. |
| Per-file import decisions | Packs can contain samples, extras, wrong seasons, and mixed qualities. | Validate and map every file separately; import accepted files only when the result remains internally consistent. |
| Seeding-aware hardlink/copy import | Moving a pack immediately breaks seeding and can disturb partially imported packs. | Prefer same-volume hardlinks; otherwise copy while seeding; move only under an explicit non-seeding policy. Verify before publication. |
| Manual import/reconciliation | Ambiguous numbering cannot always be resolved safely. | A review queue shows filename, parsed target, provider match, conflicts, and proposed destination before an operator commits it. |
| Disk-space and queue awareness | Packs are large and can starve other downloads. | Reserve staging plus import space, account for hardlink/copy behavior, and block work with an explicit reason when insufficient. |
| Proper/repack/version handling | An episode can be re-released without a simple quality increase. | Model revision signals as candidate facts and record replacement reason; never infer deletion permission. |
| Refresh/rescan separation | Metadata refresh and disk scanning are different operations. | Separate provider refresh, filesystem reconciliation, decision evaluation, search, download, import, and publication commands. |

## 7. What CP should adapt or reject

CP should not reproduce Sonarr screen-for-screen or table-for-table.

| Sonarr pattern | CP decision | Reason |
|---|---|---|
| External Sonarr service controls TV | Reject | CP is the product and must own the behavior. |
| One database for every media concern | Reject | Separate movie and TV stores reduce migration blast radius and match different schemas. |
| One active logical episode file view | Adapt | CP should support multiple physical copies and qualities, as it already does for movies. |
| Automatic deletion during upgrade | Reject for initial release | Replacement should publish the new verified copy first; deletion is a later, explicit maintenance policy. |
| Broad rename/organize subsystem | Defer | Correct identity, download, import, and playback come first. Initial naming can be deterministic and conservative. |
| Multiple download clients and protocols | Defer | CP already owns one embedded qBittorrent path. Generalizing clients would expand risk without enabling TV fundamentals. |
| Calendar and notification ecosystem | Defer | Useful later, but unrelated to a safe first local-TV vertical slice. |
| Provider numbering treated as unquestioned truth | Reject | Provider, filename, directory, Plex, and operator evidence may conflict. Ambiguity must be reviewable. |

## 8. Domain model and authoritative storage

### 8.1 Database boundary

Create `tv-catalog.sqlite` beside the movie catalog, with its own schema version, migrations, repository, integrity audit, backup, and restore path. Do not attach it to the movie database or rely on cross-database SQL joins. Application services may compose read models in memory.

Recommended initial tables:

| Table | Purpose |
|---|---|
| `series` | Canonical local series identity, titles, overview, dates, status, artwork, provider IDs, metadata timestamps. |
| `series_external_ids` | Typed provider identities such as `tmdb:tv`, TVDB, IMDb, and later aliases. |
| `seasons` | Season number/order, title, overview, air dates, statistics, and specials flag. |
| `episodes` | Episode identity, season/episode numbers, absolute/date numbering where applicable, title, overview, air time, runtime, and provider IDs. |
| `people` | TV-local canonical people records with external provider identities. |
| `series_credits` | Series-level creators and recurring roles. |
| `episode_credits` | Episode cast/crew and guest roles. |
| `media_files` | Physical path, size, hashes where available, measured video/audio facts, timestamps, and availability state. |
| `episode_file_bindings` | Many-to-many relation between files and episodes, including segment/order metadata for multi-episode files. |
| `playback_progress` | Episode-level position, duration, completion, last played, and selected file/version. |
| `watch_events` | Append-only episode completion/uncompletion history if required for audit and sync. |
| `ingestion_candidates` | Temporary, reviewable classification and mapping proposals; not canonical publication. |
| `metadata_events` | Provider refresh outcomes and provenance without duplicating current canonical fields. |

Series and season completion counts are derived from episode state. They must not be independently editable counters.

### 8.2 People across movies and TV

The TV catalog has its own people and credits because its lifecycle and database are independent. UI composition may recognize the same person through a typed provider ID, for example a TMDB person ID. It must not merge rows solely by display name. A future unified person page can query movie and TV repositories through an application service.

### 8.3 Acquisition state

If persistent CP-level acquisition intent is needed, create a separate versioned `acquisition.sqlite` containing profiles, monitored targets, candidate evaluations, events, blocklist entries, and scheduler leases. It may refer to typed targets such as:

- `movie:tmdb:603`
- `series:tmdb:tv:1399`
- `season:tmdb:tv:1399:4`
- `episode:tmdb:tv:1399:4:6`

It must not store qBittorrent percentages, peer state, temporary paths, transfer plans, or recovery truth. Those stay in `jobs.json`. Link the two domains with an acquisition correlation ID and verified torrent infohash.

### 8.4 Ordering and specials

Initial release supports the provider's aired season/episode order plus season 0 specials. Absolute, DVD, streaming, and alternate orders must be represented as explicit mappings, not destructive renumbering. If the evidence cannot choose an order safely, the item enters manual review.

## 9. Required contracts

### 9.1 Monitoring contract

Each series has a default monitoring mode, such as future episodes, missing episodes, all episodes, or none. A season or episode may override that default. The service computes one effective monitoring decision and explains its origin. Changing a series default does not overwrite explicit episode overrides.

### 9.2 Metadata contract

Provider metadata creates or refreshes canonical series, seasons, and episodes only through the TV repository. Refresh is idempotent. A provider outage leaves existing data usable. Removed or renumbered provider episodes are quarantined for reconciliation when local files or watch history depend on them.

### 9.3 Parsing contract

The parser produces claims rather than conclusions:

- probable series title and year;
- season/episode range or season-pack scope;
- daily date or absolute number when present;
- quality, source, codec, HDR, audio, language, group, proper/repack, and edition-like markers;
- release type and confidence;
- ignored/sample/extras signals.

The resolver combines those claims with the requested target, provider episode map, existing catalog, directory context, and torrent file manifest. A title match alone is never sufficient.

### 9.4 Decision contract

Every evaluated release returns:

- requested target and covered episodes;
- accepted or rejected state;
- stable rejection/warning codes;
- readable explanations;
- quality and custom-format scores;
- upgrade effect per covered episode;
- missing, already-owned, and conflict sets;
- estimated download/import space;
- policy and parser versions;
- deterministic sort key.

The UI and automation consume the same result. Routes do not reimplement release rules.

### 9.5 Download contract

Before a magnet resumes, CP must verify:

1. returned metadata matches the expected infohash;
2. every path is relative and safe;
3. the manifest contains an acceptable video share;
4. selected files cover the approved episode target;
5. dangerous extensions, samples, and unrelated payloads are rejected or explicitly excluded;
6. size stays inside policy and available-space reservations;
7. the candidate is still eligible under the current catalog and blocklist.

The approved decision snapshot and correlation ID travel with the qBittorrent job. A stale decision is reevaluated before import.

### 9.6 Import contract

Import is a journaled, restartable plan:

1. freeze and revalidate the completed manifest;
2. probe each selected video and compare measured facts with release claims;
3. resolve each file to one or more canonical episodes;
4. compute collision-safe destinations;
5. reserve disk space;
6. hardlink on the same volume when seeding; otherwise copy and verify; move only when policy permits stopping seeding;
7. write file and episode bindings transactionally;
8. publish only verified episodes;
9. retain the source until verification and rollback checkpoint succeed;
10. record history and release reservations.

A pack can partially succeed only when accepted files are independently valid and the UI/history shows which episodes failed. It must never report the whole pack as imported when some expected episodes are absent.

### 9.7 Playback and watched contract

Playback targets an episode and a selected physical file. Resume position and completion belong to that episode/file choice. Series and season progress are derived. Completing one episode must never mark the whole series watched. Rewatch and manual mark/unmark operations must preserve the existing movie semantics for movies.

### 9.8 Shared quality-profile contract

TV acquisition uses the same authoritative source dictionary, resolution dictionary, named profiles, four eligibility states, custom-format evaluator, source-confidence model, and decision explanations as movies. TV adds episode coverage and pack consistency rules; it does not create a second quality system.

- Cinema captures and pre-release screeners are hard-blocked by default.
- WEBRip, WEB-DL, Blu-ray encode, and Remux remain distinct.
- Source and resolution are evaluated separately.
- A monitored series stores a profile ID; season or episode overrides may select another profile without copying it.
- `manual_only` releases remain visible but automation cannot choose them.
- A pack is rejected or split for review when its files conflict materially with the approved source/resolution claims.
- YTS may contribute movie evidence but is not a TV availability authority. TV uses provider dates, trusted indexers/groups, manifest evidence, and measured file facts.

### 9.9 Streaming Link contract

Native TV preserves CP's existing configurable Streaming Link feature. Streaming is separate from local playback and torrent acquisition, but follows the same movie visibility and safety rules:

- the global Streaming enabled state and label remain authoritative;
- a TV-specific URL template uses typed placeholders such as `{tmdb_id}`, `{season_number}`, and `{episode_number}` rather than forcing episode data through the movie template;
- a series-card Streaming action resolves the same current episode target as Resume/Play next;
- an episode-row Streaming action targets that exact released episode;
- the action is hidden when Streaming is disabled, the TV template is incomplete, no valid episode target exists, or the episode is unreleased;
- it opens through CP's existing embedded Streaming Link owner and does not write IPTV, TV catalog, watched, or acquisition state merely by opening;
- IPTV streaming remains provider-local and is not reused as native TV authority.

## 10. Proposed service ownership

Names are provisional, but each responsibility needs one owner:

| Service | Responsibility |
|---|---|
| `tv_catalog_store.py` | Connection, schema versioning, transactions, backup, integrity primitives. |
| `tv_catalog_repository.py` | Canonical series/season/episode/person/file reads and writes. |
| `tv_metadata.py` | Provider normalization, provenance, refresh, alternate-order mapping. |
| `tv_filename_parser.py` | Pure extraction of release and episode claims. |
| `tv_episode_resolver.py` | Evidence-based mapping of claims/files to canonical episodes. |
| `acquisition_profiles.py` | Quality profiles, cutoffs, custom-format rules, inheritance. |
| `acquisition_decision.py` | Shared deterministic movie/TV decision result with media-specific evaluators. |
| `tv_monitoring.py` | Effective monitored state and missing/cutoff work generation. |
| `tv_acquisition.py` | Search orchestration, reservations, correlation, retry, blocklist, history. |
| `tv_import.py` | Per-file import plans, file operations, verification, rollback, publication. |
| `tv_ingestion.py` | Local/Plex filesystem discovery and review proposals independent of downloads. |
| `tv_read_model.py` | API-facing aggregates for cards, series pages, progress, and availability. |

`app.py` remains an HTTP composition root. It validates requests, calls a service, and serializes typed results. It does not parse releases, choose candidates, map episodes, or manipulate files.

## 11. API outline

All endpoints are versioned or added without changing current movie response shapes.

| Endpoint family | Purpose |
|---|---|
| `GET /api/tv/series` | Filtered/paginated TV Library read model. |
| `GET /api/tv/discover` | Provider-backed discovery with local availability overlay. |
| `GET /api/tv/series/{id}` | Series, seasons, episode summaries, cast, monitoring, availability, progress. |
| `GET /api/tv/series/{id}/seasons/{n}` | Episode rows and versions for one season. |
| `POST /api/tv/series/{id}/monitor` | Explicit monitoring update with effective-state preview. |
| `POST /api/tv/search` | Manual series/season/episode search returning explained decisions. |
| `POST /api/tv/acquisitions` | Submit an approved candidate by stable decision token. |
| `GET /api/tv/acquisitions/{id}` | CP-level intent/history plus linked qBittorrent status. |
| `GET /api/tv/review` | Ambiguous ingestion/import proposals. |
| `POST /api/tv/review/{id}/apply` | Apply an operator-confirmed mapping transactionally. |
| `POST /api/tv/episodes/{id}/play` | Resolve an available version and create playback handoff. |
| `POST /api/tv/episodes/{id}/progress` | Episode progress/completion update. |

`GET/POST /api/streaming/config` remains the single Streaming Link configuration owner and gains an optional TV template through a backward-compatible field. Existing movie fields and behavior remain unchanged.

Mutation endpoints require an idempotency key or stable decision token. Existing movie endpoint contracts remain byte-for-byte compatible until an explicitly approved later API version.

## 12. Delivery gates

### T0 — Freeze and measure the real baseline

- Record active checkout, dirty worktree, Python/Node versions, catalog schema/runtime paths, configured providers, and served bundle hashes.
- Inventory movie, playback, download, startup/shutdown, IPTV, and frontend contracts.
- Capture sanitized response fixtures for representative movie routes.
- Confirm no running process points at this worktree before test operations.

**Exit:** Baseline report is reviewable and current. No mutation.

### T1 — Characterization and fixtures

- Add synthetic TV naming and manifest fixtures: single episode, multi-episode, season pack, complete pack, specials, daily, absolute, proper/repack, sample/extras, unsafe paths, collisions, and ambiguous numbering.
- Lock current movie torrent preflight, import, multiple-copy, watched, resume, and final-card behavior.
- Build provider response fixtures without live network dependence.
- Add quality-profile, fake-label, listing/manifest contradiction, and movie/TV Streaming Link visibility/target fixtures.

**Exit:** Existing behavior is executable and failures are attributable.

### T2 — TV schema and repository in isolation

- Implement `tv-catalog.sqlite` v1 and forward/rollback rehearsal on disposable copies.
- Enforce foreign keys, unique typed identities, binding constraints, and transaction boundaries.
- Add integrity audit and backup/restore proof.

**Exit:** No movie database or route imports the TV store.

### T3 — Metadata hierarchy

- Implement series, seasons, episodes, specials, people, and credits.
- Implement idempotent provider refresh and conflict quarantine.
- Produce year ranges, counts, and status from canonical facts.

**Exit:** Known fixtures refresh twice with identical canonical results.

### T4 — Local ingestion and episode binding

- Implement filesystem/Plex candidate discovery.
- Parse and resolve evidence; send ambiguity to review.
- Probe files, create many-to-many bindings, and support multiple copies.

**Exit:** No torrent support yet; local TV can be cataloged safely from synthetic roots.

### T5 — Read-only API and playback vertical slice

- Add TV list/detail/season endpoints and episode playback/progress.
- Generalize shared playback seams with movie regression coverage.
- Keep navigation feature flag off in production.

**Exit:** One synthetic series can be browsed, resumed, completed, rewatched, and restored after restart without changing movie behavior.

### T6 — Acquisition policy foundation

- Introduce profiles, custom formats, structured decisions, history, blocklist, and deterministic ordering.
- First apply the shared primitives to movie search behind parity tests; retain media-specific rules.
- Keep automatic TV search disabled.
- Reuse the approved canonical quality catalog and run the new decision engine in shadow mode before it controls movie or TV selection.

**Exit:** Candidate decisions are explainable and stable; existing movie choices do not change unless an approved movie-plan policy says so.

### T7 — Manual TV search and safe download

- Extend Prowlarr transport with typed TV queries.
- Support explained series/season/episode results.
- Validate magnet metadata and selected file coverage before resume.
- Link CP acquisition intent to `jobs.json` without duplicating qBittorrent state.

**Exit:** Synthetic/fake-client downloads prove restart, cancellation, stale decision, and malicious manifest handling.

### T8 — Seeding-aware import

- Add journaled per-file plans, hardlink/copy/move policy, probe verification, collisions, partial pack outcomes, and rollback.
- Publish episode availability only after canonical commit.
- Prove crash recovery at every plan checkpoint.

**Exit:** Source, destination, catalog, and qBittorrent state agree after success, failure, restart, and rollback.

### T9 — Monitoring and automation

- Generate bounded missing/cutoff work from monitored episodes.
- Add availability delay, backoff, leases, concurrency, disk reservations, automatic retry, and blocklist rules.
- Default automation off for migrated or newly discovered series until explicitly enabled.

**Exit:** Repeated scheduler runs are idempotent and cannot duplicate a download or import.

### T10 — Desktop frontend integration

- Execute the separate frontend plan.
- Keep TV behind one capability flag until API and UI gates pass together.

**Exit:** Library, Discover, Home, player, and Downloads show the intended TV behavior; movie baselines remain unchanged.

### T11 — Controlled live pilot

This gate requires separate live-operation approval.

- Back up databases and `jobs.json`; record checksums and free space.
- Enable one manually selected series with automation off.
- Test one local import, one single-episode download, then one small pack.
- Observe restart recovery, seeding behavior, playback, and rollback.

**Exit:** Dante reviews the evidence before broader enablement.

## 13. Regression matrix

| Area | Required proof |
|---|---|
| Movie catalog | Counts, identities, multiple copies, filters, cards, file paths, and metadata unchanged. |
| Movie acquisition | Existing manual search, stable-ID enforcement, metadata stop, manifest validation, resume, completion, collision, and recovery stay green. |
| Movie playback | Start, resume, complete, rewatch, close/resume, subtitles/audio selection, and watched state unchanged. |
| TV identity | Series/season/episode IDs stable across refresh and restart; provider conflicts quarantined. |
| TV files | Single, multi-episode, pack, specials, multiple-copy, collision, rename, missing, and replaced-file fixtures. |
| TV progress | Episode-level resume/completion; derived season/series counts; no cross-episode completion. |
| TV Streaming Link | Same enable/label/visibility contract as movies, correct episode target, unreleased suppression, movie template unchanged. |
| Quality profiles | Shared canonical IDs and decisions across movies/TV; pack-specific coverage remains TV-owned. |
| Decisions | Same inputs produce same codes, score, ordering, and explanation. |
| qBittorrent | No duplicated operational state; restart checkpoints; infohash verification; malicious paths; cancellation. |
| Import | Hardlink/copy/move semantics, seeding continuity, disk-full, probe failure, partial pack, rollback. |
| Scheduling | Missing/cutoff eligibility, delay, lease, backoff, duplicate suppression, blocked candidate retry. |
| IPTV | Provider databases, projection, player routes, and UI behavior unchanged. |
| Startup/shutdown | Empty/new TV database, missing provider, schema mismatch, backup failure, and clean shutdown. |
| Frontend | Desktop routes, keyboard/focus, loading/empty/error states, served bundle, and movie visual baselines. |

All automated backend tests use `CP_TEST_MODE=1` and a unique OS-temporary `CP_TEST_ROOT`. Live media, provider, and qBittorrent tests are separate gates and never hidden inside the ordinary suite.

## 14. Performance and operational requirements

- Library list queries must use precomputed/SQL aggregates and avoid one query per series card.
- Season endpoints paginate or load one season at a time; a complete long-running series is not returned as one unbounded payload.
- Provider refreshes use bounded concurrency, caching, rate-limit handling, and backoff.
- Scheduler work uses leases and unique constraints to prevent duplicate acquisition across restarts.
- File probing is cached by path, size, and modification fingerprint.
- Disk reservations include staging and destination requirements and understand when hardlinks consume no duplicate data blocks.
- Integrity audits report orphan episodes, files, bindings, identities, progress rows, and acquisition links without automatically deleting them.

## 15. Rollback design

Before TV is visible, rollback is removal of the feature flag plus restoration of the new TV/acquisition databases; movie state is unaffected.

After a live pilot:

1. disable TV monitoring and new submissions;
2. let or explicitly cancel active qBittorrent work according to recorded job state;
3. restore `tv-catalog.sqlite`, optional `acquisition.sqlite`, and `jobs.json` from the same checkpoint set;
4. reverse only file operations recorded in the import journal and only after path/hash verification;
5. restore the prior served bundle;
6. run movie and TV integrity audits;
7. preserve failed artifacts for diagnosis rather than deleting them automatically.

Rollback never edits movie catalog rows to remove TV because TV was never stored there.

## 16. Stop conditions

Stop the gate immediately if any of these occur:

- a movie response or database row changes without an approved movie-plan reason;
- TV code writes to IPTV or movie-owned tables;
- acquisition SQL and `jobs.json` disagree about which owner controls transfer truth;
- an ambiguous file is auto-bound to an episode;
- a source file is removed before verified publication and rollback checkpoint;
- a pack is marked complete while expected selected files are missing;
- duplicate scheduler work or duplicate qBittorrent submission occurs;
- a schema migration cannot demonstrate forward and restore paths;
- the served bundle does not match the reviewed source;
- the desktop UI cannot explain an acquisition rejection or partial import.

## 17. Definition of complete

The TV backend is complete only when:

- the hierarchy, identities, people, credits, specials, files, multiple copies, and episode bindings are authoritative in `tv-catalog.sqlite`;
- local ingestion and manual review handle representative naming and numbering conflicts;
- episode playback/progress survives restart and preserves all movie behavior;
- manual search, explained decisions, safe preflight, qBittorrent recovery, seeding-aware import, blocklist, and retry work end to end;
- monitoring produces bounded, idempotent missing/cutoff work;
- schema backup, restore, import rollback, and integrity audits are proven;
- the full backend/frontend regression matrix, build, served assets, and visible desktop checks pass;
- the controlled live pilot is separately approved and accepted by Dante.

## 18. Research references

- [Sonarr source repository](https://github.com/Sonarr/Sonarr) — GPL-3.0 source used to inspect responsibilities and current behavior.
- [Sonarr `DownloadDecisionMaker`](https://github.com/Sonarr/Sonarr/blob/main/src/NzbDrone.Core/DecisionEngine/DownloadDecisionMaker.cs) — separation and aggregation of release specifications.
- [Sonarr `DownloadDecisionComparer`](https://github.com/Sonarr/Sonarr/blob/main/src/NzbDrone.Core/DecisionEngine/DownloadDecisionComparer.cs) — deterministic candidate comparison stages.
- [Sonarr `EpisodeFileMovingService`](https://github.com/Sonarr/Sonarr/blob/main/src/NzbDrone.Core/MediaFiles/EpisodeFileMovingService.cs) — episode-file move/copy ownership and transfer behavior.
- Local read-only reference snapshot: `C:\Users\dante\AppData\Local\Temp\codex-sonarr-reference-20260914` at commit `4ff1b780010d3d9ec76a4864dce96b6494e9caea`.

The local snapshot is evidence for this report only. It is outside the CP repository and must not become a build input or runtime dependency.

## 19. Explicitly outside the first release

- mobile/responsive TV redesign;
- calendar, notifications, and remote-control ecosystem;
- Usenet and multiple download clients;
- automatic deletion of replaced episodes;
- global file renaming and library reorganization;
- arbitrary alternate episode orders without provider-backed mappings;
- Movie Lists mixing movies and TV;
- IPTV-to-native-TV writes;
- Sonarr runtime integration or source-code port.

This scope is deliberate. The first release proves one safe, native vertical slice from series identity through episode playback and acquisition before broader automation is added.
