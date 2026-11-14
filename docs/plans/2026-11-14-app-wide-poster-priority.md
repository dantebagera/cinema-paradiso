# Poster priority across CP card pages

**Status** — Dante approved applying the Discover fix across CP on 2026-11-14. Implemented, compiled and live verified.

## Problem and decision

The compiled Discover candidate orders visible posters before separate card backdrops, but its scheduler is scoped to Discover. Library, Lists, Home, IPTV, AI and other pages can render the same components. Extend the existing rule to every CP desktop page that displays cards with independent backdrops. Preserve the actual photos and artwork selection. No open product decisions.

## Contracts affected and contract-change decision

| Contract and source | Callers | Behavior |
| --- | --- | --- |
| [Discover poster priority](2026-11-14-discover-poster-priority.md) and Dante's 2026-11-14 app-wide approval | Shared full cards, compact Home cards and Movie/TV related rails | Hold distinct backgrounds until in-view posters finish or fail. |
| [Existing visibility and artwork contracts](2026-10-14-new-ui-main-integration.md) | Shared cards, hidden workspace panels and horizontal rails | Preserve poster fallback, image URLs, offscreen deferral and loaded artwork reuse. Expanded artwork remains immediate, including the TV series detail header. |
| Existing desktop layout and interactions | All affected card pages | Preserve grid, card boxes, gradients, selection, navigation, and artwork quality. |

## Current design and ownership

The dirty Desktop checkout is `master` at `117526b`; preserve existing work. Flask PID 32136 listens on port 5000. The live app uses Desktop data and cache and serves `index-rEoonoEd.js`. `ArchiveApp` supplies the existing scheduler context to Discover only. `cardArtwork.js` owns poster and backdrop eligibility. `UnifiedMoviePoster` already registers poster readiness. `RelatedMovieRail` renders its own poster markup. IPTV's standard series tile uses one image for poster and backdrop.

## Exact behavior contract

### Frontend

Supply one scheduler through the app root. The shared backdrop hook reads it for independent collapsed/compact card backdrops. Register related-tile poster readiness through the same hook used by the full and compact shared poster component, retaining the related tile markup and fallback. Treat the workspace and any nested horizontal rail as clipping boundaries for current viewport checks. Posters on retained hidden pages and posters clipped by a rail do not block a visible page's background photos. Equal poster/backdrop URLs retain the single-resource path. Preserve the existing eager fallback if the intersection observer is unavailable.

### Backend

Frontend asset scheduling requires no API or data changes. Existing read models, image URLs and persistence continue to supply the same artwork.

## Implementation sequence

1. Extend the held-image desktop regression tests to Library, Home and a related-title rail. Reproduce the Library failure against the Discover-only implementation.
2. Move the existing context to the app root, move its policy lookup into the shared artwork hook, and connect related-tile posters. Account for clipped rails in the existing viewport check.
3. Verify the compiled desktop suites. Install only the verified frontend bundle into the running app's static directory and verify a fresh browser load. Keep the previous index and its referenced chunks available for rollback. The Flask process can serve a new static index without a restart.

## Acceptance matrix

| Starting state and action | Expected result | Evidence |
| --- | --- | --- |
| Visible poster held in Library or Discover | Separate backdrop waits; supplied photo and gradient appear once visible posters settle | Movie/TV network and CSS checks |
| Home cards or related tiles have independent backdrops | Same order, with the compact styles and navigation retained | Home and related rail desktop tests |
| A horizontal rail poster remains pending after scrolling out of view | Visible artwork proceeds while the hidden poster is still pending | Browser scroll and request checks |
| A poster fails or is absent | Existing fallback and background availability | Held-image tests |
| Background equals poster, detail opened, or observer unavailable | Existing single-resource, eager detail, or fallback behavior | Shared artwork and expanded TV tests |
| Same source raises no new backdrop on actual live Library data | Live asset transfer and served bundle verification | Fresh desktop browser |

## Verification and rollout

Use the existing Windows Playwright runner and temporary fixture app for artwork, Home, Lists, IPTV and TV coverage. Keep production datasets outside the fixture runs. Verify the live process, config roots, hash of the served bundle and desktop result after swapping the static index. Restore the prior index if the new bundle cannot load or scheduled artwork regresses. Report application-wide request ordering separately from the already measured Discover timing.

The Discover-only build failed the new Movie Library request-order assertion. The app-wide bundle passed 46 tests across artwork, Home Continue Watching, Lists, IPTV and TV. A second run passed 24 tests across artwork including Home Trending, Discover paging, Upcoming and IPTV badges. Twelve artwork tests ran in both suites.

The live app serves `index-XKXIpEzP.js` from the Desktop checkout. The production index was replaced after the 34 compiled assets were checked against their build hashes. Flask stayed on PID 32136. The previous index is `dist/index.poster-priority.previous.html`, with the previous chunks still in `dist/assets`.

A fresh desktop browser loaded all ten main workspaces with the new bundle and saw no page errors or failed frontend assets. Discover loaded six visible posters, then started all six independent backgrounds 16 ms after the last poster became ready. The sampled visible Home Trending and Movie Library cards reused poster images for the backgrounds. The earlier 22% timing result applies to the measured Discover comparison.
