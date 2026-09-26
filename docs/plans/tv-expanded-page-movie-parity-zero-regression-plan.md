# TV expanded-page movie-design parity — zero-regression plan

Status: approved for implementation by Dante on 2026-09-22. Workspace: `C:\Users\dante\.codex\worktrees\0870\cinema paradiso`. Preserve its existing dirty and untracked work. Desktop only. Do not restart the user's application or alter live catalog, settings, media, or transfers.

## Intended behavior

Keep the TV series as a full page with its season, episode, streaming, and acquisition controls. Make its header metadata, cast, and related-show section follow the movie expanded card's visual and interaction language. Preview and saved TV pages must behave alike.

1. Genres use prominent gold chips; original language and origin countries use quieter chips. Year range and series status remain readable. Missing metadata is shown honestly, without empty chips.
2. Cast and creator credits use the movie credit-card design, including portrait, role, biography button, and filmography button. Clicking the card or filmography button opens that person's **TV** credits. The larger TV credit list remains horizontally scrollable and its More cast control remains available.
3. More like this uses the movie rail's Recommended/Similar/View all presentation but fetches typed TV relationships. Tiles open TV series pages, and back navigation restores the originating series or listing. No movie relationship or movie ownership state may leak into TV.

## Existing authoritative owners

| Responsibility | Owner and change |
| --- | --- |
| TV page, navigation, season/episode actions | `src/features/tv/TVWorkspace.jsx` remains the page owner. Add TV relationship/listing navigation without duplicating movie Discover state. |
| Movie metadata chips | `UnifiedMovieCard` styles in `src/components/movie-card/MovieCard.jsx` and `movieCard.css`. Reuse those classes on the TV header; keep the TV full-page layout. |
| Person cards and biography | `MovieExpandedDetails` in `src/components/SharedMovieCards.jsx`. Extract its person card, portrait, biography modal, and fetch behavior to one shared component; migrate the movie caller without behavior change. Adapt TV credit fields (`tmdb_id`, `portrait_url`, `kind`, `role`) at the TV boundary. |
| Related rail and paging | `RelatedMovieRail`, `movieRelationships.js`, and `MovieRelationships` own the established presentation and bounded relationship pagination. Share the rail presentation and paging logic; use a separate TV-keyed source and TV route. |
| TV provider and search | `TVMetadata` and `TVSearch` own TMDB TV normalization and person `tv_credits`. TV filmography must use the existing TV person criterion, including actor/director/writer/creator roles. |

## Implementation sequence

1. Extract shared person-credit presentation and biography behavior; prove movie card actions still work.
2. Replace the TV plain-text header metadata and plain cast tiles with shared movie-style presentation. Retain natural-ratio poster and all current TV actions.
3. Add bounded, cached TV recommendations/similar paging using TMDB TV endpoints and the existing relationship page owner. Refactor the related rail to support TV without changing movie defaults; implement TV View all and reversible navigation.
4. Add tests for provider/media-type boundaries, empty/failing related responses, TV-person navigation, preview/local parity, cast overflow, metadata chips, and movie regression. Build the frontend and run focused backend and isolated desktop browser checks.

## Safety and acceptance

- Related requests are lazy and independent of header, playback, and episodes. Errors show a retry affordance and never blank the series page.
- Cache keys include media type or use separate TV/movie instances so equal numeric TMDB IDs cannot cross-contaminate.
- The TV rail never calls movie relationship or movie ownership endpoints; TV cast never opens movie filmography.
- Browser Back and in-page Back restore the prior TV surface; changing related source or opening a tile does not erase search filters, season, or episode progress.
- The movie expanded card retains the same ten-credit limit, biography, filmography, ownership badges, related navigation, and layout.
- No media deletion, metadata refresh, series Add, monitoring change, torrent action, runtime restart, or production write occurs during verification.

## Implementation and verification — 2026-09-22

Implemented in the isolated 0870 worktree. The TV page reuses the movie metadata chip styles, shared person cards and biography modal, and the shared relationship rail. TV filmography uses TV person credits, and TV recommendations/similar use a typed TV endpoint with separate cache entries. TV page history restores the previous series or listing and its selected season. Saved rows with a language code such as `en` display a readable language name.

Verification: frontend production build passed; 8 focused Python relationship tests passed; 12 focused Node tests passed; 3 new isolated desktop TV browser tests passed; 26 existing movie relationship and TV parity browser tests passed. The browser fixture used disposable OS-temporary data and a rebuilt isolated bundle. No real library or transfer actions were performed.
