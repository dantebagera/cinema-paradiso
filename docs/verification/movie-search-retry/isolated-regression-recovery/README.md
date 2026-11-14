# Bounded isolated regression and recovery — 2026-10-24

**Latest:** [Library exit audit completion](library-exit-audit/README.md): five unchanged compiled Library cases passed, exact owned server exited normally with code 0, complete matching guard audit recorded zero violations, and the strict gate passed 21 focused controls. This closes the earlier missing Library exit report; failed setup and all earlier history remain retained. Product and live state are unchanged.

**Latest:** [Third bounded pass](pass3/README.md) closed the remaining scoped fixture/ownership, compiled desktop and post-reopen store checks without product or live-state changes. Earlier partial records below remain historical; no fresh green full-suite claim replaces them.

**Latest:** [Second bounded pass](pass2/README.md) completed offline runnable recovery and six assertion corrections; broader regression remains partial after the batch cap stopped execution. The original first-pass record below is historical and is preserved unchanged.

**Result: partial. The broader-regression and runnable-recovery gaps are not both closed.** No live app request/control or production-data access was performed. All 1,687 original source/artifact files checked still match their initial hashes, including the ignored Library request scheduler; all 114 existing tracked dirty entries are preserved. Product source, configuration, production dist, dependencies and live processes were not changed. Only a new plan and verification documentation were added in the checkout.

## Completed verification

| Check | Actual result |
| --- | --- |
| Complete original 33-module Movie-owner batch on current source | **451 passed; zero failures/errors/skips** on final full run |
| Selected cross-domain Python batch, 33 modules | **462 run: 410 passed, 10 failures, 42 errors, zero skips** |
| All enumerated Node test files, sequential execution | **140 passed across 25 files; zero failures/cancelled/skipped** |
| Isolation negative controls | Eight deliberately attempted file/media/SQL/socket/process accesses rejected before execution |
| Windows job close control | Abrupt job-owner exit terminated the owned child |
| Copied recovery state | 27,599 saved state/bundle/metadata files, 2,561,595,752 bytes, copied by hash; copied Movie database quick_check passed |
| Recovery app boot/UI/checkpoint/reopen | **Not executed** |

The first full 451 run had one two-second concurrency timeout and its cleanup error, plus two lease-child errors caused by the harness interpreting Windows' absent explicit executable incorrectly. After correcting only the harness, all three cases passed unchanged, followed by the complete successful 451 rerun. The initial failure and timing sensitivity remain recorded; a focused rerun is not presented as a green full run.

The first Node run failed because Git's `library/` ignore pattern hid the new imported `src/features/library/librarySearchRequests.js` from a Git-only file copy. The original file was untouched and already present in the verified recovery snapshot. It was copied into the disposable source, hash verified, and the complete Node batch passed. A supplementary filesystem source inventory found exactly that one omitted relevant source file.

## Why broader regression is still open

- **45 IPTV checks were affected by the guard:** 41 errors directly blocked read-only discovery of the installed FFmpeg executable; four route tests then returned 500 rather than 201 through the same constructor path. No real transcoder was executed. The next harness correction should allow only exact installed-tool discovery while retaining real execution/network denial, followed by affected-module reruns.
- **One TV performance check lacks its baseline:** `test_local_rows_preserve_binding_encounter_order` requires `CP_TV_PERF_BASELINE_SOURCE`, which was not configured. Current-source success cannot substitute for a verified baseline comparison.
- **Six source-text assertions failed:** two in `test_full_row_card_grids_ui` and four in `test_library_action_ux`. They expect exact strings for older Home/Library implementation shapes. Those need tracing against the approved visible contracts; no assertion was weakened, no test was relabeled passing, and no product-regression or obsolete-test ruling is made here.

See `cross-failure-summary.json` for each exact failed case and classification. Full cross-domain traceback output remains at the disposable workspace's `cross-domain.log`; it contains large source-text assertion dumps and was not duplicated into the checkout.

## Recovery preparation and review

Workspace: `C:\Users\dante\AppData\Local\Temp\cp-regression-recovery-30b40a41d572`.

The verified stopped-state snapshot was the only application-data input. Original production state was not copied or opened. Current source was copied separately; the 35-file saved bundle matches the prior recorded runtime inputs. External providers, real qBittorrent and player execution are blocked. Python file/SQLite/socket/process guards are for trusted application code and are not represented as an OS sandbox. Browser request routing is restricted to the owned nonproduction origin and service workers are blocked.

One fresh read-only reviewer found three harness defects before any recovery boot: missing Job Object kill-on-close, potentially colliding media-root mappings, and insufficient exact responder-PID ownership. The harness now sets kill-on-close before child execution; an abrupt-owner-exit control passed. Mapping now allocates a distinct destination per original root and rejects dictionary-key collisions; the boot controller asserts the exact owned PID. The reviewer confirmed those source corrections and independently confirmed that recovery qualification remains open. Mapping and boot runtime behavior were not executed or claimed passing.

## Budget and boundary

The closed allowance used **589.508 of 600 active seconds**, **245.890625 process-tree CPU seconds**, **4,339,678,501 process-reported written bytes** of an 8 GiB cap, and a final **2,675,397,710-byte temporary footprint** of a 4 GiB cap. Counters include preparation, successful/failed batches and controls inside the monitored jobs; they are not hardware stress or hardware-safety measurements. About 10.492 seconds remain, insufficient to perform a safe mapping/boot/UI/checkpoint/reopen cycle, so no recovery app was started and the allowance was closed rather than extended.

The cross-domain batch consumed 227.065 active seconds. Repeating the original owner batch after its diagnosed failure consumed another 136.129 seconds. Those costs explain why the recovery rehearsal was not reached. No additional tests were run after closure. All retained source changes remain intact; only owned test processes were managed.

A future bounded continuation must first correct the discovery-only guard and supply or explicitly leave unresolved the TV baseline, resolve the six test-contract mismatches, then execute the guarded recovered startup, saved query identity/order/count checks, compiled desktop navigation, graceful checkpoint/exit, second boot and copied-store integrity checks. No live activation or production changes are required for that continuation.
