# IPTV bulk redesign verification

## Source and live baseline

- Source implementation uses the approved dirty Cinema Paradiso checkout on `master` at `be511f9`. The approval is recorded in the [implementation plan](../../../plans/2026-11-05-iptv-bulk-launch-apply-status.md).
- The live Python process PID 13348 on port 5000 served `index-BT2aYlrz.js` from the production bundle. Its data root was the checkout’s `data` directory.
- A read-only status request confirmed the live job was paused at 3,741 of 6,413 sources, with 39 of 100 approved requests used and 2,301 verified proposals. A read-only SQLite query counted 20 existing Apply receipts.
- All behavior verification used temporary data and bundles. Production activation and live runtime performance qualification remain separate.

## Observed contracts

| Area | Isolated result |
| --- | --- |
| Launch allowance | The desktop displayed 65 first-pass requests for 6,413 sources at 100 titles per request and 129 at 50. The route persisted the approved size and ceiling. Route tests rejected invalid sizes, a stale count, and a ceiling above 10,000. |
| Saved scan and continuation | The legacy desktop fixture restored 3,741 sources, 39 used requests, and the original 100-call approval. Runner tests retained a partial window and recorded interpretations across interruption, checked that an ordinary Resume added zero calls, and required the calculated extra allowance after budget exhaustion. |
| Status recovery | The compiled desktop recovered the latest-job read, a dropped active read, and a hung read. It retained the last count and disabled Pause during reconnect. It restored the Paused state and working Resume control, discarded a late response after switching providers, and recovered a newly accepted Start whose reply was dropped without sending another Start. |
| Job-wide Apply | One confirmation with proposal review closed covered 2,281 verified matches across the saved job. The request carried the revision, count, and request key. It carried zero proposal IDs. Duplicate confirmation returned the same operation ID. The foreign-provider request was rejected. |
| Saved Apply results | The desktop showed zero awaiting Apply and 2,301 applied, including the 20 earlier receipts. It showed 1,440 unresolved rows separately. The API verified the final match in the provider store. A separate desktop scenario applied one selected Film match and 20 selected classifications through the native panels. |
| Apply recovery and safety | A simulated exit after provider commit and before the AI-store checkpoint recovered the existing provider receipt without a second write. Tests also verified Stop preserves the committed row and leaves unprocessed rows pending, projection blocks stale writes, new locks remain intact, and Retry includes transient failures only. |
| Layout and legacy behavior | Catalog review rendered while facets and readiness were delayed, ignored the superseded queue read, and requested only the debounced title. The desktop checked separate IPTV Settings and Maintenance, explicit Play lookup, the 5,000-source guard for standard actions, legacy AI Continue, Movie and TV flows, and Ollama fallback. |

## Verification

- Baseline focused Python suite passed all 77 tests before source changes.
- The focused AI job, routes, transport, and IPTV enrichment suite passed 68 tests. The bulk suite passed 16 tests excluding the separate scale case. The final receipt, Stop, retry, and IPTV UI checks passed 12 tests with the final Apply implementation.
- The final broader AI, ChatGPT, and IPTV run passed 345 tests. This count excludes the 17 separately run bulk tests, for 362 distinct Python tests across those runs.
- The final 40,000-proposal test passed in 254.189 seconds including fixture setup. The writer used 400 chunks of 100 rows and one final empty read. Provider state held 39,997 newly applied matches across two TMDB identities and three preserved manual locks. Pending was empty, with zero skipped or failed writes. This run used offline TMDB fixtures.
- JavaScript passed all 11 tests across IPTV filters and sync policy, AI provider client, and Pick status.
- The offline compiled desktop suite passed all 21 scenarios in `ai-provider.spec.js` and `iptv-chatgpt-bulk.spec.js`. The two targeted IPTV scenarios in `app-smoke.spec.js` passed separately. Both final compiled runs used `index-BR6h-hEp.js`.
- A first broader Python run had a Windows loopback connection abort in the ChatGPT login preflight test. The affected test passed by itself and in the final broader run.

## Desktop captures

- Previous compiled bundle with an isolated copy of the paused-job fixture. [Metadata](iptv-metadata-before.png) · [Catalog queue](iptv-catalog-before.png)
- Current compiled bundle. [Start allowance](iptv-bulk-start.png) · [Paused job with Apply available](iptv-bulk-paused.png) · [Apply result and optional review](iptv-bulk-applied.png)
- Current destinations. [Catalog review](iptv-catalog-review.png) · [IPTV Provider Settings](iptv-metadata-settings.png) · [IPTV Maintenance](iptv-maintenance.png)
