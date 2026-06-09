# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- Cinema Paradiso v2.5 release preparation.

## Current Goal

- Publish the React/Vite Cinema Paradiso release to GitHub with updated documentation, version metadata, tests, and a clean branch.

## Completed

- Installed Impeccable skills under `.github/skills/impeccable`.
- Created root `PRODUCT.md` and `DESIGN.md`.
- Added React/Vite frontend scaffold at the repo root.
- Added Flask serving for the built React app, with the legacy template still available at `/legacy`.
- Built the black/gold Cinema Paradiso styleguide and app shell.
- Built Home with library health, release watchlist, trending discovery, movie inspector, and archive-aware actions.
- Converted the release watchlist from browser-only `localStorage` to backend user data.
- Added followed-release checks that ignore CAM/TS/HDCAM/screener releases and alert only for proper WEB/Blu-ray 1080p+ sources.
- Built Library Movie View and File View with pagination, search, filters, play, source search, rename, delete, trailer, director/cast, collections, and user lists.
- Added user-created lists and user-edited TMDB collection overrides.
- Built Settings as a system/integrations console for library paths, app data, Plex, Prowlarr, TMDB, and Ollama.
- Built Cleanup as an offline maintenance center with Duplicates, Smart Clean, Low Quality, and Unmatched Plex tabs.
- Built Discover with Explore Movies, Browse Indexers, and Pick My Movie.
- Added archive-aware Discover actions: Play, Stream, Find Sources, Find Upgrade, Trailer, Follow, and list controls.
- Added TMDB details, collection cache, and metadata helpers.
- Added tests for TMDB detail transforms, user curation store, and release quality gating.
- Updated README and context docs for v2.5.

## In Progress

- GitHub publication for v2.5.

## Next Up

- Push the v2.5 branch to GitHub.
- Optionally create a `v2.5.0` tag/release after review.
- Continue real-data QA for Discover, release watchlist checks, and multi-root library scanning.

## Open Questions

- Whether to rename the GitHub repository from `10k-movie-library-organizer` to `cinema-paradiso`.
- Whether future releases should commit built `dist/` assets or require users to run `npm install && npm run build`.

## Architecture Decisions

- Flask remains the API backend.
- Vite builds the React frontend to `dist/`; Flask serves it when present.
- The original `templates/index.html` UI remains reachable at `/legacy` during migration.
- `winapp/` remains untouched during active web app development.
- User data and cache are separate:
  - persistent user data: lists, edited collections, followed releases
  - disposable cache: TMDB metadata, resolution probe cache
- `movies_dir` remains the legacy primary library root, while `movies_dirs` supports multiple configured roots.

## Session Notes

- Brand personality is cinematic, powerful, sleek.
- Visual north star is "The Cinematic Archive Console".
- Avoid generic SaaS dashboards, cheap Plex clones, purple AI gradients, glassy crypto UI, beige premium templates, and cluttered torrent-indexer tables.
- Movie cards should be wide and proportional, with compact facts at rest and readable plot/cast/trailer in expanded states.
- File paths and destructive actions belong in file-management and cleanup contexts, not casual movie browsing contexts.
