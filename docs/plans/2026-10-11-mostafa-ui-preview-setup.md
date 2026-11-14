# Usable Mostafa UI preview

**Status:** Implemented and live preview verified, 2026-10-11. Dante said "go" to preparing a complete test copy with copied settings, catalogs and required runtimes, isolated paths and ports. No original source/configuration edits, real downloads, library mutations, publication or activation in the original installation. Evidence: docs/verification/mostafa-ui-preview/RESULT.md.

## Problem and decision

- The integration worktree has no config.json or player runtime. Its ordinary run.bat targets port 5000 and stops an existing Python server on that port. Dante launched that worktree; port 5000 is now owned by child PID 96628, whose parent 96876 executes the worktree's Python.
- Provide the reviewed UI at http://127.0.0.1:15000 with Dante's saved provider/player/settings, movie/TV catalogs, lists, posters and IPTV settings. Use independent writable data/cache/metadata and qBittorrent profile. Required player and qBittorrent executables are copied, never relocated from the original.
- Confirmed: original settings use Desktop data/cache, E:\Movies, G:\TV, qBittorrent 8686, Prowlarr 9696, Ollama 11434. Preserve existing Prowlarr/FlareSolverr/Ollama as externally running services; do not start or stop them.
- No open decisions affect implementation. This is a desktop UI preview; active acquisition work is intentionally not cloned or started. Existing media roots remain readable for accurate catalog/availability display. Real acquisition/import/delete actions are outside this review and must not be exercised by verification.

## Contracts affected and contract-change decision

| Contract/source | Preserved behavior | Proposed behavior | Contract change? | Decision |
| --- | --- | --- | --- | --- |
| Repaired CP backend and TV fixes / approved integration | Original source and user files stay intact | Copy runtime/settings; run integrated worktree | No | Approved go |
| Download recovery / jobs.json and acquisition.sqlite | One live owner retains original active jobs | Fresh preview qBittorrent profile and no copied active intents/tasks | No product change; preview scope | Approved independent test copy |
| Follow, reconciliation, import background owners / app.py __main__ | Original production behavior stays unchanged | Launch existing Flask app through Flask CLI, so automatic background workers are not started | Temporary preview execution boundary | Preview only; remove when integration is activated normally |

## Current design and ownership

| Responsibility | Owner | Exact use |
| --- | --- | --- |
| Settings | app.py _load_config | Worktree config with copied saved values and isolated data/cache/qBittorrent locations |
| Movie database | services/catalog_repository.py catalog_database_path | CP_PORTABLE_DATA=1 -> worktree data/catalog.sqlite; SQLite backup from original LocalAppData database |
| TV catalog | services/tv_services.py | SQLite backup -> worktree data/tv-catalog.sqlite |
| Acquisition settings | services/acquisition_store.py | Preserve profiles/settings/monitors in copied acquisition DB; remove copied operational rows, original unchanged |
| Process ownership | tools/friend_test_launcher.py OwnedProcesses, cp_environment, require_free_ports | Reuse these owners for preview supervisor; Windows job stops only preview descendants |
| qBittorrent | services/qbittorrent.py QBittorrentManager | Copied version executable and freshly generated isolated profile; WebUI 18686, peer port 18687 |
| Player | services/player_runtime.py | Copy complete runtime/player and verify manifest |

Baseline: both checkouts at be511f9, original dirty repaired TV work preserved. Existing UI integration proof remains in docs/verification/mostafa-ui-ux/RESULT.md. This setup adds a preview launcher and replaces only the worktree run.bat to prevent accidentally using its production launcher.

## Exact behavior contract

- **Launcher correction approved 2026-10-11:** Dante requested replacing the defective batch with the project-folder version and said "for now go". Restore its Python/dependency/bootstrap/build/error handling, adapting shutdown/startup to this copied preview on port 15000. Leave all filter/backend/UI changes untouched for Dante's testing. This approval includes testing repeat preview launches, not restarting the original installation.
- run.bat stops the previous verified preview, waits for its supervisor to close its owned CP/qBittorrent job, then starts the compiled preview. Reuse the existing supervisor and stop marker; never invoke the production stop_stale_backend.ps1 against port 5000. The temporary Flask CLI startup boundary remains until normal integration activation is separately approved.
- Validate owner.json root/port and the live supervisor's absolute launcher command before signaling a stop. Missing/dead ownership proceeds to the existing free-port checks; mismatched ownership or a shutdown timeout blocks startup without killing other processes. A foreign occupied port stays occupied and startup fails clearly. Simultaneous startups without a ready owner record are still subject to the free-port guard.
- Copy config without logging provider secrets. Rewrite user_data_dir, tmdb_cache_dir, qbt_incomplete_dir, qbt_download_dir, qbt_webui_port. Preserve media roots and provider credentials/URLs. Reserve an empty preview movie destination under the worktree for future separate testing, outside real libraries.
- Capture original database integrity and table counts through read-only connections and SQLite backup API. Save pre-operation source/config/job/runtime selector hashes; compare after preparation and HTTP/UI verification.
- Back up worktree's previously generated empty databases before replacement. Stop only the positively identified worktree server on 5000 before replacing its data. Do not stop original qBittorrent or any provider.
- Copy ordinary user documents, app_metadata, cache, IPTV settings/provider catalog and LocalAppData metadata cache. Exclude power requests, active torrent jobs/profile/runtime ownership records, acquisition work queues, transient locks and WAL files. SQLite databases use backup API, not raw file copying.
- Existing app/config/API/frontend owners remain unchanged. No new UI/business behavior. Flask CLI is a temporary preview startup path: it exists to avoid automatic download owners; only this preview launcher depends on it; remove it when normal activation is approved.

## Implementation sequence

1. Snapshot original DBs/counts/integrity and source/settings/job/runtime hashes. Write launcher tests and observe missing-launcher failures.
2. Reuse existing supervisor/config environment helpers in tools/ui_preview_launcher.py; add Stop UI Preview.bat and worktree-only run.bat. Keep logs under data/runtime/ui-preview.
3. Stop the confirmed old worktree process, preserve its generated DBs, copy settings/catalog/cache/runtime into the worktree, clear copied acquisition work queues and verify boundaries.
4. Run launcher tests, start on 15000/18686, verify actual API settings/catalog/player/qBittorrent and rendered desktop screens. Stop/restart the preview and verify its process lifecycle once. Leave it running for Dante.

## Acceptance matrix

| Scenario | Action | Expected result | Proof |
| --- | --- | --- | --- |
| Missing settings/runtimes | Run setup | Saved provider/player settings and complete player/runtime visible | Red-to-green tests, HTTP config/player verify |
| Saved movie/TV state | Browse Library/TV | Original snapshot counts and populated cards | SQLite count parity, HTTP responses, screenshots |
| Separate writable data | Save a benign existing config value | Only worktree config written, original hash unchanged | HTTP PUT plus hash comparison |
| Original active downloads | Start preview | Original qBittorrent PID/port/jobs untouched, preview torrent list empty | Original hashes/process inventory, preview API |
| Port conflict | Start another copy | Foreign port owner remains running; startup fails clearly | Real bind-conflict test and verified ownership checks |
| Repeat run.bat with a ready preview | Build, stop and wait, launch | Previous preview CP/qBittorrent processes close, replacement is HTTP-ready on 15000, original service PIDs unchanged | Launcher regression tests and two real batch launches |
| Invalid or stale ownership | Stop and wait | Mismatched root/command rejected before touching marker; dead owner returns to port guard; timeout blocks replacement | Disposable owner-record tests |
| Stop/restart | Preview marker then start | Only preview-owned CP/qBittorrent stop and restart | Process/port inventory before/after |
| Desktop UI | Open Settings/Library/TV/Lists | Mostafa compiled UI populated with copied state, no missing runtime/settings | Desktop screenshots and page errors |

## Verification and rollout

Use .venv Python unittest for launcher contracts; preserve existing integration test results without rerunning unrelated suites. Build npm run build after launcher changes only if the existing bundle differs from reviewed source; otherwise verify exact dist asset hashes. Use live HTTP checks on 15000, full player hash validation, copied SQLite integrity/count parity and a desktop browser walkthrough. No real playback/download/import/delete requests in verification. Record setup result separately from the earlier source integration report. Rollback: Stop UI Preview.bat; original installation remains intact, backups of replaced worktree state remain available.

### Launcher correction verification, 2026-10-11

- Four new regression tests failed before implementation. Restored the main batch's environment/dependency setup, build and exit handling, adapting only the copied preview shutdown/startup and browser entry point. The preview's existing browser opener remains in use; the production window helper and port 5000 shutdown are not called from this preview.
- Launcher and shared friend-supervisor tests: 23 passed. Missing/invalid config cannot prevent a verified stop; different process/root/port ownership is rejected; stale owner proceeds to free-port checks; shutdown timeout blocks replacement.
- Two consecutive real `cmd.exe /d /c call run.bat` launches compiled the frontend, stopped all three previous preview-owned process IDs and started HTTP-ready replacements. The first batch exited cleanly after the second restarted it. Original qBittorrent/Prowlarr/FlareSolverr/Ollama process IDs were unchanged. All 1,093 original source/settings/selector hashes and all three filter/portrait support files plus worktree config remained unchanged. The second preview was left running.
- Evidence: docs/verification/mostafa-ui-preview/launcher-restart/RESULT.md. No production backend, frontend/filter logic, original configuration or download behavior was changed by this correction.
