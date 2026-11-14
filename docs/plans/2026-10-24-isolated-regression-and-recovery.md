# Bounded isolated regression and runnable recovery

**Status:** Third bounded pass completed the remaining scoped checks. Offline runnable recovery and its post-reopen store checks passed; missing compiled scenarios and the affected TV module passed. Historical runs remain separately labeled. See third-pass execution result below. Approved scope, 2026-10-24. Dante: “go ahead with a bounded isolated pass to close the broader regression and runnable recovery gaps. preserve all existing changes and dont touch the live app or production data.” Execute inline with executing-plans and verification-before-completion.

## Problem and decision

- Movie search/retry scenarios and activation checks passed, but the full 33-module/451-case owner batch predates the final FIFO correction. The activated checkout includes other existing Movie/TV/IPTV/acquisition/player/shared changes.
- Recovery restored all 45,833 saved files by hash and checked 48 copied SQLite databases, but did not boot the recovered app.
- This pass verifies the current source and a recovered application using the existing stopped-state backup only. No live HTTP/UI request, process control, production-state copy, scan, dependency installation, native build, commit or deployment is included. No product source edit or contract change is planned.
- Limits: one worker, 600 cumulative active seconds, 240 seconds per batch, 8 GiB process-reported write bytes, 4 GiB temporary footprint. Setup/copy/test helpers are accounted. Safety failures and exhausted limits stop the whole pass. An unexpected product failure stops its affected check for diagnosis; independent checks may continue within the same remaining budget. Do not weaken assertions or automatically extend the allowance.

## Contracts affected and contract-change decision

| Contract | Required preserved behavior | Verification | Contract change |
| --- | --- | --- | --- |
| Movie search/retry | Membership/order/count, canonical authority, publication/ack gates, durable retry/FIFO | Complete prior owner batch on current source | None |
| Cross-domain ownership | TV/IPTV/acquisition/player/shared owners retain their own contracts | Selected existing Python suites, all enumerated Node tests | None |
| Recovery | Saved current source/bundle/data can boot, serve recovered results, checkpoint and reopen | Two normal-startup boots in a guarded copy and compiled desktop/API checks | None |
| Production isolation | No production state or live service access | Guard rejection tests, path seals, network/subprocess restrictions | Mandatory boundary |

## Current design and ownership

Checkout is Desktop `cinema paradiso`, master, HEAD be511f98846a67a182e5b371ad087938e9344362. Existing tracked/untracked files are sealed before this pass. All harness scripts and copied execution sources go under a unique OS-temp root; a clean Git worktree would omit the approved dirty source, so use a hash-verified file copy instead. Existing dependency runtimes are read only. Root documentation is additive only.

`app.py` owns configuration and normal background startup; CatalogRepository/CatalogStore own Movie persistence; independent native TV and provider-local IPTV stores keep their boundaries. `services/frontend_routes.py` owns compiled assets. `tools/run_movie_isolated_qualification.py` owns finite Windows Job Object accounting; use a separate local copy with the explicitly stated new caps and UTF-8 output. Earlier allowances remain closed.

Recovery input is the verified snapshot at `C:\Users\dante\Desktop\CP-Recovery\whole-checkout-2026-10-24-153619-e50288\snapshot`. Active application SQL/JSON and metadata are copied and hash checked; historical backups, client executable/profile payloads and player binaries are not executed. All configured state, LOCALAPPDATA/TEMP, media roots and cache paths are redirected into the disposable root. Saved offline media path strings may remain in copied records; filesystem guards reject access to their originals. External providers and real qBittorrent/player launch are unavailable in the rehearsal, as in an offline deployment; this limitation must remain explicit.

## Exact behavior contract

No frontend redesign or mobile work. Reuse the existing verified 35-file compiled bundle only if current source inputs still match its recorded manifest; otherwise report the drift before claiming compiled equivalence.

The recovered backend runs normal startup, not merely test-mode Flask. Copied config removes external credentials and redirects roots. Python filesystem/SQLite guards prohibit writes outside the sandbox, prohibit production data/media access, prohibit ATTACH/load-extension escapes, and deny external sockets/subprocess execution. Before boot, deliberate attempts to reach production-shaped paths, the live ports and external processes must be rejected without executing them. The browser uses a new disposable context and allows requests only to the owned nonproduction port.

Recovery checks compare complete returned first-page identities/order/count with saved snapshot responses at the recorded generation where applicable. Check Movie Library, TV read capability and IPTV provider-local read paths. Observe configured unavailable/offline media and provider behavior without interpreting it as permission to access originals. Perform an existing graceful internal background checkpoint/stop, confirm process exit, then reopen the same recovered stores and compare results again. Any claimed file-move recovery must use synthetic sandbox files only.

## Implementation sequence

1. [ ] Copy and seal current source, verified compiled bundle and selected saved active state. Create and challenge guards before importing the app. Record a ledger in the unique disposable workspace.
2. [ ] Run the exact module list in `final-owner-suite.json`, then selected existing TV/IPTV/acquisition/player/shared suites and all enumerated Node tests. Report counts, failures and skips separately. Native executable tests are not represented as passing source tests.
3. [ ] Boot the recovered app with normal startup behind the guards. Verify owner paths, lease and bundle, recovered API results and desktop Library navigation. Checkpoint/stop/reopen recovered stores, repeat the read assertions and verify no out-of-sandbox state access.
4. [ ] Review isolation and evidence, seal original source again, record exact resource costs and remaining limitations. Preserve artifacts. No branch integration or deployment is part of this pass.

## Acceptance matrix

| Scenario | Expected result | Evidence |
| --- | --- | --- |
| Guarded write/network/subprocess escape | Rejected before execution | Negative-control guard test log |
| Original owner batch | Entire named batch passes on final source | Full unittest log/count |
| Cross-domain regressions | Named suites pass, skips explicit | Python/Node reports |
| Restored store startup | Real current backend imports and starts owners using only copied roots | Startup log and owner/API proof |
| Missing/offline media and provider | No original path/service accessed; honest unavailable state | Guard and API logs |
| Rendered Library | Saved expected canonical titles/order/count; Movie/File return settles | Desktop assertions and capture |
| Graceful stop/reopen | Recovered backend exits and second boot returns matching state | Two boot records and copied SQL checks |
| Existing dirty work | Original tracked/untracked file hashes preserved | Before/after source seal |

## Verification and rollout

The prior owner batch took about 119 seconds, but that is a planning observation, not a promised new duration. Cross-domain coverage is selected from current changed owners; no exhaustive-regression claim is made. Every execution batch is accounted by the fresh job ledger. Dependencies and snapshot master remain unchanged. The live app and production data are not queried or controlled. Historical baseline/write-counter and actual live-completion evidence gaps remain outside this authorization.


## Execution result

See [verification report](../verification/movie-search-retry/isolated-regression-recovery/README.md). Final whole owner batch 451/451 and all 140 Node tests passed; selected cross-domain batch 410 passed, 10 failed, 42 errored. Eight guard controls and abrupt Job Object owner termination passed. Recovery boot/mapping/UI/checkpoint/reopen were not executed. The allowance is closed at 589.508/600 active seconds. Existing source/dirty work preserved; no product or live-state change.


## Approved second bounded pass

Dante: “go ahead with another bounded isolated pass. fix the harness prerequisites, resolve the six assertions without changing behavior, and finish the recovery checks. preserve all existing changes and dont touch the live app or production data.” Reuse copied state and source; new ledger bounded-pass-2.json, 600 cumulative active seconds, 240 per batch, 8 GiB writes, 4 GiB footprint, one worker. Earlier ledger remains closed. Prioritize recovered startup/checkpoint/reopen after guard and six-case preflight; reserve time before broader reruns. No new product behavior or production interaction.

TV baseline was found through the existing active-run.json record, copied under the sandbox and SHA pinned. Allow only read discovery of the exact existing FFmpeg executable; all execution/network restrictions remain. Replace the six obsolete implementation-shape assertions with checks of current authoritative wiring plus compiled behavior coverage: canonical backend health counts and cleanup destinations; quiet current-page refresh; latest-intent/freshness commits; manual full scan and separate ownership refresh; twenty-card Upcoming logical preview and shared scrolling rails; measured Library page size through the read descriptor. Preserve every other assertion and all existing dirty work.

## Second-pass execution result

See [second-pass report](../verification/movie-search-retry/isolated-regression-recovery/pass2/README.md). Six corrected assertions passed. The 462-case cross-domain run had zero assertion failures and one stale temporary evidence-file error (461 passed); it is not a passing full suite. Tests exceeded the 240-second limit (242.864; monitored runtime 248.771), so the whole pass closed at 372.219 cumulative seconds without a ledger reset or further tests.

Recovery passed two normal-mode guarded boots, saved Movie first-page identity/order/count checks, compiled desktop Library navigation, graceful checkpoint/exit and reopening the same stores. Broader compiled Home/Following/Library scenarios and post-reopen eight-store integrity checks remain unexecuted. A future synthetic browser run needs exact server ownership proof; the evidence-file rerun needs a fresh fixture root. No product behavior, live app or production data changed. All 243 runtime inputs and existing dirty work were preserved; the two test-file changes are confined to the six approved methods.

## Approved third bounded pass

Dante: “go ahead with one more bounded isolated pass to close the remaining gaps. fix the fixture and harness ownership first, preserve all existing changes, and dont touch the live app or production data.” Fresh ledger `bounded-pass-3.json`; reuse the existing guarded execution copy and recovered stores. Previous ledgers stay closed. Limits remain 600 cumulative active seconds, 240 per batch, 8 GiB process-reported writes, 4 GiB temporary footprint, one test worker. Stop the whole pass at a safety failure or limit. Setup helpers and failed attempts count. No product/test-source edits, production reads, live requests, live process control, builds, dependency installation, commits or deployment are planned; only disposable harness scripts and additive records change.

1. Seal current safe source inventory, original dirty status, runtime inputs and saved compiled bundle. Each unittest dispatch gets a new exclusive UUID root; retain prior evidence files unchanged. Run the previously failing evidence case repeatedly in distinct fresh roots, and its affected module within budget.
2. Replace synthetic HTTP readiness with a guarded child that binds a random nonproduction port itself, keeps that listener, and writes an exclusive readiness record with exact PID, nonce, root and port. Parent validates the record before HTTP, verifies the same identity through the owned server, and only then launches browser requests. Negative controls reject missing/mismatched PID, nonce, root and production port before network or browser execution. Existing process/network/filesystem guards remain.
3. Use the saved, hash-matching compiled bundle. Run the named existing Library races, stale/error recovery, repeated navigation and Movie/File return; Home backend health counts/destinations and twenty-card Upcoming rails; Following ownership races and full manual scan versus ownership-only refresh. Add a disposable compiled scenario for background refresh on page two, checking unchanged query/page/card identities, no foreground loading, and no notification.
4. Read-only quick/foreign-key checks of eight copied recovered stores after the already completed reopen; compare retained Movie row counts. Do not repeat production/snapshot copying or the already successful two recovery boots.
5. One fresh read-only review, original-source/dirty-status preservation proof, owned-test-process cleanup record, exact cumulative resource report. Keep all earlier partial/failed evidence.

Ruling: reuse the existing execution copy rather than a clean worktree because it contains the approved dirty source and matching compiled bundle; a clean checkout would lose that baseline. Ruling: test only the remaining failed case/affected module and missing compiled/store scenarios; the prior 451 Movie, 140 Node and 461 passing cross-domain cases remain historical passing evidence, not a newly green full suite. Replace repeated blocking whole-tree enumeration with cached-entry footprint sampling on a separate thread and a prompt Job Object deadline, with cleanup margin below the 240-second boundary.

## Third-pass execution result

See [third-pass report](../verification/movie-search-retry/isolated-regression-recovery/pass3/README.md). Fresh UUID fixture roots and exact child ownership validation passed regression controls. The affected TV module passed 20/20, the evidence-file case passed again under another fresh root, compiled desktop checks passed 5/5 Library and 8/8 Home/Following, and all eight copied post-reopen stores passed read-only quick/foreign-key checks with retained Movie counts. Existing guard controls passed. No product/source-test change, live request/control or production-data access occurred.

Fresh read-only review found no Critical/Important issue and confirmed remaining scoped gaps closed. One audit limitation is explicit: the first successful Library child was force-stopped within its owned tree, leaving an empty exit guard report; its boundary was installed before app import. The later Home/Following child stopped gracefully and has a complete guard report with zero violations. Do not claim a complete zero-violation exit audit for Library. Source/runtime seals and original dirty status were preserved; report references are additive. Exact final costs and the closed third ledger are retained with the report. Previous ledgers and failed evidence remain untouched.
