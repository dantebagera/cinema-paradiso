# Desktop More Like This — implementation and validation

Implemented in worktree `2420` and applied to the main checkout on 2026-09-14. No commit, publication, live catalogue mutation, or live desktop restart was performed.

## Ownership and behavior

- `SharedMovieCards.jsx` owns the rail through `MovieExpandedDetails`. Both owned and online cards use it, including Library, Movie Lists, AI Control, Discover Explore, AI picks, and indexer results.
- `RelatedMovieRail.jsx` loads eight compact tiles independently of base details. Recommended and Similar remain separate. Ownership comes from the existing canonical ownership check, not from TMDB.
- `App.jsx` owns cross-workspace navigation through a shared React context. Discover extends its existing relationship snapshots and individual-movie navigation. There is no synthetic genre or advanced-search predicate.
- `DiscoverWorkspace.jsx` stores relationship source, page, local page, ownership filter, expanded movie identity, active Discover tab, and workspace scroll in history. Breadcrumbs and browser Back reverse deeper exploration; returning to another workspace preserves its mounted expanded card and position.
- `movieRelationships.js` caches and deduplicates provider-page requests for 15 minutes, with a 256-page capacity. View all enumerates complete source rankings, then deduplicates by TMDB ID with Recommendations first. Navigation cancellation stops further page enumeration. A failed source does not block selecting the healthy source.
- `services/movie_relationships.py` provides an independent, transient, thread-safe provider-page cache. `/api/tmdb/related` validates source/identity/page, uses the existing TMDB movie normalization, and redacts upstream errors. No SQL persistence was added.
- `UnifiedMovieCard` centers on expansion and uses a scoped `ResizeObserver` to keep the finished card inside the viewport when asynchronous enrichment changes its height. Fixed rail and credits slots preserve loading geometry. Workspace restoration suppresses browser scroll anchoring and competing centering.
- Desktop heights up to 950 CSS pixels use an Overview / Lists & collection switch. At 850 and below, posters and credits become denser. Long plots remain accessible through Read full plot. No internal vertical card scrollbar was added.

## Validation

- 98 JavaScript unit tests passed (`node --test tests/*.test.mjs`).
- 66 focused Python tests passed: relationship caching/concurrency/validation/API behavior, TMDB details, unified cards, and expanded Library details.
- 19 feature E2E cases cover geometry, uniform ten-person credits, loading stability, source provenance, complete deduplication, ownership actions, all applicable shared-card surfaces, cross-workspace restoration, pagination/filter restoration, breadcrumbs, browser Back, late-response recentering, partial provider failures, and dense metadata.
- 5 existing cross-page-selection/source-search E2E tests passed.
- 23 existing smoke/card/navigation/search regressions passed, including canonical ownership parity, people/collection navigation, Library paging, curation refresh, and catalogue updates without unmounting.
- Production Vite build passed (1,665 modules). `git diff --check` passed.
- The compiled bundle was served through CP's normal Flask frontend routes on isolated port 5117 with a unique `CP_TEST_ROOT`. Served entry JS/CSS and Discover chunk SHA-256 hashes matched the built files.

## Visual evidence and limits

[1920×1080 desktop](desktop-1920x1080.png) and [1920×720 desktop](desktop-1920x720.png) show the complete border and all four corners. The smaller screenshot deliberately demonstrates a local relationship-provider failure while retaining the card and cast. Dense metadata was also checked at 1920×900.

Screenshots and browser tests use deterministic movie/ownership/provider fixtures and illustrative test posters. They prove the rendered application behavior, not the availability or ranking quality of a live TMDB account. The live desktop installation was not activated or changed.

The verified effective desktop height range is 720–1080 CSS pixels at 1920-pixel width. Layouts below 720 pixels high and mobile layouts were not validated; arbitrarily small windows cannot be assumed to fit this amount of content. Full relationship views may take longer when TMDB returns many pages; pagination limits and failures are reported rather than silently truncating or mixing rankings.
