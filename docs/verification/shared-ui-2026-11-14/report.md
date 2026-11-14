# Shared desktop UI verification — 2026-11-14

## Scope and authorization

Dante chose all eight recommended visual families, then explicitly instructed that mandatory reuse be recorded before proceeding with the plan. [Approved plan](../../plans/2026-11-14-shared-ui-standardization.md). UI only: feature callbacks, domain data and interaction policy remain with their existing owners. No backend change, live catalog action, app restart, commit, push or installed-bundle activation was performed by this task.

The permanent rule is in [AGENTS](../../../AGENTS.md); the [registry](../../atlas/shared-ui.md) identifies production owners. The reuse gate runs in `predev` and `prebuild`, rejects copied markup/feature overrides/missing imports, and bounds existing specialized controls by exact signatures and counts. It is supplemented by rendered checks and review; it does not prove arbitrary visual similarity or prevent deliberate bypass.

## Baseline and implementation

- Current dirty checkout: `C:/Users/dante/Desktop/cinema paradiso`, `master`, HEAD `117526b`. Pre-implementation status was 176 modified, 2 deleted, 308 untracked entries. Unrelated work was preserved.
- A snapshot of 499 current source/test files and hashes was saved at `C:/Users/dante/.codex/visualizations/2026/11/14/01a1da8d-18c9-7c31-9dcf-00018cd26fc7/ui-refactor-baseline`. Baseline was the actual dirty source, not HEAD.
- The baseline compiled to entry `index-DARa9R-d.js`, matching the previously observed installed frontend. The live backend was PID 52092 at port 5000, data owner `C:/Users/dante/Desktop/cinema paradiso/data`. These observations do not make the new source live.
- Shared Button/StreamButton/ActionLink, Badge, FormField/Input/Select/Textarea, DialogShell/Header/Actions and SectionTabs/Tab now own the selected families. Existing Pagination, WorkspaceSelectionBar, WorkspaceEmptyState and SearchField were extended/reused. Settings ActionButton, IPTV/AI/notification pagination and AI selection copies were retired. Ordinary callers across Movie, TV, IPTV, AI, Library, Maintenance, Lists, Settings, Home and notifications were migrated.
- `ui.css` owns core appearance. Replaced private styles were removed. Existing desktop density and mobile-specific values moved with their owners where needed; no mobile redesign or mobile testing was performed.
- StyleGuide renders real production owners with local sample state; Card Lab buttons and badges also consume production primitives. Specialized media stages, rail/poster controls, menus and local segmented choices retain their semantic owners. See the registry for boundaries.

## Evidence

| Check | Result / scope |
| --- | --- |
| Baseline Python UI source checks | 100 run; 97 passed and 3 failed before implementation. |
| Final Python UI source checks | Same three baseline failures remain; obsolete owner-path assertions were updated without changing product expectations. |
| `npm run test:shared-ui` | 15 passing rendered-contract/gate checks. New dialog-name bypass check failed before its gate fix and passed afterward. |
| `npm run check:ui-reuse` | Passed. New raw controls, copied shells, new appearance overrides and missing imports rejected; existing exact semantic owners bounded. |
| Candidate build | Passed through `npm run build` including its reuse gate; output only under OS temp. |
| First compiled desktop batch | 87 / 89 passed: Lists, workspace controls/empty states, streaming provider routing and shared reference at 1600×1000 and 1280×720. Both failures reproduced on the compiled pre-change snapshot. |
| Affected integration batch | 21 passing: all workspace smoke routes, Home layout, cross-page selection/payloads, native TV route/streaming, cast/related rails and biography. One newly written Maintenance check initially used nonexistent `/maintenance`; corrected to existing `/cleanup`, then passed. |
| Review-fix batch | 17 passing: actual plot and keyword appearance, biography shell, TV episode Stream green and exact target, AI custom selection/paging/exact keys, IPTV portrait/filter/back behavior, Maintenance equal tab widths, two-width reference and affected search/header layout. One IPTV test reaches an obsolete `Metadata sections` expectation; the same failure was reproduced on the compiled baseline, which already uses `Recovery sections`. |

The three unchanged Python failures are `test_expanded_cards_move_rating_to_top_right`, `test_expanded_people_cards_include_biography_popup`, and `test_following_is_an_independent_universal_card_badge_with_experimental_palette`. They were not weakened or hidden.

The three reproduced desktop baseline failures are:

1. `lists-layout.spec.js:271`: expects `1.5K votes`; the baseline and candidate both display `7.8 - 1.5K`.
2. `workspace-controls-empty-layout.spec.js:1046`: TV list option `81` is absent in both baseline and candidate fixtures.
3. `app-smoke.spec.js:3416`: expects navigation named `Metadata sections`; both baseline and candidate use the existing `Recovery sections` flow.

Initial desktop logs: `%TEMP%/cp-ui-e2e.log`; baseline comparison: `%TEMP%/cp-ui-baseline-e2e.log`; integration: `%TEMP%/cp-ui-final-e2e.log`; review fixes: `%TEMP%/cp-ui-reviewed-e2e.log`. Fixture processes use disposable data at port 5117, prohibit production port/data, and are stopped after each run. No real stream provider, download or AI job was exercised.

## Independent review

Fresh-context review compared current files with the saved dirty-source baseline. It found no unexplained changes to callbacks, refs, autofocus, form/method/action, tab order, roles or accessibility attributes. It found two ownership gaps: plot/biography shells and keyword Badge paint. Both were corrected and the real rendered callers checked. The strengthened dialog gate additionally exposed the Movie poster and Smart Match review shells; those now use DialogShell. Only the three excluded media stages retain native shells. No review finding is deferred.

Final cleanup verification: 3 / 3 desktop checks passed for notification/sidebar dismissal and the shared reference at both widths, after the final Card Lab/notification cleanup. Final candidate: `%TEMP%/cp-ui-standardization-reviewed`, entry `index-CD1fO69d.js`. Final gate and all 15 rendered/gate tests passed. Live recheck still returned PID 52092 with `index-DARa9R-d.js` and `index-bBaF3XqR.css`; the candidate was not installed. Additional logs: `%TEMP%/cp-ui-iptv-baseline.log`, `%TEMP%/cp-ui-finish-e2e.log`.

Desktop reference captures: [1600 px](shared-families-1600.png), [1280 px](shared-families-1280.png).

## Rollout boundary

The implementation was initially verified in isolation without changing installed `dist`. Dante subsequently authorized installation as recorded below. Known baseline failures mean this is not a claim of an entirely green repository suite.

## Authorized live installation — 2026-11-14 17:53 Cairo

Dante explicitly requested: "go ahead install the reviewed frontend bundle so i can see the changes in cp".

- Installed the exact reviewed candidate (`index-CD1fO69d.js`, `index-BEkepvH5.css`), without rebuilding current source or restarting the backend.
- Backed up the complete previous `dist` (55 files, approximately 4 MB) to `C:/Users/dante/.codex/visualizations/2026/11/14/01a1da8d-18c9-7c31-9dcf-00018cd26fc7/ui-activation-backup-20261114-175355/dist`. The parent directory contains `activation.json` and the replaced index.
- Verified all 76 candidate assets against installed file hashes. Retained previous hashed assets and atomically replaced `dist/index.html` after staging the new assets. Installed index SHA256: `6278B9F1E40EBDF8CC05CD5B0ACD06027CF8202AC95815C446A7D45E73EDD0DE`.
- Confirmed the live homepage serves the reviewed entry. Downloaded its entry JS and CSS from port 5000 and verified byte hashes against the candidate. Backend PID 52092 and data owner `C:/Users/dante/Desktop/cinema paradiso/data` were unchanged.
- Opened the live `/styleguide` in the desktop browser and visually verified the new shared controls, including green Play and Stream. No playback or catalog mutations were performed. Existing open CP windows load the new bundle on refresh; no backend restart is needed.
- Rollback: restore the saved `dist/index.html` to the installed `dist/index.html`. All assets needed by that previous entry remain installed; the complete backup is also available.
