# TV Library performance — corrected fixtures passed; desktop gate stopped

2026-10-23, Africa/Cairo. **Implementation remains incomplete.** The compact candidate passed exact output, structural and memory gates, then an existing Movie control-height assertion stopped desktop verification. The three application owners were preserved and restored to their pre-edit dirty baseline. Test/probe/harness/document changes remain. No live speedup or fully green checkout is claimed.

## Authorization, identities and isolation

Dante approved: “go fix the fixture timestamps and continue implementing the revised plan and isolated checks within the remaining 459.74 seconds. dont restart the live app or change production data.”

Checkout: `C:\Users\dante\Desktop\cinema paradiso`, `master`, HEAD `be511f98846a67a182e5b371ad087938e9344362`. Existing dirty work was preserved; HEAD was not used as the source baseline. Current evidence run: `930057e1-4f6e-4758-82bc-3c28a263aaeb`, beneath the original task root recorded in `task-root.txt`. Earlier failed/invalid observations remain separate and unchanged.

Task root: `C:\Users\dante\AppData\Local\Temp\cp-tv-library-6c63f44b-c527-4646-8563-835031b1d28c`.

All Python phases used test mode, fresh GUID temp roots, synthetic data/media and embedded/mock client transports. Build output and desktop artifacts were directed inside the temp root. Desktop requests used port 5127, with external browser HTTP(S) blocked. Player opening/process launch was prohibited; the terminal playback stub used real TVPlayback resolution and history against synthetic files. The temporary server was stopped in cleanup. Port 5000 remained owned by PID 5264; no live HTTP capture, restart, production data/configuration edit, production dist replacement, commit or publication occurred.

## Fixture and probe correction

Synthetic files now receive access/modification timestamps of `1600000000000000000` ns before binding. An assertion checks both filesystem and stored `modified_ns`; it failed before the fix and passed afterward. No response field or comparison was omitted. Setup/timestamp suite: **six passed**.

The corrected probe prepares Flask, its real client, IDNA/stringprep imports, fixtures, clocks and weak references before tracing. There is no warm-up dispatch. It traces one actual registered route through serialization and installed response hooks, consumes the complete body, releases response/client/context references, collects once and records residual bytes. Invalid records are preserved before propagating failure; output creation never overwrites older observations.

All eight observations in this run use probe SHA256 `ff3df276d2bbb3fe43a2ad5b40e47f0f123f66c4335a3bd85d38bcbf795364cc`. Each reports valid setup, zero late imports, HTTP 200 and one Flask request context created and collected. Candidate cards create exactly one repository context, collected after release; baseline and options create zero. All bodies were consumed; gzip was accepted but no encoding applied at these fixture body sizes (cards 9094/36182 bytes, options 172 bytes).

This probe uses real TV route registration and timing/compression hooks on a small Flask application with deterministic metadata display. Acquisition/monitoring callbacks are excluded. It is not a whole production application memory measurement.

## Candidate and passing gates

The preserved compact candidate changes the existing repository/read-model/search owners. One request-local snapshot retains shared episode state and coverage facts; it validates and discards full episode metadata instead of retaining overviews/guest credits across the catalog. Shared full episode assembly, coverage/detail policy, encounter order and playback selection remain authoritative. Paging prunes nonselected retained facts; options use a separate focused projection. No frontend, playback-owner, schema, pragma, persistent-cache or response-thinning change was made.

Focused command: `python -m unittest tests.test_tv_library_read_performance tests.test_tv_stabilization.TVSearchTests tests.test_tv_coverage_contract tests.test_tv_catalog -v -f` — **49 passed**, no failures/errors/skips.

Complete 24-series cards/options artifacts, all standalone episode payloads, details and adversarial local-row order compared exactly with the matching fixed-timestamp baseline. Only per-process fixture-root paths are normalized. Physical timestamps, metadata, overview, guests, versions, progress and array order are compared.

Structural route observations at 24 series:

| Endpoint | SELECTs | Connections | Distinct paths | Maximum checks per path |
| --- | ---: | ---: | ---: | ---: |
| Cards | 13 | 1 | 96 | 1 |
| Options | 2 | 1 | 96 | 1 |

Corrected memory matrix, bytes of Python-managed allocations:

| Size / endpoint | Baseline peak | Candidate peak | Peak limit | Change | Baseline residual | Candidate residual | Residual limit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 6 / cards | 424618 | 271389 | 1473194 | -36.09% | 21030 | 21024 | 283174 |
| 6 / options | 403071 | 51443 | 1451647 | -87.24% | 21319 | 21319 | 283463 |
| 24 / cards | 624654 | 981311 | 1673230 | +57.10% | 21085 | 21142 | 283229 |
| 24 / options | 541939 | 107631 | 1590515 | -80.14% | 21319 | 21264 | 283463 |

**All four peak/residual pairs pass the unchanged bounds, including the additive 1 MiB peak allowance.** The 24-series card peak increases; this is not a claim that memory decreased everywhere. Expected contexts are collected in all eight observations. These results exclude native allocations/RSS and do not guarantee production catalog scaling. Raw records and `memory-comparison.json` are in the current run directory.

Broader command: `python -m unittest tests.test_tv_stabilization tests.test_tv_vertical_slice tests.test_tv_list_filters tests.test_tv_credit_portraits tests.test_tv_relationships -v -f` — **51 passed**, no failures/errors/skips. This overlaps focused tests; do not add the counts as unique coverage.

`node.exe --test tests/tv_search.test.mjs` — **three passed**, zero failures/skips, child exit 0. The wrapper encountered a console Unicode error while displaying the saved successful output. Its stdout encoding was corrected; the suite was not rerun or misclassified as a Node failure.

## Compiled desktop gate and exact stop

Temporary `npm.cmd run build -- --outDir <CP_TEST_DIST_DIR>` passed. Five named desktop specs were copied to the isolated runner with imports/screenshot paths redirected, one worker, zero retries, fail-fast after one failure. Existing assertions were preserved. Main CSS SHA256 matched the on-disk production `dist/assets/index-C4xx5e9F.css`; no frontend source was edited by this task.

Result: **21 passed, one failed, 22 did not run**, 48.9 seconds. The runner also reports “1 error was not a part of any test” alongside “Testing stopped early after 1 maximum allowed failures”; no separate error stack is present in the retained log. This is not a green full desktop suite.

Passing desktop cases included Continue Watching, native TV navigation/selections/follow/streaming/watched/cursor/review, expanded credits/portraits/rails/filmography/Back/error behavior, identity-review card retention, and the new real-backend Library card/version test. The new test compared rendered cards with the actual backend response, opened full episodes, chose a nondefault physical version, checked its exact played key and saved selection, then verified ordinary Play reused that exact key.

Failure: `Discover and Library use the in-page media rows and TV File View shows native TV files`, in `tests/e2e/tv-parity.spec.js`, assertion `expect(movieSwitch.height).toBe(40)`: **received 36**. It fails on Movie Library before switching to TV. The existing frontend/test expectation disagree; an isolated baseline desktop rerun was not performed, so causality is not experimentally established. Neither the UI nor the 40 px assertion was changed to obtain a pass. Resolving that disagreement requires checking intended shared-control behavior, not weakening this assertion as part of the TV backend refactor.

Retained compiled evidence root: `<task-root>\8b17571d-a836-4b3b-a77c-3e5dabb2ee15`. Screenshot, error context and trace are under `playwright-results\tv-parity-Discover-and-Lib-08ef6--View-shows-native-TV-files`. Full build/test/cleanup output: `<current-run>\compiled-desktop.log`. Cleanup terminated only the owned fixture server tree; port 5127 no longer listened afterward.

No request, retry or latency comparison followed the failed gate. There are no isolated latency median/range results or production speedup measurements.

## Contract coverage and remaining limits

| Contract | Current evidence / limit |
| --- | --- |
| Membership, ordering, filters, options, counts, paging and empty/error behavior | Focused tests and full fixed-fixture output equality passed. |
| Full public metadata, episode overviews, guests, versions and progress | Exact full artifacts and independent payload assertions passed; no payload thinning. |
| Fresh availability, request-local lifetime, malformed metadata, snapshot/concurrent request behavior | Focused assertions and valid memory/context gates passed. |
| Coverage, watched/undo and cursor rules | Named coverage/catalog/stabilization/vertical-slice suites passed; relevant native desktop cases passed. |
| Physical-version selection and complete playback queue | Four standalone/compact cases passed: ordered defaults, saved nonfirst, explicit override, missing saved/explicit files and missing successors. Entire queues compared, not prefixes. Stored-available=0 was not added as a separate new adverse fixture. |
| Real Library rendering and persisted Versions/Play identity | New real-backend desktop case passed, including exact saved nondefault key and later ordinary Play. |
| All existing desktop controls/navigation/callers | Incomplete: one control-height failure and 22 unrun cases. No blanket parity claim. |
| Whole-request latency or live improvement | Unmeasured; latency gate unrun and live app unchanged. |

## Rollback, retained work and resource balance

The successful candidate's three owner files and hashes are saved in `<current-run>\candidate\services` and `candidate-hashes.json`. After a concurrent-change guard, only these application owners were copied back from the current run's pre-edit dirty baseline and their hashes verified:

- `services/tv_catalog_repository.py`: `E65DDDC6C75742BA69AA35DCC6CF80325849F08ABE21C1CD5433EB8A8D3E615A`
- `services/tv_read_model.py`: `640E88A395B3E05348FAB64FCB9676AB1175ED450DBA96889BA82D28292D3860`
- `services/tv_search.py`: `43C005522957C16C97E65EDBCB1359D5FEAD6CD64A5B369D17216149F1B108CC`

`services/tv_playback.py` was never edited. Existing dirty work remains. Probe, deterministic fixtures, prospective regression tests, isolated server/desktop harness and reports remain in the checkout. The compact-context assertions require the preserved candidate; they are not expected to pass against the restored application source. No post-rollback green-suite claim is made.

Original cumulative budget: **295.1509602 / 600 active seconds consumed; 304.8490398 remain**. Current approval consumed 154.889 seconds, including failed characterization/build/desktop work. Retained temporary footprint at inspection: **204594295 bytes**, below 1 GiB. No hardware/storage testing or live activation occurred. Further verification must explicitly address the stopped desktop gate and preserve this same balance; unused budget is not permission to retry automatically.
