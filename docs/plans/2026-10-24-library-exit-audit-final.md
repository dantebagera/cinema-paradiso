# Library exit audit completion — final implementation plan

**Status:** Implemented and verified in isolation, 2026-10-24. Evidence: [Library exit audit report](../verification/movie-search-retry/isolated-regression-recovery/library-exit-audit/README.md). Dante: “creat the final implementation plan , open a new task and implement”. Scope follows the immediately preceding discussion: finish the missing Library exit audit in isolation. Existing offline qualification remains complete; this is evidence completion, not a new product feature or an authorization for live work.

> **For the implementing agent:** Use `superpowers:executing-plans` inline, with verification before completion. Execute this approved plan without asking for implementation approval again. Use a fresh read-only reviewer at the end. Preserve the saved evidence and all existing changes; do not commit or deploy.

**Goal:** Produce a complete exit guard audit for the five already passing compiled Library scenarios, with successful graceful shutdown and verified cleanup.

**Architecture:** Reuse the existing guarded synthetic fixture, exact owned-server readiness, saved compiled bundle and five desktop scenarios. Correct the disposable browser controller so graceful shutdown and a valid child guard report are required for success. Retain previous harnesses as immutable evidence; there must be only one active controller for this new run.

**Spec:** `docs/verification/movie-search-retry/isolated-regression-recovery/pass3/README.md`, `pass3/final-review.md`, and the exact contracts below. These describe this follow-up completely; do not expand it to other previously listed out-of-scope areas.

## Problem and decision

- **Observed:** Five Library scenarios passed, but their owned fixture server was force-stopped before the guard's `atexit` handler wrote its JSON report. Guard installation was verified before app import. The empty exit file cannot establish zero violations.
- **Location:** Disposable controller `C:\Users\dante\AppData\Local\Temp\cp-regression-recovery-30b40a41d572\pass3_behavior.py` and audit writer `guard.py`. The controller now has graceful stop code, but catches cleanup errors and falls back to termination without making the audit a success gate.
- **Impact:** Product checks stand, but the Library process lacks its complete retrospective access/violation record.
- **Intended result:** The same five Library cases pass, the exact owned server exits normally, its complete guard report is parsed and validated, and no owned process remains. Forced cleanup still protects the host after failure but can never qualify a run as successful.
- **Confirmed:** Pass three completed 20 affected TV tests, one repeat evidence case, 13 compiled desktop tests and eight copied store checks. No Critical/Important review findings remain. Do not redo those unrelated checks.
- **Unknown:** Whether the complete Library exit report contains any rejected operations; discover and report honestly. Never clear, filter or relabel violations as clean.
- **Open decisions:** None within this narrowly defined follow-up. A product behavior/contract change is not approved; stop that affected work if one becomes necessary.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior | Affected owner | Proposed result | Contract change? | Decision |
| --- | --- | --- | --- | --- | --- |
| CP Library behavior / prior five desktop cases | Exact membership/count, current intent, stale-response protection, repeat navigation and settled loading | Existing compiled Library and search owner | Observe the same results | No | Preserve |
| Isolation / existing plan | No live HTTP/UI/process control or production data; embedded test client only | Guard, readiness controller, browser context | Keep all restrictions | No | Mandatory |
| Evidence completion / this plan | Empty/missing/unflushed audit cannot establish a clean exit | Disposable controller | Success requires graceful exit plus validated complete audit | Harness success criterion only | Approved |
| Preservation / Dante's instruction | Existing dirty source and prior evidence remain intact | Source seal and additive reporting | Zero source/test drift | No | Mandatory |

## Current design and ownership

Checkout: `C:\Users\dante\Desktop\cinema paradiso`, `master`, HEAD `be511f98846a67a182e5b371ad087938e9344362`; 114 tracked dirty entries at handoff. Capture current tracked/untracked safe-source state before doing work, and reject unexpected drift. Do not treat HEAD alone as the approved source.

Execution root: `C:\Users\dante\AppData\Local\Temp\cp-regression-recovery-30b40a41d572`. Existing `checkout` contains the verified dirty source and saved 35-file bundle. The 243 runtime inputs were verified against the saved manifest. Dependencies are read-only existing runtimes. The live process, configuration and served production bundle are intentionally not inspected in this follow-up.

| Responsibility | Existing owner | Preserve / change |
| --- | --- | --- |
| Before-import boundary | `guard.py`, `sitecustomize.py` | Preserve all read/write/SQL/socket/process restrictions; no new production-path allowances |
| Unique fixture and readiness validation | `pass3_support.py` | Reuse exclusive UUID allocation and exact PID/nonce/root/port/test-mode validation |
| Held random listener and private stop | `pass3_ui_server.py` | Preserve bind-once port-zero listener and nonce-protected identity/stop |
| Desktop scenarios | `pass3-specs/library-search-performance.spec.js` | Reuse exactly the five existing tests; no weakened or removed assertions |
| Browser controller | `pass3_behavior.py` | Copy to a new follow-up controller; replace soft cleanup success with strict graceful-exit/audit gate |
| Resource limits | `budget-pass3.py` | Copy into a fresh allowance controller with a different ledger; previous ledgers stay closed |
| Result/evidence | New additive verification folder | Report actual audit outcome; preserve all historical results |

## Exact behavior contract

### Desktop

No UI edits, mobile work or new build. Use the saved compiled bundle only after current runtime-input and bundle hashes match. Run at 1600 × 1000, one worker, no retries, with service workers blocked and requests restricted to the exact owned fixture origin.

The five existing scenarios are: serialized rapid typing with all 85 identities reachable; obsolete-response error/recovery with empty and repeat navigation; foreground typing during an older poster preload; Movie → File → Movie during a pending read; quiet page-two refresh through both catalog/library events with the response-only facet marker proving commit and no spinner/toast.

### Harness and persistence

Create only new disposable helpers such as `pass4_library_audit.py`, `pass4_audit_contract.py`, `pass4_audit_contract_tests.py`, a versioned budget wrapper and fresh `bounded-pass-4.json` under the execution root. Exact filenames may be adjusted only to avoid existing evidence; record that decision. Repository writes are confined to this plan and `docs/verification/movie-search-retry/isolated-regression-recovery/library-exit-audit/`, plus an additive latest-report link after success.

`validate_exit_audit(report_path: Path, *, pid: int, root: Path) -> dict` is the single audit-validation owner. It must reject a missing/zero-byte/malformed report; wrong PID, normalized isolation root or role; non-list/nonempty violations; missing/empty audit counts. Require role `ui`, the exact attested child PID and expected guard isolation root. Meaningful `open` and `sqlite3.connect` counters must be positive, proving the report covers real fixture execution. Retain any rejected raw report unchanged.

Controller completion order:

1. Establish a fresh root and exact owned child identity before any HTTP/browser request.
2. Run the five cases and require expected=5, unexpected=0, skipped=0, flaky=0, no report-level errors and zero browser exit code.
3. Send the existing nonce-protected stop request only to that attested child; require response PID equality, process exit within seven seconds and exit code zero.
4. After process exit, call the audit validator; require a complete report with an empty violations list.
5. Verify no owned test child remains, current runtime/bundle hashes match and existing source/tests/dirty status are preserved.

A browser failure, audit violation, failed shutdown, ownership mismatch or failed preservation check is a failed qualification. In a `finally` path, termination may target only explicitly owned disposable PIDs. Record forced termination as failure, even if browser assertions passed. Do not suppress the exception or replace the original failure. No schema migration, production configuration or media action is required.

## Implementation sequence

### Task 1 — strict audit completion gate

- [x] Capture a new safe-source/dirty-state seal. Verify the existing execution copy, 243 input hashes and 35 bundle hashes. Do not open production data or request a new production snapshot.
- [x] Create a fresh bounded ledger and wrapper before executing setup/test helpers. Limits: **180 cumulative active seconds, 90 per batch, 1 GiB cumulative process-reported writes, 4 GiB entire temporary-root footprint, one test worker**. Include failed attempts/setup; enforce prompt deadlines with cleanup margin. Any limit or escaped safety boundary halts the whole allowance without reset. These are smaller bounds than the preceding pass.
- [x] Write focused validator/controller contract tests. Cover missing/empty/malformed reports; wrong PID/root/role; nonempty violations; missing counters; nonzero or timed-out server exit despite passing browser stats; and a valid complete report. A forced-cleanup path must fail qualification. Observe the current soft-completion behavior fail the relevant controls before implementing the correction.
- [x] Implement the strict gate in the copied controller and single validator. Keep private readiness, `PYTHONNOUSERSITE=1`, redirected APPDATA/USERPROFILE/LOCALAPPDATA/TEMP, `CP_TEST_MODE=1`, fresh OS-temp `CP_TEST_ROOT`, `CP_TEST_QBT_MODE=embedded` and isolated dist beneath that root. Do not weaken the guard.
- [x] Run the complete focused harness contract tests. Expected: all pass with named counts and no hidden failures. Preserve the RED evidence separately.

### Task 2 — real compiled run and closeout

- [x] Run exactly the five existing compiled Library cases against a fresh owned fixture, through the strict controller. Expected: 5/5, normal exit zero, complete matching guard audit and empty violations, zero forced cleanup.
- [x] If an unexpected rejected operation appears, preserve it and diagnose only within the remaining allowance. Never allow production data/network/native execution to make the audit green. If it is outside the approved scope or budget, report the gap rather than resetting the allowance.
- [x] Obtain one fresh read-only review of the scoped controller, audit gate and evidence; no unrelated dirty-code review or second test worker. Resolve any Critical/Important findings within the same remaining budget.
- [x] Seal original source/tests and dirty status again, confirm owned process cleanup, close the ledger and write the exact resource report. No commit, push, dependency installation, deployment or deletion of old artifacts.
- [x] Mark this plan implemented only if every completion gate passes. If successful, update the latest-report reference without rewriting pass three's historical missing-audit record. No new full-suite, live or native-operation claim.

## Acceptance matrix

| Scenario | Required result | Evidence |
| --- | --- | --- |
| Missing/empty/malformed audit | Reject completion; preserve raw artifact | Focused validator tests |
| Wrong child/root/role or incomplete counters | Reject completion before clean-result claim | Focused validator tests |
| Valid audit with rejected operation | Reject clean qualification; expose operation | Adverse validator test and raw report |
| Browser cases pass but graceful shutdown fails | Fail run; owned termination only for cleanup | Controller completion regression test |
| Wrong readiness identity or child exit | No browser/mutating fixture request to another service | Existing ownership controls and controller review |
| Five Library scenarios under real guarded fixture | All five pass on unchanged compiled bundle | Playwright report and captured desktop evidence |
| Exact owned child exits normally | PID matches, exit zero, no forced termination | Shutdown/exit record |
| Complete exit audit after actual scenarios | Valid JSON, matching PID/root/role, positive workload counters, violations=[] | Guard report plus validator result |
| Preservation and cleanup | Existing source/tests unchanged, runtime/bundle match, dirty status preserved, no owned child remains | Final source seal and process cleanup record |
| Limit reached or product change required | Stop affected work/allowance as specified; no silent expansion | Closed ledger and honest result |

## Verification and rollout

- Baseline: prior five Library cases passed; missing exit audit is the sole deliverable. The earlier broad suites, two recovery boots and eight-store integrity checks are not repeated or reclassified.
- Run all Python harness commands through the new finite Windows Job Object wrapper using `.venv\Scripts\python.exe`. Run Playwright through the already installed local `node_modules/@playwright/test/cli.js` and the isolated config. Do not invoke the production launcher or the existing system-qBittorrent wrapper.
- No frontend compilation is needed while the source-to-bundle seal matches. Drift blocks compiled equivalence; it does not authorize a build or deployment.
- Real providers, downloads, native playback, physical media rollback, exhaustive catalog comparison and new live verification remain excluded.
- Final report must give all test counts, skips/failures, whether shutdown was graceful, the actual audit violations and workload counters, preservation proof, exact resource costs and any unresolved difference from this contract.
- Rollback is stopping only the owned disposable process and retaining its artifacts. Production rollback is unnecessary because production is untouched.

## Plan self-review

All behavior decisions are resolved within the established offline boundary. The new audit gate fixes the existing controller's soft success path, preserves the prior scenarios, and does not add competing product logic. Adverse completion conditions and the real five-scenario path have named checks. No requirement here authorizes an unrelated implementation, live action or contract change.

## Execution outcome

The strict disposable controller and single audit validator are implemented. Final focused harness suite: **21 passed**, zero failures/errors/skips. Unchanged compiled Library scenarios: **5 passed**, zero unexpected/skipped/flaky cases and no report-level errors. Owned server PID 35676 stopped through its attested private endpoint, exited normally with code 0, and emitted a complete matching audit: `open=652`, `sqlite3.connect=917`, `violations=[]`. No forced cleanup in this qualification.

One earlier setup attempt failed before Chromium launched because the redirected profile changed browser-cache discovery; UTF-8 error-report reading also needed an explicit encoding. That failure and its forced cleanup remain retained and charged. The existing browser runtime was selected explicitly, with no installation. The successful run used separate artifacts and a fresh fixture; no Playwright retries were enabled.

One fresh read-only reviewer found two Important failure-path issues (original exception preservation and fail-closed budget accounting). Both were fixed in one RED-to-GREEN pass; the entire focused 21-test suite passed afterward, with no repeated browser run. Final preservation and exact closed resource totals are linked in the report. No product/live/native/provider/full-suite claim is added, and pass three's missing-audit history remains intact.
