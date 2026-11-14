# Put first-pass enrichment in IPTV

**Status** Dante approved the first step of the agreed flow with “for now lets fix first go” on 2026-11-08. This covers source changes and isolated verification.

## Problem and decision

Maintenance currently owns the controls for ordinary IPTV enrichment. IPTV Metadata opens to a review surface. The automatic worker already saves a terminal result for an unmatched or ambiguous source. Provider projection preserves those decisions even when the listing evidence changes.

Place Enrich Metadata first under IPTV Metadata and use the existing deterministic worker. An unchanged terminal miss remains available for later review. A changed unresolved listing can receive one new pass. Keep technical retry and repair controls in Maintenance. The later move of the AI and manual exception workflow is a separate step.

## Contracts affected and contract-change decision

| Contract | Decision |
| --- | --- |
| Location of routine enrichment | Dante approved Enrich Metadata in IPTV as step one. Remove the routine controls from Maintenance and reuse their existing worker action path. |
| One pass per new or materially changed unresolved source | A settled miss remains terminal on an unchanged refresh. A change in provider title, year, playlist context, or a newly supplied positive provider TMDB ID makes the unresolved source eligible for reevaluation. |
| Accepted identities, manual locks, consent, and technical backoff | Preserve accepted and manually locked identities, explicit per-provider consent, visible continuation, provider isolation, and existing technical retry/backoff. The approved one-pass rule concerns settled identity outcomes. |

## Current design and ownership

The workspace is dirty `master` at `be511f98846a67a182e5b371ad087938e9344362` with 389 changed paths before this plan. The live process uses the workspace data root, PID 44016, and `index-gmdWYNEr.js`. Baseline `test_iptv_movie_enrichment` and `test_iptv_movie_ui` passed 33 tests.

| Responsibility | Owner and implementation |
| --- | --- |
| Enrichment screen | Move the existing routine controls and provider progress to an Enrich Metadata pane in `IPTVWorkspace.jsx`. Use the current subtab layout and provider selection. Keep an active or resumable bulk job accessible. |
| Shared worker state | Use the existing `useIPTVMovieStatus` hook to issue provider-scoped actions and poll the same worker in IPTV and Maintenance. Reuse the same progress summary where both surfaces show it. |
| Provider evidence changes | In `IPTVMovieStore.project_source_batch`, compare source evidence in the existing projection transaction. Reset only changed unresolved decisions and their completed queue entries. Apply classification pending only where unlocked. Clear stale cached identity details when listing identity changes. |
| Exception controls | Keep Retry failures, stale re-evaluation, diagnostics, rebuild preview and grouping repairs in `IPTVMaintenance.jsx`. |

## Exact behavior contract

- Enrich Metadata is the first subtab and the default when there is no active or resumable bulk job. Opening it, syncing, or switching providers issues no enrichment start. A click starts or continues using existing provider consent and restart acknowledgement. Pause and Cancel future work operate on that provider's existing worker.
- Display automatic work and classification review as separate counts. Preserve provider sync, projection, and worker states, including loading, missing credentials, and projection failure.
- Compare the provider fields used for classification or identity. Ignore refresh-only changes such as artwork and position. A changed unmatched, ambiguous, or previously unclassified unlocked source returns to pending evaluation. Preserve accepted matches and manual locks. Leave transport failures with their existing scheduler and retry controls.
- Compare incoming and previously stored listing IDs independently of the detail endpoint's ID. When changed listing evidence supersedes an in-flight claim, discard its pending writes and let the revised source go through the ordinary queue. Apply classification decisions only to the source generation the worker read.
- Discard a delayed status response after leaving its provider. Loading a different provider requires fresh readiness from that provider before its enrichment controls become available.

## Implementation sequence and acceptance

1. Add regression coverage for the new control location and for changed versus unchanged listings.
2. Move the existing controls, keep the repair tools in Maintenance, and add the changed-evidence check to projection.
3. Verify the following scenarios with isolated backend tests and a compiled desktop.

| Scenario | Observable result |
| --- | --- |
| Open IPTV Metadata on an idle provider | Enrich Metadata is selected, starts no request until clicked, and shows both outstanding counts |
| Start and pause on IPTV | Only the selected provider receives the existing worker actions |
| Open Maintenance | Repair controls are available and the routine start control is in IPTV |
| Refresh an unmatched or ambiguous listing with identical evidence | The saved terminal decision survives and the worker skips it |
| Correct an unresolved listing's title or year | The revised listing gets one fresh evaluation |
| Refresh an unchanged listing whose detail endpoint supplies a different TMDB ID | The detail ID does not requeue the settled listing |
| Refresh changed evidence during classification or matching | The earlier result cannot overwrite the revised source |
| Switch providers with a projection retry in flight | The newly selected provider keeps its own status and controls |
| Refresh an accepted or manually locked source | The recorded identity and lock survive |

## Verification and rollout

Run the relevant IPTV enrichment, projection, provider and UI suites in a unique `CP_TEST_ROOT` with `CP_TEST_MODE=1`. Use the repository offline desktop runner with a temporary bundle and provider data. The current live process, provider data, and running AI jobs are outside this gate.

- Isolated Python verification passed 126 tests across `test_iptv_movie_enrichment`, `test_iptv_movie_ui`, `test_iptv_movie_gates_0_5`, `test_iptv_provider_manager`, `test_iptv_routes`, `test_iptv_service`, `test_iptv_bulk_identity`, and `test_iptv_candidate_recovery`.
- The offline desktop runner passed all 11 tests in `tests/e2e/iptv-chatgpt-bulk.spec.js` using `index-B-nPNaZj.js`. The test browser verified the enrichment screen, explicit selected-provider controls, and late-response handling. The desktop screenshot was checked at 1600 × 1000. Provider control responses were simulated for the UI tests and the Python tests exercised the actual worker with isolated provider data.
- The live HTTP listener on port 5000 still served `index-gmdWYNEr.js` from PID 44016. The fixture tests provide no live Lionz match-rate or elapsed-time measurements.
