# Exact-prompt comparison: plain message versus CP request

2026-11-03. Authorized by Dante: “run that comparison with my exact prompt and the same model, repeat it a few times and show me where cp is adding time”. Diagnostic-only: no product owner, settings, catalogue or running-app change.

## Result

These three pairs do not demonstrate a consistent CP penalty in the initial GPT HTTP response. Plain mean15.262435s, CP mean14.189650s; plain median15.517039s, CP median14.605366s. This does not prove CP prompts are intrinsically faster: the sample is small and provider/network conditions were not controllable. It also does not reproduce a complete50-title response in6seconds.

| Pair | Plain full initial HTTP response | CP full initial HTTP response | CP minus plain | Complete CP workflow |
|---|---:|---:|---:|---:|
|1|15.517039s|10.915577s|-4.601462s|33.249252s|
|2|16.133276s|17.048007s|+0.914731s|34.460207s|
|3|14.136991s|14.605366s|+0.468375s|27.841832s|

All six initial responses returned50 suggestions. Plain runs produce unverified names/years; CP runs validate the candidates with TMDB. Each CP run ultimately returned50 distinct verified cards and used one extra GPT request for genuine missing results. There were no failed trials, HTTP retries, structure repairs or silent trial replacements. Total actual GPT calls:nine (six initial requests plus three top-ups).

## Where CP adds elapsed time

The mean complete CP workflow was31.850430s. Its additive phases were:

| Phase | Mean seconds | What is included |
|---|---:|---|
| Initial GPT stage |14.229491|Complete first HTTP response plus local account/slot/transport handling|
| Replacement GPT stage |5.954107|One additional request per run after3/5/3 rejected candidates|
| TMDB matching/validation/persistence |10.946905|Four bounded workers; all candidate eligibility checks and final result saving|
| Other CP preparation/state handling |0.719927|Including supplied filter context fetch and local scope/state work|
| **Complete CP workflow** |**31.850430**|Backend-ready terminal result; browser paint excluded|

The direct initial local wrapper cost in the CP runs was0.040927s,0.044733s and0.033863s (mean0.039841s), calculated as complete GPT-stage minus complete HTTP duration. The first plain run had a separate2.891258s account-access span; later account-access spans in all runs were about0.001s. Its cause was not instrumented below that owner, so this is not labelled CPU, disk, login-refresh or server time. The HTTP comparison excludes that local account delay consistently on both sides.

The first raw text arrived before the entire list was complete:

| Pair | Plain first text after HTTP start | CP first text after HTTP start | First saved CP card after workflow start |
|---|---:|---:|---:|
|1|6.197960s|2.951389s|12.286565s|
|2|12.284486s|10.496337s|18.087412s|
|3|4.228230s|4.017392s|15.636004s|

CP waits for the validated complete response before starting matching. First-text time is not complete-list time. The earlier chat marker timings excluded final response delivery and are not a valid comparator.

## Request size and observed variation

Plain:63 input tokens,278 input JSON bytes,0 instruction bytes,365 total payload bytes. CP:7137 input tokens,21225 input JSON bytes,2502 instruction bytes,1406 tool-definition bytes,25299 total payload bytes. CP sends current requirements, the full controlled genre/language/country context, conversation fields, format instructions and entity/handoff tool definitions. The original prompt appears inside the CP context envelope unchanged. No full payload or private account data was logged; byte counts and public usage metrics were recorded at the outgoing HTTP boundary.

CP therefore sends roughly113times the input tokens. That is overhead in the request, but this experiment does not establish it as a measured time penalty. All six first responses reported0cached input tokens. Plain total output tokens (including reasoning) were493,689,471; CP were773,969,623. Provider-reported reasoning tokens were45/250/34 for plain and18/227/18 for CP. Output format and reasoning varied; the trace cannot assign server-compute seconds or distinguish provider queueing from networking. Reducing context remains a possible controlled experiment, not an established explanation for the previous6second timing difference.

## Verification rejections and top-ups

| CP run | Initial suggestions | Replacements requested | TMDB HTTP reads | Matching wall time |
|---|---:|---:|---:|---:|
|1|50|3|144|14.658775s|
|2|50|5|159|9.847462s|
|3|50|3|144|8.334477s|

Rejected supplied titles included The Invisible Guest, Coherence and Frailty in all three runs; the second also could not accept Perfect Blue and Audition. Coherence/Frailty eligibility traces referenced unresolved provider records, including a resolved record titled Temptation's Hour for the supplied Frailty candidate; Temptation's Hour was not a GPT suggestion. These observations identify the matching/retrieval pipeline as the next investigation target. They are not evidence that GPT invented those rejected titles, or permission to weaken identity/eligibility rules. Failed candidates were replaced, never silently accepted. Raw traces record exact identity versus eligibility outcomes.

## Method and boundaries

- Exact user prompt, including original spelling and newline:

```text
i need you to lit 50 movies with very twisted story you wont expect the ending
your responce should be a list of movies names and years , no any other details , dont seek more info , dont reply by paragarph or any way of responce  only the list
```

- Same configured `gpt-6.1-sol`, selected CP account, official public OAuth Responses endpoint, ChatGPTTransport/PublicOpenAIHTTP connection code, default reasoning (no effort override). Each request opens its own HTTPS socket through that same transport; this was not reuse of one TCP connection.
- Sequential order:plain1,CP1,plain2,CP2,plain3,CP3. Fresh child process, isolated job/session and TMDB cache per run. No test/build workload ran concurrently with captures. The same account owner may refresh its token normally; credentials are never copied or logged.
- Plain arm:exact message, empty instructions, no tools, one permitted actual inference attempt. CP arm:actual Recommender-generated input and actual matching/eligibility/persistence; at most3 actual attempts and180seconds per run. CP generation comparison uses its FIRST HTTP response only; replacement requests and TMDB work are reported separately.
- Clock:monotonic perf_counter. First text means first nonempty response.output_text.delta, not first arbitrary stream bytes or reasoning item. HTTP time covers complete stream receipt; it includes networking/server waiting and is not pure model compute time. Complete GPT-stage includes account access and slot acquire/release as separate child spans. Parent/child overlapping times are not double-counted.
- Runtime baseline:master HEADbe511f98846a67a182e5b371ad087938e9344362; dirty checkout preserved. Production PID16180/port5000 and served dist remain unchanged. This measures the current changed source in isolation; production still has not loaded it through a restart.
- Diagnostic-only harness changes record first actual text, payload byte counts and public token/cache/reasoning details, and retain the plain candidate output. No product source changes. Five timing-harness tests passed0.005s after captures; all six real captures exercised the instrumentation. This is not a fresh claim about the previous122-test application suite.

## Interpretation

The earlier suggestion that CP's extra context explains roughly6seconds of additional generation latency is not supported by these repeated measurements. The confirmed additional waiting is matching/validation/persistence plus one replacement request. A6second complete-list target was not achieved by the plain baseline on this API/account/model during these samples. The website comparison remains unresolved because its actual model, request context and server conditions are not established.

Official measurement context:[OpenAI latency guidance](https://developers.openai.com/api/docs/guides/latency-optimization) distinguishes input processing, output generation, request count and application workflow. The numerical findings above come from the local raw captures, not that documentation.

All trial summaries, public movie outputs, raw redacted traces and logs are retained beside [measurements.json](measurements.json). Nothing was discarded from the stated comparison.
