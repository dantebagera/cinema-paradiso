# TV parity and usable episode downloads

Status: implementation completed in the existing worktree on 2026-09-18 and ready for Dante's testing. Verification finished with one previously observed intermittent IPTV timing assertion failure in the latest full backend suite; this remains unresolved and is explicitly recorded in `docs/verification/tv-parity/implementation-report.md`. UI, acquisition, isolated-client, build and preservation evidence are recorded there.

Workspace: `C:\Users\dante\.codex\worktrees\0870\cinema paradiso`.

This plan covers both sets of screenshots and the subsequent discussion. It corrects the earlier stabilization work's incomplete user experience. Earlier passing tests are historical evidence, not proof that these issues are resolved. No application code, configuration, database, runtime, or live transfer is changed by writing this document.

## 1. Intended result

Dante can browse TV using the same desktop search/filter conventions as Movies, see useful TMDB information on cards and detail pages, and search for downloads directly from a series preview. Selecting one episode, several episodes, missing episodes, or a season leads to a useful choice of releases and a clear download action. CP tracks the chosen downloads automatically without requiring a separate Add series step or enabling monitoring.

The work is one coordinated change delivered in verified stages. Movie behavior, existing TV files/progress, streaming, settings, and qBittorrent recovery remain protected throughout. Desktop only; no unrelated redesign, mobile work, movie acquisition policy changes, Sonarr service dependency, or automatic-upgrade rollout.

## 2. Confirmed findings and remaining diagnosis

| Issue | Current owner and finding | Required correction |
| --- | --- | --- |
| Short search bar and separate plus row | `TVSearchControls.jsx` builds a separate flex toolbar and always renders `AdvancedSearchBuilder` below it. Shared query logic alone did not produce movie UI parity. | Reuse the movie search presentation and interaction contract, not just its advanced-query component. |
| Missing familiar filters | Library's movie toolbar exposes resolution/source/genre/viewing/language/country/year/rating/sort; Discover exposes genre/language/country/votes/year/rating/sort. TV lacks the equivalent presentation. | An explicit field-by-field parity inventory, shared controls, and TV-specific mappings. |
| Bottom-only pagination | TV uses its own Previous/Next markup; Movies already uses `Pagination.jsx` above and below results. | Use that owner with one page state and correct known/unknown totals. |
| Sparse Discover cards | `TVMetadata.normalize` retains genre IDs but produces genre names only from detailed genre objects. `TVSearch.discover` enriches only certain query combinations. `TVSeriesCard` omits original language and country in Discover. | Resolve TV genre IDs and present available summary metadata independently of download state. |
| Inconsistent counts | Discover's local-state merge can overwrite provider episode counts with zero for an unsaved show. | Keep provider totals separate from local available/completed/released counts. |
| Slim, cropped poster | `tv.css` sets a narrow fixed width and `object-fit: cover` inside a stretched flex header. | Preserve natural poster ratio, prevent shrink/stretch, and fit the complete image. |
| Missing cast experience | Normalization requests aggregate credits; the page renders text credits after the entire episode list. Local reads fetch missing fields only when the trailer field is absent; repository credits are limited and sorted by internal person ID. | Trace the reported examples, distinguish absent data from buried content, then place ordered cast visibly near the overview with portraits/roles and independent loading/error handling. Do not claim the exact reported missing-cast cause is proven yet. |
| Add series prerequisite | The page renders season/episode search controls only when a local series ID exists. Acquisition targets require local episode rows. | Separate provider-based search targets from durable download tracking. |
| Results cannot be downloaded | TV matching requires explicit TMDB/TVDB IDs. Shared evaluation requires an upfront torrent hash; resolving a Prowlarr download link happens only later at submission. | Evidence-based series matching and transport resolution before final submission eligibility. |
| No multi-episode selection | A season target requires each candidate to cover every requested episode; there is no combination planner. | Candidate coverage and request fulfilment must be distinct. |
| Results buried in diagnostics | `TVAcquisitionReview` shows `AcquisitionDecisionDetails` first, with accepted download actions in a separate list below. | One actionable results list; diagnostics expandable per result/source. |

## 3. Ownership: improve the existing path

| Responsibility | Authoritative implementation to extend |
| --- | --- |
| Search UI and criteria | Movie `LibraryWorkspace.jsx` / `DiscoverWorkspace.jsx`, `AdvancedSearchBuilder.jsx`, `advancedSearchModel.js`, `advancedSearchRegistry.js`; extract only reusable presentation into shared search components and migrate existing consumers without changing their behavior. |
| TV query execution | `services/tv_search.py`; keep legacy TV endpoints delegating here. Remove TV query duplication introduced by local toolbar state as controls migrate. |
| TMDB normalization and display metadata | `services/tv_metadata.py`, `tv_read_model.py`, `tv_catalog_repository.py`; one normalized TV metadata contract for previews and saved shows. |
| Cards, details, pagination | `UnifiedMovieCard`, `Pagination.jsx`, existing movie cast presentation where reusable, and `TVWorkspace.jsx`. |
| Release parsing and identity | Extend `tv_filename_parser.py` with structured title/year/numbering evidence. `TVAcquisition` owns matching to the selected canonical series. Do not introduce a second episode parser or bypass this owner from UI/routes. |
| Search, combinations, download intent | `tv_acquisition.py`, `tv_routes.py`, `acquisition_store.py`. A focused pure planner may be extracted from the acquisition owner; it must not become another queue or transfer store. |
| Quality decisions | `acquisition_decision.py`, `acquisition_profiles.py`, `quality_catalog.py`; TV supplies richer evidence and explicit wanted/covered sets. Default movie decision behavior remains unchanged. |
| Torrent link resolution and transfers | Existing `_resolve_prowlarr_download` / `_submit_qbittorrent_candidate` in `app.py`, `services/qbittorrent.py`, and its `jobs.json`. Extract a common resolver only if needed; migrate both callers and remove the superseded implementation. |
| Manifest validation and import | `TVAcquisition.validate_manifest`, `verified_import.py`, current TV file bindings and checkpoint mechanisms. |
| Player | Existing `StreamPlayerModal`, trailer modal, and typed TV URL builder. No new TV player. |

Keep separate movie, TV, and IPTV ownership. Additive TV/acquisition schema changes require migration and restore tests. Reuse existing columns/contracts when sufficient. New selection evidence must not be squeezed into a fake single-episode target or an unverified `identity_verified=True` shortcut.

## 4. Search, cards, and details contract

### Search and filters

- Match the corresponding movie tab's full-width field, integrated criterion-add control, mode switching, filter expand/collapse, clear/reset, refresh, spacing, keyboard behavior, and focus behavior. No permanent warning-looking advanced bar in normal title mode.
- Library TV: resolution and upgrade candidates, source, genre, watched/unwatched/in-progress/watchlist, original language, country, first-air year range, minimum rating, and corresponding sorting. Keep TV status, monitoring, missing/available episodes, and measured audio language available as TV-specific controls.
- Discover TV: genre, original language, origin country, minimum votes, first-air year range, minimum rating, feed, and sorting. Retain applicable advanced person/actor/director/writer/creator, keyword, runtime, exclusion, and AND/OR criteria.
- Clearly distinguish original language from measured audio language. A year means series first-air year, not episode air year; runtime means episode runtime. Put explanations in labels/help, not a permanent paragraph of implementation details.
- Movie-only list, file-management, collection, and budget actions do not get meaningless TV equivalents. The parity inventory must name each omission rather than silently dropping controls.
- One canonical query state drives simple controls and advanced criteria. Switching modes, changing filters, returning from details, changing Movies/TV, and browser Back must preserve the correct independent workspace state. Reset clears every criterion and returns to page 1. Late requests cannot overwrite a newer query.
- Reuse `Pagination` above and below series results and long episode lists, with consistent disabled/loading states and page changes. Match movie scroll/focus behavior.

### Correct filtering scope

Library filtering and sorting occur before pagination. Finite person-credit results must also be combined, filtered, and sorted before pagination; this removes the current unnecessary page-local limitation for that case.

For remote title searches combined with criteria unsupported by the provider endpoint, extend the existing TV query owner with bounded continuation through provider pages. Cache by the complete normalized query; deduplicate by typed TV ID; fill displayed pages from matching results. Preserve continuation when a scanned page is empty. Never claim a complete total or globally sorted result until the candidate set is exhausted. A scan budget/rate limit must show a concise partial-results state with a continuation action, not falsely report no matches. Direct provider-supported queries keep provider pagination and ordering. Freeze request-count and deadline bounds in tests before implementation is accepted.

### TMDB metadata and cards

- Map summary `genre_ids` using the TV genre dictionary. Reuse language/country dictionaries for readable labels; follow movie country-chip conventions.
- Title, poster, rating/votes, genres, original language, and country do not depend on a local file or Add to library.
- Cache and coalesce bounded detail enrichment for status, year range, counts, or missing fields. Render known summary fields immediately. One failing detail request must not fail the entire result page or erase existing data.
- Keep announced/listed, released, available, and completed episode counts distinct. Unknown is not zero. Do not label an unsaved Discover result Unmonitored as if that were its main metadata.
- Ownership reflects available local episode files. Use explicit partial availability when only part of a show is present; a tracking record or queued download never implies full ownership.

### Detail page

- Show the full poster at its natural aspect ratio, with no clipped edges or horizontal page overflow at the agreed desktop sizes.
- Put main cast near the overview, before a potentially long season episode list. Retain TMDB ordering, portraits, character names, and creator credits; deduplicate people with multiple roles. Missing portraits have a normal placeholder. Guest cast remains episode-specific.
- Treat credits, trailer, and other detail fields independently: an existing trailer key cannot suppress repair of missing cast. Known empty credits, failed loading, and not-yet-loaded credits are different states with appropriate retry behavior.
- Preview and saved detail views have the same information and download affordances. Saving must not distort the header or drop metadata.
- Keep streaming, trailer, watch progress, and episode targeting on their existing owners; opening or closing a stream does not mark watched.

## 5. Download flow and matching

### User actions

Display Download season beside the season selector and Download episode on released episodes. These open a release chooser; they do not immediately start transfers. Episode checkboxes support Select all released, Select missing, and Download selected, including selections across episode pages. Show the selected count and scope. Exclude unaired/unknown-release episodes with a clear explanation.

Browsing and search may use caches and expiring search records but do not insert a tracked series, enable monitoring, or create a qBittorrent job. Optional Add to library is explicitly for tracking without downloading. On a confirmed download, save/resolve the series and the selected season metadata, map canonical provider episode identities to local rows, and create the durable acquisition intent. Do not fetch every season of The Simpsons just to download season 1. Partial metadata fetches must never delete unrequested seasons or existing episode bindings.

Watchlist, tracking, actual ownership, and automatic monitoring remain distinct. The existing monitor rule is preserved for a known series; a newly tracked series defaults to monitoring off. Manual download does not turn it on.

### Matching evidence

Keep two separate identities: which show/episodes a release claims to contain, and which torrent will be transferred.

- Prefer supplied provider IDs, but detect conflicts with parsed title/year rather than accepting either ID blindly.
- Without IDs, compare normalized canonical/original titles and known aliases, year where present, and compatible episode numbering. Exact title/alias plus consistent disambiguation can support a manual candidate; merely appearing in a search is not proof.
- Dark Matter 2015/2024 and Daredevil/original versus Born Again are explicit collision fixtures. Ambiguous same-title releases need a deliberate identity review; a conflicting ID/year stays blocked. Never silently choose the first match.
- Parsing returns title/year, single episode, episode range, season pack, daily date, and evidence. Preserve existing specials/daily handling. Unsupported absolute/scene numbering requires an explicit mapping rather than a guessed episode.
- Separate eligible, needs identity review, needs transport resolution, and blocked states. Display concise reasons. Soft uncertainty must not masquerade as a permanent hard rejection; real contradictions are not bypassed by a generic Force download button.

### Torrent transport

Resolve selected Prowlarr download URLs through the existing trusted resolver, preserving URL restrictions, credentials, timeouts, size bounds, and magnet redirects. Extract/compute the hash from a valid magnet or torrent file before creating a transfer intent. Revalidate the selected candidate against resolved transport; a mismatch is a hard error. Do not resolve every search hit eagerly.

For magnets needing file metadata, use the existing stop-after-metadata transfer path after the user's Download action. Do not start payload download until the manifest passes validation. A magnet hash identifies a torrent, not the TV show; these checks must not be conflated.

## 6. Multiple episodes and season planning

Represent the wanted set as stable provider episode identities plus numbering and metadata revision. A candidate has claimed coverage; verified file coverage is a later, distinct fact. A season label alone must not be recorded as verified proof of every episode.

- Search TV-capable configured indexers; preserve explicit custom selections, including an empty selection. Never apply the movie YTS restriction to TV.
- Use season searches first and bounded episode searches for uncovered selections. Keep completed results when sources fail. Fairly merge/deduplicate before limiting results; remove the current first-100-results bias that can hide useful later sources.
- Compare full packs, multi-episode releases, and individual episodes. Filter hard failures, rank by the chosen quality policy and useful coverage, then construct a deterministic combination without requesting the same episode twice. This is a bounded planner, not a claim of mathematically optimal selection over unlimited releases.
- Default to missing, unqueued episodes. Existing available episodes are retained. Replacements require an explicit upgrade choice; this work does not enable automatic upgrades.
- Show selected releases, episodes covered, gaps, total estimated size, and any extras before confirmation. Pack versus individual options remain selectable. A plan with gaps must say partial and require a clearly labelled Download available action.
- Example: wanted S01E02/E03/E04; choose one E02-E03 release plus one E04 release. Do not also queue E03 separately. If a season pack is selected, do not queue its covered episodes individually.
- If a pack includes unwanted separate files, select only intended files after manifest verification using the existing qBittorrent owner extended with file-priority support if needed. Verify the selection before resume. If a file combines wanted and unwanted episodes, disclose the inseparable extra content and require that specific choice. Do not silently download a whole pack or promise exact byte-level exclusion of shared torrent pieces.
- A batch is a group of per-torrent intents. Reserve aggregate disk space and episode targets; deduplicate by resolved hash and target coverage across concurrent requests. Persist per-item outcomes. Retrying a partial batch submits only failed/unsubmitted items; already submitted torrents are not rolled back or duplicated.
- Recheck profile version, available/queued episodes, numbering, transport, and free space at submission. A changed plan returns a concrete revised review.
- Manifest validation checks actual filenames, series identity evidence, episode mappings, wanted coverage, safe paths, samples/extras, and quality contradictions. Import verifies measured facts and publishes only valid selected bindings. Existing files, seeding behavior, cancellation, retries, and recovery continue through current owners.

## 7. Release chooser presentation

One list contains release title, claimed episode coverage, quality/source, size, seeders, indexer, match state, and an inline action. Eligible choices appear first. Needs-review choices have a specific resolution action; blocked items have readable reasons behind an optional filter. Diagnostics and per-source failures are expandable. Keep a compact partial-results banner and Retry without requiring the user to scroll past every indexer.

Keep the selection summary and Download selected action reachable; provide Close/Escape, focus restoration, loading/empty/error states, and cancellation that ignores stale responses. Closing search never submits. Do not show a second disconnected accepted-release list below diagnostics.

## 8. Implementation order and completion gates

1. **Capture baseline and reproduce.** Back up the current dirty worktree state and source hashes, including untracked files, without copying secrets into evidence. Identify config/runtime roots without changing them. Record movie reference layouts and each reported TV failure against compiled assets. Trace TMDB credit responses for the named examples. Freeze parity/acceptance cases before edits.
2. **Correct acquisition contracts.** Implement provider-based targets, identity evidence, resolution-before-final-eligibility, and nontracking preview search. Keep movie defaults unchanged. Gate: raw-style Prowlarr responses lacking IDs/hash can reach the correct review/resolution state; collisions and hostile transports stay blocked.
3. **Complete single and batch downloads.** Implement wanted-set planning, selection UI, automatic tracking on confirmed download, manifest selection, batch persistence/recovery, and actionable results. Gate: full isolated search-to-import scenarios pass, including partial batch retry without duplicates.
4. **Complete metadata and visual parity.** Share search presentation, expose all mapped filters, fix normalization/counts/cast/posters, and use top/bottom pagination. Gate: screenshots and interaction assertions match the movie reference at equal viewport/scale. No list of hidden controls counts as parity.
5. **Qualify the integrated result.** Run the relevant tests first, then full serial backend/Node/browser checks, production build, served-asset verification, and the desktop scenario walkthrough. Investigate failures without weakening assertions to fit broken behavior.

Each gate is an internal implementation checkpoint, not another permission prompt once implementation is approved. If a temporary adapter is necessary, document its consumer and removal condition and remove it when that consumer migrates. No second permanent acquisition pipeline or duplicated search state.

## 9. Acceptance and regression evidence

| Scenario | Required observable result |
| --- | --- |
| Discover landing, title search, person search, Library TV | Same movie search/filter conventions; correct genre/language/country even without a local file; independent state and working reset. |
| Combined person/genre/year query | Filtering before finite-set pagination; correct AND/OR roles; no unexplained loss of matches on page changes. |
| Remote title plus unsupported provider filter | Continuation works through empty provider pages; partial scope is explicit; no fabricated totals or global sort claims. |
| Dark Matter 2024, unsaved | Full poster, visible cast, Download season and Download episode available without Add series. Search/close leaves tracked-series count and monitoring unchanged. |
| Dark Matter ambiguous release | 2015 and 2024 cannot silently cross-match, even if numbering is identical. |
| Daredevil: Born Again | Season action visible in preview; credits clearly visible before episode list; ordinary Daredevil release rejected/reviewed appropriately. |
| The Simpsons season 1 | Useful release choices without requiring catalog IDs on every indexer row; season 33 episodes do not fulfil season 1. No full-series refresh prerequisite. |
| E02-E04 selection | Correct pack/individual combination, exact selected coverage, visible gaps/extras, no duplicate E03; selection survives pagination. |
| Missing/queued/owned episode mixture | Skip owned and already queued targets by default; retain existing files and progress; no false ownership from tracking alone. |
| One successful source, one timeout, one failure | Completed candidates remain actionable; concise partial notice; retry/cancel cannot introduce stale results. |
| Torrent URL with no initial hash | Trusted resolution yields a valid hash or an actionable error; no permanent rejection solely because the listing omitted it. |
| Bad manifest or swapped transport | No payload resume/import; show the reason and preserve prior library state. |
| Partial batch failure/restart/double click | Durable individual outcomes; no duplicate torrents/intents; failed items can retry; reservations recover. |
| TMDB slow/offline/empty credits | Existing data survives; cards still render known fields; loading versus failure versus known-empty is distinguishable and retryable. |
| Desktop 1920x1080, 1920x720, and 1366x768 | Full poster, visible search controls, usable cast/results, no horizontal overflow, accessible dialog actions; no mobile testing scope. |
| Movie and shared regressions | Related movies, movie filters/advanced search/pagination/selection, canonical details, stream/trailer controls, native player routing, settings, IPTV, downloads, and background catalog updates remain covered. |

Use three evidence levels, labelled separately:

1. Deterministic tests with realistic sanitized provider response shapes, including absent IDs/hash, aliases, collisions, packs, missing sources, and changed plans. Fixture tests must not manufacture ideal evidence to avoid the reported failure.
2. Read-only configured-provider searches and metadata/link-resolution checks for the named examples where available, with credential-redacted output and no real qBittorrent submission. Provider outages are reported honestly; they are not replaced with a claim of live success.
3. Complete download/import/recovery tests with lawful synthetic media, disposable databases, an isolated qBittorrent instance where available, and a local test seeder. A fake transport test alone cannot establish real client file-selection/stop-after-metadata behavior. If that client integration cannot be exercised, record the gap and do not claim it verified.

Use `CP_TEST_MODE=1` with unique OS-temporary roots and isolated ports. Full suites run serially where timing assertions are sensitive. Build and verify the served artifact, then visually inspect it; source tests alone cannot prove UI completion. Record baseline failures separately, test counts with their actual run scope, screenshot evidence, bundle hashes, and unresolved limitations.

## 10. Preservation and handoff

Keep this worktree's retained original settings and launch entry point intact. Do not run Dante's `run.bat`, restart normal CP, touch original Desktop source, mutate live catalogs/media/monitor rules, submit real downloads, commit, push, or release as part of implementation qualification. Live validation here means provider reads; live download operation is separate from the isolated test workflow.

Before implementation, make a targeted recoverable snapshot of current changed/untracked source. Before any disposable migration test, capture and verify a disposable database backup. Never use a hard reset or overwrite the existing worktree to roll back this change. Keep rollback scoped to edits made for this plan.

Handoff includes the exact batch path, configuration-preservation result, implementation report mapped to the acceptance table, screenshots, test/build/served-asset evidence, and any remaining provider/client limitations. Completion requires both usable TV downloads and the requested visual/metadata parity. Do not label a result complete merely because searches return rows or automated tests pass.

## 11. Research references

The existing `local-tv-backend-sonarr-adoption-zero-regression-plan.md` remains the architecture reference: learn episode-aware matching, release decisions, and import handling within CP rather than installing Sonarr or copying its source.

Current primary-source inspection confirms title/year/alternate mappings and episode mapping in [Sonarr ParsingService](https://github.com/Sonarr/Sonarr/blob/develop/src/NzbDrone.Core/Parser/ParsingService.cs), with release decisions composed separately in [DownloadDecisionMaker](https://github.com/Sonarr/Sonarr/blob/develop/src/NzbDrone.Core/DecisionEngine/DownloadDecisionMaker.cs). These are behavior references; the proposed batch UX and CP implementation above are our design, not a claim that Sonarr exposes that exact flow.
