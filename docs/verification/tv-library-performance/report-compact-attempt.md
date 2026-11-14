# Compact TV Library candidate — focused checks passed; full-output gate stopped

2026-10-23, Africa/Cairo. **Implementation is incomplete and application changes were rolled back.** The compact candidate passed focused checks but the exact full-output gate encountered nondeterministic synthetic file timestamps. No memory improvement or live speedup is claimed.

## Approval and source boundaries

Dante explicitly approved fixing probe setup/evidence handling and continuing the revised plan within the remaining 528.91 seconds, with no live restart or production data change. The same run ID (`f5369bde-015b-4c34-acaa-016573a590e0`) and cumulative ledger were retained. Actual dirty source hashes were checked before owner edits. The saved baseline includes existing unrelated read-model/playback changes; HEAD was not substituted for the working tree.

## Probe repair actually completed

Explicitly preload `encodings.idna` and `stringprep` before tracing and list them in the setup manifest. All client/app/fixture/date/weakref setup still precedes tracing; no endpoint warm-up was added.

`ProbeGateError` now carries the invalid record. `record_memory_observation()` writes available peak/residual/setup/failure data using exclusive creation before rethrowing a measurement gate failure; valid records are also written without overwriting history. Unit coverage proves a rejected record is retained and the failure still propagates. These changes do not suppress late-import or memory assertions.

Both new repair assertions failed before the fix as expected; all **five probe contract tests passed** afterward. The formerly missing numeric record from the earlier invalid attempt was not recreated or fabricated.

## Corrected baseline memory observations

Four baseline requests, each in a fresh sequential process, no warm-ups or retries. Same unchanged 6/24-series fixtures: 36 regulars plus two Specials, 2 KiB overview and eight reused guests per episode, four tiny files per series. Imports/client setup precede tracing. Each observation reports no late imports, one Flask context collected and zero repository contexts (baseline source has no Library context). All HTTP statuses 200; no Content-Encoding, with gzip accepted and the real hook installed. Body sizes are below the compression threshold.

| Size / endpoint | Peak increment, bytes | Residual increment, bytes | Body bytes | Candidate peak bound | Candidate residual bound |
| --- | ---: | ---: | ---: | ---: | ---: |
| 6 / cards | 424618 | 21085 | 9094 | 1473194 | 283229 |
| 6 / options | 403071 | 21319 | 172 | 1451647 | 283463 |
| 24 / cards | 624654 | 21030 | 36182 | 1673230 | 283174 |
| 24 / options | 541939 | 21319 | 172 | 1590515 | 283463 |

Harness SHA256 for these observations: `ff3df276d2bbb3fe43a2ad5b40e47f0f123f66c4335a3bd85d38bcbf795364cc`. The candidate observations are **all unrun**, because full-output parity stopped first. This is four valid baseline observations, not a passed eight-observation matrix. Tracemalloc covers Python-managed allocations only; native/total process memory is outside it.

## Candidate source changes, preserved but rolled back

- `services/tv_catalog_repository.py`: one compact request context; stream episode metadata through the unchanged overview decoder to preserve errors, discard payloads/guest credits, retain exactly the 16 state keys; bounded set reads/source encounter order; shared state/series assembly with full standalone episodes preserved; ordinary coverage facts; pruning after paging. Legacy cursor read preserves the existing per-series query ordering. No schema/index/pragma changes.
- `services/tv_read_model.py`: same existing coverage/detail/action formulas, supplied compact rows and coverage facts when context exists; ordinary calls still use full episodes and do not load the entire Library context.
- `services/tv_search.py`: reuse one context for local facts/selected details, retain original source-fact order, prune nonselected data, and use focused two-query options without coverage/cursor/profile work. Existing filter/sort/paging/display policies remain.

The candidate contains no whole-catalog episode overview/guest cache, payload thinning, cross-request cache, frontend change or playback-owner modification. These are source-scope statements, not proof of all unrun contracts.

Candidate source and hashes were saved under the active run's `candidate/services`. A concurrent-change hash guard preceded rollback. Repository/read-model/search were restored byte-for-byte from the run's dirty baseline; pre-existing work remains. Playback was never edited. No application source change from this candidate remains active in the checkout. No application was restarted/reloaded.

## Focused checks actually passed

Owner-only phase: **8 passed**, zero failures/errors/skips, covering compact state/lifetime, malformed metadata, full/state/detail/slice parity, coordinated writer/snapshot freshness and all four physical-version cases.

Integrated focused command: `python -m unittest tests.test_tv_library_read_performance tests.test_tv_stabilization.TVSearchTests tests.test_tv_coverage_contract tests.test_tv_catalog -v -f`.

Result: **48 passed**, zero failures/errors/skips, 20.765 active seconds including process overhead. This includes:

- Exact compact row keys; no retained episode payload/guest/overview markers or rejected cache members.
- Full standalone episode overview/metadata/eight guests retained; exact compact subset and full detail/slice equality.
- Malformed JSON and decoded non-object metadata retain existing failures.
- Snapshot survives a coordinated synthetic write; next snapshot sees it. Concurrent requests produce equal results with distinct contexts/existence maps.
- Available/pending/assigned/invisible membership, fields, options, paging/errors, search filters, coverage, cursor, watched/undo and catalog regressions in the named focused suites.
- Search at most 14 SELECTs, options at most two, and at most one check per path on the six-series unit fixture. The separate exact 24-series counter artifacts were not run.
- Out-of-order inserted episode/source encounter parity against preserved baseline owner code.

These focused passes belong to the preserved candidate. They do not certify the restored checkout as implementing the compact design, and they do not replace broader/desktop/memory gates.

## Exact physical playback identities

The unchanged real TVPlayback adapter passed all four tests through both complete standalone rows and a test-only proxy supplying compact state. Episode IDs 2/3 retain ordered files `[1,2]` / `[3,4]` despite opposing filename/quality priorities.

Default keys: `tv:episode:2:file:1`, `tv:episode:3:file:3`. Saved available nonfirst version yields `tv:episode:2:file:2`; explicit available file 1 overrides it. Removed saved file 2 falls back to file 1; explicitly requesting file 2 fails with `Episode file is missing`; all versions absent fail likewise.

The complete queue is asserted, including current supplied key `tv:episode:2:file:2`, successor `tv:episode:3:file:3` or `missing:tv:3`, every later missing episode and the future episode, with exact titles/sections/availability/reasons. No player launch occurred. Separate stored-available=0 and additional tie/credit cases beyond the tested fixtures remain part of the uncompleted matrix; no broader claim is made. Real desktop Versions/Play remains unrun.

## Full-output failure and its cause

Two baseline artifacts were captured with full route response, every series detail, complete standalone episodes and local rows, using 24 series and out-of-order insertion on the last series. The first corresponding candidate card artifact failed exact equality.

Read-only comparison of those saved JSON artifacts found **exactly 96 differing values, all `episodes.*.versions.*.modified_ns`**. No other parsed key/value/array difference was found. For example the first physical version's stored timestamp was 1792723469748065200 in baseline and 1792723655341116300 in candidate. Separate seeding processes created their synthetic files at different real filesystem times; the repository clock was fixed, but filesystem modification timestamps were not.

This is a fixture determinism defect introduced by extending full-output comparison to include physical version metadata. It is not evidence of a changed product rule. Nevertheless the agreed exact parity gate did not pass. No timestamp field was removed, masked, replaced in saved output or accepted as equivalent by weakening the assertion. No endpoint was rerun. The raw artifacts and `full-output-difference-summary.json` are preserved.

The next correction needs to assign the same fixed filesystem timestamp to every synthetic media file **before binding it**, and independently assert the stored `modified_ns` equals the actual synthetic file timestamp. Keep full output equality intact. Because the fixture input identity changes, a newly authorized comparison must use matching baseline/candidate fixtures and preserve prior evidence; do not silently reuse incompatible baselines or reset the resource ledger. No such corrective fixture edit or new observation was performed after this gate failed.

## Remaining gates and current state

No complete exact full-output gate, candidate memory observations, 24-series counter artifacts, affected-owner broader suite, Node tests, compiled build, real-backend desktop/Versions/navigation/domain checks or optional latency comparison. No performance median/range, speedup percentage or live improvement is available. All matrix rows lacking that evidence remain incomplete. Tests/harness/docs are retained for the next authorized work; prospective compact assertions cannot pass against the restored application source.

Cumulative verification: **140.2619602 / 600 seconds**, remaining **459.7380398 seconds**. The ledger was never reset. One worker, no affinity, no automatic retries. Retained temporary footprint at rollback: **91781489 bytes**, below 1 GiB.

All Python runs used CP_TEST_MODE=1, fresh GUID OS-temp roots, dist under those roots, embedded qBittorrent and synthetic data/media; probe display deterministic, acquisition/monitoring callbacks absent. No production databases/media copied or opened for tests. No temporary server started. Port 5000 remained PID 5264 and port 5127 unused at final read-only inspection.

No live restart/stop/reload/request, production data/config/catalog/dist change, scans/downloads/imports/deletions, real player or system media-client action, hardware/storage tests, delegation/worktree/commit/push/package/tag/release or activation. Source rollback preserved the pre-existing dirty checkout.
