# Private Windows 11 friend test package

**Status:** Approved for implementation, 2026-10-07. Dante approved the stated package scope with "you can go": local source checkpoint, private copy under OneDrive/E7na/Cinema paradiso test, saved service/API settings, bundled Ollama/Prowlarr, launcher and Codex handover. No push, public release, live restart or live data changes.

**Approved amendment, 2026-10-07:** Dante: "my friend has olama so delete it and write in the hand over isntructions to connect to his olama or ask him to download and intigrate one". This supersedes bundled Ollama/private Ollama identity and port 21434 throughout the original plan below. Source is clean master at 38d339a before this amendment; delivered folder is 4.709 GB, of which Ollama is 2.957 GB. Original CP/Ollama remain PID 28380/34956 on 5000/11434; no live source, settings, data or served frontend changes.

### Amendment behavior and execution

- Existing owners: `build_friend_test_folder` stops requiring/copying Ollama or identity/models; `friend_test_config` defaults to external URL 11434 with saved model unchanged. `friend_test_launcher` removes owned Ollama startup, port reservation, monitoring and private environment. It checks configured `/api/version` once (3-second timeout); missing AI prints setup guidance and CP continues. CP's existing Ollama API/Settings retain URL/model persistence and model validation. No frontend change or competing AI owner.
- Recipient address edits survive restart/relocation. External Ollama is never added to the Windows Job Object and never stopped by CP. Sign-in helper finds recipient CLI on PATH or its standard per-user install; it sets only OLLAMA_HOST from CP settings and retains recipient identity/models. Missing CLI gives handover guidance. No automatic installation, account login or model downloads.
- Handover instructs recipient Codex to inspect/reuse existing service, start it, install from official Windows download if absent, use own login, run CP's Test Model and Save Ollama. Other bundled services, private CP roots, credentials and public ZIP behavior stay as approved.
- Delivery: remove only copied `runtime/ollama` and package Ollama data directories; synchronize changed source/tests/handover, revise quick start/notices/manifest and runtime hashes. Original installation is excluded from removal. Existing manifest checks remain historical; amendment verification is recorded separately.
- Acceptance: external available -> CP starts and connects; absent -> CP starts with notice; custom URL -> retained; Stop CP -> external PID/listener survives; no runtime/ollama or identity/model directories; private assembly needs no Ollama source; public ZIP still excludes credentials. Verify focused private/public tests, Ollama owner tests, actual packaged start/stop and remaining runtime hash inventory. Full Python's known streamLoaded failure remains prior evidence, not a new full-suite claim.

### Amendment verification, 2026-10-07

- Baseline private/public suite: 18/18. New regressions failed before changing the owners (old port, copied identity directories, required Ollama source, missing external integration). Revised private/public/Ollama recommendation suite: 31/31 passed in isolated OS-temp.
- Actual revised folder started CP/Prowlarr/FlareSolverr against existing Ollama at 11434, then against an unavailable custom address. Both returned the configured URL through `/api/ollama/config`, started CP successfully and shut down owned services with exit 0. Original Ollama PID 34956/11434 and CP PID 28380/5000 remained. No inference/account change or torrent download performed.
- Remaining 2,550 runtime files hash-verified; 1,720,801,116 runtime bytes. Whole revised delivery approximately 1.75 GB. Smoke data/bytecode moved to OS-temp and pre-smoke package data restored; no .venv, Ollama runtime, account or model directories delivered. No UI source/bundle change or new full-suite claim.
- Automatic review blocked recursive deletion without a detailed reason. Safer removal from delivery succeeded by moving only the copied Ollama files to `C:/Users/dante/AppData/Local/Temp/cp-removed-bundled-ollama-eea4e45a29b14fa6a7994c3a54f3d602`, outside OneDrive. This recovery copy is not distributed; no global Ollama installation was touched.

## Problem and decision

- Current run.bat installs dependencies and rebuilds UI, but assumes external Ollama/Prowlarr and this machine's paths. config.json points at E:/Movies, G:/TV and Dante's source data/cache.
- Friend uses Windows 11 and Codex. Required outcome: copied package launches its own configured services; Codex can install ordinary Python/Node dependencies.
- Ollama 0.35.1 uses nemotron-3-super:cloud, with no installed local models. Preserve that model; account-login sharing decision is pending and must be resolved before copying authentication material.
- Prowlarr's 36 indexers use installed FlareSolverr; include its executable/browser as a required service dependency.
- No answer arrived to optional preferences during implementation. Proceed with stated recommended empty libraries and recipient-owned Ollama sign-in. No original Ollama private key is transferred. Preserve the saved cloud model. No media files, personal catalog/lists, active download queue, browser profile, logs, backups or Git credentials are transferred.

## Contracts affected and contract-change decision

| Contract/source | Agreed behavior | Callers | Proposed behavior | Changes contract? | Decision |
| --- | --- | --- | --- | --- | --- |
| Public portable builder/tests | Excludes credentials and user data | build_release_zip | Preserve existing defaults; explicit private-folder API | No | Approved private package |
| CP behavior/UI | Current source and design | Movies/TV/IPTV/AI | Same source and compiled desktop UI | No | Approved copy |
| Cloud AI | Saved cloud model | Ask AI/AI Control | Same cloud model, recipient signs in once | No | Recommended option stated; no login transferred |
| Personal library/data | Paths owned by each machine | Library/acquisition | Package-local empty roots | No | Recommended option stated; no personal catalog transferred |

## Current design and ownership

Checkout: C:/Users/dante/Desktop/cinema paradiso, master at 7e7cda5; 22 modified files and 70 untracked files, primarily TV import/cleanup, Discover paging, regression tests and verification. Inspect and checkpoint these as requested, not as new implementation in this task. Config/data remain ignored. Live backend PID 28380, port 5000; external Ollama 11434, Prowlarr 9696, FlareSolverr 8191. Current bundle remains unchanged by building to OS-temp.

| Responsibility | Owner | Behavior preserved |
| --- | --- | --- |
| Application/runtime packaging | tools/build_portable_release.py | Existing allowlists, qBT/FFmpeg/native-player copy and hash validation |
| CP configuration | app.py _load_config/config.json | API keys, preferences and domain boundaries |
| qBT lifecycle | services/qbittorrent.py | Existing embedded runtime 5.2.2, fresh profile/jobs |
| Movie database location | services/catalog_repository.py catalog_database_path | Installed CP unchanged; CP_PORTABLE_DATA=1 selects stable data/catalog.sqlite |
| Private service launch | tools/friend_test_launcher.py | Private package only; never stop unrelated services |

## Exact behavior contract

Frontend: no JSX/CSS edits. Build current Vite UI into temp dist and include that artifact.

Backend/package: add build_friend_test_folder to the existing packaging owner, sharing the application-copy routine with public builds. Fail if target already exists, rather than overwriting it. Config credentials copied only to ignored config.json. Use runtime/ollama, runtime/prowlarr and runtime/flaresolverr; Prowlarr SQLite online backup gives a consistent copy without stopping the live service. Copy configured indexers/proxies and point FlareSolverr proxy at package service. Copy IPTV provider registry/configuration only, not catalogs or live sessions. Native player, FFmpeg and qBT use existing packaging owners.

Launcher: Python stdlib supervisor; default ports CP 15000, Ollama 21434, Prowlarr 19696, FlareSolverr 18191 and qBT 18686. Bind locally where supported. Reject conflicts before launching; never kill a port owner. Rebase package-owned paths after relocation using a last-root marker, while preserving friend-selected external library paths. Keep Ollama home/models inside data/ollama-home and data/ollama-models; do not read host account identity. Start/health-check dependencies before CP; bounded startup timeouts, hidden child processes, per-service logs, Ctrl+C shutdown of owned process trees, CP exit 75 restart handled within supervisor. Sign-in helper uses same private environment. Prebuilt UI needs Python dependencies to launch, not Node; source builds remain available to Codex.

## Implementation sequence

1. Inspect dirty source and run isolated baseline; local checkpoint before copying.
2. Add failing private packaging/configuration tests, then refactor shared copy routine and implement private package assembly.
3. Add launcher and account helper; regression coverage for relocation, preserved external roots, conflicts and owned cleanup.
4. Build frontend into temp; commit packaging source and assemble requested folder using local installed service binaries, pinned runtime and consistent settings snapshot.
5. Smoke-test separate copied runtime, API and compiled desktop; verify relocation and service shutdown; produce checksummed manifest and handover.

## Acceptance matrix

| Scenario | Expected result | Evidence |
| --- | --- | --- |
| Private package | Saved API/service settings and required binaries present | Assembly integration tests and manifest |
| Public ZIP | Still excludes config/data/secrets | Existing test_release_packaging |
| Relocated folder with spaces | Local paths resolve under new root | Config tests and relocated smoke run |
| Friend-selected external roots | Preserved across restarts/relocation | Config tests |
| Port occupied | Explicit error; existing process stays running | Conflict regression |
| Service unavailable | Timeout/log path; owned started processes cleaned | Startup failure test/smoke |
| Prowlarr | Copied indexers/API key work; proxy uses bundled FlareSolverr | Read-only API probe |
| AI | Preserved cloud model; account decision honored | Cloud smoke once authorized |
| Movies/TV/IPTV | Empty approved roots, provider settings, no transferred jobs | API and package inspection |
| CP exits/restarts | Own services cleaned or retained for CP restart | Supervisor smoke |

## Verification and rollout

- Focused baseline: 61 tests passed (packaging, Discover paging, TV normal import/destinations). Full Python baseline running; record failures honestly.
- New packaging/launcher tests use OS-temp fixtures only; no production media or provider network.
- Node suite and Vite build with --outDir in OS-temp; no replacement of live dist.
- Private package verification runs on private ports and copied data; provider checks are read-only apart from one explicitly included AI smoke request. No torrent submission or catalog edits on the original.
- Manifest records source commit, runtime versions/hashes and test results without secrets. Handover gives launch, dependency setup, logs, port ownership, privacy and limitations.
- Rollback: remove only newly built private package if explicitly requested; original installation and services unchanged. Fail on existing destination.

## Execution evidence

- Source checkpoint: 6d7205e, local only, includes inspected pre-existing TV/Discover source, tests and verification material.
- Baseline: 1,626 Python tests, one pre-existing failure in test_qbittorrent_ui.test_streaming_modal_shows_loading_feedback_until_iframe_loads (expects removed streamLoaded identifier). No assertion changed. 119/119 Node tests passed; fresh Vite compilation succeeded into OS-temp.
- New private/public packaging plus catalog/poster focused suite: 43/43 passed. Includes realistic fake-runtime assembly, private settings preservation, public exclusion, occupied port, relocation, catalog storage, snapshot integrity and process timeout cleanup.
- Review found host LocalAppData sharing, copied venv risk and startup containment race. Corrected through authoritative catalog owner portable storage, package-local LOCALAPPDATA, excluding test venv from delivery, and suspended child startup before Job Object assignment. Windows descendant logs release verified before cleanup completes.
- Follow-up review found shared Edge process ownership and persisted poster relocation. Edge is outside the service job and uses the existing specific-window close owner; MediaAssetService reconciles ready checksum files under its current authoritative root. Persisted-poster move regression failed before the fix and passed after it. Focused suite now 44/44.
- Actual package assembled (4,697,789,052 bytes before smoke), launched all four service owners on private ports and stopped with exit 0. CP/FlareSolverr/Prowlarr/Ollama listeners were localhost-only. Prowlarr 2.6.5.5623 has 36 indexers (21 enabled); Ollama 0.35.1 retains cloud model; original account key excluded and private generated key differs. TMDB test returned success; copied TV roots are local, movie DB is data/catalog.sqlite. Compiled desktop UI at 1600x900 showed Home, populated Discover, Settings and repeated Discover navigation. No torrent submission or media playback performed.
- Final full suite and final transfer manifest results recorded in package TEST-PACKAGE.json. Test-run environment is outside package; no .venv is delivered.
