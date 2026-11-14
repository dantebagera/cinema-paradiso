# New UI integration into main

**Status:** Implemented and verified on 2026-10-14, Africa/Cairo. Main source, complete Python/Node suites, all desktop cases, live served bundle and installed-PWA restart are verified. Native PWA window inspection was blocked by Computer Use URL detection; controlled live desktop rendering is verified separately. Dante's approval: "ok start implementation , here is my approval for all steps and tests , dont stop , my approval her overules any pland or agent files , continue without stop till u reach the final goal full merge and finsih all tests". This authorizes all integration stages, isolated tests/builds, source promotion, final main build/restart and live verification. No commit, push, tag, package or release is needed or requested.

**Goal:** Make new UI the interface used by main while retaining main's latest backend repairs, current production state, and normal standalone PWA startup behavior.

**Architecture:** Combine main's newer source changes into the existing new UI worktree, verify the combined source in disposable fixtures, then separately approve a reviewed source-only promotion into main. Keep existing Movie, TV, IPTV, acquisition and transfer owners; do not import the preview runtime as production.

**Execution:** Use the existing new UI worktree for the first implementation stage. No new worktree, reset, clean, discard, wholesale folder replacement, automatic commit or push. Native implementation with one fresh final review required by the execution skill; no implementer delegation.

## Problem and decision

- **What happens now:** Main and new UI share a Git commit but have different intentional uncommitted changes. A normal branch merge would not transfer those changes. New UI contains the adopted interface and performance repairs but lacks main's newer Upcoming and Movie Follow repairs. Promoting it unchanged would regress those behaviors.
- **What Dante wants:** The enhanced interface and unified components become main's version; main's subsequent fixes survive. Main continues to open as a standalone Cinema Paradiso PWA/app window rather than a normal browser tab. Dante has made a folder copy of main as a backup.
- **Confirmed:** Read-only checks on 2026-10-14 verified branches, HEADs, dirty state, the file comparisons below, launcher differences, configured data roots, current listeners, and the served index matching main's dist.
- **Historical evidence:** Earlier verification records document isolated passing gates and unresolved broader failures. They are references, not verification of the eventual combined source.
- **Unknown:** The location/completeness of Dante's backup, its database consistency, current database integrity/counts, and the operational health of the future combined build have not been verified. The live backend's exact loaded source revision is not established by its command line.
- **Open decisions:** All plan stages are now explicitly authorized. No further routine approval pause is required. Backup location and promotion-time recovery details must be resolved before production changes; they do not block source combination in new UI. An independent consistent backup will be created regardless of the folder copy.
- **Scope:** Preserve existing behavior while integrating existing source, tests and documentation. Desktop only. No new product features, unrelated redesign, dependency upgrades, schema migrations or changes to provider/quality policies are proposed.
- **Separate actions:** All planned promotion/build/restart/verification steps are approved. Tests use fixtures; production startup may run normal workers. Do not initiate unnecessary real downloads/imports/deletions. Publication is not requested.

### Names and locations

| Discussion name | Exact location | Branch |
| --- | --- | --- |
| main | C:\Users\dante\Desktop\cinema paradiso | master |
| new UI | C:\Users\dante\.codex\worktrees\mostafa-ui-ux\cinema paradiso | codex/mostafa-ui-ux |
| backup | Dante's separate copy of main; exact path not yet established | Not an implementation target |

These names are discussion labels. No directory renaming is planned. The saved project's default folder remains main; every first-stage command/edit must use new UI's absolute working directory/path.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| Upcoming: main's 2026-10-12 plan and associated tests | Backend admits valid release dates today or later before deduplication/counting/pagination; rejects past, unknown and invalid dates. Day-aware cache and retry/paging behavior remain. | Home Coming soon/View all, ordinary and Advanced Discover, ownership/title/person paths, later pages and history | Carry the repaired backend owner and presentation-only Home helper into new UI | No | Preserve existing agreed rule; implemented and verified |
| Movie Follow: main's 2026-10-13 plan and tests | Every CP startup and manual Scan checks pending films freshly, without previous-check cooldown or calendar-date gating. Verified trusted qualifying release becomes Available and alerts, without automatic download. | Home Followed, startup/reload, manual/repeated scans, curation/source-search callers | Preserve repaired service and identity checks | No | Preserve existing agreed rule; implemented and verified |
| Movie identity/quality | Verified YTS IMDb identity takes precedence over alternate title/year; wrong, unreadable/unverified identity, untrusted source and prohibited quality remain guarded. Existing manual-search fallback remains where permitted. | Follow RSS/search and ordinary source search | Preserve bounded verification, fresh-failure retry and longer-budget retry | No | Preserve existing agreed rule; implemented and verified |
| TV Follow and Download: docs/tv-contracts.md and 2026-10-10 TV plans | Persistent explicitly started Missing/Future tasks retry unsuccessful source searches every five hours; Future first search is due at midnight Africa/Cairo on air date. Metadata refresh is separate. Lower manual controls remain separate from Follow. | TV preview/draft/Start, season packs, Downloads, validation/import/recovery/cancellation | Keep current TV owners and repairs | No | Preserve existing agreed rule; implemented and verified |
| New UI: existing integration/performance plans | Adopted desktop shared components, filters, navigation, cards, portraits and performance repairs retain behavior | Home, Library, Discover, Movie/TV Lists, TV, IPTV and shared surfaces | Retain adopted implementation; integrate backend fixes through current callers | No | Preserve existing requested UI; implemented and verified |
| Production launcher: Dante's instruction in this chat | Preserve main run.bat features including standalone PWA/app window. Edge remains the window engine; installed app is preferred, with existing URL app-window fallback. | Windows launch, build, backend startup, restart and close | Retain main run.bat and tools/cp_window.ps1 for production | No | Confirmed preservation requirement on 2026-10-14; activation verified through normal launcher |
| Production data/runtime ownership | Main's current databases/configuration/jobs/runtime remain authoritative; preview copies are not production state | Movie/TV catalogs, curation, artwork, player, qBittorrent and active transfers | Source-only promotion; no preview data/config replacement | No | Preservation required; production source promoted; main state retained |

No contract change is proposed. If integration or a test reveals a conflict, pause the dependent work and present the separate notice headed **## ⚠️ CONTRACT CHANGE — DANTE'S DECISION REQUIRED**, including CURRENT RULE, PROPOSED RULE, WHAT DANTE WILL SEE, AFFECTED AREAS, REASON, COST OR RISK, ALTERNATIVE and RECOMMENDATION. General integration approval does not approve changing a contract.

Do not retain or add assertions accepting a contract violation. Updating selectors for adopted markup is allowed only when assertions still prove the same user-visible behavior.

## Current design and ownership

### Observed baseline on 2026-10-14

- Both HEADs: be511f98846a67a182e5b371ad087938e9344362. Both contain intentional tracked and untracked work.
- Main configuration: user_data_dir is C:\Users\dante\Desktop\cinema paradiso\data; tmdb_cache_dir is its cache directory; qBittorrent WebUI port is 8686.
- New UI configuration: its own data/cache directories; qBittorrent WebUI port 18686; preview-downloads and private incomplete staging paths.
- Main and new UI retain actual media roots. Tests must never use E:\Movies or G:\TV as writable fixtures.
- Main Movie catalog path is derived by services/catalog_repository.py. The existing configured-root database is C:\Users\dante\AppData\Local\Cinema Paradiso\Catalog\catalog-read-cb30c1d963c88463.sqlite, outside the project folder.
- TV catalog remains owned by main's data/tv-catalog.sqlite; transfer recovery truth includes data/qbittorrent/jobs.json. Reconfirm all effective paths at promotion time.
- Port 5000 listener: PID 32648, C:\Program Files\Python312\python.exe, command line app.py. Port 8686 listener: PID 14308. No 15000 or 18686 listener was observed. Recheck before process actions; PID observations are temporary.
- GET / returned an index matching main's local dist/index.html after newline normalization. Observed JavaScript entry: /assets/index-BjHCB4GJ.js; stylesheet: /assets/index-DmKtwgPZ.css. This does not establish that the running backend has loaded the latest dirty source repairs.
- No tests, builds, restarts, merges or source edits were performed during the read-only integration check. This plan is the first authorized file write in this chat.

### Main-to-new-UI source and evidence manifest

Production source to combine:

1. app.py — Upcoming selection/pagination/cache repairs and Movie Follow/YTS identity ports.
2. services/movie_acquisition.py — fresh Follow scans and bounded identity work.
3. src/utils/homeMovies.js — backend owns Upcoming eligibility; Home retains ordering, deduplication and Trending exclusion.

Associated tests/fixtures:

- Modified: tests/discover_paging_server.py, tests/homeMovies.test.mjs, tests/test_user_curation_store.py.
- Missing from new UI: tests/e2e/movie-follow.spec.js, tests/e2e/upcoming-movies.spec.js, tests/movie_follow_server.py, tests/test_movie_follow_contract.py, tests/test_upcoming_discover.py.
- Preserve corresponding main documents: docs/plans/2026-10-12-upcoming-movies-backend-rule.md, docs/plans/2026-10-13-movie-follow-startup-scan-fix.md, docs/verification/upcoming-movies/, docs/verification/movie-follow/.
- When a document path exists on both sides with different contents, preserve both records or combine their distinct evidence; never replace newer records blindly.

Already identical after CRLF normalization, requiring preservation rather than reimplementation:

- services/acquisition_store.py, services/tv_acquisition.py, services/tv_filename_parser.py, services/tv_monitoring.py, services/verified_import.py.
- src/features/tv/TVAcquisitionReview.jsx.
- tests/native_tv_server.py, tests/test_verified_tv_acquisition.py, tests/test_tv_follow_season_planning.py, tests/test_tv_source_diagnostics.py, tests/e2e/tv-follow-season-packs.spec.js.
- tools/cp_window.ps1 and tools/stop_stale_backend.ps1.

src/features/tv/tv.css differs because new UI includes adopted styling. Prior inspection confirmed main's two TV repair rules are present. Reconfirm those rules against the actual diff; preserve the adopted styles rather than copying main's stylesheet wholesale.

### Authoritative owners

| Responsibility | Current authoritative file/component/service | Entry point and callers | Behavior to preserve | Competing or obsolete paths |
| --- | --- | --- | --- | --- |
| Upcoming backend membership | app.py: _tmdb_filter_upcoming_movies, _tmdb_person_seed_movies, _tmdb_discover_window, tmdb_discover | Home feed and Discover API, ordinary/Advanced/title/ownership/person callers | Selection before counting/paging, date-aware cache, complete/retry truth | Old unfiltered window must not return through a caller |
| Home Upcoming presentation | src/utils/homeMovies.js with HomeWorkspace.jsx and current App callbacks | Coming soon rail and View all | Returned membership, deduplication, ordering and Trending exclusion | Remove old duplicate frontend date eligibility by integrating main's current helper |
| Movie Follow orchestration | services/movie_acquisition.py and app.py identity/search ports; existing curation store | Startup/Home/manual scans and source search | Fresh pending scan, availability/alert persistence, locks, deadlines, guards | Old movie cooldown/date gate and obsolete eligibility port must not survive |
| TV operations | acquisition_store.py, tv_acquisition.py, tv_monitoring.py, verified_import.py | TV preview/save/Start, lower download controls, worker/recovery paths | Five-hour timing, packs, destinations, validation, safe cleanup and cancellation | Do not apply Movie Follow rules to TV |
| TV support for adopted interface | services/tv_metadata.py, services/tv_read_model.py, services/tv_routes.py | Credit portraits, TV list query/criteria parsing | Portrait compatibility; membership filtering/sorting before pagination; validation | Keep the three approved narrow support changes |
| Shared desktop UI | App.jsx, SharedMovieCards.jsx, MovieCard.jsx, WorkspaceChrome/Controls/SelectionBar/ViewActions/EmptyState, ListsToolbar and adopted callers | All current desktop workspaces | Current geometry, controls, navigation, domain callbacks and visual states | Do not clone shared components or revive replaced markup |
| Artwork loading | src/components/movie-card/cardArtwork.js with MovieCard.jsx, RelatedMovieRail.jsx and IPTVWorkspace.jsx callers | Movie/TV shared cards, Home/Continue, relationships and IPTV series tiles | Shared observer, immediate visible/expanded artwork, stale-notification rejection and eager fallback | Do not replace with eager CSS backgrounds or a second observer implementation |
| List filter performance | src/utils/listCatalogFilters.js and current hook/callers | Movie lists and supported shared filter paths | Zero metadata reads for default browsing; once-per-member metadata for active criteria/sort; identity/order preserved | Do not restore comparator-time repeated metadata construction |
| Production Windows lifecycle | Main run.bat, tools/cp_window.ps1, tools/stop_stale_backend.ps1 and normal app.py entry point | User launch, Power restart/close, backend termination | Build-before-start, scoped stale-backend handling, port 5000, PWA window and restart exit handling | Preview run.bat/tools/ui_preview_launcher.py remain preview-only and are excluded from production activation |

## Exact behavior contract

### Frontend

Use the already integrated new UI as the desktop layout reference, governed by its 2026-10-11 integration plan and 2026-10-12 performance plan. This integration adds no new visual component and changes no grid, spacing, typography, color or control placement.

- Keep adopted Sidebar, workspace controls, list toolbar, shared cards, horizontal rails and existing popover/tooltip owners. Domain callbacks retain Movie/TV/IPTV semantics.
- Upcoming Home uses backend-returned eligible membership. It retains presentation ordering, deduplication and Trending exclusion. View all uses current Discover navigation and criteria, including Back/Forward.
- Followed Home retains the new UI's compact preview/full view and current Scan interaction. Availability labels must reflect persisted backend results; no automatic download or inferred availability from a release date.
- Shared controls, expanded cards and selection preserve state/focus/scroll across paging and repeated navigation. A selector adaptation may target the new UI's semantic role/label but must retain the old behavioral assertion.
- Verify loading, partial/error/retry, empty, populated and long-title/Unicode states on affected surfaces. No misleading final empty state for unresolved filter metadata.
- Verify existing desktop widths used by the adopted design, including 1600x1000 for the primary integration evidence. No mobile or responsive redesign.
- Compare controlled fixtures with the pre-combination new UI for layout preservation and with main for backend-result preservation. Use equivalent data and viewport; live external provider differences are not a valid parity comparison.

### Backend

**Upcoming:** Preserve existing request/response shapes for feed, page/page size, search criteria, ownership/title filters and person-credit queries. Main's current backend filters valid today/future dates before deduplication, retained totals and pagination. Keep day-aware cache keys, provider-date-floor intersection, provider failure/retry semantics and non-Upcoming feeds. Home no longer makes a second date-membership decision. No schema/data migration is proposed.

Example: a provider page containing past, invalid and future dates must be filtered and replenished by the backend. Home and later Discover pages must show the eligible retained collection rather than disagreeing because Home alone hides records.

**Movie Follow:** Preserve the current startup/manual request routes and response shape, curation persistence, scan lock, trusted source/quality checks and bounded source queries. Every fresh scan checks pending films regardless of historical next_check_at or a future metadata release date. Already Available films retain their current treatment. Keep legacy response/storage fields as main currently does: historical scheduling fields are cleared rather than allowed to gate scans; existing skipped metrics remain compatible. No live data rewrite is proposed.

Carry the failed-YTS-identity cache clearing port into the service composition. Preserve successful cached verification, retry of failed reads on fresh scans and on larger remaining budgets, three-second RSS verification budget and 25-second Follow deadline. Preserve eight-second query timeout and three-worker limit. Wrong/unreadable/unverified identities and prohibited sources/quality must never auto-mark Available. Keep existing manual-search fallback rules without turning them into Follow proof.

Example: a followed film with next_check_at next week and a future listed release date can become Available on today's Scan if a qualifying trusted source has verified matching IMDb identity. This writes availability and alerts; it does not start a download.

**TV:** Do not alter TV scheduling, acquisition state transitions, draft/start boundaries, destinations, pack coverage, retry validation/import, cancellation or file-cleanup safety. Keep five-hour unsuccessful searches and Future midnight Africa/Cairo scheduling distinct from metadata refresh and from Movie Follow. No recursive directory deletion or live acquisition is part of integration testing.

**Production startup:** Main run.bat installs/bootstrap-checks dependencies as it currently does, builds frontend before startup, stops only its scoped stale backend, starts its normal app.py and uses cp_window.ps1 to wait for readiness and open the installed Edge web app when found. Existing --app URL fallback remains a standalone window. Preserve window ownership/close and exit-code-75 restart behavior. Normal production workers remain enabled. First-stage tests must not execute main's launcher against port 5000.

## Implementation sequence

### Stage 1 — Preserve and combine in new UI (approved on 2026-10-14)

- [x] Save dated source preservation snapshots and hash/status manifests for both folders, including intentional untracked files. Exclude credentials and runtime state from source evidence; preserve necessary ignored source artifacts explicitly. Do not modify Dante's backup.
- [x] Run the relevant pre-change baseline in disposable fixtures, recording old expected failures and missing-main-fix cases before changing owners.
- [x] Compare the exact current main source with new UI and preserve new UI-only changes when combining the three production files. Do not copy a file blindly if both sides now differ.
- [x] Transfer the listed tests/fixtures and associated plans/verification records. Adapt desktop selectors only where adopted markup requires it, while retaining API and rendered-result assertions.
- [x] Preserve the already matching TV owners and adopted TV CSS. Verify all Movie Follow composition ports/callers agree; remove only obsolete paths replaced by main's already approved repairs.
- [x] Retain new UI's preview launcher/configuration for its preview role. Do not replace it with a launcher that could target production port 5000 during this stage.

### Stage 2 — Isolated combined-source verification (approved on 2026-10-14)

- [x] Run focused regressions and broader Python/Node suites with unique OS-temp roots and blocked providers.
- [x] Build new UI's combined source to CP_TEST_ROOT/dist, leaving both existing served dist directories untouched.
- [x] Run real-route Upcoming and Movie Follow desktop fixtures, plus affected TV, shared UI and performance fixtures.
- [x] Assemble a disposable promotion-source candidate with main's run.bat and matching helper files; run production-launcher regression assertions on that candidate. Do not actually launch production or install/modify an Edge app.
- [x] Record screenshots/results and compare every acceptance row with its contract. Preserve old verification records; new evidence must be dated and distinguish baseline, combined source and promotion candidate.
- [x] Produce a reviewed promotion manifest identifying each file to add/replace/remove and its source/hash. Any removal must name the verified obsolete dependency and be within approved scope.
- [x] Report exact results, failures, skips, limitations and source-only status. Stop before writing into main.

### Stage 3 — Source promotion into main (approved on 2026-10-14)

- [x] Recheck both source states and abort blind promotion if main changed since the tested manifest. Incorporate and retest legitimate new source changes before promotion.
- [x] Preserve Dante's folder copy and establish independent verified rollback snapshots. The observed Desktop folder copy was not edited; its completeness is not claimed. Record effective production configuration/database/runtime paths, database integrity and row counts, current jobs and active download state. Create consistent SQLite backups, including the external Movie database, with a consistent backup method rather than assuming copied open database files are recoverable.
- [x] Preserve current main source/configuration/runtime recovery snapshots without replacing legitimate ongoing job state with older preview or backup state.
- [x] Apply only the reviewed source/tests/docs manifest. Retain main's run.bat, configuration, data/cache, artwork, player/qBittorrent binaries/profile, active jobs and normal startup.
- [x] Exclude preview run.bat, Stop UI Preview.bat, tools/ui_preview_launcher.py and preview configuration/data from production activation. Historical preview documents may remain documentation but must not prescribe the production startup command.
- [x] Verify transferred hashes, effective paths and launcher ownership. No database migration or production-state replacement is expected.

### Stage 4 — Production build and live activation (approved on 2026-10-14)

- [x] Obtain explicit scope for main build and production restart/live checks. Explain that normal startup Movie Follow may query providers and persist availability, and normal TV workers resume their configured behavior.
- [x] Build final main frontend and start via its retained normal run.bat.
- [x] Verify process, port, configuration/data owner and served bundle agree with the final source. Verify standalone PWA window, restart and close behavior through approved checks.
- [x] Check desktop screens and approved operational paths. Manual scans, downloads/imports/deletions are permitted only if explicitly included in the live authorization.
- [x] Compare database integrity/counts and job state with the snapshot, explaining legitimate worker changes rather than claiming all runtime files remain byte-identical.
- [x] Keep new UI and recovery snapshots until Dante is satisfied. No commits, pushes, tags, packaging or release unless separately authorized.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| New UI lacks main's repairs | Combine the approved source and request fixture feeds/scans | Adopted UI remains; main's repaired behavior passes in the combined source | Three production files and adopted callers | Source manifest plus focused and real-route suites |
| Upcoming includes past/unknown/invalid/today/future dates | Request native and filtered feed | Only valid today/future entries; selection precedes deduplication/counting/paging | app.py Discover owners | tests/test_upcoming_discover.py |
| Sparse Upcoming page or adverse duplicate | Request first/later pages, retry after provider failure | Eligible replacements fill pages when available; totals/retry truth retained; no phantom next page | Discover window | Upcoming pagination/failure/duplicate tests |
| Advanced/title/ownership/person Upcoming and date rollover | Apply criteria; cross calendar date in fixture | Same eligibility; criteria intersect rather than remove date floor; cache changes with day | Discover plan/person/cache | Upcoming backend regressions |
| Home Upcoming and history | Home View all, direct Discover, later pages, Back/Forward | Backend membership and paging retained; Home preserves ordering and Trending exclusion | HomeWorkspace/App/helper/Discover | tests/homeMovies.test.mjs and tests/e2e/upcoming-movies.spec.js |
| Pending Movie with future retry/date | Startup/reload and two consecutive Scan actions | Each action freshly checks pending movies; qualifying verified release persists Available/alert; no download | MovieAcquisition/Home/curation | tests/test_movie_follow_contract.py and tests/e2e/movie-follow.spec.js |
| Alternate title/year but verified matching YTS IMDb | Fixture RSS/query returns qualifying release | Correct movie becomes Available; verified identity outranks descriptive mismatch | Identity ports and Follow | Movie Follow/YTS/source-search tests |
| Wrong/unreadable identity, prohibited quality or untrusted source | Fixture returns adverse source | Never auto-mark Available or download | Follow/identity/acquisition guards | Movie Follow, YTS, identity and acquisition regressions |
| Failed cached identity read or short RSS budget | Fresh scan/larger-budget verification with fixture outage | Retry where allowed; maintain three-second RSS and 25-second Follow budgets | app.py ports/MovieAcquisition | Existing cache and controlled-time outage regressions |
| Existing TV Missing/Future draft/started task | Preview/save/Start; advance fixture time | Draft is not a started task; five-hour retry and Cairo air-date timing remain | TV acquisition/monitoring | TV contract and season-planning tests |
| TV pack with auxiliary files or saved failed import | Fixture validation/import/retry/cancel | Coverage/destination truth preserved; safe owned-file cleanup; explicit Retry remains | Verified import/recovery/review | Verified TV and source-diagnostics suites plus native-TV desktop fixtures |
| TV list criteria and credits | Filter/sort/page; open portrait credits | Full membership filtered before paging; validation and portrait behavior preserved | tv_read_model/tv_routes/tv_metadata | tests/test_tv_list_filters.py and tests/test_tv_credit_portraits.py |
| Offscreen/visible/expanded cards; replaced artwork URL | Navigate, expand/collapse, scroll, deliver stale observer notification | Deferred offscreen loads; immediate visible/expanded loads; stale notification rejected; geometry retained | cardArtwork/shared callers | tests/e2e/card-artwork-performance.spec.js plus existing shared-card coverage |
| Default and actively filtered lists | Browse/filter/sort/page | Default reads zero filter metadata; active processing once per member; membership/identity/order preserved | listCatalogFilters/current callers | list-catalog-filters and list-catalog-performance Node suites |
| Desktop empty/loading/error/long content | Fixture states and repeated navigation/selection/history | Existing adopted controls, retry messaging, spacing, cards, focus and scroll retained | Home/Library/Discover/Lists/TV/IPTV/shared | Compiled app-smoke, controls, scroll-return, Continue, TV and IPTV suites |
| Production source candidate with main launcher | Inspect/run isolated launcher regression tests | Main build/bootstrap/start/close/restart behavior and installed-app/fallback arguments retained | run.bat/cp_window/stop_stale_backend | tests/test_windows_launcher.py on candidate; actual PWA behavior remains a live gate |
| Promotion candidate contains preview state | Review manifest and effective configuration | Preview launcher/data/settings excluded from production; main runtime remains authoritative | Source promotion/data boundary | Whitelist/hash review and protected-state comparison |
| Main activated under explicit approval | Start normal main; inspect served bundle/PWA/data | Correct new UI bundle; standalone window; correct main owners; normal workers; recovery available | Production launcher/backend/dist | Separate dated live evidence, not a fixture claim |

## Verification and rollout

### Baseline and known failures

Before source edits, rerun relevant baselines in isolated fixtures. No current test result is claimed in this draft.

Historical new UI performance evidence (docs/verification/mostafa-performance/RESULT.md) recorded 224 broad compiled desktop passes and a full Python run with 7 failures and 3 errors. Three failures were caused by an incorrect system-qBittorrent fixture mode and passed a corrected focused embedded-fixture rerun. The full historical suite was not rerun green.

Other historical exceptions include IPTV projection timing, pinned offline awards seed input, an obsolete streamLoaded source assertion, and production-launcher assertions executed against a preview launcher. Preserve logs and assertions. Test the appropriate production candidate for the launcher; do not redefine production behavior to match preview. Unexpected/new failures block promotion until resolved or explicitly reviewed; genuine unrelated baseline failures must be identified with controlled evidence.

Main's Movie Follow record documents 160 Python passes and two real-route desktop passes on its earlier isolated source. Those counts are historical, not combined-source results.

### Environment and commands

Execute from new UI's absolute working directory:
C:\Users\dante\.codex\worktrees\mostafa-ui-ux\cinema paradiso

For each fixture run, create a new GUID-named directory under the resolved Windows OS-temp root. Set CP_TEST_MODE=1, CP_TEST_ROOT to that directory, and CP_TEST_DIST_DIR to its dist subdirectory. Use fixture providers/transfer responses only. Use CP_TEST_QBT_MODE=embedded for embedded power/proxy/acquisition tests; select any differing mode only for the named fixture that requires it. Never globally force system mode for the broad suite.

Do not invoke run.bat for isolation. It performs dependency installation, production lifecycle work and writes served dist. The existing tools/run_playwright_e2e.ps1 also forces system mode, so do not use it unchanged for an embedded-fixture gate.

Planned focused commands, with the above environment already configured:

~~~powershell
.\.venv\Scripts\python.exe -B -m unittest tests.test_upcoming_discover tests.test_movie_follow_contract tests.test_user_curation_store tests.test_yts_option2 tests.test_curation_routes tests.test_source_search_service
.\.venv\Scripts\python.exe -B -m unittest tests.test_tv_download_contracts tests.test_tv_follow_season_planning tests.test_tv_source_diagnostics tests.test_verified_tv_acquisition tests.test_tv_list_filters tests.test_tv_credit_portraits
node --test tests/homeMovies.test.mjs tests/list-catalog-filters.test.mjs tests/list-catalog-performance.test.mjs
npm.cmd run build -- --outDir $env:CP_TEST_DIST_DIR
~~~

Also run existing relevant Discover paging/criteria, identity, acquisition-decision, download-monitor, shared UI, performance and launcher modules. Confirm module names against the source manifest before dispatch.

Broader commands:

~~~powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_*.py'
$cpIntegrationNodeTests = @(Get-ChildItem -LiteralPath tests -Filter '*.test.mjs' -File | ForEach-Object FullName)
node --test @cpIntegrationNodeTests
git diff --check
~~~

For real-route desktop checks, use the existing scenario fixture directly, after confirming a free nonproduction port:

- Upcoming: tests.discover_paging_server with CP_PORT/CP_E2E_PORT=5117; run tests/e2e/upcoming-movies.spec.js and relevant Discover paging cases.
- Movie Follow: tests.movie_follow_server with CP_PORT/CP_E2E_PORT=5118; run tests/e2e/movie-follow.spec.js.
- TV: tests.native_tv_server and its documented fixture flags for season packs, normal import, navigation and expanded-card parity.
- Shared UI/performance: the existing isolated fixture seed procedures and compiled suites documented in new UI's integration/performance records.

Fixture launch must use new UI as WorkingDirectory, the resolved new UI Python executable, hidden process windows, logs under the temporary root and owned process cleanup only. Wait for readiness of that fixture; never reuse an existing listener or stop port 5000.

Playwright test invocation after starting the appropriate fixture:

~~~powershell
.\node_modules\.bin\playwright.cmd test tests/e2e/upcoming-movies.spec.js
.\node_modules\.bin\playwright.cmd test tests/e2e/movie-follow.spec.js
~~~

The two commands above belong to separate matching fixture runs, not one shared server. Set Playwright artifact output under the temporary root or new dated evidence directory; do not overwrite existing evidence.

### Compiled UI and promotion gates

1. **Source gate:** All planned owner/caller changes are reviewed, no competing old behavior remains, and protected source manifests account for every intentional change.
2. **Isolated behavior gate:** Focused and relevant broader results recorded; motivating API and rendered UI paths pass; baseline exceptions distinguished from new failures.
3. **Compiled desktop gate:** Equivalent fixtures demonstrate new UI layout preservation, main backend-result preservation, repeated navigation/history and performance contracts.
4. **Production candidate gate:** Main launcher/helpers tested against assembled source; exact whitelist ready; no preview state in production selection.
5. **Promotion gate:** Separate approval, refreshed source/runtime snapshot and consistent backups; copied hashes match the tested candidate.
6. **Live gate:** Separate build/restart authorization and actual process/configuration/bundle/PWA/operational evidence.

### Backup, rollback and reporting

A folder copy alone does not prove consistency of an open SQLite database and does not include the external Movie catalog unless explicitly copied. Before promotion, verify the actual backup destination, include consistent Movie/TV database backups and capture configuration/job/runtime recovery state without changing production state.

Rollback triggers include failed main build/start, wrong data ownership, unexpected database integrity failure, new agreed-contract regression or incorrect PWA lifecycle. Roll back the approved source/bundle set using preserved snapshots. Do not automatically overwrite newer active jobs/catalog state with an older backup; a data restore is a separate decision requiring review of intervening runtime changes.

For every stage report:
- source files changed and preserved;
- exact test counts, skips, failures and environments;
- whether evidence is source-only, isolated compiled UI, or live;
- all differences from approved contracts and their user impact;
- remaining approvals, uncertainties and recovery options.

## Supporting records

- Main: docs/plans/2026-10-12-upcoming-movies-backend-rule.md.
- Main: docs/plans/2026-10-13-movie-follow-startup-scan-fix.md.
- Main: docs/verification/upcoming-movies/.
- Main: docs/verification/movie-follow/2026-10-13/verification.md.
- Both: docs/tv-contracts.md and preserved 2026-10-10 TV plans/verification.
- New UI: docs/plans/2026-10-11-mostafa-ui-ux-integration-plan.md.
- New UI: docs/plans/2026-10-11-mostafa-ui-preview-setup.md.
- New UI: docs/plans/2026-10-12-mostafa-performance-plan.md.
- New UI: docs/verification/mostafa-ui-ux/RESULT.md.
- New UI: docs/verification/mostafa-ui-preview/RESULT.md and launcher-restart/RESULT.md.
- New UI: docs/verification/mostafa-performance/RESULT.md.
- Original integration discussion: 01a12c28-f9e3-7242-ad56-f8118974a87e.
- Performance discussion: 01a12d9a-b6f3-7052-85d9-003e4f394251.
- Movie Follow discussion: 01a136ee-6220-7933-bbc8-068f87e6dd0e.


## Execution approval and progress

All four stages approved by Dante on 2026-10-14. Earlier pending-approval labels describe the draft history and are superseded by the Status and this approval. Execution ledger: C:\Users\dante\.codex\worktrees\mostafa-ui-ux\cinema paradiso\.superpowers\sdd\2026-10-14-new-ui-main-integration\progress.md. Recovery and fixture artifacts: C:\Users\dante\AppData\Local\Temp\cp-new-ui-main-3cca1a48528b40d2ae9d5fffb8722f55. Final verification will be recorded under docs/verification/new-ui-main/2026-10-14.

### Verification-discovered repairs authorized by the all-steps approval

The first broad candidate run completed 1,752 tests with five failures and one setup error. Its temporary checkout invalidated two tests whose purpose is to reject paths outside OS-temp; it also included a preview-only launcher test without the preview source. This is retained as diagnostic evidence, not a green production-suite claim. New UI's CRLF-only byte differences in pinned awards inputs broke their hashes in the temporary candidate; production promotion retains main's exact pinned inputs, including CSV. The final broad suite must execute from actual main using disposable test data, rather than treating an OS-temp checkout as a valid fixture for outside-temp path guards.

Two baseline failures were reproduced in main before promotion:
- tests/test_qbittorrent_ui.py contained obsolete streamLoaded/preparation-message assertions. Update them to the already implemented streamStatusVisible iframe-page-load lifecycle and truthful page-loading text. Existing compiled stream-player cases prove visible behavior; no streaming product source changes.
- First-time IPTVMovieStore creation flushed CREATE statements individually because sqlite3.executescript implicitly ended the outer transaction. services/iptv_movie_store.py now begins a transaction inside each of its four SQL schema batches. The schema version remains4; provider ownership, migration backup/restore and API behavior remain unchanged. This batches DDL writes and makes each individual SQL batch atomic, not the entire multi-stage initialization/migration.

A new actual-SQLite failure-injection regression first failed on the old owner with persisted partial tables, then passed after the batch transaction repair; retry builds schema4. Existing nonblocking projection regression retains its original<1-second assertion. Three interleaved cold-start samples measured old0.957/1.063/1.092seconds versus new0.133/0.159/0.183seconds, with all200fixture movies projected and identical final completion. This is specific initialization evidence, not a claim that all IPTV operations are faster.

The independent reviewer inspected this additional owner repair and found no must-fix issue. Final main full suite passed 1,752 tests, including IPTV migrations and the new atomicity/nonblocking regressions. Include tests/test_iptv_movie_gates_0_5.py and tests/test_qbittorrent_ui.py in the promotion manifest. Snapshot all active IPTV provider catalogs/movies databases as well as the four core databases before activation. No live schema migration is explicitly initiated.


## Final completion record

Completed without another routine approval pause. Main now contains the integrated desktop UI, main's preserved Upcoming/Movie Follow fixes, TV support and acquisition repairs, and the verified IPTV schema-batch initialization repair. Final effective source/tests/documentation promotion manifest contains183files; main's exact pinned award reproduction namespace was restored and retained after a postpromotion check detected byte-sensitive newline differences. The final retained-contract gate passed75tests.

Verification: actual-main full Python1,752/1,752; all top-level Node133/133; all302desktopcases passed across matching fixtures. Initial failed diagnostic/candidate/contaminated-fixture runs are preserved in the dated verification logs; they are not presented as green runs.

Normal main run.bat built the production bundle and opened the installed PWA on localhost5000. A real CP restart through its Power API replaced backendPID54304 with55580, closed/reopened its owned app window and retained qBittorrentPID14308/port8686 with two active downloads. Startup metrics prove normal background owners were queued; no preview worker pause or private preview configuration was activated. Source, configuration and served index checks passed.

Controlled live desktop rendering at the known local URL verified Home,40Movie Library cards,32TV Library cards and Back/Forward with zero JavaScript or HTTP500errors. Extra Follow scans and other mutating test requests were blocked; normal production startup scans remained enabled. Home was observed during feed loading, so the live render does not claim successful real-provider feed completion. Native app-window inspection was refused because Computer Use could not determine the Windows browser URL confidently; that native automation stopped. Installed-app mode and window ownership/restart were verified through the actual launcher state.

All eight active Movie/TV/acquisition/awards/IPTV databases have consistent postactivation backups with integrity ok and table counts equal to the preactivation snapshots. Configuration and run.bat retain their original hashes. Main's catalog/media/list data, active jobs, runtimes and profiles were not replaced with new UI copies. Runtime timestamps/leases may change through normal operation; byte identity of all runtime state is not claimed.

Rollback: C:\Users\dante\Desktop\CP integration rollback 2026-10-14-3cca1a48. New UI and snapshots remain available. No commit, push, branch deletion, packaging, tag or release was performed.

Final evidence: docs/verification/new-ui-main/2026-10-14/RESULT.md and final-proof.json.
