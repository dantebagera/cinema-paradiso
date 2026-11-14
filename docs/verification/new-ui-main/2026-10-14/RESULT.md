# New UI is integrated and live in main

Date: 2026-10-14, Africa/Cairo. Dante approved every integration stage and all tests in this chat. Work completed under that approval; no further routine permission pause.

## Result

Main retains its latest Upcoming and Movie Follow fixes and production state, with the adopted desktop UI, shared components, TV filters/portraits and artwork/list performance repairs. Main's original run.bat and PWA helper remain authoritative. No preview launcher, settings, databases, copied active state or runtime binaries were promoted.

The effective reviewed source/tests/docs manifest contains 183 files. Main's pinned award reproduction namespace retains its exact original bytes. All retained backend fixes and the reviewed source/test hashes match their verified owners.

## Verification

| Gate | Final result |
| --- | --- |
| Full Python suite from actual main with disposable fixture data | 1,752 passed; 0 failures; 0 errors |
| All top-level Node tests from main | 133 passed; 0 failed |
| Compiled desktop suite across correct scenario fixtures | 302 distinct cases passed; all 69 general-fixture skips covered elsewhere |
| Focused combined Movie/TV/identity/filter/portrait Python gate | 217 passed |
| Retained launcher/awards/path/streaming gate after pinned-input preservation | 75 passed |
| Atomic schema rollback/retry, original nonblocking bound, corrected streaming wiring | 20 passed |
| Main production build through original run.bat | Passed; entry index-BOxSXlU5.js and index-Cz-Bcnef.css |
| Actual main served index | Matches main dist |
| Real CP restart and installed-PWA lifecycle | Backend 54304→55580; installed_web_app; localhost:5000; normal background queue started |
| Original qBittorrent | PID 14308 and port 8686 retained; two active downloads were not stopped |
| Postactivation databases | Eight consistent backups, integrity ok, all table counts preserved |
| Controlled live desktop | Home, Movie Library 40 cards, TV Library 32 cards and history; no page errors or HTTP 500 responses |

The full Python run completed in 729.539 seconds. Its warnings about unclosed fixture resources are retained in the log; they did not produce a test failure. These current results supersede historical verification counts.

The general browser run passed 233 cases and skipped 69 requiring other fixtures. Upcoming/Discover added 9 passes, Movie Follow 2, native TV 7, expanded TV 8, season packs 3, stabilization 5, fresh lower controls 9, fresh normal import 6, fresh TV parity 19and native-TV streaming 1:302 distinct cases, no uncovered skips.

## Repairs found during verification

- Old new UI failed 28 Upcoming/Movie Follow regressions with 38 failing assertions; its Home helper also failed the updated Node expectation. Main's three owners were carried together with their callers/tests.
- Upcoming tests were adapted to the existing adopted Home contract: retain all 81 fixture rail entries, open default-collapsed controls, keep exact backend membership/paging/history assertions.
- TV specs sharing one server contaminated later specs with persisted synthetic submissions. Fresh scenario fixtures passed without product or assertion changes.
- The first broad temporary candidate run had five failures and one setup error. The temp checkout location invalidated outside-temp path guards, preview-only test construction was incorrect, and pinned input bytes differed. Actual main preserved its pinned evidence and ran the correct production suite.
- An obsolete streaming source assertion expected streamLoaded and misleading preparation text. It now checks the existing iframe-page-load status owner and truthful loading text. Compiled streaming cases verify behavior; no product streaming source changed.
- First-time IPTV database initialization exceeded the existing 1-second nonblocking expectation. Existing schema scripts now begin their own transactions, avoiding per-CREATE flushes after executescript ends the incoming transaction. Three interleaved old/new cold samples were 0.957/1.063/1.092 seconds versus 0.133/0.159/0.183 seconds. All 200 fixture movies remained projected. A real SQLite failure-injection test reproduced partial old tables and now proves first-batch rollback and successful retry. Individual batches are atomic; the entire migration is not represented as one atomic transaction. Schema 4, migration backup/restore, ownership and policy remain unchanged.
- Independent reviews found no must-fix integration or schema-batch defect. The suggested complete retained-source drift check was added.

## Production preservation and limitations

Main's config.json and run.bat match their original hashes. The Movie catalog remains external to the project under AppData; TV/acquisition/awards and both IPTV providers remain in main's configured data root. The pre/post consistent database snapshots have equal table counts, including 3942 Movie media files,5168 TMDb movies,15 lists / 559 list items,43 followed entries,42 TV series and1168 TV media files. No catalog/configuration/runtime overwrite from new UI occurred.

Normal production startup and restart may update runtime timestamps, leases and availability. Additional live-render Follow scans were blocked; availability/source/quality/repeated-scan contracts were verified through real routes in isolated fixtures. No artificial real download, import, deletion or provider probe was initiated for tests.

Native Computer Use could not inspect the PWA window because it could not determine the Windows browser URL confidently; native automation stopped. Actual installed-app launch mode/window ownership, restart and served bundle were verified programmatically. The saved live screenshots come from a controlled browser at the known local main URL, not from the native PWA window. Home was captured while its feeds were loading; successful live provider-feed completion is not claimed.

The original port5000listener disappeared before the deliberate activation, for an unestablished reason. The final running instance is identified in live-restart.json; this does not attribute the earlier disappearance to a proven cause.

## Recovery and Git state

Verified source snapshots, old dist, configuration/profile/job state and consistent core plus IPTV database backups are retained at:
C:\Users\dante\Desktop\CP integration rollback 2026-10-14-3cca1a48

Dante's existing folder copy was left untouched; its completeness is not claimed or relied on. New UI remains available with its private preview launcher/settings. No new worktree, reset, discard, commit, push, tag, packaging or release occurred. Main remains master at shared HEAD be511f9 with the integrated source uncommitted; new UI remains codex/mostafa-ui-ux. A Git branch merge alone would not have transferred this dirty work.

See final-proof.json, promotion-manifest.json, pinned-input-preservation.json, database snapshots, live-restart.json, review.md and logs/ for exact evidence.
