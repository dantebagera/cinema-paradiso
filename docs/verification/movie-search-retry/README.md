# Movie search and retry implementation — isolated evidence

2026-10-23, Africa/Cairo. **The seven requested functional gaps are now verified in isolation, including the corrected restart-order defect.** Historical evidence limits remain explicit. No production activation, data/configuration mutation, production build, restart, commit, push, package or release was performed.

The approved plan is [the implementation plan](../../plans/2026-10-23-movie-library-search-and-retry-performance.md). Machine-readable measurements, hashes and limitations are in [results.json](results.json). Earlier investigation evidence remains separate in the plan's annex.

## Outcome and limits

- The combined owner batch before the later bounded FIFO fix passed **451 Python tests, 0 failures, 0 skips**, 118.420 seconds. [Full log](final-owner-suite.log) and [exact module list](final-owner-suite.json). It was not rerun as a full batch after that fix; do not describe it as a fresh final-source full suite.
- Final Node batch: **14 passed, 0 failed, 0 skipped** (`advancedSearchModel`, `catalogEvents`, `library-search-requests`).
- Separate earlier verified TV import/destination batch: **83 passed, 0 failed, 0 skipped**, 74.684 seconds. [Log](tv-import-suite.log). This predates the final Movie-only review fixes; it is not described as a final rerun.
- The first compiled desktop batch passed **14/15**, with a Windows native worker exit (`3221226505`) during completion/reconnect. Its first retry encountered the scan gate left armed by the crashed worker (409). After releasing that disposable gate, the completion/reconnect test passed **1/1**. The three search checks then passed **3/3**, including a corrected latency assertion that waits for the new total, stale errors and outstanding background poster preloads.
- Review subsequently exposed an internal Movie → File → Movie navigation race. A new compiled regression failed as expected against the first bundle. Dante then explicitly approved **one corrective isolated rebuild and focused desktop checks**. That build succeeded in `dist-corrective` under the temporary root. All **4 search/navigation checks passed (21.6 seconds)**, including the previously failing navigation case; **1 real import/publication/reconnect check passed (7.5 seconds)** against the same current backend and corrected bundle. [Build log](build-corrective.log), [search log](playwright-corrective-search.log), [completion log](playwright-corrective-completion.log). The rapid-typing test asserted the latest result within 1 second after releasing the controlled request barrier; the exact timing attachment was not retained by the line reporter.
- The approved bounded pass exercised **nine real worker-termination/restart boundaries**, all passing: before facts reservation, after reservation, during facts side effects, after the provider's own identity write, during the last allowed asset attempt, after persisted handoff before sibling admission, after publication commit before event, after event before acknowledgment, and after durable job acknowledgment. The last three also assert the restarted backend's actual Library API card, Following ownership removal and reconnect event, with one poster download and one publication mutation. [Stage evidence](process-crash-evidence.json), [commit/event/ack evidence](commit-event-ack-evidence.json).
- The initial bounded pass found a real FIFO defect: retries recorded A → B → C recovered C → B → A when file-row order was reversed. It stopped, and Dante explicitly approved the bounded correction/resumption. The existing ledger now retains an atomic admission sequence, and recovery uses it for ties. The strengthened process regression verifies **actual dispatch order**, not only recovered insertion order. Read-only review then exposed per-item clock-conversion jitter that could still reverse equal deadlines; a valid RED test reproduced B/A, and the dispatcher now compares durable due times using one shared clock pair. Both regressions and the queue suite passed. [Original RED](qualification-process-inventory.log), [clock-jitter RED](qualification-dispatch-valid-red.log), [final FIFO/queue GREEN: 15/15](qualification-final-fifo-queue.log), [actual restart dispatch](restart-dispatch-order.json).
- Across the finite additional pass, **46 distinct Python methods had successful runs**, plus **2/2 compiled desktop checks**. This is a union across explicitly logged batches, not one 46-test final suite. Additional focused retry validation passed 27/27; affected storage/canonical/rollback checks passed 12/12 after the final dispatcher repair. [Final bounded summary](bounded-final.json), [storage log](qualification-storage-regressions.log), [resource ledger](bounded-pass.json).
- All four selected/fallback metadata branches, empty selected data, competing overrides and an override writer committing during each captured read passed. The 4,000-film named-file check reached strict publication with **139 returned SQL rows / 160 reads**, no full snapshot/core-document reads or filesystem walks. Simultaneous independent inventory writers also passed. [Metadata evidence](snapshot-branches.json), [bounded read evidence](bounded-4000-reads.json).
- The larger compiled desktop check reached **all 4,000 exact identities across 100 pages**; first/latest typing dispatched two requests, with one active transport, and the latest result rendered in **452 ms after the controlled barrier release following final input**. The second desktop check proved poster transport failure → no premature publication/ack/event → no early extra attempt → due-time retry → ready local asset → Library and Following refresh without Force scan. [Desktop evidence](desktop-functional-evidence.json), [full desktop results](qualification-desktop-results.json).
- Only the unchanged 61-test search-owner baseline was captured before source implementation. The broader baseline was not frozen and rerun in its entirety. The initial 60-test completion/queue batch ran after the bounded repository changes and before the retry/monitor changes; it is not an untouched-checkout baseline.

The completed source changes improve the existing owners: one materialized search match set, pure bounded string normalization, coherent read transactions, bounded named-path facts/inventory, a shared readiness assessment, durable retry reservations, per-path execution ownership, recoverable target admission and one workspace read scheduler. No movie-specific exception was added. Movie/TV/IPTV identity and transfer boundaries remain separate.

## Performance and resource cost

Approximately 4,000 synthetic movies, two provider snapshots per movie, dense plots/keywords, 40-card pages. One cold and three warm API samples for each of the three approved query classes. Baseline and candidate ran sequentially. All three **complete API payloads** were exactly equal, including cards, fields, order, totals, facets, statistics, pages and generation. Complete filtered selection also matched for **76 / 4,000 / 0** paths. Frozen selection evidence is [selection-contract.json](selection-contract.json), also saved as `tests/fixtures/library_search_contract.json`.

| Query class | Baseline warm median | Candidate cold | Candidate warm median | Candidate worst warm |
| --- | ---: | ---: | ---: | ---: |
| Representative text | 1,604.701 ms | 706.030 ms | 110.417 ms | 111.132 ms |
| Broad short text | 355.854 ms | 88.113 ms | 75.098 ms | 75.527 ms |
| No match | 1,591.142 ms | 160.405 ms | 107.450 ms | 108.024 ms |

These candidate samples satisfy the proposed API thresholds. **A controlled speedup ratio is not established:** processor boundary samples show thread migration, and intervening scheduling/core-class equivalence was not captured. No affinity, priority, hardware polling or stress changes were made.

The mechanism reduced representative normalization calls from 79,698 to 40,078 per request; candidate warm normalization misses were zero. The full cache-bound exercise retained 32,768 entries, accounted 24,479,392 bytes and peaked at 21,499,042 traced bytes. Total diagnostic CPU, including cache memory and full-selection comparison, was **23.6875 seconds**. Recorded temporary footprint was **70,485,120 bytes** before copying evidence. **Cumulative diagnostic process write bytes were not captured and cannot be reconstructed retrospectively.** File footprint is not a substitute for that counter.

The original 4,000-entry API/selection corpus and initial 85-entry rendered corpus are separate. The later desktop qualification used a separate 4,000-film synthetic fixture, reached all 4,000 identities over 100 pages, and measured the controlled latest-intent render at 452 ms. This does not turn the older API comparison into a controlled speedup ratio or prove a production-catalogue latency.

The complete additional allowance, including failed harness runs and deliberate RED checks, used a Windows Job Object to account for owned descendants: **132.116 active seconds of 600 allowed, 156.78125 process-tree CPU-seconds, 1,063,981,573 process-reported write bytes of the 1,073,741,824-byte cap**, and a final sampled **129,520,288-byte temporary footprint**. One Playwright worker uses several browser processes, so aggregate CPU can exceed active elapsed time. Roughly 9.8 MB of the write allowance remained; no more tests were run. The 4,000-entry fixture was reused rather than seeded twice. The allowance is now closed and the runner refuses further batches. These counters do not reconstruct earlier missing writes and do not establish hardware safety. No hardware polling or stress work was performed.

Failed harness runs remain in the ledger: the new restore assertion initially used an ordinary writer that correctly rejected an incoming ledger; the selection assertion initially expected normalized keys rather than public case-preserving paths; the first clock-jitter RED attempt had a test indentation error. Each was corrected within the approved harness/fix scope, with its failed output and resource use retained. Only the subsequent assertion-level clock-jitter RED is treated as regression evidence.

## Review and repair ledger

One independent read-only review found five Important defects and no Critical or Minor findings. Its findings were reproduced before correction:

1. `/api/library/selection/items` read an unassigned variable. Fixed; real route regression changed from HTTP 500 to 200.
2. Probe reuse copied old identity/status fields back over a newly accepted identity. Fixed by retaining only `MediaFileFacts`-owned fields; the real stored identity and API card remain accepted without another probe.
3. A persisted deferred handoff could lose sibling admission on restart. Fixed by replaying idempotent target admission before early completion, recovering completed deferred parents, and excluding blocked records from recovery capacity. Regression proves an unrecorded sibling is readmitted.
4. View changes invalidated a read while the load effect skipped its replacement. Source now shares equivalent Movies/Advanced query identity and requires a replacement after actual surface invalidation. The compiled RED case is recorded; the approved corrective bundle passed the same regression, including the replacement request, visible target card and enabled Rescan control.
5. A synchronous caller could classify a live reservation as a crash. One per-path execution owner now coalesces that caller, preserves stronger follow-up intent and serializes external stages. Conditional ledger conflicts cause a bounded reread/retry and visible dirty-root recovery, rather than silent abandonment. Real SQLite concurrency/conflict regressions pass.

Additional regression evidence covers a replaced file during provider work, a manual choice arriving during a response, ordinary stale row/document writes and path migration preserving the latest ledger, resolved-largest versus deferred-all target selection, failed lookup refusing acknowledgment of an already published discovered file, four asset attempts across coordinator reconstruction, and interruption after the last reservation.

**Ruling:** Work in the actual dirty Desktop source baseline; no clean-HEAD worktree or commit was created. A clean checkout would omit approved existing work. Cost if wrong: source review would miss part of the accepted baseline; exact pre-edit source hashes/backups and a task-only diff are retained.

**Ruling:** Record execution evidence directly in this plan/report instead of commit-based skill scripts. No commit was authorized. Cost if wrong: the evidence is local rather than anchored by a new commit; source hashes identify it.

**Ruling:** Replace the obsolete source assertion requiring synchronous monitor reconciliation with assertions forbidding monitor reconciliation/assets/publication mutation. This implements the approved owner change, while final visible publication/acknowledgment assertions remain.

**Ruling:** The new probe-reuse test asserts canonical card completeness, not a requirement that an optional legacy raw `enrichment_status` hint must be rewritten. The publication contract uses the canonical owner. The old identity fields really were being restored; that defect was reproduced and fixed.

**Ruling:** The cold-start SQL parity fixture now declares its media stable before expecting completion while automatic dispatch is disabled in that fixture. Transient copying is covered separately. This removes an incidental newly-created-file delay without accepting a premature completed status for pending work.

**Build exception:** The initial one-build limit was honored until Dante explicitly answered “Approve one isolated rebuild” to the request naming the corrective build and focused desktop checks. Exactly one additional build was performed, into a separate temporary directory. Current compiled checks passed; this exception does not authorize further builds, broad tests or activation.

**Bounded FIFO fix ownership:** The coordinator carries admission order in its existing retry ledger; the repository owns atomic sequence allocation in existing `catalog_meta`; the existing per-file store/import advances the high-water mark while visiting that row. No catalogue scan, competing queue, identity rule or retry budget was added. The in-memory admission order remains separate so path/directory FIFO is preserved. Ordinary retry bookkeeping remains excluded from visible media generations. On a genuinely new episode, the current admission order is recorded; repeated stage writes retain it.

**Legacy dependency/removal condition:** Pre-sequence ledgers cannot reveal their lost admission order. Recovery keeps their deterministic first-observation/rowid fallback until a coordinator write adds a sequence or the old episode retires. Only ledgers without a positive `admission_order` depend on that fallback; it can be removed after those persisted episodes have been updated/retired. No production backfill or migration was performed.

**Review disposition:** One bounded read-only review found the dispatch clock-jitter acceptance gap. It was reproduced and corrected in the same approved FIFO fix, with RED→GREEN and the full focused queue suite; no second review loop or extra test worker was started. The desktop checks precede only this final dispatch-comparison repair; their direct controlled episode driver does not execute the dispatcher. Final dispatcher and restart/API checks use the corrected source. No frontend source or compiled bundle changed during this additional allowance.

## Acceptance matrix disposition

“Covered” names the available evidence; it does not imply every combinatorial variant was executed. “Partial” remains an open qualification item.

| Plan scenario | Evidence / remaining limit |
| --- | --- |
| Motivating generic text | Covered: baseline-exact complete 4,000-entry API payload and filtered paths; 85-entry rendered count/pagination. Corpus distinction above applies. |
| Broad text fields | Covered: existing store/advanced suites plus frozen result/order oracle and complete selection comparison. |
| Unicode/punctuation | Covered: existing matching tests, accent/Arabic normalization and inventory keys, punctuation and empty oracle cases. |
| Controlled criteria | Covered: advanced model/API, curation, maintenance and full-selection suites. |
| Canonical adverse facts | Covered for all four named selected/fallback branches, empty selected data, competing overrides and a concurrent override commit in every branch; count/card/selection and before/after snapshots agree. |
| Page boundaries | Covered: zero/no-match, clamping, final partial page, existing page-size tests and rendered 85-result traversal. |
| Freshness | Covered for tested mutations and fresh connections; complete combinations of every asset/provider/manual mutation remain bounded by existing suites. |
| Concurrent writer | Covered: a writer completes during the read context; count/keys/cards/generation remain from the captured snapshot, then a fresh read sees the change. |
| Rapid typing | Covered: Node and corrected compiled barriers dispatch first/latest only, with all 85 rendered identities reachable across three pages. |
| Background/foreground race | Covered in corrected bundle: old preload/error cannot replace a new search. |
| Initial/history/Rescan | Covered for tested initial/history/repeat navigation and Rescan API behavior; Movie → File → Movie regression reproduced compiled RED → GREEN. |
| Accepted but incomplete | Covered: real bounded paths, accepted/manual protection and already-probed unmatched acceptance → stored identity → API card. |
| Eligible but not published | Covered by shared read-only status and coordinator publication paths; status alone never commits or acknowledges. |
| Legacy accepted visible | Covered: unchanged legacy startup no-probe/no-enrichment/no-generation cases. |
| Conflicting hint/manual lock | Covered: hint cannot replace protected manual identity; delayed manual choice survives. |
| Poster transient failure | Covered end to end in compiled desktop: controlled first transport failure, unchanged early-trigger attempt count, due-clock retry, ready local asset, strict publication/ack/event, Library appearance and Following removal. |
| Exhausted/permanent failure | Covered at repository/coordinator and failed-provider monitor boundaries; no extra attempts on unchanged episodes. |
| Restart with failure/due retry | Covered by nine real process boundaries, strict post-restart API/ownership/reconnect assertions and actual recovered execution order. External provider/probe stages are controlled fakes; no live process was involved. |
| Crash during stage | Covered for the six stage/handoff boundaries: original deadline/intent and consumed reservations survive; fourth asset reservation remains blocked; deferred sibling is readmitted. Publication/event/ack cases are covered separately. |
| Relevant change/manual recovery | Covered for physical/manual changes and private rearm; Rescan preserves `force_unresolved` and uses separate `retry_blocked`. |
| Active/pending duplicate | Covered: queue admission and concurrent live reservation do not start a second path worker or overwrite the ledger. |
| Due ordering | Corrected and covered: durable A/B/C admission survives C/B/A file discovery and actual process restart/dispatch; equal due timestamps remain FIFO despite clock conversion jitter. Existing earliest-due, mixed path/directory and queue tests pass. |
| Known-path bound | Covered through successful publication of one named accepted file among 4,000 films: 139 SQL rows returned / 160 reads, at most two requested dependency keys per bounded fetch, no full snapshots/core-document reads or filesystem walks. Counters measure rows returned, not physical disk-page reads. |
| Inventory concurrency | Covered: two separate repository instances write simultaneously through independent connections; both updates survive, only the named entry is removed, unrelated fields/Unicode persist, media generation is unchanged, and an unchanged patch schedules no export. |
| Ledger versus ordinary writer | Covered: stale whole rows/documents, conditional revisions and path migration preserve newest operational state without generation changes. |
| Inputs during external work | Covered: obsolete physical and manual-identity results cannot publish; at most one newer intent remains. |
| Already-ready import | Covered: real SQL/broker/API and corrected compiled completion/reconnect fixture against the final backend. |
| Target selection/partial batch | Covered: resolved job acknowledges largest video only; deferred job requires both targets; failed lookup cannot acknowledge visible discovered media. Lost sibling admission regression passes. |
| Provider failure before hint | Covered: original timeout surfaces, durable provider reservation precedes the side effect, permanent failed polling does not renew attempts. |
| Commit/event/ack interruption | Covered by actual termination after commit, after event and after durable acknowledgment; restarted API returns the expected card, poster/publication are not repeated, pending is cleared, Following ownership is removed and reconnect returns the current generation. |
| Missing identity/outside/missing file | Covered in qBittorrent and ingestion suites; existing deferred/error semantics retained. |
| Shutdown/overflow | Covered by queue/observer/checkpoint tests and recovery capacity regression; no new root walk introduced by ledger recovery. |
| Domain isolation | Movie guards and advanced Discover suites pass; earlier separate TV import/destination batch 83/83. No native-TV/IPTV owner change. |
| Pure cache safety | Covered: bounds, oversize bypass, eviction, errors, Unicode, misses outside lock, exact cold/warm API/selection outputs. |

## Historical isolated-pass boundary (before the separately approved activation)

The original live PID remains 56296 on port 5000. Production `dist/index.html` still hashes to `5670d875c3b70b760e7e785637905872e374bed4751e830b6b0c181727362614`. The earlier fixture PID 45212 and corrective fixture PID 41876 on port 5139 were stopped after endpoint identity/listener checks; the corrective process command was also verified. No production data/config/journal/identity/artwork or database was selected by the tests. The source files are changed; the running process and served production bundle were not activated from them. Corrective desktop screenshots were inspected at 1600 × 1000 and retained as `corrective-*.png`.

The seven specifically requested functional gaps are closed by the bounded evidence above. No test worker or fixture remains running; live port 5000/PID 56296 and the production index hash were rechecked unchanged. The approved FIFO source fix modifies only the existing store/repository/coordinator owners; no extra frontend build was performed. The original untouched broader baseline, old diagnostic write count and controlled CPU scheduling comparison remain unavailable historical evidence. The 451-test batch predates the FIFO correction; newer affected-owner batches are named explicitly instead of being presented as a rerun of it. This is isolated qualification of the agreed scenarios, not proof of every possible regression. Commit, publication and live activation remain unapproved.


## Approved whole-checkout activation — 2026-10-24

Dante subsequently authorized the whole current checkout, verified backup/rollback first, and activation. That separate pass is complete: 6.28 GB / 45,833 files backed up and restored by hash, 48 copied SQLite checks passed, four freshly compiled desktop tests passed, and the current backend/bundle and desktop Library navigation were verified live. An external launcher restart preceded the snapshot; recovery captures the subsequent exact stopped current state. See the [activation report](activation-2026-10-24/README.md) for ownership, budget, measured request times and remaining limits. The historical statements above describe the earlier isolated pass, not current runtime status.
