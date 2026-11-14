# Independent final review

Read-only review against pre-task backups, no UI/build/test activity by reviewer.

- P2: Main.qml windowControls is a sibling of topBar and lacked the dismissal guard; a second outside double-click press could minimize/close the player.
- P2: WindowsWindowChrome.cpp native title-strip hit testing returns HTCAPTION even with a menu open, bypassing the QML modal overlay and allowing maximize on double click.
- Acceptance gaps: native smoke needed actual audio/subtitle/chapter selections, speed preset selection, and EOF/countdown/Play now/Cancel proof. These are verification work, not additional product changes.

Author disposition: both P2 findings accepted for the single review fix pass, backed by compiled red cases and bounded owner correction recorded in the approved plan. No deferred minor findings were reported.
