# Cinema Paradiso private test — Codex handover

This is a private Windows 11 x64 test copy. Start with this file before changing anything. It includes working source, compiled frontend and saved API/service settings. It contains private credentials: do not publish this folder, print its settings, upload its logs without checking them, or commit config/data/runtime. No Git history or remote credentials are included. The original CP installation belongs to Dante and is outside this package.

## First launch

1. Download/copy the **whole folder**, keep all OneDrive files available locally, and preferably extract/copy it outside a folder being actively synchronized before running. Runtime databases and bundled binaries need local access.
2. Start your installed Ollama if you want AI. Run `run.bat`: it creates a local `.venv` and installs `requirements.txt` on first launch, connects to your Ollama, then starts bundled FlareSolverr, Prowlarr and CP. It opens CP's existing desktop window. The compiled frontend is included; Node is not needed just to launch. Missing Ollama shows a console notice but does not block CP.
3. Keep the launcher console open. Use Ctrl+C or `Stop CP.bat` to stop its services. Do not close/kill other CP installations or system services.
4. AI uses the saved `nemotron-3-super:cloud` model through your Ollama. Internet and your own Ollama account are required for this model. If you are already signed in, keep that login. Otherwise run `Ollama sign in.bat` once and complete the browser login with your account. The helper uses your installed CLI and your own account storage. No Ollama binary, model weights or Dante's login are included.

If Python is missing, Codex can install Python 3.12 x64, reopen the terminal and run `run.bat` again. Example: `winget install --id Python.Python.3.12 --exact --accept-package-agreements --accept-source-agreements`. Prowlarr, FlareSolverr, FFmpeg, native player and qBittorrent are included; Ollama is external.

## Ollama setup for the recipient's Codex

1. Inspect the recipient's existing Ollama first: `Get-Command ollama -ErrorAction SilentlyContinue`, then `Invoke-RestMethod http://127.0.0.1:11434/api/version`. A working version response means CP can connect. Reuse their installation, models and login; do not install a second copy or change their global settings.
2. If installed but not running, ask the recipient to open Ollama from Start. If absent, explain that AI needs Ollama and install the Windows application from [Ollama's official download](https://ollama.com/download/windows), then open it. Follow [official Windows setup](https://docs.ollama.com/windows). Reopen the terminal if PATH has changed. Do not download Ollama into this CP package.
3. This copy defaults to `http://127.0.0.1:11434`. If their Ollama uses another address, enter that address in CP Settings under Ollama. The existing `/api/ollama/config` owner persists URL/model, and the package launcher preserves that address across restarts and moves. Leave Prowlarr/CP ports unchanged.
4. Keep `nemotron-3-super:cloud` unless the recipient chooses another available model. Use their existing login, or run `Ollama sign in.bat` / `ollama signin` against their local Ollama. For a server on another computer, sign in on that server. [Cloud setup](https://docs.ollama.com/cloud) explains account access; no local weights are required for cloud models. If an older CLI does not support cloud/sign-in, explain the need to update the existing installation.
5. In CP Settings use **Test Model** to verify the selected model produces a valid response, then **Save Ollama** to persist the URL/model and try one Ask AI request. Saving also validates the chosen model. `/api/version` proves connection only; it does not prove account/model access. Do not scan every cloud model or download a large local model without the recipient choosing it.
6. If Ollama is offline or stopped later, CP still runs; its AI features report the connection failure. Start Ollama and retry. Stopping this CP package never stops or modifies the recipient's Ollama. No account credentials should be printed or added to Git.

## Ownership and layout

- `app.py`, `services/`, `src/`: original CP authoritative owners. UI/design behavior has not been rewritten for the package. Root AGENTS.md still applies to development; this package handover explains launcher/runtime differences.
- `tools/build_portable_release.py`: one application-copy owner shared by public/private packaging. `build_release_zip` excludes personal settings; `build_friend_test_folder` is explicitly private.
- `tools/friend_test_launcher.py`: private service supervision and relocation, started by this copy's `run.bat`. It refuses occupied ports, uses a Windows Job Object to contain its children, and stops its own service trees. CP's restart request restarts only its backend while services stay running.
- `config.json`: saved CP credentials/preferences. Initial Movie/TV roots are empty `library/movies` and `library/tv`. No media, personal catalog, lists or active download jobs were transferred. Add the recipient's real roots through CP Settings when needed. The launcher sets `CP_PORTABLE_DATA=1`, so the authoritative movie database is `data/catalog.sqlite`; package-local `LOCALAPPDATA` keeps poster assets under `data/localappdata`. Neither uses the Windows account's shared CP metadata.
- Ollama: recipient-owned external installation at `config.json`'s `ollama_url` (default `http://127.0.0.1:11434`). This package does not start, contain or stop its server. Its existing identity/models remain with the recipient's installation.
- `runtime/prowlarr`: executable and self-contained .NET runtime; `data/prowlarr`: consistent SQLite settings snapshot, configured indexers and local FlareSolverr proxy. No live original database is opened by this copy.
- `runtime/flaresolverr`: executable and its bundled browser; `runtime/ffmpeg`: FFmpeg/FFprobe; `runtime/player`: selected hash-validated native player; `runtime/qbittorrent`: pinned embedded runtime. New qBT state/jobs belong to this package.
- `data/iptv`: saved provider configurations; IPTV catalogs/sessions are initialized normally. Providers still need internet and valid subscriptions and may impose simultaneous-connection limits. Configured Plex access is retained, but Plex itself is not bundled.
- `TEST-PACKAGE.json`: source commit, versions, account-sharing status, ports and validation. `RUNTIME-SHA256.json`: binary inventory. These contain no credentials.

## Ports and verification

| Service | Local port |
| --- | --- |
| CP | 15000 |
| Ollama (external, configurable) | 11434 by default |
| Prowlarr | 19696 |
| FlareSolverr | 18191 |
| Embedded qBittorrent | 18686 |

Open CP at `http://127.0.0.1:15000/`. Bundled services use separate ports; Ollama connects to the recipient's existing service. Do not kill the owner of a busy package port to make it start. Diagnose it first. A bundled-service port amendment must update its launcher/configuration together; changing external Ollama only changes CP's Ollama URL.

The launcher rewrites only package-owned paths on relocation. Paths the recipient selects outside the package stay unchanged. Stop the package before moving it. Never copy someone else's `.venv`; if Python setup is broken or the base interpreter is removed, recreate `.venv` in this copy and install requirements again.

For diagnostics inspect `data/runtime/friend/CP.log`, `Prowlarr.log`, `FlareSolverr.log`; Ollama logs belong to the recipient's installation. Check the configured Ollama address plus `/api/version`, Prowlarr `/api/v1/system/status` using the API key locally without printing it, and CP's Home/Discover/Settings. A loaded provider page is not proof of video playback; verify actual playback separately. No torrent download was initiated during package verification.

## Development and tests

For frontend edits install Node.js 22 LTS x64, run `npm ci`, then `npm run build`; CP serves `dist`, not raw JSX. The normal private launcher does not automatically rebuild source edits. Tests and package-lock.json are included. Python tests must use `CP_TEST_MODE=1` and a unique `CP_TEST_ROOT` under OS-temp, never recipient media/data. PowerShell example:

```powershell
$env:CP_TEST_MODE='1'
$env:CP_TEST_ROOT=Join-Path $env:TEMP ('cp-friend-tests-'+[guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m unittest tests.test_friend_test_package tests.test_release_packaging -q
```

Read TEST-PACKAGE.json's verification notes for known failures and limits. Do not interpret source tests or package smoke checks as verification on the recipient's specific hardware. Cloud/provider availability, account quotas, GPU drivers and native playback require testing on that machine.
