# Repair existing TV downloads in numeric ID folders

**Status:** Live verified, 2026-10-05. Dante said, "yes do but also see any other downloads misplaces in a folder with the id name and fix them all", then "go" in response to the concrete 18-file move and brief CP stop/restart request. All 18 files are moved; catalog/job references and approved homes agree. CP was stopped and restarted through its normal launcher. qBittorrent and staging copies were preserved.

## Problem and decision

- **Observed:** Three top-level numeric folders under the configured `G:\TV` root contain 18 available, bound videos: South Park S27E03–E05 (3), Dark Matter (2024) S01E01–E09 (9), Slow Horses S01E01–E06 (6). Approved numeric folder IDs match catalog TMDB identities and the existing jobs' exact published targets. There are no unknown files in those folders and qBittorrent currently has no torrents.
- **Intended result:** Move the existing files into the established South Park season and named show/season homes for the other two; preserve filenames, file/episode IDs, facts, segment bindings, watch progress and legacy source-retention policy. Update catalog paths and the existing jobs' destination/publication references together, then retire empty obsolete numeric folders/assignments.
- **Exact destinations:** `G:\TV\South Park\Season 27`; `G:\TV\Dark Matter (2024)\Season 01`; `G:\TV\Slow Horses\Season 01`. The latter two have no existing named home; these explicit migration destinations do not establish an automatic naming rule for future new shows.
- **Additional confirmed source defect:** An excluded file beneath South Park's Extras directory currently disqualifies the entire show home. Home selection must allow excluded descendants while season/target safety continues to reject excluded destinations. Fix only this owner-level distinction, with a regression.
- **Scope:** Existing downloaded TV videos in numeric folders across configured TV roots. No movie/IPTV changes, filename changes, staging cleanup, torrent deletion/re-addition, profile/lifecycle migration, ranking changes, UI redesign, commits or release. Existing Slow Horses `needs_review`/`Native TV import is not enabled` journal state is prior runtime evidence; moving its published library files does not silently convert that status.

## Contracts affected and contract-change decision

| Contract | Agreed result | Affected owner | Change? | Authorization |
| --- | --- | --- | --- | --- |
| Existing misplaced library paths | Correct show/season homes | Filesystem, TV SQLite, transfer journal | Authorized data correction | Dante's explicit all-numeric-download repair request |
| TV identity/playback | Existing file IDs, episode IDs, progress, measured facts and segments remain | TV catalog/playback | No | Preserve |
| Historic retention/rollback | Staging sources and stored modes/policies stay intact; rollback references follow the moved targets | Existing jobs | No lifecycle change | Preserve |
| Approved home with excluded Extras | Ignore unrelated excluded descendants during home selection; continue protecting excluded season destinations | Repository | Correct missed case in approved destination contract | Necessary to repair and continue South Park in its approved home |
| New-show naming | No general automatic rule | Acquisition | No | Explicit paths only for this repair |

## Current design and ownership

| Responsibility | Authoritative owner | Use in repair | Preserve |
| --- | --- | --- | --- |
| Approved paths, homes, media rows and bindings | `TVCatalogRepository` / `TVCatalogStore` | Existing root/assignment/exclusion/destination methods and one SQLite transaction | IDs, bindings, facts and progress |
| Published file integrity | `services/verified_import.py::sha256` | Compare physical video with durable job hash before/after same-volume exclusive rename | No overwrite or unverified deletion |
| Existing operational recovery | `QBittorrentJobStore` | Update only affected destination/imported-target/temporary-path fields through the existing atomic writer while CP is stopped | All other job fields and sources |
| One-time repair orchestration/evidence | `tools/repair_tv_numeric_folders.py` | Explicit preview manifest, offline apply, backup, checkpoints and resume | No new production queue, store or automatic relocation rule |

Baseline: Desktop checkout `master`, HEAD `7e7cda5a24ee579f38a7c1095f41d39944d18345`, prior dirty source/tests/plans preserved. Production TV catalog schema 5; config data owner `C:\Users\dante\Desktop\cinema paradiso\data`, TV root `G:\TV`. CP now runs at port 5000/PID 47924, qBittorrent port 8686/PID 37688, served entry `/assets/index-BL38s9_4.js`, showing Dante activated the preceding implementation after its source-only report. No restart performed by this repair yet.

## Exact behavior contract

No frontend amendment. Existing API/version views must return the corrected paths and availability after repair; playback keys continue to contain the same file IDs.

Preview takes an explicit numeric-folder→named-home mapping, validates it against assignments/TMDB identities, checks every physical file has one unambiguous season and unchanged catalog binding, checks filename identity/season/episodes through the existing parser, and hashes every source. Existing approved homes use the repository's destination resolver; new homes use the explicitly supplied season layout `Season NN`, with collision/ownership/exclusion checks. A target must not exist or already be registered. Differing/duplicate content is reported for review rather than overwritten or deduplicated in this repair.

Apply requires CP's port closed and qBittorrent to have no relevant active transfer. Before any move, save consistent SQLite backups of TV/acquisition, config and exact job-journal preimage beside the manifest. Recheck file IDs, bindings, fingerprints/hashes and job targets. Perform same-volume `os.rename` on exact validated paths, which refuses an existing target on Windows. Journal each step; on pre-catalog failure, reverse only this repair's verified moves. Preserve sources in the separate staging tree.

Commit one TV catalog transaction updating existing `media_files.path`/fingerprints, inserting approved named homes/preferred selections and retiring old numeric assignments/discovery entries. Keep file IDs and every progress/binding row. Patch affected jobs' `destination`, `imported_paths` and preserving-plan `target`/`temporary` references only; retain source paths, old mode/policy and state. Record original destinations in repair audit metadata. A crash after catalog commitment resumes job bookkeeping from the durable manifest and backups, rather than reversing a now-published path. Remove only empty numeric folders via `rmdir`, never recursive deletion.

## Implementation sequence

1. Add failing owner regression for excluded Extras; minimally distinguish show-home safety from destination safety. Rerun destination/acquisition tests.
2. Add failing disposable repair tests covering IDs/progress preservation, collisions, changed files, rollback on rename failure, crash resume after catalog commitment, preserved staging, job references and unrelated rows. Implement the offline repair utility through existing owners.
3. Produce the exact live hash/identity manifest and recovery snapshot; report a concrete move list and request the necessary brief stop/restart authorization only once preparations pass.
4. After authorized exclusive access, apply all confirmed moves, verify hashes, SQLite integrity/relationships/unchanged IDs and journal paths, retire empty numeric folders, then restart/verify live API and desktop paths. Record exceptions instead of guessing.

## Acceptance matrix

| Scenario | Observable result | Verification |
| --- | --- | --- |
| South Park split season | E03–E05 alongside existing E01–E02; same IDs and bytes | Hashes + SQL + live season API |
| Dark Matter/Slow Horses numeric homes | 9/6 videos in explicit named Season 01 folders; assigned homes | Manifest + SQL + filesystem + live API |
| Existing progress and segments | Exactly unchanged rows and IDs | Before/after SQL snapshot comparison |
| Existing rollback/source policy | Targets follow new paths, staging and policy unchanged | Job preimage comparison and retained-source checks |
| Excluded Extras | Show/Season 27 resolves while excluded destination remains blocked | Owner regression + live resolver |
| Collision/wrong identity/shared ownership/changed bytes | Fail before live move; no overwrite | Disposable adverse tests and live preview |
| Interrupted rename before catalog | Only owned verified moves reversed | Fault injection |
| Crash after catalog before journal | Resume bookkeeping without recopy/rebinding | Fault injection |
| Unknown neighbors | Refuse numeric-folder repair/removal | Disposable test |
| Running CP | Apply refuses concurrent mutation | Offline gate test |

## Verification and rollout

### Preparation ledger

- Inventory covers the configured `G:\TV` root: exactly three numeric top-level folders, 18 bound videos, 10,411,153,006 bytes. No unbound files or destination collisions. Every source matches its existing journal SHA-256; manifest is `docs/verification/tv-numeric-repair/manifest.json` with explicit homes in `homes.json`.
- Home/repair regressions observed RED before implementation. CLI preview additionally reproduced Windows `WinError 32` because SQLite context managers commit/rollback but do not close connections. Explicit `contextlib.closing` corrected both disposable-preview and additional SQLite backup handles; the Windows CLI regression passes.
- Current focused result: **187 tests passed in 43.800s**, including 10 repair tests, 10 destination tests, and existing normal/legacy TV, catalog, acquisition, qBT/API and monitor suites. Log: `docs/verification/tv-numeric-repair/focused.log`. `git diff --check` passes.
- Broad run: **1,625 tests in 233.721s, one failure, no skips**. The sole failure remains the unchanged `test_qbittorrent_ui.QBittorrentUiTests.test_streaming_modal_shows_loading_feedback_until_iframe_loads` assertion for `streamLoaded`; all other cases passed. This run began before the additional CLI-handle regression was added; that regression is included in the current 20 repair/destination checks and 187 focused tests. Log: `docs/verification/tv-numeric-repair/full.log`. Do not report the full suite as green.
- Preview completes cleanly. No production catalog, job-journal or library file has been changed by the repair yet. Only the excluded-Extras source correction, utility, tests and preparation artifacts were written.
- Preflight recovery snapshot: `data/backups/tv-numeric-repair-preflight-20261005-030152/` contains consistent TV/acquisition SQLite backups, exact job-journal/config copies and SHA-256 manifest. Both SQLite integrity and foreign-key checks pass. Offline apply takes a fresh coordinated snapshot before the first move.
- Asked once for brief CP stop/repair/restart authorization after all preparation above completed. Required by root `AGENTS.md` section 6; while waiting, live operations remain paused and broader verification proceeds.
- All 18 retained staging sources physically exist; path/size/mtime baseline is `docs/verification/tv-numeric-repair/staging-before.json`. No source-retention policy or staging data was changed. Preparation is ready; the stop/restart question remains pending and no library files have moved.

### Approved live execution and results

- Dante's subsequent **"go"** authorized the stated stop/repair/restart. Used CP's recoverable power action `action:'cp', close_qbittorrent:false`; port 5000 closed, qBittorrent stayed at port 8686/PID 37688 with zero torrents.
- Offline utility completed all **18 same-volume moves (10,411,153,006 bytes)**. South Park S27E03–E05 are now in `G:\TV\South Park\Season 27`; Dark Matter S01E01–E09 in `G:\TV\Dark Matter (2024)\Season 01`; Slow Horses S01E01–E06 in `G:\TV\Slow Horses\Season 01`. All three empty numeric folders and their obsolete approvals were retired. No other numeric top-level folders remain in the configured TV root.
- Fresh coordinated backups before moving: `data/backups/tv-numeric-repair-e8ef565db57c4e2983649670f651ea29/` contains TV/acquisition databases, jobs/config and SHA-256 evidence. The pre-restart served `dist` was also copied there. Manifest, apply log and offline/live evidence are under `docs/verification/tv-numeric-repair/`.
- Independently re-hashed every moved destination and compared media rows with the offline backup: only paths changed; file IDs, sizes, timestamps, measured facts, availability and creation times stayed identical. All episode bindings and all playback rows are unchanged. SQLite integrity/foreign-key checks pass; **23 other catalog tables**, all unrelated media/approval rows, acquisition tables and config match the pre-move snapshot.
- Updated only the three affected jobs' destinations, imported paths and publication target/temporary references, with original destinations retained as repair audit data. Their states/modes/policies/source references are preserved. **493 unrelated jobs are exactly unchanged**. All **18 staging sources** retain their original size and modified-time fingerprints.
- Verification-script correction: the first offline check wrongly required historical movie `imported_paths` directory entries to be files. Corrected the verification to compare unrelated jobs unchanged and validate only affected TV targets; the resulting full offline check passes. The first live served-index comparison used newline-normalizing text reads; byte comparison confirms the served index exactly matches `dist/index.html`. Neither issue required a library or production-code correction.
- Restarted with `run.bat` under a hidden launcher, without test-mode variables. CP now owns port 5000/PID **52044**; qBittorrent remains PID **37688**. Served entry remains `/assets/index-BL38s9_4.js`, matching the current compiled frontend byte-for-byte; the backend now includes the excluded-Extras owner correction.
- Live API returns every moved file at its new path with the same file ID and `available:true`; acquisitions return all three new destinations. TV stays enabled with root `G:\TV`, qBittorrent still has zero torrents.
- Read-only rendered desktop verification at **1600×1000** opened every moved episode's Versions dialog and asserted its exact new path: **18/18 passed**. Startup writes/actions were blocked in that verification browser; no Play/mark/download action was executed. Visually inspected screenshots for all three shows. Evidence: `live-desktop-verification.json`, `live-series-33.png`, `live-series-4.png`, `live-series-5.png`.
- Remaining known conditions: Slow Horses retains its pre-existing legacy `needs_review` transfer status and prior runtime warning, as specified; its six library episodes are available at the corrected paths. Existing staging copies remain by design. The recorded unrelated stream-overlay full-suite failure remains outside this repair. No episode/path contract difference remains for the 18 repaired files, and no commit/push/release occurred.

### Final acceptance comparison

| Approved result | Observed result |
| --- | --- |
| South Park joins its established season | All three hashes and file IDs verified in Season 27 alongside existing episodes; live API and dialogs agree |
| Repair every other identified numeric download folder | Dark Matter 9 and Slow Horses 6 moved; zero numeric top-level folders remain |
| Preserve playback/identity/facts | Backup comparison confirms unchanged IDs, bindings, progress, measured facts and fingerprints |
| Keep recovery coherent | Three jobs use new published paths; policies/staging intact; 493 other jobs unchanged; coordinated backup preserved |
| Continue South Park despite excluded Extras | Repository resolves ready Season 27; exclusions preserved; regression passes and corrected owner loaded after restart |
| Leave broader domains intact | Acquisition/config and unrelated catalog/job rows match snapshots; no movie/IPTV mutation by repair |
| Verify live result | CP restarted, production API returns all 18 available files, 18 rendered desktop dialogs show exact paths |

- Unique temp `CP_TEST_MODE=1`/`CP_TEST_ROOT`, `PYTHONDONTWRITEBYTECODE=1`; focused tests for repair/destinations/TV acquisition/catalog. Earlier full-suite stream-overlay failure remains recorded, not proof of current new checks.
- Live preview hashes physical files and compares legacy journal hashes; no production app import. Store task evidence under `docs/verification/tv-numeric-repair/`.
- Stop/restart authorization is pending because `AGENTS.md` section 6 treats restarts separately, and concurrent background journal writes could overwrite repair bookkeeping. All source/testing/preview work proceeds first.
- Restore is safe only while CP remains stopped and before new live work: reverse exact verified moves and restore coordinated TV/job snapshots; never overwrite newer post-repair user activity. Acquisition/config backups are recovery references, unchanged by repair.
- Report actual moved/blocked counts, every destination, retained staging, test outcomes and live API evidence. No successful repair claim until physical files, catalog and journal agree.
