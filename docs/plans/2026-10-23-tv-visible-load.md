# TV first visible load and complete cards

**Status:** Implemented and verified in isolation. Discover improved materially; Library card data improved, but its repeated complete-artwork median improved only modestly. Normal-launch behavior remains unverified. See [final evidence](../verification/tv-library-performance/visible-load-final-2026-10-23.md). Dante approved this continuation without routine approval stops; preserve all behavior, unrelated dirty work and production data, and do not restart a live app. Production dist still contains the previous source fix.

## Problem and decision

The previous fix removed a code boundary and repeated owned-card reads, but did not measure complete visible cards. A fresh isolated CP shell, using canonical TV routes/read owners and SQLite mode=ro/query_only on actual TV/acquisition data, shows Discover click5211.6ms,40 cards6298.2ms, visible counts complete7937.9ms and four posters complete7945.5ms. Initial API1045.2ms; later20-card batches1626/1980.6ms. Three of four visible cards wait for a complete20-card response. Library also starts maintenance, list contents and filter filesystem reads before the primary card request. BulkActionBar requests watchlist contents although it consumes only custom-list descriptors.

Confirmed: unnecessary auxiliary work and batch-level blocking exist in current owners. The cProfile-enabled Library capture is diagnostic only: profiling inflates/interleaves its timing and is not an uninstrumented performance baseline. New end-to-end observations must disable cProfile. Movie results in the diagnostic shell are empty fixtures; never claim Movie-versus-TV speed parity from it. Fresh provider/read-model process, but OS filesystem/CDN caches are not cleared.

Decision: schedule existing work around useful visible results, without changing data membership, public fields, policies, artwork URLs, provider details requested or final card content. No transport/dependency change, metadata thinning, speculative prefetch, persistent cache or database migration.

## Contracts affected and contract-change decision

| Contract/source | Agreed behavior and exceptions | Surfaces/callers | Change |
| --- | --- | --- | --- |
| MediaWorkspace retention | Data starts on first TV selection, cached returns retain page/filter/scroll | Library/Discover | No |
| Catalog result | Same complete payload, count/order, fresh physical availability and playback action | TVSearch/TVWorkspace | No |
| Auxiliary toolbar data | Same choices, list names, review count and independent errors; loading is already asynchronous | TVSearchControls/TVBulkActionBar/TVLibraryImport | Schedule Library choices/review and list names after initial catalog settles, including failure; do not gate later interactions |
| Discover enrichment | Every pending page identity attempted, full existing metadata merge and independent failures | All39/40-card pages, narrow/wide desktop | Visible identities first; background identities still all processed, no additional provider-detail identity or retries |
| Concurrency/cancellation | At most previous maximum concurrent batch requests for that pending page, abort on query/page/revision change | Discover | Preserve capacity ceil(pending/20); priority split may add one local HTTP batch but not remote identities or concurrent capacity |
| Movie/shared visuals | Same components, geometry, fields and assets | Movie/TV/Home/IPTV | Extend existing shared visibility owner to poster source activation; no style/layout/URL/quality change |

These are work-order changes inside existing asynchronous loading, with no product rule change. No open contract decision.

## Current design and ownership

master/be511f98846a67a182e5b371ad087938e9344362, existing dirty source preserved under `cp-tv-visible-load-af71d22f-388b-4b6a-861e-590500b9af75/baseline`. Full status snapshot retained. TVWorkspace owns initial catalog fetch and enrichment; its grid callback can retain its own DOM node to identify visible card indices. TVSearchControls owns filter-choice fetch, TVLibraryImport review count, and TVBulkActionBar list descriptors. Keep those data owners and public endpoints.

## Exact frontend behavior

1. TVWorkspace tracks auxiliary readiness. Set this monotonic flag on initial catalog success/non-abort failure **or immediately when the user opens controls**, so a stalled primary request cannot block choices/list actions. Keep it true through later refresh/paging. Library options/review and bulk list descriptors wait for that flag; Discover options remain concurrent because they populate provider label lookups. Reuse WorkspaceControls' existing onExpandedChange callback; no shared component change. Default readiness props remain true for other callers. A primary error must still release auxiliary loading and Retry remains usable.
2. TVBulkActionBar requests `/api/tv/lists` rather than watchlist items. Its consumed `lists.filter(!system)` data and list action behavior remain identical. No list route/read-model rule changes.
3. In Discover's existing enrichment effect, retain the grid node via a stable composed ref. Identify actual visible cards using intersection with the workspace/viewport and their existing item order. If hidden/unmeasurable, use the first grid row as priority. Partition pending IDs into priority then remaining chunks of at most20. Keep one queue with capacity equal to the old number of20-ID batches. Merge each completed batch immediately using the exact existing ownership/count/watchlist preservation rule. All IDs are attempted once; one failure cannot block remaining batches. Abort stops queued work and prevents stale merges.
4. No geometry, card markup, mobile/responsive redesign, new visual state, API result field or artwork-URL change.

Measured follow-up: fresh visible-lifecycle Chromium showed Library data ready in0.33s but all visible posters still1.69s. It requested24 posters plus six backdrops while six cards were visible. Native image lazy loading reaches much farther than the existing background visibility owner. Extend that existing shared owner to activate poster sources near the viewport too: one shared observer/URL-replacement implementation, same supplied URLs/quality, retained loaded images, unchanged fallback, eager expanded/data/blob images, and the existing no-IntersectionObserver fallback. The poster element/class/geometry and scroll/navigation contracts remain; only distant image request timing changes. The real card error/overlay logic stays in UnifiedMoviePoster. Add RED→GREEN request/scroll tests on TV and Movie Library, run the existing shared artwork cases (Home/related/hidden replacement/no observer), and an IPTV Movie smoke because the poster owner is shared. Preserve all public payloads and enrich every page identity.

## Backend contract

Fresh measurements still place local snapshot preparation before the provider's first request. TVSearch.discover will overlap those independent operations using one request-scoped worker. That worker opens/materializes/closes its own SQLite snapshot, preserving one context and fresh availability. The existing provider paging/filter/enrichment owner remains in one private page method. Wait for the snapshot before local filtering or owned-card composition; preserve local-validation error precedence when provider and local reads both fail, the existing15-second deadline, filtered-scan semantics, provider concurrency, output and context release. No connection is shared across threads. Add deterministic Event-based overlap and simultaneous-error tests before changing this owner, then rerun memory/contract checks.

Diagnostic server imports the isolated app shell without startup threads; injects read-only repositories, permits only normal TMDB GETs, blocks actions, and uses canonical routes including serialization/gzip. Public Movie shell results are fixtures. Test data writes remain solely in OS-temp. No production catalog/config/media writes, background scans, acquisition submissions or real player launches. The initial RAF-based viewport samples are diagnostic only; hidden tabs can throttle RAF. Final comparisons must sample committed DOM/layout in a MutationObserver microtask, with visibility recorded, and avoid claims of actual screen paint.

## Implementation sequence

1. Add deterministic tests: hold catalog while auxiliary requests must wait; release it on success/error; hold offscreen enrichment while visible cards finish. Observe baseline failures. Add queue tests for order, exact membership, capacity, failed batch continuation and cancellation.
2. Update the existing owners and a small TV enrichment scheduling helper; no duplicate field/progress rules.
3. Verify Node/Python contracts, complete named compiled desktop suite, and fresh read-only actual-data Library/Discover captures. Compare both first cards and fully populated visible cards. Keep failures/logs and use a distinct sequential900-active-second check ledger, below1GiB. Do not reset earlier ledgers.
4. Reassess measured bottlenecks. Do not declare the original goal achieved from a request-start bound or helper tests alone. Network/provider variance and residual delay must be reported plainly.

## Acceptance matrix

| Scenario | Exact result | Verification |
| --- | --- | --- |
| Initial Library pending | No options/review/list-descriptor request competes with catalog | Held-response desktop test |
| Initial Library success/error | Auxiliary data loads once after settle; correct card or error; retry works | Same test, both outcomes |
| Discover with slow offscreen details | Every visible pending card populates while background remains held | Deterministic desktop test |
| All39 pending cards | Full fields for every card; each identity attempted once | Existing39-card check plus new scheduling test |
| Partial failure/abort | Other batches continue; canceled queue stops; stale response cannot merge | Queue tests and existing close/late-response cases |
| Hidden retained tab/narrow/wide grid | All identities processed; normal cache/navigation/card geometry | Existing desktop specs and fallback queue case |
| Playback/selection/list/filters | Existing exact actions and state remain | Existing named desktop/Python/Node checks |
| First real-data useful viewport | Measured initial cards and complete visible labels/artwork improve; no fake warm-return timing | Fresh isolated read-only CP shell, same canonical owners |

## Verification and rollout

Use the existing runner with a new evidence root/config; one worker, no flaky retries, fixed temp roots and local artwork for deterministic regression. Real-provider performance captures are separately labeled. No hardware/SSD stress or filesystem cache flush. Run normal focused checks before the full desktop gate; broaden only for changed owners or new concerns. Preserve production dist and any running app. Finish with precise source/isolated versus live status and a contract comparison; a normal future build/start activates source changes.
