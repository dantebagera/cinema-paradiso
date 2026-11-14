# Request-slot delay investigation and exact-prompt repeats

2026-11-03. **The historical5.850699s slot delay was not reproduced or causally resolved. No product-slot/database fix is claimed.** A confirmed profiler attribution defect was corrected, and temp-only buffered diagnostics were added. Product slot, transport, matching and persistence owners remain unchanged.

## What is confirmed

The old Trace.span started its operation timer BEFORE synchronously appending/closing its span_start log record. A delayed trace write could therefore inflate the reported slot operation. A deterministic fake-clock regression demonstrated5.86s reported for an actual0.01s operation plus5.85s marker write; after correction it reports0.01s. This proves the attribution flaw, not that it caused the historical event.

New SlotDiagnostics measurements are buffered in memory and separately time actual acquire/release/attempt reservation, targeted SQLite connect/execute opcode/commit/rollback/close and trace-file emit. They record no SQL values, account credentials or payloads. Enclosing GPT/full-workflow timings still include nested instrumentation overhead; they are not instrumentation-free server compute measurements.

The historical trace had one long acquisition call, not repeated waiting for two busy slots. It lacks underlying SQL/file/scheduler timing, so its5.85s cause cannot be reconstructed from that trace alone.

## Causal probes before the repeats

- One fully instrumented actual F1 baseline returned50verified movies using one GPT request in18.429580s. Actual lease acquisition was14.104ms; commit6.232ms and close6.846ms. SQLite and trace leaf phases were all below8ms. A separate account-access span took3.173559s; that is not lease acquisition.
- A separate40-pair acquisition/release probe (80slot transactions, no GPT) stayed around10–15ms. Its longest release was14.917ms. This did not reproduce the historical wait.
- SQLite supports automatic checkpoint work at last connection close, and FULL WAL synchronization can require storage synchronization on commit. Those are possible phase locations, not a diagnosis of these observations. No checkpoint, synchronization, timeout, locking, concurrency-limit, storage or security setting was changed. [SQLite WAL documentation](https://www.sqlite.org/wal.html),[SQLite synchronization documentation](https://www.sqlite.org/pragma.html).

## Three source-frozen real repeats

Same exact user prompt, explicit target50, same configured gpt-6.1-sol/account/default effort, same protected account owner and public HTTP transport, sequential fresh diagnostic processes/sessions/caches. No concurrent build/test workload. At most3actual inference attempts/180seconds per capture; every run completed using one actual request and50distinct verified cards, without retries, repairs or replacement calls.

| Run | Actual slot acquisition | Actual slot release | Actual attempt reservation | Complete GPT HTTP | Full workflow |
|---|---:|---:|---:|---:|---:|
|1|11.166ms|10.231ms|9.604ms|16.054190s|19.098905s|
|2|19.887ms|19.480ms|9.727ms|15.556239s|16.532659s|
|3|14.568ms|11.324ms|9.432ms|20.566429s|22.024641s|

Mean full workflow:**19.218735s**. Mean complete GPT HTTP:**17.392286s**. Mean actual slot acquisition:**15.207ms**. These observations do not establish a speedup caused by a product-slot fix, because no such fix was justified or applied.

## Other slow phases actually captured

Run1 had a **1.684951s SQLite commit during final job completion**, after the50card results had already been persisted. The last card persistence span finished at17.779764s on that trace; the enclosing matching/completion phase ended at19.485677s. Individual card-save spans in that run were about0.011–0.012s. Therefore this is not labelled a slow card write or request-slot acquisition.

Run1 also recorded trace emits of0.329072s,0.228442s and0.207920s. Run3 had a separate0.297758s commit in its first-card persistence span. These confirm variable waits in OTHER local phases. They do not prove a disk, antivirus, lock, scheduler or checkpoint cause, or establish the cause of the historical5.85s acquisition event. Thread CPU time is included in raw samples but has limited Windows timing resolution.

**Open finding:** the original event remains unexplained. Future reproduction with these actual-operation/SQLite/logging leaf clocks can identify its containing phase. There is no evidence-based reason from the captured runs to replace the current slot owner or weaken its durability/concurrency guarantees.

## Code changes and verification

- tools/profile_ai_features.py: operation timers begin after writing their start marker; optional --slot-diagnostics wraps actual calls independently from logging and closes/flushes observers after workflow timing.
- tools/ai_slot_diagnostics.py: opt-in instrumentation restricted to a unique OS-temp root and that root's user-data/ai/ai.sqlite. Custom factories and SQLite semantics preserved; values/paths/SQL parameters not recorded; bounded10000samples (none dropped), safe hook restoration and idempotent cleanup. No per-sample file writes.
- Added regressions for slow marker attribution, temp containment, preserved explicit connection factories, original SQLite slot semantics, privacy and cleanup.
- **43 relevant diagnostic/job/transport tests passed**; exact final output retained in regression.log. Fresh read-only review found no actionable findings. This is not a rerun of the previous235-test product suite; product code did not change and no frontend build was needed.
- Two initial diagnostic launches failed BEFORE inference because wrapper keyword names collided with trace metadata. Both logs retained, root corrected with positional-only wrapper arguments and phase/label/function regression coverage. They consumed no GPT or TMDB requests; no failed inference sample was silently replaced.
- Total real GPT usage for this task:four requests (one instrumented baseline, three final repeats). No additional real inference is queued.

## Exact prompt

```text
i need you to lit 50 movies with very twisted story you wont expect the ending
your responce should be a list of movies names and years , no any other details , dont seek more info , dont reply by paragarph or any way of responce  only the list
```

## Source/runtime/data boundary

Checkoutmaster HEADbe511f98846a67a182e5b371ad087938e9344362; dirty work retained. Source baseline cp-slot-work-lsc19oi5. Product service hashes, matching app.py, config.json and production served index remain unchanged. Production PID16180/port5000 was not restarted. No live catalogue/configuration changes; normal credential refresh may occur through the existing owner. All jobs, SQL writes, probes and diagnostics use OS-temp data. This result fixes diagnostic attribution, not a proven production-slot defect.

All three summaries, traces, buffered phase samples, capture logs, the instrumented baseline,80transaction probe and failed harness launches are retained alongside measurements.json and capture-manifest.json. Historical cause/production fix remain explicitly marked false in measurements.json.
