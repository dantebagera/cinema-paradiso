# Complete movie filmography from the credit button

**Status:** Implemented, verified in isolation, and deployed to the running Desktop app on 2026-10-01. Dante approved implementation with “ok lets fix” and the subsequent live deployment with “go”. No restart, commit, or release was performed.

## Problem and decision

- **What happens now:** The small Filmography button on a Discover actor card falls back to the card's filtered person navigation. With Horror and France active, Meryl Streep opens an empty result even though her unfiltered actor credits contain movies. The empty message says no TMDB movies were found for her.
- **What Dante wants:** The small Filmography button opens the person's complete role-specific movie credits. The card body may continue to navigate using the active Discover criteria. The Filmography destination visibly starts with no filters; Back restores the preceding state.
- **Confirmed:** `MovieExpandedDetails` already accepts separate browse and discover callbacks. Discover supplies only browse. The current person context compiles active criteria into an Advanced query. The earlier 100+100 related-movie change did not introduce this behavior.
- **Open decisions:** None for this scope. The existing Director and Writer role rules remain unchanged.
- **Scope:** Movie credit buttons in Discover, Library, Lists, and AI Control. Do not alter TV filmography, relationship limits, provider credit normalization, card layout, or mobile behavior.

## Current design and ownership

| Responsibility | Authoritative owner | Callers | Preserve | Obsolete path |
| --- | --- | --- | --- | --- |
| Credit-card actions | `PersonCreditCard` through `MovieExpandedDetails` in `SharedMovieCards.jsx` | Discover, Library, Lists, AI Control | Biography button and card click | Discover filmography fallback to `onPersonBrowse` when an explicit callback is available |
| Movie person navigation and filter state | `DiscoverWorkspace.jsx` person context and history | Discover and external relationship request | Filtered card click, role, pagination, Back, later filter edits | Active criteria on full-filmography entry |
| Cross-workspace navigation | `App.jsx` `openPersonInDiscover` | Library, Lists, AI Control | Section activation and request identity | Missing full-filmography intent on the small button |

Baseline: Desktop checkout `master` at `c62b3f3`, ahead of `origin/master` by one commit, with substantial pre-existing dirty work. Port 5000 is served by `C:\Program Files\Python312\python.exe app.py`, PID 14628, and the live `dist/index.html` SHA-256 is `982C427CE0E475AFB23A2663C047BB7E855A31CF4A4A302E117671EF49C376BF`. The running bundle and live data are separate from this source-only change. Current prior reproduction: unfiltered Meryl Streep actor credits total 155; Horror+France returns zero. No baseline automated suite was run before this edit.

## Exact behavior contract

### Frontend

- Reuse the existing `PersonCreditCard`, `MovieExpandedDetails`, `DiscoverMovieCard`, and `IndexerMovieCard` controls and styling. Add no markup or CSS.
- Clicking the small Filmography button enters the existing person-credit relationship page through `/api/tmdb/person_movies`, regardless of previously active Discover criteria, and selects All movies with cleared genre, country, year, vote, rating, sort, and title criteria. Advanced mode switches to Movies for this destination. The prior state remains in navigation history.
- Clicking the card body keeps the current context refinement behavior. An empty refined result says that no movies match the active Discover filters, not that the person has no credits. Changing a filter after entering the full filmography applies that filter using the existing Advanced relationship owner. Pick My Movie's relationship path remains unchanged.
- Library, Lists, and AI Control route the small button with the same explicit full-filmography intent. TV uses its existing separate TV credit route.

### Backend

No backend, persistence, migration, retry, or provider change. Existing `/api/tmdb/person_movies` inputs and outputs remain authoritative. The frontend decides whether to request full credits or a refined relationship. Request cancellation and errors retain the existing `loadContextPage` behavior.

## Implementation sequence

1. Give movie card consumers an explicit Filmography callback while preserving the card browse callback.
2. Teach the Discover person-context owner to enter with a clean, role-specific credit context for this action; reset visible criteria and preserve the pre-navigation snapshot.
3. Carry the action intent from external workspaces through `App.jsx` and add a browser regression check for filtered versus full navigation, Back, and later refinements.
4. Run focused isolated browser checks and a compiled isolated desktop build. Do not overwrite the live `dist` or restart CP under this approval.

## Acceptance matrix

| Scenario | Action | Expected result | Evidence |
| --- | --- | --- | --- |
| Discover with Horror+France | Small Filmography button | Person-credit route, complete count, filters visibly cleared | New E2E |
| Same card with active criteria | Click card body | Existing refined route and criteria retained | New E2E |
| Full credits then filter | Select genre | Existing Advanced relationship refinement | New E2E |
| Full credits then Back | Back | Prior filters and cards restored | New E2E |
| Library/List/AI small button | Open Filmography | Explicit full-credit request | Code path and relevant E2E |
| Pick My Movie | Small button | Existing unfiltered Pick credits and paging | Existing E2E |
| TV card | Small button | TV credits remain TV-owned | Existing TV E2E if run |
| Empty/error/missing person ID | Open | Existing empty/error handling or unavailable control | Existing owner behavior |

## Verification and rollout

- **Baseline:** Dirty files are preserved; current live reproduction and prior A/B comparison are evidence, not a passing automated baseline.
- **Focused tests:** Isolated Playwright using `tools/run_playwright_e2e.ps1` and the new focused test plus the existing Pick relationship test.
- **Broader tests:** Relevant Discover, Library, and TV movie-card E2E checks as feasible; report any failure distinctly.
- **Compiled UI:** The isolated Playwright runner builds to `CP_TEST_ROOT/dist`, leaving live `dist` untouched. Verify desktop controls and page state in the browser test.
- **Live work:** Separate authorization is needed to replace live `dist` or restart CP. Report source/isolated status and any remaining limits.

### Isolated verification results, 2026-10-01

- Five targeted browser navigation tests, including the two new filmography scenarios, passed on the final source and isolated compiled bundle. All 21 tests in `tests/e2e/movie-relationships.spec.js` passed before the final filter-reset helper and refined-empty-message cleanup; those changes were covered by the final targeted run.
- `python -m unittest tests.test_unified_movie_card_ui -q` passed 30 tests. An initial `pytest` command could not run because the project virtual environment does not contain pytest; the repository's unittest runner passed instead.
- `git diff --check` exited zero. At this isolated gate, the live port 5000 bundle had not yet been replaced.

### Live deployment and verification, 2026-10-01

- The previous live `dist` was copied to `C:\Users\dante\AppData\Local\Temp\cinema-paradiso-filmography-deploy-1790827272309\dist-before`; its original index SHA-256 was `982C427CE0E475AFB23A2663C047BB7E855A31CF4A4A302E117671EF49C376BF`.
- A production bundle was built under `C:\Users\dante\AppData\Local\Temp\cinema-paradiso-filmography-deploy-1790827272309\staged-dist`. Its assets were copied into Desktop `dist` before replacing `index.html`. The served index and staged index match SHA-256 `F6DB43F83BC0875A98A70E5AD88BD48A007CDF56BB904D22EB5940E640A8D860`. `/discover` and the new `index-C4ryBrE8.js` returned HTTP 200. The server remained PID 14628.
- A fresh live browser opened The Devil Wears Prada, clicked Meryl Streep's small Filmography button, and observed `/api/tmdb/person_movies?person_id=5064&role=actor`, page 1 of 4, showing 1–40 of 155 credits with Genre and Country cleared.
- A second live browser used Raw (2017) with Horror and France selected, clicked Garance Marillier's small Filmography button, and observed the person-credit route, 25 visible cards matching the API's 25-credit total, and both filters cleared. No pager appeared because the result fits on one page.
