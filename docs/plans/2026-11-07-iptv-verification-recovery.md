# IPTV verification recovery and visible selection scope

**Status:** Approved for implementation by Dante's “ok go” following the investigation on 2026-11-07. Source fixes, isolated verification, and read-only replay first; activation and catalogue writes remain distinct actions.

## Problem and decision

- Latest Lionz job `7686c27d5cec44ba9710d1e47bc1ab04` selected 2,661 needs-review sources, applied 1,673, and left 985 review plus 3 failed. The 2,509 unmatched sources are disjoint.
- Advanced protocol hash matches. Of 985 review rows, 809 contain accepted GPT interpretations rejected downstream; 176 stopped at GPT uncertainty/confidence.
- Confirmed defects: incompatible candidates can outrank valid ones; harmless article/format differences fail corroboration; provider first-film numbering is treated as a sequel conflict. Candidate and error diagnostics are discarded.
- Scope: correct the existing bulk verifier, retain useful diagnostics, expose selected queue/provider beside Start and saved-job scope, replay saved interpretations without GPT or catalogue writes. No blanket relaxation of years, uncertainty, rival checks, or sequel protection. Targeted second GPT evaluation and production scans follow measured replay results; no new automatic inference loop in this patch.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and exceptions | Areas | Proposed behavior | Changes contract? | Decision |
| --- | --- | --- | --- | --- | --- |
| Dante's title/year policy | Interpret provider noise; allow at most one year difference; preserve meaningful sequel identity | Bulk TMDB verification | Prefer candidates satisfying original and interpreted identity; normalize articles/format symmetrically | No | Approved fix |
| Meaningful numbers | Never turn a sequel into another film | Bulk verifier | A trailing provider `1` can denote an unnumbered first film only with TMDB collection chronology proving it is the first; other numbers remain conflicts | No: corroborates first-film identity rather than dropping sequel evidence | Approved harmless-difference scope |
| Genuine rivals and uncertainty | Do not auto-confirm indistinguishable films or uncertain GPT output | Bulk service | Retain review and precise candidate diagnostics | No | Preserve |
| Selection and manual locks | Start uses the selected provider queue, existing Apply and locks remain | Metadata UI/store | Show queue and provider; no selection/data mutation | No | Preserve |

## Current design and ownership

| Responsibility | Owner | Callers / behavior to preserve |
| --- | --- | --- |
| Candidate search, hydration, scoring, independent identity | `services/iptv_tmdb.py` | Bulk and ordinary matching; new equivalence/ranking limited to bulk marker |
| Bulk outcomes and evidence | `services/iptv_movie_service.py` | `ChatGPTIPTVRunner`, Apply; keep locks/categories and outcome schema |
| TMDB batch memoization | `_CachingTMDBClient` | Reuse for collection evidence; no persistence needed |
| Selection state | `IPTVWorkspace.jsx` | Pass existing metadata status label to launch panel |
| Launch/progress | `IPTVBulkMetadataJob.jsx`, `AIJobStore` public snapshot | Existing CP layout; show current and saved selection separately |

Baseline: current checkout master at be511f9 with 383 pre-existing modified/untracked paths; preserve these. Production PID 51196 started 20:00:57, after verifier source 19:47:57, data under checkout/data; served index-Cok6xiDI.js. No existing failures asserted as current test evidence.

## Exact behavior contract

### Backend

Bulk candidate selection checks identity eligibility before ranking; incompatible candidates remain in diagnostics but do not veto an eligible winner. Only candidates with a definite original/interpretation year or meaningful-number contradiction are excluded from credible rivalry; lack of source-title corroboration alone must not erase a plausible fuzzy rival. Global search-cap exhaustion still prevents acceptance. Ordinary matching behavior remains unchanged.

Regional release dates may keep an otherwise year-incompatible rival plausible. They do not independently authorize acceptance or relax the primary-year acceptance rule. Rival scores and identity conflicts are retained in candidate diagnostics so review can explain this distinction.

Title corroboration compares symmetric removal of standalone English `the` and trailing 2D/3D; retains all other words. An added trailing `1` requires same remaining title and a collection response proving the candidate is the earliest released part (unique earliest date, all other parts dated). Hydrate collection only when needed, within existing candidate bounds; missing evidence leaves review. TMDB failures retain status/retryability and safe message; uncertain rows retain the original structured interpretation. Persist up to eight candidate summaries and query attempts in proposal evidence. No schema migration, automatic retries, or catalogue updates.

### Frontend

Reuse `iptv-bulk-launch-details` in the existing launch card. Show provider, queue, and selected-source count immediately above request size, beside the existing right-aligned Start button. Saved job displays its own snapshot queue, never the current selection. No mobile changes. Existing loading/empty/error guards stay intact.

## Implementation sequence

- [x] Add regression tests; observe failures for candidate ranking, article/format differences, collection-backed first-film numbering, diagnostics, queue display.
- [x] Correct authoritative verifier/service and snapshot/UI owners.
- [x] Replay all 809 saved interpretations against bounded TMDB candidates, compare old/new outcomes without applying; preserve report outside production data.
- [x] Run focused and broader backend suites, isolated desktop compiled UI, and final independent review.

## Acceptance matrix

| Scenario | Expected result | Verification |
| --- | --- | --- |
| Bruiser 2023, GPT 2022, candidates 2021/2022 | 2022 eligible candidate wins; 2021 remains diagnostic | Unit + replay |
| Dirty Harry Dead Pool / official Dirty Harry The Dead Pool | Verified with matching year and no rival | Unit + replay |
| Tunnel / Tunnel 3D | Symmetric format cleanup permits corroboration | Unit + replay |
| Toy Story 1 / Toy Story | Verify only with first-in-collection proof | Unit + replay |
| Toy Story 2 / Toy Story; After We Collided / After | Review | Existing/adverse tests |
| Sing 2016 and another Sing 2016 | Review with rival evidence | Unit + replay |
| Candidate cap or >1 year conflict | Review | Existing tests |
| Uncertain model, manual lock | No automatic match, preserve interpretation where available | Unit |
| TMDB error | Failed with status/retryable diagnostics | Unit |
| Switch selected queue, retain old job | Start card shows selected queue; old job shows saved queue | HTTP + desktop E2E |

## Verification and rollout

Use unique CP_TEST_ROOT with CP_TEST_MODE=1 for Python and fixture browser tests. Build to an isolated output directory, point fixture CP to that bundle; do not overwrite live dist. Read-only replay opens SQLite mode=ro and calls TMDB GET only, caching responses outside production data. Report recoveries separately from confirmed correct identities; inspect recovered examples. No restart, production Apply, new GPT requests, commit, or push in this implementation gate.

## Execution ledger

- Planning: user-approved direction translated to existing owners; no new AI loop or year-policy relaxation.
- RED: five new backend tests failed on the observed defects; scope HTTP test failed on missing selection_scope. GREEN: 18 identity tests and 77 related backend tests passed before the final review correction.
- Independent review found missing first-film collection proof was being treated as a definite contradiction for rival exclusion. Added adverse test, observed failure, then retained such candidates as rivals; all 19 identity tests passed. Reviewer rechecked both fixes and found no remaining blocker.
- Replay fidelity review found one saved row had an additional search hint; replay now appends saved hints in production order. The ongoing first replay uses earlier loaded code; final replay must use cached responses with final code before reporting totals.
- Compiled isolated desktop: 6/6 tests passed, screenshot inspected at OS temp/cinema-paradiso-playwright-d9ff004711a3443ca5afd354b021021c/bulk-ready.png. Start displays provider and selected queue; saved job displays independent scope. Build index-CwT5nqbq.js. Live dist untouched.
- Read-only replay exposed The Neighbor: primary date 2020 but official festival/region dates 2017/2018. Such a candidate must remain a rival to the 2017 Spanish namesake. Added failing regression, then score alternative release dates for rivalry only. Acceptance still uses existing year checks. Independent reviewer confirmed both rivalry and lone-candidate rejection; 20 identity tests passed.
- Final related backend suite: 79 passed in 65.716s (CP_TEST_ROOT cp-recovery-final-58b30f84794141349c4509b527544d46). Broader 97-test suite including all 19 bulk lifecycle tests passed in 595.559s; that process loaded the verifier before the regional-rival refinement, which is covered by the final 79-test suite. Do not conflate those as one final 97-test run.
- Added explicit different-queue desktop assertion. Initial fixture interception updated only the latest-job response and was overwritten by the follow-up status response, so the test failed. Corrected the fixture interception for both responses; targeted desktop test passed in 6.9s, screenshot in cp-playwright temp root cinema-paradiso-playwright-7702cec1d37f4e0d946f990df68d0e66. No product change required.
- Further investigation: cached detail_json includes precise provider duration for Sing (107m53s), Seire (101m34s), Watching (97m55s). This may help distinguish feature/short-film rivals. It is not currently used as automatic acceptance evidence; any next-stage rule must account for inaccurate provider metadata and unknown rival runtimes.
- Completed initial 809-row lookup pass: 6,287 TMDB GET requests, 1,579 seconds. This populated only an isolated response cache and is not the final acceptance result.
- Final replay with verifier SHA256 `509a36d8171999647a38259085f38d433376b3a7a4f71d86801aead9c75c069b`: 809 rows, 18 matched-auto (17 distinct TMDB IDs), 791 ambiguous; 25 seconds using cached responses plus two missing search-hint GETs. Zero GPT requests, zero catalogue writes. Results: `C:/Users/dante/AppData/Local/Temp/cp-iptv-recovery-20261107/results.jsonl` and summary.json.
- Final unresolved reasons: 374 year conflicts, 201 competing identities, 143 unsupported provider titles, 57 below-threshold evidence, 13 number conflicts, 3 candidate-cap limits. Separate original 176 uncertain GPT rows are not part of the 809 replay.
- Three original failed sources were retried through deterministic TMDB checks without GPT: no transport errors reproduced, but all still require interpretation/identity resolution. Historical errors cannot be reconstructed because old code discarded them.
- Live final checks: PID 51196 unchanged, production latest job still completed with 27 GPT requests; catalogue queues remain 2,509 unmatched and 988 needs-review. No source activation, production Apply, new GPT scan, commit, or push performed.
