# IPTV Unmatched and first-pass fallback

**Status** Implemented and verified in isolation November 10, 2026. Dante requested one Unmatched list in Maintenance, the first-pass fixes discussed after the Lionz run, and the same flow chart and GPT skills.

## Problem and decision

Lionz first pass recorded 76 TMDB 404 errors, a blank provider ID conversion error, and a duplicate genre write error on 78 retried sources. The last Maintenance selection covered 2,033 explicit misses and excluded 979 uncertain matches and 3,225 unknown categories. That run paused during local preparation of the first 100 titles with 75 prepared and zero ChatGPT calls.

## Contracts affected and contract-change decision

| Contract | Behavior | Decision |
| --- | --- | --- |
| CP classifies and matches eligible films in IPTV | Preserve the first-pass rules. A missing provider ID lookup falls through to the existing bounded title-and-year matcher. A missing finalist cannot be saved as a match. Optional localized metadata does not undo a verified identity on 404. Genuine request failures follow existing error handling. | Dante approved the fixes |
| Select settled leftovers together in Maintenance | Unmatched covers settled no-match, uncertain identity, and unresolved category. Availability, provider isolation, manual locks, and technical errors remain enforced. | Dante explicitly approved one list |
| GPT matching and persistence | Keep skills, prompts, batching, verification, approval limits, and Apply behavior. Saved selections retain their exact source keys. Use plain display wording and expose local preparation before GPT. | Dante explicitly preserved the flow and skills |

## Current design and ownership

`master` at `be511f9` with 400 dirty paths before edits. The live app is PID 36092 serving `index-CmT9ryVr.js` against the workspace data. `IPTVMovieService.enrich_source` owns first-pass matching, `IPTVMovieStore._save_tmdb_movie` owns genre persistence, and `_review_scope` supplies both displayed and submitted selections. Reuse the existing desktop review cards and saved GPT panel. Preserve older review API scopes and stored selections.

## Exact behavior contract

- An unavailable provider ID leads to normal CP title matching. A blank detail ID uses the normalized projected provider evidence where present. Repeated genres yield one relationship per genre. A timeout, 401, 429, or other technical error keeps its existing handling. Prior failed rows become eligible through the existing Retry failures action.
- Maintenance → IPTV opens on Unmatched unless a resumable GPT session needs attention. Search, category and playlist filters narrow that single queue. The existing card badges explain the three reasons. Select all filtered submits the same provider-specific result set as the listing query. Explicit stale selections still require review.
- Use ChatGPT matching and matching session in the desktop surface. Show local preparation progress while preserving the existing request and Apply counters. IPTV uses plain labels for the reasons and distinguishes technical failures from missing matches.

## Implementation sequence and acceptance

| Scenario | Expected result |
| --- | --- |
| Bad provider ID and valid title search | CP verifies and saves the title match through its existing matcher |
| Bad provider ID and no candidate | The listing is saved as unmatched |
| Blank detail ID and duplicate genre rows | CP saves a verified match and one relationship per genre |
| Detail returns a blank ID after a previous, different detail ID | The valid current listing ID remains the provider evidence |
| A search result disappears during detail lookup | The first pass continues with remaining valid candidates |
| Technical provider lookup error | The error is surfaced to the existing worker failure path |
| Maintenance all-filtered and explicit selections | All three settled cohorts appear together and the same available, unlocked rows reach the existing GPT workflow |
| Technical failure, pending classification, manual lock, or accepted match | The row stays outside the merged scope |
| Previously selected listing disappears | Standard and ChatGPT selections reject the stale set and require a fresh selection |
| Historical saved session | Frozen source keys and launch, resume, verification and Apply behavior are preserved |

## Verification and rollout

Run focused and broader IPTV Python suites with isolated provider data. Build and run the offline desktop bulk spec to check navigation, the mixed selection and the existing GPT path. Check current Lionz membership read-only and confirm the live bundle. Live data writes, actual GPT runs, build replacement and restart require separate authorization.

- The candidate list and all-filtered selection both returned 6,237 rows against the Lionz database in read-only mode. The existing paused GPT session remains bound to its saved 2,033 keys.
- Focused regressions reproduced the 404 aborts, whitespace-ID conversion and stale evidence, and selection narrowing before the fixes. Eleven focused matcher and queue checks then passed.
- Final verification passed 147 Python tests across the enrichment, provider, UI, AI routes, matching, and Apply suites. The extended run was stopped during the 40,000-listing Apply stress case. That case and the 25,001-listing inference stress case were excluded from the completed verification.
- All 13 compiled desktop tests passed using `index-9d_Ds88k.js`. They covered the merged selection, a 6,413-listing launch, saved-session navigation and Apply, and provider switching. The desktop Unmatched layout was inspected at 1600 × 1000.
- The live app continued to serve `index-CmT9ryVr.js`. No live retries or ChatGPT calls were launched by this work.
