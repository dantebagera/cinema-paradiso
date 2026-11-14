# Native player menu usability — installed 0.1.37

**Installed 0.1.37.** Dante clarified that “enough” meant stop testing and explicitly instructed installation. The existing assembled build was copied into its immutable runtime directory, all 1,366 file hashes and 6 license entries passed installation integrity validation, and the selector was atomically switched. The runtime owner reports ready. No additional UI/playback tests, commit, push, tag, release or backend restart occurred. 0.1.36 remains intact for rollback.

Dante stopped further testing, then explicitly requested installation of the existing build. Existing user player sessions were left untouched. The evidence below records the earlier test results; remaining playback/UI gates were intentionally not run after this instruction.

Confirmed passing evidence before stopping:
- 137 relevant Python tests, 0 failures/skips (`python-after-review.log`).
- 26 real shared-QML checks, 0 failures/skips (`qml-bound-popup-details.log`; 20 behavior checks plus setup/cleanup).
- Independent review completed; both P2 window-control/title-strip findings corrected, with all 3 compiled red-to-green chrome cases passing (`chrome-green-*.log`).
- Real audio/subtitle selection, chapter seek and speed preset passed (`actions-staged.log`).
- Actual EOF Cancel, Play now and natural progression passed (`autoplay-*.log`).
- Full 150% native menu pass succeeded (`final-150.log`). The 250% pass was running when Dante stopped the work; consult its saved log without assuming completion.
- Assembled candidate validated all 1,366 inventory hashes and 6 license entries, retaining the previous runtime inventory and pinned mpv DLL (`staged-inventory.json`).

Remaining gates were not completed: final 250% disposition, representative installed executable checks, current Unicode/manager runtime regression checks ; installation itself is now complete. CP was not listening on port 5000 at baseline; no live server status claim is made.

The work took too long because repeated native harness corrections and real popup input issues caused excessive iterations. Intermediate failures are retained in logs and described in `progress.md`; they are not final passing evidence.

Source/selector backup: `C:/Users/dante/.codex/backups/cp-player-menu-usability-20261024`. Temporary candidate/build/fixtures: `C:/Users/dante/AppData/Local/Temp/cp-player-menu-usability-20261024`. The original 0.1.36 runtime is unchanged. To roll back selection, atomically restore the saved selector listed in installation.json; do not overwrite or remove runtime bundles. Source recovery must apply only this task's deltas and preserve subsequent/unrelated dirty work.

Owner rule: queue truth remains in the backend; native QML presents original indexes and coordinates menu state, while the existing native chrome owner routes menu gestures into that same input boundary.
