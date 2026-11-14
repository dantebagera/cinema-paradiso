# IPTV Filmography button opens Discover

**Status:** Approved implementation and main-app activation, 2026-11-13. Dante corrected the intended behavior and answered "yes go" to applying, testing and activating the correction. No further product decision is open.

## Problem and decision

The IPTV portrait and Filmography button both use `browseIPTVPerson`; its boolean only resets filters. The original plan and test captured the wrong destination. Portrait must remain provider-local; Filmography must use the existing Movie Discover full-filmography flow. Biography and availability checks remain unchanged.

## Contracts affected and contract-change decision

| Contract and source | Current rule | Affected callers | Approved correction | Changes contract? | Decision |
| --- | --- | --- | --- | --- | --- |
| Previous IPTV integration plan | Both clicks stay in IPTV | IPTV cast/director cards | Small button opens Discover full credits; portrait stays provider-local | Yes, supersedes recorded rule | Dante: "it should open discover with the filmography like in movies"; then "yes go" after notice |

## Current design and ownership

Candidate checkout: managed `iptv-discover-streaming` worktree, detached `117526b` plus prior dirty baseline and activated integration. Main checkout is dirty master at the same commit; relevant source files match. Live process before correction: 46308, port5000, bundle `index-ClUXqNff.js`, data/cache in desktop checkout. Existing files are snapshotted before edits; unrelated changes must be preserved.

`IPTVPeopleCredits` reuses `PersonCreditCard`; `IPTVPeopleNavigationContext` currently carries one callback. `IPTVWorkspace` owns provider-local person navigation. `App.openPersonInDiscover` already carries role/person and `fullFilmography` to Discover. `DiscoverWorkspace` owns clearing criteria, loading person credits, pagination, empty/error states and navigation. `MediaWorkspace` owns Movie/TV selection.

## Exact behavior contract

Keep the same portrait, button placement, sizes and styles. Supply separate `onBrowse` and `onDiscover` callbacks through the existing IPTV context. Pass the originating movie title/year to the existing App handler. Remove the obsolete provider-local fullFilmography boolean. The shared App person handler selects Movie Discover even if TV was previously selected; all existing Movie callers benefit from this same owner.

Full filmography clears Discover criteria through its existing owner, uses normal TMDB filmography requests, and may contain films absent from IPTV. IPTV badges remain asynchronous local-only reads. Existing portrait filters/Back and Biography remain unchanged; missing person IDs remain disabled. Switching back to IPTV preserves its mounted provider/card state, matching existing cross-surface navigation behavior. No backend, schema, configuration, migration or design changes.

## Implementation sequence

1. Add actor/director tests asserting `/discover`, exact person/role request, a film absent from IPTV, and preserved IPTV state. Correct the old test to exercise portrait browsing.
2. Run the new regression against unchanged source and observe failure.
3. Wire the distinct existing navigation callbacks; ensure Movie mode through App's shared handler.
4. Run focused compiled tests and broader existing Movie/TV relationships tests; update guides and evidence.
5. Snapshot main source/dist, copy only the correction, rebuild and restart through CP's normal handler. Verify new bundle/API and rendered UI if computer-use permits; report limitations.

## Acceptance matrix

| Scenario | Action | Expected result | Evidence |
| --- | --- | --- | --- |
| Actor/director credit | Small Filmography button | Discover full credits with correct person and role, including non-IPTV films | New parameterized browser tests |
| TV last selected in Discover | Small button | Movie Discover visible | Same test with saved TV media selection |
| IPTV portrait | Click body | Current provider movies, refinements and Back preserved | Existing test changed to portrait action |
| Return to IPTV | Sidebar IPTV | Same provider/expanded source card | New tests |
| Missing person ID | Small control | Disabled explanation | Existing browser test |
| Biography and shared geometry | Open Bio | Existing modal and 106x132 portrait | Existing browser tests |
| Existing Movie/TV navigation | Related and person actions | Existing behavior retained | Movie relationships and TV expanded parity |

## Verification and rollout

Use isolated Playwright runner/port5117 with CP_TV_E2E=1 and temporary data; external TMDB credit response is fixture-controlled, local IPTV APIs remain real. Run `iptv-people.spec.js`, existing `movie-relationships.spec.js` excluding its mobile-only390px cases, and `tv-expanded-parity.spec.js`. Run all Node tests and focused Python IPTV UI guards. Prior activation tests are historical, not new evidence. Activation is explicitly approved. Preserve rollback files/dist; rollback on failed build/start/navigation. No commit/push. Report actual isolated versus live evidence.

## Results

Implemented and activated in the desktop main app. Final desktop suite 47/47, Node 155/155, focused Python 22/22. Review finding about origin capture fixed and regression-tested. Main serves the tested `index-rEoonoEd.js` bundle; configuration/data ownership preserved. Production desktop browser verification passed: the small Brad Pitt button opened Movie Discover with 115 credits and the correct IPTV breadcrumb. [Evidence and rollback](../verification/iptv-filmography-discover-2026-11-13/report.md).
