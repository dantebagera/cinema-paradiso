# Cinema Paradiso private test — Codex handover

This is a private Windows 11 x64 test copy. Start with this file before changing anything. It includes working source, compiled frontend and saved API/service settings. It contains private credentials: do not publish this folder, print its settings, upload its logs without checking them, or commit config/data/runtime. No Git history or remote credentials are included. The original CP installation belongs to Dante and is outside this package.

## First launch

1. Download/copy the **whole folder**, keep all OneDrive files available locally, and preferably extract/copy it outside a folder being actively synchronized before running. Runtime databases and several GB of binaries need local access.
2. Run `run.bat`. It creates a local `.venv` and installs `requirements.txt` on first launch, then starts FlareSolverr, Prowlarr, Ollama and CP. It opens CP's existing desktop window. The compiled frontend is included; Node is not needed just to launch.
3. Keep the launcher console open. Use Ctrl+C or `Stop CP.bat` to stop its services. Do not close/kill other CP installations or system services.
4. AI uses the saved `nemotron-3-super:cloud` model. Internet and an Ollama account are required. If this package does not include a signed-in account (see TEST-PACKAGE.json), keep CP running and run `Ollama sign in.bat` once; complete the browser login with the recipient's own account. No local model weights are needed for this cloud model.

If Python is missing, Codex can install Python 3.12 x64, reopen the terminal and run `run.bat` again. Example: `winget install --id Python.Python.3.12 --exact --accept-package-agreements --accept-source-agreements`. Do not install Ollama, Prowlarr, FlareSolverr, FFmpeg or qBittorrent globally; their required binaries are already inside this folder.

## Ownership and layout

- `app.py`, `services/`, `src/`: original CP authoritative owners. UI/design behavior has not been rewritten for the package. Root AGENTS.md still applies to development; this package handover explains launcher/runtime differences.
- `tools/build_portable_release.py`: one application-copy owner shared by public/private packaging. `build_release_zip` excludes personal settings; `build_friend_test_folder` is explicitly private.
- `tools/friend_test_launcher.py`: private service supervision and relocation, started by this copy's `run.bat`. It refuses occupied ports, uses a Windows Job Object to contain its children, and stops its own service trees. CP's restart request restarts only its backend while services stay running.
- `config.json`: saved CP credentials/preferences. Initial Movie/TV roots are empty `library/movies` and `library/tv`. No media, personal catalog, lists or active download jobs were transferred. Add the recipient's real roots through CP Settings when needed. The launcher sets `CP_PORTABLE_DATA=1`, so the authoritative movie database is `data/catalog.sqlite`; package-local `LOCALAPPDATA` keeps poster assets under `data/localappdata`. Neither uses the Windows account's shared CP metadata.
- `runtime/ollama`: CLI and CPU/GPU libraries; `data/ollama-home`: isolated identity; `data/ollama-models`: isolated models. Do not use the Windows user's global Ollama identity or models as a hidden fallback.
- `runtime/prowlarr`: executable and self-contained .NET runtime; `data/prowlarr`: consistent SQLite settings snapshot, configured indexers and local FlareSolverr proxy. No live original database is opened by this copy.
- `runtime/flaresolverr`: executable and its bundled browser; `runtime/ffmpeg`: FFmpeg/FFprobe; `runtime/player`: selected hash-validated native player; `runtime/qbittorrent`: pinned embedded runtime. New qBT state/jobs belong to this package.
- `data/iptv`: saved provider configurations; IPTV catalogs/sessions are initialized normally. Providers still need internet and valid subscriptions and may impose simultaneous-connection limits. Configured Plex access is retained, but Plex itself is not bundled.
- `TEST-PACKAGE.json`: source commit, versions, account-sharing status, ports and validation. `RUNTIME-SHA256.json`: binary inventory. These contain no credentials.

## Ports and verification

| Service | Local port |
| --- | --- |
| CP | 15000 |
| Ollama | 21434 |
| Prowlarr | 19696 |
| FlareSolverr | 18191 |
| Embedded qBittorrent | 18686 |

Open CP at `http://127.0.0.1:15000/`. These differ from common globally installed service ports. Do not kill the owner of a busy port to make this package start. Diagnose it first. A port amendment must update the launcher, CP settings, copied Prowlarr XML and proxy settings together.

The launcher rewrites only package-owned paths on relocation. Paths the recipient selects outside the package stay unchanged. Stop the package before moving it. Never copy someone else's `.venv`; if Python setup is broken or the base interpreter is removed, recreate `.venv` in this copy and install requirements again.

For diagnostics inspect `data/runtime/friend/CP.log`, `Ollama.log`, `Prowlarr.log`, `FlareSolverr.log`. Check `http://127.0.0.1:21434/api/version`, Prowlarr `/api/v1/system/status` using the API key locally without printing it, and CP's Home/Discover/Settings. A loaded provider page is not proof of video playback; verify actual playback separately. No torrent download was initiated during package verification.

## Development and tests

For frontend edits install Node.js 22 LTS x64, run `npm ci`, then `npm run build`; CP serves `dist`, not raw JSX. The normal private launcher does not automatically rebuild source edits. Tests and package-lock.json are included. Python tests must use `CP_TEST_MODE=1` and a unique `CP_TEST_ROOT` under OS-temp, never recipient media/data. PowerShell example:

```powershell
$env:CP_TEST_MODE='1'
$env:CP_TEST_ROOT=Join-Path $env:TEMP ('cp-friend-tests-'+[guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m unittest tests.test_friend_test_package tests.test_release_packaging -q
```

Read TEST-PACKAGE.json's verification notes for known failures and limits. Do not interpret source tests or package smoke checks as verification on the recipient's specific hardware. Cloud/provider availability, account quotas, GPU drivers and native playback require testing on that machine.
