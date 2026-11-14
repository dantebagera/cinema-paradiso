# CP desktop performance improvement plan

**Status:** Discussion draft, 2026-10-14, Africa/Cairo. Dante authorized writing and extending Markdown planning files. Product implementation, migrations, artwork backfill, production builds, restarts, commits and publication are not approved by this request.

**Goal:** Improve startup, page switching, Library pagination, scrolling and card expansion while retaining the new interface, its backgrounds and all existing product behavior.

**Architecture:** Improve the existing artwork, catalog query, shared card, list-membership and application-state owners. Keep Movie, TV, IPTV and acquisition ownership separate. Select and verify changes independently so that each claimed improvement has its own evidence.

**Tech stack:** Existing React 19/Vite frontend, Flask/Python services, SQLite catalog and managed local artwork service. No dependency upgrade is proposed.

**Discussion and evidence:** [Findings, corrections and measurements](2026-10-14-cp-performance-findings.md). This master plan follows the CP plan template and remains open for discussion. It is not an execution-ready implementation plan while the decisions below remain unresolved. The historical [Mostafa performance plan](2026-10-12-mostafa-performance-plan.md) records earlier work; its approval does not authorize this new work.

## Problem and decision

- **What happens now:** Dante reports slower startup, page switching, scrolling and card expansion after the UI integration. Library Next also feels slower than Discover. Current diagnostics identify several costs, but do not establish one cause for all symptoms or reproduce a large historical Library regression under matched conditions.
- **What Dante wants:** Keep the enhanced interface and backgrounds. Improve caching, loading and responsiveness. Bring all suggestions into one evolving plan rather than focusing only on wallpapers.
- **Confirmed:** Background artwork adds raster work during the measured scroll; owned poster backgrounds are already local in inspected collapsed cards; expanded artwork can use remote TMDB backdrops; the managed asset service has no backdrop type. Library performs count/sort work for each page. Home renders substantially more entries than the old previews. Global application updates can involve retained hidden pages. Existing list membership searches repeat during card rendering.
- **Suspected:** Unnecessary image resolution, repeated decoding, broad updates, offscreen rendering and measurement scheduling may amplify the perceived sluggishness. Their individual contributions to the installed-window experience are not all quantified.
- **Unknown:** The cause of the reported historical Library speed difference; the remaining expansion delay; the contribution of GPU/compositing, installed-window settings, background services and cold versus warm caches. Do not substitute a plausible explanation for a completed diagnosis.
- **Scope:** Desktop Movie/Home/Library/Discover performance and shared consumers exposed by changed owners. TV and IPTV receive regression verification where they share components, without adopting Movie-specific caching or catalog rules automatically.
- **Explicit exclusions:** Removing backgrounds, reducing accessible rail contents, changing sort/filter/identity rules, disabling required refreshes, changing Follow schedules, redesigning controls, mobile work, production data mutation and publication.

### Recorded decisions

| ID | Decision | Status/source |
| --- | --- | --- |
| R1 | Backgrounds remain part of the enhancement in collapsed and expanded cards. | Required by Dante in this discussion. Removal recommendation rejected. |
| R2 | Keep all movies and trailers accessible; the six-item probe was diagnostic only. | Preservation constraint; no truncation approved. |
| R3 | Recap every proposed improvement and keep extending the Markdown discussion. | Dante's latest request; documentation authorized. |
| R4 | Caching owned wallpapers and optimizing loading are the desired direction. | Dante's proposal; exact design and implementation remain pending. |

### Open decisions and discussion queue

| ID | Decision needed | Current recommendation / next evidence |
| --- | --- | --- |
| D1 | Cache coverage: fetch on demand, gradually backfill owned movies, or both? | Consider on-demand retrieval plus bounded background backfill. Measure storage and provider work first. No bulk download is authorized. |
| D2 | Should collapsed cards keep their current poster/backdrop selection, or always show a true wallpaper? | Preserve current selection initially. Always using a wallpaper would be a separate visual/product decision. |
| D3 | What decoded/display sizes and image quality should cached variants use? | Derive sizes from actual desktop card geometry and display scaling. Decide after visual and raster comparisons; no invented resolution or quality percentage. |
| D4 | How should next-page prefetch and page-result reuse work? | Establish query dependencies, invalidation and measured benefit first. Bound speculative work; do not mask an expensive owner with uncontrolled prefetch. |
| D5 | Which Home offscreen-rendering approach preserves arrows, keyboard access and layout? | Compare incremental mounting with browser rendering containment. Choose from evidence; do not introduce a second rail implementation. |
| D6 | Which remaining installed-window differences explain Dante's reported experience? | Reproduce cold/warm pagination and longer browsing sessions at the actual zoom, size and image state. |
| D7 | What performance targets should become acceptance criteria? | Discuss the provisional targets below. No universal speed percentage has been established. |
| D8 | Which work package should be implemented first after design review? | First finish reproducible baselines; then consider artwork ownership and Library query work as separate bounded packages. |

New ideas belong in the backlog below with evidence, ownership and a decision status. Do not silently turn suggestions into approved requirements.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior / exceptions | Affected callers | Proposed behavior | Changes contract? | Dante's decision |
| --- | --- | --- | --- | --- | --- |
| New UI artwork, R1 | Retain backgrounds, gradients, posters and current card appearance. | Shared cards, Home, related rails, Library/Discover/Lists; other shared consumers | Cache and prepare artwork without deleting the enhancement. | No intended visual change; variant quality needs approval. | Keep backgrounds required; implementation pending. |
| Canonical card/detail projections in `canonical_catalog.py` | Card summaries defer backdrop/details; expansion retrieves the richer representation. This is a current implementation contract, not a newly invented user requirement. | Library cards/details, canonical callers | Prefer extending managed asset ownership and details projection first. | Possible if adding backdrops to summary payloads; unresolved. | Pending; do not silently weaken deferred-detail behavior. |
| Existing managed artwork ownership | Checksummed local assets, selected provider/overrides and retention semantics remain authoritative. | MediaAssetService and canonical projections | Add owned-backdrop support through the existing owner. | Asset/schema lifecycle design needs review. | Pending. |
| Movie identity, filtering and ordering | Preserve canonical precedence, list membership, full matching before pagination, stable order and truthful counts. | Library, Discover, Lists, Home | Optimize computations; cache only with correct invalidation. | No intended change. | Preserve. |
| Full Home/credit/related rails | Retain every accessible item and existing arrow, focus and selection behavior. | HorizontalCardRail callers | Defer work outside the useful viewport without truncation. | No intended change; accessibility must be demonstrated. | Preserve. |
| Navigation and card expansion | Preserve page/history state, Back/Forward, scroll return, centering, controls and expanded geometry. | Shared cards and workspaces | Reduce layout/render work while keeping observed behavior. | No intended change. | Preserve. |
| Freshness and Follow | Movie Follow checks each startup and manual Scan. TV Missing/Future unsuccessful searches retry every five hours; lower manual controls remain separate. | App events, Movie/TV acquisition and Home | Limit rendering updates without suppressing required operational work. | No schedule or behavior change proposed. | Preserve existing contracts. |
| Desktop and production boundaries | Desktop only; source, served dist, process and live data are separate facts. | All packages | Verify isolated builds first; activate only with applicable authorization. | No. | Planning only currently authorized. |

If a selected design changes or weakens an agreed contract, present a separate notice headed `## ⚠️ CONTRACT CHANGE — DANTE'S DECISION REQUIRED` with CURRENT RULE, PROPOSED RULE, WHAT DANTE WILL SEE, AFFECTED AREAS, REASON, COST OR RISK, ALTERNATIVE and RECOMMENDATION. A row in this document is not that notice or approval. No test assertion may silently settle an unresolved product decision.

## Current design and ownership

### Baseline recorded for this draft

- Main: `C:\Users\dante\Desktop\cinema paradiso`, branch `master`, HEAD `be511f98846a67a182e5b371ad087938e9344362`, ahead of origin by nine commits at inspection; package version `3.0.0-beta.2`.
- Before these new documents: 80 tracked dirty files and 385 untracked files, including prior tests, plans and verification records. HEAD is not a complete description of this checkout. Preserve all existing work.
- Old copy: `C:\Users\dante\Desktop\cinema paradiso - Copy`. Its configuration points at main's data directory. Its UI was compared without launching its backend or treating it as an independent historical data snapshot.
- Current configuration: main `data` and `cache` directories. Movie catalog: `C:\Users\dante\AppData\Local\Cinema Paradiso\Catalog\catalog-read-cb30c1d963c88463.sqlite`. Managed artwork uses the existing AppData Metadata owner. TV and other domains retain their own stores.
- Most recent identified port-5000 listener: Python PID 23664, `C:\Program Files\Python312\python.exe app.py`, started 2026-10-14 at 21:37:17 host-observed time. Earlier listeners differed. Recheck process/timezone before operational use; PID is not a durable identifier or proof of the exact loaded source revision.
- Current dist references: `index-B51l7aON.js`, `index-DFMDe_8_.css`. Earlier checks found the server serving those references. Reconfirm served bytes before any future live claim. Old-copy entry: `index-pJcXpaa4.js`.
- No implementation, build, restart or live artwork backfill was performed in this investigation. Diagnostic browser overrides and read-only query probes are not product fixes.

| Responsibility | Existing authoritative owner | Entry/callers | Behavior to preserve | Waste or uncertainty to address |
| --- | --- | --- | --- | --- |
| Artwork loading and styling | `src/components/movie-card/cardArtwork.js`; roots in `MovieCard.jsx` | Unified, Continue, Upcoming; RelatedMovieRail/IPTV callers | Existing image choice, gradient, visibility deferral and expanded loading | Image sizing/decoding/raster costs; do not reimplement the observer per screen. |
| Managed local artwork | `services/media_assets.py`; `app.py` asset service/routes | Existing registry, checksum URLs and download lifecycle | Selected provider, overrides, integrity and retention | No backdrop asset type today; extend this owner rather than create another cache. |
| Canonical artwork representation | `services/canonical_catalog.py` | Card and details projections | Identity/provider precedence and deferred details | Local backdrop reference design and invalidation. |
| Library page selection | `services/catalog_store.py::library_page`, effective CTE and sort helpers | `app.py::advanced_library_search` and `_library_cards_payload` | Exact membership, count, order and pages | Repeated count/sort of the same query; current SQL cost measured. |
| Library request/display lifecycle | `src/features/library/LibraryWorkspace.jsx` | Next/Previous, filters, background refresh | Current results, stale-response protection, selection/history | Request wait versus pre/post-response render time; page reuse/prefetch undecided. |
| Discover comparison | `DiscoverWorkspace.jsx`; `app.py::_tmdb_discover_window` | Normal/advanced Discover and related contexts | Dense unique pages, exact final page and filter semantics | Uses retained search windows; not an equivalent cache baseline by default. |
| List membership and identity | `src/utils/libraryUtils.js`, `src/discoverUtils.js` | Library/Discover/Lists and actions | Their distinct identity/matching semantics | Repeated scans and normalization; avoid conflating the two identity rules. |
| List criteria and sorting | `src/utils/listCatalogFilters.js` | Movie/TV list callers as implemented | Prior default fast path and canonical precedence | Earlier fix already exists; preserve it rather than redo it. |
| Global application updates | `src/App.jsx`, Sidebar and status owners | Power polling, Home data and catalog/curation events | Polling, notifications and event freshness | Broad updates involving retained hidden pages. |
| Rails and Home content | `HorizontalCardRail.jsx`, HomeWorkspace/HomeTrailersPanel | Home, credits, related titles | Layout, all items, arrows, focus and return state | Full collection mounting; per-child observation and update lifecycle. |
| Expanded geometry | `MovieCard.jsx`, `expandedCardViewport.js`, `useMovieCardScrollReturn.js` | Shared expanded Movie/TV surfaces | Centering, sticky chrome allowance, poster/body dimensions | Extra layout work observed; exact cause remains unresolved. |
| Scrollbar painting | `scrollbarActivity.js`, `styles/scrollbars.css` | Shared scroll containers | Reveal behavior, native dragging and geometry | Candidate contributor only; no demonstrated independent regression yet. |

## Exact behavior contract

### Frontend, if affected

Preserve the current desktop screens as the visual reference: grid density, card geometry, spacing, typography, backgrounds, controls, default collapsed toolbars and selection. Reuse the existing shared card and rail owners. No new performance setting, duplicate card component or route-specific workaround is proposed.

Proposed work packages, all pending implementation approval:

| Package | Intended behavior | Verification / unresolved boundary |
| --- | --- | --- |
| P1 — owned artwork and preparation | Reuse local owned backdrop files after successful caching. Keep the current poster/background visible while missing artwork is prepared; page data and controls must not wait for a remote wallpaper download. Use the same selection policy across the existing card callers. | Resolve D1–D3. Preserve genuine missing-artwork fallback. Do not fetch full details for every collapsed card merely to obtain a backdrop. |
| P2 — global/hidden rendering | A status update changes the controls/data that depend on it. Retained hidden pages keep navigation state without needlessly repeating unaffected card work. | Trace actual dependencies and measure render counts. Do not stop required polling, operational events or unmount pages wholesale. |
| P3 — offscreen rails | All existing rail entries remain reachable. Prepare nearby items soon enough to avoid visible blank cards, while reducing unnecessary offscreen mounting or rendering. | Resolve D5; verify keyboard traversal, screen-reader access, arrow distance, edge detection, resize and reveal after hidden navigation. |
| P4 — list calculations | Resolve membership/identity work once per relevant data change rather than scanning all list rows repeatedly for each render. | Keep Library and Discover matching rules distinct; update immediately after watched/watchlist/list edits and ownership changes. Preserve the existing list-filter performance fix. |
| P5 — Library pagination | Return the same correctly ordered page with less repeated catalog work; keep stale-response protection and full-row page sizing. | Resolve D4; verify first and revisited pages, rapid Next/Previous, query changes and live invalidation. Image caching alone is not this fix. |
| P6 — expansion and scroll painting | Preserve the complete expanded card and its current return behavior while reducing proven layout/raster costs. | Diagnose remaining costs before selecting a geometry change. Rail grid-to-flex substitution did not improve the tested case and is not the chosen fix. |
| P7 — startup and Home requests | Independent Home panels become useful as their own data is available. Avoid duplicate equivalent in-flight reads and unnecessary sequential waits where semantics permit. | Measure current statistics, Continue Watching, capability resolution and Trending/Upcoming dependency chains. Preserve startup Follow and ownership truth; no automatic request removal. |

Adjacent-page prefetch, separating independent Continue Watching reads, incremental Home data display, and image-size variants are candidates to evaluate, not settled implementation choices. Waiting on both Trending and Upcoming currently also supports their exclusion relationship; do not simply remove that dependency.

### Backend, if affected

**Artwork:** Extend `MediaAssetService` and canonical details ownership. Review whether existing tables accommodate backdrop bindings or require migration before choosing storage changes. Reuse checksummed URLs and existing retention rules. Concurrent requests for the same selected source should share work; failures must leave current usable artwork intact and permit a bounded retry. Resolve worker concurrency, queue priority, disk budget, backfill scope, variant keys and replacement/cleanup policy before implementation. No global cache wipe or production backfill is authorized.

**Library:** Keep the existing POST request shape (`query`, `page`, `page_size`) and response membership, count, order, facets, stats and catalog identity. Profile count, sorting and card projection separately. Evaluate query/index improvement and reusable ordered-result/count work in the existing catalog owner. The database follow-up (F10) found a passing quick check, zero free pages and existing indexes; planner-statistics and one covering-index experiment gave modest gains only in a discarded RAM copy. Do not select a blanket database cleanup or that candidate index as an established fix. Repeat timing without profiler overhead: warm read-only file-owner calls were approximately 186–193 ms, versus the earlier instrumented 268–272 ms. If caching is selected, specify its key, size bound, lifetime and invalidation before coding: normalized criteria and sort, relevant catalog/identity/curation/asset changes, generation captured during computation, and any page-size-dependent representation. A generation change during work must not publish a falsely current cached result. Do not persist stale watched/list/poster state inside a page snapshot without the corresponding invalidation.

No new Movie/TV/IPTV identity authority or parallel business-rule implementation is proposed. Any schema migration needs an explicit backup/rollback design and separate authorization for production execution. Retire obsolete repeated paths only after callers and regression evidence demonstrate that the selected replacement owns them.

## Implementation sequence

These are proposed stages, not permission to execute. Each selected package needs its unresolved design decisions resolved and an executable, scoped plan before code changes.

- [x] Capture the discussion, measured findings, corrections and authorization boundaries in Markdown.
- [ ] **Stage 0 — settle the reproducible baseline:** Save reusable probe scripts and raw results; compare the same Next/Previous, startup, scrolling and expansion paths in old/new UIs under equivalent conditions. Include the actual installed-window geometry/zoom and longer browsing sessions. Separate data arrival, text/card display, visible poster readiness, wallpaper readiness, main-thread work and raster worker totals.
- [ ] **Stage 1 — review P1 artwork design:** Resolve D1–D3; map the existing asset lifecycle and detail projection contract; specify on-demand caching, failure/retry, variants and migration needs. Verify that the visual enhancement stays intact.
- [ ] **Stage 2 — review P5 Library owner improvement:** Profile the confirmed SQL hot path and current response projection; select an index/query/reuse design with complete invalidation and concurrency semantics. Keep the historical-regression question separate from an independently worthwhile optimization.
- [ ] **Stage 3 — review P2/P4 repeated UI work:** Trace global state ownership and list-matching call sites; pin the distinct matching semantics; isolate updates and remove repeated calculations through the existing owners.
- [ ] **Stage 4 — review P3/P7 offscreen/startup work:** Select a rail approach and request-coordination changes only after lifecycle/accessibility and data dependencies are clear.
- [ ] **Stage 5 — complete P6 expansion/painting diagnosis:** Retest with artwork retained; select only a change whose causal benefit is reproduced. Audit scrollbar/compositing only where traces point to them.
- [ ] **Stage 6 — implement approved packages independently:** Add meaningful failing regressions, change the authoritative owner, verify the package, and review the result before combining timing claims. Execution method is not selected by this draft.
- [ ] **Stage 7 — combined isolated verification:** Check compiled desktop behavior, all shared consumers and the agreed acceptance matrix. Report exact failures and limitations.
- [ ] **Stage 8 — production activation, only if separately approved:** Recheck process/configuration/data/bundle ownership, establish recovery, activate and inspect the installed window. No commit, push, release, package or shutdown is part of this plan by default.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Evidence |
| --- | --- | --- | --- | --- |
| Owned wallpaper already cached | Expand, collapse and reopen the same movie | Existing background appearance retained; selected wallpaper comes from managed local storage with no remote wallpaper request. | Artwork/details/shared card | Asset tests plus compiled URL/network and visual assertions. |
| Missing or failed wallpaper | Load page and expand while provider is slow/offline | Page data and controls remain usable; existing poster/background fallback remains; failure does not erase cached good artwork or start unbounded retries. | Asset owner/card | Slow/failing fixture and repeated-action test. |
| Duplicate requests / selected source changes | Request same asset concurrently, then change metadata source or artwork | Bounded shared work; correct new identity wins; late old completion cannot overwrite current artwork. | MediaAssetService/canonical | Concurrency, stale completion and integrity tests. |
| Cold and warm Library pages | Next, Next, Previous, Previous, Next | Correct identities, row count, order and page labels; separate API/card/poster/backdrop timings improve against the agreed baseline. | Catalog + Library | Matching 39/other full-row fixtures, API and compiled tests. |
| First/final page or restrictive criteria | Navigate and change filters/sort/page size | Full valid nonfinal pages; exact final page/count; no stale or duplicated results. | Library/Discover contracts | API and paging browser suites. |
| Catalog/list/poster changes while results are reused | Complete a fixture download/import or edit watched/list/artwork, then revisit page | Fresh relevant membership, counts, badges, selection and artwork; no stale generation published. | Catalog/curation/asset events | Existing completion/following-refresh fixtures plus new invalidation assertions. |
| Rapid navigation and Back/Forward | Issue overlapping pages; revisit expanded cards | Latest intended response wins; current history, scroll, focus and selection retained. | Workspaces/card lifecycle | Repeated desktop and adverse-response tests. |
| Global power update while another page is visible | Poll unchanged status, then a genuine change | Required status remains current; unrelated hidden card work is avoided; no disabled Follow/notifications. | App/status owners | Render-count and event tests plus idle trace. |
| Full Home/credit/related rails | Reach end with arrows and keyboard; resize; leave and return | Every original item remains accessible; correct geometry/edges/focus and prompt visible artwork. | HorizontalCardRail/shared callers | Compiled populated/long-content, loading/empty/error and accessibility assertions. |
| Large lists and conflicting identities | Render and edit membership/filter/sort | Exact existing matching semantics and order; immediate updates; reduced repeated computation. | Library/Discover/list helpers | Identity adversity and operation-count regressions. |
| Expanded long card with late content | Repeated expand/collapse, change selection and return | Current layout, centering, controls and scroll return retained; no observer/layout feedback loop. | MovieCard/viewport owner | Long-content compiled fixtures and layout trace. |
| Shared TV/IPTV consumers | Browse and use relevant shared cards | Shared visuals/loading remain correct; domain-specific identity, caching and acquisition boundaries retained. | Shared consumers | Relevant fixture suites; no production provider/download action. |
| Startup under slow independent Home requests | Open CP, navigate away/back while requests complete | Usable shell; truthful loading/error states; no stale response replacement or lost startup Follow check. | App/Home | Request timeline and compiled fixtures. |

## Verification and rollout

- **Baseline:** Current diagnostics are summarized in the findings file. No fresh product regression/full-suite run was performed for this documentation task. Historical passes or exceptions are not current-checkout proof. Recheck dirty source, effective data roots, listener and served bytes before implementation.
- **Isolation:** Use `CP_TEST_MODE=1`, a unique OS-temp `CP_TEST_ROOT`, and `CP_TEST_DIST_DIR` within it. Do not use production media/data as writable fixtures. Python API/qBittorrent fixtures require the appropriate embedded test mode. The existing Playwright wrapper explicitly selects system qBittorrent; preserve its scenario-specific setup rather than assuming one mode fits all tests.
- **Focused backend commands, after source approval:** `.venv\Scripts\python.exe -m unittest tests.test_media_assets tests.test_canonical_catalog tests.test_catalog_store tests.test_advanced_library_api`, with the isolated environment established first. Extend the named existing owners' tests for the selected package, not test-only expectations that change behavior.
- **Focused frontend commands, after source approval:** `node --test tests/list-catalog-filters.test.mjs tests/list-catalog-performance.test.mjs tests/browser_ownership_cache.test.mjs tests/home-trailer-model.test.mjs`; add meaningful package-specific render/identity/lifecycle checks as designed.
- **Compiled UI:** Build to the isolated dist with `npm.cmd run build -- --outDir <isolated-dist>`. Use `tools/run_playwright_e2e.ps1` with the appropriate fresh scenario fixtures. Relevant existing specs include `card-artwork-performance`, `movie-scroll-return`, `continue-watching`, `following-refresh`, `app-smoke`, `discover-paging`, `lists-layout`, `scrollbar`, and relevant native-TV/shared-card specs. Do not run direct Playwright commands that accidentally start a production service.
- **Broader suites:** After focused checks pass, run the affected full Node/Python and compiled desktop gates. Preserve assertions and disclose failures, skips and fixture limitations separately.
- **Cache measurement discipline:** Distinguish managed files, browser HTTP cache, decoded-image reuse, catalog/query-result reuse and GPU/raster cost. Browser routing can disable HTTP caching; an intercepted saved-response experiment is not evidence of native cache speed. Record this for each probe.
- **Comparison discipline:** Freeze or identify equivalent response identities, row counts, criteria, image state and process load. Interleave old/new samples and report distributions, not a single best sample. Separate cold first use, warmed first visit and repeated visits. Headless results do not establish the installed PWA's frame responsiveness.
- **Provisional goals, D7 pending:** Cached owned wallpapers use local URLs; reduced repeated catalog sorting/counting and unaffected-page rendering are demonstrated by operation counts. Warm Library changes below 500 ms are a discussion target, not a promise or an approved universal threshold. No whole-app percentage is established; the 26% artwork result was raster-worker work with backgrounds removed, not an expected retained-background improvement.
- **Live work:** Requires applicable separate authorization, consistent backups and verified process/configuration/data/bundle ownership. Do not launch the old copy against main's data. Production artwork backfill and any schema execution need their own reviewed scope.
- **Reporting:** Distinguish documentation, source changes, isolated tests, compiled desktop and installed-window/live proof. Compare every result with approved contracts and state remaining differences, even when tests pass.

## Future ideas and discussion history

| ID | Idea / correction | Status and next step |
| --- | --- | --- |
| B1 | Bounded adjacent-page/artwork prefetch after idle | Candidate; measure usefulness and cancellation before selecting D4. |
| B2 | Persistent normalized sort keys / appropriate index, or generation-aware ordered-result reuse | Alternatives for P5. Profile and compare; do not implement both by default or change sort semantics. |
| B3 | Image variants and measured layer/compositing adjustments | Candidate for P1/P6. No blanket `will-change`, per-card GPU layers or unbounded decoded-image retention. |
| B4 | Coalesce repeated Home reads and overlap independent Movie/TV Continue Watching reads | Candidate for P7; preserve complete results, errors and operational timing. |
| B5 | Inspect shared scrollbar attribute/style invalidation | Hypothesis only; preserve reveal/drag behavior and measure before changing it. |
| B6 | Restore the old UI, remove collapsed backgrounds, or cap rails at six entries | Not selected. Background removal rejected; content caps were diagnostic only. |
| B7 | Treat Library's current query latency as proof of the historical UI regression | Withdrawn inference. Identical backend functions and matched tests do not support that causal claim. |
| B8 | Database statistics, unused space and targeted snapshot indexes | Investigated in F10. Quick check passed; zero free pages; no live mutation. RAM-only statistics/index changes produced modest gains, not a selected standalone fix. |

Continue discussion by adding a finding to the linked findings record, then updating the relevant D/P/B identifier and its status here. Keep one authoritative decision entry rather than competing plans with different approvals.
