# Native player menu usability implementation plan

**Status:** Execution approved, 24 October 2026. Dante said “ok open a new task , hand it over the plan and implement”. The approved proposal covers the four changes below, isolated testing, native rebuild and installation, executed inline with one independent final review. No backend restart, active-user-player termination, production data change, commit, push or release is authorized.

**Execution record:** `docs/verification/native-player-menu-usability/progress.md` records current evidence and decisions. Earlier “execution pending” statements below describe the planning baseline and are superseded by this approval.

**Goal:** Hide unhelpful single-item playlist controls, make TV seasons collapsible, match Home's thin CP scrollbars, and dismiss player menus with an outside click.

**Architecture:** Keep queue membership/order in the existing backend owners. Extend the native bridge only to expose the media type already present in the authenticated load message. Use shared native QML components for playlist presentation, scrollbar painting and menu dismissal; retire the replaced inline/default implementations.

**Tech stack:** Existing Qt 6.10.3 / QML / C++20 / MSVC 2022 / pinned libmpv. Native desktop only.

**Spec:** The agreed behavior and exact contracts below are the design specification for this small amendment; no separate redesign is proposed.

**Execution recommendation:** Implement inline in this chat, with one independent final code review. Do not dispatch a separate implementer for each component. Preserve the dirty checkout and use temporary fixtures/builds for isolation. No commits are included.

## Problem and decision

| Requested change | Current evidence | Agreed result |
| --- | --- | --- |
| Useful playlist button | `Main.qml` playlist `CpIconButton` has no visibility condition. Dante's screenshot shows a menu containing only The Others. | Hide the button for zero/one queue item; show it for two or more, including when playing the last item. |
| Collapsible TV seasons | Playlist `Repeater` renders section labels and every episode in one column. | Opening the menu expands the playing episode's season and collapses all others. Expanding another season collapses the previous one. |
| Thin CP scrollbars | Only the side panel has a custom 4px thumb. Audio/subtitle/chapter ScrollViews and subtitle-search ListView retain default Qt bars. The supplied screenshot shows white vertical/horizontal bars. | Use Home Following's 2px gold Reveal line, transparent track, wider invisible drag area and interaction-based visibility across player scrolling menus. |
| Outside-click dismissal | Most menus are Rectangles; background playback input is disabled while open but does not dismiss them. Speed alone is a Popup with an outside-close policy. | Outside click closes the open menu and consumes that click. It must not also pause, seek, change volume, select a file or activate a control behind the menu. Inside interaction remains usable. Close/Back controls and Escape remain available. |

The season behavior was explicitly confirmed by Dante: “open with the playing episode season expanded and rest collapsed and yes one at a time”. The other rows restate the behavior agreed in this conversation. Implementation and live activation remain pending.

**Scope:** Local native player menus: playlist, Settings/shortcut help, audio/subtitle tracks, chapters, subtitle search and playback statistics; speed joins the same dismissal behavior. Existing dimensions, panel positions, typography, colors, row actions and playback behavior remain except for the four requested amendments.

**Excluded:** React/Home changes, mobile, IPTV/embedded players, queue membership/order/availability, acquisition/import, history schemas, autoplay rules, resume-choice semantics, theme redesign and new persistent preferences. The resume decision and Up next countdown are not ordinary dismissible menus.

**Open decisions:** No unresolved product decision blocks this design. Proposed execution approval covers source changes, isolated verification, native rebuild and installation as detailed below. It does not include closing Dante's active player or restarting CP.

## Contracts affected and contract-change decision

| Contract/source | Existing agreed behavior | Proposed behavior | Contract change? | Decision |
| --- | --- | --- | --- | --- |
| This conversation: playlist visibility | Button useful only for lists with another item | `queue.items.length > 1`; last-item position does not hide it | Explicitly requested presentation change | Behavior agreed; execution pending |
| This conversation: seasons | Playing season expanded on open; one expanded at a time | TV accordion; movie collections stay flat | Explicitly requested presentation change | Exact season rule confirmed |
| Home Reveal line / scrollbar request | Thin gold interaction scrollbar | Native QML equivalent using the existing PlayerTheme gold | Explicitly requested presentation change | Behavior agreed; execution pending |
| Outside-click request | Dismiss without activating the background | One shared native popup rule | Explicitly requested interaction change | Behavior agreed; execution pending |
| Existing queue plan/tests | Missing/unreleased/review items stay visible and block advancement; no wrapping; Specials separate | Preserve all items and original indexes, including unavailable entries | No | Preserve |
| Existing native playback contracts | Authenticated file resolution, per-file generations, same-window transitions, resume/history/subtitle ownership | UI sends the original selected queue index/key through existing bridge methods | No | Preserve |
| Unicode fix, installed 0.1.36 | UTF-8 filenames work for playback/subtitles/thumbnails | No MpvItem changes; retain fix in new bundle | No | Preserve |

Existing tests that assert the literal speed `CloseOnPressOutside` source line test an implementation detail. Update those only as needed for the shared owner, backed by real outside-click/no-click-through tests. Do not weaken their user-visible speed-control assertions. There is no known conflicting agreed product rule requiring a separate contract-change decision. Stop and raise the repository's contract-change notice if one is discovered during execution.

## Current design and ownership

Read-only baseline captured on 24 October 2026:

- Checkout: `C:\Users\dante\Desktop\cinema paradiso`, branch `master`, HEAD `be511f98846a67a182e5b371ad087938e9344362`. Extensive unrelated tracked and untracked work is present. Native files also contain prior approved, uncommitted feature/fix work; HEAD alone is not a usable source baseline.
- Live backend: Python PID **55244**, launched through venv PID **32668**, owns `127.0.0.1:5000`. Native PID **38892** is currently running from installed **0.1.36**. Do not close, replace or use that session for tests.
- `runtime/player/current.json`, source build metadata and live `/api/player/status` all select ready **0.1.36-qt6.10.3-mpv20260610-lgpl-cp2.8.5**. No full integrity scan was run during planning.
- Live served and disk frontend agree on `index-CwW9dSyz.js` / `index-3_nuXu-W.css`. This work does not rebuild or modify those React assets.
- Configuration points to Desktop `data` and `cache`. Do not use either for tests or print provider credentials.
- Pinned Qt SDK and mpv headers remain under `%TEMP%\cp-player-unicode-20261022`; `qmake.exe` and headers were found. Revalidate those inputs before building; do not assume old build outputs prove current source.
- The previous report's 137 checks and installed playback proof describe 22 October, not a current test baseline. No tests, builds or playback were run for this plan.

| Responsibility | Authoritative owner and path | Preserve / replace |
| --- | --- | --- |
| Movie/TV queue membership | `services/player_queue.py`, `services/tv_playback.py`, existing collection provider | Read only; preserve membership, chronology, missing items and limits |
| Queue delivery/selection/history | `PlayerManager` → authenticated load → `PlayerBridge` | Preserve protocol/generation and re-resolution |
| Native media type | `media.media_type` already sent by existing TV resolver | Expose read-only `PlayerBridge.mediaType`; do not infer TV from labels or titles |
| Playlist presentation | `native/player/qml/Main.qml` side panel | Extract the current playlist rows into `CpPlaylistContent.qml`; no second queue owner |
| Scrollbars | Web reference: `src/styles/scrollbars.css` plus `src/utils/scrollbarActivity.js`; native controls in Main | Add one native `CpRevealScrollBar.qml` and `CpScrollView.qml`; remove replaced inline/default bars |
| Menu open/close state | Main's existing menu flags, `sidePanelMode`, `closeOverlays()` and speed Popup | Add `CpMenuPopup.qml` as the common interaction shell; keep Main as the single state coordinator |
| UI controls/theme | Existing inline `CpButton`, `CpIconButton`, generated `PlayerTheme.qml` | Reuse/extract the existing CpButton once so playlist content shares it; do not duplicate button JSX/QML or edit generated theme |
| Build/runtime | `native/player/CMakeLists.txt`, build script, metadata, runtime assembly/selector | Register new QML files, produce immutable 0.1.37, retain 0.1.36 |

### Implementation approach

Use a shared `Popup` shell, embedded in the existing window, for ordinary menus. This corrects the current split between painted Rectangles and speed's Popup. A separate full-window click catcher would require competing hit-testing and stacking rules for every panel; copying one into each menu would perpetuate the inconsistency. No broader UI framework rewrite is needed.

Qt's modal popup overlay consumes input rather than forwarding it underneath. Configure `popupType: Popup.Item`, `modal: true`, `dim: false`, `focus: true`, and `Popup.CloseOnEscape | Popup.CloseOnReleaseOutside`. Closing after the completed outside click keeps the underlying playback handler disabled throughout that gesture. Verify this on the pinned Qt build, including double clicks and drags; source configuration alone is not proof. [Qt Popup behavior](https://doc.qt.io/qt-6/qml-qtquick-controls-popup.html#closePolicy-prop).

## Exact behavior contract

### 1. Playlist availability and TV seasons

- `Main.qml` owns a derived `hasPlaylist = queueItems.length > 1`. Bind the toolbar button's `visible` and effective keyboard focusability to that value; the Row reflows without a blank slot. No change to Previous/Next behavior.
- Count all authoritative queue entries, including unavailable members. One local movie plus another known missing collection member still has two entries and keeps the button. Filtering those out would violate the existing queue contract. A genuinely single-entry list hides it.
- Hide during the initial empty state. Recompute after a successful replacement load/queue update. If an ordinary playlist is already open and its queue becomes zero/one, close it; keep existing blocker/error information available through the current warning paths, using the existing toast for a singleton fallback error rather than silently losing the message. Do not re-notify the same error on preference-only queue signals.
- Expose `QString mediaType READ mediaType NOTIFY mediaChanged` in PlayerBridge from the current authenticated `media` object. Values for presentation are `tv` or `movie`; omitted/unknown values use ordinary movie presentation, preserving older load fixtures. No new protocol field or backend deployment is necessary.
- `CpPlaylistContent.qml` consumes `items`, `currentIndex`, `mediaType`, `switching` and `resumeDecisionPending`; emits `itemSelected(int queueIndex)`. It renders the existing CpButton style and existing unavailable reasons. It never resolves a file or changes membership/order.
- Movies remain a flat chronological list with their existing year headings. TV uses each existing `section` as a season identity/label, preserving encounter order. Retain the existing separate Specials sequence when supplied; do not merge it into regular seasons. Empty/malformed sections retain their episodes under a plain Episodes heading rather than dropping rows or inventing a season number.
- On every menu opening, reset expansion to the section containing `currentIndex`. Expand exactly that season; keep all other headers visible and their episode rows out of layout and keyboard navigation. Mark the current episode with the existing highlight/play indicator. After layout, ensure that episode is visible within the existing side scroll area.
- Season headers reuse CpButton styling, with a chevron for expanded/collapsed state, accessible name and expanded state. Header height remains that of the existing ordinary playlist button, with current 6px row spacing, 11px gold section labels and 13px episode text. Do not change the side panel's 440px maximum width, 16px content margins or current sizing formula.
- Clicking an expanded header may collapse it; clicking another opens that one and closes the previous one. There is never more than one expanded season. Preserve the clicked header's visibility when content shrinks. Opening the menu again always restores the playing season, not the last browsed season.
- A successful file switch while the menu is visible resets expansion/highlight to the new playing episode. Pending/failed switches do not pretend a different episode is playing. Expansion changes never start playback or send `queue.select`.
- Selecting an episode emits its original flat queue index even after grouping. All availability checks, missing-item reasons, resume decisions, autoplay and chronological Previous/Next remain with their existing owners.

### 2. Shared native Reveal line

- `CpRevealScrollBar.qml` extends ScrollBar; `CpScrollView.qml` extends ScrollView and installs it. Use the same bar directly on the existing subtitle-result ListView. This is a native adaptation of the web reference, not a second CSS stylesheet.
- Vertical drag area is **8 logical pixels**, with **3px transparent padding on either side** leaving a **2px visible thumb**. Rounded line, transparent background/track/corner, no arrow controls. Use `PlayerTheme.projectorGold` at 72% opacity for reveal and 100% while the thumb is hovered/pressed.
- Reveal while the viewport is hovered, focus is inside its content, the bar is dragged, or scrolling is active; retain reveal for **900ms after scrolling**. Fade paint over **120ms**, matching the Home owner. Scrolling and focus must not be moved by the reveal logic. No white platform thumb or background in any state.
- Bars exist only when content overflows vertically. Keep `contentWidth: availableWidth`, constrain every content Column/delegate to that width, and set horizontal policy AlwaysOff. Long track labels keep existing elision and playlist/error rows keep wrapping; do not merely hide horizontally overflowing content behind an off scrollbar.
- Replace all four ScrollView instances: shared playlist/Settings/help, audio tracks, subtitle tracks and chapters. Replace the subtitle-search ListView's default vertical bar with the same owner. Keep speed presets and statistics unchanged where there is no scrolling content.
- Verify short/empty lists show no bar; long lists, long release names, Arabic text and 150%/250% desktop scaling show the thin gold line, preserve wheel/keyboard/drag access, and produce no horizontal bar or white corner.

### 3. Shared dismissal and state coordination

- `CpMenuPopup.qml` owns outside-click/Escape interception and focus containment; Main retains the existing state flags and actions. Migrate the side panel, track panel, subtitle search, statistics and speed to that shell. Keep each panel's current geometry, padding, background opacity, border and contents; only remove obsolete Rectangle input blockers and per-menu dismissal rules.
- Outside press/release closes the open menu and is consumed, including when aimed at the video or another toolbar control. A later separate click may operate that control. Do not forward a double-click to fullscreen or a release to play/pause. Pointer gestures begun inside a menu (including scrollbar dragging) remain usable when the pointer moves outside.
- Inside blank space, row clicks, scrolling, sliders, season headers and subtitle-provider actions remain functional and do not close the menu accidentally. Preserve actions that intentionally close or switch menus today.
- The existing opening button remains a toggle: clicking it while open dismisses the menu. Close buttons remain; shortcut-help Back returns to Settings without closing the shared side popup. Escape closes the current ordinary menu and restores normal player input/focus.
- Do not call global `closeOverlays()` from every Popup's `onClosed`: it also cancels Up next and could close a replacement menu. Synchronize each popup's own closed state only. Keep global close/action transitions authoritative in Main; if factoring, `closeMenus()` handles ordinary menu flags while `closeOverlays()` calls it and retains the existing explicit countdown cancellation.
- When an action switches from Settings to another menu, stale close signals must not clear the newly opened menu. Reopening a dismissed menu must work, with no stale modal blocker or lost focus. Per-file subtitle results continue through the existing generation checks even if a menu was dismissed.
- Resume decisions still require Resume/Restart; outside clicks do not dismiss them or start playback. Up next retains its existing countdown, Play now, Cancel and EOF semantics; ordinary menu dismissal does not cancel or trigger progression. Normal window-close and native playback shutdown paths remain supported.

### Backend, persistence and recovery

No backend service/store/config/schema modification is planned. Existing load payloads, queue snapshots, queue.select keys, generations and error handling stay intact. The small native media-type exposure consumes an existing field only. Accordion/reveal/dismissal state is session UI state and is never persisted. No migration, network retry or catalog operation is needed.

## Implementation sequence

### Task 1 — Playlist visibility and season presentation

Files: Main.qml, PlayerBridge.h/.cpp, CMakeLists.txt; new `qml/CpButton.qml` extracted from the existing inline definition and `qml/CpPlaylistContent.qml`. Add native QML tests in `native/player/tests/qml/tst_PlaylistContent.qml` and runner `native/player/tests/ui_main.cpp`; default production builds do not package test tooling.

- [ ] Snapshot touched dirty files/selector into a persistent task backup. Record fresh relevant baseline tests under a unique temporary CP_TEST_ROOT. Preserve source metadata and exact diffs from the pre-task files.
- [ ] Write component behavior tests (`test_currentSeasonOnOpen`, `test_oneSeasonAtATime`, `test_originalQueueIndexForS06E20`, `test_moviesRemainFlat`) before adding the new behavior. Extract existing playlist markup unchanged so the failing assertions exercise the actual flat implementation, not a missing-type/import error. Cover reopening, unavailable/current/malformed sections and no row/index loss. Singleton/empty/two-entry toolbar visibility and last-item visibility belong to the actual Main window; write those cases in the native smoke early and record their failing 0.1.36 baseline before changing visibility.
- [ ] Expose bridge mediaType; extract/reuse the existing CpButton; implement the playlist content owner and Main wiring/visibility. Register QML files once. Preserve all other uses of CpButton.
- [ ] Run playlist component tests and existing queue/manager tests. Verify the complete typed TV load → mediaType → rendered TV grouping path in the later native smoke, not by parsing section text.

### Task 2 — Scrollbar parity across menus

Files: new `qml/CpRevealScrollBar.qml`, `qml/CpScrollView.qml`; Main.qml, CMakeLists.txt; new `native/player/tests/qml/tst_PlayerScrolling.qml`.

- [ ] Write failing QML tests using real shared scroll controls with short/long text: 8px drag width/2px painted line; no overflow means no bar; overflow reveals on hover/focus/wheel/drag; 900ms activity lifetime; correct content width/no horizontal bar; selecting/scrolling inside does not dismiss. Assert geometry/state and scrolling results, not source strings.
- [ ] Replace every listed native scrollbar owner; remove the old side panel's inline scrollbar paint and default scrollbar instances. Reuse PlayerTheme color values; do not edit Home CSS or generated PlayerTheme.qml.
- [ ] Run QML tests, then inspect actual compiled short/long audio/subtitle/chapter/search/playlist/settings/help menus at desktop scaling. Compare with Home Following and supplied screenshots.

### Task 3 — Consistent outside-click dismissal

Files: new `qml/CpMenuPopup.qml`; Main.qml, CMakeLists.txt; new `native/player/tests/qml/tst_MenuDismissal.qml`.

- [ ] Write failing tests with the production popup shell above a real clickable background: outside press/release hides it and leaves the background counter zero; inside interaction works; second separate click reaches the background; Escape/explicit Close work; drag from inside is not mistaken for an outside click; reopen and replacing a menu leave no blocker. Exercise both paused and playing state in real smoke.
- [ ] Migrate the five ordinary menu shells and remove redundant blockers. Keep Main's single state coordinator, existing action methods and shortcut toggles; synchronize popup closure without global close callbacks clearing another menu/countdown.
- [ ] Run popup tests and all existing native UI/source checks. Update literal implementation assertions only where behavior coverage now verifies the actual shared rule.

### Task 4 — Compiled end-to-end proof and rollout

Files: new `native/player/tools/smoke_player_ui.py`; extend existing smoke helpers only where reusable behavior is required; runtime-metadata.json; new `docs/verification/native-player-menu-usability/RESULT.md` plus logs/captures.

- [ ] Build the Qt Quick Test runner against the pinned SDK; run all component cases. The test-only CMake block stages the actual shared production QML files plus a generated `qmldir` under `<build>/ui-test-imports/CinemaParadiso/Player`, declaring the existing PlayerTheme singleton and shared types. Use that isolated import root in the runner; do not link against an executable, duplicate component source bodies or stub their controls. This avoids needing Main's C++/media objects for component tests. The separate real-executable smoke covers Main and the actual bridge. Test-only fixtures/fakes stay in tests; do not add production debug endpoints or IPC commands.
- [ ] Add a bounded real-executable UI smoke using the existing private named-pipe transport/message helpers, real PlayerBridge and synthetic media. Feed six seasons with at least 20 episodes per season, a collection, a singleton, many long audio/subtitle/chapter rows and subtitle-search loading/empty/error/populated results. Use distinct test keys and original index assertions. Isolate APPDATA/LOCALAPPDATA/cache/history/config and keep fake providers offline.
- [ ] Capture before/after for every menu. Verify actual visibility visually and use protocol events to prove outside dismissal did not pause/seek/select; separately prove internal selection targets S06E20 through the real bridge/manager and reopens the right season. Check Settings/help actions, audio/subtitle selection, speed, missing blockers, resume and EOF countdown.
- [ ] Run the complete relevant Python/native suites, then build/deploy an immutable **0.1.37** bundle. Compare staging with 0.1.36's inventory so compatible software OpenGL/translations/licenses are retained. Validate every manifest SHA-256 before selection.
- [ ] After approved installation, atomically select 0.1.37, verify live `/api/player/status`, and repeat representative checks against that installed executable through private test sessions. Keep active user PID 38892 untouched; it remains on 0.1.36 until Dante closes/reopens it. No CP backend restart is required for this native-only change.
- [ ] Independent final review; fix important findings with regression coverage. Save exact test counts, failures/skips, rendered evidence, inventory/hash and recovery instructions. No commit/push/tag/release/shutdown.

## Acceptance matrix

| Scenario | Action | Exact expected result | Evidence |
| --- | --- | --- | --- |
| Standalone movie / one-episode queue | Load/open controls | No playlist button and no blank toolbar gap; playback/Settings intact | QML + native capture |
| Two collection members, current last | Open controls/menu | Button present; both entries retained and earlier file selectable | Queue regression + native |
| One owned and one missing member | Open playlist | Button present; missing entry/reason shown, no skipping | Existing queue tests + native |
| Empty/loading/singleton-error snapshot | Load/update | No bogus button; selected file still plays; existing error retained once | QML + protocol smoke |
| Six-season show at S02E03 | Open playlist | Only Season 2 expanded, playing episode visible/highlighted | QML + native |
| Browse Season 6 | Expand header/select E20 | Season 2 collapses; original S06E20 index/key selected | QML + manager/real bridge |
| Reopen / successful/failed switch | Dismiss/reopen/change file | Playing season restored; failed switch keeps current identity; no stale highlights | QML + native |
| Specials / movie year labels / bad section | Render supplied queue | Specials boundary preserved; movie list flat; no rows lost | Queue + QML |
| Subtitle screenshot motivating case | Open long subtitle list | Thin gold bar, no white tracks/corners or horizontal overflow | Native screenshot + geometry |
| Every scroll surface, short/long/Arabic | Hover/focus/wheel/drag | Reveal behavior, all rows reachable, no layout/selection regression | QML + desktop 150%/250% |
| Playlist/Settings/help/audio/subtitle/chapter/search/stats/speed | Click outside while playing/paused | Menu closes; playback state/position/speed/selection unchanged by dismissing click | Shared popup tests + per-menu native evidence |
| Inside click and scrollbar drag | Operate content/drag beyond edge | Action/scroll works; no accidental dismissal | QML + native |
| Opening button / Close / Back / Escape / replacement menu | Dismiss/navigate/reopen | Correct state, focus restored, new menu not closed by stale callback | QML + native |
| Resume prompt / Up next / natural EOF | Outside click / explicit Cancel / real EOF | Explicit resume and existing countdown/next-file semantics preserved | Existing manager/session + native |
| Unicode playback / ordinary single-file playback | Native smoke after build | Files still decode, position advances, clean shutdown | Existing smoke/Unicode regression |
| Installed selection and active old player | Install/status | 0.1.37 ready for new launches; existing player not terminated | Status + process/inventory evidence |

## Verification commands, gates and rollout

No commands below were executed during planning. Use a unique `%TEMP%\cp-player-menu-usability-<id>` as `$taskRoot`, `CP_TEST_MODE=1`, `CP_TEST_ROOT=$taskRoot\cp-data`, and separate APPDATA/LOCALAPPDATA/cache paths. Stop after an unexplained failure; diagnose it without repeating an unbounded loop. Do not run scans, storage benchmarks, real provider searches or the unrelated full app suite.

1. **Fresh baseline / Python gate:** run all `tests/test_player*.py` (exclude opt-in executable regression unless its fixtures are explicitly configured), `tests/test_native_player*.py`, `tests.test_playback_history`, and `tests.test_tv_vertical_slice` using the existing venv/unittest runner. Record current counts instead of assuming the previous 137 remain current. Preserve and report existing failures; do not weaken them.
2. **QML red/green gate:** add CMake option `CP_PLAYER_BUILD_TESTS` default OFF and a `cp-player-ui-tests` Qt6::QuickTest target using `tests/ui_main.cpp`. Register CTest name `player-ui`, supply `-input <source>/native/player/tests/qml`, point QML_IMPORT_PATH at the build-only import root described above, and supply the pinned Qt DLL/import paths for that child process only. Enable the option when configuring the test build; `cmake --build <build> --target cp-player-ui-tests --parallel 4`, then `ctest --test-dir <build> --output-on-failure -R player-ui`. The source test runner exercises production shared components with fixture queues and real pointer/key events. Production target still builds with the existing build script. A green component suite is not complete player proof. [Qt Quick Test](https://doc.qt.io/qt-6/qtquicktest-index.html).
3. **Compiled production gate:** `native/player/tools/build_player.ps1 -QtRoot <validated-qt> -MpvRoot <validated-mpv> -BuildRoot <task-build> -StageRoot <task-stage>`. Run `python native/player/tools/smoke_player_ui.py --runtime <staged-runtime> --fixtures <task-fixtures> --output <task-evidence>` with a bounded timeout and inspect saved desktop captures against Home's CSS/reference. No mobile work. Ordinary playback, queue/autoplay and Unicode regression are separate smoke checks, not inferred from menu tests.
4. **Activation gate, after execution approval includes installation:** bump only runtime build metadata to unused 0.1.37; back up touched files and current.json under `.codex/backups`; assemble with `tools/assemble_player_runtime.py`; validate all hashes/licenses; move selector only after staged checks pass. Validate live status and installed helper. If version 0.1.37 already exists by execution time, do not overwrite it: choose the next unused version and record that mechanical adjustment.
5. **Recovery/reporting:** keep 0.1.36 intact. If installed status/manifest/playback fails, restore the saved selector to 0.1.36 atomically; do not alter or close an active user session. Revert only task source deltas when necessary, preserving newer unrelated work. Report source tests, compiled UI proof and installed selection separately, along with any remaining contract differences.

## Review focus / self-review

The most likely hidden regressions are original-index loss after grouping, missing-item removal, outside-click leakage, delayed popup closure clearing a new menu, and long-text/high-DPI scrollbar overflow. Each has an explicit acceptance case and test task above. The native media-type exposure avoids treating movie years as seasons; existing UTF-8 and authenticated playback paths are preserved. State remains in the existing owners, and obsolete scrollbar/dismissal implementations are removed rather than retained as fallbacks.

## Independent review correction — bounded native chrome owner

The final review and real executable red cases exposed two paths outside Main's toolbar: its separate `windowControls` Row, and `WindowsWindowChrome::nativeEventFilter`, which returned HTCAPTION while a menu was open. Chrome red tests reproduce a title-strip hit of 2 (HTCAPTION) and accidental minimize/close from an outside double click. This correction stays within the approved outside-click consumption contract: Main publishes one derived `blocksWindowGestures` UI state; the existing native chrome owner returns HTCLIENT while an ordinary menu or its dismissal guard is active. The separate window-controls Row joins that same guard. No new persisted preference, protocol, bridge command, layout, or backend action is introduced. Normal native hit testing remains unchanged when menus/guard are inactive; resume and Up next retain existing rules. Verify title-strip click/double-click and both window controls against the compiled executable, followed by ordinary window chrome smoke.
