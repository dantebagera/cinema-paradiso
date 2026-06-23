# Changelog

## v2.6.5 - June 2026

Cinema Paradiso v2.6.5 improves large-library metadata matching, followed-release availability, and bulk list workflows while keeping the local-first v2.6 architecture.

### Added

- Trusted Prowlarr indexer selection for followed-release availability, with YTS/YIFY used as the default trusted source when no explicit choice was saved.
- Bulk selection and add-to-list workflows in Library and Discover.
- List popup select-all and local-file copy export with a folder browser.
- Library reset-filters control.

### Changed

- Followed releases only become Available from trusted Prowlarr indexers and approved sources: WEBRip, Blu-ray, BDRip, or BRRip.
- Trusted release indexers are managed from a Prowlarr Settings popup instead of expanding the Settings card.
- Automatic metadata matching accepts clearly dominant exact TMDB title/year matches while keeping strong provider conflicts in review.
- Manual unmatched matches persist as accepted metadata across restarts.

### Fixed

- Rejected WEB-DL, Remux, BDRemux, HDCAM, and TELESYNC-style followed-release matches.
- Improved adult-title handling through separate metadata-search and Movie View visibility settings.
- Kept Movie View fast after restart by avoiding unnecessary full metadata fetches during normal library loading.

## v2.6.4 - June 2026

Cinema Paradiso v2.6.4 adds the Help workspace and prepares the app for a portable release that includes a tested bundled qBittorrent runtime.

### Added

- Help sidebar page with setup guidance for Plex, Prowlarr, TMDB, Ollama, and qBittorrent.
- Official dependency links and Settings shortcuts for each Help section.
- Portable release packaging helper for building a ZIP artifact with the tested bundled qBittorrent runtime.

### Changed

- Settings remains the only dynamic Ready/Missing and connection-test area; Help is documentation only.
- qBittorrent install/update controls are disabled for v2.6.4 because the portable release includes the tested runtime.
- Embedded qBittorrent status now describes the bundled runtime and keeps the system default client option.

### Fixed

- CP-managed qBittorrent now runs hidden in the background instead of opening a standalone desktop window.
- The portable release helper excludes qBittorrent debug symbols, profiles, incomplete downloads, and user data.

## v2.6.3 - June 2026

Cinema Paradiso v2.6.3 strengthens metadata identity, repair, and curation workflows while preserving the local-first behavior of the v2.6 stable line.

### Added

- Identity Review queue for uncertain matches, provider conflicts, and metadata discrepancies, with pause, resume, rescan, selection, and explicit apply controls.
- Home metadata-health counts for unmatched, pending, and identity-review items, with direct Cleanup navigation.
- Library reconciliation for stable files that are missing metadata records, including files predating the current metadata checkpoint.
- Local title/year correction for owned movies without changing Plex metadata or renaming files.
- Durable poster overrides using TMDB artwork, Plex artwork, or local uploads, with reset support.
- Protected Watched and Watchlist system lists, poster controls, and Library viewing-state filters.
- Richer manual Plex matching with local-only apply behavior and explicit retry after a Plex scan.

### Changed

- Unified Library, Discover, collections, lists, duplicates, posters, and ownership checks around accepted Cinema Paradiso identities.
- Improved automatic TMDB decisions using exact titles, official alternative titles, provider evidence, and controlled release-year tolerance.
- Preserved accepted movie identity when provider enrichment is missing, unavailable, or incomplete.
- Grouped duplicate copies by shared strong identity while refusing to merge conflicting provider IDs.
- Smart Match now keeps matching, review, apply, and rename as separate explicit operations.

### Fixed

- Prevented conflicting strong IDs or weak title-only evidence from silently replacing an accepted movie.
- Rejected stale Smart Match proposals after the underlying identity revision changes.
- Hardened metadata JSON writes and restart recovery, including repair backups for corrupt state.
- Prevented Plex tokens and sensitive provider details from appearing in returned errors.
- Kept poster and metadata overrides through provider refreshes and shared them only across conflict-safe duplicate identities.
- Prevented previously unrecorded library files from remaining invisible to metadata repair workflows.

### Notes

- Plex matching remains local and read-only: applying a match does not modify the Plex server.
- Watched applies only to owned movies; Watchlist can also contain online discovery results.
- Runtime data, local posters, configuration, caches, generated builds, and dependencies are not committed.
- `v2.6.0` remains the stable rollback point before the identity and metadata changes in this release.

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

- Removed the old Flask template UI from the public app so a missing React build can no longer show the pre-React interface.
- Updated Windows `run.bat` to bootstrap `.venv`, install Python dependencies, install frontend dependencies when needed, build React when `dist/` is missing, then start Flask.
- Flask now returns a clear setup error if the React build is missing instead of silently falling back to legacy HTML.
- Reduced false "not in library" Discover results caused by title differences between Plex and TMDB.
- Prevented Browse Indexers from timing out just by opening the tab; broad latest loading is now explicit.
- Preserved indexer rows without TMDB metadata instead of hiding them.
- Improved v2.6 metadata read-path performance by avoiding writes and TMDB fetches during normal library reads.
- Kept local resolution probing so cropped 1080p files are not mislabeled as 720p.

### Notes

- `config.json`, `data/`, `cache/`, `res_cache.json`, `node_modules/`, `dist/`, and `winapp/` are not part of the committed release.
- Windows users can use `run.bat` to install dependencies and build the React frontend from a source ZIP or fresh clone.
- Manual setup users should run `npm install` and `npm run build` after checkout because built frontend assets are generated locally.
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
