# Native player Unicode filenames

**Status:** Implemented, installed and live runtime selection verified, 22 October 2026. Dante: “go fix it rebuild and install the player and test it with Les Misérables and Arabic filenames”.

## Problem and decision

- Les Misérables (2012) exists and its stored probe is successful, but recent sessions record no duration/progress. MpvItem passes QFile::encodeName bytes (Windows ANSI) to libmpv, which requires UTF-8 on Windows. The existing system ANSI page is 1252; é is consequently invalid UTF-8. Arabic characters also cannot survive this conversion.
- Correct every native filename boundary to libmpv. Preserve names, paths, media files, playlist/settings behavior and history identity. No open product decisions.
- This defect predates the playlist update. Runtime reproduction is required before claiming it explains the observed failure. Other failures remain unclassified.

## Contracts affected and contract-change decision

| Contract/source | Agreed behavior | Callers | Proposed behavior | Contract change? | Decision |
| --- | --- | --- | --- | --- | --- |
| Trusted local playback | Open the selected existing local file | Movie/TV manager → PlayerBridge → MpvItem | Preserve the complete Unicode path at mpv boundaries | No | Approved fix |
| External subtitles, screenshots, seek thumbnails | Read/write the requested file | MpvItem | Same operation with UTF-8 filenames | No | Approved fix |
| Queue/settings/history | Existing 0.1.35 behavior | Native bridge and backend | Unchanged | No | Preserve |

## Current design and ownership

Desktop checkout is master at be511f9 with extensive unrelated tracked/untracked changes, including the approved 0.1.35 feature work. Back up the touched source files and runtime selector; never reset this checkout. Live Python PID 5264 serves port 5000 and selects runtime 0.1.35. Configuration/history remain in the existing data owner; verification instead uses private named pipes and temporary APPDATA/LOCALAPPDATA/cache roots. Served React assets index-fNsBSLQr.js/index-C4xx5e9F.css are unaffected.

| Responsibility | Owner | Existing path | Preserve/retire |
| --- | --- | --- | --- |
| File resolution/authentication | player_catalog.py / player_manager.py / PlayerBridge | Selected catalog identity → authenticated pipe load | Preserve |
| All mpv commands and filename conversion | native/player/src/MpvItem.cpp | Main load, external subtitle, screenshot, thumbnail worker | Replace ANSI conversion with QString::toUtf8; no second path owner |
| Thumbnail identity/cache environment | MpvItem.cpp | Hash path and read CP_PLAYER_CACHE_ROOT | UTF-8 hash input; Windows Unicode environment via qEnvironmentVariable |
| Immutable runtime assembly/selection | tools/assemble_player_runtime.py / services/player_runtime.py | Stage → manifest/hash inventory → current.json | New 0.1.36 bundle, retain 0.1.35 rollback |

## Exact behavior contract

No UI layout or React changes. A path such as `Les.Misérables.2012.mp4` or `مجلد/فيلم.mp4` must produce real duration, audio/video tracks and advancing playback. External subtitle filenames follow the same conversion. IPC and persistent history schemas do not change; failures still use existing error handling. Runtime installation changes only the version selector after validation. No backend restart is needed if the live resolver reads its selector for each launch; verify this in current code.

## Implementation sequence

1. Add opt-in native executable regression tests around the existing production smoke harness. Run the accented case against 0.1.35 and observe a real playback failure. Restore pinned Qt 6.10.3 SDK in a task temporary directory and use the existing pinned libmpv DLL/headers.
2. Change the existing MpvItem filename conversions and cache environment read. Bump runtime metadata to 0.1.36. Build with existing MSVC/Ninja script and assemble a new immutable runtime. Preserve original runtime files/licenses/software OpenGL support.
3. Run regression cases with an ASCII fixture, Arabic basename, Arabic directory plus accented basename, and the real Les Misérables file. Assert duration, tracks, advancing position and clean exit. Exercise existing timeline/subtitle checks where applicable. Run the full relevant player Python suites in unique CP_TEST_ROOT with CP_TEST_MODE=1.
4. Review the bounded diff; validate the full runtime inventory, back up current.json, install/select 0.1.36, verify live status and repeat production-file/Arabic playback using the installed executable with private test sessions. Report exact results and limits.

## Acceptance matrix

| Scenario | Action | Expected | Evidence |
| --- | --- | --- | --- |
| Real Les Misérables 2012 | Private session loads original E: file | Duration > 0, audio/video tracks, advancing position | Native regression + screenshot |
| Arabic basename | Load temporary fixture | Same playback success | Native regression |
| Arabic directory / accented basename | Load temporary fixture | Same success without path replacement | Native regression |
| ASCII / ordinary playback | Load original synthetic fixture | Same success | Native regression |
| External Unicode subtitles | Existing subtitle IPC/UI flow | Selected external subtitle track | Native smoke |
| Seek thumbnails / Unicode output root | Existing timeline smoke with Unicode temp roots | Generated thumbnail file and working seek | Native smoke |
| Missing/invalid files, trusted IPC, queue/history/settings | Relevant existing suites | Existing rejection and state behavior retained | Python suites |
| Installed result | Query status and run installed helper | 0.1.36 ready, actual playback passes | Status + fresh smoke |

## Verification and rollout

Use tests/test_player_unicode_runtime.py with explicit CP_NATIVE_TEST_* fixture settings; ordinary unit runs skip this Windows/executable-dependent integration suite. Runtime smoke uses no production backend session and writes no production history. Run relevant tests/test_player*.py and tests/test_native_player*.py with unique OS-temp test roots. Do not run the unrelated full app suite or any catalog/storage benchmark for this bounded native fix.

Build/assembly logs and regression reports go in docs/verification/native-player-unicode/. Restore current.json to 0.1.35 if installed manifest/status/playback validation fails. Retain both runtimes. No commit, push, tag, release, shutdown or unrelated restart is in this approval.

## Completion evidence

- Existing 0.1.35 reproduced `playback_failed: Playback failed: loading failed` on the original Les Misérables file before production edits.
- All six filename/hash conversions and Unicode environment reading corrected in the existing MpvItem owner; no compatibility path or second implementation.
- Native build and runtime assembly succeeded. Final relevant suite: 137 passed; staged and installed real executable regressions: five passed each. Independent focused review found no remaining important issues.
- Les Misérables reports duration 9,474,453 ms and reached 4,838 ms in the installed check; its rendered video was inspected. Arabic file/folder and external subtitle checks pass. Separate real timeline check generated a JPG under the exact Arabic cache path and verified click/drag seeking.
- Test correction: the protocol intentionally exports audio/subtitle tracks only. Replaced an invalid total-track-count assumption with advancing progress assertions and inspected rendered video. Existing UI smoke needed Windows' double-click interval between two intended single-click checks; preserved both checks and the final run passed.
- Live `/api/player/status` selects ready 0.1.36 without a backend restart. All 1,366 runtime inventory entries passed SHA-256 validation. Old 0.1.35 remains available; source/selector recovery is at `C:\Users\dante\.codex\backups\cp-player-unicode-20261022-200026`.
- Product contracts preserved. Native screenshot saving's Unicode path conversion was corrected but not separately exercised; window captures are visual evidence, while the thumbnail test proves actual libmpv image output to a Unicode path. Broader causes of other unnamed failing movies remain unclassified.
