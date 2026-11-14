# Pick My Movie: one candidate response, then concurrent TMDB matching

**Status:** Approved implementation, 2026-11-03. Dante: “implement that simple flow in pick my movie, then test with my exact prompt for 50 movies and show me how long gpt, tmdb matching and the full process each take”. This is the design and implementation plan; execution is inline using the existing checkout. No commit, production restart or configuration change is authorized.

## Problem and decision

- Current F1 asks for 50 explanations plus a large typed submission tool. Prior measured replay needed 55.54 seconds across two GPT calls and 72.65 seconds overall. The existing TMDB matcher already uses four bounded workers.
- Requested behavior: request title/year candidates in one response, resolve them through TMDB, publish verified cards progressively, and request replacements only for a genuine shortfall. Preserve arbitrary positive total counts and resumable larger batches.
- Chosen implementation: replace the F1 candidate submission tool with locally validated JSON text. Each candidate contains title and year only. The initial response also declares constraints once; subsequent responses cannot change them. Controlled person/company lookup and factual AI Control handoff remain genuine exceptions. No second recommender or prompt-specific shortcut.
- Alternatives: keeping the old full result tool retains unnecessary schema/explanation overhead; removing objective validation would weaken exclusions. Neither meets the request.
- Unknown: actual latency improvement, response validity and rejection counts until measured. No model-speed inference from chat timers.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and exceptions | Proposed behavior | Changes contract? | Decision |
|---|---|---|---|---|
| Dante's approved simple flow | Titles/years only, CP performs matching | Remove generated reasons and candidate tool | Yes, replaces prior per-card reason generation | Explicitly requested in this turn; same existing cards accept absent reason |
| Scope/exclusions/followups | Keep objective filters and conversation constraints | Same normalized query owner; small initial constraint envelope, fixed for replacements | No | Preserve |
| Verified identities and feature eligibility | No guesses, duplicates, shorts or upcoming cards | Existing ranker/catalogue, four workers and progressive persistence | No | Preserve |
| Exact positive target/Continue | Any positive integer target; honest shortfall and durable progress | Up to 50 candidates per response; replacement/big-target batches only as needed | No | Preserve |
| Other providers/features/privacy | Ollama and F2–F5 independent, selected account/model, no automatic apply | Same owners | No | Preserve |

## Current design and ownership

Checkout `master`, HEAD `be511f98846a67a182e5b371ad087938e9344362`, extensive pre-existing tracked/untracked dirty work. Retain it. Running Python312 PID16180, port5000; config.json uses data/, ChatGPT gpt-6.1-sol and default50. Served index SHA256 equals dist/index.html (`2a0dcb446ffccfa403c998c11be3437bc25947050aa094aaec84a843c30f3916`); config SHA256 `685522f0a8dde8fc63cb2f2e616927c2e0d4d72b56d8b6889ec68c9c35816a82`. This backend process predates these changes.

| Responsibility | Owner/callers | Preserve/retire |
|---|---|---|
| F1 orchestration | services/chatgpt_recommendations.py, /api/ai/recommendations | Preserve job lifecycle; retire cp_result submission processing for F1 |
| F1 output/instructions | services/chatgpt_skills.py, resources/ai/chatgpt/movie-curator/SKILL.md | Hash instructions, output schema and continuation schema; no reasons |
| TMDB matching/eligibility | app.py::_ai_resolve_recommendation, AICatalog.candidate_eligibility | Existing ranker, release/runtime/filter checks |
| Durable results | AIJobStore | Same account/session/target ownership, exact counts |
| UI | DiscoverWorkspace and existing AIJobStatus/cards | No JSX/CSS change; absent reason already supported |
| Diagnostics/fixtures | tools/profile_ai_features.py, tests/ai_provider_fixture.py, tools/qualify_chatgpt_features.py | Update actual protocol callers; retain historical evidence |

## Exact behavior contract

### Frontend

Reuse current desktop status and movie cards without changing layout. Cards no longer require generated explanations. Existing failure, partial, Continue, cancellation and history controls remain.

### Backend

Keep route request/count/session fields unchanged. GPT receives original prompt text inside the existing context envelope, current count/batch target, exclusions and actual previous results. Return JSON recommendations of title/year only and initial scope using the existing query language. CP parses JSON, validates the registry schema, normalizes query and verifies controlled identities before matching. Catalogue lookup/handoff tool calls are supported for real entity/factual cases; a normal taste request requires none. No result-tool compatibility adapter remains. One existing bounded structure repair remains for malformed data; provider failures remain visible. Four concurrent identity workers preserve order. Filter validation and progressive publication stay in the authoritative recommender. A duplicate/unresolved/excluded candidate must cause actual replacement feedback. Stop with honest partial result when no new eligible identities are available.

### Timings

Use monotonic clocks and a unique OS-temp CP_TEST_ROOT with existing credential owner and real public GPT/TMDB calls. Exact prompt: `i need you to lit 50 movies with very twisted story you wont expect the ending\nyour responce should be a list of movies names and years , no any other details , dont seek more info , dont reply by paragarph or any way of responce  only the list`. Explicit target50. Do not echo/copy credentials or change production settings. Bound capture to six HTTP inference attempts and600seconds. GPT time is complete transport roundtrip (report HTTP separately), matching is measured wall time across all workers including eligibility/persistence; total starts before job creation and ends at terminal backend result. Report overlapping HTTP durations separately, never sum worker durations as wall time. UI paint not included.

## Implementation sequence

1. Add failing protocol and one-call50 tests; retain exclusion, quantity, handoff, followup, partial, budget and real route tests.
2. Simplify existing F1 schema/instructions and response parser, update fixtures and qualification caller; remove obsolete F1 candidate tool handling.
3. Add matching phase spans/explicit diagnostic count, test trace metrics; run focused then broader AI/Ollama regression suites.
4. Run actual F1 test using exact prompt, preserve raw trace and results, report all attempts and honest timing breakdown. If a captured error exposes a defect, preserve that capture and label the corrected repeat separately.

## Acceptance matrix

| Scenario | Expected result | Evidence |
|---|---|---|
| Exact prompt/50 valid candidates | One GPT response,50 TMDB verified unique cards | New one-call test + real capture |
| Candidate duplicate/excluded/unresolved | Only actual shortfall replaced; reasons sent to next call | Adverse regression |
| Objective exclusion and continuation | Rejected horror never appears; fixed scope cannot change | Existing strengthened tests |
| 120 and huge target | Batched exact target, pause/Continue preserves progress | Existing tests |
| Followup “third” | Actual prior third result and constraints available | Existing test |
| Exhaustive factual set | Original request handed to AI Control; no fabricated shortlist | Existing test |
| Malformed JSON/provider failure | Bounded repair/visible failure; retain saved cards | New adverse tests |
| Full backend/UI path | Actual route returns cards using new protocol, unchanged desktop renders cards | Route fixture + existing desktop scenario if needed |
| Ollama/F2–F5 | Existing contracts unchanged | Preservation/matrix suites |

## Verification and rollout

Baseline:21 focused tests passed in6.642seconds in unique OS-temp isolation. Test current changed owners with unittest; broaden to related AI provider, jobs, transport, catalogue, matrix and preservation suites. No frontend build required for backend-only changes; desktop fixtures exercise existing rendering with updated protocol. Real benchmark uses separate diagnostic store and fresh TMDB cache. Production activation is a separate action; do not imply the live PID has loaded changed Python source. Retain dirty files and config/dist hashes. Report total real GPT calls, state/card count, timing boundaries, failures and activation status.

## Execution result

Implemented and isolated-tested. Final122 tests pass38.833s; compiled desktop4pass27.7s. Final exact-prompt capture:50 distinct verified cards,2GPT calls,24.410854s GPT stage,13.435064s matching/validation/persistence,0.812706s other,38.658624s total. Full evidence in docs/verification/chatgpt/simple-pick-2026-11-03/report.md. First47.585904s trial retained. No production activation. Review corrections: duplicate rejection feedback including older-session results, actual fixture request key, final-save-inclusive timing boundary.

## Authorized repeated comparison

Dante: "run that comparison with my exact prompt and the same model, repeat it a few times and show me where cp is adding time". Diagnostic-only: alternate three plain exact-message runs and three actual CP F1 runs. Same .venv interpreter, selected account/model from unchanged configuration, same ChatGPTTransport/PublicOpenAIHTTP implementation and default reasoning; fresh process/session per capture. The main comparison uses the first completed GPT response of each run, excluding any CP replacement requests and TMDB matching. Plain controls use no extra instructions or tools and produce an unverified list. Full CP runs retain constraints, matching and true replacement handling; report these separately. Plain captures allow one HTTP attempt; each CP capture allows at most three actual attempts and180seconds. No silent failed-trial substitution. Measure first actual text delta, complete HTTP duration, account/lease and transport roundtrip, token usage including cache/reasoning details, actual payload byte counts, scope-context fetch time, TMDB and total. No tests/builds concurrently with captures. Provider server/cache/queue conditions cannot be held fixed; paired ordering and three observations describe variation, not a model-wide benchmark. Harness additions only retain public metrics and requested movie output; credentials are never logged. Production source owners, config, data and running process unchanged. Harness-focused five tests pass before captures. Existing full relevant-suite proof remains a previous run, not repeated as current full-suite verification.

Repeated comparison completed:three plain+three CP initial requests,plus three genuine CP top-ups,nine HTTP calls total. All six returned50 suggestions;three CP workflows each completed50verified. Initial HTTP means plain15.262435s/CP14.189650s;CP initial local wrapper mean0.039841s. CP full mean31.850430s=14.229491initial+5.954107replacement+10.946905matching+0.719927other. Five diagnostic tests pass0.005s. Product source/config/served bundle unchanged. Evidence:docs/verification/chatgpt/prompt-comparison-2026-11-03/report.md. Extra-context6second penalty hypothesis not supported; matching/top-up costs confirmed. No further real calls scheduled.
