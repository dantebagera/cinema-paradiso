# Changelog

## v2.6.0 - June 2026

Cinema Paradiso v2.6 is the current stable baseline for the React/Vite movie archive console. It folds the recent UI, metadata, Discover, Library, Cleanup, Settings, and release-watchlist work into one recoverable GitHub release.

### Added

- App metadata storage for file facts, TMDB metadata, Plex metadata, manual matches, and conflicts under user data.
- TMDB-based local metadata matching so users without Plex can still build a rich offline movie library.
- Cleanup > Unmatched Metadata workflow with TMDB search/apply, optional Plex matching, rename, fix-path, and refresh actions.
- Discover vote-count preservation and minimum vote filtering for stronger rating confidence.
- Browse Indexers source selector that loads enabled Prowlarr indexers before search/load and can query one selected indexer.
- Progressive Browse Indexers enrichment: raw Prowlarr rows appear first, then TMDB details are added when available.
- Tests for metadata architecture, library ownership matching, Discover utilities, adult metadata settings, library action UX, and Prowlarr indexer scoping.

### Changed

- Movie View now focuses on files with accepted Plex or TMDB metadata; File View remains the complete local-file management surface.
- Plex is optional for rich local metadata instead of being the only practical metadata source.
- Discover/Home ownership matching prefers stable IDs such as TMDB/IMDb before title/year fallback.
- Browse Indexers search and latest feeds can be scoped to `All indexers` or one selected Prowlarr source.
- Project docs now describe v2.6 as the stable release baseline before future code optimization work.

### Fixed

- Reduced false "not in library" Discover results caused by title differences between Plex and TMDB.
- Prevented Browse Indexers from timing out just by opening the tab; broad latest loading is now explicit.
- Preserved indexer rows without TMDB metadata instead of hiding them.
- Improved v2.6 metadata read-path performance by avoiding writes and TMDB fetches during normal library reads.
- Kept local resolution probing so cropped 1080p files are not mislabeled as 720p.

### Notes

- `config.json`, `data/`, `cache/`, `res_cache.json`, `node_modules/`, `dist/`, and `winapp/` are not part of the committed release.
- Users should run `npm install` and `npm run build` after checkout because built frontend assets are generated locally.
- `v2.6.0` is intended as the stable rollback point before larger code optimization/refactor work.

## v2.5.0 - June 2026

Cinema Paradiso v2.5 is the major release that moves the app from the old file-organizer interface into a React/Vite movie archive console.

### Added

- React/Vite frontend served by the existing Flask backend.
- Cinema Paradiso black/gold UI system with styleguide assets and updated screenshots.
- Home command center with library health, archive-aware discovery, selected movie details, and release watchlist.
- Persistent release watchlist stored in user data, with Prowlarr checks for WEB/Blu-ray availability and CAM/TS/HDCAM filtering.
- Library Movie View for watching decisions and File View for file management.
- Library pagination with 40 items per page.
- Local library search ranking that prioritizes title matches over plot-only matches.
- Simplified resolution buckets: 4K, 1080p, 720p, and Below 720p.
- User lists and edited TMDB collection overrides stored separately from disposable metadata cache.
- Settings workspace for library paths, app data, Plex, Prowlarr, TMDB, and Ollama.
- Cleanup workspace for duplicates, smart clean, low quality, and unmatched Plex workflows.
- Discover workspace for Explore Movies, Browse Indexers, and Pick My Movie.
- Expanded movie cards with director, cast, collection/list context, trailers, and source actions.

### Changed

- App branding changed from My Library Organizer / 10k Movie Library Organizer to Cinema Paradiso.
- Release watchlist now opens a full list view and supports unfollow/delete actions.
- Discover and Library cards now expose Play, Stream, Find Sources, and Find Upgrade based on local ownership and quality.
- Library default sort is newly added instead of title.
- Video stream resolution probing is used to avoid mislabeling cropped 1080p files as 720p.

### Notes

- `config.json`, `data/`, `cache/`, and `res_cache.json` are local runtime/user files and are not committed.
- The Windows app experiment under `winapp/` remains out of scope for this release.
