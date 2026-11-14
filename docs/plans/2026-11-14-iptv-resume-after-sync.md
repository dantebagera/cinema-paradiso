# Resume IPTV ChatGPT matching after catalog sync

**Status** · Implemented and verified in isolation on 2026-11-14. Dante asked CP to resume the 861 unfinished sources after sync without repeating sources it already checked, and to show the full preparation bar only in IPTV Metadata.

## Problem and decision

Lionz job `61733bc8…` stopped when projection invalidated generation 49. The job had saved 4,325 of 5,186 outcomes, including 358 applied matches, and used 44 of 780 approved requests. The refreshed Unmatched queue included all 861 unfinished sources as well as 3,967 sources with saved outcomes. Starting a new session from that queue would repeat completed work. The Maintenance launch card also showed progress through all 41,353 projected listings. The first-pass worker had 25 pending items separately.

The approved scope covers explicit Continue for first-pass bulk jobs with automatic Apply and the two IPTV desktop views. A completed outcome is the boundary for avoiding repeat work. For the 75 unfinished sources with a saved interpretation in this job, the original title input was not persisted alongside the reply. CP will recheck them using fresh evidence. Legacy jobs with a pinned candidate-recovery stage keep their current behavior. Live sync, Continue, service restart, and activation are separate actions.

## Contracts affected and contract-change decision

| Contract and source | Behavior to preserve | Owner and callers | Approved change |
| --- | --- | --- | --- |
| Saved scope and quota in the [bulk decisions](../second-brain/iptv.md#approved-bulk-matching-decisions) | Same job, original source keys, cumulative counts and request budget. Continue requires a click. | Existing Continue route, job store and Maintenance | Dante approved revalidating just the unfinished keys and running them against the newly prepared generation. |
| Verified Film Apply and catalogue safety in the [bulk decisions](../second-brain/iptv.md#approved-bulk-matching-decisions) | Existing verification, permission, generation, manual lock and Apply receipt checks. | Movie store, matching worker and proposal review | Historical results remain reviewable. Earlier unapplied proposals cannot write under the new generation. Reconcile any outstanding write receipts before switching. |
| Preparation bar in the [launch readiness plan](2026-11-06-iptv-bulk-launch-readiness.md) | Readiness still gates matching. ChatGPT progress stays in Maintenance. | `IPTVBulkMetadataJob`, `IPTVEnrichmentPanel` | Dante explicitly moved full provider preparation progress to IPTV → Metadata only. Desktop tests now assert that placement. |

## Current design and ownership

The baseline is dirty `master` at `117526b` with 169 tracked changes and 267 untracked files. The live instance observed on localhost:5000 used PID 49768, local `data`, and the `IPTVWorkspace-Cx-D6QsA.js` served chunk. Isolated checks use a separate data root and output bundle.

| Responsibility | Owner and call path | Existing behavior to preserve |
| --- | --- | --- |
| Continue | `useAIJob` → `ai_job_continue` → `AIJobStore.continue_job` → `IPTVJob` | Account, configuration, revision, request replay, single active job and budget checks. |
| Current catalogue | `IPTVMovieService` and `IPTVMovieStore` | Complete projection and current raw generation are required. The worker still checks generation before inference and writes. |
| Progress | `IPTVBulkMetadataJob` and `IPTVEnrichmentPanel` share `IPTVMetadataProgress` | Overall GPT and first-pass CP progress retain their existing scopes. |

## Exact behavior contract

### Frontend

Maintenance shows the saved job with its original overall progress and a **Resume N unfinished sources** button when catalog recovery is available. Readiness gates that action and the panel directs the user to IPTV Metadata while it waits. The Metadata page shows the existing cyan provider preparation bar in its own progress card above the status cards while projection is running. Its green first-pass bar continues to show pending CP work. No duplicate full preparation bar appears in Maintenance.

### Backend

The existing Continue endpoint accepts the current job revision and request key, plus the existing budget approval when applicable. CP checks readiness and selects eligible IDs from the original saved job with no outcome. Removed sources, sources with a manual match lock, already matched sources with current evidence and other out-of-queue leftovers get a review outcome with a reason and no model or TMDB work. Manual classification still follows the existing matching rules. CP atomically checkpoints the new execution generation and remaining work in the existing job, preserves original selection and receipts, and fences off historical proposals from Apply. Continue within the same generation uses the current checkpoint path. Another sync still stops processing against stale evidence. No schema migration is required.

## Implementation sequence

1. Cover a stale job with intermediate replies, completed rows and a changed catalogue in isolated tests.
2. Extend the existing Continue endpoint, job checkpoint and catalog eligibility lookup. Keep the existing Apply receipt and generation protections.
3. Move the shared bar to IPTV Metadata. Verify the Resume action, waiting state and full progress placement in the compiled desktop UI, and update the CP knowledge pages.

## Acceptance matrix

| Scenario | Expected result | Verification |
| --- | --- | --- |
| Lionz-shaped stale job | Same job and original total, only unfinished eligible IDs checked, earlier outcomes and spend retained | Isolated bulk worker and Continue endpoint |
| Provider still preparing or resumes during another sync | Continue waits or returns a readiness error. Worker rejects an invalidated generation | Isolated API and desktop |
| New out-of-scope rows, removed or locked original source | No model or TMDB work for those rows. Saved selection remains fixed | Isolated catalogue and worker |
| Old Apply or request replay | Receipts retained, old proposals cannot write under the new generation, replay cannot enqueue a second run | Isolated job and Apply tests |
| Same-generation Pause, restart or request approval | Uses saved checkpoint and existing allowance | Existing bulk regression tests |
| Preparation in progress | Full cyan bar only in IPTV Metadata. Maintenance shows readiness text and retains the GPT job bar | Compiled desktop |

## Verification and rollout

- **Backend** · The first broad run passed 124 tests across bulk matching, AI jobs and routes, and IPTV enrichment, UI contracts, catalog gates and availability. It included the 40,000-proposal and 25,001-source scale cases. The later 123-test run covered the new write-receipt test and omitted those two scale cases. The two new recovery cases and the manual-lock/category case passed again against the final eligibility rule.
- **Compiled desktop** · The isolated Vite build and all 14 cases in `tests/e2e/iptv-chatgpt-bulk.spec.js` passed via `tools/run_playwright_e2e.ps1 -AIProviderOffline`. The recovery and preparation placement cases passed again against the final backend. The first desktop run exposed the matching panel closing at completion of a short resumed job. The Resume action now keeps that panel selected.
- **Live read-only** · The final eligibility query recognized the saved Lionz job as resumable from generation 49 to 50 with 4,325 saved results, 358 applied matches, all 861 unfinished sources eligible, and 44 of 780 approved requests used. The live listener still served the earlier bundle from PID 49768. No live Resume or activation was performed.
