# Movie awards icons, winning-film navigation, and annual refresh — Implementation Plan

**Status:** Approved for source implementation and isolated verification on 2026-10-02. Dante: “good lets hand over to a new task for implrmenatation”. Approval covers the six tasks, source/test/assets/docs, historical seed building and its external source acquisition, and isolated testing/compilation in OS-temp roots. Work directly in the existing Desktop checkout without delegation. Live data/config/seed/dist changes, app restarts, commits, pushes, tags, packaging and releases require separate authorization.

**Date:** 2026-10-02, Africa/Cairo.

**Execution checkpoint:** Source implementation and isolated verification are recorded in [the implementation report](../verification/movie-awards/implementation-report.md). Dante clarified that his selected placement area governs award sizing: shrink the award images to fit, rather than resizing actors' portraits or changing the credit grid. The previously proposed 52px reservation and fixed award measurements were implementation assumptions and are superseded by this explicit clarification. The selected-area correction is verified at all four desktop sizes, including unchanged portraits during late snapshot loading and unclipped two-digit counts. Oscar ceremonies 1–98 are reproducibly bundled; Golden Globe totals remain unpublished under the independent coverage gate (57/83 winner checks pass, 119 unresolved identity references, modern primary redistribution terms unverified). The latest full Python suite passes all 1,535 tests. No live deployment has occurred. Dante canceled the shutdown request; no shutdown is authorized after completion.

**Goal:** Show accurate Oscar and Golden Globe win counts on regular movie and movie-credit cards, open a person's winning films in Discover, and update complete ceremony results once each year.

**Architecture:** Add one awards subsystem with its own local SQLite store and verified historical seed. Read counts through one shared frontend snapshot; extend the existing card and Discover owners. Awards never become part of cached TMDb descriptions or IPTV/TV metadata.

**Tech stack:** Existing Python 3.12, Flask, SQLite, React 19, Vite 6, Python unittest, Node tests, and Playwright. Use Python's existing standard-library HTTP/CSV/JSON tools. No new runtime dependency is planned.

**Specification:** The agreed contracts below, Dante's five supplied screenshots, current root [AGENTS.md](../../AGENTS.md), and [the CP plan template](_template.md). No separate specification or implementation approval is implied.

**Execution:** After explicit implementation approval, use the executing-plans workflow in this checkout. Do not create another worktree, delegate without authorization, or commit automatically.

## Problem and decision

### What happens now

Regular movie cards and their actor/director cards have no awards count or winning-film action. Movie metadata is built from TMDb and owned-film canonical projections. IPTV has its own provider databases and enrichment settings; sharing card markup does not make those databases the same owner.

The important implementation traps are:

- `UnifiedMovieCard` and `PersonCreditCard` also serve excluded TV/IPTV or other search results. Adding awards based on an ID alone would leak movie behavior into those surfaces.
- The collapsed rating footer currently exists only when there is a rating. Award-winning films without a rating must still show awards.
- The current person action opens a filmography. It does not identify the films for which the person actually won an award.
- Expanded credits have a fixed 238px slot, ten person columns, and a separate related-film rail. A new row beneath names would change the agreed geometry; Dante instead marked the right-side positions.
- A source containing a ceremony year, nominations, or some winners is not proof that all results are ready. Recipient rows also do not equal distinct film wins.

### What Dante wants — recorded decisions

1. Oscars and Golden Globes; wins only, no nominations.
2. Movie cards show the film's wins across all film categories, including film-associated historical special awards.
3. An actor card shows that person's career wins in leading/supporting **film acting**. A director card shows career **Best Director** wins. The same person's totals are different for the two card roles.
4. One film/category/ceremony win counts once even if several people received it. For example, the approved film interpretation gives *Gladiator* two Golden Globe wins: picture and score. Two score recipients do not turn that into three film wins.
5. IPTV and TV are excluded, including their person cards. No connection to their databases is introduced.
6. Use the supplied gold award artwork, with the number on its **left**. No badge, pill, surrounding circle, border, or filled background. Hide each zero pair; hide the entire awards group when neither pair is available.
7. Standard movie card: awards at the bottom right of the information area, opposite the rating. Expanded movie card: awards in the upper-right header, immediately left of the rating.
8. Person card: Oscar above Golden Globe, at the two white-dot positions on the right, below biography and filmography. This supersedes the earlier suggested row below the character/director label.
9. Hover text is exactly **`Oscars`** and **`Golden Globe`**. No counts, explanations, or click instructions in these tooltips.
10. Each person award icon opens Discover movie cards for the films that earned **that person** the chosen award in the card's role. Dante confirmed the interpretation and the corresponding Golden Globe action with “yes correct.”
11. Keep a local historical snapshot. Check weekly during the relevant ceremony month, continue weekly if results remain incomplete, import complete results once, then stop until the following year. Golden Globes use January and Oscars March under the agreed month-based approach.
12. Movie-level storage needs aggregate counts, not a saved movie/category breakdown. Person win records retain the award/category/film association required for correct role totals and navigation.

### Confirmed, suspected, and unknown

**Confirmed by current code/read-only investigation:** shared owners and callers below; separate provider-local IPTV storage; current source and runtime baseline; current source formats and sampled count distinctions; no existing awards implementation.

**Confirmed by Dante:** the twelve decisions above. This is product agreement, not authorization to implement.

**Not established:** complete historical identity coverage, accuracy of every historical source row, future source update timing, future ceremony page formats/category changes, final cleaned artwork, and passing test/build/live results. Spot checks do not establish these facts.

**Open product decisions:** none identified after the latest confirmation. Technical choices below are proposals for plan approval. If a source limitation would require partial career totals, a new category scope, different placement, or different click behavior, stop the affected work and obtain Dante's decision; do not invent a replacement rule.

### Scope and global constraints

- Regular movie cards: Library, Discover Explore/results and Pick My Movie, movie Lists, AI Control results, and Home `SmartMovieCard`.
- Regular expanded movie credits: every actor/director `PersonCreditCard` rendered by `MovieExpandedDetails`, including owned and unowned films and Discover cards reached through related-film navigation.
- The winning-film results use existing Discover cards, expansion, ownership handling, playback/stream/acquisition controls, and history.
- Exclude TV, all IPTV views/enrichment, people/keyword search cards, compact related tiles, Continue/Upcoming poster-only tiles, Home's separate inspector cast chips, and style-lab fixtures. Opening a full regular movie card from an excluded compact tile may show awards there.
- Desktop only. Keep existing mobile code and breakpoints; no mobile design or testing work.
- No new general award filter, curated list, manual refresh button, notification UI, biography redesign, Rotten Tomatoes work, or catalog migration.
- Preserve dirty work, canonical ownership, language behavior, movie identity decisions, playback, lists, acquisition, transfer, and existing search contracts.
- “Zero regression” means the explicit preservation checks and release gates below. It is not a promise that finite tests can prove absence of every possible defect.

### Review focus

| Easily missed condition | Required outcome | Owning task/check |
| --- | --- | --- |
| Two people receive one film award; one early acting award references several films | Film count and person count use different distinct keys; navigation deduplicates films | Task 1; A03–A05 |
| Stale/partial winners and a new or removed category | Keep the last complete generation; never mark the ceremony complete on file existence/count alone | Tasks 1–3; A12–A16 |
| Movie/TV/person IDs collide or accepted movie identity changes | Only explicit movie callers receive awards; conflicting identities do not fall back to a guessed match | Tasks 2/4; A07–A09 |
| Award click bubbles, old filmography request returns late, or unrelated Discover filters remain active | One winning-film navigation; stale response discarded; full matching set reachable; Back restores prior state | Tasks 5/6; A21–A25 |
| No rating, long names, two-digit counts, or narrow desktop columns | Correct counts remain legible without clipping controls, changing the fixed credits slot, or losing rating behavior | Tasks 4/6; A17–A20 |

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| Movie/TV/IPTV separation; AGENTS.md and discussion | Separate ownership and identity namespaces | Shared movie/person renderer; provider stores | Awards opt-in only from regular movie callers | No | Preserve; IPTV explicitly excluded |
| Film count; discussion | Distinct film/category/ceremony wins, all film categories | Standard/expanded regular cards | Same definition in one backend aggregator | New feature, agreed | Film frame confirmed |
| Person count; discussion | Film acting on actor cards; Best Director on director cards | Movie expanded credits | Role-specific career totals | New feature, agreed | Cast/director frame confirmed |
| Award appearance; screenshots and refinements | Number left of supplied icon; no badges; zero hidden | Regular cards and credits | Placement and metrics below | New feature, agreed | Movie positions confirmed; person white-dot positions confirmed |
| Tooltips; latest correction | Exactly “Oscars” / “Golden Globe” | All award icons | Exact strings below | Earlier explanatory proposal superseded | Explicit correction recorded |
| Person award click; latest confirmation | Show films earning that person's selected role award | Expanded credits → Discover | New award relationship context | Earlier informational person proposal superseded | Explicit request and “yes correct” |
| Existing biography/filmography/person body actions; current intended CP behavior | Biography stays biography; filmography stays full filmography; body action stays its existing filter/browse action | Shared person cards | Separate callback for award buttons | No | Preserve |
| Discover navigation, owned identity, and relationship limits; current CP owners/plans | Preserve existing cards/history and existing related/collection/person result rules | Discover, Lists, Library, AI Control | Add a distinct award relationship without modifying their other kinds | No | Preserve |
| Refresh; discussion | Weekly in award month until complete; done until next year | New local awards subsystem | Persistent per-organization/per-ceremony state | New feature, agreed | Weekly approach accepted |
| Movie metadata/canonical and catalog generation; AGENTS.md | One canonical movie identity; language descriptions and catalog generation retain their meaning | Existing caches, repository, SSE | Awards generation is separate, counts never written into TMDb payloads | No | Preserve |

No unapproved weakening of an existing contract is proposed. If a conflict emerges, use the separate **`## ⚠️ CONTRACT CHANGE — DANTE'S DECISION REQUIRED`** notice required by AGENTS.md, with CURRENT RULE, PROPOSED RULE, WHAT DANTE WILL SEE, AFFECTED AREAS, REASON, COST OR RISK, ALTERNATIVE, and RECOMMENDATION. A note in this file does not replace that notice or Dante's decision.

**Existing test conflict to handle explicitly:** `tests/test_unified_movie_card_ui.py` asserts the literal source condition `{rating && !expanded ? (`. That condition would suppress awards when a film has no rating. Replace this implementation-text expectation with assertions preserving existing rating visibility and proving award-only footer behavior. Do not drop rating/vote checks. `tests/test_startup_background.py` checks three existing worker launches; keep those assertions and mock/test the separately owned awards start/stop, rather than weakening the test to accept arbitrary worker counts.

## Current design and ownership

### Baseline recorded during this planning investigation

| Fact | Observed value | Limit of the evidence |
| --- | --- | --- |
| Checkout | `C:\Users\dante\Desktop\cinema paradiso` | Active checkout; no new worktree |
| Branch / commit | `master` / `c62b3f3` | Current source contains uncommitted changes |
| Dirty scope before saving this plan | 98 entries: 74 tracked changes and 24 untracked entries | Includes existing plans, TV work, app/card owners, tests; preserve all |
| Package version | `3.0.0-beta.1` | Not proof of exact source loaded by the running Python process |
| Runtime | `127.0.0.1:5000`, PID 22228; `C:\Program Files\Python312\python.exe app.py` | Process created 2026-10-02 02:16:05 Africa/Cairo; loaded commit cannot be established from this alone |
| Active user-data / TMDb cache | `...\cinema paradiso\data` / `...\cinema paradiso\cache` | Read from `/api/app-data/config`; credentials not printed |
| Regular catalog | `C:\Users\dante\AppData\Local\Cinema Paradiso\Catalog\catalog-read-cb30c1d963c88463.sqlite` | Read-only SQLite: schema 11, canonical contract 4, 5,152 TMDb films |
| Served frontend | `/` byte-identical to checkout `dist/index.html`; linked assets also byte-identical | Dist may predate current dirty source; no claim that current source was compiled |
| HTML SHA-256 | `f6db43f83bc0875a98a70e5ad88bd48a007cdf56bb904d22eb5940e640a8d860` | Planning snapshot only |
| Main JS / CSS | `index-C4ryBrE8.js` / `index-Cg9hZsbq.css` | Recheck served names/hashes at approved deployment |
| Test/build baseline | Not executed during this planning task | No passing-suite claim; record failures/skips before implementation |
| Calendar support | Both system and project-venv `ZoneInfo('Africa/Cairo')` raise `ZoneInfoNotFoundError`; Windows has `Egypt Standard Time` | Do not assume that Python's IANA timezone database is installed |

Before implementation, capture fresh Git status and hashes of pre-existing dirty files; rerun relevant baseline suites in OS-temp isolation. Do not reset, stash, clean, replace, or commit unrelated work. A changing runtime/bundle baseline must be recorded, not silently reused.

### Existing owners and callers

| Responsibility | Authoritative owner | Entry point/callers and behavior to preserve | Competing paths to account for |
| --- | --- | --- | --- |
| Standard/expanded movie geometry and rating | `src/components/movie-card/MovieCard.jsx`, `movieCard.css` | `UnifiedMovieCard`; footer, header, selection/expand/play | Shared TV/IPTV, person/keyword search, indexer wrappers, Home direct caller |
| Canonical regular card identity/details/credits | `src/components/SharedMovieCards.jsx` | `DiscoverMovieCard`, `LibraryMovieCard`, `MovieExpandedDetails`; owned canonical merge, Arabic view, ten-credit allocation | Never resolve awards from a raw candidate that disagrees with the accepted owned identity |
| Person portrait and existing actions | `src/components/PersonCreditCard.jsx` | Shared `PersonCreditCard`, biography modal; actor/director display | `creator` is treated as director for existing appearance, but is not eligible for movie awards |
| Expanded credits/related geometry | `src/styles/movieRelationships.css`; person action positioning in `src/styles.css` | 238px credits slot, ten columns, avatars max 106×132, 236px related rail at normal height | Preserve compact-height rules and existing mobile rules; no new page overrides |
| Home direct movie card | `src/features/home/HomeWorkspace.jsx` | `SmartMovieCard` | Inspector/plain cast chips have different semantics and stay outside this amendment |
| Cross-workspace Discover requests | `src/App.jsx` | `openPersonInDiscover`, `discoverRelationshipRequest`; active tab/section | Existing request types and source/origin/history must remain correct |
| Discover relationships/results/history | `src/features/discover/DiscoverWorkspace.jsx` | `buildPersonMoviesContext`, `browsePerson`, `loadContextPage`, request abort/sequence guards, snapshot/history restoration | Explore, Pick My Movie, indexer-enriched and owned result branches; filters must not accidentally exclude award films |
| Library/Lists/AI callback forwarding | `src/features/library/LibraryWorkspace.jsx`, `src/features/movie-lists/MovieListsWorkspace.jsx`, `src/features/ai-control/AIControlWorkspace.jsx` | Existing `onOpenDiscoverPerson`/person callbacks | Library wrapper changes callback signature; owned Lists branch lacks the same explicit filmography forwarding as the unowned branch; wire both |
| Regular identity/canonical persistence | `services/catalog_repository.py`, `services/catalog_store.py`, `services/canonical_catalog.py`, app metadata store in `app.py` | Accepted movie IDs and cached card projections | No awards columns/migrations or raw-JSON annotations here |
| Metadata caches/local projections | `src/api/movieDetails.js`; `_movie_card_projection`, `_tmdb_card_projection_by_id`, `_normalize_tmdb_movie_summary` in `app.py` | Existing cache/owned/language/detail behavior | Detail early returns, Arabic transient replacements, stale detail caches must not own awards |
| Catalog events | `services/catalog_events.py`, `src/api/catalogEvents.js` | Existing catalog/media generation | Do not put awards revisions in catalog generation/SSE |
| Normal runtime start/stop | `_start_background_services`, `_shutdown_library_background_services`, atexit registration in `app.py` | Library observer/catchup, qBittorrent import, conditional TV monitoring | New worker has its own stop event and test-mode guard; no timer-based duplicate startups |
| IPTV metadata/database | `services/iptv_provider_manager.py`, `iptv_movie_store.py`, `iptv_movie_service.py`, `iptv_metadata_settings.py` | Provider `iptv.sqlite` / `movies.sqlite`, provider settings, direct TMDb enrichment | No regular-catalog bridge, award columns, migrations, provider settings changes, or backfills |
| TV | `src/features/tv/TVWorkspace.jsx`, TV service/catalog owners | Existing shared card/person appearance and interactions | Explicitly absent awards even when numeric IDs match a movie/person |

### New files: one owner per new responsibility

| File | Responsibility |
| --- | --- |
| `services/movie_awards_sources.py` | Source adapters, exact category taxonomy, completeness validation, distinct-win aggregation; no DB/UI/network policy |
| `services/movie_awards_identity.py` | Verified IMDb ↔ TMDb mapping, source alias evidence and identity-conflict checks; no catalog identity writes |
| `services/movie_awards_store.py` | Awards SQLite schema, transactions, ceremony contributions, person win links, refresh state, read projections |
| `services/movie_awards_refresh.py` | Bounded source transport and one persistent weekly refresh owner; bootstrap installation and lifecycle |
| `services/movie_awards_routes.py` | Local read-only snapshot/status/person-winning-films endpoints using injected store and existing projection callbacks |
| `tools/build_movie_awards_snapshot.py` | Reproducible offline-seed build/coverage audit against pinned source revisions; explicit output root |
| `static/movie-awards/seed.json`, `manifest.json`, `category-taxonomy.json`, `identity-overrides.json` | Historical aggregates, provenance/coverage, explicit category classifications and evidence-backed missing-ID resolutions |
| `src/api/movieAwards.js` | One deduplicated local snapshot cache/revalidation owner and identity lookup; no external award requests |
| `src/components/MovieAwardsProvider.jsx` | React subscription/context over that cache; disabled consumers remain inert |
| `src/components/AwardIcons.jsx`, `src/components/awardIcons.css` | One icon/count renderer; optional action on person variants only |
| `src/assets/awards/oscar.png`, `golden-globe.png` | Clean transparent versions of the supplied artwork; preserve silhouette/aspect ratio |

`static` is already included by `tools/build_portable_release.py`; verify seed inclusion with `tests/test_release_packaging.py`. Do not introduce an unshipped `resources` directory or change release behavior just for the seed. Add source notices to the existing `THIRD-PARTY-NOTICES.md` after confirming redistribution terms.

## Exact behavior contract

### Frontend

#### Shared renderer and desktop placement

`AwardIcons({ counts, variant, onAwardClick })` accepts `counts: { oscar: number|null, golden_globe: number|null }`, `variant: 'movie'|'person'`, and optional `onAwardClick(award)`. `null` means unknown/unavailable, not zero. Only positive finite integer counts render. Backend invalidity is reported in diagnostics and never converted to a plausible count. Do not round/truncate malformed values.

| Element | Exact layout/interaction |
| --- | --- |
| Movie pairs | Oscar then Golden Globe horizontally; icon height 24px, width auto; number 16px, weight 900, existing CP rating/text-soft color; 6px number/icon gap; 12px pair gap |
| Standard movie | Existing body footer becomes present when collapsed and either rating or positive awards exist. Rating stays left; awards align right and vertically centre against the rating. No dummy rating or votes |
| Expanded movie | Insert awards before `ExpandedRating` in existing header metadata; at least 16px separation from rating. Centre against the star/score line, not the combined score/vote block. Preserve IMDb and collapse controls |
| Desktop collision | At insufficient available footer/header width, move the awards group to a right-aligned line immediately above the rating/control row. No overlap, shrink-to-unreadability, or global card/grid widening |
| Person pairs | Oscar first, Golden Globe second vertically, within the selected right-side area beneath the existing biography/filmography controls. Size award artwork and counts to fit that area; two-digit numbers remain on the left. At shorter portrait heights, compact the award rows to stay clear of the person's name and role. Measurements are implementation choices, not additional fixed product requirements |
| Person portrait protection | Preserve existing portrait sizing and uniform widths, including 106×132 at 1920×1080 and the existing proportional fit at narrower desktop widths. Do not reserve extra space only on award-bearing cards, resize portraits to accommodate awards, or change the 238px credits slot, ten columns, text order, or related rail. Like the existing right-side controls, awards occupy the selected control area; there is no separate mandatory 52px strip |
| Single person award | Keep the award in its designated position; do not move Golden Globe into the Oscar position when Oscar is zero |
| Appearance | Transparent icons; no checkerboard/black rectangle, circle, pill, border, filled background, or stretched artwork. Person pairs are buttons styled without button chrome; visible keyboard focus is retained |
| Hover | Native/shared hover title exactly `Oscars` or `Golden Globe`. Accessible names may include the visible count and action for screen readers, but do not add that text to the tooltip |
| Movie action | Informational only; no separate award-list click on a movie card. Preserve its existing body expand/select action |
| Person action | Click or keyboard activation opens that person's selected winning-film context. Stop propagation so neither person body action nor movie expansion/selection also runs |

**Dante's explicit clarification (2026-10-02):** “i selected an area for implementations , the sizes of the award photos should shrink to fit the place”. Preserve the selected placement and existing credit cards; fit the awards to them. This supersedes the earlier assumed fixed award sizes and 52px rail. No portrait shrinkage or horizontally scrolling replacement is approved or needed.

#### Award data and states

- `MovieAwardsProvider` wraps the existing application tree. It does not fetch merely because TV/IPTV is mounted. The first enabled regular movie consumer starts one shared local snapshot request. Excluded callers never opt in.
- Export `useMovieAwards(movie, { enabled })` and `usePersonAwards(person, role, { enabled })`. Accepted canonical IDs from `canonicalOwnedMovie`/Library identity are used, not title matching or tentative metadata IDs.
- `UnifiedMovieCard` gains an explicit `awardCounts = null` prop; it does not derive domain/identity or contact any source. `PersonCreditCard` gains `awardCounts = null` and `onAwardDiscover = undefined`. Its `creator` appearance shortcut does not enable awards.
- `DiscoverMovieCard`, `LibraryMovieCard`, and Home `SmartMovieCard` opt in. `MovieExpandedDetails` supplies actor/director counts and forwards a distinct `onPersonAwardDiscover(role, person, award)` callback. Do not use the old `onPersonDiscover || onPersonBrowse` fallback for this action.
- No per-card network calls for award counts, no calls to award sources during rendering, and no identity resolution in the browser. Movie/person namespaces stay explicit in the snapshot.
- Snapshot GET on first regular consumer; deduplicate concurrent requests. Revalidate on visible-window focus after at least 60 seconds and every five minutes while a regular-movie consumer is visible. Stop the interval when none is visible; use ETag/304. These are **local** reads, never ceremony-source checks.
- Initial loading/unavailable snapshot: show no pairs and no false zeros, loader, error chip, or rating substitution. A failed refresh retains the last valid snapshot. Record error/status in the local status endpoint, without exposing credentials or adding a notification UI.
- Reject a late snapshot response older than the active `awards_generation`. Same generation/304 retains object identity. A valid new generation updates counts without replacing film descriptions or resetting expanded state/scroll.
- English/Arabic metadata changes do not change counts. Every pair preserves left-to-right number-then-icon order with an explicit direction independent of plot language.

#### Winning films in Discover

- Extend root `openPersonInDiscover(movie, role, person, options)` with optional `award: 'oscar'|'golden_globe'`. Existing callers with `fullFilmography` retain their behavior. Award requests have `type: 'person-awards'`, person ID/name, explicit actor/director role, award, origin section, and source movie label; they do not impersonate a general filmography request.
- Discover's existing relationship dispatch handles this type before the generic person branch. Add `buildPersonAwardMoviesContext(movie, role, person, award, origin)` and `browsePersonAwards(...)` beside the existing person helpers. Reuse `loadContextPage`, movie result rendering, abort/sequence guards, pagination, history snapshots, and browser-history machinery.
- Base URL: `/api/movie-awards/person-films?person_id=<TMDb ID>&role=<actor|director>&award=<oscar|golden_globe>`. Context owner/type is `person-awards`, never `advanced`/`person-credits`.
- Open Discover **Explore**, movie results. Set availability to all and start page 1. Current text/genre/person/year/owned filters do not silently trim the initial award set. Store those criteria in the prior snapshot and restore them on Back. No new global awards search filter is introduced.
- Label: `<Person name> — Oscar-winning films (Acting)` / `… (Directing)`, or `Golden Globe-winning films`. Visible summary uses returned film count; it does not assume that the number of unique films equals the number of wins.
- A person with two relevant awards for one film still has two wins and one film card. One historical acting award associated with several films counts as one person win and can open several film cards.
- Sort deterministically by latest associated ceremony year descending, then title ascending, then TMDb ID. Return each winning film once across all relevant years/categories. No arbitrary related-film limit of 100 applies to a career winning-film set.
- Clicking a person's Oscar must not include a film merely because the **film** won an Oscar for someone else, or because the person was nominated, produced it, wrote it, or won a TV award.
- Library/Lists/AI Control call the root owner; Discover calls the same local context builder. Pick My Movie award buttons explicitly switch to Explore. Wire owned and unowned Lists/Discover branches and any wrapper that otherwise drops extra arguments.
- Back from an internal Discover action restores results, query/filter state, page, expansion, selection, and scroll using current snapshots. From Library/Lists/AI Control, return to that recorded origin without losing its expanded card. Browser Back/Forward must agree with the existing relationship-history contract.
- Loading, empty, retry, and error UI reuse existing Discover states. A projection error does not display unrelated films or misreport a partial page as the complete set. Existing full-filmography and biography buttons remain separately usable.

### Backend

#### Sources and verified limitations

| Input | Proposed use and adapter contract | Evidence / limitation |
| --- | --- | --- |
| [DLu Oscar dataset](https://github.com/DLu/oscar_data) | Oscar historical primary; pinned `oscars.csv`; tab-delimited `csv.DictReader`; capitalized fields; `Winner=True`; pipe-separated IMDb film/person IDs | `Year` is eligibility year, not ceremony year. `Category` distinguishes historical special-award subtypes; do not deduplicate only by `CanonicalCategory`. Unknown IDs may be `?`. BSD-2-Clause |
| [Golden Globe historical dataset](https://www.kaggle.com/datasets/unanimad/golden-globe-awards), [inspected CSV mirror](https://raw.githubusercontent.com/prasertcbs/basic-dataset/master/golden_globe_awards.csv) | Historical 1944–2020 primary; parse `year_film,year_award,ceremony,category,nominee,film,win`; explicit field rules by category | 7,991 inspected records, no IMDb/TMDb IDs. Some film awards put the title in `nominee` with empty `film`. Dataset attribution/licensing and mirror provenance must be captured before bundling |
| [MengtingWan dataset](https://github.com/MengtingWan/oscar) | Golden Globe supplement for 2021–2026; `eventId=ev0000292`, `awardName=Golden Globe`, `isWinner=True`; primary/secondary `tt`/`nm` IDs | Overlap 1990–2020 is identity/cross-check evidence only, never an additive second primary. Array cells use bounded `ast.literal_eval`, never `eval`. Check data-specific redistribution terms as well as repository license |
| Annual Wikipedia ceremony pages through [MediaWiki parse API](https://www.mediawiki.org/wiki/API:Parsing_wikitext) | Completeness cross-check and a whole-ceremony replacement source when the primary feed lacks complete results; fetch wikitext + revision, then pin revision for all companion reads | 83rd Golden Globes revision `1373661746` and 98th Oscars revision `1375628081` inspected. Parse category winner blocks, not photo captions, prose, nominees, or “multiple wins” summaries. Page existence is insufficient. Preserve source attribution |
| [TMDb find-by-ID](https://developer.themoviedb.org/reference/find-by-id) | Bootstrap/refresh-time identity bridge; `external_source=imdb_id`; explicit movie/person result collections | Only accept exactly one correct-domain match. No TV fallback or per-card lookups. Missing credentials keep unresolved work pending |

Source snapshots inspected in memory on 2026-10-02:

- Oscar raw SHA-256: `3b1d39eedad7303468b83323f51bd1069289a2710ff9873efc4b4298ae1bba78`; 12,137 CSV records, 3,515 winning rows; ceremonies 1–98. Winner-row count is **not** a film-win count.
- Historical Globe raw SHA-256: `ae99a5029bdfb8089fccd6da65177d2eae2757b947f850c045b357db8679bfee`; years 1944–2020.
- Modern mixed-event raw SHA-256: `00ede56bd799b3f86b6c84eea12eb76b0dc82d35467a0da145955eee189914fd`; 131,070 mixed-event records. Filter event/award/category before using any row.

Pin repository commits/revisions and verify these hashes during the seed build; moving branch URLs are discovery endpoints, not reproducibility guarantees. Do not redistribute the entire mixed-event dataset or scrape the Golden Globes' official database automatically. Official ceremony/film pages can support manual audit, but recipient-oriented official totals must not override Dante's film-category definition.

#### Normalized records, classification, and complete-result proof

Pure adapter interface in `movie_awards_sources.py`:

```text
parse_source(source_id: str, payload: bytes, manifest: dict) -> list[NormalizedWin]
validate_ceremony(wins: list[NormalizedWin], program: CeremonyProgram,
                  evidence: dict) -> ValidationReport
aggregate_ceremony(wins: list[NormalizedWin]) -> CeremonyContribution
```

`NormalizedWin`: organization, ceremony ordinal, ceremony year, exact award-instance key, normalized category, category scope (`film`, `tv`, `career`, `other`), person role (`actor`, `director`, or none), film references, person references, and source evidence. These are transient import records, not a saved film-category ledger.

- Use an explicit category alias taxonomy by source/year, including historical leading/supporting men/women categories, drama/comedy variations, renamed categories, film-associated special awards, and retired film categories.
- Film scope includes all film awards. Actor scope includes only leading/supporting film acting; director scope includes only Best Director. New Star, Juvenile, honorary/lifetime, writing, score, production, and TV categories do not become actor/director career wins.
- Never classify with a substring such as “Motion Picture”: TV movie categories contain that phrase, while Cinematic and Box Office Achievement does not. Unknown categories block that candidate ceremony rather than disappearing from totals.
- Film distinct key: `(organization, ceremony, award_instance, verified_film_identity)`. Most award instances are categories; distinct named historical special-award subtypes remain separate. Two tied winning films each count once.
- Person distinct key: `(organization, ceremony, award_instance, verified_person_identity, eligible_role)`. Shared recipients each receive their own personal win. A single person's award linked to multiple films still counts once.
- `CeremonyProgram` contains expected categories/award instances and film-associated special-award coverage for that ceremony, based on nomination/program evidence and the explicit taxonomy. Do not hardcode “24 Oscar / 15 Globe” for every future year; those are current 2026 competitive coverage checks only.
- A complete candidate requires correct organization/ceremony/year; a past ceremony date; every expected eligible award instance represented by positive, explicit winner evidence; supported tie markers; no unknown included category; and agreement with the independent ceremony/program cross-check. No rows with ambiguous winner markers are accepted.
- Annual wikitext adapter uses supported category-block headers and explicit bold winner list entries inside the relevant award tables/film sections; ignore nominees and decorative winner photographs. Test actual pinned 2025/2026 layouts for both organizations. An unsupported template/layout fails validation and retains the previous published generation.
- Fetch annual page/program revisions consistently; redirect resolution and revision IDs are recorded. Prefer a complete primary dataset ceremony; otherwise accept a complete annual-page ceremony as a **replacement**, not as rows added to the primary. Conflicting complete sources block publication and produce a diagnostic for review.
- Film/person identities required for the candidate contribution must be resolved before annual publication. Missing category/identity evidence is `pending`, not `complete`. Never label a partial career count complete.
- Historical bootstrap must produce a per-ceremony coverage audit, including excluded categories with reasons and unresolved identities. Resolve included winner identities through the evidence process below before marking that organization's historical seed ready. If full coverage cannot be established, report the concrete gap to Dante rather than shipping silently partial totals.

#### Identity authority

`resolve_identities(wins, *, existing_mappings, find_by_imdb, search_candidates, overrides) -> IdentityResolution` in `movie_awards_identity.py` returns verified references plus unresolved/conflicting evidence. It does not change catalog identities.

- Prefer source `tt`/`nm` IDs and existing verified mappings. Accept TMDb `/find` only in `movie_results`/`person_results`, respectively; zero/multiple results stay unresolved. Reject one-to-many mapping conflicts.
- Historical Globe identity without IDs: use modern-overlap evidence where ceremony/category/title/person agree; otherwise generate candidates using title + eligibility/release context and source aliases, then verify external IDs and winning-film credits/role. A matching normalized name/title alone is insufficient.
- Evidence-backed overrides live in the seed input file with source URL/revision, reason, IMDb/TMDb IDs, and role where relevant. They resolve missing identifiers; they are not rules that special-case a production title's count.
- Awards movie identity is independent from file matching. Frontend lookup uses the movie's currently accepted canonical TMDb/IMDb IDs. If both supplied IDs map to different award entities, suppress that lookup and report the conflict; do not borrow a candidate's count.
- Save minimal verified movie card facts from identity resolution (title, release date/year, poster path, language, genre IDs, TMDb rating/votes when available). These serve winning-film navigation offline. They do not overwrite canonical movie metadata.

#### Store and interfaces

Database path: `Path(active_user_data_dir) / 'awards' / 'awards.sqlite'`. Test path is always under `CP_TEST_ROOT`. This is the authoritative awards store; the bundled seed is an installation input, not a second writable truth.

Schema version 1:

| Table | Key/content and invariant |
| --- | --- |
| `awards_meta` | Schema/seed revision, global `awards_generation`, per-organization historical coverage; monotonic generation |
| `ceremony_imports` | Unique `(organization, ceremony)`; ceremony year, primary source/revision/hash, validation/program evidence, committed time. Only successfully committed complete ceremonies appear |
| `film_contributions` | Unique `(organization, ceremony, film_identity)` with positive aggregate `wins`; no saved per-film categories/nominations |
| `person_wins` | Unique person/role/ceremony/award-instance key, category and source evidence; one row per actual personal win |
| `person_win_films` | Links a person win to one or more verified film identities; navigation deduplicates these links |
| `identity_mappings` | Explicit movie/person namespace, IMDb/TMDb IDs, verification evidence, minimal movie facts; uniqueness/conflict constraints |
| `refresh_state` | Organization/ceremony, status, last attempt, next due, failure reason, bounded lease owner/expiry; separate from published import rows |

Derived totals are SQL sums/counts from committed contributions/person wins. Do not maintain another incremented lifetime counter that can disagree after retries or corrections.

Store API:

```text
MovieAwardsStore(path: Path)
read_snapshot() -> Snapshot
person_films(person_id: int, role: str, award: str, page: int,
             page_size: int, generation: int|None) -> PersonFilmPage
publish_ceremony(contribution: CeremonyContribution,
                 evidence: ValidationReport, lease_token: str) -> int
install_seed(seed: dict, manifest: dict) -> int
claim_due(organization: str, ceremony: int, now_utc: datetime) -> Lease|None
record_pending(lease_token: str, reason: str, next_due_utc: datetime) -> None
```

- Validate the full candidate in memory before a transaction. Use a SQLite transaction to replace that ceremony's contributions/links, insert its import record, update generation, and mark refresh complete together. A crash or exception rolls all of this back.
- Same source/content/program hash for an already committed ceremony is a no-op. Different validated content replaces its contribution rather than adding it again. No routine polling of completed years; a historical correction is a separately authorized import.
- SQLite busy timeout 5 seconds; one process worker and persistent transactional lease protect against duplicate processes. Lease expiry 15 minutes; bounded job duration 10 minutes. Another owner skips a claimed job. Expired crash lease becomes eligible again without exposing partial totals.
- Seed installation is transactional/idempotent, in the background startup owner, and never downgrades or deletes newer complete ceremony data. Invalid or missing seed leaves awards unavailable and records the precise diagnostic; app startup/search remains usable.
- Schema migration applies only to this new store. Unsupported future schema fails closed for awards, with no overwrite or catalog/TV/IPTV repair attempt.

#### Local endpoints

`register_movie_awards_routes(app, get_store, project_movie)` in `movie_awards_routes.py` registers:

Dependency contracts: `get_store(*, create: bool = False) -> MovieAwardsStore|None`; all three GET handlers use `create=False`. Only the startup/bootstrap/import owner may request creation. `project_movie(verified_movie_facts: dict) -> dict` reads existing cached projections and normalizes minimal facts without provider or catalog-write calls.

Snapshot shape (illustrative IDs/counts, not seed data):

```json
{
  "schema_version": 1,
  "ready": true,
  "awards_generation": 1,
  "coverage": {"oscar": "complete", "golden_globe": "complete"},
  "movies": {
    "tmdb:123": {"entity_id": "movie:imdb:tt1234567", "oscar": 2, "golden_globe": 1},
    "imdb:tt1234567": {"entity_id": "movie:imdb:tt1234567", "oscar": 2, "golden_globe": 1}
  },
  "people": {
    "tmdb:456": {"actor": {"oscar": 1, "golden_globe": 2}, "director": {"oscar": 0, "golden_globe": 0}}
  }
}
```

The movie `entity_id` is required to detect conflicting aliases even when the two entities happen to have equal counts. Hooks return only the selected count pair to the renderer. An unavailable organization's values are `null`; its status is not disguised as a zero. Complete zero entities may be omitted from compact maps, with the coverage/mapping owner distinguishing a verified zero from an unresolved ID.

`ready` is true when at least one organization's verified historical seed is installed. Coverage reports that historical readiness and the latest committed ceremony/year per organization. A pending future annual ceremony does not invalidate its previous complete totals: return the last committed counts with that latest-committed year, and expose the pending refresh separately in status. An organization with no verified historical seed returns `null` counts even when the other organization is ready. An absent identity-map entry is unknown, never a frontend-invented zero.

1. **GET `/api/movie-awards/snapshot`** — no provider calls or import initiation. Return `schema_version`, `ready`, `awards_generation`, organization coverage/status, `movies` keyed by explicit `tmdb:<id>`/`imdb:<id>`, and `people` keyed by explicit person TMDb ID with distinct actor/director count objects. Both movie aliases are projections of one entity. Integer counts or `null`; unknown identity stays absent. ETag includes schema and generation; If-None-Match returns 304. Missing store returns `ready:false`, empty maps, and no filesystem creation.
2. **GET `/api/movie-awards/status`** — safe coverage, import, next-due, and failure summaries. No credentials, source payload dumps, mutations, or external requests.
3. **GET `/api/movie-awards/person-films`** — positive `person_id`, `role` exactly actor/director, `award` exactly oscar/golden_globe, `page>=1`, `page_size` 1–100, optional `generation`. Bad inputs return 400. Requested superseded generation returns 409 with current generation so Discover restarts page 1 once. Read one transaction-consistent generation; return standard Discover `results`, `page`, `page_size`, `total_pages`, `total_results`, `has_previous`, `has_next`, plus `award_wins` and `awards_generation`. For a validated zero: empty results/zero films, minimum one empty page. Unavailable awards coverage returns 503 with an explicit retryable error, not a successful zero.

Winning-film endpoint uses existing cached `_movie_card_projection`/`_tmdb_card_projection_by_id` and `_normalize_tmdb_movie_summary` through the injected `project_movie` callback, falling back to the verified seed's minimal movie facts. It does not fetch providers, enrich the catalog, change identities, or write descriptions. Existing frontend owned-canonical merging and ordinary card-detail loading remain authoritative. Titles/posters/rating may be sparse offline; keep the winning identities and exact total, show existing placeholders, and allow normal detail loading when the user expands a card. Do not drop a verified winning film merely because its full TMDb metadata is uncached.

#### Weekly refresh and runtime lifecycle

`MovieAwardsRefresh(store, source_transport, identity_resolver, clock).start()/stop()/run_due_once(now)` owns all automatic imports. `app.py` constructs it once from the active user-data owner, starts it from normal `_start_background_services`, and stops it through the existing shutdown/atexit path. Automatic startup is disabled in `CP_TEST_MODE`; tests inject the clock/transport and call `run_due_once` directly.

- Bootstrap current seed through the approved implementation/deployment process. Retain per-organization last complete ceremony and year; the next ceremony is not inferred from film eligibility year.
- Use Africa/Cairo calendar months for eligibility; persist all attempt/due/lease timestamps in UTC. Define `cairo_calendar(now_utc: datetime) -> date` in the refresh owner. On Windows, cache the `Egypt Standard Time` dynamic zone entry from [EnumDynamicTimeZoneInformation](https://learn.microsoft.com/en-us/windows/win32/api/timezoneapi/nf-timezoneapi-enumdynamictimezoneinformation) and convert injected UTC using [SystemTimeToTzSpecificLocalTimeEx](https://learn.microsoft.com/en-us/windows/win32/api/timezoneapi/nf-timezoneapi-systemtimetotzspecificlocaltimeex) through standard-library `ctypes`. This permanent platform adapter uses Windows' own DST data and does not depend on the host's selected timezone or missing Python tzdata. On non-Windows, use `ZoneInfo('Africa/Cairo')`; absence/conversion failure keeps scheduling pending with a diagnostic, while existing counts/cards remain usable. No fixed UTC+2 assumption or new dependency.
- First eligible check in January (Globe) or March (Oscar); subsequent pending checks seven days after the last attempt. A result arriving after the award month remains due weekly until complete. Do not scrape next-ceremony dates to drive this schedule.
- App closed for the award month: on next startup, check an overdue uncommitted ceremony immediately, even outside its month. No worker runs while CP is closed; reopen resumes from persisted state. More than one missed year creates chronological due ceremony jobs; completed jobs remain idempotent.
- Worker wakes at most every 60 seconds to inspect local due state; it does not contact sources on each wake. Organizations/years are independent; an incomplete Globe ceremony does not hold a complete Oscar ceremony back.
- Source requests: identified User-Agent, HTTPS allowlisted domains, 20-second socket timeout, 40MiB dataset / 2MiB ceremony-response limits, maximum five redirects, conditional ETag/Last-Modified when supplied. Read bounded bytes before parsing. Schema/category/winner/identity errors are pending results, not empty wins.
- Only one source-check attempt per due job per seven-day window. No tight network retry loop. For HTTP 429 honor Retry-After when later than the weekly due; otherwise wait seven days. Failures, unavailability, missing credentials, and incompleteness keep the prior committed generation.
- Identity bridge: reuse verified mappings first, at most two concurrent TMDb requests and four requests/second, with the same bounded timeouts. Persist unresolved evidence; do not change any accepted catalog identity or request credentials from a card.
- Success publishes atomically, clears pending state, marks that ceremony complete, and computes eligibility for the following year. Stop external checks for the completed ceremony. Frontend sees the new generation on its next shared local revalidation.

Refresh states are `awaiting_month` (not eligible), `pending` (due or retry scheduled), `checking` (valid lease), and `complete` (atomic import committed). A failed/expired checking lease returns to pending. A pending ceremony's incomplete evidence is never stored as a complete import. Imported contributions and diagnostics remain separate.

The refresh does not need ceremony-date automation. A future ceremony moved outside the agreed month can delay the first check; do not quietly introduce a different scheduling product. Unknown future categories/layouts keep the job pending for reviewed adapter/taxonomy maintenance.

### Reference screenshots and asset preservation

The supplied temporary files are design evidence; do not make runtime code depend on these paths:

| Reference | Supplied file in `C:\Users\dante\AppData\Local\Temp` |
| --- | --- |
| Expanded movie header placement | `codex-clipboard-62cd44c9-242e-44d6-a74c-73e60688e0b6.png` |
| Standard movie footer placement | `codex-clipboard-c8292870-8f37-4859-b9c0-4dd76701c957.png` |
| Golden Globe artwork | `codex-clipboard-91457cf6-78e6-481d-a71b-01142148d25a.png` |
| Oscar artwork | `codex-clipboard-966a032f-bf24-4d0c-8993-18c41b8e6ad8.png` |
| Person white-dot positions | `codex-clipboard-8e12edbe-2694-4aee-836c-49ad9b1efb8f.png` |

After implementation approval, preserve these under `docs/verification/movie-awards/reference/` with hashes before cleanup. Prepare transparent runtime PNGs from the supplied symbols, removing only background/checkerboard and trimming empty bounds; retain the approved actual artwork. Use the image-editing skill/tool for raster preparation when required. If files disappear, recover the attached originals or request them again; do not silently substitute a generic trophy. No image editing has been performed while writing this plan.

## Implementation sequence

Each task has a focused test cycle; do not continue past a failing contract gate. Tasks depend on their predecessors unless stated otherwise. Names/interfaces below are shared contracts, not permission to implement.

### Task 1 — Verified sources, taxonomy, and historical seed

**Replacement-source execution refinement:** The approved whole-ceremony replacement path also reads pinned Wikipedia category tables as independent winner/film-association evidence when annual summaries omit associations. Keep this parsing in `services/movie_awards_sources.py` under `category_html`; it accepts explicit award taxonomy, pinned revision/URL, declared eligibility/ceremony year basis and named film/person columns. Reconstruct table row spans before reading ties and multi-film winners. Require the source's explicit winner legend or a revision-matched reviewed convention (bold/colored winner cells, or an exact recipients-only table header), then a positive winner marker; reject nominees, reject year/ordinal disagreement and missing winning evidence, and retain linked film/person targets for the existing typed identity bridge. A category page alone never declares a whole ceremony complete: independent program expectations and full winning-set comparison remain mandatory. Acquisition remains bounded, cached, public and separate from runtime rendering. The scraped modern feed remains audit-only unless its data permission is established; replacement bundled inputs retain their own attribution and license. This refines the already approved incomplete-feed fallback without weakening historical completeness or any counting contract. A declared primary group may combine disjoint category owners for a ceremony; two sources owning the same category in the same ceremony are rejected. Pinned independent supplements may replace an explicitly named inaccurate/incomplete category block and extend the program from independently observed awarded categories. Independence is required for each category: a primary record must never verify its own category, even if a different category legitimately uses the same publication on the other side of the audit. Every supplemental byte hash and factual-record citation must be retained; no claimed complete flag substitutes for the full winning-set comparison. Targeted official film pages resolve concrete source disagreements; retain raw pages in OS-temp and distribute only reviewed sparse factual records and attribution, never website prose or a copy of its database.

**Create:** sources/identity modules, seed builder, four `static/movie-awards` inputs above, `tests/test_movie_awards_sources.py`, `tests/test_movie_awards_identity.py`, small pinned source fixtures under `tests/fixtures/movie_awards/`.

**Interfaces:** Produce `NormalizedWin`, `CeremonyProgram`, `ValidationReport`, `CeremonyContribution`, `IdentityResolution`, the parser/validator/aggregator and resolver signatures above. JSON seed contains committed ceremony aggregates, person win links, mappings, coverage and schema version; manifest includes source revisions/hashes, category-taxonomy revision, seed hash, licenses, and per-ceremony audit.

- [x] Add failing fixture tests: `test_gladiator_counts_two_categories_not_three_recipients` → film Globe count 2; `test_les_girls_shared_actress_category` → film count 2 and each tied actress has her own win; `test_hindenburg_special_subtypes_remain_two` → film Oscar count 2; `test_one_person_win_multiple_films` → one person win and all linked films.
- [x] Add failing classification/completeness tests: nominations-only, missing winner/category, TV movie misleading phrase, new category, tied short-film winners, unknown `?` IDs, year/ceremony mismatch, malformed literal arrays, 2025/2026 annual layouts, source disagreement, and a same-name identity conflict.
- [x] Run focused modules in isolated test mode; confirm failures are missing new behavior, not unrelated import/setup errors.
- [x] Implement pure adapters, explicit aliases and aggregation. Implement verified identity mapping with injected provider callbacks. Assert unresolved/ambiguous identities stay unresolved and TV/person/movie collections cannot cross-map.
- [x] Implement builder CLI `--output-root <OS-temp path> --sources-manifest <file> --identity-overrides <file>`; credentials come from the existing credential owner without logging. Fetch source bytes only under the authorized seed-build scope, pin revisions, retain required source notices, and write aggregates rather than raw full datasets.
- [x] Produce and inspect the full historical coverage report. Resolve all included identity/coverage gaps before marking a historical organization ready; otherwise stop that publication step and report exact missing evidence. Small count examples do not waive this gate.
- [x] Run focused tests green. Verify deterministic seed output from the same pinned inputs, no category breakdown in saved movie contributions, no unrelated events/TV awards, and no network needed to render the seed.

### Task 2 — Transactional store and read-only APIs

**Create:** store/routes modules; `tests/test_movie_awards_store.py`, `tests/test_movie_awards_api.py`.

**Modify:** `app.py` only for lazy store dependency/projection callback and route registration. Existing catalog schema/canonical contracts stay unchanged.

**Interfaces:** Produce `MovieAwardsStore` and `register_movie_awards_routes` APIs above; consumed seed schema exactly matches Task 1.

- [x] Add failing tests: seed idempotence; repeat same import no generation increase; valid correction replaces totals; exception between film/person writes rolls everything back; malformed seed/newer schema rejected; concurrent lease readers see one committed generation; read endpoints do not create/import a missing store.
- [x] Add API tests asserting body, ETag/304, namespace/role counts, all validation statuses, exact person winning-film IDs, deduplication versus `award_wins`, generation conflict, pagination, and uncached winning films retained via minimal facts. Verify external transport and catalog-writing callbacks are never invoked.
- [x] Implement schema constraints, transaction publication, SQL-derived totals, and independent awards generation. Keep pending source attempts separate from visible imports.
- [x] Wire existing normalization/projection callbacks rather than a second movie normalizer. Test owned canonical merge in the subsequent complete-path UI task.
- [x] Run Task 1–2 focused modules green and existing catalog/canonical/cache tests unchanged; assert normal catalog/media generations, TV/IPTV schemas and existing metadata rows are unchanged by awards operations.

### Task 3 — One annual refresh owner and lifecycle

**Create:** refresh module, `tests/test_movie_awards_refresh.py`.

**Modify:** app startup/shutdown dependency wiring; extend `tests/test_startup_background.py` with awards lifecycle assertions while preserving its existing worker, no-artwork-mutation and catalog-generation assertions.

**Interfaces:** Consume Task 1 validation/identity and Task 2 lease/publication APIs. Produce `start`, `stop`, `run_due_once` with injected clock/transport.

- [x] Add failing fake-clock tests for January/March first check, seven-day cadence, crossing month end while incomplete, process reopen after a missed month/year, independent organizations, no requests after completion, HTTP failures/429, unsupported categories, crash lease recovery, missing credentials, and clean stop.
- [x] Add Windows calendar tests around Cairo month boundaries and UTC due times, including an injected June UTC timestamp that exercises Cairo DST, Windows host set to another timezone, missing zone entry, and conversion failure. Implement `cairo_calendar` using the explicit platform contract above; do not shell out or hardcode an offset.
- [x] Implement bounded transport, persisted due state and one cancellable worker. Install seed without blocking Flask readiness; periodic wake reads local state only.
- [x] Prove `_TEST_MODE` never auto-starts external refresh and two runtime starts cannot launch two award workers. Prove existing library/qBittorrent/TV owners still start as before and shutdown cancels the new worker without interrupting them.
- [x] Run focused source/store/API/refresh/startup tests green. Record exact failure diagnostics from incomplete fixtures and verify they do not publish partial rows.

### Task 4 — Shared counts and precisely placed icons

**Create:** shared API/context/renderer/styles/assets; `tests/movieAwards.test.mjs`; preserve screenshots under the verification reference directory when authorized.

**Modify:** existing `MovieCard.jsx`/`movieCard.css`, `SharedMovieCards.jsx`, `PersonCreditCard.jsx`, relevant person rail rules in `styles.css`/`movieRelationships.css`, Home `SmartMovieCard`, root provider mounting. Do not add page-specific award CSS.

**Interfaces:** Task 2 snapshot → shared cache; hook signatures and renderer props exactly as specified above. Extend card props explicitly; default remains null/inert.

- [x] Add failing JS checks for concurrent snapshot deduplication, ETag unchanged identity, stale generation rejection, last-good preservation, canonical conflicting IDs, opt-out consumers, role-specific person totals and zero/unknown suppression.
- [x] Prepare and inspect supplied artwork on CP dark background; verify true alpha, silhouette, dimensions, no checkerboard/black rectangle. Add exact tooltip strings in the one renderer.
- [x] Implement shared cache/context and opt-in regular wrappers. Refactor the existing footer condition to permit award-only cards while preserving rating/votes and expansion behavior. Add the person rail at the two approved positions.
- [x] Preserve default TV/IPTV/search rendering. No title guessing, external source imports, count logic, or provider calls belong in JSX.
- [x] Update the conflicting source-text test only with preserved rating expectations plus award-only cases. Run JS/source UI checks green; compiled geometric proof follows in Task 6.

### Task 5 — Winning-film Discover relationships without changing filmography

**Modify:** `PersonCreditCard.jsx`, `SharedMovieCards.jsx`, `src/App.jsx`, Discover, Library, Movie Lists, AI Control workspace callback owners.

**Create/extend tests:** `tests/movie_relationships.test.mjs` for context/history helpers and `tests/test_movie_awards_api.py` for complete backend result identity.

**Interfaces:** `onPersonAwardDiscover(role, person, award)` → root/local Discover `person-awards` context → Task 2 endpoint. Keep the existing biography/full-filmography/body callbacks separate.

- [x] Add failing tests: award action chooses award+person+role, existing filmography remains full, owned/unowned wrapper forwards callback, Pick award action enters Explore, and existing related/collection/person contexts remain unchanged.
- [x] Extend the existing request/context owners and their snapshot/history storage. Reuse current request abort/sequence handling and result card rendering. Give the initial award context all availability without carrying stale narrowing criteria.
- [x] Wire Library, both Lists branches, AI Control, and all Discover expanded-credit branches, including enriched indexer results. Do not infer eligibility from `creator`, person name, or full-filmography fallback.
- [x] Restore the previous criteria/context/scroll through current Back machinery; handle cross-workspace origin and browser history consistently with related navigation. Late unrelated responses cannot replace award results.
- [x] Run API and relationship JS tests green; prove exact winning-film membership, not just the outgoing query string.

### Task 6 — Complete-path desktop proof and preservation gates

**Create:** `tests/e2e/movie-awards.spec.js`, `tests/seed_movie_awards_e2e.py`.

**Modify:** isolated `tools/run_playwright_e2e.ps1` to install deterministic awards fixtures inside its generated `CP_TEST_ROOT`; add fixture-shape helpers to `tests/native_tv_server.py` only when needed to render the same shared card under the existing TV test environment. No production test-only endpoint.

**Extend:** `tests/e2e/movie-relationships.spec.js` to test award-bearing geometry while preserving current assertions; packaging inclusion assertion in `tests/test_release_packaging.py`.

- [x] Seed a synthetic complete local awards database and movie/person fixtures; use real Flask awards endpoints for at least one click-through test. Mock normal TMDb transport only at the fixture boundary. Assert API film IDs/counts and rendered title/ID cards agree.
- [x] Implement A01–A30 below at desktop 1920×1080, 1600×1000, 1366×900, and the existing compact desktop height case. These are desktop viewports, not mobile targets.
- [x] Capture standard/expanded/person screenshots with zero, one and two awards, long names/titles, two-digit counts, absent ratings, and Arabic metadata. Compare placement against preserved references and numeric geometry, not general appearance.
- [x] Run existing regular movie relationship/card, owned Lists, Library, Home/AI, TV and IPTV tests. Demonstrate the unchanged biography/filmography/body actions and exclusions in rendered screens, not only source assertions.
- [x] Run broader suites and isolated build gates below. Record all pre-existing versus new failures. Never weaken a geometry/history/identity assertion to obtain green.
- [x] Produce a contract-by-contract verification report under `docs/verification/movie-awards/`. Implementation is not live merely because this report passes.

## Acceptance matrix

| ID / starting state | Action | Exact expected result | Owner / automated proof |
| --- | --- | --- | --- |
| A01 Regular film with both positive counts | Render standard and expanded | Number-left gold icons at agreed positions; Oscar first; unchanged rating/votes/IMDb/expand | Real API + Playwright card assertions/screenshots |
| A02 Zero / one award / unknown coverage | Render all three states | Hide zero/unavailable pair; retain other award in its designated place; no false zeros or empty badge | JS + Playwright |
| A03 *Gladiator* recipient-oriented rows | Aggregate | Globe film count 2; source 3-recipient presentation never becomes CP 3 | Source fixtures |
| A04 *Les Girls* shared acting winner category | Aggregate film/person | Film count 2; each recipient's eligible personal win counted once | Source fixtures |
| A05 Multiple-film historical personal award; Oscar special subtypes | Aggregate/open person set | One personal win can link several films; *Hindenburg* film specials remain 2 | Source/store/API tests |
| A06 One person wins acting and directing | Render each credit role / click each award | Separate role totals and role-specific winning-film IDs; no producing/writing/TV additions | Source/API/real-path E2E |
| A07 TV/IPTV/people/keyword IDs collide with movie IDs | Render excluded surfaces | No award elements; prior controls/layout/provider enrichment remain unchanged | JS opt-out + TV/IPTV/search E2E |
| A08 Owned canonical ID differs from raw candidate | Render Library/Discover/Lists | Use accepted owned identity; no raw candidate's counts or description overwrite | Owned merge E2E |
| A09 IMDb/TMDb disagreement, missing IDs, same-name people | Resolve/render | Conflict/unresolved stays unavailable; no title/name guess or wrong person | Identity/API/JS tests |
| A10 Existing published ceremony | Import identical payload twice | Same totals/generation; no extra wins | Store tests |
| A11 Crash during replacement / two import workers | Publish/reopen/concurrent claim | Readers see old or fully new generation only; expired lease recoverable; one writer | Store/refresh tests |
| A12 Nominees only / some winners / missing category | Weekly check | No publication/completion; previous counts retained; next due seven days | Source/refresh tests |
| A13 Legitimate tie / shared recipients | Validate complete ceremony | All tied winning films/people retained; no “exactly one winner” false failure | Source tests |
| A14 Unknown/new/retired category or unsupported page layout | Validate | Pending with precise diagnostic; no silent skip or invented counts | Source/refresh tests |
| A15 January/March check; results arrive next month | Advance fake clock | Weekly beyond month until complete; stop completed year; organizations independent | Refresh tests |
| A16 CP closed in award month / offline / 429 / missing credentials | Reopen/retry | Catch up overdue years; honor bounded retry; do not block app or falsify zero | Refresh/startup tests |
| A17 Award-winning film without rating | Render collapsed/expanded | Awards visible; no fabricated star/rating/votes; footer geometry correct | UI + Playwright |
| A18 Long names/titles and two-digit counts; narrow desktop | Render each target viewport | Award pairs fit the selected right-side area below existing actions and clear of person labels; preserve uniform existing portraits, complete readable counts, rating/control separation and artwork aspect ratio; no general grid widening | Playwright box/overflow assertions |
| A19 Expanded card populated/loading/error/long credits | Expand/load details and rail | Credits slot 238px, ten-column allocation, 106×132 reference avatars at 1920, normal rail 236px and 16 tiles; existing compact-height rules and scroll stable | Existing relationship E2E plus awards cases |
| A20 English/Arabic metadata and delayed snapshot | Switch language/finish request | Same totals; number left of icon; no description/canonical overwrite or expanded-state reset | Cache JS + Playwright |
| A21 Hover and keyboard focus/activation | Hover/click/Enter/Space award controls | Hover exactly “Oscars” / “Golden Globe”; one action; visible focus; biography/filmography/body actions do not also run | Playwright events/tooltips/navigation |
| A22 Person Oscar/Globe membership | Click each icon | Only films earning that person's relevant award; exclude nomination-only films and films awarded solely for others | API IDs + rendered IDs in real endpoint E2E |
| A23 Two wins for same film; multiple pages | Open winning films/page | Person win count and unique film count separate; every matching film reachable, no duplicates or related-feed cap | API pagination + Playwright |
| A24 Existing search/ownership filters and cross-workspace origin | Click award then Back/Forward | Initial complete award set; prior Library/Lists/AI/Discover state, criteria/page/expansion/scroll restored | Relationship JS + origin E2E |
| A25 Slow prior filmography/search response | Click awards, complete old request late | Old response ignored; latest request owns results; history not duplicated | Playwright deferred responses |
| A26 Awards unavailable/local request fails | Load cards/revalidate | Last good data retained; first load quiet; normal movies usable; no external provider request | JS/API/E2E request assertions |
| A27 Active snapshot changes between pages | Request old generation | 409 handled with one page-1 reload; consistent new generation; no mixed totals | API + Playwright |
| A28 Winning film metadata uncached/offline | Open awards set/expand | Verified winning identity retained with normal placeholders; no award-route provider calls/catalog writes; ordinary details path preserved | API + real-path E2E |
| A29 All included shared callers | Visit Library, Explore/Pick, Lists owned/unowned, AI, Home | Same count renderer and correct opt-in; original controls/list/watch/play/acquisition behavior preserved | Existing suites + award caller matrix |
| A30 Runtime/test seed, package, restart | Start isolated app / inspect package manifest | Seed included in existing static packaging; startup remains usable; no automatic test network or TV/IPTV/catalog schema changes | Startup/package/broad suites |

## Verification and rollout

### Baseline and isolation

Before code edits, record current status, branch/commit, runtime/data/dist facts again and run existing relevant tests using fresh OS-temp roots. Record counts, failures and skips as the baseline. No tests were run or claimed green while preparing this plan.

Existing focused baseline selection: `tests.test_startup_background`, `tests.test_unified_movie_card_ui`, `tests.test_movie_relationships`, `tests.test_collection_resolution_api`, `tests.test_release_packaging`, and the current Node movie-details/catalog-events/relationships tests. Run the existing broader suites below before adding new behavior. Do not attempt the new awards test modules until their task creates them.

Run commands from `C:\Users\dante\Desktop\cinema paradiso` in a dedicated PowerShell session. Resolve `.venv\Scripts\python.exe` first. Do not point tests at live configuration/databases or build over live `dist`.

```powershell
$cpAwardsTestRoot = Join-Path ([IO.Path]::GetTempPath()) ('cp-awards-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $cpAwardsTestRoot | Out-Null
$env:CP_TEST_MODE = '1'
$env:CP_TEST_ROOT = $cpAwardsTestRoot
$env:PYTHONDONTWRITEBYTECODE = '1'
```

### Focused tests

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_movie_awards_sources tests.test_movie_awards_identity tests.test_movie_awards_store tests.test_movie_awards_api tests.test_movie_awards_refresh tests.test_startup_background tests.test_unified_movie_card_ui -v
node --test tests/movieAwards.test.mjs tests/movie_relationships.test.mjs tests/movieDetails.test.mjs tests/catalogEvents.test.mjs
```

Expect all selected tests to pass with no unplanned skips, real identity/count assertions, and external network disabled. Run the task's module first for red/green; these combined commands are the final focused gate. Preserve traces/logs on failure.

### Broader suites and compiled desktop UI

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
$cpAwardsNodeTests = Get-ChildItem -LiteralPath tests -Filter '*.test.mjs' -File | ForEach-Object { $_.FullName }
node --test $cpAwardsNodeTests
npm.cmd run test:e2e -- tests/e2e/movie-awards.spec.js tests/e2e/movie-relationships.spec.js
npm.cmd run test:e2e
$env:CP_TV_E2E = '1'
npm.cmd run test:e2e -- tests/e2e/native-tv.spec.js tests/e2e/tv-expanded-parity.spec.js tests/e2e/tv-parity.spec.js
Remove-Item Env:CP_TV_E2E
```

The Playwright script builds into its own OS-temp `CP_TEST_DIST_DIR`, starts a hidden isolated server on 5117 and seeds provider fixtures. Its current `playwright test @args` forwards the selected spec arguments shown above. Add the awards seed there as Task 6 specifies. Confirm 5117 is available rather than terminating someone else's process. Recheck script argument forwarding if the dirty checkout changes before execution. The native-TV server is a separate test environment, not a substitute for the normal Flask complete-path proof.

The full Python/Node/normal E2E suites and appropriate TV subset must be reported separately. An existing failure must be reproduced/documented and its effect on this feature explained; a newly introduced failure blocks acceptance. A focused rerun is never described as a green full suite.

Verify rendered compiled screenshots and actual clicks at the desktop viewports above. Preserve existing numerical movie-relationship geometry assertions, snapshots/scroll/history, ownership controls and IPTV/TV actions. Build success alone does not prove the design.

### Gates and separate live authorization

| Gate | Evidence needed | Authorization |
| --- | --- | --- |
| Plan saved/reviewable | This Markdown file and complete contracts/owner/test map | Already authorized |
| Source implementation | Dante approves this stated plan; isolated implementation/tests only | Still required |
| Historical data readiness | Reproducible pinned build and full ceremony/identity coverage audit; no silent partial totals | Within approved seed-building implementation scope, explicit external data acquisition included |
| Isolated acceptance | Focused/broader results, real awards API→Discover proof, compiled desktop screenshots, exclusions | Within approved implementation/testing scope |
| Live installation and app restart | Fresh process/config/data/dist ownership, backup, version/bundle verification and visible result | Separate explicit authorization |
| Commit/push/package/tag/release | Reviewed scoped diff and corresponding action scope | Separate authorization for each |

For approved live work: back up existing awards DB with SQLite backup semantics (including a consistent WAL state), or record that this is first installation; preserve the previous served `dist` and record exact hashes. Do not backfill/change catalog, TV, IPTV, configuration, or metadata caches. Install the verified seed/store through its owner, build the approved frontend, restart only the identified CP process, and prove that `/` and linked assets match the new served bundle. Record local endpoint counts and visually verify standard/expanded/person clicks against the same generation.

Rollback triggers: wrong film/person association, recipient multiplication, partial totals published, TV/IPTV leakage, broken biography/filmography/history, clipped controls/portrait, changed fixed desktop geometry, failing newly affected tests, or source parsing that treats nominations as wins. Restore the prior verified frontend/source deployment and awards backup; stop the awards worker before restoring its DB. Do not reset the dirty checkout or repair unrelated domains. First installation rollback removes only explicitly identified new awards deployment artifacts after checking paths/authorization; catalog and provider databases are untouched.

### Completion report

Report the changed owners and reasons; seed coverage/provenance and known source limits; exact test pass/fail/skip results; desktop screenshots and backend/rendered winning-film IDs; any remaining contract difference; and whether the state is source-only, tested in isolation, or live verified. Recheck every contract table row. A passing suite does not erase an observed contract violation.

### Plan self-review

- Agreed count frames, role boundaries, zero handling, placements, exact hover text and both person award actions each map to tasks and acceptance rows.
- Shared callers, stale metadata/canonical identity, excluded TV/IPTV/search surfaces and owned/unowned forwarding are named explicitly.
- Source completeness, category changes, historical shared/tied/multi-film awards, identity ambiguity, retry/crash/concurrency and bootstrap coverage have blocking checks.
- Backend totals and rendered membership are tested together; outgoing URL assertions alone are insufficient.
- No source, test, asset, runtime, config, catalog or provider change is authorized by the existence of this plan. No implementation has been performed during this planning task.

## Implementation evidence and rulings

- 2026-10-02: The proposed contract-change warning about a collective film-series special honor was withdrawn as unnecessary. The approved contract already counts wins for individual movies. Verified non-individual subjects are classified in the authoritative source taxonomy, remain visible in the audit as collective exclusions, and do not resolve to a guessed movie. Film-specific historical special awards remain included. This is source classification within the approved scope, not a new product decision.

- 2026-10-02: Dante supplied an additional Tom Cruise placement example (`docs/verification/movie-awards/reference/person-placement-clarified.png`) and explicitly said the white areas identify award-logo placement and the actor photo was untouched. Preserve portraits and the existing grid; resize only the awards to fit those areas. Previous portrait-resize/scrolling choices are withdrawn.

- 2026-10-02 completion checkpoint: all six approved source tasks are implemented. The clarified layout preserves actor photos/grid and shrinks logos within the selected right-side area. Historical coverage is now Oscar 98/98 and Globe 83/83, zero unresolved/conflicting identities or source failures. Pinned licensed category sources and 118 sparse independently cited official facts close the retired/special/new-star gaps. Eight factual additions preserve distinct film-specific/outdoor/Samuel Goldwyn instances; unassociated career honors stay excluded. The full independent program/winning-set gate and actual cited-origin independence remain mandatory. The seed is offline-reproducible, SHA-256 d634b020c4f8410cc1b916eab6c38ab5b389cea749885347f2da51240da918b3, 181 contributions and 2,377 typed mappings. Current focused source/identity/bundle checks: 119 passed. Final full Python: 1,563 passed in 206.699 seconds, including the source-independence guard and expanded bundled-store assertions; two non-failing ResourceWarnings. Latest evidence is authoritative in docs/verification/movie-awards/implementation-report.md. No live actions, new approval questions or shutdown are part of completion.
