# Native player filename fix — 22 October 2026

Installed **0.1.36**. The running CP server reports the new runtime ready. No backend restart was required: the existing runtime owner reads the selector for each resolution.

## Cause and correction

The native player passed Windows ANSI filename bytes into libmpv, which requires UTF-8 filenames. This damaged `é` in the original Les Misérables path and could replace Arabic characters. The defect was present before the playlist update.

`MpvItem.cpp` now converts paths with `QString::toUtf8()` for main playback, external subtitles, thumbnail playback and image output, and uses Unicode paths consistently in thumbnail identity hashing. `CP_PLAYER_CACHE_ROOT` uses Qt's Unicode environment reader. Media files, catalog identities, IPC/history schemas, playlists, settings and layout are unchanged.

## Verification

- **Failure reproduced before the fix:** installed 0.1.35 returned `playback_failed: Playback failed: loading failed` when the new regression launched the actual Les Misérables file.
- **Native production build:** MSVC 2022 x64 / Qt 6.10.3 / original pinned libmpv build succeeded.
- **Final relevant suite:** 137 tests passed, no failures/skips. Includes player, native player, configuration, runtime, protocol, catalog, manager, queue, playback history and TV vertical slice tests. This is the full relevant suite, not the unrelated full application suite.
- **Real executable checks:** five passed against the staged runtime and five passed again against the installed runtime. Cases: original Les Misérables, Arabic filename with Arabic external subtitle, Arabic folder with accented filename, ASCII filename, and an Arabic external subtitle on an ASCII video. Assertions include actual duration, advancing progress, audio presence, subtitle selection where requested, and clean shutdown.
- **Original Les Misérables:** `E:\Movies\Les Misérables (2012) [1080p]\Les.Misérables.2012.1080p.BrRip.x264.YIFY.mp4`. Installed runtime reported duration **9,474,453 ms**, advanced to **4,838 ms**, exited normally, and rendered video was visually inspected. [Capture](les-miserables.png).
- **Arabic subtitle rendering:** selected external subtitle `ترجمة.srt`; Arabic text was visibly rendered over the `فيلم.mp4` fixture. [Capture](arabic-filename.png).
- **Real timeline/thumbnail check:** Arabic directory plus accented filename played; click seek reached 120,167 ms and drag seek reached 142,706 ms. A real JPG was generated within the exact `ذاكرة/seek-thumbnails/...` cache directory. The test checks the requested Unicode directory, not a surrounding folder. [Capture](timeline-timeline-preview.png).
- **Installation validation:** all **1,366** manifest inventory entries passed SHA-256 validation. Executable SHA-256: `0965456023F9462D8C7C32D37B6C3093F70CC28AD0BA1061CD90326D7BDECA6D`.
- **Independent focused code review:** initial test assertion corrected; final review found no remaining important issues in the scoped changes.

These checks use authenticated private test pipes and isolated APPDATA, LOCALAPPDATA and cache roots. They read the original movie but do not create production playback sessions, change watch history or alter media files. Live production evidence is runtime selection/status; actual playback evidence comes from the installed executable connected to the isolated harness. Test player processes were closed.

## Failures corrected during verification and limits

The first staged run failed one assertion after playback had succeeded: the test assumed at least two exposed tracks. CP exposes audio/subtitle tracks rather than video tracks, so a file with one audio track can legitimately expose one track. The corrected test checks advancing playback instead; video was also inspected visually.

The first timeline attempt failed an existing pause assertion when its two quick single clicks were interpreted as a double click. The harness now waits Windows' configured double-click interval between these two distinct single-click checks; both original assertions remain, and the final timeline check passed. No production input behavior changed.

Qt deployment warned about missing translations/software compiler discovery/DX compiler DLLs. The compatible original runtime support files were retained, including software OpenGL and 37 translations; the assembled runtime passed integrity and real rendering checks. Raw build output is retained in build.log.

Native screenshot saving's filename conversion is corrected but was not exercised separately. Window captures above use PIL; the thumbnail check does exercise real libmpv image output into a Unicode path. This fixes the demonstrated Unicode filename defect; other unnamed playback failures have not been classified.

## Recovery

Source and prior selector backup: `C:\Users\dante\.codex\backups\cp-player-unicode-20261022-200026`.

The previous runtime 0.1.35 remains intact. Restore its saved `runtime/player/current.json` to roll back runtime selection; source restoration must preserve any subsequent edits. Unrelated dirty source was preserved. No commit, push, tag, release or shutdown was performed.

Owner rule: **Qt filesystem paths stay Unicode until a library boundary; every filename passed to libmpv is explicitly UTF-8 on Windows.**
