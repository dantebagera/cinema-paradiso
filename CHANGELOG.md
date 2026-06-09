# Changelog

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
