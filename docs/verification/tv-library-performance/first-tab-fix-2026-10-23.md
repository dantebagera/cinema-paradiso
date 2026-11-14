# First TV-tab delay: confirmed causes and source fix

Source implementation and bounded verification completed on 2026-10-23. This is not live activation. Existing backend PID31584 and production dist remain unchanged during this continuation. No production catalog/configuration/media edits, live scans/downloads/imports, real playback, commit or publication were performed by these checks. Disposable fixtures intentionally write isolated test data. Normal app background activity remains outside any zero-write claim.

## Confirmed causes and changes

MediaWorkspace placed the first TV mount behind an additional lazy code import and Suspense boundary. The browser fetched the small TV module in about10ms but waited about300ms after module readiness before starting TV requests. React's production fallback scheduling contains this300ms delay. MediaWorkspace now imports the same TV component eagerly while retaining its selection-gated mount, hidden retained panels, session selection, navigation callbacks and scroll state. Importing code does not fetch TV data.

TVSearch.discover acquired compact local facts, released their context, then independently read complete episode/version/coverage facts again for each owned card. It now passes one request-local context through the existing local_rows and detail owners. No cross-request cache, payload thinning, paging/provider concurrency change or second business-rule implementation was added. Filter scan state does not retain this context; a later request observes a newly missing file.

Reusable owner rule: code readiness belongs to the containing workspace; data remains first-selection gated. Within one TV search, local filtering and owned-card display must use one fresh fact snapshot through the existing read-model owner, and release it before returning control to the caller.

## Browser evidence

Same running backend; fresh frontend origins5128 before and5129 after. Candidate frontend served only from an isolated compiled directory. Neither observation is a fresh backend-start measurement. Timings are individual instrumented observations, not universal latency guarantees. Page timestamps, in milliseconds:

| Library event | Before | Candidate |
| --- | ---: | ---: |
| Actual TV click |6873.8|10520.6|
| Catalog fetch begins |7285.2|10635.1|
| Response headers |8035.0|11423.0|
| Body consumed |8039.7|11428.3|
|33 rendered cards, four in viewport |8086.6|11493.2|
| Click to fetch |411.4|114.5|
| Click to rendered cards |1212.8|972.6|

Both responses contained2616826 decoded characters; server716.0/748.6ms. This isolates the frontend improvement from backend speed variation. JSON parsing was about4ms in the baseline, so payload parsing was not the principal first-tab cause.

Discover rendered40 cards in both observations. Its initial server3045.2/1575.4ms varied while the backend implementation remained unchanged; **that difference is not evidence of the backend fix's speedup**. Provider requests and subsequent full-page enrichment remain, with unchanged product behavior. Earlier enrichment batches were about1.9s each concurrently. These changes do not make all cold provider/artwork work instantaneous.

The actual Library Movie→TV return produced no additional catalog request. The two candidate catalog requests were one Library first selection and one Discover first selection. Earlier proxy startup backlog makes initial Movie bundle timing unsuitable for a fair Movie-versus-TV comparison.

## Backend evidence

SQLite mode=ro and query_only, no app import/store constructor/migration: fixed provider summaries for40 owned cards on the actual catalog produced identical complete serialized responses, SHA256 `987e5f4ebb67a0a3114d63e61d31dd632d6c44b808bd789be34737c77b372eb3`.

| Local fact work | Before | Candidate |
| --- | ---: | ---: |
| Connections |201|1|
| SELECTs |449|13|
| Distinct physical paths checked |1193|1193|
| Maximum checks per path |2|1|
| One service observation, ms |617.9|230.8|

This excludes provider latency, routing and browser work; baseline ran first, so do not present it as an end-to-end percentage improvement. A separate candidate read-only real-provider profile returned40 cards in889.4ms; owned-card detail calls were0.03–1.11ms. Provider response identities/timings varied from the earlier profile.

## Regression and memory checks

Evidence root: `C:\Users\dante\AppData\Local\Temp\cp-tv-first-tab-fix-317228b6-e92c-4665-97b4-028cfb3c2882`.

- Focused Python:51 passed. Broader Python:51 passed, overlapping coverage; Node TV:3 passed. The strengthened Discover case separately passed exact fields/order/counts, one connection, bounded queries, fresh missing-file availability and context collection even with retained filtered scan state.
- Complete named desktop gate `compiled-desktop-green`:45 passed, zero failures/skips/retries, one worker, including the original first-switch test and existing44 desktop cases.
- Final corrected first-switch checks:2 passed, one fresh browser page each for Library and Discover; actual browser click→fetch5ms each under the unchanged400ms limit, no TV request before selection, exactly one catalog request after cached returns. Reused the unchanged compiled application; no production build/install.
- **There was no final successful46-case full run.** The expanded full attempt stopped after20 passed, one failed and25 unrun because the disposable Movie Discover endpoint returned400 without a provider key. The corrected focused test supplies only an empty Movie response; TV uses the real fixture backend. Existing44 product cases passed in the earlier complete45-case gate against the same application implementation.
- Initial Discover RED:31 connections/85 queries for six owned cards. Initial frontend RED:668ms under a600ms delayed TV chunk. A later controller-timed attempt failed774ms; its trace proves744.5ms was pre-click stability waiting. Chromium network timing was unavailable at the request event in the next attempt and failed the validity assertion. Final timestamps are both taken in Chromium at capture-phase click and fetch invocation, with actual outgoing request awaited. Bounds were not raised. All failed logs/traces remain separate.
- One focused run initially stopped on a missing baseline repository file. The corrected run used the original preserved full-read baseline. No product assertion was removed.

Synthetic Discover memory is a **service-only** four-observation comparison, distinct from the historical full-route Library protocol. Fresh process per observation, imports/fixture preparation outside tracing, complete serialization/release inside, no late imports, matching complete outputs, every request context collected. Python-managed bytes, not RSS:

| Series | Baseline peak | Candidate peak | Baseline residual | Candidate residual |
| --- | ---: | ---: | ---: | ---: |
|6|983365|290039|22146|11762|
|24|1302003|1044106|33864|13074|

Both pass baseline + max(1MiB,10%) peak and +256KiB residual bounds. No production memory-scaling guarantee follows from these small fixtures.

Continuation checks consumed287.117 seconds of the distinct300-second cap, including failures and56.412 seconds for the browser capture; historical580.590/600 ledger remains untouched. Temporary files remain below1GiB. No further tests are scheduled under this cap. Owned fixture/proxy servers and browser tabs were closed; the original live backend stays running. Production main bundle hash still matches the pre-fix compiled baseline; activating both changes requires the normal frontend build and backend startup later.
