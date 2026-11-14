# Movie and TV detail feature decisions

[Movie and TV detail features code map](../atlas/movie-and-tv-details.md) · [Second Brain index](README.md) · [Update log](log.md)

## 2026-11-13 IPTV integration candidate

On 2026-11-13 Dante extended the existing portrait controls to IPTV. IPTV actor-card navigation retains compatible refinements within the current provider. The small Filmography button clears Discover criteria and opens full Movie Discover filmography, including titles absent from IPTV. This supersedes the earlier provider-only small-button behavior. Reset filters within provider-local portrait browsing retains the person. Explicit Provider View leaves person navigation. Biography is lazy and uses IPTV settings; provider-local portrait browsing remains offline. Full Discover filmography uses the existing TMDB credits flow. Existing Movie/TV behavior stays unchanged.

Authority: [approved plan](../plans/2026-11-13-iptv-cast-discover-streaming.md). Evidence: [2026-11-13 isolated verification](../verification/iptv-cast-discover-streaming-2026-11-13/report.md). Candidate is in the managed `iptv-discover-streaming` worktree at baseline `117526b` plus the preserved dirty desktop source. **Historical integration verification; see the correction and activation record below for current status.**

## Approved behavior

| Decision | Rule | Authority |
| --- | --- | --- |
| TV expanded page, 2026-09-22 | Reuse the Movie visual design for TV detail and credit presentation. Preserve TV episodes, season navigation, and saved versus preview actions. Provider detail failures leave existing local TV actions usable. | [TV expanded parity plan](../plans/tv-expanded-page-movie-parity-zero-regression-plan.md#intended-behavior) |
| Movie collections, 2026-10-01 | Discover shows the collection's provider members with deliberate refinements, clears the previous title search, and restores the original state on Back. Library counts only valid local owned files and reports unresolved parts and conflicts. | [Collection contract](../plans/movie-collection-navigation-and-count-plan.md#exact-behavior-contract) |
| Movie filmography, 2026-10-01 | The small Filmography button opens full credits with cleared Discover criteria. The credit card body retains contextual refinements. Back restores the prior search, filters, and expansion. TV uses its own credits query. | [Filmography contract](../plans/movie-credit-filmography-button-plan.md#exact-behavior-contract) |
| Movie related browse, 2026-10-01 | The compact rail shows at most 16 posters. View all exposes up to 100 unique Recommended and 100 unique Similar movies. All backfills Similar duplicates where possible. A failed total keeps healthy pages and navigation usable. | [Related browse contract](../plans/movie-related-browse-limit-plan.md#exact-behavior-contract) |
| Movie awards, 2026-10-02 | Count verified individual-film wins once per film, category, and ceremony. Person totals and winning-film browsing are role-specific. Display positive counts on approved Movie surfaces and fit the icons in the existing credit area without shrinking portraits. Awards navigation preserves origin and canonical identity. | [Recorded decisions](../plans/2026-10-02-movie-awards-implementation-plan.md#what-dante-wants--recorded-decisions) · [Placement clarification](../verification/movie-awards/implementation-report.md#placement-clarification-and-sizing-correction) |
| Plot restoration, 2026-10-04 | Use a loaded detail plot when a card summary lacks it. Keep valid canonical plots, restore the English description after Arabic display, and preserve the ordinary placeholder for a truly missing description. | [Plot repair contract](../plans/2026-10-04-award-navigation-missing-plots.md#exact-behavior-contract) |
| Movie artwork loading, 2026-10-12 | Defer offscreen artwork through the shared card owner while preserving visible imagery and the desktop design. The later main integration preserves the adopted shared cards and performance changes. | [Artwork performance contract](../plans/2026-10-12-mostafa-performance-plan.md#contracts-affected-and-contract-change-decision) · [Main integration](../plans/2026-10-14-new-ui-main-integration.md#contracts-affected-and-contract-change-decision) |

## Evidence and limits

- **Observed in source on 2026-11-13** · Owned and provider-only Movies use the shared details client. TV uses typed routes and its own catalog. Poster overrides, ordinary artwork loading, and award data each have a distinct owner. The map records current source paths for TV posters and shared artwork, whose behavior should be checked independently of the older Movie relationship approvals. [Code map](../atlas/movie-and-tv-details.md)
- **Historical verification** · The 2026-10-01 plans record isolated results and separately authorized local deployment at that time for Movie collection, related browse, and filmography. TV expanded parity and the 2026-10-04 plot repair record isolated results for their stated scopes. [Collection record](../plans/movie-collection-navigation-and-count-plan.md) · [Related record](../plans/movie-related-browse-limit-plan.md) · [Filmography record](../plans/movie-credit-filmography-button-plan.md) · [TV expanded verification](../plans/tv-expanded-page-movie-parity-zero-regression-plan.md) · [Plot evidence](../plans/2026-10-04-award-navigation-missing-plots.md#execution-evidence)
- **Historical awards evidence** · The 2026-10-02 report records isolated API, compiled desktop and historical seed verification, including 1,563 Python passes in that run. It records source coverage and its installation boundary. The current checkout and active awards generation were outside this pass. [Awards verification](../verification/movie-awards/implementation-report.md#current-verification)
- **Live status unverified** · Current served bundle, local poster availability, TMDB results, and active awards coverage were outside this documentation pass. No single current fixture result establishes all four.

## Cold-start questions

- **Why are there fewer owned collection members than provider parts?** Confirm the route, which records have real owned files, unresolved parts, and any active Discover criteria. [Collection scenario](../atlas/movie-and-tv-details.md#scenario-pointers)
- **Why does an award, credit, or related link land on an unexpected page?** Start with the origin and accepted identity. Then inspect the domain, person role or related source, and the saved navigation context. [Details and relationships](../atlas/movie-and-tv-details.md#collections-related-awards-and-artwork)

## Filmography destination correction, 2026-11-13

Dante clarified the small button must open Discover like Movies, and approved applying, testing and activating it with "yes go". The old provider-only button assertion was incorrect and was replaced; portrait browsing retains its local assertion. [Correction plan](../plans/2026-11-13-iptv-filmography-discover-correction.md) · [Verification and activation](../verification/iptv-filmography-discover-2026-11-13/report.md).

Correction activated in the desktop main app: tested bundle `index-rEoonoEd.js` served on port5000 after normal restart; compiled desktop tests 47/47. Live desktop clicking verified: Brad Pitt's small button opened Movie Discover with 115 credits and the IPTV breadcrumb.


## RT main-folder application — 2026-11-14

Dante approved the4px exception for crowded collapsed cards without TMDB/awards, and applying the feature to main. He then instructed not to test; he will handle testing. Applied21feature files while preserving current main changes and rebuilt main dist successfully. No tests, runtime restart or live verification were performed. Collapsed RT shares the bottom row with TMDB; votes label is omitted there, numeric count retained. Expanded RT sits between awards and TMDB; long titles wrap. Optional-Plex persistence and lazy-loading behavior are unchanged. [Application record](../verification/plex-rotten-tomatoes-2026-11-14/report.md).


## Arabic Movie card defaults — 2026-11-14

Dante approved Arabic movie cards defaulting to Arabic across CP, with English available. `src/utils/movieLanguage.js` selects display titles from original-language metadata. `useTransientMovieLanguage` applies the default to shared Movie cards and Home inspector; Home tiles and related Movie rails reuse the title helper. TV retains its existing hook and IPTV retains its provider-owned Arabic display.

Provider summaries, compact SQL Library cards, curated entries and Continue Watching retain original_title/original_language. Saved original metadata is read from the matching TMDB snapshot even when Plex supplies artwork. No identity, file path, catalog language migration or playback-target change. Arabic detail requests occur on expansion, share a bounded session cache, and retain source text on missing translations. The English choice stays local to the mounted card; a different card starts with the default again. Owned/custom artwork and collection membership stay authoritative; existing localized artwork on unowned cards remains supported.

[Approved plan](../plans/2026-11-14-arabic-movie-card-defaults.md) · [Verification and installation boundary](../verification/arabic-movie-cards-2026-11-14/report.md). Worktree implementation; live installation is not implied by tests.
