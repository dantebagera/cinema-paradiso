# IPTV focused TMDB verification and saved recheck

**Status** · Implemented and verified in isolation. Dante approved implementation with “go” after the proposal to focus TMDB lookup, recheck saved search-limit results using existing hints, and clarify the review message. Public search integration and live execution are outside this approval.

## Problem and decision

Lionz had 1,363 review rows with the search-limit reason. The strict search treated a full TMDB page as unfinished even when it had already found an exact candidate. The dry run recovered 9 of 20 deliberately selected search-limit rows with focused querying. That sample does not establish a catalog-wide recovery rate. A further 582 of those rows had been marked stale during the earlier catalog resume. Rechecking them requires fresh source evidence and the same verification used for other rows.

## Contracts affected and contract-change decision

| Existing contract | Implementation |
| --- | --- |
| Incomplete rival search stays in review. Release year, title, sequel, source facts and applicable locks must agree. | Collect candidates in the existing matcher using page metadata and bounded queries. Examine actual returned rivals. Treat unsearched relevant pages, omitted plausible rivals and incomplete hydration as incomplete evidence. Preserve the existing verifier. |
| Continue is explicit, bulk scope and request usage are durable, verified Film matches use existing automatic Apply. | Recheck is explicit and operates on a completed, compatible saved job. Freeze its search-limit subset and reuse fresh provider facts and saved title hints. Save per-source progress and use the existing verified Apply and receipt path. |
| Accepted matches and category rules are protected. | Only unresolved Film listings with saved evidence are eligible. Never recheck applied results. |

## Current design and ownership

Baseline is dirty `master` at `117526b`. Local port 5000 served PID 52396 and `index-hjeN8MRq.js`. The live Lionz completed job and projection both bind to generation 50. Tests use a dedicated temporary data root and build output.

| Owner | Work |
| --- | --- |
| `IPTVTMDBClient`, `bounded_search_candidates` and `IPTVMovieService.bulk_source_proposal` | Preserve legacy callers. Give strict automatic Film matching a paginated, year-aware search, and use the same entry point for the recheck. |
| `ai_job_continue`, `AIJobStore.continue_job`, `IPTVJob._run_bulk` | Admit an explicit `recheck_search_limits` Continue for the owned completed job. Persist target IDs and progress in the existing cursor and dispatch the same worker and Apply path. |
| `IPTVBulkMetadataJob`, `useAIJob` | Show a recheck count and action on the saved session and a separate progress indicator using `IPTVMetadataProgress`. Keep original whole-job progress and request usage visible. |

## Exact behavior contract

Search the listing year and adjacent years when the primary provider year is known. Check unfiltered candidates for regional dates and other rivals. Use actual TMDB page counts, a maximum of five pages per query and 29 search pages per source. Keep up to 20 plausible candidates and hydrate at most eight. Retain review when search or relevant verification cannot be completed within those bounds. Preserve no-year and existing historical recovery behavior. No public web search or inference is required for rechecks.

Start with a ready provider and unchanged job execution generation. Require the existing provider, account, permission, revision and request key. Historical hints are usable only if recorded title evidence still agrees with the current source. Recheck uses fresh source and match revisions, input facts and provider locks. Save each settled outcome with its cursor. Preserve unresolved evidence when the source is protected or the new search cannot verify a match. Verified results replace the unresolved row and use normal automatic Apply. A repeated POST cannot start a duplicate run. Pause, cancellation, restart and sync use the existing fences. If sync invalidates the active recheck, use the existing explicit Continue after projection to rebind pending work. Retryable TMDB failure preserves the original row and pauses at its checkpoint.

## Implementation sequence

1. Reproduce the false full-page review and real rival cases in strict matching tests. Extend the TMDB owner and fix the review message.
2. Add saved-run fixtures with retained results, stale proposals, lock and source changes, restart and guard cases. Connect the existing job, Apply, and progress owners.
3. Verify backend regressions and compiled desktop action, progress, history counts and empty state. Update the IPTV code map and decisions.

## Acceptance matrix

| Scenario | Expected result |
| --- | --- |
| Full single search page with unrelated rows | An otherwise verified exact match can pass. |
| Nearby or regional rival on a later checked page | Review or independently rule out the rival. |
| Omitted plausible rival or a relevant search cap | Stay in review. |
| Explicit saved recheck | Original job and selected titles stay attached, request count remains unchanged, only target rows are visited. |
| Stale saved proposal, changed title, lock, or accepted match | Fresh evidence required. Protected listings retain their saved result and catalog identity. |
| Pause, restart, failure, or sync | Checkpointed outcomes and receipts survive. No evidence from a superseded generation can write. |

## Verification and rollout

- The final 153-case backend selection passed across IPTV identity, recovery, bulk jobs, enrichment, and AI jobs and routes. An earlier 138-case run included the 40,000-proposal and 25,001-source scale fixtures. Both runs used isolated data roots.
- The isolated compiled desktop run passed all 15 cases in `tests/e2e/iptv-chatgpt-bulk.spec.js`. The saved recheck, catalog recovery and new automatic matching passed again against the final backend using the same isolated bundle.
- The final saved-job test pauses a queued recheck, verifies that Continue is held until the new catalog is prepared, and confirms rebind, unchanged request usage, one verified Apply, and preserved protected and changed-title outcomes.
- Read-only replay of the frozen Lionz sample through the implemented matcher verified 8 of 20 selected search-limit rows. All eight agreed with the saved leading identities. All ten conflict cases stayed in review. The previous exploratory pilot searched a narrower rival set and returned one additional search-limit verification. This sample does not establish accuracy or expected recovery for all 1,363 saved candidates.
- Live port 5000 still served PID 52396 and `index-hjeN8MRq.js`. The latest Lionz job had 5,186 saved outcomes, 1,363 recheck candidates, 869 applied matches and 53 ChatGPT requests used. The live recheck was never dispatched.

## Approved follow-up · Start a saved recheck after sync

Dante approved updating the existing Recheck button so the 1,363 saved Lionz candidates can be rechecked after sync with no additional ChatGPT requests. The completed session is bound to generation 50 and the prepared catalog is on 51. `IPTVBulkMetadataJob` and `AIJobStore.continue_job` currently block this case. The existing Continue contract for protecting results across generations still applies. No change to lookup, verification, permissions, or automatic Apply rules is required.

1. Extend the existing API and compiled desktop tests to start with a completed saved session and a newer projected catalog. The API must reject the same action before projection is ready and admit the identical request afterward. It must retain the original and applied results, freeze the saved recheck subset, preserve request usage, and keep old unapplied proposals fenced off.
2. Call the existing `_refresh_bulk_catalog` transaction when starting a recheck. Keep it responsible for provider readiness, stale proposal fencing, receipt reconciliation and execution generation. `IPTVJob._run_bulk` and `IPTVMovieService.recheck_bulk_search` already read fresh rows and reject changed, removed, matched and locked sources before using saved title hints. Existing revision, owner and request replay checks still apply.
3. Enable the existing button when the current catalog is prepared. Verify isolated backend admission, generation change and no-inference Apply, plus compiled desktop readiness, progress and completion. Live activation and dispatch remain separate actions.

**Verified** · The API regression initially returned 409 with the newer catalog fully prepared. After the fix it rejected the request only while preparation was pending, accepted the same request afterward, and passed a second sync across Pause and Continue. It preserved the applied result, fenced off the old unapplied proposal, and skipped the removed, changed and locked listings. The recheck applied one verified fixture without constructing a ChatGPT transport. All 153 selected Python tests and all 15 compiled offline desktop tests passed. The selected Python run omitted the two existing large stress fixtures.

Read-only Lionz inspection at generation 51 found all 1,363 saved hints still eligible, with 53 requests used and 869 applied matches on the saved session. This checks eligibility for TMDB verification. The live frontend still served `index-BIL_deZ4.js`, and no live recheck was started.

## Live Lionz recheck · 2026-11-14

Dante approved live activation and the TMDB-only recheck. On preflight, port 5000 already served the updated `index-BD_it945.js` and `IPTVWorkspace-BMk8w4Z3.js` from PID 52092, so another restart was unnecessary. CP admitted the 1,363 saved listings on catalog generation 51. The recheck completed at 14:49 Cairo time with 246 verified matches applied and 1,117 left in review. The 869 earlier matches retained their TMDB identities. All 246 new provider records and Apply receipts matched their saved TMDB IDs. The request counter remained at 53. [Live completion record](<C:/Users/dante/AppData/Local/CinemaParadiso/rollout-backups/lionz-tmdb-recheck-20261114-131011-7d5e077e/completion.json>)
