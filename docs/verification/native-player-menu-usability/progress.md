# SDD ledger — plan: docs/plans/2026-10-24-native-player-menu-usability.md

Approval: Dante approved implementation, isolated tests, rebuild and installation in the source chat; explicit handoff preserved above. Execute inline, one independent final review, no commits.

Baseline: master be511f98846a67a182e5b371ad087938e9344362, extensive existing dirty work. Persistent pre-task file/selector backup: C:/Users/dante/.codex/backups/cp-player-menu-usability-20261024. Tests and build root: C:/Users/dante/AppData/Local/Temp/cp-player-menu-usability-20261024.

Baseline tests: 137 passed, 0 failed/skipped (baseline-python.log). No player process and no listener at port 5000 when checked. Selector/metadata choose 0.1.36. Do not start CP for a status check.

Ruling: Edit the approved dirty Desktop checkout in place and isolate test/build data in OS temp — the handoff expressly requires preserving existing native edits and forbids a bare-HEAD build; a new worktree would omit those dependencies. Cost if wrong: shared source edits require comparison against the persistent pre-task backup.

Ruling: Keep this durable ledger and artifacts instead of skill scratch scripts/commits — the approved plan forbids commits and provides its own four tasks and acceptance matrix. Cost if wrong: recovery uses file deltas rather than task commits.

Pre-flight: Tasks 1–3 share Main.qml and CMake registration. Task 4 consumes all new shared QML types through a generated test-only import stage and compiled production module. No interface conflict found. Media type must come from the bridge, never labels.

SDK: pinned production Qt inputs exist, but its QuickTest libraries/imports were removed. Fetch the same pinned Qt 6.10.3 qtbase/qtdeclarative into this task's temporary SDK for the test runner; do not modify the prior SDK.

Task 1–3 component red gate: qml-red-valid-details.log, 12 passed / 10 failed. Failures reproduce flat TV seasons, scrollbar paint/activity and popup outside-click leakage. Preserved movie/index/missing-row cases already pass. Native installed 0.1.36 singleton button assertion failed with capture (baseline-native-singleton-red.log).

Task 1–3 component green gate: qml-green-details.log, 22 passed / 0 failed / 0 skipped (16 behavior tests plus 6 setup/cleanup). Actual production shared components, Qt 6.10.3 Basic style, real pointer/key events.

Harness repairs before valid red: TestCase is invisible by default; explicitly show it. Match production Basic control style. Send QtTest output to a file because this Windows runner did not expose console output to CTest. Wait for actual Column layout before clicking S06E20. None of these change production contracts.

Ruling: Qt 6.10.3 does not expose Accessible.expanded in QML; season buttons expose a checkable/checked toggle and Expanded/Collapsed description with the season name. Cost: screen readers announce toggle state instead of a tree expansion state.

Build failure: original pinned SDK also lacks syncqt.exe and cannot configure a fresh build. Use newly downloaded complete Qt 6.10.3 qtbase/qtdeclarative for production as well; same pinned version/compiler. Seed staging from 0.1.36 to preserve its SVG plugin, software OpenGL, translations and licenses, then replace compiled/deployed files. Full inventory validation remains required.

Compiled checks exposed and corrected: ListView horizontal attached bar was null (startup failed with exit 3); removed invalid assignment and made ListView vertical-only with fixed content width. Explicit QtQuick.Controls.Basic imports allow CP custom painting without native-style rejection. A native current-row capture exposed nested Column layout timing; settle nested layout before ensuring current row/header visibility. Added actual viewport regression (qml-viewport: 23 passed).

Adverse coverage added: real wheel/drag and outside double click. The double click test failed against bare Qt popup modal closure (qml-doubleclick: 24 passed / 1 failed). Guard iterations exposed Qt Overlay signals emitted for inside clicks and already-closed popup instances. Do not treat intermediate qml-guard/gesture logs as final passing evidence. Native test harness also required status=complete/error for subtitle.results, real physical desktop scale normalization, and scrolling before resolving offscreen UIA rows. A diagnostic run overlapped a QML runner and is discarded; run UI suites serially.

Long fixture: synthetic 180-second MP4 with 14 audio, 28 subtitle tracks and 40 chapters, long/Arabic labels; 1,609,061 bytes, generated with finite ffmpeg stream-copy work. Providers remain offline; test IPC only. No production media/config/history modified.

Task 1–3 final shared-component gate: qml-bound-popup-details.log, 26 passed / 0 failed / 0 skipped (20 behavior checks plus 6 setup/cleanup). Added Main-like visibility-bound opener and derived close callbacks. Guard expiry is awaited as an observable state, not assumed from a fixed sleep. The final shell uses completed-release state and synchronous internal Connections onClosed; no hover/press heuristics, custom overlay or full-window catcher remains. Main directly guards TapHandler/WheelHandler and underlying controls. A selected row's intentional close also receives the brief system double-click guard.

Final review: two P2 findings accepted (independent-review.md). Real compiled red cases: title strip returned HTCAPTION=2; outside double click minimized/closed the private test player. Single fix pass: windowControls joins Main's guard; WindowsWindowChrome reads Main's derived blocksWindowGestures state and returns HTCLIENT while ordinary menus/guard are active. All three corresponding compiled green cases passed (chrome-green-*.log). Native owner extension is recorded in the plan and pre-edit Chrome source is persistently backed up.

Final Python after review: 137 passed / 0 failed / 0 skipped (python-after-review.log).

Native track/chapter/speed actions: passed (actions-staged.log). The first fixture used identical track fingerprints; regenerated uniquely titled audio/subtitle streams in synthetic Matroska (the issue was in the test fixture, not a production track change). Actual EOF Cancel, Play now, natural advancement: all 3 passed (autoplay-*.log).

Frozen-scope stop rule after Dante's timing concerns: one bounded remaining full menu pass at 150% and 250%, then only the already-planned immutable installation/integrity and representative installed checks. No additional acceptance scenarios or broad reruns. Final 150% pass succeeded (final-150.log), including singleton/empty/last/missing queues, TV selection/reopen, ordinary menus in both states, double-click/timeline consumption and resume.

Assembly validated all 1,366 files and 6 license entries, retained 0.1.36 inventory, pinned mpv hash unchanged. Exact staged inventory/hash in staged-inventory.json. Installation pending remaining frozen gate.

STOPPED: Dante said "enough really". No further tests, build, installation or task work. Selector unchanged at 0.1.36. RESULT.md records the last verified state and pending gates. Resume only on a new instruction from Dante.

INSTALLATION: Dante clarified stop testing, install now. Existing 0.1.37 assembled candidate installed immutably, all 1,366 hashes / 6 licenses verified before atomic selection, runtime owner status ready. No further playback/UI tests or backend restart. 0.1.36 retained; selector backup in installation.json.
