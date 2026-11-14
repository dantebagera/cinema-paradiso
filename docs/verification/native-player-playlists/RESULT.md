# Native player update — 20 October 2026

Installed player **0.1.35** and its backend changes into the Desktop Cinema Paradiso checkout. The current CP process was deliberately not restarted immediately before the requested PC shutdown; the next CP launch loads the updated backend and player together. The React frontend bundle was not changed.

## Delivered

- Settings gear with playback, window/picture, audio/subtitle synchronization, advanced actions and a reference showing the configured keyboard shortcuts.
- Always on top is visible and adjustable through Settings or T. The running app's saved enabled preference was changed to **off** through its existing configuration API.
- Previous / Play-Pause / Next file controls, with destination tooltips. Ten-second seeking remains on Left/Right and in Settings; minute seeking remains available too.
- Playlist overlay: TV episodes grouped by season, or movie collection members ordered by full release date/year. The current file is highlighted and another item can be selected directly.
- A five-second cancellable Up next countdown after actual playback EOF. Reaching the watched threshold never advances the playlist. File changes reuse the same native window/process.
- Missing, unreleased or reconciliation-blocked entries stop progression instead of being skipped. Specials stay in a separate sequence when explicitly opened. A file covering multiple episodes without playback boundaries requires manual selection; uncertain collection membership disables automatic continuation.
- Each file retains its own progress, subtitle state and playback generation. Recent progress is flushed before replacement; stale events and late subtitle results cannot update the next file.

Scope is local/downloaded files played by the CP native player. IPTV and embedded streaming players, acquisition/import behavior, and the existing TV series-card Play selection were unchanged.

## Verification

- Original focused baseline: **61 passed**.
- Final relevant suite in both the isolated worktree and installed Desktop source: **148 passed** (92 player/config/protocol/runtime/route/queue checks; 56 native/history/TV/collection checks). No failures or skips. The unrelated full application suite was not run.
- Independent review: issues were corrected with regression tests; final targeted review reported no remaining important findings and independently passed **19 overlapping focused tests**.
- Native Qt/QML production compilation passed. The pinned Qt 6.10.3 development tools were restored in a task-only temporary directory because old development folders had been cleaned. The original software OpenGL fallback and translations were retained in the staged runtime.
- Real synthetic runtime smoke: S02E03 → S02E04 after EOF/countdown, one process/window, then stopped at missing S02E05. Manual overlay selection and Previous navigation produced a → b → a, with media generations 1 → 2 → 3.
- Final desktop inspection: Settings, CP-styled scrollbar, configured shortcut help, highlighted playlist, unavailable reason, named toolbar controls, and working manual navigation. Settings and T were checked against the same always-on-top state.
- Ordinary single-file synthetic playback passed independently, with progress, tracks, duration and clean shutdown. Fixture helper stderr was empty. No production movie/TV file was played and no production watch history was used for testing.
- Installed runtime inventory: **1,361 files**, full SHA-256 validation passed. Player EXE SHA-256: `039ce0af29ed15f701da60916f601c9156779d882fc1019f4e7fdb5b0783060c`.
- All promoted task files matched verified source before the final documentation update. The pre-existing Desktop app.py changes were compared exactly and preserved. The incidental aqt tooling log was restored to its original clean contents. No commit, push, tag or release.

Screenshots: [Settings](settings.png), [shortcut help](shortcuts.png), [playlist](playlist.png). Raw smoke logs, state records, build log and installation inventory are alongside this report.

## Recovery and activation

Recovery copies of every replaced/deleted source file, original configuration and original runtime selector are at:

`C:\Users\dante\.codex\backups\cp-player-playlists-20261020-041140`

Old runtime 0.1.34 remains intact. Rolling back requires restoring the task files and selector/config from that backup, preserving any newer unrelated edits. Do not reset or clean the checkout.

The native runtime selector is switched to 0.1.35 after verification. Existing Python PID 38088 still holds the old backend in memory until shutdown; this report does not claim a production-media playback test or a backend restart. Next CP startup uses the installed backend source and matching 0.1.35 runtime.

## Shutdown

Authorized by Dante after task completion. A task-owned helper requests the existing CP device power action, which checkpoints CP work and calls Windows normal shutdown without forced application termination. See `shutdown-request.json` for dispatch evidence after the helper runs. An operating-system unsaved-work blocker is not bypassed.
