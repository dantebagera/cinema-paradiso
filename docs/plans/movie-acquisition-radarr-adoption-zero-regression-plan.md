# Movie Acquisition: Radarr-Informed Zero-Regression Plan

**Status:** Proposed for review. Documentation only; implementation is not approved.

**Prepared:** 2026-09-14

**Revised:** 2026-09-18 after Dante approved the quality-profile decisions

**Repository:** Cinema Paradiso (CP)

**Implementation worktree:** `C:\Users\dante\.codex\worktrees\tv-acquisition-20260918\cinema paradiso` on branch `codex/native-tv-acquisition`

**Reference snapshots:** CP commit `adfa90a2e984f59585c7635e839f0c594b74b4cc`; Radarr `master` commit `7827e5368947f158ad06f757334f5cde6c406411`

## 1. Executive finding

CP already has a useful movie-download path: it searches configured Prowlarr indexers, presents variants, requires stable TMDB or IMDb identity, validates torrent identity and contents, submits to CP-managed qBittorrent, journals transfer recovery, imports the payload, and hands the selected identity to the movie catalog.

The weakness is not basic downloading. The weakness is acquisition policy and lifecycle depth. CP has narrow quality choices, limited automatic upgrade policy, no general release-decision explanation model, no persistent failed-release blocklist, no automatic replacement after failure, and an import process that moves completed payloads and normally ends seeding. Much of the source-search and followed-release policy also remains in `app.py`.

Radarr is stronger in those areas. CP should adopt its architectural techniques while preserving the parts CP already does better: pre-download torrent inspection, typed provider identity, multiple movie copies in one catalog, measured local-media facts, final-card publication, and integrated playback/curation.

This is an incremental repair of the current authoritative owners. It is not a Radarr dependency, source-code port, full rewrite, or replacement of the movie catalog.

This report is paired with `local-tv-backend-sonarr-adoption-zero-regression-plan.md`, `local-tv-frontend-zero-regression-plan.md`, and `local-tv-project-executive-approval-summary.md`.

## 2. Authorization boundary

Dante authorized this report. That authorization covers documentation only. It does not authorize:

- editing application code or configuration;
- changing `catalog.sqlite`, `jobs.json`, a media library, or qBittorrent;
- building or restarting CP;
- performing a live Prowlarr search or torrent submission;
- staging, committing, pushing, tagging, packaging, or publishing.

Implementation begins only after Dante explicitly approves this named plan or a named subset of its gates.

All implementation under this plan must occur in the dedicated worktree named above. It must not edit, build into, start from, or point tests at the current-use checkout `C:\Users\dante\Desktop\cinema paradiso`, its runtime configuration, databases, qBittorrent profile, or media roots.

## 3. Meaning of zero regression

No engineering plan can prove that a regression is impossible. For this project, zero regression means:

1. Existing behavior is captured as executable contracts before refactoring.
2. Every test uses `CP_TEST_MODE=1`, a unique temporary `CP_TEST_ROOT`, disposable SQLite files, fake provider responses, and synthetic media unless a later live gate is separately approved.
3. Movie SQL schema v11, catalog identities, user data, media files, IPTV stores, configuration, and qBittorrent state are unchanged by pre-cutover gates.
4. Existing Movie Library, Discover, Movie Lists, Home, Maintenance, AI Control, playback, source review, Downloads, IPTV, Settings, startup, and shutdown contracts remain green.
5. Forward migration and exact rollback are rehearsed against a verified catalog snapshot before any live schema change.
6. The production bundle and visible desktop behavior are verified before completion is claimed.
7. Any unexplained data, API, UI, performance, or process difference stops the rollout.

## 4. Confirmed current owners and constraints

The implementation gate must refresh line numbers, but the current ownership map is:

| Responsibility | Current owner | Required disposition |
|---|---|---|
| Prowlarr transport | `services/source_search.py` | Preserve as the only Prowlarr request owner; extend its typed search contract rather than adding route-local HTTP code. |
| Movie search orchestration and variant projection | `app.py` (`_prowlarr_search_movie`, `_torrent_variants_from_prowlarr_results`) | Extract behind a movie acquisition service after parity fixtures exist. |
| Followed-release scheduling and release gate | `app.py` (`_proper_release_from_title`, `_check_followed_releases`) | Move policy into the acquisition decision owner; retain curation ownership of Follow state. |
| Torrent transport, embedded runtime, manifest validation, transfer journal, crash recovery | `services/qbittorrent.py` | Preserve as the exclusive qBittorrent owner. Do not duplicate its lifecycle in SQL. |
| qBittorrent operational persistence | `user-data/qbittorrent/jobs.json` through `QBittorrentJobStore` | Preserve. It is intentionally external to the movie catalog and remains the transport/crash-recovery authority. |
| Canonical movie and physical file state | `services/catalog_store.py`, `services/catalog_repository.py`, `services/canonical_catalog.py` | Preserve schema-v11 authority and final-card publication. |
| Measured file quality | `services/media_file_facts.py` and catalog columns | Use as disk truth when comparing upgrades. Release-name claims remain provisional. |
| Ingestion and publication | `services/library_ingestion.py`, `CatalogRepository.final_card_publication` | Reuse the same targeted path pipeline after an approved import. |
| Movie watched/list/follow state | `services/curation_store.py` and catalog curation tables | Do not create acquisition-owned copies. |
| Playback progress | `services/playback_history.py` | Unchanged by the movie acquisition project. |
| Movie cards and source review | `src/components/SharedMovieCards.jsx`, `SourceReviewDialog.jsx`, `TorrentActions.jsx` | Extend candidate explanation and policy controls without redesigning cards. |

Important baseline facts from source inspection:

- `app.py` is currently 13,306 lines, so new acquisition policy must not be added there.
- Source declares `CATALOG_SCHEMA_VERSION = 11`; the active runtime must be remeasured at Gate M0.
- qBittorrent jobs use an atomic JSON journal and recover interrupted transfer plans.
- Magnet submissions stop after metadata, validate the manifest, and resume only after acceptance.
- Ordinary movie submission requires TMDB or IMDb identity and blocks an owned movie unless it is explicitly submitted as an upgrade.
- Completed downloads are currently paused, moved from staging, and removed from qBittorrent without deleting the moved files.
- CP supports multiple physical copies for one canonical movie. Radarr's movie model selects one active `MovieFileId`; CP must not inherit that limitation.

## 5. Research boundary and licensing

Radarr and Sonarr are GPL-3.0 projects. Their source is used here to understand responsibilities, state transitions, failure cases, and test scenarios. CP implementation must be written independently unless Dante deliberately adopts a compatible licensing strategy.

The engineering record for every adopted behavior must state:

- the observed behavior or architectural technique;
- the CP requirement it satisfies;
- the CP owner implementing it;
- an independently written acceptance test;
- no pasted or translated GPL implementation code.

## 6. Adoption matrix

### 6.1 Adopt for movies

| Radarr capability | Why CP needs it | CP adaptation |
|---|---|---|
| Structured release decisions with explicit rejection reasons | A user and an automated worker must know why a release is unsafe, wrong, unwanted, or inferior. | Create immutable `ReleaseDecision` results. Each rule returns accepted/rejected, stable reason code, user-facing explanation, evidence, and severity. |
| Ordered quality profiles and upgrade cutoff | A global 1080p/4K preference cannot express WEB-DL versus Blu-ray, codec, HDR, language, edition, or when upgrading should stop. | Add CP acquisition profiles with allowed qualities, ordering, desired cutoff, minimum score, and upgrade policy. Existing default quality maps to a generated compatibility profile. |
| Custom-format scoring | Resolution alone is a poor proxy for the desired copy. | Support bounded declarative conditions for source, codec, HDR/DV, audio, language, release group, edition, title tokens, and size. Every matched rule is explainable. |
| Queue, history, and disk-aware upgrade decisions | CP must not grab a release that is inferior to the queued or owned copy. | Evaluate the candidate against accepted catalog file facts, outstanding CP acquisition intent, and qBittorrent jobs. No cross-database SQL join; the service composes read models. |
| Failed-release blocklist and replacement search | Repeating the same broken hash wastes time and can loop. | Record a domain-level failure against movie identity, release hash/title, indexer, failure class, and expiry policy; search again while excluding it. |
| Seeding-aware import | Immediate move/removal prevents normal torrent seeding and is unsuitable for private trackers. | Prefer hardlink from staging to the movie library on the same volume; copy otherwise. Keep qBittorrent seeding until ratio/time policy is met. Move only when seeding is disabled or impossible. |
| Per-file import decisions | A completed payload can contain samples, extras, multiple videos, or an ambiguous main feature. | Inspect every artifact, select the main feature using measured evidence, classify extras, and require review when confidence is insufficient. |
| Proper/repack and edition recognition | A corrected release or director's cut should not be treated as an arbitrary duplicate. | Parse release revision and edition as evidence. Keep edition/copy identity explicit and never overwrite another copy silently. |
| Free-space and size policy | Submission can succeed yet leave staging or destination unable to complete safely. | Check staging capacity before submission and destination capacity before copy import. Hardlink imports account for zero duplicated payload bytes on the same volume. |
| Minimum seeder and indexer-priority policy | Availability and reliability affect whether an automatic grab should proceed. | Add per-indexer minimums and priorities through CP's Prowlarr-facing configuration; manual review can show but deliberately override soft rules. |
| Search delay window | Grabbing the first merely acceptable upload can cause an immediate replacement. | Allow an optional bounded wait for a preferred source. Default remains immediate for manual requests. |
| Manual search explanation | Automation must be inspectable. | Source Review displays accepted/rejected status, rule explanations, score breakdown, coverage, and the final selection reason. |

### 6.2 Adapt rather than copy

| Radarr behavior | CP decision |
|---|---|
| One active file per movie | Reject. CP retains many files per canonical movie and marks preferred playback/quality separately. |
| Broad download-client abstraction | Defer. Embedded qBittorrent remains the only automatic transport in this program. Do not weaken its ownership for hypothetical clients. |
| Provider/title-first movie ownership | Adapt to CP's canonical TMDB/IMDb/Plex identity rules and manual locks. |
| Automatic renaming and folder reorganization | Defer. Import preserves filenames initially. Optional organization needs its own media-mutation approval and rollback plan. |
| Automatic deletion of replaced copies | Reject. A successful upgrade adds a copy. Maintenance can recommend removal; destructive cleanup remains explicit and recoverable. |
| Complete Radarr option surface | Reject. CP exposes a compact profile model that serves observed CP requirements. Complexity must earn its place through a concrete use case. |
| Radarr as a runtime or database authority | Reject. It remains a research reference only. |

### 6.3 Preserve CP behavior that is stronger

1. Stop magnets after metadata and validate before payload download.
2. Verify the selected release's info hash against the retrieved torrent.
3. Reject unsafe paths, dangerous extensions, non-video payloads, low video share, and material advertised-size mismatch.
4. Require stable provider identity before movie submission.
5. Carry exact identity into targeted catalog ingestion.
6. Preserve multiple qualities/editions/copies in one catalog.
7. Use measured media facts after download instead of trusting release text.
8. Publish only final, accepted cards after transaction commit.
9. Keep IPTV completely outside local acquisition and catalog writes.
10. Keep AI Control as a preview/validate/confirm client of the same acquisition API, never a privileged bypass.

## 7. Target architecture

### 7.1 One acquisition application service

```text
Movie card / Follow scan / AI Control
                  |
                  v
        MovieAcquisitionPlanner
                  |
                  v
          ReleaseSearchService -----> ProwlarrClient
                  |
                  v
         ReleaseDecisionEngine
          | reject       | accept/rank
          v              v
       explanation   AcquisitionCoordinator
                              |
                              v
                    QBittorrentManager
                    jobs.json authority
                              |
                              v
                     ArtifactInspector
                              |
                              v
                     ImportDecisionEngine
                              |
                              v
               seeding-aware file transfer
                              |
                              v
                    LibraryIngestionCoordinator
                              |
                              v
                 MovieCatalog final publication
```

Routes, scheduled scans, frontend components, and AI Control call this application service. They do not parse releases, rank candidates, or move files themselves.

### 7.2 Proposed code ownership

Names are recommendations to validate at Gate M1:

- `services/acquisition/models.py`: typed targets, candidates, decisions, profiles, failure and history events.
- `services/acquisition/release_parser.py`: generic release facts with movie/TV parser plugins.
- `services/acquisition/decision_engine.py`: ordered rules and deterministic ranking.
- `services/acquisition/coordinator.py`: requests, selection, submission correlation, retry and cancellation.
- `services/acquisition/import_decisions.py`: artifact inspection and approved import plan.
- `services/acquisition/store.py`: acquisition policy, decision evidence, history, blocklist, and request state.
- `services/movie_acquisition.py`: movie-specific identity, ownership, edition, copy, upgrade, and import rules.
- `services/qbittorrent.py`: unchanged exclusive transport/runtime/journal owner, extended only through explicit capabilities.
- `services/source_search.py`: unchanged exclusive Prowlarr transport owner, extended with typed movie/TV search parameters.

The exact module layout may change if Gate M0 finds a cleaner existing owner. It may not result in two decision engines or two import coordinators.

### 7.3 State ownership

| State | Authority |
|---|---|
| Canonical movie, provider identity, copies, measured facts | Existing movie catalog SQLite |
| Followed movie and list state | Existing curation owner |
| qBittorrent process/torrent/transfer recovery | Existing `jobs.json` journal |
| Acquisition request, profile, candidate decisions, history, blocklist | Proposed `acquisition.sqlite`, owned only by `AcquisitionRepository` |
| UI selection/loading/cache | Browser memory only |

`acquisition.sqlite` must not copy qBittorrent progress, transfer plans, canonical movie metadata, TV metadata, or playback state. It stores the user's intent and the acquisition engine's decisions. A torrent hash and correlation ID link it to `jobs.json`; the qBittorrent journal remains authoritative for transport recovery.

No SQL joins or foreign keys cross the acquisition, movie, TV, or IPTV databases. Application services compose read-only projections.

### 7.4 Typed target contract

Every request uses a typed target:

```json
{
  "media_type": "movie",
  "target_key": "tmdb:movie:603",
  "intent": "acquire|upgrade",
  "profile_id": "default-1080p",
  "manual": true
}
```

Bare numeric provider IDs and title-only automatic requests are invalid. Title/year remain search evidence, not authority.

### 7.5 Release decision contract

A candidate is evaluated in this order:

1. **Identity:** correct movie/provider identity or sufficiently strong verified alias evidence.
2. **Safety:** trusted transport origin, valid hash, acceptable manifest when available.
3. **Eligibility:** released, requested, not blocklisted, not already satisfied by disk/queue.
4. **Profile:** quality, language, source, codec, HDR, audio, edition, size and custom-format rules.
5. **Feasibility:** seeders, free space, compatible import destination.
6. **Ranking:** quality order, custom score, revision, indexer priority, peers, preferred size.

Hard rejection stops automation. Soft rejection can remain visible for manual review with an explicit override. Safety and identity failures are never overridable through the UI.

### 7.6 Acquisition and import states

```text
requested
  -> searching
  -> awaiting_selection | no_candidate
  -> selected
  -> validating_manifest
  -> downloading
  -> import_pending
  -> needs_review | importing
  -> catalog_pending
  -> ready

Any stage may enter failed_retryable, failed_terminal, cancelled, or superseded.
```

The acquisition state describes CP intent. qBittorrent transport state stays in `jobs.json`. State reconciliation is idempotent: repeating a completion event cannot import twice, advance the catalog generation twice, or submit a duplicate torrent.

### 7.7 Seeding-aware import contract

- Staging and library roots must be distinct and must not contain one another.
- Same-volume imports use a hardlink when enabled and verified.
- Cross-volume imports copy to a temporary destination, flush, verify size/hash as required, then atomically publish the final filename.
- A seeding torrent is never moved behind qBittorrent's back.
- The library copy is ingested only after stability and media probing.
- Torrent cleanup occurs only after the configured ratio/time rule, explicit cancellation, or a terminal safety failure.
- Failed copy/import leaves the staging payload and job recoverable.
- Upgrade collision behavior preserves both copies and uses the existing deterministic destination journal.

### 7.8 Authoritative quality catalog

CP currently recognizes more sources than Follow can express, and the definitions are split between `app.py`, `services/maintenance_audit.py`, `services/smart_match.py`, and a smaller Follow allowlist. The amendment replaces those competing dictionaries with one authoritative catalog used by parsing, display, acquisition policy, Source Review, AI Control, Follow, Movie Lists, and TV acquisition.

The catalog identifies a release claim; it does not decide whether the release may be downloaded. It contains stable source IDs, display labels, aliases, families, and parser evidence for:

- cinema captures: CAM, CAMRip, HDCAM, HQCAM, TS, HDTS, telesync, TC, and telecine;
- pre-release material: workprint, SCR, screener, and DVDScr;
- broadcast/disc: HDTV and DVDRip;
- web: HDRip, WEBRip, and WEB-DL;
- Blu-ray: BDRip, Blu-ray encode, Remux, and BD Remux;
- Unknown.

Resolution is a separate dimension: 480p, 576p, 720p, 1080p, 2160p/4K, and Unknown. This permits a profile to allow 1080p WEB-DL while blocking 720p WEB-DL, and ensures that a `1080p HDCAM` is still treated as a cinema capture.

Existing local files are always classified and displayed even when their quality is excluded from acquisition. Download settings cannot hide, delete, or make an existing file unplayable.

### 7.9 Named quality profiles

A profile controls the eligibility of each source/resolution combination with four states:

| State | Meaning |
|---|---|
| `blocked` | Neither automation nor ordinary manual grab may select it. The profile must be edited deliberately. |
| `manual_only` | Visible in Source Review and selectable manually; never selected by Follow, retry, or another automatic worker. |
| `allowed` | Eligible for automatic selection. |
| `preferred` | Eligible and ranked above ordinary allowed combinations. |

Profiles also own cutoff, automatic-upgrade permission, size limits, language/codec/HDR/audio preferences, custom-format score requirements, delay policy, and seeding/import policy. A profile ID is passed to the one acquisition engine; callers may not copy or override its rules privately.

Approved defaults:

1. Existing installations receive a `CP Compatibility` profile that reproduces current behavior. Automatic upgrades remain off.
2. New safe profiles hard-block cinema captures and separately hard-block workprints/screeners by default.
3. Unknown source is manual-only by default.
4. WEBRip, WEB-DL, Blu-ray encode, BDRip, and Remux remain distinct choices; WEB-DL is not classified as a cinema capture.
5. Remux may be configured as manual-only independently of Blu-ray encodes.
6. CP supports multiple named profiles, one global movie default, and a stored profile ID for each followed movie.
7. Deleting a referenced profile requires reassignment; CP never silently falls back.

Settings owns profile editing under `Settings > Downloads > Quality Profiles`. Prowlarr owns discovery transport, not quality policy.

### 7.10 Claimed source, source confidence, and measured facts

CP must not turn a release title into a measured fact. It keeps three concepts separate:

1. **Claimed quality:** what the listing and release name say, such as `1080p Blu-ray`.
2. **Source confidence:** whether that claim is verified enough for automation, plausible, suspicious, or contradictory based on availability timing, trusted indexer/group, listing-versus-manifest agreement, size, history, and other evidence.
3. **Measured facts:** resolution, codec, HDR, bitrate, audio, language, duration, and related properties obtained from the downloaded file.

YTS remains one high-confidence identity and availability signal and may remain a candidate source. It is not a universal gate: absence from YTS cannot reject an otherwise verified WEB-DL or Blu-ray candidate from another trusted source.

The pre-download manifest check compares the Prowlarr listing with internal torrent filenames and structure. `BluRay` outside and `HDCAM` inside is a hard contradiction. When both names repeat the same false claim, CP uses timing, reputation, plausible size, history, and post-download measurements. CP must state the remaining uncertainty because frame dimensions cannot prove Blu-ray provenance.

### 7.11 Two-level Source Review

Source Review keeps CP's bulk workflow and adds Radarr-style evidence:

1. The collapsed movie row shows the recommended release, profile, source/resolution, size, seeders, score, and short selection reason.
2. `Review releases` expands every accepted and rejected candidate for that movie with claimed quality, confidence, indexer, history, score components, and all rejection reasons.
3. Rejected releases remain visible. A user can distinguish no search results from results rejected by policy.
4. `manual_only` candidates can be selected deliberately. `blocked` candidates require a profile edit. Identity and safety failures are never overridable.
5. Bulk selection remains available across multiple movies.

The backend decision result is the only authority. React displays reasons; it does not reimplement profile, safety, or ranking logic.

### 7.12 Shadow-mode cutover

Before the new engine controls any selection, it evaluates the same captured and isolated search results beside the current engine. The current path remains authoritative. Each comparison records accepted/rejected sets, chosen candidate, ordering, reasons, and evaluation time.

An unexplained difference blocks cutover. An intended difference, such as distinct WEB-DL and Remux policy, requires a named approved rule and fixture. Shadow mode performs no submissions, writes no qBittorrent state, and mutates no catalog or media file.

## 8. Compatibility migration

Existing installations must behave identically before a user enables new acquisition policies.

1. Generate one compatibility profile from current settings:
   - current default quality;
   - current trusted indexers;
   - current accepted release-source gate;
   - automatic upgrades off unless already requested explicitly;
   - seeding policy set to the current behavior until the user enables seeding-aware import.
   - current Follow source behavior preserved while the new quality catalog is shadow-evaluated;
   - cinema-capture and screener exclusions represented explicitly rather than hidden in route code.
2. Existing followed releases remain in their current store and retain timestamps/status.
3. Existing `jobs.json` is not migrated or rewritten merely because the new service exists.
4. Existing active/terminal jobs continue through `QBittorrentManager` with byte-for-byte compatible keys.
5. Existing movie catalog schema is not changed until a later gate proves a schema need. Acquisition state belongs outside it.
6. Source Review initially consumes the new decision projection while submitting through the existing API adapter; the old path is removed only after parity.
7. YTS continues as a trusted signal without becoming a mandatory gate for every accepted source.
8. Existing followed movies are assigned `CP Compatibility`; new profile selection requires an explicit save.

No permanent dual-write or fallback implementation is allowed. Compatibility adapters have an explicit removal gate.

## 9. Delivery gates

### Gate M0 — Read-only baseline and behavior oracle

- Confirm checkout, dirty state, app version, source schema version, configured runtime owner, and active process without mutation.
- Inventory every movie acquisition route, caller, setting, state field, job state, and user-visible error.
- Capture deterministic fixtures for Prowlarr results, magnets, torrent files, collisions, cancellation, recovery, identity handoff, Follow scans, upgrades, AI Control, and source review.
- Record full Python/Node/Playwright inventory and current baseline results in an isolated test root.
- Record API payloads and frontend DOM/ARIA contracts for normal movie source review and downloads.

**Stop if:** the baseline is red for a touched surface, runtime ownership is unclear, or current source and served bundle differ.

### Gate M1 — Architecture and contract freeze

- Approve the ownership map, typed target, candidate, decision, history, blocklist, and import contracts.
- Freeze compatibility behavior for current settings.
- Define rule ordering, reason codes, profile schema, correlation IDs, state transitions, and idempotency keys.
- Decide `acquisition.sqlite` schema and prove it does not duplicate `jobs.json` or catalog authority.
- Freeze canonical source IDs, aliases, resolution IDs, four-state eligibility, profile references, cutoff semantics, and claimed/confidence/measured evidence.
- Write GPL-independent behavior notes and source provenance.

No production code changes beyond test fixtures and contract types.

### Gate M2 — Behavior-preserving service extraction

- Route current movie search, variant normalization, submission preparation, and Follow checks through the new movie acquisition service.
- Preserve current results, ordering, settings, errors, payloads, qBittorrent behavior, and UI.
- Add shadow comparison while the old engine remains authoritative; any unexplained decision difference stops the gate.
- Remove the old `app.py` implementations after call-site parity; do not leave forwarding logic indefinitely.

**Acceptance:** golden API/decision fixtures match; all current movie download tests pass forward and reverse; no schema or media change.

### Gate M3 — Structured decisions and Source Review explanation

- Add rule results and deterministic ranking.
- Keep automatic behavior on compatibility policy.
- Display accepted/rejected reasons and score components in Source Review.
- Preserve CP's bulk review while adding expandable per-release results, history, confidence, and policy state.
- Keep blocked, manual-only, allowed, and preferred releases visually distinct.
- Ensure manual overrides cannot bypass safety or identity rules.

**Acceptance:** every result has a stable decision; no existing acceptable release becomes rejected without an approved policy reason.

### Gate M4 — Seeding-aware artifact import

- Add artifact inspection and per-file import decisions.
- Add verified hardlink/copy import and seed-ratio/time policy.
- Preserve current move behavior behind the compatibility profile until Dante enables the new policy.
- Add interrupted hardlink/copy, locked file, out-of-space, collision, restart, and cleanup tests.

**Stop if:** a source payload can be deleted before catalog readiness, qBittorrent loses a recoverable job, or an import can publish twice.

### Gate M5 — Profiles and upgrades

- Add compact quality profiles and custom-format scoring.
- Compare candidates against measured disk facts and queued acquisitions.
- Recognize editions, proper/repack revisions, language, codec, source, HDR and audio evidence.
- Add automatic upgrade monitoring only after non-destructive copy retention is proven.

### Gate M6 — Failure recovery and monitoring

- Add durable release history and blocklist.
- Add bounded retry with backoff and a maximum attempt policy.
- Followed movies may optionally auto-grab only after explicit per-profile/user enablement.
- Never auto-grab an unverified title-only match.

### Gate M7 — Full isolated qualification

- Run complete Python, Node and desktop Playwright suites in isolated roots.
- Run production frontend build.
- Run forward/reverse critical repetitions for source search, selection, submission, import, crash recovery, final-card publication, playback and curation.
- Exercise concurrency, restart, unavailable roots, Prowlarr timeout, qBittorrent restart, hash mismatch, disk exhaustion and blocklist loops.
- Compare performance against Gate M0.

### Gate M8 — Served isolated runtime acceptance

- Serve the built bundle on a non-production port using disposable configuration, catalog, acquisition store, qBittorrent profile and synthetic media roots.
- Verify visible Source Review reasons, job progress, failure recovery, successful import, continued seeding and final card publication.
- Verify Library/Discover/Movie Lists/Home/Maintenance/AI Control/IPTV/Downloads/Settings state preservation and zero console errors.

### Gate M9 — Separately approved live rollout

This gate is not authorized by approval of implementation Gates M0-M8.

Before live use:

- create and verify application-wide backups and a manifest;
- rehearse any new store/schema creation and rollback from that backup;
- confirm one CP backend and one embedded qBittorrent owner;
- verify the served `dist` hashes match qualified source;
- use one explicitly selected movie and release;
- stop on any unrelated catalog generation, provider call, file mutation, duplicate, missing job, playback regression, or UI error;
- retain a one-action rollback that restores prior source/config/store state without touching unrelated media.

Git commit, push, tag, package and release publication remain separately authorized actions.

## 10. Regression matrix

| Protected behavior | Required proof |
|---|---|
| Existing movie catalog schema and rows | Logical table digests, counts, integrity check, foreign-key check, generation stability and second-open idempotence. |
| Canonical identity and manual locks | TMDB/IMDb/Plex/manual identity fixtures; title-only automatic rejection; exact post-download identity handoff. |
| Multiple copies and duplicates | Existing copy retained; upgrade adds a copy; Maintenance rankings unchanged unless new measured facts justify a difference. |
| Torrent safety | Hash mismatch, path traversal, dangerous payload, no-video, low-video-share and size-mismatch cases remain blocked before resume. |
| Current download lifecycle | Submission, already-exists handling, cancellation, missing torrent grace, collision, interrupted transfer and handoff replay remain idempotent. |
| Followed releases | Release-date gates, trusted indexers, RSS fast path, provider identity checks, retry times and ownership reconciliation retain compatibility defaults. |
| Source Review | All existing variants and qualities remain reachable; new rejection explanations do not silently remove manual choices. |
| Quality catalog | One canonical source/alias dictionary; resolution remains separate; no route-specific allowlist survives. |
| Profiles | Compatibility migration is idempotent; blocked/manual/allowed/preferred and cutoff behavior are deterministic. |
| Fake quality | Listing/manifest contradiction, impossible release timing, implausible size, renamed CAM/TS, claimed/measured mismatch, and unknown-source fixtures. |
| Shadow mode | Old path remains authoritative; differences are recorded without submission or catalog mutation. |
| Final-card publication | No placeholder/partial card; one generation/event after commit; rollback leaves no visible movie. |
| Playback and Watched | Resume, restart, completion, auto-Watched and rewatch behavior unchanged. |
| Stateful frontend navigation | Filters, paging, searches, selections, expansion, focus and scroll survive navigation exactly as before. |
| IPTV isolation | No local acquisition code imports, opens, writes or projects an IPTV provider database. |
| AI Control safety | Preview/confirmation remains mandatory and executes through the same validated acquisition API. |

## 11. Performance budgets

Gate M0 records current values. Unless an approved feature necessarily adds work:

- normal Library and Discover reads must remain within 10% of baseline median and 20% of baseline p95;
- no provider calls occur for ordinary owned-card rendering;
- candidate evaluation is linear in returned candidates and performs no per-card provider request;
- one Follow scan preserves current bounded parallelism and deadline behavior;
- idle acquisition monitoring performs no full movie-root scan;
- startup performs no automatic search and no rewrite of unchanged acquisition/catalog state;
- a repeated identical qBittorrent event produces no additional import, generation bump, or acquisition history duplication.

## 12. Rollback

- Gates M2-M4 must remain reversible by restoring code and the disposable acquisition store; they must not require movie catalog rollback.
- `acquisition.sqlite` is introduced through a candidate file and active pointer or equivalent replaceable boundary. Creation failure leaves the feature disabled and current movie behavior intact.
- qBittorrent compatibility adapters are removed only after the new path has passed forward and reverse recovery tests.
- A failed seeding-aware import leaves the original staging payload untouched and recoverable.
- Any live schema/config transition requires a verified application backup and restore rehearsal.
- Rollback never deletes a media file merely to restore software state.

## 13. Global stop conditions

Stop implementation or rollout if:

- two components claim qBittorrent lifecycle or transfer ownership;
- movie catalog and acquisition store disagree about canonical identity;
- current accepted releases change without an approved compatibility exception;
- a hardlink/copy cannot be distinguished and recovered safely;
- seeding cleanup can delete the only payload copy;
- retry can resubmit a failed/blocklisted hash indefinitely;
- title-only evidence can trigger an automatic grab;
- a movie copy is overwritten or deleted silently;
- IPTV code/data enters the local acquisition path;
- the full existing suite is red on a touched surface;
- performance exceeds the agreed Gate M0 budget;
- production state changes before Gate M9 approval.

## 14. Definition of complete

The movie acquisition project is complete only when:

- current movie behavior passes the frozen parity oracle;
- one authoritative acquisition service owns search-to-import policy;
- `app.py` no longer owns release policy for migrated routes;
- profiles, decisions, explanations, upgrades, blocklist and recovery work through the same engine;
- one quality catalog and named profile model serve every movie acquisition caller;
- Source Review preserves bulk selection and exposes every candidate, confidence signal, score, and rejection reason;
- seeding-aware import is restart-safe and does not overwrite existing copies;
- qBittorrent `jobs.json` remains the sole transport/crash journal;
- movie catalog, playback, curation, IPTV and frontend state contracts pass unchanged;
- the production bundle and an isolated served desktop workflow are verified;
- no compatibility shim or dual-write path remains without a named removal dependency;
- live rollout, Git publication and release remain clearly separated from isolated completion.

## 15. Research references

- [Radarr source repository](https://github.com/Radarr/Radarr) — GPL-3.0 source used to inspect domain boundaries and current behavior.
- [Servarr Radarr Quick Start Guide](https://github.com/Servarr/Wiki/blob/master/radarr/quick-start-guide.md) — user-facing monitoring, quality-profile, and upgrade concepts.
- Local read-only reference snapshot: `C:\Users\dante\AppData\Local\Temp\codex-radarr-reference-20260914` at commit `7827e5368947f158ad06f757334f5cde6c406411`.

The local snapshot is evidence for this report only. It is outside the CP repository and must not become a build input or runtime dependency.

## 16. Recommended implementation relationship to TV

The TV project should reuse the acquisition models, decision engine, coordinator, failure history and qBittorrent capability layer created here. It must provide its own episode/season target planning, TV release parsing, coverage scoring and import mappings.

If TV is approved before the full movie improvement program, implement only the behavior-preserving shared extraction needed by TV, guarded by the complete movie parity suite. Do not smuggle automatic movie policy changes into the TV project.
