# Whole-checkout activation — 2026-10-24

**Activated.** Dante explicitly selected the whole current checkout and required verified backup/rollback first. No product source, dependency, configuration, identity or repair change was made in this activation pass. Existing current changes were preserved. The backend is PID 55244 (venv launcher 32668), with the configured Desktop data/cache roots and E:\Movies. The normal installed CP window was reopened through its existing owner.

## Recovery first

An external `run.bat` invocation restarted CP while preparation was underway and rebuilt production dist to the corrected candidate. This was outside this pass. The old October 23 loaded-code state was unavailable for exact recovery. CP then shut down successfully through its lifecycle checkpoint, including the owned embedded client (which reported two active downloads). No force-stop was used.

Recovery: `C:\Users\dante\Desktop\CP-Recovery\whole-checkout-2026-10-24-153619-e50288`.

- 45,833 snapshot files, 6,276,193,649 bytes; every original/copy SHA256 and length verified, with a stable second inventory and zero Restart Manager recovery-resource owners.
- All files restored into a separate directory and verified again before checking 48 restored SQLite databases: all `quick_check` results were `ok`. Neither snapshot master nor production originals were opened with SQLite by this verification.
- Snapshot took 193.375 seconds; restore/check rehearsal took 123.938 seconds. Payload copies for the two trees total 12,552,387,298 bytes, plus small manifests/logs.
- Source/config/dist, .git and local dirty/untracked source material, active data/journals, qBittorrent profile/runtime, external Movie SQL, metadata, cache and player runtimes are included. Existing dependencies, release archives, named historical backup trees and actual media/payload files are excluded explicitly and remain untouched. See local `manifest.json`, `inventory.json`, `ROLLBACK.md`, `restore-byte-proof.json` and `rollback-rehearsal.json`.
- Rollback target is the captured stopped current state. No earlier loaded-runtime equivalence is claimed. Restoring an app against real media was not rehearsed; byte restoration and copied-database integrity were. If ordinary startup has moved media/payloads, preserve both states and resolve that divergence before restoring old SQL/jobs.

## Isolated verification

All 243 recorded runtime inputs were unchanged. One fresh staged build exited 0; all 35 output files exactly matched current production dist, so no redundant directory swap was made. The build wrapper hit a console encoding error after recording successful exit and output; the retained build log and complete output hashes confirm success, and no rebuild was repeated.

Four compiled desktop tests passed: first/latest typing and exact pagination, stale errors and Back/Forward recovery, typing during old poster preload, and Movie → File → Movie loading recovery. Synthetic OS-temp data, embedded test mode, a separate port and explicit disposable dist were used. This fresh activation allowance is now closed: 22.498 active seconds, 17.71875 process-tree CPU seconds and 129,269,562 process-tree written bytes. The old isolated allowance was not reused.

## Live checks

The backend became ready in 1.953 seconds. Correct source root, data/cache paths, Movie root, one writer lease, backend PID and complete served bundle were verified. The index SHA256 is `695e94fc071215559545e280c896f3eddd17016c23b6d64dadce22f1651146fa`. Existing 114 tracked dirty entries and 1,732 checkout files outside .git matched the snapshot before startup; all 243 runtime inputs and config remained unchanged afterward.

| Query, page 1 / size 40 | Total | Returned | Request duration |
| --- | ---: | ---: | ---: |
| christmas | 75 | 40 | 2695.33 ms |
| m | 3955 | 40 | 207.24 ms |
| unique no-match | 0 | 0 | 421.72 ms |

All three responses had the expected paging/count/query-signature/catalog contract at generation 10178. A 1600 × 1000 desktop check verified all 40 rendered canonical titles in order and Movie → File → Movie with loading settled. Screenshot inspected: `live-library.png`. The first live harness assertion incorrectly expected filename labels; it was corrected by importing the existing authoritative `getMovieIdentity` helper, without changing application code and retaining exact canonical-title, order and count assertions. Its original failure evidence remains in recovery.

Passive SSE observation lasted 30.875 seconds: current-generation sync and heartbeats, generation unchanged, no retained completion event, no coordinator error. No fresh natural completion occurred, so production completion/Following refresh was not observed; earlier synthetic end-to-end evidence remains valid for its named scenarios. The installed CP app window was reopened and its owner recorded. Normal startup writes and resumed work were explicitly in scope; no repair, rescan, import, new download, media deletion, dependency installation, commit or publication was manually triggered.

The cold Christmas request still took 2.70 seconds. These bounded checks do not establish a production speedup ratio or exhaustive regression coverage of every unrelated dirty change. Earlier broader-baseline/CPU-comparison limitations remain as recorded in the qualification report.

Evidence: [machine-readable result](result.json), [desktop capture](live-library.png). Full recovery manifests, logs, scripts, failed harness evidence and verified restored files remain in the local recovery directory.
