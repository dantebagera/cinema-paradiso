# TV season-pack auxiliary-file repair

Source repair for the Louie season-2 torrent, 2026-10-10. Automatic stalled-source replacement is separate and is not implemented by this change.

## Result and cause

The pack contains thirteen correctly identified episode videos and one featurette under `Featurettes/`. CP interpreted the featurette's title as a different series and saved `validation_failed` before resuming. Dante force-started the transfer. Read-only qBittorrent evidence now shows it complete: progress 1, 10,278,791,570 downloaded bytes. CP's journal still holds the earlier validation failure. Preserve those files; activate the corrected backend and use the existing explicit Retry before verification/import can continue. No production pause, deletion, retry, restart, configuration or journal edit is performed here.

The shared filename parser now recognizes exact auxiliary folders below the torrent package root, preserving existing basename and episode parsing. The manifest records those videos as skipped; qBittorrent sets them to zero priority before resume. Actual episode identity, requested coverage, transport and measured-quality checks remain required. Wrong-show episode files still block the pack, and auxiliary-only content cannot supply episode coverage.

A force-start may have already downloaded the featurette. Snapshot only existing ignored video paths from the validated skipped manifest, preserving the manifest name, source, size and SHA-256. The existing verified move finalizer checks ownership, content, aliases and neighboring files before deleting any selected or auxiliary staging source. Auxiliary videos never become library files. Changed, shared, unknown or unsafe sources require review. Existing unlinking/removed checkpoints support a Retry after interruption.

## Independent review

The first review reproduced a destructive alias case: a Featurettes junction into another staging directory was accepted because only the leaf's symbolic-link status was checked. Permanent tests reproduced the failure. The corrected owner inspects the lexical path and every ancestor for symbolic links/reparse points before resolving, preserving the original manifest path for cleanup checks.

Re-review caught the same issue at qBittorrent's save root: resolving it before the guard hid a root junction. That path is now checked in the normal TV import owner before resolution. Four real Windows junction regressions cover directory/root aliases initially present or substituted after snapshot. An additional permanent regression covers interruption after auxiliary unlink and recovery without duplicate import/add. Final review found no remaining Critical, Important or Minor finding in this source scope; live activation, broader stalled-source design and unrelated prior changes were declined boundaries.

## Verification ledger

| Gate | Result/evidence |
| --- | --- |
| Pre-repair focused baseline | 82 passing; `baseline-focused.log`; source fingerprints in `pre-repair-main-source.json` |
| Initial motivating failures | `red.log`: directory classification and complete transfer path reproduce the problem |
| Forced-download cleanup failure | `green.log` / `cleanup-red.log`: parser repair exposed existing unknown-staging failure; ownership safeguards asserted before extending cleanup |
| Initial combined repair | 10 passing; `complete-green.log`; superseded by final gates |
| Alias regressions before correction | `junction-red.log` and `save-path-red.log`; destructive cases reproduced only in disposable fixtures |
| Four corrected junction cases | 4 passing; `save-path-green.log` |
| Final focused TV/import checks | 200 passing, 216.185 seconds; `focused-final.log` |
| Fresh full Python discovery | 1,716 tests, 1,711 passing and five failures, 586.225 seconds; `full-python-completed.log`; this gate is not green |
| Compiled desktop regression | 6 passing, no skips, 15.0 seconds; successful isolated Vite build and actual normal-import/review/cleanup desktop screens; `desktop-normal-import.log` |
| Main-checkout acquisition regression | 36 passing, 45.049 seconds; `main-checkout-tests.log`; includes all fifteen new tests |
| Main source delivery | Four source/test files and repair plan copied after matching the pre-repair fingerprints; copied SHA-256 values match the reviewed worktree; `source-delivery.json` |
| Live read-only observation | Completed torrent, CP `validation_failed`; `live-read-only.json` |
| Actual fourteen filenames through corrected parser | Thirteen matched Louie season-2 episode claims and one ignored featurette, complete 1–13 numbering; `live-manifest-read-only.json`; read-only, without import or measured-video probing |

All tests use `CP_TEST_MODE=1` and unique OS-temporary roots. Full-suite route checks use compiled dist inside their test root. Production `G:\TV`, `E:\Movies`, catalog and recovery data are excluded from test writes. Desktop test captures in the existing verification folder are restored from pre-run copies. No UI source change is introduced.

The full run's five failures exactly match the previously recorded non-TV baseline findings in `../tv-follow-season-packs/README.md`: offline movie-awards seed generation returns null, two power API expectations disagree with test-mode/system-client behavior, a streaming-modal test expects the obsolete `streamLoaded` identifier, and the qBittorrent proxy-route fixture returns 409 instead of 200. They remain unresolved outside this repair. The prior additional IPTV timing failure did not recur in this run; no IPTV change or claim of a timing fix is made.

`focused.log`, `final-targeted.log` and earlier review coverage predate final junction/root corrections and are supplemental evidence only. Two intervening broad runs were intentionally stopped because later review required a source correction; their partial logs are not pass/fail gates. The first stopped full attempt also pointed its isolated dist outside the fresh test root, producing import errors from CP's test isolation guard; the final command copies dist into its own root. No product assertion was weakened to bypass that guard.

## Source delivery and remaining boundary

The four changed source/test files and repair plan are delivered to the main checkout after checking all four captured pre-repair SHA-256 values; copied bytes match, and the acquisition tests pass from main. Preserve the earlier approved dirty season-pack implementation and all unrelated work. No commit, push, release or live activation. After restarting CP to load the corrected backend, open Downloads and use Louie's **Retry validation / import** button. This retries the existing acquisition and completed files, without adding another torrent. It is distinct from **Retry search** in the release chooser.

Dante chose automatic replacement for zero-data Follow stalls and review for partial-download stalls. Timing and complete replacement/recovery rules remain unresolved in that separate feature. This repair changes neither the five-hour source retry interval nor automatic transfer replacement.
