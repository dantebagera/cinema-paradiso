# Library exit audit completion — 2026-10-24

**Result: the remaining isolated Library exit audit is complete.** Five unchanged compiled desktop cases passed. The exact owned server exited normally with code 0 and emitted a complete matching guard audit with zero violations. Product source, tests and live state were preserved.

| Completion gate | Actual result |
| --- | --- |
| Final focused harness suite | 21 passed, zero failures/errors/skips |
| Existing compiled Library cases | 5 passed; unexpected=0, skipped=0, flaky=0; report-level errors=[] |
| Exact child identity | PID 35676, fresh UUID fixture, nonce/root/test-mode/held random port validated before HTTP/browser |
| Private stop and shutdown | Matching stop PID; normal exit 0 within the seven-second wait; no forced cleanup |
| Exit guard report | Valid complete JSON; exact PID, normalized isolation root and role `ui` |
| Workload counters | `open=652`, `sqlite3.connect=917` |
| Audit violations | `[]` |
| Preservation | 1,788 pre-existing safe files sealed; 243 runtime inputs, 35 bundle files, 161 historical evidence files and all 114 tracked dirty entries match; no source/test drift |
| Owned process cleanup | All four recorded owned root PIDs absent; successful Job Object tree drained; no owned process left |

The five scenarios cover serialized rapid typing with all 85 identities reachable, obsolete-response error/recovery and empty/repeat navigation, foreground typing during older poster loading, Movie → File → Movie during a pending read, and page-two quiet refresh through both catalog/library events. The quiet-refresh response marker proves commit while ordered cards, query, page, loading and notifications remain correct. Screenshots were captured from the unchanged compiled bundle at 1600 × 1000; page-two screenshot inspected. No UI edits, mobile work or frontend build.

The new disposable controller calls one strict audit validator. Missing, empty, malformed, mismatched or violating audits cannot qualify a run. Five passing browser results alone are insufficient: exact owned graceful shutdown, exit 0, complete positive workload counts and empty violations are mandatory. Forced termination is failure cleanup only. The guard, private server, fixture allocator, origin restriction and existing five assertions remain unchanged.

The original controller's actual finally body failed six adverse controls before correction. Initial strict controls passed 14/14; two setup regression controls expanded that to 16/16. One fresh read-only reviewer found two Important failure-path defects: outcome writing could replace the original failure, and wrapper exceptions could leave consumed allowance unrecorded. Four adverse controls then failed across five review controls; both fixes passed in the final complete 21-test suite. Budget accounting now persists halted/in-progress state before launch, records exceptional batches and blocks reuse when accounting is uncertain. Pending completion errors retain a secondary report-write-failure note. No second review or repeated browser execution was needed for these failure-path changes. No Critical or unresolved Important finding; provisional bookkeeping Minor resolved at closure.

One initial setup attempt failed: redirecting LOCALAPPDATA changed Playwright's browser-cache lookup, so all five reported launch errors before any browser assertion ran; report decoding also failed under Windows' default cp1252 encoding. The failed owned server was force-cleaned and its guard file is empty. That is a failed setup, not a clean audit. Raw files, failed controller version and costs are retained in `failed-setup/`, `guard-18512.json` and the disposable workspace. Explicit selection of the already installed Chromium cache and UTF-8 report reading corrected setup without installation or guard changes. The qualifying run used a new fixture and separate `qualified/` artifacts; retries remained zero. Two early setup-control development runs errored before explicit RED assertions; their raw logs and costs are also retained.

The source/dirty seals permit only this plan and the additive latest-report link to change among pre-existing files. New checkout files are confined to this verification folder. Existing source/test work and historical pass-three evidence were not overwritten. No commit, push, build, dependency installation, restart, production database access, real provider/torrent/native operation or new live-app interaction was performed.

This closes only the missing Library exit report. Prior pass-three TV/Home/Following/store results and recovered boots remain historical, and the earlier empty Library audit is still documented. Python guards cover trusted application execution, not an OS sandbox; the result does not establish real provider/native/media behavior or physical SSD write volume.

Fresh limits: 180 cumulative active seconds, 90 seconds per batch, 1 GiB process-reported writes, 4 GiB entire temporary-root logical footprint, one worker, zero retries. Setup, failed attempts and controls are charged in the single closed `bounded-pass-4.json`; older allowances remain closed. Exact final totals and all gate results are in [result.json](result.json). These are descendant-process counters and logical footprint, not physical SSD writes or hardware stress measurements.

Evidence: [raw guard audit](guard-35676.json), [strict completion result](qualified/completion.json), [browser report](qualified/browser.json), [final preservation](pass4-preservation-final.json), [fresh review and fixes](pass4-final-review.md), [execution ledger](pass4-progress.md). Reusable disposable helpers and unchanged dependencies are under `harness/`; the original execution root remains `C:\Users\dante\AppData\Local\Temp\cp-regression-recovery-30b40a41d572`.

Closed totals: **30.637 active seconds** across 13 batches; **24.703125 process-tree CPU seconds**, **114309050 process-reported written bytes**, maximum batch **18.923 seconds**, peak temporary footprint **2717387409 bytes**. All limits satisfied, including failed setup and control-development runs. No tests ran after closure.
