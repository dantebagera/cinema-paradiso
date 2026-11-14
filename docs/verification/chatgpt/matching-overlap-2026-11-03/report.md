# Pick My Movie matching correction and streaming overlap

2026-11-03. Implemented and tested in isolation. No production restart, model/settings change, catalogue write, commit or release.

## Observed result

Three fresh real-provider runs of Dante's exact prompt, same selected CP account and configured `gpt-6.1-sol`:

| Run | Complete GPT HTTP | CP request handling | Residual matching/save after GPT | Other preparation/state | Full workflow | Verified cards | GPT requests |
|---|---:|---:|---:|---:|---:|---:|---:|
|1|16.128265s|2.941511s|0.451705s|0.855462s|20.376943s|50|1|
|2|14.635040s|5.895286s|0.417129s|0.678009s|21.625464s|50|1|
|3|20.194439s|0.048689s|0.418062s|0.710273s|21.371463s|50|1|

Mean full time:**21.124623s**, versus **31.850430s** in the immediately preceding three CP runs: an observed **33.68% reduction**. This is not a fixed latency guarantee or a perfectly controlled server benchmark: GPT HTTP itself averaged16.985915s here versus14.189650s previously. First-card times here were19.943504s,21.223414s and20.969104s; these samples do not demonstrate improved first-card latency. Full completion improved and every run used only the initial GPT response.

## Overlapping work and actual timings

The measured TMDB HTTP active wall time averaged8.198398s; **7.552849s occurred while the GPT HTTP stream was still active**. Do not add that overlap to GPT time. Only **0.428965s** remained for matching/eligibility/persistence after the complete GPT stage, versus10.946905s serial matching previously. The previous three runs also needed one replacement GPT request each (mean5.954107s); none was needed in these three runs.

The exclusive additive clock is: complete GPT stage (HTTP plus account/slot handling) + residual matching/validation/save + other preparation/state = full workflow. `tmdb_http_active_seconds` merges concurrent request intervals; `gpt_tmdb_overlap_seconds` intersects that union with GPT HTTP intervals. `matching_after_gpt_seconds` explicitly replaces the old diagnostic `tmdb_matching_seconds` name; historical captures are unchanged. Backend-ready time includes worker cleanup and excludes startup/import and browser paint.

TMDB reads were127,119,131 (mean125.667), versus144,159,144 (mean149) in the preceding sample. Output film choices vary across GPT responses, so the per-run count difference is descriptive. The fixed five-film reproduction below isolates the unnecessary-read correction directly.

## Confirmed matching defect and reusable owner rule

The shared search candidate conversion passed the requested title/year as fallbacks to movie-card normalization. An undated source record could therefore inherit the request year and become an apparent exact identity. Actual reproduced examples:

- Frailty2001 was wrongly associated with undated TMDB record1387467 (Temptation's Hour, aliasFrailty), then rejected for unknown eligibility.
- Coherence2013 could select undated short992200 instead of actual film220289.
- Audition1999 could select undated short1492357.
- The Invisible Guest2016 and Perfect Blue1997 became ambiguous among additional unconstrained title matches.

The correct films' primary dates are one year later, while TMDB's detailed release histories contain the requested years. Five read-only detail responses proved the supplied years for the actual IDs. The fix uses that evidence; it does not copy requested years into provider metadata or change confidence thresholds.

**Owner rule:** query hints are not provider facts. The shared search adapter now preserves a missing title/year as missing. The existing identity ranker remains authoritative. F1 can avoid unconstrained/alias searches only after that ranker accepts the year-filtered candidate set, the actual title/original title matches, a real primary date exists, and a same-ID detailed release history proves the requested near-year date. Canonical card years remain TMDB primary years. Actual objective filters still run through AICatalog and can reject a film based on the agreed primary-date filter semantics. When proof is missing or real identities remain ambiguous, deeper matching/rejection remains.

Same-ID detail data fetched for this proof is reused in final resolution. The fixed five-film replay accepted all five as eligible with **10reads (two each), versus28reads before**. Files:matching-before.json,provider-release-proof.json,matching-after.json. No motivating movie title or ID is hardcoded into product rules.

## Streaming implementation and acceptance boundaries

- ChatGPTTransport has an optional output-text-delta observer; request payloads, selected model/account, retry/deadline rules and terminal/tool validation remain.
- RecommendationReader decodes complete objects in the TOP-LEVEL recommendations array across arbitrary JSON/Unicode/escape boundaries. Nested keys and quoted text cannot masquerade as candidates. Its speculative buffer cap is64KiB; final complete-response parsing is unchanged.
- CandidateBatch replaces the old post-response-only executor. It owns at mostfour workers, at most50 speculative title/year keys, deduplicated reads and final-only fallback lookahead. Final output is authoritative; unused speculative futures are cancelled. Failed/incomplete/malformed responses, repairs, cancellation and handoffs close the batch without promoting speculative cards.
- No card is saved before complete response/schema/scope validation. Account permission is rechecked after the response and before each result write. Existing eligibility, exclusions, identity deduplication, exact positive targets, paging, follow-ups, Continue and visible provider failures remain in their owners. No alternate recommender/ranker or speculative publication path was added.
- The common Movie identity adapter also stops inventing missing facts for Smart Match/verification callers; relevant shared-owner regressions passed. Ollama prompts, wire requests, settings/limits and independent inference owners were not edited; frozen preservation checks pass.

## Remaining intermittent local delay

The second run recorded **5.850699s acquiring the request slot before HTTP started**, while the actual GPT HTTP was14.635040s. The first run recorded about2.9s in account access. These are included in the table's CP request handling, not mislabelled as GPT computation. The third run's request handling was0.048689s.

A separate synthetic lease-only probe performed six acquire/release pairs in an isolated temporary database. Subsequent acquires/releases were around0.01s, so it did not reproduce the5.85s stall. Its connect/execute/commit/close timings are retained in lease-probe.json. The cause remains unresolved. No database durability, locking, security software, storage or system setting was changed based on a guess.

## Exact request and capture protocol

```text
i need you to lit 50 movies with very twisted story you wont expect the ending
your responce should be a list of movies names and years , no any other details , dont seek more info , dont reply by paragarph or any way of responce  only the list
```

Explicit target50. Same existing account/model/default effort; fresh process, diagnostic job/session, empty TMDB memory cache each run. Existing protected credential owner used without copying/logging credentials; normal token refresh may occur. At most3 actual inference attempts and180seconds per capture, but all three completed with one request, no retries, no structure repair and50verified distinct cards. No test/build workload ran concurrently. Total GPT inference usage for this task:three actual calls. Matching investigations used28before+5release-proof+10after=43additional public TMDB reads; no inference. All raw captures retained; no trial was replaced or hidden.

## Verification and source/runtime status

- Pre-edit baseline:**112 passed in28.657s**. Date/title-provenance and release-history regressions failed before the fix. Then96 shared matching/identity/Ollama-preservation checks passed7.470s, and36 initial transport/stream/recommendation tests passed27.637s.
- Permission-loss-during-lookup and queued-cancellation tests failed before the corresponding hardening. Final broader suite:**235 passed in83.314s** in unique OS-temp test mode with embedded qBittorrent and blocked external fixture connections. Includes matching/remakes/history-proof absence, parser escapes/caps, real pre-terminal lookup barriers, changed final candidates, failed terminal, cancellation, permission loss, exact targets/follow-ups, F1–F5 matrix and frozen Ollama preservation. Logs are retained. This is the relevant suite, not a claim that the entire repository suite is green.
- Fresh production build to OS temp:**2.47s**. Compiled desktop:**4 passed in32.7s**, testing120-card paging/restoration at1600/1280px, visible failures/manual switching, budget pause/Continue/cancel. HTTP fixture now emits real text deltas so it exercises the observer path. No frontend layout/JSX/CSS changed. Screenshots retained.
- Fresh read-only review against the pre-task byte baseline found no actionable correctness findings. No code changed after this reviewed/tested source was frozen for the real captures.
- Checkoutmaster HEADbe511f98846a67a182e5b371ad087938e9344362, extensive pre-existing dirty work preserved. Pre-task source backup/hash root:cp-overlap-work-z3h8cgh_. Full capture source hashes are in capture-manifest.json. App changes are limited to the four named candidate/detail/resolver owners; no unrelated source changes reverted.
- Configuration and production dist hashes remain unchanged. Production Python PID16180/port5000 predates these changes; **production has not been restarted and has not loaded the corrected backend**. Source-only implementation, isolated regression, compiled fixture behavior and real-provider backend captures are distinct evidence.

## Contract comparison

The implemented flow preserves final-only publication, objective filters, genuine ambiguity/rejections and exact targets; it overlaps read-only lookup work and corrects false year evidence. All three motivating real runs reach50with one model response. The captured5.85s local request-slot stall and provider-response variation remain limitations; no claim of universal sub20s latency or improved first-card timing is made.

References for protocol semantics:[OpenAI streaming responses](https://developers.openai.com/api/docs/guides/streaming-responses),[TMDB movie search](https://developer.themoviedb.org/reference/search-movie). Numerical claims come from local source-bound traces, not documentation. See measurements.json and all three overlap-final-* summary/trace/log files.
