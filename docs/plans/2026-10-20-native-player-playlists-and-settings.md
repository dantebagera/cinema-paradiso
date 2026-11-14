# Native player playlists and discoverable controls

**Status:** Approved for autonomous implementation on 2026-10-20. Dante: "please finish this task dont stop untill you finish and then shutdown the pc ... dont come back to me to ask anything ... from here you are approved to finish the task then shutdown". This overrides further design/plan check-ins. Execute inline, with an independent final review.

## Problem and decision

- Running native player 0.1.34 restores `window_state.always_on_top=true`. Many controls are shortcut-only. Backend/native protocol accepts one file per session. Movie/TV launch, history, subtitles and security already have authoritative owners.
- Implement local native movie/TV playlists, Previous/Next file, playlist overlay, autoplay at actual EOF with a 5-second cancellable countdown, visible Settings and shortcut help. Preserve seeking through arrow keys and settings actions. IPTV/embedded streams are separate players and excluded.
- Conservative rulings under autonomous approval: regular TV episodes ordered by season/episode, Specials form their own sequence when explicitly opened; missing/unreleased/review items remain visible and block automatic advancement. Collections use release date then title/identity as deterministic ties; unknown dates follow dated items. One version per movie/episode, existing selected version preferred. Manual playlist selection resumes; automatic next starts from the beginning. No playlist wraps.
- Do not alter show-card Play policy, manual watched state, file import or acquisition. Preserve all unrelated dirty work.

## Contracts affected and contract-change decision

| Contract/source | Behavior preserved or approved | Surfaces | Change? | Decision |
| --- | --- | --- | --- | --- |
| Current keyboard controls | Left/Right remain +/-10s; all configured shortcuts discoverable | Native player | No | Preserve |
| Dante's toolbar amendment | Replace +/-10s buttons with Previous/Play/Next, preserve seeking in menu | Native player | Yes, explicitly requested | Approved in conversation |
| Latest show-card correction plan | Do not change show-card target selection | TV cards | No | Outside scope |
| Completion threshold | 92% may mark watched but never triggers next file | Typed history/queue | No | Preserve |
| Native file security | Authenticated IPC and catalog-resolved paths only | Local playback | No | Preserve |
| Always-on-top | Explicit toggle, visible state; reset existing enabled setting off once at activation | Native/config | Approved repair | Autonomous task approval |

## Current design and ownership

- Source baseline Desktop checkout `master` at `be511f9`, many unrelated tracked/untracked changes. Isolated managed worktree `player-playlists` contains the current text source baseline. No commit/push/release.
- Running CP PID 38088 on 127.0.0.1:5000; config/data/cache belong to Desktop checkout. Served bundle `index-fNsBSLQr.js`; this work changes native QML, not React or that bundle.
- `PlayerManager`: lifecycle, transport, validated queue selection and history changes. New `PlayerQueue`: ordered projection over TV repository / existing collection metadata. `PlayerBridge`: native protocol and current-item generation. `MpvItem`: real EOF discrimination and file decoding. `Main.qml`: reuse CpButton/CpIconButton, generated PlayerTheme and existing panel styling. Separate playlist/settings QML components if needed for readability.

## Exact behavior contract

### Desktop player

Previous/Play/Next at left of bottom toolbar, existing volume/time/speed/audio/subtitles/fullscreen retained; Playlist and Settings added at right. Tooltips name destination, end buttons disabled. Playlist is a right side overlay, current row highlighted, season/code/title or movie/year displayed, unavailable reason visible. Settings uses the same overlay surface, scrolling groups for playback, window/picture, audio/subtitle sync, advanced tools and shortcut help; all actions invoke existing owners. Only one overlay open; Esc closes it. Controls stay visible during overlays. Always-on-top state updates immediately from keyboard and menu; persist via existing window-state channel.

### Backend/native

Queue records carry stable catalog key, title, section, available/reason. No arbitrary paths accepted from native UI. Queue snapshot is bounded to protocol size; fail visibly rather than truncate chronological order. Every native per-file event carries a media generation. Manager rejects stale per-file events and duplicate selection/EOF transitions. Native queue-select names a snapshot item key and generation. Manager flushes old progress, resolves selected identity again, establishes new history, then sends authenticated replacement load in same window. Subtitle callbacks must match media generation. Natural EOF only triggers completion/countdown; stop/replacement/quit/error do not.

Autoplay saved in PlayerConfig (default true), countdown local UI, cancellation stays stopped. Queue disabled or absent still permits ordinary single-file playback. Metadata failure must never prevent the chosen file playing: show queue unavailable with retry capability on subsequent load; never auto-skip missing or invent membership. No database migration.

## Implementation sequence

- [x] 1. Add queue projection/regression tests (TV boundaries/missing/Specials; collections order/versions/missing/date), then implement existing-owner adapters.
- [x] 2. Add validated queue/generation messages and manager/native same-window transitions; exercise progress isolation, duplicate/stale events, resume/restart, subtitle races and actual EOF.
- [x] 3. Expose Settings, shortcut help, playlist, Previous/Next and countdown; compile native QML and verify actual desktop interactions.
- [x] 4. Focused and broader player/TV regression suites; independent review; repair findings; assemble versioned 0.1.35 runtime and verify manifest.
- [x] 5. Back up only affected Desktop files and selector/config, verify baseline unchanged, promote task files, reset always-on-top off, activate runtime without starting scans/downloads. Smoke isolated runtime, verify live config/runtime. Save report and gracefully shut down with no forced app termination.

## Acceptance matrix

| Scenario | Action | Expected | Proof |
| --- | --- | --- | --- |
| Topmost enabled | Menu toggle / T | Same visible state, other app can foreground, persists | Native smoke/UI + live config |
| S02E03 ends | EOF + countdown | Exactly one S02E04 load in same window | Protocol/manager/native smoke |
| 92% progress | Progress update | No queue movement | History/manager regression |
| Missing S02E04 | Finish E03 | Missing row/reason; no E05 skip | Queue + native UI |
| Season boundary | Finish season | Next regular season episode; no Specials insertion | Queue regression |
| Collection | Open middle film | Earlier/later members sorted by release; current highlighted | Queue/native smoke |
| Standalone | Open film | No selectable next/previous; playback preserved | Manager/native smoke |
| Stop/error/close | End-file non-EOF | No autoplay/completion fabrication | Native EOF regression |
| Fast switches/stale events | Select another then late event | New progress never receives old position/subtitle | Manager regression |
| Hidden features | Settings actions/help | Every action accessible, actual shortcuts displayed | Compiled native smoke |
| Existing boundaries | Movie/TV playback tests | Typed history, roots, revisions, OS fallback preserved | Broader suites |

## Verification and rollout

Baseline: 61 player/manager/protocol/config/catalog/history/native tests pass in isolated OS-temp CP_TEST_ROOT. Tests use finite fixtures, no production playback/history. Native build uses pinned Qt 6.10.3/mpv and four build workers. Cleaned development tools required restoring Qt development archives in the task temp directory; no media was downloaded. Test full relevant player suites, TV playback integration, compile and inspect screenshot/interaction at desktop size. Activation preserves old versioned runtime and config/targeted-file backups for rollback. Runtime selector must pass full manifest hashes. No broad full application benchmark, media scan, acquisition, production test playback, commit or push. Save final evidence before shutdown. Shutdown uses Windows normal shutdown without `/f`, after task-owned fixture players/processes are closed; do not dismiss unsaved-work blockers.

## Execution ledger

- Baseline recorded and isolated worktree created with current source text; 61 relevant baseline tests passed.

- Completed: queue, protocol generations, same-window native transitions, Settings/help/overlays, real EOF countdown and missing-item blocking.
- Independent review findings were fixed with red/green regressions: departing progress flush, curated identity matching, optional queue DB failure, preference-save failure, SQLite switch errors, and legacy collection projection. Final independent targeted review: no remaining important finding, 19 overlapping tests passed.
- Full relevant suites passed: 92 player tests + 56 native/history/TV/collection tests in isolated source and installed Desktop source. Unrelated full-application suite not run; no performance benchmark or production playback test.
- Production native build and synthetic same-process autoplay/manual Previous/playlist tests passed. Single-file smoke passed; 1,361 installed runtime hashes verified. Screenshots/logs: docs/verification/native-player-playlists/.
- Installed: Desktop task files preserved the exact pre-existing app.py baseline and unrelated dirty files. Runtime selector now 0.1.35; live runtime status ready. Saved topmost preference reset off through API. Existing backend process deliberately remains loaded until requested shutdown; next CP launch loads new source. No commit/push/release.
- Recovery: C:\Users\dante\.codex\backups\cp-player-playlists-20261020-041140; old runtime 0.1.34 preserved. Default first scope is local native files; IPTV and show-card selection unchanged.
- Autonomous authorization replaces skill review menus and check-in pauses. Execution stayed inline with one independent reviewer; generic branch finishing options were not presented. Final relevant checks, installation and recovery copies take precedence over unrelated full-suite work.
- Ruling: incomplete full collection metadata disables automatic continuation and explains the blocker while local members remain manually selectable. Reused the existing bounded collection provider request rather than inventing membership from only owned files.
