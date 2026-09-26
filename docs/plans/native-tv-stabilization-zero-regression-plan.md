# Cinema Paradiso: restore the current baseline and complete TV parity

Date: 2026-09-18
Status: Dante approved implementation with 'go'. Implemented in worktree 0870; qualification evidence is tracked in `docs/verification/native-tv-stabilization/implementation-report.md`.

## Objective and agreed scope

Deliver the four requested repairs without losing behavior from either existing checkout:

1. Restore current Desktop features omitted from the TV worktree, including More Like This and other uncommitted improvements.
2. Bring Library and Discover search/filter behavior to TV, reusing the existing interface and query machinery where appropriate.
3. Complete TV detail actions and information, including trailers and the SAME StreamIMDB player already used by movies.
4. Diagnose and repair season-release search timeouts.

Separate visual redesign is deferred. Desktop only. Order: baseline preservation, season-search reliability, search/filter parity, TV details/actions, integrated qualification.

Zero regression is the acceptance requirement. Test counts alone cannot guarantee it: require evidence against the actual current Desktop behavior, the existing TV behavior, the compiled UI, and the external paths exercised. Unknowns and failures stay visible; they do not become passes by exclusion.

## Workspace, data, and authorization boundaries

- Implementation checkout: `C:\Users\dante\.codex\worktrees\0870\cinema paradiso`.
- Read-only reference checkout: `C:\Users\dante\Desktop\cinema paradiso`.
- Both currently resolve to `adfa90a2e984f59585c7635e839f0c594b74b4cc`; both contain uncommitted changes.
- Preserve both sets of changes. No reset, clean, wholesale replacement, new worktree, staging, commit, push, release, or package operation.
- The worktree's ignored configuration was copied from Desktop. It includes original credentials and live data/cache/library paths; TV is enabled with `G:\TV`. Do not expose credentials or treat this as a disposable configuration.
- Do not start `run.bat`, restart CP, or stop Dante's application. Dante controls normal application startup. Before any future live check, identify the actual process, checkout, loaded bundle, and configured data owner.
- Following implementation approval, use isolated test processes only, with unique OS-temporary `CP_TEST_ROOT`, `CP_TEST_MODE=1`, isolated ports, and fake download/player adapters. A test fixture must prove its roots before imports/startup.
- Real search/provider diagnostics may read responses and logs; they must not submit downloads, enable monitoring, import media, or mutate live catalogs. The current TV search route records decisions, so it is not a read-only live probe: use an isolated acquisition store or the transport directly for diagnosis.
- Keep movie catalog, TV catalog, IPTV stores, acquisition decisions, and qBittorrent transfer state under their existing owners. Do not introduce cross-database SQL joins or move transfer authority out of `jobs.json`.

## Confirmed findings and unresolved facts

| Area | Confirmed from current inspection | Still to establish |
| --- | --- | --- |
| Baseline | More Like This exists as uncommitted Desktop code and is absent from the TV tree. Desktop also changes library search/publication/startup and native-player code. | Complete behavior inventory, dependencies, current test health, and relevant ignored runtime assets. |
| TV search | `TVWorkspace.jsx` has a separate simple toolbar. `TVMetadata.discover()` accepts only query/page. | Full parity mapping, performance, and provider support for combined criteria. |
| Streaming | TV and movies already use `StreamModal` in `src/App.jsx`. TV buttons depend on a separate empty template. | Reliable playback within CP, subtitles, controls, episode switching, and close/unmount behavior. |
| Trailers/details | TV refresh requests external IDs and credits, not videos; no TV trailer control exists. Credits currently cover the latest season rather than the aggregate series. | Other missing detail actions compared with the restored movie UI. |
| Timeout | TV calls Prowlarr synchronously with a 20-second timeout. TV injects the raw configured trusted-indexer list; movies resolve the effective indexer mode/list. | Actual failing request, provider/indexer durations, correct category/capabilities, and whether list selection contributes to this failure. |

Earlier evidence in `docs/verification/native-tv/implementation-report.md` and `final-qualification.txt` is historical. The 1,299 Python / 95 Node / 5 TV browser checks did not include the omitted Desktop changes and do not qualify this repair.

## Phase 0: preserve and characterize both baselines

Before source changes:

1. Re-read both Git states and applicable instructions. Capture tracked, untracked, deleted, and relevant ignored build/runtime dependencies in a redacted manifest with hashes. Exclude credentials, media, databases, and caches from ordinary source artifacts.
2. Make an external, access-restricted backup of the source changes from BOTH checkouts, including untracked feature/test assets and deletion records. A Git diff alone does not preserve untracked files. Leave all originals in place.
3. Build a per-file reconciliation ledger: Desktop change, TV change, intended merged behavior, dependent tests, disposition. Recheck source hashes before applying a reconciliation; incorporate intervening user edits rather than overwriting them.
4. Establish the existing test results using isolated test roots. Record pre-existing failures explicitly. Do not modify tests merely to make a baseline green.
5. Build a behavior inventory across Home, Library, Discover, expanded cards, Movie Lists, Downloads, Settings, playback/trailers/streaming, and IPTV. Use existing tests, code, and safe fixture UI. Mark live observations separately.

Exit: every Desktop-only source/test change and every overlapping edit is accounted for. Any unknown dependency is resolved before merging its feature.

## Phase 1 / point 1: reconcile omitted Desktop work

The four currently overlapping changed files are:

- `app.py`: Desktop relationship/catalog changes plus TV/acquisition composition and prior cold-start repair.
- `src/App.jsx`: Desktop relationship navigation plus TV routing and shared streaming state.
- `src/components/movie-card/MovieCard.jsx`: Desktop expanded-card positioning plus TV card support.
- `tests/e2e/app-smoke.spec.js`: preserve both sets of behavioral checks.

Reconcile these against the common committed ancestor, hunk by hunk. For Desktop-only changes, verify dependency groups rather than assume that a file with no textual conflict is safe alone:

| Dependency group | Existing owners/assets |
| --- | --- |
| Related movies | `services/movie_relationships.py`; `src/api/movieRelationships.js`; `RelatedMovieRail.jsx`; `MovieRelationshipNavigation.jsx`; `SharedMovieCards.jsx`; Discover/Library navigation; related styles/imports; relationship tests. |
| Movie details and card behavior | `src/api/movieDetails.js`; `WorkspacePathBar.jsx`; `movie-card/expandedCardViewport.js`; card/global styles; movie-details and caret-visibility tests. |
| Catalog search and publication | `services/catalog_repository.py`, `catalog_store.py`, `library_ingestion.py`, `library_startup_catchup.py`, related wiring and tests. Preserve the TV tree's first-creation repair. |
| Native player | `native/player/CMakeLists.txt`, `qml/Main.qml`, icon replacement/deletions, `runtime-metadata.json`, and player tests. Verify source/runtime consistency; do not copy a version label without the corresponding executable behavior. |

Do not copy debug logs, production configuration, live databases, or stale `dist` assets into the implementation as feature code. Keep reference verification records clearly attributed to their original run.

Acceptance:

- More Like This works on all currently supported movie-card surfaces, including owned and online details.
- Recommended/Similar remain distinct; All deduplicates correctly; `View all`, breadcrumb navigation, browser Back, ownership actions, and previous search/page/scroll state survive.
- Expanded cards center/scroll correctly without repeated asynchronous jumps; input caret remains visible.
- Movie search ranking, final-card publication, startup catch-up, and native-player changes retain their Desktop behavior.
- TV tabs, series pages, downloads, monitoring state, playback, and movie acquisition compatibility still work.
- Related and previously existing tests pass against the combined source and compiled desktop fixture.

## Phase 2 / point 4: season-search reliability

Authoritative chain: `TVAcquisitionReview.jsx` -> `services/tv_routes.py` -> `TVAcquisition.search()` -> `ProwlarrClient` in `services/source_search.py`. Existing movie search orchestration and indexer-mode resolution live in `app.py` and `services/movie_acquisition.py`.

Investigation before selecting the repair:

1. Recover the actual series/season and error from available logs. If unavailable, request only that missing reproduction detail.
2. Record redacted timestamps, target, query, chosen indexer IDs, category, request duration, status, and exception type. Correlate with Prowlarr/indexer logs without dumping keys or credential-bearing URLs.
3. Compare the TV indexer selection with the configured mode and movie owner. Test empty/custom/all/default selections independently. Separate permission to search an indexer from confidence that a release is safe to acquire.
4. Reproduce fast success, slow success, one stalled indexer, all failed, empty response, unauthorized provider, malformed response, and user cancellation with fixtures. Compare a bounded real read-only search where available.

Repair policy:

- Correct indexer/category/request composition at its existing owner if wrong. Reuse/extract the existing effective-selection policy where it genuinely applies; preserve movie behavior.
- Do not treat a larger timeout as the diagnosis. Define a bounded overall search deadline and meaningful error classification.
- If one stalled indexer is confirmed to block useful results, implement bounded per-indexer work and partial-result reporting in the existing search owner. Keep one owner for execution; no second release-evaluation pipeline.
- If synchronous request limits cannot support the measured normal search duration, use the existing search-job pattern with a TV target. Do not add asynchronous machinery without that evidence.
- Show loading, partial/incomplete results, failure, retry, and cancellation honestly. Ignore late responses after target change or closure; retries must not submit transfers.
- Keep quality decisions, token validation, manifest checks, and qBittorrent submission protections intact. Do not loosen identity checks to make results appear.

Exit: reproduce the original timeout cause, prove the correction, and demonstrate a search that completes or returns useful bounded failure/partial status. A result-free response is not success if the provider actually timed out. Movie source search and configured indexer modes pass regression checks.

## Phase 3 / point 2: Library and Discover search/filter parity

Reuse `AdvancedSearchBuilder.jsx`, `advancedSearchRegistry.js`, `advancedSearchModel.js`, existing field editors, validation, and established toolbar presentation. Extract shared presentation from the restored movie workspaces where needed. Keep the movie defaults and query contracts unchanged; add explicit media/scope capabilities rather than scattered TV conditionals.

TV query execution belongs to `tv_read_model.py`, `tv_metadata.py`, and TV routes/repository. Persist TV facts only in the TV domain. General query parsing can be shared; movie SQL and movie TMDB endpoints cannot accept TV IDs.

Required mapping:

| Existing behavior | TV meaning and acceptance |
| --- | --- |
| Title search, people, keywords, Advanced mode | Same interaction pattern; TV identities and TV results. Match original/translated titles as supported. Role filters distinguish actor, director, writer, and creator rather than treating every credit as cast. |
| Genre, language, country | TV genres and origin country; original language separate from local-file audio language. Preserve movie labels/meaning on movie tabs. |
| Year range, rating range, minimum votes | First-air year for series; rating/votes for series; existing draft validation and explicit unknown-value behavior. |
| Runtime | Clearly labelled episode runtime, not total series length. Define representative/provider runtime consistently; missing runtime is unknown, not zero. |
| Resolution, source, upgrade candidates | Measured available episode files; multi-version series match a documented any-available-version rule. Upgrade status comes from the existing profile evaluator. |
| Viewing status / Watchlist | Episode-derived series progress, with an explicit definition for fully watched released episodes. Watchlist is separate from acquisition monitoring; add TV-owned curation support if needed, never reuse movie numeric identities. |
| Ownership/availability | Catalog membership is not ownership. Distinguish no local episodes, partial availability, and all released episodes available. Local availability filtering must remain correct across pages. |
| Sort, feed, reset, clear, refresh, paging | TV-compatible feed/sort values with deterministic ties; preserve total/count meaning and filter state. |
| Existing TV status/monitoring/missing filters | Retain them alongside shared criteria. |
| Movie lists, film collections, file-management-only filters | Not silently mapped to monitoring or series. Keep movie behavior intact. TV custom lists and a full TV file-management workspace require an explicit scope decision; these are not claimed as delivered parity. |

Backend work must include metadata needed for visible controls: typed genre/keyword/person IDs, role credits, origin countries, language, runtime, votes, and local-source facts. Add only necessary TV migrations, preserve IDs/bindings/progress, and test upgrade/reopen on disposable stores. Do not require a destructive rescan.

TMDB TV Discover supports many filters but is not a drop-in copy of movie Discover. Person criteria require TV-credit-backed candidates; combined text/keyword/person/range queries need an explicit execution strategy. Reuse existing completeness/candidate-resolution patterns where valid. Never filter only the first provider page and claim complete totals. Bound costly work and label incomplete results; don't show a control whose backend ignores it.

Acceptance:

- Criterion matrix covers basic and advanced modes, positive/negative/multiple predicates, valid combinations, unsupported cases, reset, draft errors, and unknown metadata.
- Library filters the whole TV result set before paging; Discover handles provider pagination without pretending partial scans are complete.
- Rapid typing, response reordering, tab switches, series open/back, and browser Back preserve the correct query, selection, page, and scroll state.
- Movie/TV caches and navigation keys cannot collide for equal numeric TMDB IDs.
- All existing movie search/advanced-search/race/pagination tests pass unchanged in meaning.

## Phase 4 / point 3: complete TV details, trailers, and streaming

Start with a field/action inventory against restored movie details. Cover TV-relevant title/artwork, rating/votes, dates/status, synopsis, genres/language/country, cast/creators/crew, provider links, seasons, episode information, local versions, watch state, acquisition actions, streaming, and trailers. Track each as present, repaired, TV-adapted, or explicitly inapplicable. Don't declare the whole page complete after adding two buttons.

Preserve the existing dedicated series/seasons/episodes structure. Share proven card/action/dialog presentation; keep series containers distinct from playable episodes. Movie-only collections, movie budgets, and movie file actions must not be represented as TV facts. Additional TV recommendations/collections or unrelated redesign remain separate scope decisions.

### Streaming: reuse the existing movie player

- Keep `StreamModal` in `src/App.jsx` as the single CP streaming-window owner. TV already calls it; finish the URL/configuration/action path instead of building another player.
- StreamIMDB URL: `https://streamimdb.ru/embed/tv/{tmdb_id}/{season_number}/{episode_number}`. The ID identifies the series, not TMDB's episode-record ID.
- For the existing StreamIMDB movie configuration, supply the TV template automatically; no second manual setup. Preserve custom movie providers and explicit TV overrides. Do not guess a TV URL for an unrelated provider or overwrite saved settings as a side effect of reading them.
- Retain the provider player, subtitles, settings, fullscreen, and existing iframe permissions. Do not replace it with a native video element, extract raw streams, or hardcode a transient nested CDN hostname.
- Episode-row Stream targets that exact released episode. Series-level Stream uses the existing explicit resume/next target and identifies it to the user. Local file absence must not suppress online streaming. Unreleased/ambiguous numbering stays explained and unavailable.
- Switching episodes replaces the old iframe; close/Escape unmounts it and restores focus. Opening a stream does not mark an episode watched or invent playback progress.
- Preserve movie streaming URL generation, provider configuration, focus, and close behavior.

Prior live investigation (2026-09-18): Reacher S01E01 displayed video and 54:03 duration. S01E02 selected the correct identifier/player title, but reliable playback was not established. Black loading and unexpected homepage navigation occurred. This establishes the URL structure, not full CP streaming acceptance. Test subtitles/settings inside CP's equivalent desktop fixture and later the user-started application; report provider failures separately.

### Trailers and metadata

- Extend `TVMetadata`/repository/read model with TV video metadata and use the existing trailer player.
- Make identity/cache keys and any fallback search explicitly TV-aware. Never send a series ID to movie details or run movie matching on a series trailer.
- Prefer official suitable trailers with clear language/availability handling. A failed or absent trailer must not block series information or episodes.
- Fetch aggregate series credits where appropriate; the existing TMDB `/credits` response only represents the latest season. Preserve role data needed by person search.
- Load optional detail enrichment independently, cache it, and cancel/ignore stale results. Avoid fetching every season simply to show a trailer or basic details.
- Audit Discover opening: currently `open()` can add/refresh an entire series before showing it. Plan explicit separation of read-only browsing and Add/Monitor actions so streaming/trailer viewing does not silently create monitoring or acquisition activity.

Exit: the details inventory passes; correct episode streaming and TV trailer identity work; absent-provider behavior is honest; existing local playback/progress and all movie actions remain intact.

## Regression gates and evidence

| Gate | Required evidence |
| --- | --- |
| Baseline reconciliation | Per-file/behavior ledger, source backups/hashes, imported Desktop regression cases, no unexplained omissions. |
| Backend and data | Relevant existing/new Python tests after each batch; full suite after integration. TV upgrades preserve identifiers, bindings, progress, curation; movie/IPTV schema and data authority unchanged by TV work. |
| Search and acquisition | Query/selection contracts, provider failures and deadlines, result completeness, duplicate requests, no transfer submission during search/retry; movie selection parity. |
| Frontend utilities | Existing Node tests plus meaningful query/identity/navigation/URL regression cases. No tests that merely search source strings as the sole proof of behavior. |
| Compiled desktop UI | `npm.cmd run build`; serve the resulting assets only in an isolated fixture after approval; verify asset identity, then focused browser behavior and existing desktop regression suite. |
| Playback boundaries | Existing movie stream/trailer open/close; exact TV episode targets; subtitle/settings checks where provider responds; no background playback after close; local-play adapter coverage separately. |
| Visible review | Desktop screenshots/interaction checks for related movies, restored navigation, TV search and filters, series/episodes, acquisition review, and streaming/trailer windows. No mobile redesign. |
| Real configured acceptance | Once Dante starts the correct batch, confirm process/config/bundle ownership and inspect agreed non-destructive flows. Record provider status, actual playback versus iframe load, and any remaining live-only blocker. |

Use existing test runners after checking their isolation settings. Python discovery and Node test patterns must cover both imported Desktop tests and TV tests. Existing `tools/run_playwright_e2e.ps1`, `playwright.config.js`, and `tests/native_tv_server.py` are the starting points; inspect/repair fixture coverage when it misses current features. Do not assume historical counts are targets.

No batch is accepted with a new failure, missing Desktop behavior, ignored filter, incorrect identity, broken movie streaming, or unexplained data mutation. Known pre-existing failures remain reported; no claim of full green until resolved or explicitly handled with Dante. External outages are recorded as unverified acceptance, not hidden as a success or automatically blamed on CP.

## Recovery and handoff

- Maintain a batch-level changed-file manifest and verified pre-edit copies. Revert only this repair's edits, never all working-tree changes. Account for subsequent user edits before restoring anything.
- Test TV migrations on disposable existing-version databases and verify backward/recovery limitations. Do not alter live data during qualification or rely on an automatic production rollback.
- At completion, provide the four-item acceptance table, restored-feature inventory, actual test/build/UI results, unresolved provider issues, and exact batch path: `C:\Users\dante\.codex\worktrees\0870\cinema paradiso\run.bat`.
- Do not auto-launch the batch. Do not commit/push/release unless separately requested.

## Decisions proposed for approval

1. Implement in the order 1 -> 4 -> 2 -> 3, with visual redesign deferred.
2. Use current Desktop source behavior plus existing TV behavior as the combined baseline; preserve the reference checkout.
3. Reuse movie search presentation and player components, with TV-owned identities/data/query execution.
4. Treat movie-specific lists/collections and a full TV file-management workspace as separate scope decisions rather than silently inventing equivalents.
5. Require passing regression gates and visible desktop evidence; distinguish verified provider playback from an iframe merely loading.

## Primary provider references checked during planning

- TMDB TV Discover filters: https://developer.themoviedb.org/reference/discover-tv
- TMDB aggregate TV credits: https://developer.themoviedb.org/reference/tv-series-aggregate-credits
- TMDB latest-season credits distinction: https://developer.themoviedb.org/reference/tv-series-credits
- StreamIMDB episode URL observed from its own Reacher episode-page iframe: https://streamimdb.ru/tv/63xf7-reacher/season/1/episode/1
- VidAPI TV iframe pattern: https://vidapi.ru/
