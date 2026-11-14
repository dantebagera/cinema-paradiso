# CP performance findings and discussion record

**Status:** Investigation record and discussion draft, 2026-10-14, Africa/Cairo. [Master plan and open decisions](2026-10-14-cp-performance-plan.md). This records observations and proposals; it does not approve implementation or claim the slowdown is fixed.

## What Dante reported and decided

- Loading, page switching, scrolling and card expansion feel slower since adopting Mostafa's UI.
- Library Next feels slower than Discover, despite the owned posters being cached.
- Library was substantially faster in Dante's earlier experience with the old UI.
- Background artwork is an intentional enhancement and must remain. Removing it is not the desired fix.
- Dante proposed caching owned wallpapers and optimizing loading, then asked to collect all suggested improvements in Markdown and continue developing the plan.

Treat the historical experience as a report to explain. Failure to reproduce it in a controlled probe does not disprove it.

## Evidence scope and limitations

Most timings below came from temporary headless Chromium desktop sessions using the current running backend or frozen responses. New and old static bundles were compared without starting the old backend. The old-copy configuration points to main's data root, so it is not an independently running historical system or database snapshot.

The installed CP window was inspected through the computer-use tool. At that inspection it exposed 75% zoom and a 1536×816 screenshot; controlled probes used 1920×1080 or 2048×1040 viewports. Those conditions are not equivalent proof of native-window frame latency. Match them in Stage 0 of the master plan.

Many probes defined card readiness as a changed first-card title, sometimes followed by two animation frames. That does not mean every poster/backdrop has loaded, every pixel has been painted, or the full page is interactive. Report these endpoints separately in future probes.

Probe code was executed from shell stdin; outputs and traces were inspected in the chat. Raw new probe scripts/JSON were not saved as a reproducible verification artifact in this investigation. The summaries here preserve the findings, not a substitute raw-results archive. Earlier `docs/verification/mostafa-performance/` files concern the earlier task and must not be cited as containing these new results.

Early browser-route experiments used controlled responses and can disable browser HTTP caching. They support UI-work comparisons, not native HTTP-cache claims. Later real pagination checks used a read-only fetch guard, and static interception was removed before warmed pagination measurements. The guard blocked mutating API operations while allowing identified read-only POST query routes.

No CP source, configuration, catalog, tests, production dist or service lifecycle was intentionally modified. Temporary browser CSS/bundle overrides were diagnostic only and disappeared with their sessions. The catalog profile used a read-only SQLite URI and `query_only=ON`, without importing/running the Flask app. Ordinary running services were not frozen; production background activity could continue.

## F1 — background artwork has a measurable drawing cost

**Confirmed mechanism:** `cardArtwork.js` supplies an image under a gradient with `background-size: cover`. Loading an image from disk/cache does not remove its decoding, scaling, blending or raster work. Rasterization converts drawing commands into pixels.

**Controlled probe:** Same page, data, card dimensions, posters and gradients; temporary CSS removed only Unified Movie card background image layers. Warmed scrolling and four expand/collapse cycles were repeated in on/off/on/off order.

| Scroll sample | Background image | Sum of raster-worker work | Frame observation |
| --- | --- | --- | --- |
| First on | Present | 3867.5 ms | 120-frame sequence stayed approximately 60 Hz. |
| First off | Removed only for diagnosis | 2878.7 ms | One long frame; not a consistent frame-rate improvement. |
| Second on | Present | 3907.3 ms | Approximately 60 Hz. |
| Second off | Removed only for diagnosis | 2896.2 ms | Approximately 60 Hz. |

This is approximately 26% less **summed raster-worker work** with artwork removed. Worker sums can exceed elapsed time because work runs in parallel. It is not 26% faster CP, not a promise for image caching, and not evidence that backgrounds are the only cause.

Expansion click-to-frame samples remained around 195–225 ms in this probe. Removing backgrounds did not yield a material consistent expansion-response improvement. The proposed product fix retains artwork and needs its own measurements.

**Owners:** `src/components/movie-card/cardArtwork.js`, `MovieCard.jsx`, `SharedMovieCards.jsx` and existing shared callers. **Plan:** P1/P6, D2/D3.

## F2 — owned poster caching exists; owned wallpaper caching is missing

Actual cards inspected on current Library page 1:

- Buddy, Hope and Practical Magic 2 used `/api/assets/<checksum>` for both the visible poster and collapsed background.
- Expanding Buddy selected a separate `https://image.tmdb.org/t/p/w780/...jpg` wallpaper while keeping the local poster. This establishes the selected remote source, not a completed-download timing or global cache census.
- `MediaAssetService.VALID_ASSET_TYPES` currently contains `poster`, `portrait`, `discover_poster`; it does not include a backdrop asset type.
- Canonical projection selects ready local poster bindings. `canonical_card_projection` deliberately defers `backdrop_url`; details projection includes it.
- The shared card chooses a supplied backdrop, otherwise its poster. Loaded details can therefore change which background it selects. Do not assume every collapsed card always uses a separate remote wallpaper or always uses a poster.

**Conclusion:** Extending the existing managed cache to owned backdrops is a concrete enhancement opportunity. It primarily removes provider/network dependency after successful caching. It does not automatically eliminate image drawing cost or Library's page-data wait.

**Plan:** P1. Unresolved: coverage/backfill, image sizes/quality, storage/retention, replacement, retry and exact projection contract (D1–D3).

## F3 — Home does more immediate work than the old previews

With equivalent saved responses, one comparison found roughly 5,592 total page elements and 175 poster/Continue-style cards in the new Home, versus 2,596 elements and 69 such cards in the old Home. Counts depend on current content and which card types are included; they are not fixed product limits.

Source comparison shows old Upcoming was sliced to six visible entries, while the new rail maps the returned collection. Trending and trailer display also changed from bounded previews to full rails. Native image lazy loading does not avoid creating the cards, text, controls and their React work.

**Causal follow-up:** A temporary in-memory override limited only new Home's Upcoming, Trending and trailer rendering to six entries while keeping the supplied data and backend responses. No product file was edited. In two interleaved samples:

- Full Home subtree: 5,457 elements, 118 Upcoming/Trending posters and 88 trailer cards.
- Diagnostic preview counts: 2,588 elements, 12 Upcoming/Trending posters and six trailer cards.
- Measured return work fell from roughly 0.56–0.63 s to 0.47–0.52 s; layout work fell from roughly 42–64 ms to 21–29 ms in the chosen measurement window.

This demonstrates an offscreen-content contribution, not a justification to truncate accessible content. Some earlier whole-return samples were about 0.62–0.78 s new versus 0.48 s old; endpoints/settlement differed and must not be combined into one benchmark series.

**Plan:** P3. Retain full rails; resolve D5 before implementation.

## F4 — broad updates can involve retained hidden pages

`App.jsx` retains previously visited workspace panels and polls power status every five seconds. Its power response updates application state. A React instrumentation probe observed a commit involving hidden Home while Library was visible during an idle interval. Component counts from that probe are not treated as a precise audited rerender census.

This application structure predates the redesign. Larger retained content can amplify its cost, but its share of the reported native sluggishness has not been quantified. Do not disable polling, notifications, catalog events or Follow as an optimization.

**Plan:** P2; measure actual dependencies and unnecessary versus necessary renders before choosing the state boundary change.

## F5 — repeated list matching is a CPU hotspot, not a newly introduced rule

A CPU profile of repeated Library expansions highlighted `listsForItem`, `movieIdentityKeys` and title normalization in `libraryUtils.js`. Library renders also call `movieHasSystemState` for watched/watchlist. Discover uses its own `listsForDiscoverMovie` matching rule, sometimes repeatedly for the same card.

These rules and repeated calls already existed in the old UI. They identify optimization work, not proof that Mostafa introduced the historical slowdown. Any indexed/reused computation must preserve the different matching rules, canonical precedence, list order and immediate curation updates.

Earlier `listCatalogFilters.js` default-browsing/metadata-reuse repairs are present and distinct from this membership hotspot. Do not replace one with a competing implementation.

**Plan:** P4.

## F6 — Library versus Discover today is a different question from old versus new

A real-current-backend sequence at 39 cards per page found:

- Library revisits still requested `/api/library/search/advanced`; one page-2 revisit produced **zero image requests** yet took about 0.77 s to show changed card text. The data request took about 0.47 s.
- Revisited Discover pages reused the backend's accumulated search window. Some data responses took 5–10 ms and changed-card display about 0.07–0.17 s.
- First Discover page fetches in the same sequence could take about 0.56–0.88 s. Discover is not universally instant or inherently faster on a cold query.
- Both screens use the shared `<img loading="lazy">` poster component; background visibility deferral is also present. Missing Library lazy loading was not established.
- Local asset responses use checksum URLs and long immutable cache headers. Managed disk assets, browser cache, decoded images and query-result caching are separate mechanisms.

**Conclusion:** Repeated Library data preparation explains a current wait even with cached images. It does not, by itself, explain the historical old/new report.

**Plan:** P5 and D6.

## F7 — the matched old/new Library test did not reproduce a large UI-only gap

The old copy's static bundle was supplied in disposable browser sessions. It was not launched as a second production app.

AST comparison found these current/old functions identical: `advanced_library_search`, `_library_cards_payload`, `_library_card_item`, `_catalog_library_item`, `_maintenance_upgrade_path_keys`, `CatalogStore.library_page`, `_candidates_for_path_keys`, `_library_effective_cte`.

With identical saved current page responses, equal 39-card pages, warmed images and repeated Next/Previous actions:

- Old: approximately 185–244 ms.
- New: approximately 202–217 ms in the collected samples.
- New with backgrounds temporarily removed: approximately 200–217 ms.

No large pagination regression or meaningful background-removal benefit appeared in that particular UI-only test. This does not cover full native painted readiness, different zoom, cold wallpapers or longer accumulated browsing state.

With actual current-backend requests in interleaved old/new/new/old runs, both showed variable long waits: old approximately 0.65–1.41 s; new approximately 0.71–1.61 s. Most variation tracked backend response time; the front-end interval after the response was broadly similar in those samples. These small uncontrolled-load samples do not establish statistically equivalent overall runtime performance.

**Conclusion:** The current query and backend wait exist with the old interface too. Do not claim that Library query caching changed during the redesign, or that the historical regression has been explained. Historical data/process/cache/display conditions still need a matched reproduction.

## F8 — Library count/sort is a directly measured backend cost

A standalone read-only connection invoked the existing catalog owner against the current Movie catalog. It did not run the Flask app, write a fixture into production, change pragmas to WAL or permit database writes. Profiling overhead and a separate process make these diagnostic stage timings, not exact production request totals.

| Query | Total diagnostic time | Count | Page selection / sorting |
| --- | --- | --- | --- |
| First page, summary initially uncached | 530 ms | 78 ms | 185 ms, plus initial facet work. |
| Page 2 | 272 ms | 76 ms | 190 ms. |
| Page 3 | 268 ms | 77 ms | 184 ms. |

Page 2 called `_catalog_sort_key` 3,946 times. The owner counts and orders matching entries before selecting 39. Candidate/canonical projection in this particular probe was comparatively small. Other route-level work and contention can add time.

**Conclusion:** There is an identifiable catalog-query optimization target. It predates the UI change. Evaluate SQL/index improvement or valid result/count reuse with preserved ordering/freshness; do not promise to recover the entire measured time or assume all requests are identical.

**Follow-up without cProfile:** A later read-only production-file probe measured warm full-owner calls at 186.0, 193.1 and 189.8 ms. Direct count statements were approximately 77–85 ms and page selection 104–114 ms; the first full-owner call was 483.3 ms while initial summary/facet work was uncached. These are distinct runs, not additive stage measurements from one identical request. The earlier 268–272 ms profiled measurements included instrumentation overhead and must not be advertised as 260 ms of assured recoverable latency.

**Plan:** P5, D4.

## F9 — startup, expansion and painting still contain unresolved work

- One Home trace showed statistics around 2.7 s and Movie/TV Continue Watching around 2.4 s combined, with sequential Movie then TV reads. Some equivalent reads occurred more than once during startup/capability resolution. Current costs and dependencies need a reproducible new trace.
- Trending and Upcoming are awaited together before Home commits their results; Trending exclusion is part of the current Upcoming presentation rule. Earlier partial readiness observations do not justify changing that rule.
- Earlier expanded-card traces showed more layout work in the new UI, sometimes about 40–70 ms versus about 5 ms old. Later isolated first-Library runs varied substantially. Extra layout is an observation, not an isolated explanation for all expansion latency.
- A temporary grid-to-flex substitution in the rail preserved measured geometry but did not produce a consistent improvement. It is not the recommended fix.
- ResizeObserver instrumentation did not reveal an unbounded callback loop in the sampled expansion. Do not label it a proven observer leak.
- Scrollbar custom properties/attribute updates, compositing/layer behavior and image sizes remain hypotheses to profile. Do not optimize them merely because they appear in traces.

**Plan:** P6/P7 and backlog B3–B5.

## F10 — database condition, query plan and isolated index/statistics experiments

Dante asked whether anything in the database itself was slowing the application. The source was opened through a read-only SQLite URI with `query_only=ON`. No live ANALYZE, schema/index change, vacuum, repair or data cleanup was performed.

### Current database observations

- File size: 171,737,088 bytes, approximately 164 MiB; 41,928 pages of 4096 bytes.
- `PRAGMA quick_check(1)` returned `ok`. This is a bounded structural check, not proof of every application-level identity/relationship contract.
- Freelist count: zero. There is no demonstrated unused-page bloat for a vacuum to reclaim; file size alone is not a diagnosis.
- Table counts: 3,948 media files, 3,947 canonical movies, 3,947 canonical file bindings, 7,612 provider snapshots and 23,370 managed assets. The default accepted/published query returned 3,946 eligible identities; that is a different count from all file records.
- Existing indexes include file identity/status/added-time indexes and provider snapshot movie/provider and path indexes. This is not a database with no indexes.
- No `sqlite_stat*` tables were present. The effect of planner statistics needed an experiment; absence alone did not establish a bottleneck.

### Query-plan finding

EXPLAIN QUERY PLAN for the existing default count and page query reports `SCAN mf`, indexed joins and correlated subqueries for selected/fallback metadata. Several subqueries use temporary B-trees for their ordering; the final page query also needs temporary ordering. The existing added-time index does not directly satisfy the complete effective ordering, which includes computed date selection, canonical/override display title and `cp_sort_key` tie breaking.

This gives a concrete query-work explanation: eligibility and effective metadata/order are resolved across the matching library before returning one small page. It is not proof that records are corrupt, that duplicate user movies should be deleted, or that an arbitrary index will solve the delay.

### Discarded in-memory experiments

A read-only backup of the database was copied into SQLite `:memory:`. All experimental changes below were applied to that disposable connection only. Memory-copy timings must not be compared directly with the production-file timings as a promised gain from moving the product to RAM.

1. **Planner statistics:** Before ANALYZE, count samples were 23.5–25.0 ms and page samples 48.4–48.7 ms. After ANALYZE on the RAM copy, count was 21.4–22.8 ms and page 45.7–46.1 ms. The planner changed some snapshot index choices; the improvement was small.
2. **Candidate covering index:** Starting with statistics present, a diagnostic index on `provider_movie_snapshots(movie_key, provider, updated_at DESC, snapshot_key, path_key)` was added in RAM and statistics refreshed. Count changed from 22.3–23.7 ms to 19.0–19.4 ms; page selection from 47.1–50.2 ms to 45.5–47.0 ms. Temporary-sort plan nodes reduced from four to two for count and seven to five for page, but the principal work remained.
3. The full ordered list of 3,946 eligible identities was unchanged in that single default-query comparison. This is not regression coverage for all source fallback, override, filtering and ordering cases, and the candidate index is not approved for production.

**Conclusion:** The current database shows no obvious structural failure or reclaimable-page bloat. Repeated query structure and sorting are confirmed costs. The specific statistics/index experiments produced modest improvements only, so neither should be sold as a large standalone fix. P5 should examine the authoritative effective-query work and safe reuse before deciding which query/schema change, if any, is worthwhile. The historical old/new speed question remains open.

## Corrections and rejected directions

| Earlier statement or idea | Current record |
| --- | --- |
| Removing backgrounds as a performance fix | Rejected by Dante. Preserve the enhancement and improve its implementation. |
| Six-item Home limit | Throwaway causal probe only; no product truncation approved. |
| More page elements proves the whole slowdown | Incorrect inference. It demonstrates more content; a bounded follow-up established one contribution, not every symptom. |
| The rail grid is the cause | Not established; grid-to-flex probe did not help consistently. |
| The Library query explains why the UI update slowed it | Withdrawn. The relevant code also exists in the old copy. |
| 26% faster app, or 26% expected caching gain | Unsupported. The measurement was summed raster work with backgrounds removed. |
| Warm page turns below half a second are guaranteed | Unsupported. This is a provisional discussion target, not a demonstrated result or approved threshold. |
| The profiled 260–270 ms is assured removable database time | Incorrect. Instrumentation affected that run; later non-profiled warm owner calls were approximately 186–193 ms. No entire-stage saving is guaranteed. |
| Missing statistics or one additional snapshot index is the main fix | Not supported by the discarded-RAM experiments; improvements were modest. |
| The entire old CP environment was benchmarked | Incorrect. The old UI was tested with current data/backend or saved current responses. Its original backend/data/native environment was not independently run. |

## How to extend this record

For each new observation, add an F identifier with: user-visible symptom; exact checkout/process/bundle and display conditions; cache state and fixture identities; measured endpoint and method; confirmed mechanism versus hypothesis; affected owner/contract; and the next distinguishing test. Save scripts and raw outputs for future measurements.

Record product decisions in the master plan's R/D tables and update the appropriate P package. Rejected proposals stay labeled as rejected so a future implementer does not revive them as an approved workaround. Do not overwrite historical evidence or move an open question into the approved column without Dante's decision.
