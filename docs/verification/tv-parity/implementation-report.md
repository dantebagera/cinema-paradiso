# TV parity and episode download workflow

Workspace: `C:\Users\dante\.codex\worktrees\0870\cinema paradiso`.

Implementation follows `docs/plans/tv-parity-and-download-workflow-plan.md` and is ready for Dante's testing. Verification is complete with one unresolved, previously observed IPTV timing failure in the latest full backend run, detailed below.

## What changed

TV Library and Discover now use the movie search field shell, shared advanced-query builder, shared cards and shared pagination. The search field spans the available row, with the criterion button inside it. The familiar genre, original language, country, year, rating, ordering and scope-specific ownership/vote/resolution/source controls are visible. Extra TV status, monitoring and local-audio filters remain available. Changing modes retains the title draft; clearing filters and returning from details preserve the expected navigation behavior.

Cards resolve TMDB genre names and original-language labels without waiting for local downloads. Provider episode totals are separate from available local episodes. Detail pages show the full poster at its natural ratio and ordered cast with portraits and roles before the episode list. Known metadata survives unavailable label requests. Missing detail data remains retryable.

Download season and episode actions are available in unsaved previews. Add to library is optional tracking; it does not enable monitoring or submit a download. Search and release review create no tracked show. Confirming a download saves the selected season's metadata automatically. Other seasons remain browsable as previews and are saved when needed, avoiding a whole-series fetch as a download prerequisite.

Release review presents selectable releases first, coverage, quality/source claims, size, seeders, source and the download action. Diagnostics are expandable. Title, year, aliases and supplied provider IDs contribute identity evidence; same-title ambiguity needs a specific identity choice. Wrong years, conflicting IDs and unrelated series stay blocked. Trusted Prowlarr links are resolved before final eligibility, including listings with no hash. A resolved-hash mismatch is rejected.

The existing acquisition owner handles single episodes, selected episodes, missing episodes and seasons. Recommendations combine nonoverlapping releases using the quality policy and useful coverage. Season searches have bounded episode fallbacks; failures preserve completed choices. Gaps require the explicit Download available action. Durable batch outcomes and per-item keys prevent resubmitting completed members after partial failure or restart.

qBittorrent remains the transfer owner. Magnets acquire metadata before payload resume; torrent files start stopped. The manifest selects intended files and disables unrelated separate episode files before resume. Combined files containing extras need an explicit extras choice. Existing copies are retained, imports use measured facts, and manual replacements require the upgrade choice. Existing explicitly configured automatic policy behavior is preserved; this work enables no monitoring or automatic upgrades.

An interrupted torrent-file submission can recover the client's accepted transfer without a second add. A torrent already present outside the acquisition is rejected; retrying that rejected intent cannot take ownership of it. Permanent validation failures release episode reservations and require a new review.

## Acceptance evidence

| Plan scenario | Evidence |
| --- | --- |
| Movie-style search, visible filters, reset and title-mode transitions | Desktop browser assertions and `discover-*.png`, `library-filters.png`; shared movie regression suite. |
| Top/bottom pagination | Both navigators change one page state in the browser test; episode pagination uses the same component. |
| Person/keyword/runtime combinations; filtered pagination | Backend predicates run before finite-set paging. Remote continuation retains pending metadata, avoids fabricated totals, and continues through empty provider pages. |
| Dark Matter 2024 preview | Browser checks at 1920×1080, 1920×720 and 1366×768 verify full poster ratio, cast, metadata, season search and unchanged catalog count after closing. |
| Dark Matter 2015 versus 2024; Daredevil versus Born Again | Identity tests reject contradictory years and unrelated titles, preserve aliases, and expose yearless ambiguity for review. Born Again browser check finds Charlie Cox and enabled preview download actions. |
| Simpsons season 1 and multi-episode downloads | Browser test resolves hashless fixture links and queues two selected episodes exactly once with monitoring unchanged. Wrong-season results fail coverage. |
| Packs, partial coverage and overlap | Backend tests cover individual combinations, overlapping rejection, partial confirmation, file selection and retained source files. |
| Changed profile, files, queue, transport or episode identities | Submission checks reject changed plans before transfer; invalid roots do not materialize previews. Provider-number snapshots guard preview conversion. |
| Retry, restart and schema migration | Durable batch retry, crash between intent and outcome persistence, stale retry, additive v1→v2 migration, checkpoint restore and qBittorrent recovery tests. |
| Provider outage/partial completion | Deterministic timeout/failure tests plus actual configured-provider reads, summarized below. |
| Shared regressions | 85 existing movie/shared browser checks passed, including More Like This, advanced search, canonical details, settings, native player routing, IPTV, downloads and background catalog changes. |

### Configured providers: reads only

`providers-read-only.json` records actual configured TMDB/Prowlarr reads for the first three episodes of season 1. Each example produced at least one selected release whose trusted link resolved to a 40-character hash and passed review:

| Show | Resolvable choices | Identity-review choices | Result |
| --- | ---: | ---: | --- |
| Dark Matter (2024) | 1 | 1 | Selected link accepted after resolution. |
| Daredevil: Born Again | 2 | 15 | Selected link accepted after resolution. |
| The Simpsons | 21 | 0 | Selected link accepted after resolution. |

Some indexers timed out or failed. Other-season results remained blocked for the requested season. These are search/link checks, not downloads of these shows. The disposable catalog remained empty and no real-user torrent was submitted. `tmdb-read-only.json` separately records public metadata/cast responses.

### Actual isolated client

`real-client.json` and `real-client-torrent.json` record qBittorrent 5.2.3 tests using two disposable profiles, a loopback seeder and generated synthetic 1080p media. Magnet and `.torrent` paths both selected episode 1, set episode 2 priority to zero, imported only episode 1 as measured 1080p, and retained source files. Both isolated clients were stopped. No normal CP or user qBittorrent client was restarted.

### Test and build record

- Final backend run on the completed code: 1,351 tests, 1,350 passed and one failed in 267.380 seconds. The sole failure was `ProjectionAndWorkerTests.test_movies_get_is_pure_and_projection_is_nonblocking_progressive`: 1.319 seconds against its 1-second startup bound. A fresh isolated run of that exact test passed. The IPTV implementation and test have no changes relative to HEAD. Earlier stabilization also recorded this intermittent failure. Its underlying timing variability remains unresolved; the final full run is not described as green.
- Earlier full runs: 1,343 passed in 267.377 seconds; 1,348 ran with the same IPTV timing failure (2.784 seconds); 1,350 passed in 251.132 seconds before the final ownership-collision fix. That final fix passed all 117 TV acquisition/qBittorrent tests in 18.664 seconds. The timing assertion has not been weakened.
- Node: 101 tests passed, no skips or failures.
- Movie/shared browser run: 85 passed; the 15 TV tests in that discovery snapshot were intentionally skipped because they require the TV fixture server.
- Final TV browser run on completed code: 16 passed in 25.3 seconds, including inline-plus geometry, title-draft keyboard assertions and refreshed screenshots. The 85 movie/shared checks plus these 16 TV checks total 101 passing browser checks across their appropriate isolated servers.
- Production build succeeded. The actual frontend route owner served three page routes and all 37 compiled assets byte for byte from the rebuilt bundle through an isolated Flask test client. `build-evidence.json` contains hashes. No normal application server was launched.
- Screenshots were visually inspected. The final captures show the inline plus button, visible filters, full posters, ordered cast and actionable release chooser. These are disposable fixture sessions, not Dante's live library.

Intermediate failures were retained and corrected: the legacy Library adapter had no metadata client; one preview test assumed a fixed global catalog count; a criterion-picker overlay required closing before reset; duplicate provider rows left continuation pending; a migration test left its backup connection open. Screenshot review caught the plus button wrapping onto another line, and a geometry assertion now covers that. One browser worker exited with Windows status 3221226505; the complete TV rerun passed. No assertion was weakened to accept a product defect.

Logs are retained under `C:\Users\dante\.codex\backups\cp-tv-parity-20260918-205801`. Final-run files are `backend-complete.log`, `retry-ownership-final.log`, `iptv-timing-isolated.log`, `browser-tv-complete.log`, `real-client-torrent-final.log`, `real-client-magnet-final.log` and `bundle-complete.log`. Earlier movie/shared and Node results are in `browser-movies-final.log` and `node-final.log`.

## Preservation and limitations

`preservation.json` verifies that this worktree's `config.json` and `runtime/player/current.json` match the pre-edit hashes. All 43 recorded changed-file states in the original Desktop checkout also still match its baseline. The pre-edit manifest records 148 changed/untracked paths: 145 backed-up files and three pre-existing deletions. Existing uncommitted TV and restored movie work is retained.

Provider availability and release naming remain variable. Unsupported absolute/scene numbering needs an explicit mapping; conflicting titles/years are not force-downloaded. Recommendations use a bounded deterministic planner, not an unlimited optimal search. Search totals/order remain explicitly partial until remote filtering completes. Torrent shared pieces can contain bytes from skipped files; priority zero does not promise byte-level exclusion of shared pieces. A title/hash review does not prove the contents of a public torrent; manifest and measured import checks remain required.

The unresolved IPTV timing assertion above prevents a claim that the latest full suite is entirely passing. No unrelated IPTV implementation or test threshold was changed to conceal it.

No real-user media, live catalogs, monitoring or settings were changed. No commits, pushes or releases were created. The tests provide regression evidence, not a guarantee that every provider or media file will work.

## Dante's launch path

`C:\Users\dante\.codex\worktrees\0870\cinema paradiso\run.bat`

The batch exists and was not run by this task. Dante can launch this version himself with its retained settings.
