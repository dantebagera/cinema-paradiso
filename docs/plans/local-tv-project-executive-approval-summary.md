# Local TV Project: Executive Approval Summary

**Decision status:** Awaiting Dante's approval

**Prepared:** 2026-09-14

**Revised:** 2026-09-18

**Approval documents:**

- `movie-acquisition-radarr-adoption-zero-regression-plan.md`
- `local-tv-backend-sonarr-adoption-zero-regression-plan.md`
- `local-tv-frontend-zero-regression-plan.md`

## 1. Decision requested

Approve CP's native local-TV project as a staged implementation, together with the shared acquisition foundation needed to support it safely. Approval authorizes implementation and automated verification of the gates described below. It does not authorize live catalog/media mutation, live torrent downloads, runtime restart, Git commit/push, packaging, release publication, or general rollout; those remain separate checkpoints.

“Zero regression” is an engineering gate, not a claim that defects are impossible. It means current movie behavior is captured first, TV remains isolated until proven, every shared seam has regression coverage, and any unexplained difference stops the rollout.

The movie acquisition improvements are a related plan, not a prerequisite for every TV screen. Shared acquisition primitives may be introduced only where movie parity is proven first. Movie behavior must not be silently changed to make TV easier.

## 2. Isolation already established

The project now has a dedicated worktree:

- **Path:** `C:\Users\dante\.codex\worktrees\tv-acquisition-20260918\cinema paradiso`
- **Branch:** `codex/native-tv-acquisition`
- **Starting commit:** `adfa90a2e984f59585c7635e839f0c594b74b4cc`

Implementation, tests, builds, and generated artifacts for this project stay there. They must use disposable configuration, databases, qBittorrent profiles, ports, and synthetic media roots. The current-use checkout `C:\Users\dante\Desktop\cinema paradiso`, its runtime, databases, qBittorrent profile, and media libraries remain untouched unless Dante later approves a controlled live pilot.

## 3. Outcome

CP will gain native local-TV support from discovery through playback:

- TV browsing in Library and Discover using standard CP information cards;
- a dedicated series page with seasons, episodes, cast, availability, progress, and versions;
- episode-level playback, resume, completion, and Continue Watching;
- safe cataloging of existing local/Plex TV files;
- manual series, season, episode, and pack search through Prowlarr;
- CP-managed qBittorrent downloads with manifest validation and restart recovery;
- seeding-aware, per-file import with review for ambiguous mappings;
- monitoring of future, missing, and cutoff-unmet episodes after the manual path is proven;
- explainable profiles, candidate decisions, history, blocklist, and retry.
- the existing configurable Streaming Link experience for TV series and episodes under the same rules as movies.

Sonarr and Radarr are design references only. CP remains the runtime owner and independently implements the approved behavior.

## 4. Why this architecture

TV differs structurally from movies. Treating a series as a movie with episodes attached would corrupt responsibilities throughout cataloging, search, playback, and watched state.

The approved architecture therefore uses:

1. **`catalog.sqlite` unchanged as movie authority.** Existing movie identities, files, cards, playback, curation, and acquisition behavior remain protected.
2. **New `tv-catalog.sqlite` as native TV authority.** It stores series, seasons, episodes, people, credits, physical files, episode-file bindings, and episode progress.
3. **Existing `jobs.json` as qBittorrent operational authority.** Percentages, paths, transfer plans, and crash recovery do not move into SQL.
4. **Optional `acquisition.sqlite` as CP policy/history authority.** It stores monitoring, profiles, decisions, blocklist, scheduler leases, and events without copying qBittorrent transfer state.
5. **Application composition rather than database joins.** Movie and TV data can appear together on Home or a person page while their stores remain independently recoverable.
6. **Many-to-many episode-file binding.** This supports multi-episode files and multiple physical versions instead of pretending every episode maps to exactly one file.

## 5. Features adopted from Sonarr and Radarr

### Native TV, informed mainly by Sonarr

| Adopt | Business value |
|---|---|
| Hierarchical series/season/episode monitoring | Users can follow future episodes, fill gaps, or choose specific seasons without uncontrolled downloads. |
| Episode and pack parsing | CP can understand single episodes, multi-episode releases, season packs, specials, daily, and absolute numbering. |
| Missing/cutoff search | The library can complete itself over time and upgrade below-target episodes. |
| Per-file manual/automatic import | Samples, extras, wrong-season files, and ambiguous numbering do not poison the catalog. |
| Quality profiles and custom formats | Selection accounts for resolution, source, codec, HDR, audio, language, group, size, and user preferences. |
| Decision explanations | Every accepted or rejected result has a visible reason. |
| History, blocklist, and retry | CP avoids repeatedly choosing a failed or corrupt release. |
| Seeding-aware import | Hardlink/copy keeps torrents seeding and avoids unsafe early moves. |
| Delay, free-space, and queue awareness | Automation waits for better releases and avoids filling disks or duplicating work. |

### Existing movies, informed mainly by Radarr

| Adopt | Business value |
|---|---|
| Structured decision engine | Manual and followed-release choices use the same explainable rules. |
| Profiles, cutoffs, and scored formats | Movie upgrades become intentional rather than a narrow quality check. |
| Persistent history/blocklist/retry | Failed candidates are remembered and safe alternatives can be selected. |
| Seeding-aware verified import | CP no longer has to end seeding merely to publish a movie. |
| Proper/repack/edition awareness | Replacements can be judged beyond resolution alone. |
| Disk, seeder, age, and indexer policy | Candidate ordering becomes safer and deterministic. |

CP retains its stronger movie behavior: torrent metadata is inspected before resume, stable TMDB/IMDb identity is required, multiple physical copies can coexist, measured file facts become disk truth, and final-card publication connects acquisition directly to the usable library.

### Approved quality and Source Review decisions

1. One authoritative source dictionary serves movies and TV; resolution remains a separate dimension.
2. Named profiles assign each source/resolution combination `Blocked`, `Manual only`, `Allowed`, or `Preferred` and define a cutoff.
3. Existing installations receive a behavior-compatible profile; automatic upgrades remain off initially.
4. Cinema captures and pre-release screeners are separate default hard blocks.
5. YTS remains a high-confidence movie identity/availability signal and candidate source, not a mandatory gate for other verified sources.
6. Multiple named profiles are supported; one movie default is selected and followed items store a profile ID.
7. Source Review retains CP's bulk workflow and adds an expandable table containing every accepted/rejected release, confidence, score, history, and reason.
8. Claimed source, source confidence, and measured file facts remain distinct.
9. The new engine runs in non-mutating shadow mode before controlling selection.

## 6. Product experience approved

### Library and Discover

- Add `Movies | TV Shows` switches with independent state.
- Use full CP movie-style cards, not poster-only tiles.
- TV cards show title, `2017–2020` or `2018–Present`, genres, rating/votes, normalized status, season count, episode count, and context-specific availability/progress.
- Quality/language appear only when local file aggregates support the claim; mixed libraries say `Mixed`.
- Clicking a card opens the dedicated series page.

### Series page

- Backdrop/poster, overview, status, year range, genres, rating, creators, and cast.
- Primary Resume/Start/Play next action.
- Season selector, with season 0 labeled Specials.
- Episode rows with code/title/date/runtime/overview, availability, progress, and play/search actions.
- Multiple versions behind the episode action.
- Monitoring and acquisition controls use backend decisions and explanations.
- The Streaming button remains available. Series-level Streaming resolves the current episode; episode rows stream the selected released episode through a TV URL template and the existing embedded Streaming Link owner.

### Home and Downloads

- Continue Watching shows one item per series with episode code/title and distinguishes Resume from Play next.
- Downloads identifies series/season/episode/pack scope and displays partial import, retry, rejection, or manual-review reasons.
- Movie behavior and labels remain unchanged.

The approved UI scope is desktop only. Movie Lists remains movie-only. IPTV remains separate.

## 7. Delivery sequence and approval gates

Approval authorizes the following implementation sequence only in the dedicated project worktree, with a stop-and-report requirement whenever a gate fails.

| Phase | Deliverable | Exit evidence |
|---|---|---|
| 0. Baseline | Current owners, runtime/schema, dirty state, movie APIs/UI/download/playback, and served hashes captured. | Reviewable baseline; no behavior change. |
| 1. Safety harness | Characterization tests plus synthetic episode, pack, numbering, quality-profile, fake-label, Streaming Link, manifest, collision, and recovery fixtures. | Current movie suite and new fixtures green. |
| 2. TV catalog core | Isolated schema, repository, migrations, backup/restore, identities, hierarchy, people/credits, files/bindings. | Disposable migration and integrity proof; movie DB untouched. |
| 3. Existing-library vertical slice | Metadata refresh, local/Plex ingestion, ambiguity review, TV read API, episode playback/progress. | Synthetic/local fixture series works across restart. |
| 4. Frontend vertical slice | TV cards, series page, Library/Discover switch, Home/player integration behind a flag. | Desktop fixture flow accepted; movie UI baseline green. |
| 5. Acquisition decisions | Canonical quality catalog, profiles, formats, confidence, shadow comparisons, decision codes, ordering, history, blocklist, retry, typed Prowlarr search. | Same inputs give deterministic explained outcomes; old path remains authoritative until parity. |
| 6. Manual download/import | Safe preflight, qBittorrent correlation, per-file mapping, hardlink/copy/move journal, verification/rollback. | Fake-client success/failure/restart matrix green. |
| 7. Monitoring automation | Missing/cutoff work, delay, leases, backoff, disk reservations, duplicate suppression. | Repeated runs are bounded and idempotent. |
| 8. Integrated desktop proof | Focused/full backend and frontend tests, build, Playwright, served hashes, visible UI, console/network inspection. | Reviewed source equals served behavior; movies unchanged. |
| 9. Live pilot | One approved series, then one episode and one small pack with backups and rollback rehearsal. | Requires a new explicit approval before execution. |

Implementation may stop after Phase 4 to deliver local catalog/playback before download automation. It must not skip earlier safety gates to reach acquisition faster.

## 8. Non-negotiable protection rules

1. Do not put TV rows in the movie catalog.
2. Do not duplicate qBittorrent transfer/recovery state in SQL.
3. Do not let IPTV write native TV or movie stores.
4. Do not put release parsing, episode mapping, or candidate selection into HTTP routes or React components.
5. Do not auto-bind ambiguous files.
6. Do not remove or overwrite a source file before verified publication and a recoverable checkpoint.
7. Do not auto-delete an old movie or episode version in the first release.
8. Do not enable monitoring automatically for discovered/migrated series.
9. Do not change existing movie API shapes or behavior without the movie plan's explicit gate and parity evidence.
10. Do not claim frontend completion from source tests alone; verify the production build, served assets, and visible desktop behavior.
11. Do not copy Sonarr/Radarr GPL source into CP without a separately approved licensing decision.
12. Any unexplained movie, IPTV, catalog, download, playback, or startup difference stops the rollout.
13. Do not run this worktree against the current-use configuration, databases, qBittorrent profile, media roots, or production port.
14. Do not duplicate the movie Streaming Link owner; extend it with a backward-compatible TV template and typed episode target.

## 9. What this approval does not include

- live downloads or live catalog/media changes;
- restart of the user's running CP instance;
- commits, pushes, tags, packages, or releases;
- mobile/responsive TV design;
- Usenet, multiple download clients, calendar, or notifications;
- automatic deletion or broad renaming/organization;
- Movie Lists support for TV;
- IPTV/native-TV data merging;
- a runtime dependency on Sonarr or Radarr.

These require later scope decisions where applicable.

## 10. Principal risks and controls

| Risk | Control |
|---|---|
| TV work breaks movies through shared UI/playback/download code | Characterize movies first; typed adapters; feature flag; movie regression suite at every shared seam. |
| Wrong episode mapping | Multi-evidence resolver, confidence/reasons, provider-order mappings, manual review, transactional publication. |
| Pack import loses data or seeding | Journaled hardlink/copy/move plan, free-space reservation, post-copy verification, source retention, crash-recovery tests. |
| Duplicate downloads after restart | Scheduler leases, unique work keys, infohash/correlation checks, idempotent mutation endpoints. |
| Database rollback crosses inconsistent points | Checkpoint TV/acquisition DBs and `jobs.json` together; movie DB remains independent. |
| UI misrepresents series facts | Backend read models own counts/status/progress; mixed quality/language shown honestly; explicit empty/unknown states. |
| Scope grows into a Sonarr clone before a usable result | Ship gated vertical slices; defer clients, calendar, notifications, rename system, deletion, and mobile. |
| GPL contamination | Behavioral study with independent CP design and tests; no source copying without a licensing decision. |
| Fake source labels | Separate claim/confidence/measurement, trusted evidence, listing-versus-manifest comparison, post-download probes, and visible uncertainty. |
| New work reaches current CP runtime | Dedicated branch/worktree plus disposable roots, ports, databases, and qBittorrent profile; live pilot remains separately approved. |

## 11. Acceptance criteria

The project can be called implemented only when:

- a series with seasons, specials, episodes, people, credits, multiple files, and progress survives refresh and restart;
- local ingestion handles single/multi-episode files and sends ambiguous mappings to review;
- Library, Discover, the series page, Home, player, and Downloads work in the served desktop build;
- episode Start/Resume/Complete/Rewatch and Play next are correct;
- TV Streaming Link follows the movie visibility/player rules, resolves the correct episode, leaves movie streaming unchanged, and does not mark watched merely by opening;
- a manually approved single episode and pack can be searched, validated, downloaded, imported, recovered, and rolled back in tests;
- monitoring is deterministic, bounded, explainable, and duplicate-safe;
- movie catalog, acquisition, cards, filters, curation, playback, multiple copies, IPTV, startup, and shutdown regressions pass;
- database backup/restore, import rollback, and qBittorrent crash recovery are proven;
- the separately authorized live pilot passes and Dante accepts the result.

## 12. Approval wording

If Dante approves the whole proposal, a clear authorization is:

> Approve the Local TV Project Executive Approval Summary revised 2026-09-18, Phases 0 through 8, exclusively in worktree `C:\Users\dante\.codex\worktrees\tv-acquisition-20260918\cinema paradiso` on branch `codex/native-tv-acquisition`. Documentation, implementation, automated tests, disposable fixtures, isolated runtime verification, and production build verification are authorized. Phase 9 live operations, the current-use checkout/runtime, runtime restart, Git commit/push, packaging, and release remain unapproved.

Dante may instead approve named phases. Any materially expanded scope returns for approval with its effect on architecture, regression risk, and schedule stated explicitly.
