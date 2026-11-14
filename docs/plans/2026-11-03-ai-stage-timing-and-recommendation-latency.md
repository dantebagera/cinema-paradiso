# Measure AI stages and correct recommendation latency

**Status:** Approved diagnostic replay and optimization, November 3, 2026. Dante: “repeat this test using my prompt and give me a break down of time so we can see how long each step takes and optimise the whole process ... we will need to do the same with every ai feature in cp”. Earlier no-repeated-approval instruction applies within this scope. No production restart/config/catalogue action, commit or release is included.

## Problem and decision

- Actual request: `movies with very twisted story you wont expect the ending`, configured target 50, selected model `gpt-6.1-sol`.
- The production job saved 18 cards but failed with `scope_changed_during_operation`. Its original record has no per-call duration; its lifetime includes explicit Continue and must not be presented as GPT inference duration.
- Current F1 requires a full query/scope tool, up to 20 candidates per reply, full serial identity lookup and batch publication. A later repeated scope compares free-text descriptions for literal equality. A diagnostic replay must measure these owners before changing them.
- Scope: bounded real F1 baseline and after capture, reusable timing harness for F1–F5, focused source optimization justified by measurements, isolated regression and compiled desktop proof for UI changes. Existing Ollama remains unchanged.
- Unknown before capture: GPT network/completion time, local transport overhead, actual TMDB cost and the exact changed scope field. Do not invent timings or convert a single observation into a performance guarantee.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior | Proposed behavior | Changes contract? | Decision |
|---|---|---|---|---|
| Dante's quantity decision / previous provider plan | Any positive exact target, no arbitrary total cap, verified distinct results, explicit Continue and genuine shortfalls | Preserve target and continuation; reduce unnecessary per-response overhead for ordinary requests | No | Within optimization scope |
| Recommendation filters and durable context | Original objective requirements and exclusions remain authoritative | Fix requirements once rather than repeatedly asking GPT to redefine identical intent | No; never ignore an actual objective contradiction | Within optimization scope |
| Identity matching | Movie identity and eligibility verified, ambiguous matches not guessed | Retain authoritative ranker and adverse cases; avoid unnecessary deeper lookups for unambiguous titles | No weakening allowed | Within optimization scope |
| Explanation / card behavior | Existing movie cards and brief spoiler-free reasons | Preserve existing card semantics and reasons | No | Within optimization scope |
| Provider/privacy/domain actions | Selected model/account remain pinned; no fallback, model confirmation or automatic apply | Unchanged | No | Existing approved rules |

If measurement suggests weakening any of these rules, stop that part and present the separate required contract-change notice. Increasing the 24-call ceiling is not the fix.

## Current design and ownership

Checkout master at `be511f98846a67a182e5b371ad087938e9344362`, extensive dirty work retained. Baseline snapshot `.superpowers/sdd/2026-11-03-ai-timing/baseline.json`. Production listener was PID16180 on port5000, config `config.json`, data `data`; served index and main bundle matched checkout dist when inspected. This records current activation by Dante, not activation by this task.

| Responsibility | Owner / caller | Preserve |
|---|---|---|
| F1 loop | `services/chatgpt_recommendations.py`, Discover Ask AI | Target, exclusions, follow-ups, batch resume, dedup, no writes |
| GPT response / typed validation | `services/chatgpt_transport.py`, `chatgpt_skills.py` | Public endpoint, complete-only acceptance, redaction, bounds and cancellation |
| Identity retrieval / decision | `app.py` matching helpers, existing identity decision owner | Correct remakes/year/alias discrimination, no first-result guessing |
| Durable jobs | `services/ai_jobs.py` | Account/skill pin, revision/receipt isolation, saved results |
| F2 / F3 / F4–F5 | Agent / MovieIdentity / IPTVInference and native domain owners | Typed actions, consent, supplied candidates, human apply |
| Status/cards | `AIJobStatus.jsx`, `useAIJob.js`, existing Discover cards | CP desktop design, page/history/selection ownership |

## Exact diagnostic behavior

`tools/profile_ai_features.py` creates a new OS-temp root, uses existing CP owners under isolated test paths, and uses the explicitly connected CP account through its existing OAuth/DPAPI owner. Tokens are never copied or logged. No browser consent, background manager, download or confirmation is launched. TMDB key remains in process memory; no production config copy is written.

F1 baseline uses the unchanged runtime skill, prompt and saved target. It starts a fresh session, so it is not the production job's Continue. Cold process/cache state is labelled. Maximum six actual inference attempts and 600 seconds; every retry counts. TMDB reads capped at350. Partial/failed records remain evidence, never rerun silently. A new separately labelled after capture uses the same prompt/model/count and cap. Additional feature captures are explicit and bounded; synthetic evidence is labelled rather than presented as live full-feature latency.

Trace JSONL records monotonic stage starts/ends, GPT first bytes and completed-event times, account access, provider request counts/endpoints without credentials/query secrets, candidate matching, first saved cards, and terminal state. Parent spans overlap child spans: never sum both. Backend-ready timing is distinct from rendered paint. Stage totals and raw trace remain in each evidence root.

## Implementation sequence

1. Guard and test the timing harness; run F1 baseline before changing the product owners. Identify exact latency and failure evidence.
2. Correct only the measured F1 owners, with regressions first. Reuse existing matching/ranking; retire repeated scope declarations after pinning. Preserve independent Ollama code.
3. Extend bounded captures across F2–F5, separating real GPT protocol timing from native/full workflow timing. No proposal applies as part of profiling.
4. Run focused owner/legacy tests and offline full-flow fixtures; compile only to temp if frontend source changes. Execute one labelled F1 real after capture; report variability and any remaining dominant stage.

## Acceptance matrix

| Scenario | Expected result | Evidence |
|---|---|---|
| Exact motivating prompt, target50 | Measured GPT / TMDB / local / first cards / total, no manufactured timing | Real baseline and labelled after trace |
| Same meaning reworded by GPT | No fatal free-text scope comparison after original requirements are pinned | Regression and captured scope difference |
| Actual changed objective / wrong count | Cannot weaken or change original request | Adverse regression |
| Duplicate, ambiguous remake, rejected identity | No wrong identity or padded count | Existing ranker + additional boundary tests |
| 120/500/large exact target | Preserved pagination, saved partial result, Continue and account pin | Existing full-flow tests |
| Provider fails after valid cards | Preserve and report cards and real failure, no silent fallback | Adverse tests |
| F2–F5 timing | Same timing conventions, genuine attempt counts, synthetic/native scope labelled | Bounded capture records |
| Privacy | No tokens/API keys/credential URLs in traces; no catalogue writes | Harness redaction / guard tests |

## Verification and rollout

Focused commands use a unique temp `CP_TEST_ROOT`, `CP_TEST_MODE=1`, embedded qBittorrent and offline guards. Harness-only unit checks need no app/network. Relevant suites: `tests.test_ai_timing_capture`, `tests.test_chatgpt_recommendations`, `tests.test_chatgpt_transport`, `tests.test_chatgpt_skills`, `tests.test_ai_jobs`, `tests.test_ai_feature_matrix`, `tests.test_ai_provider_preservation`, plus any modified identity-owner tests. Existing broad-suite unrelated failures remain recorded in the November2 report; do not rerun all tests or call a focused pass full-suite proof.

No production activation is authorized. Preserve current config/dist hashes and unrelated dirty work. Report exact real call usage, failed captures, measured versus inferred costs, source/compiled/live distinction and every remaining contract difference.

## Execution and measured outcome

November3 source correction complete; activation unperformed. Detailed evidence: `docs/verification/chatgpt/latency-2026-11-03/report.md` and its raw traces/measurements JSON.

The unchanged baseline replay failed after85.561s with19 verified cards,52.541s in three completed GPT round trips and122 TMDB reads. Its exact false scope change was GPT adding an instruction to avoid the19 already accepted films. Two retained optimization trials stopped at their declared caps with49 cards, exposing missing rejected-candidate feedback rather than being labelled successful.

The final corrected replay completed50 verified cards in72.654s: first completed50-candidate GPT reply45.480s, replacement reply10.061s, TMDB HTTP wall time9.695s, request-slot acquire/release6.503s, other local time0.916s. First backend card47.735s.155 provider reads overlapped through bounded matching; their summed duration must not be added to elapsed time. The slot release spike is observed but not causally diagnosed. A separate single-call names/years-only50-suggestion control took27.226s at the GPT boundary and made no verified-card claim.

Actual owner changes: F1's initial `cp_result.submit` includes scope and candidates together; continuation schemas forbid redeclaration and are hashed with the initial schema. The obsolete `cp_scope.set` registration/caller is retired, including the forward-looking qualification harness; old failed qualification records are untouched. Normal per-response capacity50, total target unrestricted. Four-worker/four-lookahead matching preserves order, first verified card and small chunks publish incrementally,200 accepted examples plus200 bounded rejection records inform top-ups. Exact-first matching uses the existing identity authority, requires an actual matching provider release year, and keeps deeper lookup for uncertainty; default legacy callers retain their previous behavior. No accepted filter/count, identity gate, human confirmation, provider/privacy or card-reason contract was weakened.

Other native samples: F2 public Movie lookup26.828s/three GPT calls/one card with partial coverage; F3 synthetic two-file native Smart Match6.883s/one call/two proposals; F4 synthetic IPTV two-title classification4.878s/one call/two review proposals; F5 synthetic IPTV two-title matching10.140s/two calls/two proposals. No Apply. These are representative baselines, not a claim that all other workflows are optimized.

The explicit new profiling request consumed22 real inference attempts across all nine labelled captures, including unsuccessful trials and the output-format control. Every cap was enforced, no failed capture was silently replayed, no earlier six-call qualification reservation was reset. No more real requests are running or planned in this pass.

Verification:115 focused tests passed37.359s,23 focused follow-up tests passed11.993s; final fresh-root group117 passed42.859s. Four affected compiled desktop scenarios passed24.7s using existing temp compiled bytes; frontend source was unchanged and no build was made. Production config/dist index hashes remain unchanged. No restart, commit, package, release, catalogue action or shutdown.
