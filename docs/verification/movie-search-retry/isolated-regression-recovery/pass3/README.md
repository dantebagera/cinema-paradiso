# Third bounded isolated pass

The previously listed fixture, browser ownership, compiled desktop and post-reopen database gaps passed their remaining scoped checks. Final read-only review and ledger closure are recorded in result.json. Product behavior, existing source/tests, the live app and production data were not changed.

## Fresh results

| Check | Result |
| --- | --- |
| Fixture/ownership regression controls | Two tests, including seven mismatched-identity subcases and a missing-record case: observed failing legacy behavior, then passing correction |
| Affected TV performance module | All 20 tests passed, including baseline encounter-order parity and preservation of invalid observation evidence |
| Repeat evidence-file case | Passed again under a distinct fresh UUID root; earlier evidence retained |
| Compiled Library desktop | Five passed: serialized live typing and all 85 identities reachable, obsolete-response error/recovery, old background poster race, Movie/File return, current-page quiet refresh |
| Compiled Home/Following desktop | Eight passed: ownership during full scan and pending ownership; manual full scan versus ownership-only refresh; health counts, error/cache/loading states and cleanup destinations; Upcoming twenty-card fill and rail reachability |
| Post-reopen recovery databases | All eight quick checks returned `ok`; zero foreign-key errors; Movie retains 3,957 media rows and 5,208 canonical movies |
| Existing safe source inventory | 1,722 pre-existing files matched before report closure; all 243 runtime inputs and 35 compiled bundle files matched; all 114 tracked dirty status entries identical |

The quiet-refresh case starts on page two (rows 41–80 of 85), holds each background response, then releases it. It checks both `cp-library-changed` and `cp-catalog-ready`: unchanged query, page, page size and ordered card titles, enabled refresh control, no foreground spinner or toast. A synthetic facet marker is rendered only after the refreshed response commits, proving that the test did not merely observe the old screen while a response was ignored. Screenshot inspected.

The manual scan case observes exactly one startup full scan, one additional button-triggered full scan, and one separate catalog-event ownership refresh with no additional full scan. Existing ownership-race tests also passed. Health count/loading screenshots were inspected. All browser tests used the saved, source-matching compiled bundle at a desktop viewport of 1600 × 1000; no build was required or performed.

## Harness corrections and boundary

Every unittest dispatch now creates a new root exclusively using a UUID. The production evidence writer's exclusive-create behavior and all existing test assertions are unchanged. A repeat-run control confirms that a new root does not contain the earlier evidence and the earlier evidence remains intact.

The guarded synthetic child binds port zero itself and retains the resulting listener. It writes an exclusive readiness record with its actual PID, nonce, sandbox root and random nonproduction port. The parent validates that record before making any HTTP request, then verifies the same identity through a nonce-protected endpoint before launching browsers. Parent monitoring rejects server exit during browser execution. The browser and request fixtures share only this owned origin; browser routing blocks other origins and service workers. Negative controls reject wrong PID, nonce, root, production/invalid port, false test mode and an empty record.

One initial startup failed before readiness/HTTP: the base interpreter discovered optional `defusedxml` in the user-site directory, and the guard rejected that dependency read. Setting `PYTHONNOUSERSITE=1` and redirecting APPDATA/USERPROFILE fixed the environment without widening the guard. The failed attempt and startup log are retained and included in the allowance.

Eight existing filesystem/SQL/socket/process negative controls passed again; exact FFmpeg discovery remains read-only and both execution and writes remain blocked. The successful Home/Following child exited through its private stop endpoint; its guard report has no violations. The first successful Library child used owned-tree termination, so it has no flushed exit guard report; the boundary was installed before its app import. No broader guard-log completeness claim is made.

Database connections for the eight copied recovered stores used `mode=ro` and `query_only=ON`. Inputs were the existing disposable recovery copies after the second successful boot from pass two. Production state and the master recovery snapshot were not recopied or opened as databases. Only owned disposable processes were controlled. The final owned-process record is empty. Python guards protect trusted application code and are not an OS sandbox; the production boundary is established by the reviewed action record and guard evidence, not physical I/O instrumentation.

## How this closes the earlier record

Pass two reached all 462 selected cross-domain cases: 461 passed and one stale temporary evidence-file error. The complete affected 20-case module now passes, and the failed case passes again in another fresh root. This resolves that recorded error; **it is not a new green full 462-case run**. Earlier 451 Movie owner and 140 Node successes remain historical results on unchanged runtime source.

Pass two already completed two normal-mode recovered application boots, saved Movie first-page identity/order/count parity, compiled Library navigation, graceful checkpoint/exit and reopening the same copied stores. This pass supplies the missing post-reopen database checks and broader compiled scenarios. It does not repeat or relabel the prior boots as new runs.

Real provider connectivity, torrent/download operation, native playback, physical media rollback and new live-app verification remain outside this offline scope. No product behavior or contract change was introduced. Existing files were preserved; only additive verification artifacts and the plan/latest-report references were updated in the checkout.

## Resource accounting and retained evidence

Fresh allowance: 600 cumulative active seconds, 240 seconds per batch, 8 GiB process-reported writes, 4 GiB temporary footprint, one test worker. Earlier ledgers remain closed. The runner samples footprint separately from its prompt process-tree monitor and deadline; no batch approaches the previous cap breach. Exact final totals, failed startup cost, closure and review outcome are in [result.json](result.json) and [bounded-pass-3.json](bounded-pass-3.json). These counters are process-reported writes and logical footprint, not physical SSD writes or a hardware stress test.

Closed totals: **70.859 active seconds** across fourteen batches, **48.28125 process-tree CPU seconds**, **220,317,335 process-reported written bytes**, maximum batch **25.902 seconds**, peak temporary footprint **2,710,192,040 bytes**. All limits satisfied. Totals include the deliberately failing RED controls, rejected initial startup and one failed metadata-seal expectation (the generated plan was outside the inherited file inventory); the corrected final seal passed. No tests ran after closure. Final read-only review found no Critical/Important issue; its one deferred exit-audit limitation is stated above.

Evidence includes the fresh unit/browser logs, post-reopen store report, ownership proof, source seal, screenshots, process cleanup record, harness scripts and disposable specs. The original sandbox is retained at `C:\Users\dante\AppData\Local\Temp\cp-regression-recovery-30b40a41d572`; no recovery or prior-pass artifact was deleted.
