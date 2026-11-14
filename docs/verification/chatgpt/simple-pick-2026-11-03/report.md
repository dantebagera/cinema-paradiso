# Pick My Movie simple flow: implementation and actual timing

2026-11-03. Source implemented and tested in isolation. The production app was not restarted.

## Exact request and environment

```text
i need you to lit 50 movies with very twisted story you wont expect the ending
your responce should be a list of movies names and years , no any other details , dont seek more info , dont reply by paragarph or any way of responce  only the list
```

Explicit target:50. Selected model:`gpt-6.1-sol`; existing selected CP OAuth account, provider defaults (no reasoning override). A fresh process/cache and empty isolated session/store used the actual Recommender, CP identity ranker, AICatalog, protected credential owner and public GPT/TMDB HTTP. This is a complete backend-ready workflow; startup/import and browser paint are excluded. No concurrent test/build workload was running during this final capture. No production catalogue/configuration change, proposal Apply, commit or release.

## Final captured result

**50 verified distinct movie cards; completed; two GPT requests; 135 TMDB HTTP reads; 38.658624 seconds total.**

| Stage | Seconds |
|---|---:|
| Initial GPT response:50 title/year candidates |19.426721|
| Replacement GPT response:two candidates |4.984133|
| **Total GPT stage** |**24.410854**|
| **TMDB matching, eligibility and card persistence** |**13.435064**|
| Other CP setup/scope/state handling |0.812706|
| **Full workflow** |**38.658624**|

The GPT-stage clock includes request-slot/account access and complete HTTP response reading/validation. Pure HTTP durations were 19.394112s and 4.952798s (24.346910s total). These are network request times, not server compute-only time. Matching is wall time across four workers, not the sum of overlapping requests. First saved/backend-ready card:20.543193s. Initial matching accepted48; two suggestions failed the existing provider eligibility checks, so one genuine replacement request supplied the missing two. No separate setup/planning GPT call, candidate-submission call or explanation call occurred.

Raw final trace:[final-timings.jsonl](final-timings.jsonl). All50 cards, request, counts and boundaries:[final-summary.json](final-summary.json). The original source hash in that summary matches the final recommender. More detailed source bindings:[source-hashes.json](source-hashes.json).

## Earlier trial, retained

First real trial completed50 cards in47.585904s with three GPT requests (initial50, replacements3, replacement1),146 TMDB reads. GPT stage31.347720s; HTTP22.158206s; matching15.299395s; other0.938789s. Its matching generator span excluded the last pending save, so that save is included in its other category. That boundary was corrected for the final run. Non-HTTP work inside its GPT stages accounted for9.189514s, including2.928399s account access and one5.352390s slot release; no hardware cause is asserted. This is observed variability, not a controlled model-speed benchmark. See trial-1 files. An earlier harness launch using system Python failed before inference because jwt was missing; CP's .venv interpreter ran both actual captures. Total real GPT usage for this task:five HTTP attempts, no retries or structural repairs.

## Implementation

- One authoritative F1 pipeline parses ordinary JSON output locally. Candidate entries contain title/year only; generated per-movie reasons and F1 cp_result.submit are retired.
- Initial response declares requirements in the same response; local schema validation, existing query normalization and controlled identity validation remain. Replacements receive the fixed scope and cannot redeclare it. Factual catalogue handoff and necessary person/company disambiguation remain available.
- Four bounded matching workers and incremental first-card/chunk persistence remain. Duplicate, unresolved and excluded candidates receive replacement feedback, including older-session duplicates. Further GPT calls are driven by an actual missing verified count or larger target.
- Exact positive counts, multi-batch Continue, subjective followups, visible provider failures, no automatic provider switching and independent Ollama/F2–F5 owners are preserved. No model or reasoning settings were changed.

## Verification

- Pre-edit baseline21 tests passed6.642s. New title/year-only one-call50 regression failed against old code, then passed. Duplicate-feedback regression also failed before its correction.
- Final broader suite:**122 passed in38.833s**, including route/worker/transport, scope exclusions, one-call50, structural repair, exact quantity, target120/huge count, shortfall, older-session duplicate, final-save timing, matrix all five features, handoff/shortfall through actual fixture protocol, and frozen Ollama preservation. [regression.log](regression.log).
- Compiled existing desktop UI:**4 passed in27.7s** at1600/1280px:120-card paging/restoration, visible provider failure/manual switching, budget pause/Continue/cancel. No JSX/CSS was changed. The later duplicate/timing corrections have backend122-test coverage; the desktop run predates those corrections. Build2.44s into unique OS temp. Screenshots retained in this directory.
- Read-only fresh-context review identified duplicate-feedback, fixture-request-key and matching-final-save boundary gaps; all corrected and regression covered. Final review found no remaining actionable findings.
- Production config SHA256 remains685522f0a8dde8fc63cb2f2e616927c2e0d4d72b56d8b6889ec68c9c35816a82. Production dist index remains2a0dcb446ffccfa403c998c11be3437bc25947050aa094aaec84a843c30f3916. Original live PID16180/port5000 predates source changes. Live activation requires restarting CP; it has not happened here.
- This is the relevant AI regression suite, not a claim the entire repository suite is green. Historical unrelated failures remain recorded in earlier reports.

## Contract comparison

Approved removal of per-movie generated reasons is implemented. Verified target50, eligibility and exclusions, progressive cards, replacement-only shortfalls, controlled factual handoff and unchanged provider boundaries are exercised. No arbitrary total count cap was added. The real sample needed one replacement request; one response is sufficient when all initial50 identities are accepted, as the regression proves.38.66s is this sample, not a latency guarantee; UI delivery time is additional.

Protocol reference: [official OpenAI output guidance](https://developers.openai.com/api/docs/guides/structured-outputs). CP validates its ordinary JSON response locally and permits one bounded repair; this implementation does not claim provider-enforced JSON Schema generation.
