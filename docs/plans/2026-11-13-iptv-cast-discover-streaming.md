# IPTV cast navigation, Discover availability, and streaming source choice

**Later correction approved 2026-11-13:** The small IPTV Filmography button opens full Movie Discover filmography; portrait click remains provider-local. The provider-only small-button rule below is superseded by the [correction plan](2026-11-13-iptv-filmography-discover-correction.md).

**Status** - Implementation approved by Dante on 2026-11-13: "i approve those choices go ahead and implement the plan keep it fast and follow cp design". Candidate implemented in the isolated managed worktree. Live activation, database migration, restarts, commits, pushes and releases are not authorized.

**Goal** — Browse an actor's films on the current IPTV provider, see locally known IPTV availability in Movie Discover, and choose a streaming service inside the player dialog without delaying movie browsing.

**Execution** - Inline implementation using executing-plans, with the current dirty desktop baseline preserved and one independent final reviewer. See the [verification report](../verification/iptv-cast-discover-streaming-2026-11-13/report.md) for actual results and limits.

## Problem and decision

### Observed baseline before implementation

- Enriched IPTV movies already store accepted TMDB movie identities, people, and credits. `IPTVPeopleCredits` renders static portraits with separate markup. Movie and TV credit cards already provide Biography and Filmography actions through `PersonCreditCard`.
- Movie Discover does not consult IPTV catalogs for its availability display. Provider movie databases are separate files owned by `IPTVMovieStore`.
- `App.streamMovie` resolves the saved web template and opens `StreamPlayerModal` with an iframe URL. IPTV playback uses provider-specific sessions and `IPTVPlayer`. IPTV already has a source-version chooser.
- Provider/store initialization can do significant work. Using `movie_service()` or `list_providers()` as a shortcut for Discover availability can initialize services, inspect status, or initialize a database. The lightweight lookup must avoid those paths.

Sources are the [IPTV Atlas](../atlas/iptv.md), [detail Atlas](../atlas/movie-and-tv-details.md), [streaming Atlas](../atlas/playback-and-streaming.md), [Discover Atlas](../atlas/search-and-discover.md), and the current owners listed below. Decisions were checked in the corresponding [IPTV](../second-brain/iptv.md), [details](../second-brain/movie-and-tv-details.md), [streaming](../second-brain/playback-and-streaming.md), and [Discover](../second-brain/search-and-discover.md) Second Brain pages.

### Dante's requested behavior

- Keep every provider's database file separate. Use saved TMDB identities to connect the experiences.
- Clicking a cast member in IPTV finds their movies on the current provider. Add the existing small Biography and Filmography controls next to portraits.
- Check **every configured IPTV provider** for Movie Discover badges, using **only locally saved catalog data**. No online availability probes, automatic sync, or enrichment is part of this lookup.
- Render Discover movies immediately and allow badges to arrive later. Stream opens the player dialog immediately, with service selection before playback.
- Offer StreamIMDB, VSEmbed, a configured custom template, and matching configured IPTV providers. Use CP's desktop design and existing components.

### Confirmed facts and limits

The desktop checkout is `C:\Users\dante\Desktop\cinema paradiso`, branch `master`, commit `117526b` (`Resolve CP knowledge guide references`). Before this plan was written, Git reported 152 modified, 2 deleted, and 242 untracked paths. Relevant dirty owners include `app.py`, `src/App.jsx`, `IPTVWorkspace.jsx`, and `iptv_movie_store.py`. Preserve this work and capture a fresh baseline at implementation time.

On 2026-11-13, the live listener was `127.0.0.1:5000`, PID 22372, Python 3.12, with launcher PID 50768 in the project virtual environment. The running app reported data root `C:\Users\dante\Desktop\cinema paradiso\data` and TMDB cache root `C:\Users\dante\Desktop\cinema paradiso\cache`. Its HTML referenced `index-9d_Ds88k.js` and `index-BqgPLqsb.css`. Source-to-bundle equivalence and rendered behavior were not verified in this planning pass.

Read-only SQLite inspection found Lionz's `movies.sqlite` at about 932.6 MiB, schema 4, movie generation 70950, source generation 48. EgySat's was about 57.2 MiB, schema 3, movie generation 0, source generation 13. Both have the match, source, classification, and credit columns needed for local lookup. This makes schema-3 read support an actual requirement. No performance benchmark or test suite was run during planning.

### Approved choices - 2026-11-13

| Decision | Approved choice and reason | Approval state |
| --- | --- | --- |
| Movie Stream scope | Apply the chooser through the shared `App.streamMovie` owner to Discover, Home, Movie Library, and Movie Lists. This provides consistent behavior across its current callers. | Approved explicitly by Dante on 2026-11-13. |
| One service available | Open the chooser even with one selectable service, following Dante's choose-then-play interaction. | Approved explicitly by Dante on 2026-11-13. |
| IPTV actor card versus Filmography | Actor-card click preserves applicable current refinements. Filmography clears those refinements and shows all matched films for that person on the current provider. Both remain within that provider. | Approved explicitly by Dante on 2026-11-13. |
| Custom sources | Include the existing saved custom movie template when configured. Future built-ins use the existing provider catalog. A manager for multiple saved custom URL entries would require a separately defined settings change. | Approved explicitly by Dante on 2026-11-13. |
| Disabled web streaming | The saved Streaming Link enabled flag controls web sources. IPTV choices remain usable when web streaming is disabled. | Approved explicitly by Dante on 2026-11-13. |

The implementation scope is Movie media. TV's existing episode streaming remains supported by the shared dialog refactor. IPTV Series identity matching and TV Discover IPTV badges require their own design. Native desktop-player embedding is outside this design. The requested player is CP's existing in-app streaming dialog.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| Provider ownership, IPTV Second Brain | Matches, sources, lists, and progress belong to each provider | IPTV and cross-provider read queries | Aggregate lightweight read results with provider IDs, retain each file and owner | No | Separate files and all-provider local lookup explicitly requested in this chat |
| Discover paging, Discover Second Brain | Filters and deduplication precede logical-page slicing | Movie Discover feeds, title, Advanced and relationship pages | Decorate returned movie cards asynchronously, without changing filtering, totals, order, or page size | No | Immediate movies and later badges explicitly requested |
| Filmography, 2026-10-01 | Movie small button clears criteria, card click preserves refinements, Back restores context | Shared credits, new IPTV callbacks | Preserve Movie/TV behavior and introduce provider-scoped IPTV callbacks as proposed above | Extension | Approved explicitly on 2026-11-13, including the two-action distinction |
| Streaming selection, 2026-10-24 | Movie and TV Stream open the saved provider | All Movie `streamMovie` callers and shared dialog | Movie Stream opens source choice. Saved provider is first among web sources. TV retains existing targeting | Yes | Approved explicitly on 2026-11-13 for all Movie callers, including one-source cases |
| Streaming disabled state, 2026-10-24 | Disabled Streaming Link prevents web streaming | Movie controls and chooser | Disabled web sources are excluded, IPTV remains independently available | Yes | Approved explicitly on 2026-11-13 |
| Playback readiness, 2026-10-04 | Iframe load reports page loading only | Embedded web player | Web availability stays unknown, local IPTV status means catalog presence | No | Local-only availability clarified by Dante |
| History ownership, playback and IPTV guides | IPTV history is provider-specific, web embeds do not update owned Movie/TV history | Chooser-launched playback | Reuse these owners for the selected playback source | No | Existing contract |

Dante approved all choices on 2026-11-13 before implementation. Movie tests now assert explicit service selection; TV retains the saved-provider direct stream contract. No new contract decision remains open within this scope.

## Current design and ownership

| Responsibility | Current authoritative file/component/service | Entry point and callers | Behavior to preserve | Competing or obsolete paths |
| --- | --- | --- | --- | --- |
| Provider registry and validated roots | `services/iptv_provider_manager.py`, `IPTVProviderManager` | `providers.json`, settings, IPTV routes | Provider identity, ordering, rename/removal, selected-provider state | Availability must avoid status-heavy listing and service construction |
| Matches and available source membership | `services/iptv_movie_store.py`, `IPTVMovieStore` | `source_matches`, `movie_sources`, `source_classifications`, `_cards_cte`, `sources` | Accepted identities, manual locks, unavailable source exclusion, film grouping | Consolidate accepted-film eligibility where new SQL needs the same rule |
| Movie browsing and credits | `services/iptv_movie_service.py`, `services/iptv_routes.py`, `src/api/iptv.js` | Provider `/movies`, detail and source routes | Current filter, paging and source semantics | Extend current movie query with person filters |
| IPTV UI and navigation | `IPTVWorkspace.jsx`, `IPTVCards.jsx`, `iptvMovieFilters.js` | IPTV Movie CP/Provider views | Filters, Back, provider selection, exact source playback | Retire static `IPTVPeopleCredits` portrait markup |
| Credit presentation | `PersonCreditCard.jsx`, `HorizontalCardRail.jsx`, `SharedMovieCards.jsx`, `TVSeriesCredits.jsx` | Movie/TV expanded details | Biography, portrait actions, keyboard behavior, existing filmography semantics | Reuse cards and rail, avoid pulling unrelated relationship widgets into IPTV |
| Discover cards | `DiscoverWorkspace.jsx`, `SharedMovieCards.jsx`, `movie-card/MovieCard.jsx` | Normal, Advanced, people, collection, related and indexer results | Grid metrics, ownership badge, expansion, lazy artwork | One shared optional IPTV badge slot, no route-specific badge markup |
| Web source definitions | `services/streaming_templates.py`, `app.py::streaming_config` | Settings, App, Movie and TV Stream | URL validation, custom templates, IMDb lookup, exact episode targets | Backend provider definitions remain authoritative |
| Streaming dialog | `src/App.jsx::StreamPlayerModal`, `usePlayerDialog` | Movie and TV streaming | Focus, Escape, close, iframe loading feedback | Extract the existing modal into one shared component and remove its old inline definition |
| IPTV session and media | `IPTVWorkspace.playItem`, `IPTVPlayer.jsx`, `iptv_service.py::start_playback` | IPTV workspace, proposed chooser | Relay credentials, FFmpeg session, HLS recovery, provider history and cleanup | Extract shared session lifecycle and version list from existing owners |

## Exact behavior contract

### Frontend

**IPTV cast.** Render existing `PersonCreditCard` inside `HorizontalCardRail` using `credit-card-rail` and `movie-expanded-people-grid`, the same reference used by Movie expanded details. Keep IPTV's existing two-director/eight-cast display limit in this scope. Use the shared 106-by-132-pixel portrait, 28-pixel action column, existing BookOpen/Film icons, title typography, director styling, focus treatment, and arrow behavior from `horizontalCardRail.css`. Remove the duplicate static portrait markup and only the CSS proven exclusive to it.

The Biography action opens `PersonBioModal` immediately and loads on demand. No biographies are prefetched with Discover or cast rendering. Provider filmography uses saved credits and accepted matches. Missing person IDs disable person navigation with an explanatory accessible label. Missing portraits use the existing avatar fallback. Biography failure remains inside the modal and leaves filmography usable.

Actor-card click saves provider ID, tab/view, filter values, page, expanded movie, locale, and scroll position. It opens CP Film results for that person and preserves compatible refinements. Filmography uses the same navigation owner, resets title/playlist/list/genre/year/rating/language/country/quality/watched/metadata refinements, and applies person ID, role and CP Film scope. Back restores the captured state and scroll. Nested person navigation pushes another snapshot. Switching providers clears this navigation stack and aborts previous requests. Each result uses `IPTVMovieCard` and the existing grid/page-size owner. Empty copy is `No matched films for {person} in {provider}'s saved catalog.`

**Discover badges.** Add an optional named availability slot to `UnifiedMovieCard`, supplied through `DiscoverMovieCard` and the indexer card adapter only when a valid movie TMDB ID exists. Its single reserved 30-pixel row sits immediately below the existing metadata chip row in both collapsed and expanded Discover cards. Its presence is determined at first render, so delayed results do not change card height. Reuse the existing status/Owned chip base metrics by extracting their shared styling in `movieCard.css`. Use neutral CP colors and a TV/monitor icon for provider labels. Keep Owned and Following semantics and positions.

Show up to two provider names and a `+N` overflow control. Truncate long names within the fixed row, expose full names through accessible labels, and show all providers in the player dialog. A badge or overflow click opens that dialog and highlights the named provider without starting playback. Pending, failed and zero-match states leave the reserved row visually empty. Do not show a negative availability badge. A tooltip on a positive badge reads `Listed in {provider}'s last synced catalog`.

Render the Discover response before starting availability work. The workspace sends batches of up to 100 distinct IDs for its current rendered logical page. Large pages split into chunks, with the expanded movie and first visible chunk first. No per-card requests, hidden-tab scans, query debounce delay, or wait for all providers before showing movie cards. Availability never feeds Discover's loading, filtering, sorting, totals or page-filling logic.

**Player and service choice.** Move the current `StreamPlayerModal` into `src/components/StreamPlayerModal.jsx` and retain its `trailer-dialog stream-dialog` shell, header, close control, backdrop, viewport sizing and focus management. Movie Stream sets dialog state synchronously before any lookup or IMDb resolution. Use existing `btn`, `screen-kicker`, loading and error styles. Place a source list in the player stage until selection. During playback, keep a `Change source` action in the dialog header. It stops the current playback and returns to the source list for the same movie.

Rows display provider name and one of `In catalog`, `Not in saved catalog`, `Checking saved catalog`, `Catalog unavailable`, or `Availability unknown`. Each configured IPTV provider has a row. Only a successfully completed local query may produce `Not in saved catalog`. Unsupported/missing databases and read errors produce `Catalog unavailable`. Web sources display `Availability unknown` and remain selectable when enabled and required IDs can be resolved. Display matching IPTV providers first, then selectable web sources with the saved web provider first, then nonselectable IPTV rows. Preserve registry order within equal IPTV states.

Selecting a web provider resolves its existing template through the current URL builders. IMDb lookup happens only after choosing a template that requires it. Load one iframe using the existing loading/slow-page feedback. Do not probe, preload, auto-select or automatically fall back between services.

Selecting IPTV rechecks locally saved source membership, then retrieves source versions for that movie/provider. One available source starts directly. Multiple available sources show the existing playlist, quality/dubbed/subtitled claim rows inside the same dialog. Reuse an extracted `IPTVSourceList` from the current source chooser and have the old IPTV chooser consume it too. Unavailable versions remain disabled. Use `IPTVPlayer` for HLS playback inside the dialog. Source list labels describe provider claims exactly as today.

The Movie action label becomes `Stream` because service choice happens afterward. If web streaming is disabled, configured IPTV providers still make the Movie Stream action available while local availability is checked. Zero usable sources show `No streaming source available` with Retry and Close. A movie without a TMDB ID cannot claim IPTV availability. A compatible custom IMDb template can still play if its required ID is present.

Desktop verification uses existing Movie/TV credit rails, Movie Discover cards, stream dialog, and IPTV source list as references at 1600x1000 and 1920x1080, including Windows 150% scaling. Measure dimensions, spacing, wrapping and keyboard behavior. No mobile redesign is part of this plan.

### Backend and local data

**Read-only store entry.** Add `IPTVMovieStore.lookup_availability(provider_root, provider_id, tmdb_ids)` as a class-level read operation in the current store owner. It validates the root and opens the existing file with SQLite URI `mode=ro`, WAL-aware normal reads and a 100 ms busy timeout. It must not construct `IPTVMovieStore`, call initialization, set journal mode, migrate, rebuild, start projection, or use `immutable=1` on a live WAL database. Close connections in all outcomes. Missing files stay missing.

Support schemas 3 and 4 using their common columns and the same query. Schema 1/2 cannot establish the approved Film rule: `source_classifications` is introduced by `_migrate_schema_v3`. Return `unsupported_schema` for them without migration, never a false negative. The old-schema read path exists because configured providers can remain on older catalog schemas. It depends on the common identity/source/credit fields and can be removed only when those schema versions cease to be supported by CP. This operation introduces no persistent database or mandatory migration.

Query accepted identities with `matched-auto` or `matched-manual`, a positive TMDB ID, source `available=1`, and Film classification. Preserve manual locks and existing treatment of accepted stale identities. Begin with the indexed requested TMDB IDs and join source/classification keys, then group only those matches. Reuse one accepted-film membership predicate with the current CP grouping and source resolver. Cached metadata rows, provider-supplied candidate IDs, uncertain matches, sports/music, and unavailable sources cannot independently establish availability. Inspect `EXPLAIN QUERY PLAN` to ensure the new lookup does not aggregate the whole catalog.

**All-provider API.** Add class-level `IPTVProviderManager.movie_availability(user_data_dir, tmdb_ids)` and `POST /api/iptv/movies/availability` in the current IPTV route owner. Body is `{"tmdb_ids":[123,456]}` with 1â€“100 distinct positive integer IDs up to 2147483647. Reject booleans, unknown fields, invalid values and oversized input with 400. Extend `register_iptv_routes` with a read-only data-root callback from App. This route must not call `_get_iptv_provider_manager`, because the lazy manager constructor itself can initialize directories and migrate legacy state. Extract the existing registry parsing/root validation into reusable methods in the manager, read one atomic registry-file snapshot, and reuse those methods in both normal management and class-level reads. A missing registry means zero configured providers. A corrupt registry is a retryable 503, with no automatic rewrite. Never call status-producing provider summaries. At most four provider reads run concurrently in a bounded shared executor. Bound each SQLite query to 250 ms with an interrupt/progress deadline and return a provider error when exceeded. Reuse completed healthy-provider results when another provider fails.

Response contains `providers`, each with `provider_id`, `name`, `state` (`ready` or `unknown`), `reason`, `source_generation`, `movie_generation`, and `matches` mapping requested TMDB ID strings to `{movie_key,source_count}`. For `ready`, an omitted requested ID means no accepted available film match. For `unknown`, omission has no negative meaning. Include `checked_at` and a registry revision derived from validated registry content. No credentials, provider URLs, large detail payloads, posters or cast data cross this endpoint. This POST performs reads only.

The API reads the last committed movie projection. Raw sync can finish before projection catches up, so these results describe that saved projection. Concurrent classification, matching and projection use a coherent SQLite snapshot per provider. Provider removal during a read becomes a provider-local unknown/removal result. A renamed provider retains its ID. No global transaction or merged catalog is required.

**Fresh source resolution.** Add read-only `POST /api/iptv/movies/sources` with `{provider_id,tmdb_id}` and the same registry validation, returning `{provider_id,movie_key,items}`. It calls class-level `IPTVMovieStore.lookup_sources(provider_root, provider_id, tmdb_id)`, supports the same schema-3/4 common fields, and returns the current available source versions using the existing source payload fields. Reuse source-row selection/serialization inside the existing store `sources(movie_key)` implementation, avoiding a second definition of version labels or identity membership. A removed provider returns 404, an unsupported/unreadable catalog returns 503, and no currently matching version returns an empty `items` array. The chooser shows the current result and never silently substitutes a different identity. Only the subsequent explicit playback POST enters normal provider session initialization. Tests must cover an old-schema matched movie from badge through this resolver into exact raw-source playback without upgrading its movie database.

**Client reuse.** Create `src/api/iptvAvailability.js` as the single in-memory request/cache owner for Discover and the chooser, with `getMovieAvailability(tmdbIds, {signal, force})` and `invalidateMovieAvailability()`. Add `src/hooks/useIPTVMovieAvailability.js` for view subscription, request-sequence guards and disposal. Cache at most 500 movie entries for 15 seconds, coalesce identical in-flight work, and preserve per-provider unknown states. One subscriber aborting must not cancel another subscriber's shared request. Clear the cache when data root, provider registry, or an acknowledged match/classification/sync mutation changes through CP. While Discover is visible, revalidate the displayed batch at most every 15 seconds so background enrichment becomes visible. Stop timers when hidden. A newly opened chooser may display fresh cached results immediately and revalidates expired results locally. Before IPTV start, resolve fresh source membership regardless of cache age. No server result cache or additional persistent index is needed initially.

**Person filters.** Extend `iptvMovieQuery`, route validation and `IPTVMovieStore.list_movies` with `person_id` and `person_role` (`actor` or `director`). Map actor to saved credit department `cast`. Apply indexed credit membership before count and pagination, use `EXISTS` to avoid duplicate results, and use current CP Film grouping. Reject a role without a valid person ID. All source versions remain behind their grouped movie. Person browsing must not fetch TMDB credits online or trigger enrichment.

**Biography.** Reuse the person-details normalization currently in `app.py::_normalize_tmdb_person_details_payload`. Extract that unchanged mapping into `services/tmdb_people.py` and have the main route and a new provider `/people/<person_id>` route call it. The IPTV route uses `IPTVTMDBClient` and IPTV metadata settings. Extend `usePersonBiography` with an optional loader, retaining its current default for Movie and TV. IPTV supplies `iptvApi.person(providerId, personId, {signal})`. A biography request may access TMDB only after explicit user action. This is separate from offline availability and filmography. Preserve missing-key/error handling and cancellation on close/provider switch.

**Streaming choices and sessions.** Extend the response of `/api/streaming/config` with a derived `movie_sources` list of `{id,label,url_template}` using `streaming_templates.py`. Include both built-ins when enabled and the saved custom movie template when it differs from them. Preserve saved custom overrides and remove exact duplicate templates. Persist no new selected-service state. Existing template validation and TV URL behavior remain authoritative.

Extract the lifecycle currently in `IPTVWorkspace.playItem` into `src/features/iptv/useIPTVPlaybackSession.js`, used by the workspace and Movie chooser. It owns start/stop, pending-request sequence, session token and the exact provider/source pair. Preserve the provider relay and FFmpeg service. Use one shared active IPTV session coordinator within this hook module so switching between the workspace and chooser cannot orphan a session. Closing or switching while start is pending disposes any late-created token. Double clicks cannot create two retained sessions. Stop the old session before switching provider or to a web iframe. IPTV history retains the existing source/movie history IDs and provider, while owned Movie/TV progress is untouched. Remove superseded lifecycle logic only after both callers pass regression coverage.

### Performance acceptance targets

These are engineering acceptance targets, not guarantees for arbitrary hardware. Actual measurements and conditions are recorded in the verification report.

- With the availability endpoint held for 5 seconds, movie cards, title search, pagination and expansion remain usable. No availability request participates in the main Discover promise chain.
- Clicking Stream displays the dialog within 100 ms in the isolated desktop fixture while availability and IMDb requests are held. Available web rows can be selected while IPTV reads are pending.
- For the current two-provider catalog sizes, a 100-ID local batch targets warm p95 at or below 100 ms and first-process-read at or below 250 ms. Report first-read conditions accurately, without claiming OS-cache eviction.
- Obtain at least 30 warm samples, mix present/absent IDs and multiple versions, and test 1, 2 and 10 synthetic providers. Record payload size, SQL plan and request count. Use the existing near-1-GiB Lionz database through the read-only path for realistic scale, plus small 1/2/10-provider synthetic fixtures for fan-out. No live database copy or write is needed.
- Deliberate locks, read failures and expired schemas may exceed normal targets through bounded failure paths, but must leave Discover interactive and other providers usable. No automatic online call, schema write or full catalog scan is accepted to meet the target.
- Badge arrival changes card bounding boxes and scroll position by at most 1 CSS pixel. No repeating per-card spinners or layout reflow.

## Implementation sequence

### Task 1 — Local availability through the existing store and manager

Files to modify are `services/iptv_movie_store.py`, `services/iptv_provider_manager.py`, `services/iptv_routes.py`, and `app.py` for the data-root callback. Create `tests/test_iptv_movie_availability.py` and extend `tests/test_iptv_routes.py`.

- [x] Capture current focused test baseline in an isolated environment and record existing failures.
- [x] Add failing tests for the store/manager/API contract, including schema-3 EgySat-shaped data, WAL reads, unknown states and no initialization/network calls.
- [x] Implement class-level availability/source reads, shared accepted-film eligibility and manager batching, then expose both validated APIs through the read-only data-root callback.
- [x] Assert matched IDs and provider names in the actual JSON response, verify zero catalog writes, inspect SQL plans, and run the focused tests.

Produces the exact availability response described above. Later tasks consume it without duplicating match eligibility.

### Task 2 — IPTV actor navigation and shared buttons

Modify `IPTVWorkspace.jsx`, `IPTVCards.jsx`, `iptvMovieFilters.js`, `PersonCreditCard.jsx`, `src/api/iptv.js`, `iptv_movie_store.py`, `iptv_movie_service.py`, `iptv_routes.py`, `iptv_tmdb.py` and `app.py`. Create `services/tmdb_people.py`. Extend `tests/iptv_movie_filters.test.mjs` and create `tests/test_iptv_people.py`, `tests/e2e/iptv-people.spec.js`.

- [x] Add tests for actor/director isolation, grouping, pre-pagination filtering, contextual versus full-provider navigation and Back restoration.
- [x] Extend the current movie query contract and render the shared credit rail/cards with the approved callbacks.
- [x] Extract shared biography normalization, add the IPTV loader and verify IPTV-only TMDB configuration works while the main TMDB key is absent.
- [x] Remove obsolete static credit markup, verify Movie/TV biography and filmography regressions, and capture compiled desktop parity evidence.

Produces provider-scoped actor/director result pages through the existing movie browsing endpoint.

### Task 3 — Asynchronous Discover badges

Create `src/api/iptvAvailability.js`, `src/hooks/useIPTVMovieAvailability.js`, `tests/iptv_availability.test.mjs`, and `tests/e2e/iptv-discover-availability.spec.js`. Modify `DiscoverWorkspace.jsx`, `SharedMovieCards.jsx`, `movie-card/MovieCard.jsx`, `movie-card/movieCard.css`, and existing mutation/data-root callbacks only as needed for cache invalidation.

- [x] Test batching, deduplication, unknown versus negative, expiry, cancellation isolation, navigation races and invalidation.
- [x] Implement the client owner and workspace subscription after Discover results render.
- [x] Add the shared fixed-height badge slot, pass results to all specified Discover card adapters, and wire badge activation to the Movie stream callback.
- [x] Hold the endpoint, change pages and expand cards in compiled tests. Assert visible movie content before release, exact badge identities afterward and unchanged geometry.

Produces reusable availability state for Task 4, including fresh cached results and provider-local failures.

### Task 4 — Shared Movie source chooser and IPTV playback reuse

Modify `src/App.jsx`, `services/streaming_templates.py`, the config endpoint, `IPTVWorkspace.jsx`, `IPTVPlayer.jsx`, and existing Movie Stream control props. Create `src/components/StreamPlayerModal.jsx`, `src/features/iptv/IPTVSourceList.jsx`, `src/features/iptv/useIPTVPlaybackSession.js`, and `tests/e2e/movie-stream-sources.spec.js`. Move reusable source-list styles out of the `.iptv-workspace` scope into the shared component's stylesheet, with both callers consuming them.

- [x] After contract approval, add tests for derived sources, disabled-web behavior, custom templates, immediate modal opening and explicit selection.
- [x] Extract the existing dialog and IPTV version list. Keep TV's supplied iframe-target mode and all its prior loading/close behavior.
- [x] Extract the session lifecycle, convert the IPTV workspace to it, then add chooser selection and local fresh-source validation before launch.
- [x] Update all approved Movie callers and action eligibility through their shared owner. Resolve IMDb only after source selection.
- [x] Verify exact provider/source and token passed to playback/history, rapid switching, close-during-start and cleanup after errors. Verify no autoplay on dialog opening or badge click.

### Task 5 — End-to-end acceptance, performance and documentation

- [x] Evaluate all acceptance rows below and run the relevant Python/Node suites and compiled desktop checks, recording fixture limits. Save actual timing, screenshots and failures in `docs/verification/iptv-cast-discover-streaming-2026-11-13/report.md` during implementation.
- [x] Compare against reference Movie/TV credit controls and existing CP cards/dialogs, including long content, missing data and 150% scaling.
- [x] Update the existing IPTV, details, Discover and streaming Second Brain/Atlas pages and update log with approved decisions, actual owners and verification limits. This maintenance is part of the approved implementation.
- [x] Report each contract and acceptance result, source/isolated/live status, exact failures and unresolved differences. Request separate live activation only after the candidate is reviewable.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or evidence |
| --- | --- | --- | --- | --- |
| Actor in Lionz and EgySat | Click Lionz actor | Lionz films only, one card per accepted Film identity | IPTV movie query | `test_person_filter_is_provider_local_and_groups_versions`, rendered result assertions |
| Actor also credited as director | Browse each role | Results match selected saved department | Store | `test_person_roles_do_not_leak` |
| Active filters and page/scroll | Card click, Back, Filmography, Back | Context preserved for card, cleared for button, exact original state restored | IPTV navigation | `iptv-people.spec.js` |
| Person absent/missing ID/portrait | Open credits | Correct empty state or disabled navigation, avatar fallback | Shared credits | People backend and desktop checks |
| IPTV TMDB key only | Click Biography | Existing bio design loads through IPTV settings | Person endpoint/hook | `test_iptv_bio_uses_iptv_settings`, desktop modal assertion |
| Biography timeout/provider switch | Close or switch | Modal error or cancellation, no old-person overwrite | Shared hook | Abort and late-response assertions |
| Accepted ID with two providers | Load Discover | Both provider names arrive after movies | Full API-to-card path | `iptv-discover-availability.spec.js` with real isolated API |
| Candidate ID, cached metadata, unavailable source | Lookup | No positive match from those records | Store | `test_only_available_accepted_films_establish_presence` |
| Schema 3 and schema 4 | Lookup same IDs | Same query semantics, no migration/backup creation | Store | `test_schema_three_and_four_are_read_only` |
| Manager never initialized in this process | First Discover lookup | No manager construction, directory creation or migration | App/route/manager | `test_cold_availability_does_not_initialize_manager` |
| Schema-3 accepted movie | Badge, select provider, start | Resolves exact saved source and starts raw playback without upgrading movie DB | Complete read-to-play path | API and compiled fixture |
| Live WAL commit | Lookup after commit | Reads committed match without checkpoint requirement | Store | `test_readonly_lookup_observes_wal` |
| Unsupported/missing/corrupt/locked database | Lookup | That provider unknown, healthy providers returned | API/chooser | Per-provider failure fixtures |
| Deleted/renamed provider | Revalidate | Removed row disappears, new name keeps identity, no provider selection change | Registry/cache | Registry-race tests |
| Availability held five seconds | Browse, page, expand | Movies and actions work before response | Discover | Delayed-route compiled test |
| Rapid page or filter change | Old response arrives last | No wrong-page badge or visible error | Client request sequence | JS and compiled race tests |
| Badge appears, long provider names, 10 providers | Complete query | Fixed geometry, truncated names, `+N`, all names in chooser | Shared card | Bounding-box and accessible-label assertions |
| Match corrected/removed during session | Invalidate/revalidate, choose source | Old match removed, fresh resolution prevents wrong start | Store/cache/playback | Real API mutation-to-UI fixture |
| IPTV lookup has no internet | Load Discover/filmography | Works entirely from saved catalogs | API/store | External network clients patched to fail if invoked |
| Multiple services or one service | Click Movie Stream | Immediate dialog, no iframe/session until choice | App/dialog | `movie-stream-sources.spec.js` |
| Configured web providers/custom template | Choose each | Correct URL, deferred IMDb resolution, unknown availability | Streaming owner | Config/API and compiled tests |
| Web disabled, IPTV present | Stream matched movie | IPTV selectable, no web launch | Shared Movie callers | Contract-specific compiled test |
| Multiple IPTV versions | Choose provider/version | Exact available version starts, disabled versions cannot start | Source list/session | Request payload and rendered playback assertions |
| Close during start or rapid double click | Complete delayed start | Late token stopped, at most one retained IPTV session | Shared hook/service | Delayed playback fixture |
| Switch IPTV to web/other provider | Select new service | Old token stopped, one active media element/session | Dialog/lifecycle | Service stop and element-count assertions |
| IPTV playback/history | Watch selected movie | Provider/source history only, owned Movie/TV state unchanged | Player/API | Recorded history body and store assertions |
| Existing TV episode stream | Stream exact episode | Same series/season/episode URL and prior saved-provider behavior | Shared dialog/TV | Existing TV and streaming suites |
| Existing IPTV Live/Series playback | Start, recover, close | Existing recovery/progress behavior preserved after lifecycle extraction | IPTV workspace/player | Existing service suites plus desktop regressions |
| Discover filters/count/ownership | Receive badges | Identical order, totals, owned badges, grid/page size | Discover/card owner | Paging, ownership and artwork regression specs |

## Verification and rollout

### Baseline and focused commands

Use a suitable existing isolated checkout when available, otherwise create an isolated worktree through the native tool after implementation approval. Carry the relevant dirty baseline deliberately. Do not use a clean historical commit as a substitute for the current intended source. Use temporary test configuration/data and an isolated output bundle.

Set `CP_TEST_MODE=1` and `CP_TEST_ROOT` to a new absolute OS-temporary directory before Python tests that import `app`. The commands below define the focused checks. Exact executed commands and results are recorded in the verification report.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iptv_movie_availability tests.test_iptv_people tests.test_iptv_routes tests.test_iptv_provider_manager tests.test_streaming_config_api
node --test tests/iptv_availability.test.mjs tests/iptv_movie_filters.test.mjs tests/movieDetails.test.mjs
npm.cmd run test:e2e -- tests/e2e/iptv-people.spec.js tests/e2e/iptv-discover-availability.spec.js tests/e2e/movie-stream-sources.spec.js tests/e2e/streaming-providers.spec.js tests/e2e/stream-player.spec.js
```

The existing Playwright runner compiles to its temporary `CP_TEST_DIST_DIR`, seeds isolated fixtures and uses port 5117. Extend the fixture seeder for provider identities and cast, without touching live catalogs. New UI tests must assert both the actual API output and the rendered result. Intercept only external TMDB biography/embed/media transports when appropriate, retaining real local availability and session routing.

### Broader checks

Run `tests.test_iptv_service`, `tests.test_iptv_movie_gates_0_5`, `tests.test_iptv_movie_enrichment`, `tests.test_iptv_chatgpt_bulk`, `tests.test_iptv_movie_ui`, and `tests.test_iptv_ui` for shared-owner regressions. Run all Node tests using an explicit expanded file list. Run existing compiled filmography, Movie relationships, card artwork and Discover paging suites in their required fixture environments. Run TV expanded parity and native-TV streaming tests with `CP_TV_E2E=1`. Record the actual commands and counts. Compare baseline failures rather than silently accepting or weakening them.

The acceptance gates are separate. First pass local backend/client tests. Then compile and inspect actual desktop UI. Then measure availability and render behavior with the stated fixtures. Live playback can only be claimed after separately approved activation and direct observation with the actual selected source.

### Rollout and recovery

The availability and cast query design needs no catalog migration, file merge or new persistent index. Preserve existing config fields, adding derived API output only. If profiling demonstrates a necessary schema/index change, revise this plan with its cost and obtain the applicable approval before applying it to real providers.

For separately approved activation, record the process, data root, settings, selected player runtime where applicable, previous served bundle and candidate bundle. Preserve a recoverable prior bundle/source/config state. Verify visible badges against accepted local records, choose a real source, confirm cleanup and confirm existing TV streaming. Roll back the activated source/bundle if source identity, history ownership, browsing performance or session cleanup fails. Do not clear or rewrite provider data as a rollback technique.

At handoff, compare every approved contract and acceptance row with the observed result. Report source-only, isolated-tested and live-verified states accurately. The deliverable is the implemented, isolated-tested candidate and its verification report; it is not activated in the running app.

## Implementation rulings and review dispositions

- All proposed product choices above were approved together before implementation.
- Native worktree creation completed after a delay. The temporary isolated snapshot was transferred to the managed worktree; the desktop checkout was not overwritten. A baseline hash manifest and file copies substitute for commits, which are outside authorization.
- Older schema 1/2 absence of classification makes Film availability unknowable. Schema 3/4 reads share the same query and need no migration.
- SQLite initially chose an available-source scan on the real Lionz catalog. The indexed TMDB-driven CROSS JOIN fixes the read plan without adding an index or changing any provider database.
- Reset filters preserves the current person and Film scope. Switching explicitly to Provider View exits person navigation so the heading cannot describe unrelated results.
- The session owner distinguishes ordinary owner-only cleanup from an explicit user source selection, which may stop the other IPTV surface. Closing an old surface cannot stop its successor.
- Review findings: cross-surface stop, actor Reset/View scope, pending provider rows, missing-ID explanation and genuine schema-3 playback-route coverage were addressed. Review excluded live activation/playback and unrelated dirty baseline work; those exclusions are accepted because they are outside authorization. Documentation/test status exclusions were resolved in the final report.
