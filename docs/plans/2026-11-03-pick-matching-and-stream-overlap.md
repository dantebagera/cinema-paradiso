# Correct Pick My Movie identity evidence and overlap GPT/TMDB work

**Status:** Approved implementation. 2026-11-03, Dante replied “ok” to the concrete recommendation: correct recurring matching failures, start bounded TMDB reads while GPT streams, and retire unnecessary deeper searches where evidence already settles the identity. No model/settings change, production restart, commit or release is included. Execute inline; fresh review at the end.

## Problem and decision

- Repeated exact-prompt comparison: initial GPT HTTP mean14.189650s; matching10.946905s, replacement GPT5.954107s and other0.719927s. Three complete CP runs returned50 verified movies in27.84–34.46s.
- Reproduction using existing search/ranker (28 public TMDB reads): missing TMDB release dates were replaced with the requested year in `_smart_match_tmdb_candidates`. Undated Frailty/Coherence/Audition namesakes acquired false exact-year evidence. The Invisible Guest and Perfect Blue hit unrelated duplicate-release branches.
- Five additional read-only detail requests confirmed that the actual films have the supplied GPT years in TMDB release history despite primary dates one year later. No guessed year or lowered confidence is needed.
- Chosen implementation: preserve provider facts in the existing matching conversion; enrich only a ranker-accepted year-filtered near-year candidate with actual release history before avoiding unconstrained search. Reuse details in the final resolver. Replace the existing post-response worker owner with one bounded candidate batch that can also prefetch streamed title/year objects. Accept and publish only final validated response candidates under fixed constraints.
- Alternatives: silently accepting nearest titles/years weakens identity; matching only after full output retains measured serial waiting; another matcher or speculative publication creates competing behavior. These are excluded.
- Unknown until measured: remaining rejections and actual overlap/latency improvement. Three fresh exact-prompt runs on the same configured model will measure this; no speed guarantee.

## Contracts affected and contract-change decision

| Contract/source | Agreed behavior and exceptions | Proposed behavior | Changes contract? | Decision |
|---|---|---|---|---|
| Verified identity | Existing identity ranker accepts; genuine remakes/ambiguity cannot be guessed | Missing source date stays unknown. Early near-year identity must be accepted by the existing ranker on the year-filtered set AND requested year evidenced by same-ID TMDB release history | No weakening; correct provenance | Approved correctness scope |
| Complete-response acceptance | Failed/incomplete/malformed GPT output never publishes verified recommendations | Streamed names initiate bounded reads only; final schema, scope, permission and identity/eligibility checks still gate publication | No | Preserve |
| Exact target and filters | Arbitrary positive target, exclusions/follow-ups, dedup, honest shortfall/Continue | Existing owners and result order; replacement requests only for real remaining count | No | Preserve |
| Independent provider/domain owners | Ollama instructions/limits/wire/recommendations unchanged; existing Movie Smart Match cannot gain fabricated date evidence | Correct common search-result provenance; no Ollama prompt/transport edit. Test affected shared identity callers | No product-contract weakening; invalid behavior is not an agreed contract | Preserve |
| Early lookup lifecycle | Four concurrent workers and bounded per-response work | One worker implementation; at most50 speculative candidate keys, four workers; final-only matching retains four-item lookahead | Internal scheduling only | Approved overlap scope |

If actual provider evidence is insufficient, retain existing deeper lookup/ambiguity behavior and genuine replacement calls. Do not manufacture certainty to reach50.

## Current design and ownership

Checkout `master`, HEAD`be511f98846a67a182e5b371ad087938e9344362`, extensive dirty work retained. Baseline byte copies/hashes at OS-temp `cp-overlap-work-z3h8cgh_/baseline`. Production PID16180/port5000, config`config.json`, data`data/`, model`gpt-6.1-sol`, default50. Served index previously verified equal to dist/index.html hash`2a0dcb446ffccfa403c998c11be3437bc25947050aa094aaec84a843c30f3916`. This process predates current implementation. No restart is part of this work.

| Responsibility | Authoritative owner/callers | Preserve/retire |
|---|---|---|
| Search candidate conversion | app.py::_smart_match_tmdb_candidates, _identity_tmdb_candidates; Smart Match, verification/import, F1 | Preserve real provider dates and ranker; remove query-year fallback from evidence |
| Actual release-year extraction | app.py::_tmdb_release_year_values, _ai_movie_details | Reuse extractor; append release_dates to existing read; same-ID detail reuse |
| Confidence decision | services/identity_decision.py::evaluate_identity | No second ranker or changed thresholds |
| Streaming and terminal acceptance | services/chatgpt_transport.py | Optional text-delta observer; public payload, deadline/retries, terminal/tool checks unchanged |
| Candidate decoding and lookup work | New services/chatgpt_recommendation_stream.py, orchestrated by Recommender | Replace old _resolve_candidates pool; one bounded lookup owner for streamed/final candidates |
| Scope, eligibility, persistence | Recommender, AICatalog, AIJobStore | Final-only accepted entries, fixed scope, dedup/order/chunks/Continue |
| Instrumentation | tools/profile_ai_features.py, tests/ai_provider_fixture.py | Actual streamed fixture, overlapping wall-time metrics, no double-counting |

## Exact behavior contract

### Frontend

No JSX/CSS/layout change. Reuse Discover cards and AIJobStatus. No unverified speculative cards appear. Existing paging, restore, failure, cancellation and Continue remain. Verify compiled desktop with real fixture streaming.

### Backend: matching

1. Normalize candidate with provider date/year only; a query year may filter a search but may not fill a missing result year.
2. Keep exact-year fast matching. For an exact title/original-title match with a real primary date one year away, permit the existing ranker's accepted year-filtered decision to proceed early only when same-ID detailed TMDB release history includes the requested year. A supplied read-only detail callback provides that evidence. No raw guessed identifiers or first-hit selection.
3. If proof fails, use existing unconstrained/alias retrieval and ranker; genuine ambiguity remains unresolved. Cache the already-fetched same-ID detail on the operation candidate so final resolution does not repeat it. Canonical card year remains provider primary date. Objective year filters still run through AICatalog and can exclude the film.
4. Other shared matching callers retain legacy retrieval depth but stop receiving invented release years. Test Smart Match API, identity decisions/verification and authoritative identity contracts.

### Backend: stream overlap

- Add optional on_text_delta callback to transport.run; consume nonempty output_text deltas without serializing the callback or changing requests. Failure/cancellation remains failure. No successful CompletedResponse before terminal validation.
- Incrementally decode only complete title/year objects in the top-level recommendations array, respecting strings/escapes, arbitrary chunk boundaries and scope-field ordering. Validate each entry against the same F1 item schema. Speculative parser has64KiB memory cap and at most50 unique keys; exceeding its cap disables prefetch, not valid final-response processing.
- One CandidateBatch owns max4 executor threads, at most50 speculative keys and per-key futures. Duplicate keys share a read. Final accepted list is authoritative: discard unrelated speculative results, fetch missing/mismatched final entries through the same owner, maintain recommendation order and four-item lookahead for non-streamed final input. Speculative reads may complete before GPT; they cannot publish or weaken scope.
- Close on success, repair, handoff, provider failure and cancellation; cancel queued work, wait for bounded active lookups under existing network timeouts. Errors in speculative-only results do not replace the final model result. No background worker survives job cleanup. No new persistence schema/migration/config flag.
- Recheck account permission before publishing after streaming, so mid-call loss does not promote prefetch results.

### Timing boundaries

GPT and prefetch now overlap. Existing tmdb_matching phase measures residual matching, eligibility and persistence AFTER the response; label it accordingly. Also record total active TMDB HTTP wall time and its intersection with GPT HTTP spans, using interval unions so workers are not summed. Total includes all stages and cleanup. Source-bound real runs use unique OS-temp roots, actual same selected model/account, exact prior prompt/explicit target50, at most3 attempts/180s each, no concurrent test/build workload. Preserve unsuccessful captures as evidence.

## Implementation sequence

1. Record baseline and read-only TMDB reproduction. Add failing provenance, release-history proof/absence/ambiguous-remake and detail-reuse tests. Correct existing search owner and its callers.
2. Add failing transport-observer and chunked candidate/worker tests. Build one bounded stream lookup owner; replace the old recommender pool and wire the optional observer. Cover failed terminal, changed final data, exclusions, no premature publication, cancellation and permission loss.
3. Update offline HTTP fixture to emit real text deltas and timing instrumentation for overlap. Run focused and broader matching/AI/Ollama checks; classify pre-existing failures honestly. Build/run affected compiled desktop scenarios in OS temp.
4. Request fresh read-only review, fix concrete findings, then run three fresh exact-prompt real captures; report GPT, hidden overlap, residual work, matching requests, first card, total and actual call counts. Verify config/dist/live PID unchanged and preserve unrelated dirty files.

## Acceptance matrix

| Scenario | Expected result | Proof |
|---|---|---|
| Undated namesake vs real one-year release | Missing date stays unknown; cannot invent exact-year confidence | Matching regression + retained public reproduction |
| Year-filtered exact title with requested year in actual release history | Existing ranker agrees, real ID resolved, details read once, no unconstrained/alias calls | Synthetic proof/adverse cases + real replay |
| Missing proof, wrong ID, >1year, actual remake ambiguity | No new early acceptance; deeper owner or explicit rejection | Adverse tests |
| Stream contains complete candidate before terminal | TMDB read starts while GPT ongoing; zero saved cards until full validation | Barrier-based integration test |
| Streamed and final candidates differ | Only final validated candidates displayed | Adverse integration test |
| Malformed/failed/incomplete/tool response after speculative reads | No speculative cards accepted; pool closes; normal failure/repair/handoff | Transport + orchestration tests |
| Prompt injection-like string mentions recommendations | No nested/string candidate extraction | Parser fragmentation/escape tests |
| Explicit exclusions, unknown runtime, duplicates, older session | Same eligibility/rejection/target semantics | Existing + affected tests |
| 120/huge target, Continue, page restore | Exact count and saved progress retained | Existing suites and compiled desktop |
| Cancellation/permission lost | No publication from prefetched results after invalidation; bounded cleanup | Adverse tests |
| F2–F5 and Ollama | Optional observer does not alter their payloads/acceptance | Transport/matrix/frozen preservation |
| Timing overlap | No double-counted HTTP workers; GPT+residual+other matches full wall clock | Synthetic interval test + real traces |

## Verification and rollout

Baseline suite captured in unique OS-temp root before edits. Relevant commands use .venv Python, CP_TEST_MODE=1, unique CP_TEST_ROOT, CP_TEST_QBT_MODE=embedded and non-production ports. Focused suites: test_ai_recommendation_matching, test_chatgpt_recommendations, test_chatgpt_transport, new stream tests, test_ai_timing_capture. Broader: Smart Match API/service, identity decision/verification/authoritative identity, AI jobs/routes/catalogue/provider/matrix and F2–F5/preservation. Do not call a focused rerun a green repository suite. Desktop wrapper uses -AIProviderOffline with its own compiled bundle/root; production dist remains unchanged. Actual provider samples cannot verify browser paint. No production activation; final answer states this and gives measured evidence.

## Execution ledger

Baseline112 tests passed28.657s. New provenance/history tests failed against original code, then96 shared matching/identity/Ollama preservation tests passed7.470s. Real5-title replay now accepts all5eligible films with2TMDBreads each (10reads total versus28 in initial reproduction), without changing canonical primary years. Reproduction roots:cp-ai-match-repro-iivfikgp,cp-ai-release-proof-3x82o6jl,cp-ai-match-after-fx9itng4. Stream observer/early-read barrier tests failed before implementation. Initial36stream/transport/recommender tests passed27.637s. Added permission-loss-during-lookup and queued-cancellation regressions failed before hardening, then final235-test broader suite passed83.314s in cp-overlap-regression-ea713bb11aa54e6c8b00fa44b2fb2ffa. Fresh read-only review against byte baseline found no actionable findings. Compiled desktop and real captures pending. Diagnostic matching field renamed to matching_after_gpt_seconds (only harness/test callers); historical evidence is retained unchanged. At most50 speculative keys plus final-list-only misses are bounded; old separate resolver pool removed.

Completed:compiled desktop4pass32.7s/build2.47s. Three source-frozen real captures each complete50verified/oneGPT:20.376943s,21.625464s,21.371463s;mean21.124623s versus31.850430s before (33.68% observed reduction). MeanGPTHTTP16.985915s;localrequesthandling2.961829s;residualmatching0.428965s;hiddenHTTPoverlap7.552849s. Slotacquire5.850699s spike recorded, not reproduced by six synthetic lease pairs;noDBowner change. Evidence:docs/verification/chatgpt/matching-overlap-2026-11-03/report.md. Productionconfig/dist/PIDunchanged;noactivation. All approved contracts covered;first-card improvement not proven.
