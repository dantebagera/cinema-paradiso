# Native TV and acquisition: isolated implementation evidence

Date: 2026-09-18. Assigned checkout: `C:\Users\dante\.codex\worktrees\0870\cinema paradiso`.
Starting HEAD: `adfa90a2e984f59585c7635e839f0c594b74b4cc` (detached). Changes remain uncommitted.

## Scope and protection

Dante approved continuation through the isolated implementation and verification scope without further approval stops. Production was not opened, restarted, built, or changed. No real provider search, real torrent submission, media import, publication, commit, push, package, or release was performed. Phase 9 remains outside this work.

The four revised plans were copied verbatim from the planning checkout before implementation. Their historical approval wording is preserved. The assigned checkout supersedes the planning checkout location for this execution.

## Delivered owners

- `tv_catalog_store.py` and `tv_catalog_repository.py`: separate WAL SQLite TV authority, typed provider IDs, series/seasons/episodes, series and guest credits, multiple versions and many-to-many bindings, episode progress with stale-session rejection, metadata reconciliation, backup/restore. Movie schema is unchanged.
- `tv_metadata.py`, `plex_tv.py`, `tv_filename_parser.py`, `tv_ingestion.py`: cached and bounded TV metadata refresh with rate-limit backoff, exact TMDB-identified Plex discovery with bounded paging, exact numbering/daily/specials/multi-episode parsing, measured local files, and explicit review for ambiguity. Provider numbering conflicts retain accepted files and progress.
- `tv_read_model.py`, `tv_playback.py`, `tv_routes.py`: paginated TV reads, the approved TV filters and sorts including monitoring state, truthful local quality/language aggregates, episode Start/Resume/Play next without skipping missing episodes, existing native-player/history adapters, independent watched state, TV configuration, and catalog/acquisition integrity audit endpoints.
- Shared existing card and Streaming Link owners: Library/Discover Movies–TV switches with isolated state and scroll positions, dedicated `/tv/series/<id>` route, seasons/specials, episode versions/actions, Home Continue Watching, TV Downloads, manual local/Plex import review, monitoring controls, exact released-episode streaming, and Settings controls for the capability and roots. TV is disabled by default.
- `quality_catalog.py`, `acquisition_profiles.py`, `acquisition_decision.py`, `acquisition_store.py`: canonical source definitions, independent resolution, four eligibility states, profiles/cutoffs/formats, deterministic reasons and ordering, expiring review tokens, idempotent intents, overlapping-episode claims, history/blocklist, leases and reservations.
- `movie_acquisition.py`: extracted existing movie orchestration. Existing movie selection remains authoritative; new profile decisions are explicitly shadow comparisons. The source-review UI exposes that distinction. Profile edits do not silently change existing movie automatic selection, and newly followed movies retain the profile ID selected at follow time (the current default when none is supplied).
- `tv_acquisition.py`, existing `QBittorrentManager`, and `verified_import.py`: typed manifest validation before magnet resume, hash correlation, measured completed media, journaled hardlink/copy publication, per-file partial-pack outcomes, collision preservation, crash recovery without a remaining torrent, bounded transient retries, configurable seeding cleanup that removes torrents without deleting source files, cancellation/retry/block/rollback. All operational paths stay in `jobs.json`.
- `tv_monitoring.py`: explicit opt-in hierarchical monitoring, future/missing/cutoff selection, bounded work, backoff, leases, queue suppression, measured-upgrade comparison, and pending-job disk budgeting.
- `tv_checkpoint.py`: coordinated TV/acquisition/jobs checkpoint and checksum-verified repeatable offline restore. It excludes movie/IPTV stores. Restore requires a stopped application.

## Verification

| Check | Evidence |
|---|---|
| Cold catalog defect reproduced and repaired | `phase-0/cold-catalog-result.json`, `phase-0/cold-catalog-fixed.json`; factory now synchronizes first creation without weakening the process writer lease |
| Repaired pre-TV full baseline | 1,254 Python tests passed; `phase-0/python-fixed.log` |
| Frontend utility regression | 95 tests passed; `node-integrated.log` |
| Existing desktop regression | 63 passed; `playwright-movies.log` (TV tests deliberately skipped on movie-only fixture) |
| TV desktop flows | 5 passed, including Streaming Link Escape/focus restoration; `playwright-tv.log` |
| Movie Streaming Link regression | Existing release-watcher test extended to open/close the movie iframe and verify focus; passed; `playwright-movie-stream.log` |
| Final focused TV/acquisition/recovery/profile/curation checks | **66 passed**; an additional **29** cold-start, safety, decision, and qBittorrent UI checks passed |
| Frontend utility regression | **95 passed** on the final source |
| Production bundle | Vite production build passed after the final Downloads visibility fix |
| Served desktop TV flows | **5 passed in 6.8 seconds** against the final built bundle, including an assertion that the qBittorrent frame is absent from the TV tab |
| Visible desktop review | Final Library, series, release-review, and Downloads screenshots inspected; the discovered qBittorrent-frame leak was fixed and re-captured |
| Full backend final serial qualification | **1,299 passed in 234.009 seconds**. Original timing thresholds retained. |

Desktop screenshots: `library.png`, `series-final.png`, `release-review.png`, `downloads.png`. The fixture intentionally uses synthetic metadata/media and a no-op OS player; it does not claim real video decoding or real-client/provider acceptance.

Intermediate failures were investigated rather than hidden. The final run initially found one stale exact-dictionary assertion after the integrity audit gained the required orphan counters; the expanded contract passed its focused rerun and then the clean 1,299-test qualification. Visual inspection also caught the qBittorrent iframe still rendering under TV Downloads because component CSS overrode the HTML `hidden` attribute; the iframe now unmounts on the TV tab and the browser test asserts its absence. Two test-harness `ResourceWarning` messages for unclosed file handles remain non-failing.

## Operational limits and rollout notes

- TV capability remains off by default; monitoring remains off for newly discovered series. This is isolated qualification, not live acceptance or general enablement.
- Movie profile decisions remain in shadow mode. Compatibility selection and current movie move policy are retained; cutover requires parity evidence and the separately controlled rollout. This temporary boundary is deliberate, visible in Settings/Source Review, and removable only after movie selection parity and rollout acceptance.
- Ambiguous absolute/alternate numbering requires an explicit mapping; no heuristic title-only binding or automatic numbering rewrite occurs.
- Missing provider IDs, unverified source evidence, unavailable media probes, unsafe paths, mismatched labels, changed profile versions, and incomplete target coverage stop automation with a reason.
- Preserving imports keep seeding payloads and old library versions. A configured ratio/time policy can pause and remove the torrent after verified publication while retaining its files. Physical rollback removes only this journal's verified newly published files after checking retained source hashes.
- An ambiguous or unrelated manifest is held before download resumes. After a validated pack completes, independently verified files can publish while failed files remain in staging and are shown as a partial outcome with per-file reasons.
- Plex discovery accepts only an exact typed TMDB series identity, uses typed episode IDs where available, and still enforces configured TV roots during ingestion. Live Plex/provider and real-player operation are not demonstrated by synthetic fixtures.
- Checkpoint restore is an offline maintenance operation; an interrupted restore is repeated from the intact checkpoint before the application is restarted.
- Movie Lists remains movie-only; IPTV ownership is unchanged; no mobile UI was built or tested.

Both disposable listeners (5117 and 5127) were stopped after final served verification. Production listeners were not stopped. No new approval prompt is needed to finish the authorized isolated verification.
