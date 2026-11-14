# IPTV bulk interpretation verification

**Status:** Implemented and verified in isolation, 2026-11-07; not activated in the running backend. Dante said "yes go" to pausing the live run and fixing final verification to use GPT's cleaned identity, with checks against competing films and conflicting evidence. No restart, resume, catalogue Apply, commit or release is included.

## Problem and decision

The advanced prompt is active (protocol `435ea3756a5d453cd5c3e3041385a856c194b5e732b867fc62f6a7f0f3c7c6ef`). Its cleaned titles are search hints only; its year is saved but not used in scoring. Live examples: Black Widow (2021) 3D scores 85.4; Good Luck Chuck (2008), actually 2007, and The Holiday (2007), actually 2006, score 90 against a 94 threshold. First 100 results: 66 unmatched, 29 rejected candidates, 5 uncertain GPT answers. Correcting the prompt alone did not correct verification.

Confirmed: Pause POST accepted with pause_requested=true; subsequent live reads report cancelled, with 182 results and 2 GPT requests saved. Only Pause was sent by this task; the cause of the later cancellation is not established. Do not overwrite or restart this saved job.

Scope is the interpreted bulk verification path. Preparation counters, redundant local searches, automatic Apply, replay of terminal results and UI layout are excluded. No unresolved product choice is needed for this repair.

## Contracts affected and contract-change decision

| Contract/source | Agreed behavior | Callers | Proposed behavior | Contract change? | Decision |
| --- | --- | --- | --- | --- | --- |
| Dante's advanced movie identification instructions | Clean prefixes/suffixes and multilingual titles; one year alone is not ambiguity | GPT bulk matching | Use cleaned evidence in final verification; tolerate one year when title is independently supported and no credible rival exists | Implements explicitly approved behavior | yes go, 2026-11-07 |
| Independent TMDB verification and identity conflicts | GPT does not assign IDs; competing films, sequels and larger year conflicts remain review | Bulk matching | Retain TMDB IDs/details and rival checks; require source support for interpreted name, preserve meaningful numbers | No weakening | Preserve |
| Legacy AI hint path and deterministic matcher | Search aliases do not independently justify fuzzy matches | Legacy F5, local matching, enrichment | Default parsed evidence and thresholds unchanged | No | Preserve |
| Locks, budget, checkpoints, Apply | Existing provider-local protection and explicit application | Bulk runner/store/API | Unchanged | No | Preserve |

Existing `test_hints_find_candidates_but_are_not_identity_evidence` and `test_model_search_aliases_do_not_corroborate_a_fuzzy_candidate` belong to legacy/general hint matching and remain unchanged. They are not authority to ignore the explicitly approved structured bulk interpretation. Unrelated model substitution must still fail in the new path.

## Current design and ownership

Checkout master/be511f9 with 381 existing dirty/untracked paths, preserved. Runtime PID 36876, checkout data/ai and data/iptv, frontend index-Cok6xiDI.js. IPTV is not mapped in the current knowledge index.

| Responsibility | Owner | Preserved behavior / retired mistake |
| --- | --- | --- |
| Parse, score, compare candidates | services/iptv_tmdb.py | Extend existing evidence/scorer with explicitly scoped interpreted evidence; keep deterministic defaults |
| Build verified bulk proposals | IPTVMovieService.bulk_source_proposal | Pass effective evidence through search and final decision; preserve locks/category gates/errors |
| Batch, budget, durable results | services/chatgpt_iptv.py, services/ai_jobs.py | No production changes |
| Visible results | ai_routes snapshot and IPTVBulkMetadataJob | Existing verified/review/unmatched payloads and pending Apply counts |

## Exact behavior contract

No frontend changes. Backend input remains the validated bulk interpretation (title, year, aliases, confidence, uncertain). Build effective title evidence in the existing TMDB owner, preserving original provider evidence alongside it. Search cleaned names first, retaining original variants within existing limits. Use the suggested release year only as bounded evidence: a candidate must be within one year of every available provider/model year; no chained two-year tolerance. An exact supported title with a one-year difference receives the same year contribution as an exact-year interpreted match. General/noninterpreted scoring is unchanged.

The model cannot substitute an unrelated movie: require the candidate's official/original/alternative name to relate to original provider evidence (exact, recognized leading film label/trailing 2D/3D cleanup, or near-identical spelling with the same token count). Arbitrary substring removal is prohibited. Delimited alternate titles must each have catalogue alias support; a leading collection label may be removed only when it identifies a TMDB-credited actor/director/character in the same candidate and the final title segment is supported. Keep meaningful numeric and Roman sequel tokens; format tags such as 3D are not sequel numbers. A translated title can be corroborated through TMDB alternative/localized names. Preserve source evidence separately for these checks. Competing plausible candidates remain review. Interpreted search must inspect the no-year phase even after an exact-year candidate is found, to expose nearby remakes; reaching the existing candidate cap forces review because rival discovery was incomplete. Existing query/hydration limits remain bounded.

Persist diagnostic interpretation evidence (original aliases/year, effective aliases/year and rejection reason where relevant) in each proposal. No schema migration. Existing terminal results are not rewritten; existing pending answers can use the repaired verifier after separately approved activation. No new GPT requests during tests; use synthetic transports and isolated temporary providers/stores. No lowering of global thresholds.

## Implementation sequence

1. Add failing real-service tests for the motivating titles and year tolerance, plus adverse competing films, unrelated substitutions, sequels, material year conflicts, uncertainty and manual locks.
2. Extend the authoritative evidence and scoring path; pass structured evidence from bulk_source_proposal. Retain one candidate selection implementation.
3. Verify full bulk runner -> stored proposal -> public job counts and existing Apply protection in isolation. Run relevant broader IPTV/cloud tests. Compare each contract above with observed results.

## Acceptance matrix

| Scenario | Expected result | Check |
| --- | --- | --- |
| Black Widow (2021) 3D -> Black Widow 2021 | Verified ID 497698 with TMDB evidence | Service and bulk runner |
| Good Luck Chuck 2008 -> 2007; Holiday 2007 -> 2006 | Verified unique candidate | Service |
| GPT preserves provider year; real release differs by one | Verified exact supported title | Service |
| Candidate two years from provider although one from GPT | Review, no candidate assigned | Service |
| Same title within nearby years | Review even if exact-year search alone finds one | Service/search |
| GPT substitutes unrelated same-year movie | Review | Service |
| GPT drops/changes sequel number, Roman numeral, title year-number | Review | Service |
| Cleanup of collection label or multilingual source supported by TMDB alias | Verified unique title | Service |
| Uncertain/low-confidence, manual match/classification lock, nonfilm | Existing behavior | Bulk suite |
| Legacy F5 hints and deterministic +/-1 behavior | Unchanged | Cloud and deterministic suites |
| Stored verified proposal/public counts and subsequent Apply | Existing payload/receipt contract | Real runner/store/route tests |

## Verification and rollout

Use CP_TEST_MODE=1, a unique OS-temp CP_TEST_ROOT, python -B -m unittest for focused and broader suites. Record red and green results. Backend only, so no frontend rebuild is required. No production Apply/restart/resume is authorized by this plan. Keep the stopped job and saved results intact. Any restart or rescan proposal must specify that already-terminal failures are not automatically reverified by Continue.

## Execution record

Implemented in `services/iptv_tmdb.py` and `IPTVMovieService.bulk_source_proposal`; legacy matcher/hint consumers are unchanged. New tests are in `tests/test_iptv_bulk_identity.py`. The first run failed on the motivating identities, bounded year support and full runner persistence; the initial implementation passed ten tests. Fresh review found that arbitrary substring cleanup could confuse After We Collided with After, and the candidate cap could bypass rival discovery. Both were reproduced as failing tests. A punctuated variant of the same subtitle issue was also reproduced and corrected by requiring catalogue support for split titles/collection labels. Final focused tests: 13/13 passed; final reviewer independently reproduced the original/dash/slash sequel and cap cases as ambiguous, with no edits.

Read-only replay against real TMDB on final source, using the stopped job's persisted search hints/suggested year (not a new GPT request): Good Luck Chuck -> verified ID 10030; Black Widow -> verified ID 497698; The Holiday -> verified ID 1581. All scored 100 under the bounded interpreted policy. No result was written to the live job or catalogue. This is verification of these three examples, not a guarantee for all 2,509 titles.

Additional read-only real-catalogue replay: In the Last Days of the City / اخر أيام المدينة -> ID 381722; أهل القمة -> ID 341525; Mickey's Delayed Date -> ID 67043. Home Defense initially remained review because TMDB combines multiple roles into `Donald Duck / Huey / Dewey / Louie (voice) (uncredited)`. Replacing the synthetic single-role fixture with the real combined-role format reproduced that failure. Character roles now split on `/` while actor names remain intact; a single-word credited character must match the complete label, not merely begin a longer unrelated label. Final focused regression and real replay both verify Home Defense as ID 62598. Seven real examples now verify in read-only checks; no live result/catalogue was changed.

Verification completed:

- Final source: `python -B -m unittest tests.test_iptv_bulk_identity tests.test_chatgpt_iptv tests.test_iptv_movie_enrichment tests.test_iptv_movie_gates_0_5 tests.test_ai_routes` -> **72 passed**, 86.338 seconds. Isolated root `C:/Users/dante/AppData/Local/Temp/cp-bulk-verifier-qualified-718d2b984c8a44e2a35fb0701cd85fab`.
- Earlier full bulk/broader run: `python -B -m unittest tests.test_iptv_bulk_identity tests.test_iptv_chatgpt_bulk tests.test_chatgpt_iptv tests.test_iptv_movie_enrichment tests.test_iptv_movie_gates_0_5` -> **78 passed**, 601.864 seconds, including all 19 bulk tests and the 40,000-proposal Apply and 25,001-title batch regressions. Isolated root `C:/Users/dante/AppData/Local/Temp/cp-bulk-verifier-suite-980ac57eae0f410cb2285b92aa1353fc`. This process loaded the initial implementation before review refinements; the final 72-test run above covers the refined verifier, real service/runner/persistence/public HTTP result counts, Apply identity, and legacy callers. Counts overlap and must not be summed.
- Fresh review independently confirmed all original/punctuated subtitle and candidate-cap reproductions are now ambiguous. Scoped `git diff --check` passed. No frontend changes or build required.
- Failures were the deliberate red tests described above (including the combined-role fixture); no final suite failures or skipped tests. Independent verifier defaults and legacy hint tests remain passing.

Production still reports cancelled, 182 saved results (118 unmatched/64 review), two requests, zero applied; backend PID 36876 remains unchanged. Only the approved Pause POST was issued. No restart/resume/Apply, commit, push or deployment was performed. The saved job is cancelled, so activation requires a backend restart and a new matching run; terminal old failures do not reverify themselves. No source behavior difference remains against this approved repair. Titles lacking sufficient catalogue support remain review; this repair does not promise a match for every provider entry.
