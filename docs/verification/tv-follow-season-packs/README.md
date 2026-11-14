# TV Follow season packs — source implementation evidence

Source scope approved by Dante on 2026-10-10 after the explicit P1/P2 decision question. Implementation and disposable verification use managed branch `codex/tv-follow-season-packs`, based on `be511f98846a67a182e5b371ad087938e9344362`. Production activation remains outside this plan.

## Result and ownership

- `tv_filename_parser.py` has one shared season-declaration owner. Agreeing `Season 2 S02` is a pack; contradictory `Season 2 S03` and `Season 2 3x01` are conflicts. Number-bearing titles, daily/range/absolute numbering and existing manifest consumers retain their behavior.
- `TVAcquisition` classifies transport by scheme, reuses the existing allowed resolver, and retains hash disagreement/origin/trust/profile checks. The existing recommendation loop is now the one `plan_releases` implementation used by manual and automatic planning.
- Follow Missing considers packs first for eligible fully missing released seasons. Quality precedes coverage. Complete packs can satisfy authorized non-due siblings; individual/partial candidates cannot. Episode-query fallback evaluates returned packs against the season's remaining authorized targets. It does not reduce a full pack to the queried episode.
- `TVMonitoring` persists one intent and every covered task association before an external add. Reservation is submission pending; acknowledgement is queued; verified episode bindings are acquired. Recovery adopts the same intent/job after interrupted submission. Cancellation rechecks ownership and handles one shared transfer once.
- Version 4 adds bounded, attributed diagnostics. Source review has no transfer intent and continues the five-hour retry. Transfer/import review retains its intent and recovery path. The existing desktop dialog handles explicit manual confirmation; no permanent show trust is introduced.

## Verification gates

Final focused/full/desktop results are recorded below. Logs preserve the actual exits and earlier failures instead of treating a focused success as a green full suite.

| Gate | Result/evidence |
| --- | --- |
| Pre-change Python baseline | 1667 tests, seven failures; `baseline-python.log` |
| Parser/workflow/catalog/contract initial gate | 55 passing; `recognition-green.log`; five motivating failures in `recognition-red.log` |
| Node regression suite | 119 passing, no skips; `node-completed.log` |
| Final build | Successful isolated Vite build; `build-completed.log`; production `dist` not built |
| Final TV focused gate | 184 passing in 258.751 seconds; `focused-completed.log`; a subsequent supplemental 13-episode import/cleanup check passed in `thirteen-episode-green.log` |
| Final complete Python gate | 1700 tests in 599.557 seconds, six failures: five recorded baseline failures and an additional IPTV projection timing failure; `full-python-completed.log`. This gate is not green. |
| Additional IPTV timing investigation | The unchanged module rerun has seven passes and one timing failure; its single-test rerun also fails. A pristine baseline single-test run passes. All twelve loaded project dependencies match the pristine baseline and no changed TV module is loaded; `iptv-timing-*.log`, `iptv-timing-dependency-check.json`. The timing failure remains unresolved outside this source scope. |
| Final compiled desktop | 30 passing, no skips: pack 3, native TV 7, download contracts 9, normal import 6, stabilization 5; five `desktop-*-completed.log` files; each spec receives a fresh disposable server |
| Main checkout delivery | Twelve source/test/document files copied from the isolated worktree with matching SHA-256; all 34 new regression tests pass from the main checkout in 91.793 seconds; `source-delivery.json`, `main-checkout-tests.log` |
| Independent review | Six important findings reproduced and corrected; final narrow review found no unresolved Important issue; no critical or deferred important findings |

Baseline failures: awards offline-input reproducibility; two power API assumptions about embedded qBittorrent; one qBittorrent proxy assumption under system mode; an existing streaming JSX source-shape assertion; two routes checked before their isolated dist existed. A subsequent compiled run removed the two dist-environment failures. No assertion or unrelated owner was weakened to hide these failures.

The completed full run also failed `ProjectionAndWorkerTests.test_movies_get_is_pure_and_projection_is_nonblocking_progressive`: its nonblocking call took 11.8586 seconds against an unchanged one-second assertion. This extra failure was absent from the pre-change and earlier compiled full runs. The module rerun executes eight tests with one timing failure (3.0776 seconds); the current single-test rerun also fails (1.5479 seconds). A pristine `be511f9` source archive runs that single test successfully in 0.781 seconds total. Every one of the twelve project modules loaded by the test matches that archive byte-for-byte, and none of the four changed TV backend modules is loaded. The evidence identifies a run-dependent timing failure in unchanged IPTV code, not a changed-TV execution path. Its underlying timing cause remains unresolved and it is not relabeled as a confirmed baseline failure. No unrelated IPTV code or timing assertion was changed.

The interim full run loaded an invalid synthetic hash (`g` is not hexadecimal) in the new seven-episode fixture before that fixture was corrected. Its six failures consisted of five baseline failures and that fixture failure. The corrected test is green; final full-suite evidence is separate. The interim 179-test focused run also loaded a diagnostic test whose 21 identical provider rows correctly deduplicated to one release. The fixture now provides 21 distinct releases. These were test-data corrections, not changed product expectations.

## Contract comparison and acceptance evidence

| Approved/preserved rule | Observable evidence |
| --- | --- |
| P1: eligible complete season, equal quality pack first | `test_follow_prefers_one_pack_and_associates_every_target`; one season query, one add, one intent, three queued members |
| Quality before coverage; no overlapping selection | `test_quality_precedes_coverage_and_gaps_do_not_overlap`; existing manual/multi-season workflow suite |
| Full pack found by an episode query remains a full pack | `test_pack_found_by_gap_query_is_planned_once_for_the_remaining_season`; season + one gap query, one add, three queued |
| Deferred query keeps full scope and excludes earlier work | Deferred pack covers the non-due original trigger; immediate/deferred overlapping packs are rejected; new local ownership becomes acquired without a redownload |
| Non-due targets have no early individual query/preparation | Full-pack/non-due and non-due-singleton tests; clock assertions |
| Deferred work reaches later gaps and keeps its clocks | Seven-episode bounded fallback test; queries `season,1,2,3,4` then `5,6,7`; no repeated season query |
| Partial ownership, release dates, claims, scope and exclusions | `test_grouping_excludes_owned_unreleased_claimed_partial_and_bulk_scopes`; real worker passes in independent stores |
| Frozen Missing snapshot | `test_missing_snapshot_never_expands_when_later_episode_metadata_arrives`; later metadata does not add targets or enable whole-season grouping |
| Five-hour P2 source retry; deduplicated notifications; later eligible recovery | `test_manual_quality_is_review_and_still_retries_in_five_hours`; no query at 17999 seconds, retry at 18000, same unread count, later BluRay queues |
| Hard conflicts cannot be manually confirmed through source review | Wrong-show/manual-quality diagnostic test and contradictory season tests; existing wrong-year/provider/manifest suites |
| Scheme normalization preserves validation | HTTP-in-magnet regression, wrong origin/hash tests and existing supported-link/hash-swap/trust-removal tests; no add during preparation |
| Durable association/recovery, one add | Orphan reservation, post-association failure and actual saved-job/lost-acknowledgement tests |
| Cancellation does not revive a stopped task | In-flight search cancellation and unassociated reservation cancellation tests; existing playing/shared/ownership protection suites |
| Transfer errors are review, never replaced by another source | `test_pack_transfer_recovery_failure_is_review_with_intent_preserved` |
| Version-3 upgrade preserves shared data | Migration/reopen snapshots of customized profiles/defaults, tasks/clocks, TV and Movie intents/claims, events and notifications; future version refused |
| Attributed bounded diagnostics | 21 distinct evaluations, three failed sources, five displayed candidates, redacted provider links; empty-result and preparation-failure classifications |
| Actual compiled desktop and import path | Two viewports, existing manual dialog, blocked wrong season, explicit Start, one intent, real manifest/import/cleanup owners, Versions, Close/Escape/focus and repeated Back/Forward |
| Thirteen-episode season scale | `test_thirteen_episode_pack_verifies_every_binding_and_cleans_staging_once`; 13 queued/acquired, one add, 13 published files, staging removed, task completed |
| Other CP surfaces retained | Existing native TV, manual lower multi-season, normal import, stabilization, Node and broad Python suites; full-suite limitations listed separately |

Desktop media/network are synthetic: providers, qBittorrent transport and video probe are fixtures, while acquisition, SQLite claims, manifest mapping, verified publication, cleanup, API and compiled UI run their actual owners. These checks do not prove a live screenshot torrent's availability or its measured codec.

## Review findings and execution rulings

1. The reviewer found bounded-pass starvation. Deferred gap work now carries a continuation marker without advancing search/retry clocks; later passes reach later episodes. Red/green evidence: `review-red.log`, `review-green.log` and final focused/full gates.
2. The reviewer found submitted/import-pending job errors remained displayed as queued. Associated job review/validation/import/cleanup failures now project review while preserving their intent. Red evidence: `transfer-review-red.log`; green in final gates.
3. The reviewer found contradictory `Season 2 3x01` declarations escaped conflict checks. The shared declaration extractor now includes `NxNN` episode forms. The exact contradictory title is asserted.
4. The reviewer found wrong-show plus manual-only quality could expose misleading manual review. Hard identity conflicts now remain rejected without a review action.
5. The final implementer check found a pack returned only by an episode query was truncated to one target. Provider query scope is now distinct from authorized planning scope through the existing search owner. Red/green evidence: `gap-pack-red.log`, `gap-pack-green.log` and final gates.
6. Preserve the already explicitly enabled automatic-upgrade profile caller. Ordinary manual and Follow Missing submissions still reject newly owned targets. Removing this existing explicit exception would change an excluded caller's contract.
7. A simulated failure before add must report no remote torrent. An inherited fake torrent otherwise correctly invokes lost-acknowledgement recovery. A separate test exercises an actual saved owned job after add, proving no duplicate submission.
8. Existing E2E specs do not all clean up their queued fixture episodes. Combining them in one server produced inherited active claims and cascading failures. Each complete spec now runs against a fresh disposable server, preserving all product assertions and leaving existing test/source behavior unchanged.
9. The pack completion fixture supplies the next worker tick after synthetic import. Production worker timing remains unchanged; a disabled fixture worker cannot settle immediately without that tick. The UI test also waits for Start acknowledgement before invoking the fixture worker.
10. Retain execution logs/ledger as review evidence. No commits, pushes or live activation are performed. Generated changes to older tracked screenshots are restored; only this feature's evidence is delivered.
11. The reviewer then reproduced two scope leaks in the final gap change: deferred work still used single-target selection, and current claims shrank later pack coverage before overlap checks. Both are fixed in the same grouped owner. The original coverage scope is preserved across queries/passes, submission still records Missing semantics, and current ownership is excluded/revalidated. Three red cases are in `final-scope-red.log`; 32 tests are green in `final-scope-green.log`, and new local ownership passes in `new-ownership-green.log`. The reviewer confirmed no unresolved important issue after these changes. The superseded per-episode continuation implementation is removed.

## Delivery boundary

The source files are delivered to `C:\Users\dante\Desktop\cinema paradiso` with a clean-baseline check before copying and byte-for-byte integrity verification. The isolated worktree remains available for review/recovery. No production catalog/config/task migration, restart, real download, commit, push, tag, package or release is part of this implementation.

The existing live process remains PID 8068 on port 5000. Production acquisition schema remains version 3; Louie's saved CP Compatibility task remains running. Configuration and served `dist/index.html` fingerprints are unchanged. The live `jobs.json` fingerprint changes while the existing app is running; it is an active recovery journal, not an immutable verification fixture. No test or delivery command writes it or issues a live add, so the report does not claim its bytes remain unchanged. Before/after fingerprints are retained separately.
