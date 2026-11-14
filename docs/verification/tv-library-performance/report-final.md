# TV Library performance implementation — isolated verification result

2026-10-23, Africa/Cairo. **The compact application candidate remains applied in source, and all44 desktop tests in the five named specs passed.** Matching complete-output, query/path, lifetime and memory gates passed earlier against the identical source. No live activation or whole-request speedup is claimed.

## What changed and why

- `services/tv_catalog_repository.py`: one request-local snapshot retains compact episode state, version/source order and coverage facts. It validates then discards full episode metadata instead of retaining whole-catalog overviews/guest credits. Shared full episode assembly remains authoritative; `episodes()` still returns full metadata/overview/guests/versions/progress. Selected-page preparation prunes unused facts. Focused options read only their required facts. No schema, pragma or persistent cache change.
- `services/tv_read_model.py`: existing coverage/detail/action rules accept compact facts and reuse coverage once per series. Standalone detail remains full and does not load the entire Library context.
- `services/tv_search.py`: Library filtering/sorting/paging/profile/display behavior uses that same request context; options avoid full Library preparation. Physical availability remains fresh per request; no response fields were removed.
- Tests/probe: fixed synthetic file timestamps before binding; prepare Flask/imports/client before tracing; preserve invalid observations and nonvacuous context-collection evidence; test exact physical-version choices/entire queues, metadata errors, snapshot/concurrency behavior and retained-state shape.
- Desktop isolation: simulated terminal playback uses real TVPlayback resolution/history, guards real launch, serves deterministic local artwork, blocks other external traffic and directs all screenshot string forms into CP_TEST_ROOT. No production frontend/CSS change.

## Discover12px root cause and final correction

Dante explicitly approved investigating/fixing the mismatch and continuing within the remaining151.83 seconds, preserving behavior and prohibiting live restart/production changes.

The first controlled attempt waited for fonts, normalized scroll and measured each mode's entire layout synchronously. It passed1366/1920 but failed2048: filter y Movie176 versus TV188, with equal x263, width1734 and height42. Thus the difference was specifically vertical and the initial sampling/scroll hypothesis was insufficient.

The existing TV owner renders `.library-grid-metrics-probe` while sizing/loading or without populated items. It has zero height but remains a child of the Discover grid, so the existing12px grid gap precedes WorkspaceChrome. The test sampled that loading state in TV and a different state in Movie. Corrected test readiness requires a visible TV card and absence of the sizing probe before geometry capture. Production loading behavior remains unchanged; no tolerances increased and no geometry assertion removed. This corrected the approved test case rather than modifying the loading UI.

The separately labeled failed controlled attempt and successful loaded-state attempt are retained. The continuation ruling is recorded in `progress.md`: correction of the same explained fixture/readiness defect remains within Dante's approved investigation/fix; preserve all failed evidence and budget rather than retry unchanged. A genuinely unexplained/application contract failure would still stop.

## Verification evidence

| Gate | Actual result |
| --- | --- |
| Timestamp/setup regression checks | Six passed after the timestamp RED failure. No timestamp field normalized away. |
| Focused Python suite |49 passed, zero failures/errors/skips, against the saved compact candidate. |
| Stored-unavailable physical version | One additional case passed through full and compact adapters after correcting fixture writes to use `store.transaction()`. Earlier uncommitted-fixture failure retained. This was not a newly rerun50-test suite. |
| Complete output parity | Full24-series cards/options/details/standalone episodes/adversarial local rows exactly equal fixed-fixture baseline; only per-process root paths normalized. |
| Structural cards / options |13 /2 SELECTs, one connection each,96 distinct paths, maximum one check per path. |
| Corrected memory matrix | All eight observations valid; all four peak/residual pairs and expected context-collection gates passed. |
| Broader Python suite |51 passed, zero failures/errors/skips; overlaps focused coverage. |
| Node TV search | Three passed, zero failures/skips; earlier console display error did not change child exit0. |
| Final temporary build | Passed; production `dist` unchanged. |
| Final complete named desktop gate | **44 passed, zero failed/skipped/unrun, one worker, zero retries**, reported1.3minutes. Phase exit0. |

Focused command: `python -m unittest tests.test_tv_library_read_performance tests.test_tv_stabilization.TVSearchTests tests.test_tv_coverage_contract tests.test_tv_catalog -v -f`.

Broader command: `python -m unittest tests.test_tv_stabilization tests.test_tv_vertical_slice tests.test_tv_list_filters tests.test_tv_credit_portraits tests.test_tv_relationships -v -f`.

Final desktop phase: cumulative `run_check.py compiled-desktop-discover-loaded powershell.exe -NoProfile -ExecutionPolicy Bypass -File docs/verification/tv-library-performance/compiled_desktop.ps1`, building into temp dist and running `continue-watching`, `native-tv`, `tv-expanded-parity`, `tv-parity`, `tv-stabilization` against the disposable real backend fixture.

The final gate passed Discover parity at1366/1920/2048, poster loaded/contain/ratio cases at1920×1080/1920×720/1366×768, actual File View, shared controls/filter/search/pagination/card enrichment, credits/portraits/filmography, Back navigation, Continue Watching, manual watch/cursor/follow behavior, read-only previews and fixture-only action review. These are desktop sizes, not mobile projects.

Real-backend Library acceptance compares rendered cards with actual route output, opens full episode payloads, chooses a nondefault physical version, asserts the exact played key and persisted selected_file_id, then asserts ordinary Play reuses that exact key. Terminal launch is simulated; native player transport is not covered here.

Physical-version fixtures retain ordered file IDs `[1,2]` and `[3,4]`. Default target keys are `tv:episode:2:file:1` / `tv:episode:3:file:3`; saved nonfirst chooses `tv:episode:2:file:2`; explicit file1 wins, unavailable explicit errors, unavailable saved falls back, all unavailable errors. The supplied current queue key remains file2; successor is file3 or `missing:tv:3`; complete later missing/future queue titles/sections/reasons are compared. Stored available=0 with existing files is now independently covered.

## Memory results and limits

All values below are bytes of Python-managed allocations, not RSS/native memory. Each observation used the same corrected probe SHA256 `ff3df276d2bbb3fe43a2ad5b40e47f0f123f66c4335a3bd85d38bcbf795364cc`, fresh synthetic process, no warm-up, prepared client, one real registered route dispatch, full body consumption and post-release collection. Zero late imports; all expected repository and Flask contexts collected. Candidate cards create exactly one repository context; options/baseline create zero. Each request creates one collected Flask context.

| Size / endpoint | Baseline peak | Candidate peak | Peak limit | Baseline residual | Candidate residual | Residual limit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
|6 / cards |424618 |271389 |1473194 |21030 |21024 |283174 |
|6 / options |403071 |51443 |1451647 |21319 |21319 |283463 |
|24 / cards |624654 |981311 |1673230 |21085 |21142 |283229 |
|24 / options |541939 |107631 |1590515 |21319 |21264 |283463 |

**The24-series card peak increases57.10%; it passes because it remains within the approved additive1MiB allowance.** This is a bounded-memory pass, not a claim that memory decreased everywhere. Peak/residual limits were not changed. Response bodies matched (cards9094/36182bytes, options172bytes), HTTP200, gzip accepted but unused below threshold. The probe includes real route serialization/timing/compression hooks with deterministic display; it excludes production acquisition/monitoring callbacks. Native allocations and production catalog scaling remain outside this evidence.

## Contract comparison and remaining limits

| Contract group | Evidence / remaining limit |
| --- | --- |
| Membership/order/counts/options/filtering/paging/errors | Focused assertions and exact complete artifacts pass. |
| Full public metadata, overview, guest credits, versions/progress and action values | Exact full episode/detail/local-row artifacts plus independent concrete assertions pass; no payload thinning. |
| Fresh physical availability, source/version order, coverage/cursor/watched rules | Counters, concurrency/snapshot cases, named coverage/catalog/vertical-slice/stabilization suites and relevant real desktop interactions pass. |
| Request lifetime/retention and malformed metadata | Shape/error assertions and valid8-observation memory/collection gate pass. |
| Physical version/entire queue and saved later Play | Exact standalone/compact tests and real route-to-rendered Versions/Play case pass. |
| Named desktop callers/states/navigation/geometry | All44 named cases pass. Loading probe behavior is preserved; geometry comparison now explicitly uses populated state. |
| TV Lists / other shared callers | Python list/filter/relationship coverage passed. No separate new Lists or IPTV browser smoke was run; do not extend the44-case claim to every product screen. Production shared frontend was not edited. |
| Speed and live behavior | No uninstrumented latency comparison or live activation/capture; no measured speedup claim. |

Optional16-request latency required express approval and sufficient remaining time under the plan; it was not explicitly requested and did not run. No further tests were launched with19.41seconds remaining. The named gates provide bounded regression evidence, not an exhaustive guarantee across all production data/hardware.

## Final source/evidence state and resource cost

Checkout `C:\Users\dante\Desktop\cinema paradiso`, master, HEAD `be511f98846a67a182e5b371ad087938e9344362`; existing dirty work preserved. The three application owner hashes match `candidate-hashes.json` exactly. They remain applied after the successful gate; earlier rollback reports are historical. `tv_playback.py` still equals the pre-task dirty baseline. No new commit/worktree/delegation/publication.

Evidence run `930057e1-4f6e-4758-82bc-3c28a263aaeb`, beneath the task root recorded in `task-root.txt`. `final-evidence-manifest.json` records SHA256 identities for application owners, tests, native fixture, artwork, probe and runners. Earlier corrected full-output/structural/memory artifacts remain in the same run; older rejected/invalid runs remain separate.

Final compiled root: `C:\Users\dante\AppData\Local\Temp\cp-tv-library-6c63f44b-c527-4646-8563-835031b1d28c\d6fb1dad-ffca-4f7a-8304-961b96a3e464`. Final log: `<current-run>\compiled-desktop-discover-loaded.log`. Screenshot files, including all template-literal paths, are beneath that root's `screenshots\docs\verification\tv-normal-import\parity`; the existing repository screenshots still hash-match their preserved originals. Visual inspection confirmed the full local poster border/geometry and rendered desktop detail layout. Artwork is synthetic and does not prove real CDN availability/content.

Original cumulative verification: **580.5899602 /600 active seconds consumed;19.4100398 remain**. This approval consumed132.422seconds: failed controlled phase43.547 plus successful loaded phase88.875. All failed attempts/builds are retained in the original ledger; it was never reset. Final retained temp footprint: **396440688bytes**, below1GiB.

Temporary server cleanup succeeded; port5127 is unused. Live port5000 remains PID5264. Main compiled CSS hash matches unchanged production `dist/assets/index-C4xx5e9F.css`. No live HTTP request/restart, production catalog/config/data/dist modification, real player launch or hardware/storage testing occurred. This is **source implementation with isolated verification**, awaiting any separately authorized live activation.
