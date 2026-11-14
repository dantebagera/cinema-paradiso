# Movie and TV database adoption plan

**Status:** Draft, 2026-10-18, Africa/Cairo. Dante authorized this planning document only: "prepare a plan for Movie and TV only, leave IPTV unchanged" and "dont implement anything yet". No application/test/tool implementation, test execution, benchmark, production data access, activation, restart, commit, push or release is authorized by this document.

**Goal:** Prepare independently reviewable Movie and native-TV improvements, preserve the current IPTV implementation, and establish the evidence needed before considering activation.

**Architecture:** Extract the reviewed Movie and TV changes into an isolated snapshot of the current agreed source baseline. Keep the current SQLite stores, schemas, writer durability settings and frontend design. Verify Movie alone, then Movie plus TV; neither stage inherits acceptance from the earlier all-domain candidate.

**Tech stack:** Existing Python/SQLite, unittest, Node, Vite and desktop Playwright; no dependency upgrades.

**Execution:** Only after separate approval, use `superpowers:executing-plans` for sequential work. No delegation, commits or live actions are implicit. This plan follows `docs/plans/_template.md`; CP rules and Dante's scope override generic skill defaults.

**Spec and evidence:** `AGENTS.md`; `docs/tv-contracts.md`; `docs/plans/2026-10-15-database-browse-performance-zero-regression-plan.md`; candidate `docs/verification/database-browse-performance/{report.md,contract-results.md}`; preserved `acceptance-status.json` and domain writer reviews. Latest enriched-IPTV-only write evidence is `C:\Users\dante\Documents\Codex\database-write-recheck-2026-10-18-cd8e65fdb9344f80b016331b328615a0\comparison-complete-report.md`. It is context for excluding IPTV, not Movie/TV timing evidence.

## Problem and decision

- **What happens now:** The isolated all-domain candidate has verified Movie/TV browsing gains, but it also contains unaccepted IPTV changes. Copying that candidate wholesale would violate this request. Its tests do not prove that an extracted Movie/TV-only combination works against today's complete source and desktop.
- **What Dante wants:** Retain the Movie and TV opportunities, leave raw and enriched IPTV unchanged, explain and satisfy the remaining checks before a separate activation decision.
- **Confirmed:** Earlier TV comparisons improved all 74 tested median/P95 results, with typical database request durations about 7–10 times lower. Three large Movie saved-list pages improved from about 66 seconds to 0.22 seconds. These are historical synthetic, warm-cache results, not current live guarantees.
- **Confirmed write limits:** Historical large-fixture active-reader P95 whole-write durations were Movie 311.39 -> 651.32 ms and TV 767.36 -> 1685.87 ms, despite improved medians. Follow-up diagnostics reproduced long Windows disk-flush waits in both versions without finding extra lock/flush-count/write-volume work. They do not explain every earlier individual pause or prove universal non-regression. The saved all-domain status lists those mechanism investigations as complete, while retaining these observations.
- **Unknown:** Exact current live source/data/bundle ownership; behavior of the extracted stages; their current write distributions. The original executable Temp baseline is incomplete, although 85 exact original source files were recovered. Do not run controls against that incomplete environment.
- **Scope:** Movie library/query/projection and native TV browse/read-model changes only, plus their isolated verification infrastructure. No schema/index migration, new persistent cache, new background work, weaker durability, maintenance, download/transfer behavior, source-policy change, UI redesign or mobile work.
- **Open decisions:** Implementation remains unapproved. The deployment destination must be resolved before promotion because the running launcher belongs to a different folder. No slowdown tolerance or waiver is approved. If evidence cannot clear a slowdown, hold the affected stage and return the evidence to Dante; do not invent a permitted percentage or silently relax the contract.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes contract? | Dante's decision |
| --- | --- | --- | --- | --- | --- |
| Exact Movie results; existing Library/API and canonical contracts | Same identities, totals, duplicates, sorting/ties, selection, selected provider, per-field overrides, posters/assets and eligibility | Library, Lists, owned-movie consumers, details, advanced person/keyword lookup | Same result with less repeated work | No intended change | Planning only |
| Movie freshness and snapshot contract | Page, count, projected fields and reported generation describe one committed snapshot; the next request sees committed changes | Legacy/advanced pages, full selection, facets/stats | Capture and return the generation of that read, preserving response fields | No intended weakening | Planning only; conflicts block execution |
| TV coverage and playback; coverage tests and TV contracts | Preserve Specials/release/date policy, completeness, file versions, missing/available counts, progress, cursor ties, lists and Continue Watching | TV library/detail/files/options/identities/Lists/Home | Collect request facts once; retain existing policy owners | No intended change | Planning only |
| TV physical availability | Current surface-specific handling of unavailable files remains; no availability survives across requests | Browse, details, Lists, Continue Watching | Check each relevant unique path at most once per request, after closing the DB snapshot | No intended change | Planning only |
| IPTV exclusion; Dante's explicit instruction | Current raw and enriched IPTV source, routes, provider ownership, readiness, schedules and data remain | IPTV screens/API and shared consumers | Baseline IPTV unchanged in every stage | No | Explicit scope requirement |
| Write correctness, durability and failure truthfulness | Successful writes read back; rollback/errors remain truthful; no unexplained reproducible slowdown accepted | Movie/TV writers overlapping reads | Existing writes/settings retained and checked | No | No slowdown waiver |

No contract amendment is proposed. If extraction reveals a conflicting agreed rule, stop that portion and issue the separate contract-change notice required by AGENTS.md before coding it. Existing output alone is not an oracle for a disputed rule. Tests must assert the agreed result, not encode a convenient new expectation.

## Current design and ownership

### Baseline recorded during this planning pass

| Location | Observed state | Meaning |
| --- | --- | --- |
| `C:\Users\dante\Desktop\cinema paradiso` | `master`, HEAD `be511f98846a67a182e5b371ad087938e9344362`; 80 tracked changes and 79 untracked status entries before this plan | Dirty working source is the planning reference, not clean HEAD. Preserve unrelated work. |
| `C:\Users\dante\.codex\worktrees\database-browse-performance\cinema paradiso` | Detached at the same HEAD; 741 tracked changes and 75 untracked entries | Counts include unrelated snapshot/line-ending differences. Do not merge, cherry-pick indiscriminately or copy the whole tree. |
| `C:\Users\dante\Desktop\cinema paradiso - Copy` | No Git identity returned; launcher Python executable is inside this folder | Treat as an independently managed runtime candidate, not a clean checkout or approved destination. |
| Running processes | Launcher PID 10920, backend PID 48556, both started 2026-10-17 15:24:36 Cairo | Process metadata only was read. No app request, DB connection or restart was performed. Relative `app.py` arguments do not prove the full loaded source or data root. |
| Desktop checkout `dist/index.html` | SHA256 `4c0af16926b677a8d71121b402599b44b5f463c0b44bf8ddd7dfa83e8e5f5bef` | Local file only; not evidence of the bundle served by the running app. |
| Copy folder `dist/index.html` | SHA256 `d9d51b9174ae48cf421979d2ebb6c0e16de147e1d716ffc873038a1084ceaba9` | It differs from the planning checkout. Served identity remains unverified. |

The seven proposed application files currently match the recovered original source byte for byte in the Desktop checkout. Both excluded IPTV store files also match those originals. Refresh the full source/dependency inventory at execution time; these observations are not permission to overwrite later edits.

Movie database location is owned by `catalog_repository.catalog_database_path(user_data_dir, local_app_data=None)`: portable mode uses the user-data root; normal mode uses an AppData path derived from that root. Native TV uses `TVCatalogStore` and its configured data root. Do not assume an old AppData filename or Desktop `data` folder is what the Copy process uses. Resolve configuration without importing app constructors or opening production stores. If the active owner cannot be established safely, activation stays blocked.

### Application allowlist and execution paths

| Responsibility | Authoritative files and interfaces | Entry points/callers | Preserve / retire |
| --- | --- | --- | --- |
| Movie effective metadata and bounded projection | `services/canonical_catalog.py`: `CanonicalCatalog.project_paths(connection, path_keys, *, include_details=False, include_overrides=True)` and shared eligibility/snapshot/override helpers | Catalog store -> repository -> cards/details/owned-movie callers | Selected-provider choice, latest nonempty per-field overrides, stored aliases, asset precedence. Replace the duplicated query/projection interpretation with the reviewed shared owner. |
| Movie page/filter/selection preparation | `services/catalog_store.py`: `library_page(filters=None, *, query=None, page=1, page_size=40, upgrade_path_keys=())`; `_library_selection_snapshot(...)` | Legacy and advanced Library, saved lists, people/keywords, full selection | Exact ordering/counts/clamping; bounded custom-metadata page preparation; coherent read transaction. Preserve existing generation-based summary semantics, with locking against older snapshots replacing newer summaries. Add no TTL/result cache. |
| Movie repository/API generation handoff | `services/catalog_repository.py`: page/selection delegation and `library_people_identities(query='', *, limit=20)`; Movie-only hunks in `app.py` | `/api/library`, `/api/library/search/advanced`, `/api/library/search/identities`, `/api/library/selection` | Pass existing upgrade-path facts once; use the captured media generation in responses. Retire the post-read generation lookup in the reviewed Movie paths. All non-Movie app.py code remains baseline. |
| TV request facts/projections | `services/tv_catalog_repository.py`: `_TVBrowseFacts`, `_browse_facts(...)`, series/episode projection helpers | TV repository -> read model/search | One bounded DB snapshot, closed before filesystem checks; independent mutable file/episode results; existing legacy cursor tie resolution. Replace repeated request preparation, not writer behavior. |
| TV policy and public reads | `services/tv_read_model.py`: `coverage`, `detail`, `tv_lists`, `continue_watching`; `services/tv_search.py`: `local_rows`, `library`, `options`, `identities` | `services/tv_routes.py` -> TV Library/detail/Lists/Home and shared consumers | Coverage remains in `TVReadModel.coverage`; reuse request facts across local rows and selected details. Preserve missing-data/errors and current schedules. No route or acquisition rewrite. |

Only these seven application files may change relative to the execution baseline. Movie consists of the first four files (including app.py); TV consists of the last three. No change to `services/iptv_store.py`, `services/iptv_movie_store.py`, any IPTV service/route/frontend, or unrelated source/configuration is allowed. Shared callers still need regression checks: a file allowlist alone cannot prove IPTV behavior unchanged.

### Verification-only files

- Create `tests/test_movie_tv_browse_adoption.py` by extracting the applicable `MovieSnapshotTests`, `MovieInterpretationTests` and `TVRequestFactsTests` from the candidate's `tests/test_database_browse_contracts.py`. Preserve their independent oracles and adverse assertions. Do not import candidate-only Raw/Enriched tests whose implementation is excluded. Add missing complete-path or stage-interaction coverage here, rather than duplicate business logic.
- Reuse/adapt `tests/database_browse_fixtures.py` and `tools/catalog_read_performance.py` only for guarded disposable fixtures. Do not introduce a second production resolver or writer.
- Reuse the candidate's fail-closed `tests/e2e_isolation.py` and necessary isolation hunks in `tools/run_playwright_e2e.ps1`, including embedded-only fake transfer transport and cohort-only DB access. Preserve current launcher behavior outside tests.
- Create `tests/e2e/movie-tv-browse-adoption.spec.js` using the Movie/TV user-visible assertions from the candidate combined desktop test. IPTV navigation may be a preservation check, but candidate IPTV optimizations/assertions are excluded.
- If a bounded writer adapter is needed, create `tools/movie_tv_write_comparison.py` from the saved writer control. It may call existing owner connection/read/write operations only; its exact safety/measurement interface is specified below. This is verification infrastructure, not a production write implementation.
- Store future manifests/reports under `docs/verification/movie-tv-database-adoption/`; no acceptance flag in the historical all-domain work is to be rewritten.

## Exact behavior contract

### Frontend

No JSX/CSS/product bundle change is proposed. Reuse the current `LibraryWorkspace`, `MovieListsWorkspace`, `TVWorkspace`, `MediaWorkspace`, `TVListsWorkspace`, `HomeWorkspace` and existing shared cards. Preserve grids, controls, loading/empty/error states, selection, expanded-card geometry, filter state and Back/Forward behavior. Verify desktop only against the baseline build, including repeated navigation. The runtime UI in Copy is not assumed to equal this checkout's UI.

### Backend

- Preserve existing request validation, normalized advanced-query inputs, filter-before-pagination behavior, all eleven Movie sorts and their tie breakers, limits and full-selection semantics. Public response field names/types remain; `_media_generation` is an internal handoff and must not leak into JSON.
- Movie count, page, projected fields, facets/stats and reported generation must describe one committed read state. A concurrent edit may produce a coherent before or after result, never a mixed response. A subsequent request sees the committed edit. Public selection count equals its exact returned paths and captured generation.
- TV request facts include the existing series, episodes, bindings, progress/cursors, hydration/review, curation and relevant lists. Snapshot scope and response completeness follow the reviewed owner methods; full episode APIs retain fields omitted from summaries. Day rollover and subsequent file removal are visible on the next request.
- No writer SQL, schema/index/version, busy timeout, journal/synchronous setting, retry policy, background schedule, migration or initialization policy changes. Keep the actual per-owner settings; do not make writes appear faster by reducing durability.
- Propagate validation/not-found/DB errors through existing handlers; close snapshots on success, interruption and exceptions. No new stale response fallback or swallowed error.
- Example: filtering Movie year and opening a returned card must use the same effective year; a TV file removed after request A must be unavailable in request B even if the database did not change.

## Implementation sequence — future work, not authorized now

### Stage 0: Freeze and separate the source

- [ ] Refresh paths, Git state, source/dependency hashes and runtime-owner uncertainty. Record baseline failures without changing their assertions. Do not import the live app to discover its settings.
- [ ] After source-work approval, create isolated baseline B0 from the agreed current dirty source, including required untracked source. A clean worktree from HEAD alone loses existing work and is not B0. Exclude production data/config/credentials/media; build synthetic fixtures instead.
- [ ] Create B1 = B0 plus only Movie owner changes, then B2 = B1 plus only TV changes. Review the original-to-candidate semantic diff, preserve unrelated edits, and stop if dependency changes exceed the allowlist.
- [ ] Record complete stage manifests. Check both IPTV stores, all IPTV product files, frontend and configuration against B0, plus AST/semantic review of all non-Movie app.py code. Every difference must be explained and within scope.
- [ ] Validate isolation before tests: unique OS-temp root, fake transports, nonproduction ports, no external network/player/torrent helpers or production DB reads/writes. Never use the incomplete original Temp executable baseline.

**Deliverable:** Reviewable B0/B1/B2 manifests and exact Movie-only / TV-only diffs. No production promotion.

### Stage 1: Verify Movie independently

- [ ] Extract the reviewed four-file Movie change and its tests into B1. Preserve canonical rules and later current-checkout behavior. Exercise B0 and B1 with the same fixtures/oracles; distinguish existing failures from introduced failures.
- [ ] Run Movie snapshot/interpretation/API tests, existing catalog/writer-lease/event/cold-start tests and applicable shared Movie suites. Verify filtering -> API payload -> compiled card/detail results, including overrides and generation handoff.
- [ ] Assess historical read/write evidence against the exact extracted source/dependency hashes. Reuse matching evidence; do not rerun completed trials merely to get a favorable result. Run only the justified new integration/timing checks described below.
- [ ] Record Movie readiness separately. Any unexplained mismatch, side effect or reproducible slowdown holds B1; do not automatically alter SQL/settings to chase a timing result.

### Stage 2: Verify TV on top, retaining Movie-only results

- [ ] Extract the three-file TV change into B2, including repository facts, coverage/detail/list/Continue Watching consumers and search reuse.
- [ ] Run TV facts/coverage/progress/list/search tests, including physical-file changes and day rollover. Compare complete responses with B0 and independent oracles.
- [ ] Check both B1 -> B2 Movie preservation and B0 -> B2 TV changes. Verify shared Home/Lists and acquisition-facing reads using fakes; do not change acquisition rules or exercise real transfers.
- [ ] Record TV readiness independently. If TV blocks, retain B1 as the Movie-only candidate; do not add a feature flag or parallel runtime fallback. If Movie blocks, a TV-only variant needs its own reviewed source manifest/tests before adoption; B2 cannot stand in for it.

### Stage 3: Complete the combined acceptance package

- [ ] Run the bounded verification matrix below on the exact B2 build; perform broader tests once for the final unchanged combination. Preserve all failures/skips and their source hashes.
- [ ] Produce a separate Movie decision, TV decision, IPTV-preservation result and proposed activation/rollback procedure. No activation follows automatically, even if every isolated check passes.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Required evidence |
| --- | --- | --- | --- | --- |
| Movie populated/current and large fixture | Page/filter/sort/select all | Same eligible identities, order/ties, totals, selected paths and card fields; no skipped/duplicate items | Store -> repository -> API -> Library | Existing interpretation tests and compiled desktop assertions |
| Conflicting provider snapshots and partial custom overrides | Filter title/year and open details; use people/keyword/list filters | Displayed value is the value used to filter; current precedence and independent oracle agree | Canonical/catalog/API | Candidate adversarial tests extracted without weakening assertions |
| Concurrent Movie commit/rollback, older read finishing last | Read page/selection/facets while a writer runs | Coherent before/after response and generation; new summary cannot be replaced by old; next request sees commit | Movie snapshot owner | Twenty scheduled interleavings and full-response/API generation assertions |
| Movie empty, missing metadata, huge/out-of-range page, invalid query | Browse/select/error | Current clamping, empty structures and validation/error result preserved; no stale-success fallback | Library and advanced routes | Existing bounds/error tests plus B0/B1 comparison |
| TV regular/Special/future/unknown-date episodes, incomplete hydration | Browse/filter/detail | Existing coverage, watched/missing counts and completeness decisions unchanged | TV facts/coverage/search | Coverage and request-facts tests with independent expectations |
| TV multi-version/multi-episode files and equal progress timestamps | Read episodes/detail/resume | Complete fields, independent mutable values, existing segment/progress/cursor ties and next episode | Repository/read model | Existing TV tests plus full response comparison |
| TV file removed between requests; Cairo day boundary | Repeat identical browse/detail | Next request reflects disappearance/release; DB closed before stat calls; no cross-request facts cache | TV browse/detail/Lists/Continue Watching | Unique-file check and day-rollover tests |
| Playback/curation/list changes overlap read | Read TV lists/Home and Movie shared cards | Correct coherent facts, next-request refresh and no Movie/IPTV identity leakage | Shared surfaces | Fact interleavings, Home/Lists API and desktop tests |
| Query interruption / DB error / lookup not found | Interrupt or raise inside disposable owner | Existing truthful error; all transactions/connections released; later valid request succeeds | Both domains | Fault-injection and fresh-request checks |
| IPTV preservation | Compare B0/B1/B2 hashes and synthetic raw/enriched APIs/screens | IPTV product source/settings unchanged; same normalized responses, identities, order/counts, provider isolation and readiness errors | Unchanged IPTV plus shared callers | Existing baseline-compatible IPTV tests and desktop checks; no IPTV benchmark |
| Busy writer with actual active reader | Run bounded write control in each selected stage | Correct token readback, rollback behavior, native READ proof, unchanged settings; no unresolved reproducible latency regression | Movie/TV only | Full raw distributions/components and finite diagnostics, not averages alone |
| Desktop repeat navigation | Filter/page/select/open/close; navigate Lists/TV/Home and Back/Forward | API and rendered identities agree; current selection/filter/scroll behavior remains | Existing compiled desktop | New scoped spec plus current relevant specs; zero required skips |
| Boundary safety | Attempt outside-fixture DB/socket/helper action | Guard rejects it before real access; normal synthetic tests still pass | Test launcher/fixtures | Isolation tests and owned process/port proof |

## Verification and rollout

### Gate A — source scope and isolation

Required before running application tests: B0/B1/B2 source manifests, explicit dependencies, allowlist review, no unintended IPTV/frontend/config differences, and working negative isolation checks. Current harness may not be replaced wholesale with a historical version that loses later changes. The candidate launcher defaults to embedded mode and rejects system mode; carry that protection into the isolated stages.

Run future commands only from an approved isolated stage, with its existing Python environment; stop if missing dependencies require an unapproved installation. Example setup, not executed during planning:

```powershell
$planPython = (Resolve-Path '.venv\Scripts\python.exe').Path
$env:CP_TEST_MODE = '1'
$env:CP_TEST_ROOT = Join-Path ([IO.Path]::GetTempPath()) ('cp-movie-tv-' + [guid]::NewGuid().ToString('N'))
$env:CP_TEST_QBT_MODE = 'embedded'
$env:PYTHONDONTWRITEBYTECODE = '1'
```

No live database copying, constructors against production paths, port 5000 requests, real media operations or provider calls in these gates.

### Gate B — exact results and current integration

Commands after the named verification files are prepared:

```powershell
& $planPython -B -m unittest tests.test_movie_tv_browse_adoption -v
& $planPython -B -m unittest tests.test_catalog_store tests.test_catalog_repository tests.test_catalog_writer_lease tests.test_catalog_events tests.test_catalog_cold_start -v
& $planPython -B -m unittest tests.test_tv_catalog tests.test_tv_coverage_contract tests.test_tv_stabilization tests.test_tv_list_filters tests.test_tv_bulk_actions -v
& $planPython -B -m unittest discover -s tests -p 'test_*.py' -v
$nodeTestFiles = @(rg --files tests -g '*.test.mjs')
node --test @nodeTestFiles
```

All applicable tests must pass. Record genuine baseline failures separately; an introduced failure blocks the affected stage. Do not import the full candidate test suite with optimization-specific IPTV expectations. Existing baseline IPTV regression tests remain required. Historical 1,815 Python / 133 Node / desktop results are evidence only, not fresh results for this combination.

### Gate C — reads and writes, with a finite budget

1. First review matching saved Movie/TV evidence; preserve original distributions and hashes. Never repeat the completed enriched-IPTV 200-trial comparison, start an IPTV benchmark, or restart the old all-domain queue.
2. Additional performance work requires explicit approval of the finite session. Preserve the previous constraints: one measurement worker at a time, no CPU pinning, and a hard ten-minute total measurement deadline, including fixture preparation. The parent supervisor must stop only its owned worker. Incomplete coverage remains incomplete; do not extend or launch another session automatically.
3. Prioritize the unresolved large-fixture active-reader writer concern: Movie first, then TV. Use 50 original/B0 and 50 selected-stage writes per phase, alternating five blocks of ten per version, with idle and active-reader phases recorded separately. Native reader READ state must be established before the unchanged one-second writer delay. Use independent but equivalent synthetic fixtures and record preparation/cache limitations; no live DB copy. Review the complete comparison schedule against the deadline before starting; do not promise it will fit.
4. The writer adapter interface is `--domain movies|tv --baseline-source <B0> --candidate-source <B1-or-B2> --fixture-root <unique-temp-root> --output <new-json-path> --deadline-epoch <shared-deadline>`. It must reject expired deadlines, restricted inherited CPU masks, non-temp fixture roots, other databases, external network/processes, duplicate trial keys and changed source hashes. The supervisor enforces the same deadline outside the worker. Settings come from the actual owner connection; no PRAGMA override. Preserve every completed observation and never rerun its key after a stop.
5. Each write records connection/lock/update/COMMIT/close/whole duration, committed-token readback, source/settings/affinity and native reader state. Reader responses must match independent expected membership/order/counts and baseline values. Report median/P95/max separately; use the historical discrete P95 convention `sorted(values)[round((n-1)*0.95)]` consistently. Do not pool idle/reader, current/growth, versions, sessions or instrumented diagnostics.
6. Existing `tools/catalog_read_performance.py` is the read owner. If new read evidence is necessary, add only named cases justified by extraction/dependency drift to the approved schedule, using `--domain movies` or `--domain tv`, `--fixture-root`, `--scale current|growth`, `--case <exact fixture case>`, `--samples 50` and `--output <new file>`. Never use `--domain all`, `--base-url` or `--cpu`. Full historical matrices need not be rerun when source/dependency equivalence is established. Never treat a one-sided CLI timing as a matched comparison.
7. Gate passes only with correct results, complete required evidence and no unexplained reproducible slowdown. A slow tail is not dismissed because the typical write improves, because a null control is noisy, or because a Windows flush wait occurred in another observation. If the deadline prevents resolution, stop and report the exact gap. Any new diagnosis or tolerance requires a separate decision; no rerun-until-green.

### Gate D — compiled desktop and unchanged IPTV

Build only to the isolated cohort's dist. Use the guarded launcher and one Playwright worker. With the fixture flags restored to their prior values after each command:

```powershell
$env:CP_TV_E2E = '1'
$env:CP_DATABASE_BROWSE_E2E = '1'
npm.cmd run test:e2e -- --workers=1 tests/e2e/movie-tv-browse-adoption.spec.js
npm.cmd run test:e2e -- --workers=1 tests/e2e/native-tv.spec.js tests/e2e/tv-parity.spec.js tests/e2e/tv-expanded-parity.spec.js tests/e2e/tv-stabilization.spec.js tests/e2e/continue-watching.spec.js
```

The guarded wrapper performs `npm.cmd run build -- --outDir <cohort-dist>` and fixture startup. Confirm the flags actually seed the combined Movie/TV data, the selected server runs through `tests.e2e_isolation`, and zero required tests are skipped. Run baseline-compatible IPTV preservation cases in that same synthetic environment; no live IPTV request. Check API payloads and rendered cards, not screenshots alone. Any browser/environment failure remains recorded; a repaired retry is reported separately.

### Gate E — activation preparation, still without activation

- Establish the exact intended deployment folder and current runtime ownership: process/working source, configuration and user-data root, actual Movie/TV DB paths, served index/assets and source version. The Copy launcher is a concrete mismatch to resolve, not proof that editing Desktop affects the running app. If safe inspection cannot settle the destination, ask Dante before promotion.
- Present exact application-file diffs, test counts/failures/skips, source hashes, speed/write distributions and remaining uncertainties for Movie and TV separately. State explicitly whether each passes or is held. Recheck IPTV/front-end/config preservation after all work.
- Prepare a recoverable source/config inventory for the chosen destination. No schema migration means rollback should restore the previous code without rewinding newly written user data. Any database backup must be separately authorized and transaction-consistent; never copy a live main SQLite file while ignoring WAL state.
- Specify an activation procedure that touches only the selected source files and the necessary backend restart. Do not run `run.bat` casually: it installs dependencies, rebuilds the frontend and stops a backend. No dependency installation, unrelated bundle replacement or automated background job follows from this backend-only plan.
- Give Dante the concrete activation and rollback actions for approval. Restart, deployment, production backup/data actions, live smoke checks, commits and publication remain separate permissions.

### Gate F — live checks, only after separate approval

After approved activation, verify the intended process/config/data/bundle ownership, compare the same Movie/TV browse paths and desktop interactions, and confirm unchanged IPTV behavior. Live saves/edits/playback/scan/download actions require their applicable explicit authorization; do not perform a production write merely to create verification evidence. Roll back code on a new mismatch, regression, forbidden side effect or wrong runtime target. Do not revert catalogs or user progress as an automatic code rollback.

### Reporting and final contract comparison

Use separate labels: **planned**, **source prepared**, **isolated tests passed**, **performance unresolved/passed**, **activation approved**, **live verified**. No stage advances by inference. Compare every acceptance row with the observed result, retain historical adverse evidence, and identify the precise impact of any remaining difference. A passing suite does not authorize a contract change or live activation.

## Review focus / plan self-review

- Current dirty work and the Copy runtime can diverge: Stage 0 and Gate E prevent a source-only success from being presented as a live change.
- A Movie canonical helper has non-Library callers: Movie tests and IPTV synthetic preservation compare their actual public results.
- A read can be correct while its version label is wrong: Movie snapshot/API tests assert both data and generation.
- TV files, dates and progress can change without a new browse input: unique-path, day-rollover and interleaving cases prove next-request freshness.
- Windows flush waits can hide unresolved writer cost: Gate C retains all tails and blocks an unexplained reproducible slowdown rather than accepting an improved median.

All required CP template sections are covered. Movie and TV remain separately reviewable deliverables; IPTV implementation and activation are excluded. Only this draft document has been created during planning.
