# Local TV Frontend: Desktop Zero-Regression Implementation Plan

**Status:** Proposed for review. Documentation only; implementation is not approved.

**Prepared:** 2026-09-14

**Revised:** 2026-09-18 to preserve the TV Streaming button and shared movie rules

**Depends on:** `local-tv-backend-sonarr-adoption-zero-regression-plan.md`

## 1. Product decision

TV should feel native to CP, not like a second application and not like IPTV relabeled as local media. Library and Discover receive a clear `Movies | TV Shows` media switch. TV uses the same full-width information-card language as movies: poster, title, year range, genres, rating, language/quality where truthful, and direct actions. A TV card also shows status, season count, episode count, and local availability or progress where relevant.

Clicking the card opens a dedicated series page. The series page owns season selection, episode availability, progress, versions, and acquisition actions. The list card stays useful for scanning but does not try to become a miniature season browser.

The first implementation is desktop only, following the repository instruction. It does not redesign existing movie pages or mobile layouts.

## 2. Authorization boundary

Dante authorized this frontend plan document. It does not authorize JSX/CSS changes, builds, screenshots, runtime restarts, database changes, live data operations, or Git publication. Implementation begins only after explicit approval of the executive summary or this named plan.

## 3. Current UI facts and regression risk

Current source inspection shows:

- primary navigation is centered on Home, Library, Movie Lists, Maintenance, Discover, AI Control, IPTV, Downloads, Help, and related utilities;
- movie cards are implemented through movie-specific components including `UnifiedMovieCard`, `DiscoverMovieCard`, and `LibraryMovieCard`;
- Library and Discover are large page components with their own query, filter, selection, and loading behavior;
- Home Continue Watching currently assumes movies in its data and accessible labels;
- the app keeps workspace sections mounted to preserve page state;
- IPTV contains provider-local series presentation, but its data ownership is isolated from native CP media.

The main risk is forcing TV fields through movie-shaped components and API state. That would produce conditionals across cards, filters, playback, and curation while making movie regressions hard to detect. The frontend needs shared presentation primitives with separate movie and TV adapters.

## 4. Information architecture

### 4.1 Navigation

No new top-level `TV` navigation item is required for the first release. Use media switches inside:

- **Library:** `Movies | TV Shows`
- **Discover:** `Movies | TV Shows`

Home and Downloads show both media types through typed cards/rows. Movie Lists remains movie-only for the first release and should say so where ambiguity exists.

The selected media type is preserved independently per workspace section. Returning to Library should restore its media type, filters, scroll position, and selection state without changing Discover.

### 4.2 Routes

Recommended route ownership:

| Route | Purpose |
|---|---|
| Existing Library route | Hosts the media switch and preserves current movie state. |
| Existing Discover route | Hosts the media switch and preserves current movie state. |
| `/tv/series/:seriesId` | Dedicated local/discover series page. |
| `/tv/series/:seriesId/season/:seasonNumber` | Optional URL-addressable season state; can render through the same page owner. |
| Existing Downloads route | Adds typed TV acquisition labels and target links. |

URLs use canonical CP series IDs. Provider IDs remain metadata, not primary route identity.

## 5. TV card specification

### 5.1 Shared visual frame

TV cards should use the same proportions, border, spacing, typography, poster treatment, focus behavior, and density as the existing standard movie card shown by Dante. The shared shell may be extracted only after movie visual and interaction characterization tests exist.

The card contains:

1. poster;
2. title;
3. year range;
4. genre chips;
5. rating and vote count when available;
6. status;
7. season and episode counts;
8. context-specific availability/progress or acquisition action;
9. a visible navigation affordance that communicates opening the series page.

### 5.2 Year and status rules

Use these display rules:

| Canonical facts | Display |
|---|---|
| Start 2017, ended 2020 | `2017–2020` |
| Start 2018, continuing | `2018–Present` |
| Start and end 2020 | `2020` |
| Start known, current status unknown | `2018–` plus an explicit `Status unknown` label only where space allows |
| Dates unknown | Omit the range; do not invent one. |

Use `Present`, not `Still`. Status labels are normalized to plain user terms such as `Continuing`, `Ended`, `Limited Series`, or `Status Unknown`. Provider-specific raw status text stays out of the card.

### 5.3 Count rules

- `4 seasons · 38 episodes` for ordinary plural counts.
- `1 season · 8 episodes` with correct singular/plural grammar.
- Specials are excluded from the ordinary season count and shown separately when present, for example `4 seasons + specials · 40 episodes`.
- Discover shows canonical released counts and may separately label announced episodes.
- Library shows canonical total counts plus local availability, for example `31 of 38 available`.
- Counts come from the TV read model; the component never counts a partially loaded episode array.

### 5.4 Rating, quality, and language truthfulness

Provider rating and vote count may appear when available and must identify the provider in accessible text or tooltip.

Quality and language are file facts in Library, but a series can contain mixed files. Use:

- a single value only when all available playable episodes agree, such as `1080p`;
- `Mixed quality` or `Mixed languages` when values differ;
- `No local episodes` when none are available;
- no quality/language chip in Discover unless describing a specific release candidate.

Never project one episode's quality or language as the whole series value.

### 5.5 Context-specific card content

| Surface | Required extra content |
|---|---|
| Library | Local episode count, progress, Resume/Start action, and missing/cutoff indicator if monitoring is enabled. |
| Discover | Library ownership state plus Streaming, Add/Monitor, or View in Library actions. No fake local quality. |
| Home Continue Watching | Current episode code/title, time remaining or progress, and Resume. One card per series. |
| Search results | Match reason and local state; avoid duplicating Discover controls. |

Clicking the main card opens the dedicated series page. Inline buttons stop propagation and perform only their labeled action. The corner affordance must look like navigation, not the movie card's expand/collapse control if that control has different behavior.

## 6. Dedicated series page

### 6.1 Header

The header contains:

- backdrop and poster with stable fallback states;
- title and optional original title;
- year range and normalized status;
- genres, rating/votes, runtime range, network/provider where useful;
- overview;
- creators and top cast;
- season/episode totals and local availability;
- `Resume`, `Start`, or `Play next` based on derived episode state;
- monitor state and acquisition entry point when acquisition is enabled.

The primary action is computed by the backend read model so Home and the series page cannot disagree.

### 6.2 Season navigation

- Default to the season containing the resume/next episode; otherwise the first season with local availability; otherwise the newest released regular season.
- Show season 0 as `Specials`, never as an unlabeled number.
- The selector shows availability and progress, for example `Season 2 · 7/10 available · 4 watched`.
- Load one season's episode rows at a time and keep selection in the URL or page state.
- Changing season does not reset the whole series page or scroll unexpectedly.

### 6.3 Episode rows

Each row shows:

- episode code such as `S02E03`;
- title;
- air/release date and runtime when known;
- short overview, expandable if necessary;
- local availability;
- watched/resume progress;
- quality/language summary for the selected version;
- play/resume action;
- a versions/download action only when relevant.

Unaired episodes are clearly labeled and cannot be played. Missing released episodes can expose Search/Monitor actions when enabled. A provider metadata gap must not look like a missing local file.

### 6.4 Multiple versions

Multiple physical copies belong behind an episode-level versions action. The chooser displays measured resolution, codec, HDR, audio/language, runtime, file size, path label, and playback compatibility. The last successful selection may be remembered per episode, with an explicit automatic/default rule.

For a file bound to multiple episodes, each episode row links to the same file identity but keeps separate episode progress policy only if the player can map segments correctly. Until segment support is proven, playback should treat the shared file conservatively and explain the limitation.

### 6.5 Cast and people

Show series-level cast first and episode guest cast within episode details. A person action may open a unified read-only view assembled from movie and TV repositories using provider person identity. The frontend must not merge people by name.

### 6.6 Streaming button

The TV Streaming button remains a first-release feature and follows the established movie Streaming Link behavior.

- It uses the same global enabled state, configurable label, embedded modal/player owner, unreleased suppression, focus restoration, and error handling as movie cards.
- A separate TV URL template accepts the canonical TV TMDB ID, season number, and episode number. The movie URL template is not repurposed or broken.
- On a series card or series header, Streaming targets the episode selected by the backend primary-action model: resume the unfinished episode, otherwise the next released episode, otherwise the first released episode.
- On an episode row, Streaming targets that episode directly.
- If no released target exists or the TV template is incomplete, the button is hidden rather than opening a malformed URL.
- Opening a streaming link does not mark an episode watched. Progress changes only through an explicit supported player-progress contract.
- Streaming Link is not IPTV and does not read or write provider-local IPTV state.

## 7. Home and Continue Watching

Continue Watching becomes a typed media feed. For TV:

- show one card per series, representing the most relevant unfinished episode;
- display the episode code/title and episode progress;
- `Resume` means continue the unfinished episode;
- `Play next` means the prior episode is complete and a playable next episode exists;
- do not silently skip a missing next episode;
- completing an episode recalculates the series card without marking the entire series watched;
- movie cards retain their current behavior and wording.

The backend chooses the current TV item. The frontend does not infer it by sorting a partial episode list.

## 8. Library behavior

The TV Library switch owns independent:

- query and pagination;
- sort order;
- filters;
- selection state;
- scroll position;
- loading, empty, and error state.

Initial TV filters:

- genre;
- status;
- year range;
- rating;
- available/missing;
- watched/unwatched/in progress;
- monitored/unmonitored;
- quality and language based on local-file aggregates.

Initial sorts:

- title;
- first-air year;
- rating;
- recently added;
- recently aired;
- recently played;
- progress;
- missing episode count.

Bulk selection is deferred unless a concrete first-release action needs it. It must not reuse movie-list selection because Movie Lists remains movie-only.

## 9. Discover behavior

TV Discover mirrors the established movie discovery experience while using TV-specific metadata and actions:

- search and browse series, not individual episode results by default;
- show existing Library/monitor state;
- open the same dedicated series page with discovered metadata;
- allow Add/Monitor with an explicit default monitoring profile;
- keep release search separate from title discovery;
- preserve independent filters and state from Movie Discover.

Adding a series creates canonical metadata/monitoring intent only. It must not automatically search or download unless the approved action explicitly says so.

## 10. Downloads and decision explanations

Downloads rows need a typed target label:

- series, season, episode, multi-episode release, or pack;
- covered episode range;
- acquisition state and qBittorrent transfer state without conflating them;
- release title and quality claims;
- imported/failed/skipped file counts for packs;
- clear reason for rejection, retry, or manual review;
- link back to the series/season.

Search results and history consume the backend's stable decision codes and explanations. UI code must not reproduce size, quality, coverage, or upgrade rules.

## 11. Component ownership

Recommended structure, subject to Gate F0 source refresh:

| Component/owner | Responsibility |
|---|---|
| `MediaTypeSwitch` | Accessible Movies/TV selection with section-local persistence. |
| `MediaCardFrame` | Visual shell, poster, focus, layout, navigation affordance. No media rules. |
| `MovieCardAdapter` | Maps the existing movie view model to the shell without changing behavior. |
| `TvSeriesCard` | Maps the TV series-card read model and context-specific actions. |
| `TvSeriesPage` | Page orchestration and stable header/season state. |
| `TvSeasonSelector` | Season choices, counts, progress, keyboard behavior. |
| `TvEpisodeList` / `TvEpisodeRow` | Virtualized/paginated episode presentation and actions. |
| `EpisodeVersionDialog` | Multiple-copy selection using measured file facts. |
| `AcquisitionDecisionDetails` | Shared display of backend decision reasons for movies and TV. |
| existing Streaming Link owner plus TV adapter | Builds validated TV episode URLs and opens the existing embedded stream experience without duplicating configuration. |
| typed query stores/hooks | Separate movie and TV request/cache state; no mixed untyped arrays. |

Do not create a single component with dozens of `mediaType === 'tv'` branches. Share visual primitives and interaction utilities; keep domain formatting in adapters.

## 12. Accessibility and interaction contracts

- Media switch uses tabs or a radio-group pattern with correct keyboard behavior and accessible state.
- Cards are reachable once in the tab order; nested actions have distinct labels.
- Focus returns to the originating card after closing a dialog or returning from the series page where routing permits.
- Status, progress, rating, and availability are conveyed in text, not color alone.
- Poster and backdrop alt text avoids repeating visible titles unnecessarily.
- Loading skeletons preserve card geometry; errors expose Retry; empty states explain filters versus an empty library.
- Reduced-motion settings apply to transitions.
- All visible dates, counts, and singular/plural text are locale-safe even if the initial UI language remains English.

## 13. Desktop layout specification

Use the current standard movie-card row as the visual baseline. At the approved desktop viewport:

- poster remains the left anchor;
- title/year and metadata occupy the central content area;
- status/counts form one concise metadata line;
- rating remains visually stable near the bottom;
- primary/context action is reachable without opening the page;
- long titles and many genres truncate predictably without moving the rating/action outside the card;
- cards within a row have consistent height;
- skeleton, error, and empty states use the same grid/list width.

Responsive/mobile redesign is outside scope. Existing generic CSS must still avoid obvious breakage at current supported windows, but no new mobile composition or screenshots are required.

## 14. Frontend delivery gates

### F0 — Baseline and ownership refresh

- Record active source, served dist hashes, viewport, theme, and representative data.
- Capture screenshots and interaction traces for movie Library, Discover, Home, card actions, player, and Downloads.
- Characterize existing mounted-section state preservation.

**Exit:** Current movie visuals and interactions are reviewable.

### F1 — Typed view models and API adapters

- Define `MovieCardViewModel`, `TvSeriesCardViewModel`, series detail, season, episode, version, progress, and acquisition types.
- Add fixture-backed API adapters and error/loading contracts.
- Keep the TV capability flag off.
- Add typed streaming availability and episode target fields; do not construct episode choice from a partial frontend list.

**Exit:** No existing rendered DOM or bundle behavior changes.

### F2 — Extract the shared card frame

- Extract presentation from the authoritative movie card implementation.
- Keep the movie adapter's DOM, accessible names, events, and visual result equivalent.
- Remove obsolete duplicated shell code after parity is proven.

**Exit:** Movie component and screenshot regressions pass before any TV card is mounted.

### F3 — TV cards in isolated stories/fixtures

- Implement Library, Discover, Home, loading, empty, error, long-title, missing-art, mixed-quality, and continuing/ended states.
- Verify the exact year/count/status rules.

**Exit:** Desktop visual review accepts representative card states.

### F4 — Dedicated series page

- Implement header, season selector, episode rows, progress, versions, cast, and acquisition entry points against fixtures.
- Validate keyboard, focus, back navigation, and large-season performance.

**Exit:** Full synthetic series flow works without touching live data.

### F5 — Library and Discover integration

- Add section-local media switches and independent query state.
- Wire TV APIs behind the capability flag.
- Preserve Movie Lists and movie filters exactly.

**Exit:** Switching repeatedly cannot leak filters, selection, results, or scroll state between media types/pages.

### F6 — Home, player, and Downloads integration

- Add typed Continue Watching, episode playback handoff, progress refresh, and acquisition rows.
- Preserve movie accessible labels and completion behavior.
- Integrate the TV Streaming button through the existing movie Streaming Link owner and verify movie template compatibility.

**Exit:** Resume/start/complete/rewatch flows pass for movies and episodes.

### F7 — Production build and served-route verification

- Run focused tests, full frontend tests, build, and Playwright desktop E2E.
- Verify the running app serves the reviewed asset hashes.
- Inspect real rendered Library, Discover, series page, Home, player, and Downloads, including console/network errors.

**Exit:** Source, dist, served assets, API behavior, and visible result agree.

### F8 — Controlled enablement

- Enable TV for the approved pilot only after backend Gate T10.
- Record before/after screenshots and rollback bundle.

**Exit:** Dante accepts the desktop result before general enablement.

## 15. Regression coverage

| Contract | Required coverage |
|---|---|
| Movie cards | Visual snapshot, accessible names, click/keyboard, expansion/actions, rating/genres/year/quality, selection. |
| Library | Movie results, filters, sort, pagination, selection, scroll preservation, loading/error/empty states. |
| Discover | Movie search, filters, actions, card navigation, state preservation. |
| Home | Movie Continue Watching ordering, labels, resume and completion. |
| Player | Movie start/resume/complete/rewatch/close-resume and TV episode equivalents. |
| Streaming Link | Movie behavior unchanged; TV card/header/episode targets, template validation, unreleased hiding, focus return, and no implicit watched mutation. |
| TV cards | Ended/continuing/unknown dates, specials, mixed quality/language, local/no-local, missing art, long text. |
| Series page | Default season, season switch, missing/unaired/watched/in-progress, multiple versions, provider error. |
| Downloads | Movie rows unchanged; TV target range, partial pack, rejected/retry/manual-review explanations. |
| State isolation | Movie/TV and Library/Discover query, filters, cache, selection, scroll, and route history. |
| Accessibility | Keyboard traversal, focus restoration, dialog semantics, text alternatives, non-color status. |
| Performance | Bounded list requests, no per-card request waterfall, large season scrolling/render time. |
| Served output | Build passes, asset hashes match, desktop route visibly renders, no console/runtime failures. |

## 16. Stop conditions

Stop if:

- movie card structure, behavior, or visual output changes without an approved reason;
- a TV component calculates canonical counts, progress, quality policy, or acquisition decisions from partial data;
- Library and Discover share mutable movie/TV filter or result state;
- IPTV data becomes a native TV source of truth;
- cards imply an entire series has one quality/language when files are mixed;
- Home confuses Resume with Play next;
- completing one episode marks a season or series complete directly;
- a production screenshot is taken from a source dev server while CP serves a different dist bundle;
- keyboard/focus behavior regresses;
- the desktop page creates an unbounded episode payload or per-card request waterfall.

## 17. Definition of complete

The frontend is complete only when:

- Movies/TV switches exist in Library and Discover with isolated persistent state;
- TV cards match CP's standard information-card language and truthfully show year range, status, counts, rating, and availability/progress;
- the dedicated series page supports seasons, episodes, versions, cast, playback, progress, monitoring, and acquisition explanations;
- Home shows one correct Continue Watching item per active series and preserves movies;
- Downloads represents typed TV targets and partial pack outcomes;
- movie visual, interaction, and state baselines remain green;
- focused/full tests, build, served-asset verification, desktop Playwright, visible inspection, and console/network review pass;
- Dante accepts the pilot presentation.

## 18. Deferred frontend scope

- mobile/responsive redesign;
- TV entries in Movie Lists;
- calendar and notification pages;
- person-page redesign beyond a minimal unified read view;
- IPTV/native-TV merging;
- advanced bulk season operations;
- visual redesign of existing movie cards unrelated to the shared-shell extraction.
