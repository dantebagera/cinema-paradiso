# IPTV first-pass continuation and Maintenance recovery

**Status** Implemented and verified in isolation on November 10, 2026. Dante approved fixing Continue and IPTV counts after resync, then moving leftovers to Maintenance with the same flow chart and GPT skills.

## Problem and decision

Lionz has 41,329 provider sources. The old evaluated count of 38,084 excludes 3,225 classification decisions sent to review, six protected manual matches, and 14 sources made pending by the last projection. The previous worker completed before that projection. Read-only classification of the pending rows yielded eight Sports and six classification review results. The reported live Resume failure has no saved error. The process launcher discards startup output and does not report a child that exits before recording its own state. Simultaneous launch requests can also replace a worker lease before the first child reads it.

## Contracts affected and contract-change decision

| Contract | Observable behavior | Approval |
| --- | --- | --- |
| First pass lives in IPTV | Resync projects the catalog. When eligible work remains, IPTV Metadata shows the exact pending count and offers explicit Continue. A completed pass includes reviewed, unmatched, failed, and protected decisions in the handled count. Accepted matches have their own count. | Approved November 10 |
| Existing worker lifecycle | Preserve per-provider consent, technical backoff, manual locks, and explicit resumption. Only one launch may own a provider lease at a time. An early child failure leaves a visible error and an actionable Continue. | Bug fix within approval |
| GPT recovery lives in Maintenance | Move the existing review, selection, and job UI to Maintenance → IPTV. Default review scope includes settled unmatched, uncertain identity, and uncertain classification. Existing saved jobs retain their selection, prompts, skills, verification, budgets, and Apply behavior. | Approved November 10 |

## Current design and ownership

The current workspace is `master` at `be511f9` with 397 dirty paths. The live HTTP listener uses PID 3008, the workspace provider data, and `index-B-nPNaZj.js`. Leave live data and activation outside this implementation.

| Responsibility | Owner and implementation |
| --- | --- |
| Startup and resume | Keep `IPTVMovieService` and `IPTVMovieStore` as owners. Serialize the local lease and launch decision. Report failed spawn and premature exit using the existing durable worker error field. Continue after a completed run uses the full worker budget. |
| Progress | Use `automatic_remaining` from the same transactional snapshot as `sources`. Display handled as total minus pending and keep identity outcomes separate. Resync and projection must complete before enabling controls. |
| Review and job controls | Render the existing provider workspace's Catalog review and Bulk matching surfaces inside the selected Maintenance provider. Reuse its review cards, pagination, job widgets and match dialog. Remove the duplicate first-pass dashboard from Maintenance and keep its repair actions. |
| Recovery queue | Share the opt-in leftover filter between `review_queue` and filtered selection resolution. Keep legacy selection behavior and saved jobs compatible. |

## Exact behavior contract

IPTV Metadata shows the first-pass progress, projection state, and its worker controls. While resync or projection is running, starting a new pass is gated. Once it completes, a completed worker with pending sources displays Ready to continue. Settled misses do not re-enter routine work on unchanged refresh. Completed with zero pending sources can coexist with unmatched and classification review results. Maintenance shows the selected provider's review and existing job controls. Move the full job UI without changing the AI engine or saved job APIs.

## Implementation sequence

1. Add regressions for child launch failures, repeat Continue, post-resync work and separation of handled/pending counts.
2. Correct the existing worker start/resume and status paths, then verify the worker against isolated provider fixtures.
3. Add a settled-leftovers query shared by displayed and submitted selections. Move the existing review and bulk surface to Maintenance and keep repair tools separate.
4. Run isolated Python suites and compiled desktop tests. Verify that the current live process still serves the previous build.

## Acceptance matrix

| Scenario | Exact expected result |
| --- | --- |
| Lionz resync adds a movie after completion | Continue appears once projection is ready and processes the newly eligible source |
| Prior pass leaves unmatched and uncertain sources | Pending shows only automatic work. Maintenance counts and sends settled leftovers |
| Continue pressed concurrently | Both requests observe one worker lease and one spawn |
| Child exits before saving an outcome | Current lease reports a startup or unexpected exit error and can be resumed |
| Last projection batch commits during a status read | Pending counts and projection come from the same SQLite snapshot |
| Windows worker exits with a scheduler marker left behind | Continue can reclaim the dead worker's slot without signaling a live process |
| Switch providers or return to Maintenance | Review and launch use current provider readiness. Saved bulk jobs reopen through existing endpoints |
| No pending work, existing accepted/locked identities | First pass is complete and existing match decisions remain protected |

## Verification and rollout

Run focused enrichment and review tests, broader IPTV backend suites with isolated data, and the compiled desktop bulk suite through `tools/run_playwright_e2e.ps1 -AIProviderOffline`. Verify navigation, exact displayed counts, resync readiness, existing launch and Apply, and no duplicate controls. Live data writes, server restart, and catalog jobs require separate authorization.

- Baseline Python verification passed 36 enrichment and UI tests. Regression tests reproduced an uncaught process launch error, a worker that stayed Starting after an early exit, and a completed diagnostic run carrying its old cap into Continue. Additional tests cover concurrent Continue and scoped leftover selection.
- Code review identified a race between the worker summary and projection reads, and a Windows scheduler check that reported an exited process as alive. Both failures reproduced in regression tests. The status now uses a single SQLite snapshot and the scheduler reuses the Windows-safe process check already used by the AI job store.
- Applying the candidate count and queue queries to the live Lionz database read-only returned 41,315 of 41,329 handled and 14 first-pass pending. Maintenance totals were 2,033 unmatched, 979 uncertain matches, and 3,225 classification review entries.
- Final isolated Python verification passed 156 tests across `test_iptv_movie_enrichment`, `test_iptv_movie_ui`, `test_iptv_movie_gates_0_5`, `test_iptv_provider_manager`, `test_iptv_routes`, `test_iptv_service`, `test_iptv_bulk_identity`, `test_iptv_candidate_recovery`, and `test_ai_jobs`.
- The compiled offline desktop run passed all 12 tests in `tests/e2e/iptv-chatgpt-bulk.spec.js` using `index-CmT9ryVr.js`. The desktop first-pass and Maintenance review screens were checked at 1600 × 1000. Tests covered the resync state, pending counts, Continue, worker-error display, provider switching, preparation refresh, and existing GPT job launch, reopening, and Apply.
- The live listener remained on PID 3008 and served the prior `index-B-nPNaZj.js` bundle.
- The reported historical Lionz failure has no retained startup error. The isolated tests verify the failure paths above and the resync-to-Continue flow. They do not identify the historical failure or provide a live Lionz run time.
