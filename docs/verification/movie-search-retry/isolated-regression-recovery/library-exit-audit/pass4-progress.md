# SDD ledger — plan: docs/plans/2026-10-24-library-exit-audit-final.md

Approved scope: strict disposable Library exit-audit completion only. No product/live changes, commits, builds or dependency installation.

Pre-flight: Task 1 produces the single strict validator/completion function; Task 2 consumes it after the five unchanged compiled cases. Exact guard report root is the existing isolation root, not the nested fixture root.

Ruling: Reuse the expressly approved guarded execution copy and keep this ledger there instead of creating a Git worktree or skill scratch directory — preserves the hash-verified dirty source and authorized paths — no new product source is developed.

Ruling: Run only the plan's focused harness controls and five compiled cases, retain all scratch evidence, and do not commit — explicit plan boundaries supersede skill defaults for broad suites, workspace deletion and commits — conclusions remain limited to this follow-up.

Task 1: in progress. Fresh budget-pass4.py/bounded-pass-4.json; 180s cumulative, 90s batch, 1GiB reported writes, 4GiB footprint, one worker, no retries. Wrapper begins deadline at 80s to leave cleanup margin.

Preparation passed: 1,788 safe-source files sealed, 114 tracked dirty entries, 243 runtime inputs and 35 bundle hashes match; 161 prior evidence files sealed. No production data opened.

RED: six controls executed the actual prior controller finally body via AST with external HTTP/process effects doubled. All six failed because exceptions/audit failures were swallowed or ignored: timeout, nonzero exit, wrong stop PID, missing audit, recorded violation, forced cleanup. Raw pass4-harness-red.log retained. No application was started in controls.

Initial GREEN: all 14 focused tests passed.

First desktop setup failed: redirected LOCALAPPDATA changed Playwright's existing browser-cache lookup, so none of the five cases launched Chromium (reported five unexpected launch failures, no retries). Default cp1252 decoding then rejected the UTF-8 error report. Owned server PID 18512 was force-cleaned as failure; raw guard file is empty, not clean. All failed artifacts retained.

Ruling: Correct these two harness setup defects and make the one real compiled qualification attempt using a fresh fixture and separate artifacts within the same allowance — no scenario/product assertion executed in the failed browser launch, no test retries or dependency installation; failed setup remains charged — if interpreted as a qualifying run, it would falsely erase failure, so report it separately.

Setup control development: two initial control runs errored (missing helper exports, then the reproduced UnicodeDecodeError/missing cache key). Kept both; revised the assertions to make the two actual behavior failures explicit in pass4-setup-assertions-red.log. Final whole focused suite: 16 tests passed, zero errors/failures/skips.

Task 1: complete (no commits authorized; pass4-final-controls-green.log, 16/16).

Task 2 compiled qualification: five expected, zero unexpected/skipped/flaky, zero report errors; server PID 35676 normal exit 0 after exact nonce-protected stop; valid guard report role ui/root match with open=652, sqlite3.connect=917, violations=[]; forced_pids=[]; owned process cleanup empty. Initial setup failure is retained separately and charged. No test assertion changed.

Preclose preservation passed: all 1,788 sealed files unchanged; 243 runtime inputs, 35 bundle files, 161 historical evidence files and all 114 tracked dirty entries match. Known owned PIDs 3876/18512/35676/49112 absent.

Fresh reviewer library_exit_review returned zero Critical, two Important, one provisional bookkeeping Minor, no declined judgments. Both Important findings accepted: original error replacement by outcome writer; exception path omitted resource ledger/halt. One fix pass, four explicit RED failures across five controls, then entire focused suite 21/21 GREEN with zero failures/errors/skips. No browser rerun; successful path and raw audit untouched. See pass4-final-review.md.

Final: fixed outcome reporting failure — ReportingFailureTests.test_outcome_write_failure_preserves_shutdown_timeout RED→GREEN; successful-path outcome write failure also rejects qualification; suite 21/21.
Final: fixed exceptional allowance reuse — three BudgetFailureTests RED→GREEN, charged failed batch and durable fail-closed in-progress state; suite 21/21.

Final review: one fresh reviewer; no second review. Provisional closure Minor resolved by final metadata closure. No deferred minor finding.

Finish: retain all disposable evidence and leave existing branch/source changes in place, as expressly approved; no commit/merge/push/cleanup choice is requested because those actions are excluded. Final source seal, report staging and ledger closure pending.

Task 2: complete. Final preservation passed; additive report staged and plan/latest link updated only after actual qualification and review fixes. All automated work finished; wrapper/resource ledger closure follows, no more tests.

Closed bounded-pass-4.json: 30.637s active; 114309050 reported write bytes; peak footprint 2717387409; all limits satisfied. No subsequent tests. No deferred minors.
