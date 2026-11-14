# AI timing capture and recommendation correction — November 3, 2026

The exact requested 50-film prompt now reached 50 verified cards in an isolated replay. It is still not a few-second operation: the measured completed GPT round trips accounted for 55.5 of 72.7 seconds. The source correction is tested but has not been activated in the running production CP process.

## Request, authorization and boundaries

Dante explicitly requested repeating `movies with very twisted story you wont expect the ending`, measuring every stage, optimizing the process, and doing the same for every CP AI feature. All F1 captures retained the selected `gpt-6.1-sol` model and Settings target50. Settings were not changed.

The disposable profiler imports the existing CP owners under test-mode paths, then allows only the necessary public TMDB reads and the existing public OAuth/Responses transport. It uses the already connected CP account through CP's own credential/refresh owner; tokens are not copied or printed. No background manager, browser sign-in, stream, download, confirmation, metadata Apply or production catalogue mutation is started. The Movie identity and IPTV samples are explicitly synthetic. Their real native services, proposal stores and real GPT/TMDB boundaries are exercised. No attempt is made to benchmark the ChatGPT website.

Current implementation baseline: master, HEAD `be511f98846a67a182e5b371ad087938e9344362`, pre-existing dirty work preserved. Baseline snapshot: `.superpowers/sdd/2026-11-03-ai-timing/baseline.json`. Production listener was PID16180/port5000, data owner `data`, configuration `config.json`; HTTP index and main bundle matched checkout dist. Source, loaded backend and compiled frontend are separate facts. The process was not restarted, and configuration/dist index hashes still match the start of this task.

## F1: measured breakdown

The initial production job record had no per-stage timestamps and included a Continue. Its historical lifetime was not used as a GPT timing measurement. The numbers below come from new timed replays through the actual recommendation, identity, catalogue, transport and job-store owners in separate temporary roots.

| Stage | Original baseline | Corrected replay |
|---|---:|---:|
| Completed GPT round trips, summed | 52.541s across3 calls | 55.541s across2 calls |
| TMDB HTTP time on the wall clock | 23.927s /122 reads | 9.695s /155 reads |
| Timed request-slot acquire/release | Not separately captured | 6.503s |
| Other local work, initialization and persistence | 9.092s, including unclassified slot overhead | 0.916s |
| Total from capture request start | **85.561s** | **72.654s** |
| First cards available from backend | 80.254s | **47.735s** |
| Terminal outcome | **Failed,19 cards saved** | **Completed,50 verified cards** |

Original call1 returned only scope in5.743s; call2 returned20 suggestions in41.599s; the later scope response took approximately5.200s and caused the failure. Corrected call1 returned scope and50 candidate entries together in45.480s; rejected or unresolved candidates required a replacement response taking10.061s. The first card was saved promptly after that first completed response. Unknown runtime and ambiguous identity were not accepted merely to reach50.

The local request-slot release spiked to roughly6.5 seconds in the corrected run. Other samples usually spent hundredths of a second there. This is an observed intermittent local cost, not a proven storage/hardware diagnosis; no storage stress test, benchmark or configuration change was performed to explain it.

Parallel candidate HTTP intervals overlap. The155 request durations sum to27.291s, but occupy9.695s of elapsed wall time. **Do not add the overlapping27.291s to the total.** The published table uses the union of timed HTTP intervals, keeps slot time separate, and puts remaining elapsed time in Other. GPT round-trip time includes network/server waiting and streaming until completion; it is not a measurement of internal GPU compute time. First backend-ready cards are not a measured browser paint time.

These are single samples with different generated candidates and network conditions. They are not a statistical latency guarantee or a like-for-like throughput percentage: the original attempt failed with19 results while the corrected attempt completed50. Some offline regression checks ran during diagnostic captures, so local overhead is not an isolated hardware benchmark.

## Names/years-only control

The same prompt, account, model and target50 were also sent once with a short instruction to return JSON containing only title/year pairs, no tools or reasons. GPT returned50 suggestions in **27.226s**; the whole control took27.319s. No TMDB matching occurred and no verified-result claim is made for that list.

This isolates the output-format difference. It supports reducing unnecessary prompt/output complexity, but does not establish that CP can display50 verified cards in27s or that this model/account will always return50 suggestions in a few seconds. Existing concise spoiler-free card reasons were retained; they were not silently removed as a speed tradeoff.

## Confirmed owner faults and source corrections

1. **Repeated scope declaration caused a false failure.** The baseline trace captured GPT adding “Avoid all19 previously accepted films in this recommendation session” to the subjective requirements. The objective query was unchanged, but CP compared the whole description for exact equality and failed with `scope_changed_during_operation`.

   F1 now declares scope and candidates together in the first `cp_result.submit` result. The later result schema accepts candidates only. The original typed scope remains pinned; actual objective/count conflicts remain rejected. The obsolete `cp_scope.set` tool was removed from runtime registration and callers. Scope and continuation schemas are included in the skill hash, so old jobs are not silently rebound to new instructions.

2. **Every recommendation paid for full deep matching.** The existing matching owner performed title/year and title-only searches, fetched aliases for up to three candidates, then fetched chosen details.

   The shared owner now has an explicit `exact_first` option used by recommendations. It still calls the authoritative identity decision over the full year-filtered candidate set. It short-circuits only when that owner accepts an exact provider title and actual provider release year. Missing dates, wrong years, aliases and ambiguity retain deeper matching. Legacy callers retain their default two-search/alias behavior; no first-search-result shortcut was introduced.

3. **Matching was sequential and publication waited for the entire batch.** F1 now resolves with a maximum of four workers and four-item lookahead, preserving recommendation order. It saves the first verified card promptly, then small chunks. Cancellation stops future submissions; no unbounded full-list work queue is created.

4. **Small top-ups repeatedly suggested rejected films.** The first optimization trials exposed this separate problem. CP had only sent the last20 accepted titles and no explanation of which suggestions failed. F1 now sends up to200 accepted examples plus bounded persisted rejected-candidate feedback. This preserved actual eligibility rather than padding the total. The default per-response capacity is50; larger total targets remain unrestricted and resumable. The24-attempt per-run safety guard remains; there are no24 compulsory steps.

No Movie title, ID, path or studio was hardcoded into a production rule. The reusable rule is: **fix request requirements once, ask for the candidate list directly, use existing identity authority with deeper work only when needed, and tell subsequent calls which candidates are already accepted or rejected.**

## Other AI features: native measured samples

| Feature and measured input | GPT completed round trips | TMDB wall time | Total | Outcome |
|---|---:|---:|---:|---|
| F2 AI Control: read-only The Prestige(2006) lookup | 17.015s /3 calls | 4.517s /18 reads | **26.828s** |1 card; partial coverage reported |
| F3 Movie Smart Match: two synthetic files, Alien/The Prestige | 4.461s /1 call | 2.154s /10 reads | **6.883s** |2 processed,2 native proposals, no Apply |
| F4 IPTV classification: two synthetic titles in one group | 4.757s /1 call |0 | **4.878s** |2 native review proposals, no Apply |
| F5 IPTV matching: the same two synthetic titles | 7.649s /2 calls | 2.275s /8 reads | **10.140s** |2 native matching proposals, no Apply |

F2 intentionally remained read-only and its partial-coverage result is not labelled a complete catalogue proof. It made a search call, a details call, and a final response. F3's native proposals live in its coordinator, not F1's card-result table; zero generic result items does not mean zero proposals. F4/F5 use synthetic providers and separately owned IPTV metadata settings; no actual provider account or stream URL was sent to GPT. These samples cover one chosen workflow per feature, not every CP action or all catalogue sizes. The other features now have a repeatable timing method; they are not all claimed optimized.

## All attempts retained and real-call cost

| Capture | Real inference attempts | Total | Saved verified/review items | Result |
|---|---:|---:|---:|---|
| Original F1 baseline |3 |85.561s |19 |Scope-change failure |
| F1 trial1: larger batches, matching/publishing work |6 |101.579s |49 |Stopped at diagnostic cap; duplicate top-ups exposed |
| F1 trial2: single initial result |3 |74.278s |49 |Stopped at diagnostic cap; rejection feedback still missing |
| Corrected F1 including rejection feedback |2 |72.654s |50 |Completed |
| F2 native sample |3 |26.828s |1 |Partial coverage |
| F3 native sample |1 |6.883s |2 native proposals |Completed preview |
| F4 native sample |1 |4.878s |2 |Completed preview |
| F5 native sample |2 |10.140s |2 |Completed preview |
| Names/years-only control |1 |27.319s |50 unverified suggestions |Format control only |

**22 real inference attempts total**, under Dante's new explicit replay/optimization request. This is separate from the earlier completed six-call implementation qualification; those exclusive reservation files were not reset or reused. No capture silently retried after its declared call/time cap. Each capture had at most6 inference attempts and600 seconds; lower individual caps were used for the other features and final trials. TMDB reads were capped at350 per capture. The final useful output was not selected by hiding the two unsuccessful optimization trials.

Raw redacted traces, per-run summaries and aggregate `measurements.json` are saved beside this report. The reusable command is `python tools/profile_ai_features.py --feature F1 --label diagnostic --max-calls 3 --seconds 300`; it performs real inference and must only be invoked within the user's authorized profiling scope. Other feature choices are F2–F5; `--plain-control` is an explicitly labelled F1 format experiment. No unrequested scheduled profiler or background capture was installed.

## Verification and remaining limits

- The capture budget, trace credential redaction and failure recording tests failed before implementation, then passed.
- The50-film single-response capacity, pinned continuation schema, incremental first cards, rejected-candidate feedback and matching fast-path regressions were watched fail before their fixes.
- A focused provider/transport/skills/jobs/F1/native-domain/Smart Match/Ollama group passed **115 tests in37.359s** after product changes. Follow-up matching/harness/recommendation/preservation checks including two extra adverse cases passed **23 tests in11.993s**.
- Final verification in a fresh isolated root passed **117 tests in42.859s**. Raw log: `C:\Users\dante\AppData\Local\Temp\cp-ai-timing-final-3bb01a7482dc440a891b1651e7001aa7\focused-tests.log`. No further real inference was sent for this verification.
- Actual compiled desktop checks passed **4 scenarios in24.7s**:120-result paging/restore at1600/1280, actual two-item selection/list persistence, and480/500 budget pause/read-only restore/Continue/cancellation. Existing temporary compiled bytes were reused because frontend source did not change. No new production or isolated build was needed.
- The older full Python suite's unrelated failures remain recorded in the November2 verification report. No full-suite-green claim or new full discovery run is made. No Node code changed, so the full Node suite was not repeated.
- Configuration and served-dist index hashes are unchanged from this task's baseline. Source changes are not live backend activation. No commit, restart, release, package, shutdown or production data action was performed.

Remaining: variable GPT generation time dominates this50-film request; source fixes do not guarantee a few-second result. The intermittent slot-store cost was observed but not causally diagnosed. No comparison between other models was made. Full native latency for every AI Control action and real catalogue/provider size remains separate from these five representative samples. The stock UI still shows the24-call safety counter; this work did not redesign it or falsely call it24 required stages.

The public transport behavior was checked against [OpenAI's supported account inference flow](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference): public Responses endpoint, selected account model, non-stored streamed requests and completed-event acceptance.

## Follow-up: Dante's actual website prompt

Dante subsequently reported that Adam on the ChatGPT website returned the whole50-film list within a few seconds. His screenshot shows High selected in the website's thinking control; the screenshot does not show the actual model name or independently establish the settings used to generate that earlier response. This evidence must not be dismissed by assuming the website used less reasoning. The preceding27.2s JSON control was not an exact match for his plain-list message and does not establish that50 suggestions inherently require that time.

The earlier JSON-control trace contains a reasoning item: its answer-message item appeared22.227s into the request, approximately5s before terminal completion;374 output tokens were attributed to reasoning and545 to the visible message. This does not prove that all the preceding22.227s were reasoning compute—network/server waiting is also included. CP's transport omitted an explicit reasoning setting. Official documentation says `gpt-6.1-sol` defaults to medium and supports low, but does not support none. No production reasoning setting was changed.

Two further single-call diagnostic controls used Dante's exact user message, no added instructions, no tools, plain list output, and the same CP model/account. They made no TMDB reads or verification claim:

| Control | Completed GPT round trip | Suggested title/year lines |
|---|---:|---:|
| Exact website prompt; effort omitted/default |13.134s |50 |
| Exact website prompt; explicit low effort |13.301s |50 |

Low reasoning did **not** improve this sample. It must not be presented as the proven fix for the website/API gap. The exact plain-list request was faster than the earlier27.2s JSON-format control, but those samples also differ in prompt structure/output and stochastic response, so this is not a controlled causal estimate for JSON syntax alone. Neither13s API result reproduces Dante's reported few-second website result, and the remaining gap is unresolved. No ChatGPT website model, internal routing, cache or service-tier explanation was inferred without evidence.

These two controls extend the profiling total from22 to **24 real attempts across11 labelled captures**, under the ongoing optimization request. The earlier six-call qualification reservations remain untouched. Raw follow-up traces and summaries are saved beside the original evidence. Only the diagnostic harness gained explicit plain-list/effort controls; production code/configuration was not changed in this follow-up. Its three containment/redaction/budget tests passed, and `git diff --check` passed. No further inference is planned for this follow-up.
