# Investigate and correct the AI request-slot delay

**Status:** Approved investigation and cause-specific fix. Dante: “investigate and fix that 5.85 second request slot delay, then repeat the same test”. The fix must follow captured evidence; an unreproduced delay is not proof of a database defect. No production restart, data/config edit, commit or release.

## Problem and decision

- Previous capture overlap-final-2 measured5.850699s inside the whole acquire-inference-slot wrapper; its actual GPT HTTP took14.635040s. Earlier lease-only six-pair probe did not reproduce it.
- This task's instrumented full F1 baseline completed50movies/oneGPT in18.429580s. Its SQLite connect/execute/commit/close and diagnostic logger phases were all below8ms. A separate40-pair probe measured acquisition/release around10–15ms and also did not reproduce the stall. Raw evidence roots:cp-slot-deep-gadt020l and cp-slot-phase-probe-rz0mx4cs.
- Confirmed current behavior: one shared SQLite owner limits installation inference to two; BEGIN/COMMIT plus connection close and logging are enclosed by the old broad timer. Root cause of the historical stall remains unknown.
- Add opt-in, temp-only diagnostic instrumentation to distinguish actual slot work, SQLite phases and trace-file I/O. Repeat three actual F1 runs with the same exact prompt/account/configured model. If a concrete defect is captured, fix the existing owner with a failing regression and remeasure. If no recurrence is captured, report that the historical cause remains unresolved and do not manufacture a fix.
- Scope excludes guessed changes to database synchronization/durability, schema, slot limits, timeouts, hardware, security software or unrelated databases.

## Contracts affected and contract-change decision

| Contract | Existing agreed result | Proposed result | Changes contract? | Decision |
|---|---|---|---|---|
| Installation slots | At most2shared requests, owned release, live expired leases retained, dead owner recoverable | Preserve all guarantees | No | Approved |
| Durable jobs/results | Exact targets, progress/budgets and confirmation state survive restart | No changes without demonstrated defect | No | Preserve |
| Diagnostic attribution | HTTP separate from local work; bounded isolated capture, no credentials | Actual slot time separate from logger/SQLite leaf times | No product behavior change | Approved investigation |
| Model/provider | Existing selected account/model; independent Ollama | Unchanged | No | Preserve |

## Current design and ownership

Checkoutmaster HEADbe511f98846a67a182e5b371ad087938e9344362, pre-existing dirty work retained. Byte/hash baseline cp-slot-work-lsc19oi5. Production PID16180/port5000, config/data owner unchanged; served dist remains existing index. The running app has not loaded recent source optimizations.

| Responsibility | Owner/callers | Preserve/retire |
|---|---|---|
| Shared request slots | AIJobStore.acquire_inference_slot/release_inference_slot/inference_slot | SQL owner, expiry/liveness, cross-process2limit |
| Invocation | ChatGPTTransport.run/inference_slot callback | Account access, retries/attempt accounting and cancellation |
| Capture | tools/profile_ai_features.py | Add --slot-diagnostics; retain existing summaries |
| Fine phases | New tools/ai_slot_diagnostics.py | In-memory operation timing and isolated SQLite/trace observers; no production behavior |

## Exact behavior contract

Frontend unchanged. Backend store unchanged unless a cause-specific defect is proven. The new diagnostic helper operates only under a unique OS-temp root and instruments connections to that root's ai/ai.sqlite. It captures timings/opcode/thread identifiers without SQL parameters, database payloads, request bodies or credentials. SQLite connect, execute/script, commit/rollback/close and actual slot acquire/release/reserve are individually timed in memory. Trace.emit file I/O is separately observed. Instrumentation restores sqlite3.connect and the trace emitter on close, writes evidence after feature timing finishes, and is bounded in sample count. Custom connection factories are preserved. Close is idempotent.

## Implementation sequence

1. Preserve current files and capture underlying baseline phases before any product edit (completed).
2. Test temp containment, actual-slot-versus-log attribution, SQLite semantics and hook restoration; add diagnostics only.
3. Run relevant diagnostic/job/transport regression checks. Reproduce a confirmed owner defect before selecting a fix; preserve current durability/concurrency contracts.
4. Run three exact-prompt F1 captures with actual phase observers, one at a time, no test/build workload. Maximum3inference attempts/180seconds each; all failures retained. Report actual slot times, GPT HTTP, matching residual and full process; source/runtime separation explicit.

## Acceptance matrix

| Scenario | Expected result | Evidence |
|---|---|---|
| Historical slow acquire recurs | Identify connect/begin/commit/close/log/other contribution | Buffered low-level capture |
| No recurrence | Report non-reproduction and unresolved cause; no claimed fix | All retained captures |
| Slow logger | Logger time not attributed to actual slot | Deterministic diagnostic regression |
| Connection errors/custom factory | Original semantics, proper restoration | Unit checks |
| Non-temp/live database | Refuse instrumentation | Containment unit check |
| Close twice/exception | Hooks restored and evidence retained | Unit check |
| Slot2limit/expiry/dead process/owned release | Existing guarantees remain | Job/transport suites |
| Exact prompt50 | Actual cards, calls and stage times recorded | Three real isolated captures |

## Verification and rollout

Use .venv Python and unique CP_TEST_ROOT for store tests. Focus on new diagnostics, test_ai_jobs, test_ai_timing_capture and test_chatgpt_transport. Broaden only if product code changes. No frontend build needed for diagnostic-only changes. Verify product source, config and served index hashes unchanged where no owner fix is justified. Capture report must distinguish a fixed defect, a measured hypothesis and an unresolved historical event.

## Execution result

Investigation complete within the bounded captures; historical root cause remains OPEN and no product fix is claimed. Confirmed profiler marker-attribution defect fixed (red5.86s/green0.01s fake-clock regression). New buffered diagnostics retained.43tests pass; fresh review no actionable findings. Final actual captures all50verified/oneGPT:19.098905s,16.532659s,22.024641s;actualslot11.166ms,19.887ms,14.568ms. Meanfull19.218735s. Captured unrelated1.684951sjob-finalizationCOMMIT and0.329slogwrite; no5.85srecurrence. Product owners/config/servedbundleunchanged. Full evidence docs/verification/chatgpt/request-slot-investigation-2026-11-03/report.md. One real baseline+three repeats=4GPTcalls. Two failed diagnostic launches before inference retained. No further inference queued.
