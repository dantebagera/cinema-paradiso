# Discover visible posters before backdrops

**Status** — Dante approved implementation and desktop measurement on 2026-11-14. “Keep the background photos but load the visible posters first.” Implemented and measured in an isolated desktop build.

## Problem and decision

Discover's six visible Movie cards requested their separate TMDB backdrops alongside the posters. On the running build, the median poster load after cards appeared ranged from 390–430 ms, compared with 290–360 ms with the six backdrops blocked for the same cards. The change will keep the supplied photos and defer independent backdrop requests until the visible poster requests settle. Desktop Discover Movie and TV result cards are in scope. The benchmark uses the Movie results where the delay was measured. No open product decisions.

## Contracts affected and contract-change decision

| Contract and source | Affected callers | Disposition |
| --- | --- | --- |
| Dante's 2026-11-14 approval | Discover Movies, Browse Indexers, Pick My Movie and TV result grids | Prioritize visible posters ahead of separate, collapsed-card backdrops. Use the existing backdrop after the visible posters load or fail. |
| Existing shared artwork visibility and expanded behavior in the [UI integration plan](2026-10-14-new-ui-main-integration.md) | Discover and the other shared card surfaces | Keep the existing offscreen eligibility, loaded artwork reuse, eager expanded artwork and no-observer fallback. |
| Existing card geometry, URL selection, navigation and failure handling | Shared card callers | Keep the same components, gradients, image URLs, sizing, result layout, controls, detail actions and poster fallback. |

## Current design and ownership

- Desktop checkout is `master` at `117526b` with tracked and untracked local work, including shared card and Discover code. Preserve those edits. The live Flask listener on port 5000 was PID 32136 and served `index-rEoonoEd.js` using the configured Desktop `data` and `cache` directories at baseline.
- `App` mounts the Discover Movie and TV workspaces together. They render full results through `UnifiedMovieCard` and `UnifiedMoviePoster`. The shared `cardArtwork.js` hooks govern when the poster source and card background become eligible. Extend that owner with one queue scoped to Discover. The same card adapters are used in other workspaces.

## Exact behavior contract

Use the existing card, poster, fallback, and background gradient. For a collapsed full Discover card with a distinct backdrop, allow the normal near-viewport observer to make the backdrop eligible, then wait for all in-view poster images to finish or fail before assigning the backdrop URL. Only actual viewport intersections count toward the wait. A card without a poster contributes no wait. When a card uses the same image for its poster and background, retain the existing single-resource behavior. Expanded cards retain immediate artwork. Use the existing near-viewport eligibility and no-observer fallback. Track poster replacements and remove pending work on unmount. Once a backdrop starts, scrolling or opening another card does not restart it.

The change is limited to frontend image scheduling. Catalog inputs, outputs, writes and configuration stay as before.

## Implementation sequence

1. Add held-image Playwright tests on the existing Discover entry points and see the current request-order assertion fail.
2. Provide the Discover workspace with its own instances of the shared poster-priority scheduler. Connect the actual poster element and distinct collapsed backdrop assignment through the existing shared artwork owner.
3. Run the compiled artwork, Discover and TV checks. Compare the baseline and candidate on identical desktop Movie results, alternating fresh sessions. Measure from card appearance to poster readiness and verify that the candidate also loads the supplied backdrops.

## Acceptance matrix

| Starting state and action | Expected result | Evidence |
| --- | --- | --- |
| Two visible Discover posters held | A backdrop waits after just one poster loads. Release the other, then verify the same backdrop loads and displays. | Movie desktop request and computed style |
| Visible poster fails or is absent | The fallback appears and the backdrop still loads. | Movie desktop request and fallback |
| Nearby poster outside the viewport is held | Its transfer does not stall backdrops once visible posters settle. | Movie desktop scroll geometry and requests |
| TV Discover posters and independent backgrounds | Same order as Movie Discover. | TV desktop result grid |
| Movie Library, Home, or existing shared expanded card | Existing artwork and visibility behavior continues. | Shared artwork and TV desktop suite |
| Results change, card disappears, or a poster URL changes | Removed or replaced images do not hold future work. | Observer cleanup and desktop regression |

## Verification and rollout

- Run the existing OS-temp Playwright runner for compiled desktop checks, including `card-artwork-performance.spec.js` and `tv-visible-load.spec.js`. Run the isolated Discover paging and related coverage where applicable.
- For timing, serve the two frontend builds through identical browser interception. Reuse the same Movie Discover API responses and keep the real TMDB image requests. Compare fresh Chromium sessions with the browser cache disabled at 1600 × 1000.
- The live build and process are outside this implementation and test approval. Record candidate timings separately from live behavior.
- The baseline failed the new Movie request-order assertion. The final isolated build passed 24 artwork and TV tests and 11 Discover paging, Upcoming and IPTV badge tests. The TV suite used the repository's `tests/fixtures/tv_artwork.svg` through `CP_TV_E2E_ARTWORK`.

## Desktop timing results

The baseline `index-rEoonoEd.js` and candidate `index-C09OnWcf.js` each ran eight times in alternating pairs. All 16 runs rendered the same six titles, poster and backdrop URLs, gradient and final poster boxes. Time is measured from the cards appearing to poster image readiness or backdrop download completion.

| Measurement | Baseline | Candidate | Difference |
| --- | ---: | ---: | ---: |
| Median visible poster | 412 ms | 323 ms | 89 ms sooner, 22% |
| All six visible posters | 429 ms | 363 ms | 66 ms sooner, 15% |
| All six backdrop downloads | 428 ms | 510 ms | 82 ms later |

Per-run median poster times in ms were `453, 414, 394, 389, 356, 427, 424, 409` before and `321, 319, 320, 325, 334, 329, 329, 315` after. The candidate started its first backdrop request 12–30 ms after the last poster was ready in all runs. Every backdrop transferred successfully, including one run where the last backdrop took 1.53 seconds after card appearance. The measurements describe Movie Discover on the tested connection. TV Discover was covered by request-order tests.
