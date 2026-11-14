# TV Library performance — memory gate blocked; source rolled back

2026-10-23, Africa/Cairo. The approved candidate reduced repeated work and passed focused parity checks, but failed the required memory gate. This is an incomplete implementation, with no active application change and no demonstrated speedup.

## Authorization and baseline

Dante approved implementation and isolated checks, then replied "go" to correction of the first fixture error and resumption from the remaining 592.63 seconds. Both approvals and boundaries are recorded in the plan. The cumulative 600-second budget was never reset.

Checkout: master, be511f98846a67a182e5b371ad087938e9344362, with substantial pre-existing dirty/untracked work. All comparison baselines use preserved actual pre-task source, including the existing read-model and playback changes. No historical database optimization candidate was used. Source hashes were checked again immediately before owner edits.

## Candidate changes and rollback

The candidate changed only these application owners:

- `services/tv_catalog_repository.py`: TVLibraryReadContext and 13 set SELECTs in a short deferred read snapshot; focused two-query options facts; shared series/episode assembly; optional context for series, episodes, hydration and viewing cursor; coverage facts. Filesystem checks ran after closing the database connection and once per distinct stored path.
- `services/tv_read_model.py`: optional context passed through the existing coverage formula/detail projection; coverage reused within the request. No second coverage or playback rule.
- `services/tv_search.py`: Library search reused one context for local rows and selected details; Library options used metadata/bound-path facts instead of full preparation. No persistent cache, payload thinning or frontend changes.

The unchanged response fields, filter/sort logic, profile evaluation, metadata display call and TVPlayback selection owner remained in place. These statements describe source scope; only the checks below establish observed parity.

After the failed gate, candidate source and SHA256 hashes were retained under `candidate/services` in the task OS-temp evidence. A concurrent-change hash guard ran before rollback. All three owners were restored byte-for-byte from the captured dirty baseline. Playback was never modified and its hash also matches the baseline. Pre-existing edits were preserved.

Retained workspace changes: the corrected new regression fixture/suite, four additive tests in `tests/test_tv_catalog.py`, authorization/status documentation, budget/probe scripts and evidence pointers. The context/structural tests are prospective: they will fail against the restored application source until an approved replacement is implemented. No post-rollback green suite is claimed.

## Tests and full-output parity

| Phase | Result | Meaning |
| --- | --- | --- |
| Original pre-change focused suite | 29 passed; zero failures/errors/skips | Tested baseline behavior |
| First new suite | 15 run: 11 passed, three expected structural/interface failures, one fixture-input error | Historical first stop; required pending path was missing |
| Explicitly authorized corrected characterization | Two passed; zero failures/errors/skips | Exact membership/detail/options and paging/error expectations passed before owner changes |
| Candidate focused command | 38 passed; zero failures/errors/skips | New suite plus TVSearchTests, coverage contract and catalog suites |
| Full real-route comparison | Cards, options and every series detail on 24-series fixture exactly matched parsed baseline output | All keys, nested values, nulls and array order compared; fixed clock/day; deterministic display stub |

Candidate command: `python -m unittest tests.test_tv_library_read_performance tests.test_tv_stabilization.TVSearchTests tests.test_tv_coverage_contract tests.test_tv_catalog -v`.

The route probe used the real `register_tv_routes` handlers and the production timing/compression hooks on an isolated Flask app, with synthetic repository, no acquisition/monitoring callbacks and deterministic display transport. It does not prove full application composition, compiled desktop behavior, or live parity.

Structural evidence:

| Version / fixture | Endpoint | SELECTs | Connections | Distinct paths | Max checks per path |
| --- | --- | ---: | ---: | ---: | ---: |
| Baseline, six series | Cards | 113 | 50 | 24 | 3 |
| Baseline, six series | Options | 40 | 19 | 24 | 2 |
| Candidate, 24 series | Cards | 13 | 1 | 96 | 1 |
| Candidate, 24 series | Options | 2 | 1 | 96 | 1 |

Monitoring/profile service reads were absent from the isolated route probe and excluded from these counts; they are not claimed optimized. Structural counts are not latency measurements.

## Exact physical playback and queue identities

The four required named tests passed both before refactoring (standalone) and in the candidate (standalone and supplied-context assembly), through the real TVPlayback adapter without a real player.

Episode IDs 2 and 3 had exact ordered file IDs `[1, 2]` and `[3, 4]`. Low-quality `z-low` was inserted before high-quality `a-high`, so fallback could not pass by sorting quality or filename.

- No saved choice: exact targets `tv:episode:2:file:1` and `tv:episode:3:file:3`.
- Saved available nonfirst version: `tv:episode:2:file:2`; explicit available file 1 overrides it.
- Saved version 2 absent: fallback `tv:episode:2:file:1`; explicit file 2 raises `Episode file is missing`. Both versions absent: same missing-file error.
- Queue retained supplied current key `tv:episode:2:file:2`. Successor key remained `tv:episode:3:file:3`; with both successor versions absent, key `missing:tv:3`, availability false and reason `Episode is missing locally`. Exact titles and Season 1 sections were asserted for those entries.

The real-backend Versions/Play desktop case remains unrun, so the complete physical-version gate is not satisfied.

## All eight memory observations

Exactly one request per version/size/endpoint, each in a fresh sequential Python process. Fixture: 36 regulars plus two Specials per series; deterministic 2 KiB overview and eight reused guest people per episode; four tiny files per series, at most 96 total. Inputs, effective day and dependencies matched. No warm-ups, retries, larger fixtures or threshold changes.

All eight responses were HTTP 200 with no Content-Encoding; cards were 9094 bytes at six series and 36182 at 24; options were 172 bytes in both sizes/versions. `Accept-Encoding: gzip` and the real hook were used, but these response bodies did not reach its compression threshold. No second JSON parse occurred inside tracing.

All numbers below are absolute bytes. Peak limit is baseline + max(1048576, 10% of baseline); residual limit is baseline + 262144.

| Size / endpoint | Baseline peak | Candidate peak | Candidate change | Peak limit | Peak result | Baseline residual | Candidate residual | Residual limit | Release result |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| 6 / cards | 1097798 | 2647688 | +141.18% | 2146374 | FAIL | 688170 | 688198 | 950314 | PASS |
| 6 / options | 1075866 | 805965 | -25.09% | 2124442 | PASS | 687953 | 688619 | 950097 | PASS |
| 24 / cards | 1297917 | 8643817 | +565.98% | 2346493 | FAIL | 688253 | 687844 | 950397 | PASS |
| 24 / options | 1215278 | 833545 | -31.41% | 2263854 | PASS | 688538 | 688109 | 950682 | PASS |

Candidate card requests each created one independently weak-referenced repository context; both were collected after response/client release and garbage collection. Options created no repository context. Every residual comparison passed. This indicates no observed retained request context; it does not excuse the peak failures.

**Probe procedure defect:** source review after the observations found that the Flask client was constructed after tracing began. Flask's `test_client()` lazily imports its testing module; this setup work therefore may be included in all eight observations, contrary to the plan's imports-before-tracing requirement. The numbers are preserved unchanged, not certified as a clean execution of the exact planned memory procedure. No automatic remeasurement was performed. The observed card peaks independently exceed their bounds, and the procedure defect also blocks declaring the gate passed.

`tracemalloc` measures Python-managed allocations, not total process/native SQLite/compressor memory. Instrumented request times are not performance evidence.

## Why this stopped and what needs review

Confirmed source mechanism: the candidate retained every series' full assembled episodes in `assembled_episodes` until the Library request finished. Those rows retained raw metadata, decoded overview and guest-credit dictionaries together. Popping raw episode/credit maps prevented a second set of row dictionaries but did not shorten the lifetime of the full assembled catalog. This is consistent with the measured card peak growth. It is not a leak after release.

The next design review should address the internal requirement to retain full episode projections for all Library series. Preserve full public responses and the existing coverage/playback owners, but identify which facts the Library projection actually consumes and shorten full metadata/credit lifetimes. The reviewed plan currently requires full supplied-context episode assembly, so replacing that retention contract needs an explicit design amendment before coding. No field removal, weaker freshness, version reorder, cross-request cache, schema change or threshold increase is recommended. This report does not approve a replacement design or another measurement pass.

## Acceptance coverage and remaining uncertainty

| Contract/matrix area | Candidate evidence | Remaining gap |
| --- | --- | --- |
| Membership, ordering, counts, paging, metadata and options universe | Explicit available/pending/assigned/invisible fixture; full 24-series route/detail equality; focused search tests | Complete matrix of tie/sort/malformed cases not independently added |
| Full API fields, cast and shared episode assembly | Full response/detail equality; standalone/context episode and slice equality | Broader credits/portraits and shared callers unrun |
| Coverage, Specials, hydration, watched/undo and durable cursor | Existing focused coverage/catalog/search tests passed | Full rendered and all adverse-state matrix not completed |
| Fresh physical truth / multiple versions | Remove/recreate file freshness assertion; exact version/target/queue tests | Real desktop Versions/Play and all queue entries beyond asserted motivating entries unrun |
| Options source choices and bounded work | Exact basic choices; full baseline equality; two-query bound | Complete adverse source/future/shared-path matrix not separately implemented |
| Profile/provider/legacy/shared caller behavior | Existing TVSearch tests and unchanged owner logic | Full affected-owner suites and real composition unrun |
| Snapshot concurrency, writer interaction, error/retry breadth | Deferred snapshot inspected in candidate | Coordinated concurrency/writer tests unrun |
| Memory | Eight observations retained; two card peak failures, all release checks passed | Exact procedure uncertified due client setup; approved design failed observed peak bounds |
| Desktop layout/loading/navigation/selection and domain smoke | Frontend source unchanged | Build and all desktop checks unrun |
| Latency and live behavior | None | Zero of sixteen optional latency requests; no median/range or live speedup claim |

## Resource budget and boundaries

Active verification: **65.6219602 / 600 seconds**, remaining **534.3780398 seconds**; do not reset on future work. One worker, no affinity. Retained OS-temp footprint at rollback: **48937182 bytes**, below 1 GiB. Eight memory observations and output/structural checks are included in that cumulative time. No hardware polling, growth/stress/storage benchmark or overnight work.

All Python runs set CP_TEST_MODE=1, GUID OS-temp CP_TEST_ROOT, CP_TEST_DIST_DIR inside that root and embedded qBittorrent mode. Synthetic data/media only. No unchanged Playwright wrapper used. No temporary server started. Broader Python suites, Node tests, build, desktop tests and optional latency gate were not run after the memory stop.

No production database/media copied for testing; no live restart/stop/reload/request, production dist overwrite, production catalog/config mutation, scan/download/import/deletion, system media-client action, delegation, worktree, commit, push, package/tag/release or activation. Read-only listener inspection after rollback showed port 5000 still owned by PID 5264; port 5127 unused. No live improvement is claimed.

Evidence root is recorded in `task-root.txt`. Raw eight observations, full response artifacts, per-phase logs, budget, pre-task/candidate source and hash manifests remain there. `memory-comparison.json` in this folder provides the compact numerical comparison. Author review only; no delegated review.
