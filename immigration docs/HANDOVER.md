# FilebotX — Full Developer Handover

> **Purpose:** Complete handover document for continuing development of this project in Codex or any new environment.
> **Date:** June 2026 · **Current Version:** v1.5

---

## 1. What This App Is

**FilebotX** (also called "My Library Organizer" / "10K Movie Library Organizer") is a **self-hosted, local Windows web application** for managing, cleaning, and organising a large Plex movie library.

- Built with **Python + Flask** (backend) and **vanilla HTML/CSS/JS** (frontend — no framework).
- Runs entirely on the user's machine — no cloud, no accounts, no data leaves the PC.
- Designed for libraries with **thousands of files** (tested with 10,000+).
- Has two deployment modes: **dev server** (run `run.bat`) and **packaged Windows EXE** (pywebview + PyInstaller, built via `winapp/build.bat`).

---

## 2. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Backend | Python 3.10+ · Flask 3.x | Single file: `app.py` |
| Frontend | Vanilla HTML + CSS + JS | Single template: `templates/index.html` |
| File deletion | `send2trash` | Sends to Recycle Bin by default |
| Media probing | `pymediainfo` | Reads actual video resolution when filename has none |
| Plex API | urllib (no SDK) | XML/JSON REST calls to local Plex Media Server |
| Prowlarr API | urllib (no SDK) | REST calls to local Prowlarr instance |
| TMDB API | urllib (no SDK) | Free TMDB v3 API |
| Windows EXE | pywebview + PyInstaller | `winapp/` folder |
| Installer | Inno Setup 6 | `winapp/installer/` folder |

**Dependencies** (`requirements.txt`):
```
flask>=3.0.0
send2trash>=1.8.0
pymediainfo>=6.0.0
```

**winapp dependencies** (`winapp/requirements.txt`) also include:
```
pywebview>=4.4.1
pyinstaller>=6.0.0
```

---

## 3. Project File Structure

```
filebotx/
├── app.py                  ← ENTIRE backend (Flask routes + all logic)
├── config.json             ← User settings (auto-created, git-ignored)
├── res_cache.json          ← Resolution probe cache (auto-created)
├── requirements.txt        ← Python deps for dev server
├── run.bat                 ← One-click dev server launcher
├── Agent.md                ← Instructions for AI agents working on this repo
│
├── templates/
│   └── index.html          ← ENTIRE frontend (HTML + CSS + JS — all inline)
│
├── static/                 ← Static assets (logo, CSS if any)
│
├── context/                ← AI agent context files (see Section 10)
│   ├── project-overview.md
│   ├── architecture.md
│   ├── ui-context.md
│   ├── code-standards.md
│   ├── ai-workflow-rules.md
│   └── progress-tracker.md
│
├── winapp/                 ← Windows EXE build (separate deployable)
│   ├── app.py              ← Copy of main app.py (keep in sync)
│   ├── main.py             ← Desktop entry point (pywebview wrapper)
│   ├── build.bat           ← Full build script (PyInstaller + Inno Setup)
│   ├── filebotx.spec       ← PyInstaller spec file
│   ├── requirements.txt    ← Includes pywebview + pyinstaller
│   ├── assets/             ← icon.ico etc.
│   ├── installer/          ← Inno Setup .iss script
│   ├── static/             ← Mirrored static/
│   ├── templates/          ← Mirrored templates/
│   └── tools/              ← make_icon.py etc.
│
└── immigration docs/       ← This handover folder
```

**Critical rule (current policy):** Do NOT touch or update the `winapp/` folder during active development. All new features are built in the root `app.py` and `templates/index.html` only. The winapp sync will be done in a single pass before the next EXE build — not after every change.

---

## 4. How to Run (Development)

```bat
# Windows — double-click or run:
run.bat
```

This starts Flask on `http://localhost:5000` and opens the browser automatically.

**Manual start:**
```bash
python app.py
```

**With virtual environment:**
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

---

## 5. How to Build the Windows EXE

```bat
cd winapp
build.bat
```

Output: `winapp/dist/LibraryOrganizer/LibraryOrganizer.exe`

If Inno Setup 6 is installed, the script also builds a full Windows installer at `winapp/dist/LibraryOrganizer_Setup.exe`.

The `winapp/main.py` entry point:
1. Starts Flask in a background daemon thread on port 5000
2. Polls localhost until Flask responds (up to 15 seconds)
3. Opens a native `pywebview` window pointing at `http://localhost:5000`
4. Closing the window exits the process

**Data directory when frozen:** `%APPDATA%\10KMovieLibrary\` (config.json, res_cache.json stored here, not next to the EXE).

---

## 6. Configuration

Stored in `config.json` (next to `app.py` in dev, in `%APPDATA%\10KMovieLibrary\` when packaged):

```json
{
  "movies_dir": "E:\\Movies",
  "prowlarr_url": "http://localhost:9696",
  "prowlarr_key": "YOUR_PROWLARR_API_KEY",
  "plex_url": "http://localhost:32400",
  "plex_token": "YOUR_PLEX_TOKEN",
  "tmdb_key": "YOUR_TMDB_API_KEY"
}
```

| Field | Default | Description |
|---|---|---|
| `movies_dir` | `E:\Movies` | Root folder scanned for video files |
| `prowlarr_url` | `""` | Prowlarr base URL |
| `prowlarr_key` | `""` | Prowlarr API key (Settings → General) |
| `plex_url` | `http://localhost:32400` | Plex Media Server URL |
| `plex_token` | `""` | X-Plex-Token from Plex account |
| `tmdb_key` | `""` | TMDB v3 API key (free at themoviedb.org) |

Config is loaded once at startup into module globals (`_movies_dir`, `_prowlarr_url`, etc.) and re-saved via `_save_config()` whenever Settings are updated through the UI.

---

## 7. All API Endpoints

### Config & Settings

| Method | Route | Description |
|---|---|---|
| GET | `/api/config` | Get current movies directory |
| POST | `/api/config` | Set movies directory |
| GET | `/api/prowlarr/config` | Get Prowlarr URL + key |
| POST | `/api/prowlarr/config` | Set Prowlarr URL + key |
| GET | `/api/prowlarr/test` | Test Prowlarr connection |
| GET | `/api/plex/config` | Get Plex URL + token |
| POST | `/api/plex/config` | Set Plex URL + token |
| GET | `/api/plex/test` | Test Plex connection |
| GET | `/api/tmdb/config` | Get TMDB key |
| POST | `/api/tmdb/config` | Set TMDB key |
| GET | `/api/tmdb/test` | Test TMDB key |
| GET | `/api/ollama/config` | Get Ollama URL + model name |
| POST | `/api/ollama/config` | Set Ollama URL + model name |
| GET | `/api/ollama/test` | Test Ollama reachability |

### Library

| Method | Route | Description |
|---|---|---|
| GET | `/api/library` | Full library listing (all video files + metadata) |
| GET | `/api/library/status` | Live scan status string (polled during scan) |
| GET | `/api/stats` | Dashboard statistics (resolution breakdown, decades, etc.) |
| GET | `/api/duplicates` | All duplicate groups |
| GET | `/api/low-quality` | All files below 1080p |
| GET | `/api/smart-scan` | Auto-recommendations for which duplicate copies to delete |
| GET | `/api/fix-unmatched` | Files not matched in Plex |

All scan endpoints accept `?force_plex=1` to force a Plex cache refresh before scanning.

### File Operations

| Method | Route | Description |
|---|---|---|
| POST | `/api/delete` | Delete/trash a file |
| POST | `/api/open-file` | Open a file in its default application |
| POST | `/api/rename-file` | Rename a file (title + year → clean filename) |
| POST | `/api/fix-path` | Move a deep-nested file up one level for Plex |

`/api/delete` body: `{ "path": "...", "trash": true }` — `trash: true` sends to Recycle Bin (default), `trash: false` permanently deletes.

**Security:** Both `/api/delete` and `/api/rename-file` and `/api/fix-path` validate that the path is inside the configured `movies_dir` before doing anything.

### Plex

| Method | Route | Description |
|---|---|---|
| GET | `/api/plex/sync` | Force re-fetch Plex library into cache |
| POST | `/api/plex/force-scan` | Trigger Plex library rescan (all movie sections) |
| GET | `/api/plex/image?url=` | Proxy Plex poster images (avoids CORS) |
| GET | `/api/plex/match-search` | Search for Plex metadata matches for a file |
| POST | `/api/plex/match-apply` | Apply a Plex metadata match to a file |

### Prowlarr / Torrents

| Method | Route | Description |
|---|---|---|
| GET | `/api/prowlarr/search?q=` | Search all Prowlarr indexers (all resolutions) |
| GET | `/api/explore/browse` | Latest movies from all Prowlarr indexers (deduplicated) |
| GET | `/api/explore/search?title=&year=` | Find all 1080p+/4K torrents for a specific title |

### TMDB

| Method | Route | Description |
|---|---|---|
| GET | `/api/tmdb/discover?list=&genre=&page=` | Browse TMDB curated lists |
| GET | `/api/tmdb/search?q=&page=` | Full TMDB text search |
| GET | `/api/metadata?title=&year=` | TMDB metadata lookup (cached in memory) |
| GET | `/api/tmdb/details?tmdb_id=` | TMDB cast/trailer details for expanded React movie cards |
| GET | `/api/tmdb/imdb_id?tmdb_id=` | Look up IMDB ID from TMDB ID (used for streaming) |

**TMDB discover lists:** `trending_week`, `trending_today`, `now_playing`, `popular`, `upcoming`, `top_rated`, `best_all_time`

### Ollama / Pick My Movie

| Method | Route | Description |
|---|---|---|
| POST | `/api/ollama/recommend` | Send a movie description prompt → returns 5 AI recommendations enriched with TMDB |
| POST | `/api/library/check` | Check which of a list of `{title, year}` movies exist in the local library |

`/api/ollama/recommend` body: `{ "prompt": "..." }`. Response: `{ "results": [{title, year, reason, poster_url, genres, tmdb_rating, plot, tmdb_id}], "model": "..." }`

`/api/library/check` body: `{ "movies": [{"title": "...", "year": "..."}] }`. Response: `{ "results": [{"title": "...", "year": "...", "found": bool, "path": "...", "resolution": "...", "size_human": "..."}] }`. Matching uses Plex title+year (preferred) then filename-parsed title, both normalised (lowercase, no punctuation, no leading article). Returns `found: false` gracefully when `movies_dir` is not configured.

---

## 8. Data Models

### Video File Object (used in library, duplicates, low-quality)

```json
{
  "title": "The Dark Knight (2008)",
  "filename": "The.Dark.Knight.2008.1080p.BluRay.mkv",
  "path": "E:\\Movies\\The Dark Knight (2008)\\The.Dark.Knight.2008.1080p.BluRay.mkv",
  "resolution": "1080p",
  "resolution_rank": 3,
  "rip_source": "Blu-ray",
  "rip_rank": 7,
  "size": 8589934592,
  "size_human": "8.0 GB",
  "plex_title": "The Dark Knight",
  "plex_year": "2008",
  "plex_genres": ["Action", "Crime", "Drama"],
  "plex_matched": true
}
```

### Resolution Rankings

| Resolution | Rank |
|---|---|
| 4K | 4 |
| 1080p | 3 |
| 720p | 2 |
| 480p | 1 |
| Unknown | 0 |

### Rip Source Rankings

| Source | Rank |
|---|---|
| BD Remux | 9 |
| Remux | 8 |
| Blu-ray | 7 |
| BDRip | 6 |
| WEB-DL | 5 |
| WEBRip | 4 |
| HDRip | 3 |
| HDTV | 2 |
| DVDRip | 1 |
| DVDScr | 0 |
| CAMRip | -1 |
| HDCAM | -2 |
| Unknown | -3 |

### res_cache.json

Persists resolution probe results (from pymediainfo) across app restarts:

```json
{
  "E:\\Movies\\somefile.mkv": {
    "mtime": 1506898115.9274473,
    "res": "480p"
  }
}
```

Key: full absolute file path  
Value: `{ mtime: float (os.path.getmtime), res: "4K" | "1080p" | "720p" | "480p" | "Unknown" }`

The in-memory cache key is `(abspath, mtime)` — a tuple. The file on disk uses the path as a string key.

### Plex Cache Structures (in-memory only)

```python
_plex_cache              # _norm(file_path) → {plex_title, plex_year, plex_genres, plex_summary, plex_rating, plex_thumb}
_plex_unmatched          # _norm(file_path) → {rating_key, plex_title}   (in Plex but no metadata match)
_plex_matched_by_fname   # filename.lower() → matched entry              (fallback for path-mismatch cases)
_plex_unmatched_by_fname # filename.lower() → unmatched entry            (fallback)
_plex_section_ids        # list of movie section keys (for triggering rescans)
```

Auto-refresh every 300 seconds (5 min) via `_auto_sync_plex()`. Forced by `?force_plex=1`.

### TMDB Discover Movie Card Object

```json
{
  "tmdb_id": 155,
  "title": "The Dark Knight",
  "year": "2008",
  "poster_url": "https://image.tmdb.org/t/p/w342/...",
  "genres": ["Action", "Crime", "Drama"],
  "tmdb_rating": "9.0",
  "plot": "Batman raises the stakes...",
  "language": "English",
  "country": "US",
  "country_flag": "🇺🇸"
}
```

### Explore Browse Result Object

```json
{
  "parsed_title": "Oppenheimer",
  "parsed_year": "2023",
  "best_seeders": 1250,
  "best_resolution": "4K",
  "indexer": "YTS",
  "variants": [
    {
      "resolution": "4K",
      "seeders": 1250,
      "magnet_url": "magnet:?xt=...",
      "download_url": "https://...",
      "info_url": "https://...",
      "indexer": "YTS",
      "size_human": "14.2 GB",
      "title": "Oppenheimer.2023.4K.UHD.BluRay..."
    }
  ]
}
```

---

## 9. Core Backend Functions

| Function | Description |
|---|---|
| `parse_movie_title(filename)` | Returns `(title, year)` tuple parsed from filename |
| `get_resolution(filename)` | Returns resolution string from filename tags |
| `get_resolution_from_file(filepath)` | Resolution from filename; falls back to pymediainfo probe |
| `get_rip_source(filename)` | Returns rip source string from filename |
| `get_resolution_rank(filename)` | Returns numeric resolution rank (0–4) |
| `get_rip_rank(rip_source)` | Returns numeric rip quality rank |
| `format_size(size)` | Formats bytes as human-readable string |
| `scan_duplicates(movies_dir)` | Returns `(duplicates[], stats{})` — groups files by title+year |
| `_probe_resolution(filepath)` | Uses pymediainfo to read actual video dimensions |
| `_load_res_cache()` | Loads `res_cache.json` into `_res_cache` at startup |
| `_save_res_cache()` | Persists `_res_cache` to `res_cache.json` |
| `_auto_sync_plex(force=False)` | Refreshes Plex cache if stale (>5 min) |
| `_fetch_plex_library()` | Full Plex library fetch — returns all 4 cache dicts + section_ids |
| `_plex_rescan()` | Triggers Plex library refresh on all movie sections |
| `_ensure_tmdb_genres()` | Lazy-loads TMDB genre list into `_tmdb_genres` dict |
| `_norm(path)` | `os.path.normcase(os.path.normpath(path))` — used as cache key |
| `_load_config()` | Reads `config.json` |
| `_save_config(data)` | Writes `config.json` |
| `_all_config()` | Returns dict of all config values for saving |

---

## 10. Frontend Architecture

### React/Vite Migration Note (June 2026)

The new UI redesign has started a React/Vite frontend migration at the repo root:

- `package.json`, `vite.config.js`, `index.html`, and `src/` define the new React frontend.
- `npm.cmd run build` outputs the production frontend to `dist/`.
- The Flask `/` route serves `dist/index.html` when it exists.
- The original single-file Flask template remains available at `/legacy` during migration.
- `templates/index.html` is still the legacy interface and should not be deleted until all panels have been rebuilt in React.
- `winapp/` remains out of scope during active web development.

Current React phase 1 scope:

- New grouped app shell: Home, Library, Cleanup, Discover, Settings.
- Home command center with library health, release watchlist, wide smart movie cards, and a right-side movie inspector.
- Smart movie cards keep Play as the primary action for owned movies; Find Upgrade is secondary when local quality is low.
- Expanded movie details load readable plot, cast, and official YouTube trailer data via `/api/tmdb/details`.

Legacy details below describe the old single-template UI and are still relevant for functionality that has not yet migrated.

The entire frontend lives in **one file: `templates/index.html`**. It contains:
- All HTML structure
- All CSS (inline `<style>` blocks)
- All JavaScript (inline `<script>` blocks)
- No external JS or CSS frameworks (no jQuery, no React, no Tailwind)

### Layout Structure (v1.7 — Sidebar)

The body is a **flex row**:
- `<nav class="sidebar">` — fixed 220px left sidebar (logo + nav + settings)
- `<div class="app-content">` — flex-1 scrollable column (all page content)

The sidebar contains:
- `.sidebar-logo` — logo image + "Cinema / Paradiso" two-line wordmark
- `.sidebar-nav` — scrollable list of `.nav-item` buttons (all features)
- `.sidebar-footer` — Settings button pinned at bottom

Each nav button has: `<span class="nav-icon">` + `<span class="nav-label">`
The scan button's label span has `id="scan-btn-label"` so JS can update its text without clobbering the icon.

Inside `.app-content` (top to bottom):
- `#plex-loading-bar` — Plex sync spinner bar
- `#stats-bar` — scan result summary (hidden until scan completes)
- `#trash-toggle-wrap` — delete mode toggle
- `#search-wrap` — search input
- `<main>` — main content area
  - `#status-bar` — home screen (cinematic hero + 8 feature cards) OR scan spinner
  - `#results` — duplicate group cards (shown after scan)

All full-screen overlay panels (Library, Dashboard, Explore, Pick My Movie, Unmatched, Smart Clean, Low Quality) sit **outside** `.app-content` and use `position: fixed; inset: 0` — they cover the full viewport including the sidebar.

### Panel / ID Reference

| Panel | Description |
|---|---|
| Sidebar | `.sidebar` — 220px left nav |
| Home screen | `#status-bar` with `.home-hero` + `.home-cards` |
| Dashboard | Library stats with inline SVG charts |
| Duplicate Scanner | Table of duplicate groups; Smart Clean tab |
| Low Quality Scanner | Table of sub-1080p files |
| Library Browser | Full virtual-scroll table of all files |
| Unmatched Panel | Files Plex can't find; Fix Path / Rename / Match actions |
| Explore Torrents | Full-screen modal: TMDB Discover tab + Browse Indexers tab + global search |

### Key HTML IDs

| ID | Element |
|---|---|
| `#scan-btn-label` | `<span>` inside scan sidebar button (for JS text updates) |
| `#explore-panel` | Explore Torrents full-screen modal |
| `#explore-search-input` | Global TMDB search input |
| `#explore-search-grid` | Search results grid |
| `#explore-tab-discover` | TMDB Discover tab content |
| `#explore-tab-browse` | Browse Indexers tab content |
| `#discover-grid` | Discover cards grid |
| `#browse-grid` | Browse cards grid |
| `#tab-btn-discover` | Discover tab button |
| `#tab-btn-browse` | Browse tab button |
| `#browse-filter-res` | Resolution filter dropdown |
| `#browse-filter-idx` | Indexer filter dropdown |
| `#browse-sort` | Sort dropdown |
| `#discover-list-sel` | TMDB list selector |
| `#discover-genre-sel` | Genre filter |

### Key CSS Classes

| Class | Usage |
|---|---|
| `.sidebar` | Left nav container |
| `.nav-item` | Sidebar button (all nav items) |
| `.nav-icon` | Icon span inside nav button |
| `.nav-label` | Label span inside nav button |
| `.app-content` | Scrollable main content wrapper |
| `.home-hero` | Cinematic headline section on home screen |
| `.home-cards` | CSS grid of 8 feature cards |
| `.home-card` | Individual feature card |
| `.home-card-accent-bar` | 2px coloured top bar on each card |
| `.tr-card` | Movie card (both Discover and Browse) |
| `.tr-poster-wrap` | Card poster image container |
| `.tr-res-badge` | Resolution badge (`.tr-res-4K`, `.tr-res-1080p`, etc.) |
| `.tr-card-body` | Card text content area |
| `.tr-title` | Card title |
| `.tr-year` | Card year |
| `.tr-genres` | Genre tags container |
| `.tr-genre-tag` | Individual genre pill |
| `.tr-rating-row` | TMDB rating row |
| `.tr-tmdb-score` | TMDB star rating badge |
| `.tr-plot` | Plot text (expandable with `.expanded`) |
| `.tr-plot-toggle` | ▾ more / ▴ less toggle button |
| `.tr-variants` | Resolution variant pills (Browse only) |
| `.tr-footer` | Card footer (seeders, indexer, size, action buttons) |
| `.explore-grid` | Card grid layout |
| `.explore-tab-btn` | Tab button (`.active` = orange underline) |

### Key JS Functions

| Function | Description |
|---|---|
| `scanMovies()` | Triggers duplicate scan; updates `#scan-btn-label` text |
| `openExplore()` | Opens Explore Torrents panel |
| `closeExplore()` | Closes Explore Torrents panel |
| `switchExploreTab(tab)` | Switches between `'discover'` and `'browse'` |
| `loadBrowse()` | Fetches `/api/explore/browse` and renders cards |
| `applyBrowseFilters()` | Filters browse grid by resolution/indexer/sort |
| `renderBrowseCards(results)` | Renders browse grid from data |
| `selectBrowseVariant(movieIdx, variantIdx)` | Switches which resolution variant is active |
| `loadBrowseMetadata(results)` | Async TMDB poster/rating load for browse cards |
| `loadDiscover()` | Fetches `/api/tmdb/discover` and renders cards |
| `loadDiscoverMore()` | Loads next page for discover |
| `renderDiscoverCards(results)` | Renders discover grid |
| `searchExplore()` | Runs global TMDB search |
| `loadSearchMore()` | Loads next page for search |
| `clearExploreSearch()` | Clears search and returns to tab view |
| `openTorrentModal(title, year)` | Opens Find Torrent modal for a movie |
| `closeTorrentModal()` | Closes torrent modal |
| `streamMovie(tmdbId)` | Opens playimdb.com in new tab |
| `togglePlot(el)` | Expands/collapses plot text |

### Key HTML IDs

| ID | Element |
|---|---|
| `#explore-panel` | Explore Torrents full-screen modal |
| `#explore-search-input` | Global TMDB search input |
| `#explore-search-grid` | Search results grid |
| `#explore-tab-discover` | TMDB Discover tab content |
| `#explore-tab-browse` | Browse Indexers tab content |
| `#discover-grid` | Discover cards grid |
| `#browse-grid` | Browse cards grid |
| `#tab-btn-discover` | Discover tab button |
| `#tab-btn-browse` | Browse tab button |
| `#browse-filter-res` | Resolution filter dropdown |
| `#browse-filter-idx` | Indexer filter dropdown |
| `#browse-sort` | Sort dropdown |
| `#discover-list-sel` | TMDB list selector |
| `#discover-genre-sel` | Genre filter |

### Key CSS Classes

| Class | Usage |
|---|---|
| `.tr-card` | Movie card (both Discover and Browse) |
| `.tr-poster-wrap` | Card poster image container |
| `.tr-res-badge` | Resolution badge (`.tr-res-4K`, `.tr-res-1080p`, etc.) |
| `.tr-card-body` | Card text content area |
| `.tr-title` | Card title |
| `.tr-year` | Card year |
| `.tr-genres` | Genre tags container |
| `.tr-genre-tag` | Individual genre pill |
| `.tr-rating-row` | TMDB rating row |
| `.tr-tmdb-score` | TMDB star rating badge |
| `.tr-plot` | Plot text (expandable with `.expanded`) |
| `.tr-plot-toggle` | ▾ more / ▴ less toggle button |
| `.tr-variants` | Resolution variant pills (Browse only) |
| `.tr-footer` | Card footer (seeders, indexer, size, action buttons) |
| `.explore-grid` | Card grid layout |
| `.explore-tab-btn` | Tab button (`.active` = orange underline) |

### Key JS Functions

| Function | Description |
|---|---|
| `openExplore()` | Opens Explore Torrents panel |
| `closeExplore()` | Closes Explore Torrents panel |
| `switchExploreTab(tab)` | Switches between `'discover'` and `'browse'` |
| `loadBrowse()` | Fetches `/api/explore/browse` and renders cards |
| `applyBrowseFilters()` | Filters browse grid by resolution/indexer/sort |
| `renderBrowseCards(results)` | Renders browse grid from data |
| `selectBrowseVariant(movieIdx, variantIdx)` | Switches which resolution variant is active |
| `loadBrowseMetadata(results)` | Async TMDB poster/rating load for browse cards |
| `loadDiscover()` | Fetches `/api/tmdb/discover` and renders cards |
| `loadDiscoverMore()` | Loads next page for discover |
| `renderDiscoverCards(results)` | Renders discover grid |
| `searchExplore()` | Runs global TMDB search |
| `loadSearchMore()` | Loads next page for search |
| `clearExploreSearch()` | Clears search and returns to tab view |
| `openTorrentModal(title, year)` | Opens Find Torrent modal for a movie |
| `closeTorrentModal()` | Closes torrent modal |
| `streamMovie(tmdbId)` | Opens playimdb.com in new tab |
| `togglePlot(el)` | Expands/collapses plot text |

---

## 11. Colour Palette & UI Theme

The app uses a **dark cinematic theme** ("Cinema Paradiso"):

| Role | Value | Used for |
|---|---|---|
| Page / sidebar background | `#0a0a10` | Body + sidebar + app-content background |
| Sidebar border | `#1c1c28` | Sidebar right border, dividers |
| Card surface | `#10101e` | Home screen feature cards |
| Card border | `#1c1c2e` | Home screen card borders |
| Primary text | `#e5e5e5` | Body text |
| Muted / nav default | `#555` | Inactive nav items, secondary labels |
| Gold accent | `#fdcb6e` | Logo accent, scan button highlight, home hero |
| Orange accent | `#e5a00d` | Low Quality highlight, accent gradient |
| Green accent | `#2ecc71` | Smart Clean button |
| Blue accent | `#74b9ff` | Library Browser |
| Pink accent | `#fd79a8` | Dashboard |
| Purple accent | `#a29bfe` | Unmatched / Pick My Movie |
| Error | `#e74c3c` | Error messages |
| Cyan | `#00cec9` | Plex integration elements |

> The `#settings-dropdown` is positioned `bottom: 20px; left: 228px` — adjacent to the bottom of the sidebar.

---

## 12. Security Controls

These are implemented and must not be removed:

1. **Path traversal prevention:** `/api/delete`, `/api/rename-file`, and `/api/fix-path` all call `os.path.abspath()` and verify the result starts with the configured `movies_dir` before doing anything.

2. **Plex image proxy:** `/api/plex/image` only proxies URLs that start with the configured `_plex_url` — rejects all other origins with 403.

3. **File-only deletion:** `/api/delete` can only delete individual files — not directories.

4. **Fix-path boundaries:** `/api/fix-path` verifies the destination (grandparent or great-grandparent) is still inside the library root.

---

## 13. Known Quirks & Important Behaviours

### Duplicate Scanning
- Uses **Plex metadata title+year** as the grouping key when available (more accurate than filename parsing).
- **Plex bulk-mismatch guard:** If Plex has assigned more than 4 files to the same title+year key, it assumes Plex mis-tagged an entire folder. Those files fall back to filename-based grouping.
- Files are ranked: resolution rank first, then rip source rank, then file size — highest wins.
- Smart Clean only auto-flags a copy if it's clearly inferior **and** safe (5% size-difference threshold for same-resolution/different-source cases).

### Resolution Detection
1. Checks filename tags first (fast).
2. If filename shows `Unknown`, probes with pymediainfo (slow but accurate).
3. Results cached in `res_cache.json` keyed by `(abspath, mtime)` — cache is invalidated automatically when the file changes.

### Plex Cache
- Auto-syncs every 5 minutes (300s TTL).
- Forced by `?force_plex=1` on any scan endpoint.
- Path-mismatch fallback: if a full-path lookup misses, falls back to filename-only lookup (handles drive-letter case differences, path changes).

### Library Cache
- The `/api/library` endpoint caches the full file list for 300 seconds.
- Cache is busted immediately when a file is deleted, renamed, or the movies directory is changed.

### TV Episode Filtering
- Browse/search results filter out TV episodes using `_TV_RE` regex before processing torrents.

### Fix Path Logic
- If a file is in a folder with exactly one video file AND the folder name contains a year (looks like a movie title), it moves the **entire folder** up one level (preserves the Plex metadata hint).
- Otherwise it moves just the file.

---

## 14. winapp (Windows EXE Build)

The `winapp/` folder is a **self-contained copy** of the app with an additional desktop entry point.

### Key difference from dev server
- `winapp/main.py` launches Flask in a background thread then opens a `pywebview` window.
- When packaged, data files (`config.json`, `res_cache.json`) are stored in `%APPDATA%\10KMovieLibrary\` not next to the EXE.
- `_FROZEN = getattr(sys, 'frozen', False)` flag controls which paths are used.

### Build process
```
winapp/build.bat
```
1. Installs all pip dependencies.
2. Checks for `assets/icon.ico` (generate with `winapp/tools/make_icon.py` from `static/logo.svg`).
3. Runs PyInstaller with `filebotx.spec`.
4. If Inno Setup 6 is installed, builds a full Windows installer.

### Keeping winapp in sync
Any change to `app.py` or `templates/index.html` must also be applied to `winapp/app.py` and `winapp/templates/index.html` before building.

---

## 15. Context Files (for AI agents)

The `context/` folder is designed for AI coding assistants. Read these files before making architectural changes:

| File | Contents |
|---|---|
| `context/project-overview.md` | Template (not filled in) — see README.md instead |
| `context/architecture.md` | Template (not filled in) — see this document |
| `context/ui-context.md` | Template (not filled in) — real theme is in `templates/index.html` |
| `context/code-standards.md` | Template (not filled in) |
| `context/ai-workflow-rules.md` | Template workflow rules |
| `context/progress-tracker.md` | Template (not filled in) — update this after each session |

> **Note for Codex:** All `context/` files are unfilled templates. The real documentation is this handover document and `README.md`.

The `Agent.md` file at the repo root tells AI agents to read all context files in order before implementing anything.

---

## 16. Current State (June 2026)

### Fully Implemented Features (v1.7 — Cinema Paradiso)

- ✅ **Cinema Paradiso v1.7 — Cinematic UI Redesign:**
  - ✅ App renamed from "My Library Organizer" / "FilebotX" → **Cinema Paradiso**
  - ✅ Top header button bar replaced with **fixed left sidebar navigation** (220px)
  - ✅ Sidebar: logo wordmark ("Cinema / Paradiso" two-line gold), icon+label nav items with per-feature accent hover colours
  - ✅ Home screen (`#status-bar`) replaced with **cinematic hero + 8 feature cards grid**
  - ✅ Each feature card: 2px colour-coded accent bar, icon badge, title, description, ghost action button
  - ✅ Deep dark background `#0a0a10` throughout; body is flex-row for sidebar + content layout
  - ✅ Settings dropdown repositioned to `bottom: 20px; left: 228px` (sidebar-adjacent)
  - ✅ JS `scanMovies()` updated to target `#scan-btn-label` span for text changes (icon preserved)
- ✅ Duplicate Scanner with Smart Clean
- ✅ Low Quality Scanner
- ✅ Library Browser with virtual scroll
- ✅ Dashboard with stats and charts
- ✅ Plex integration (sync, match, fix-path, force-scan)
- ✅ Prowlarr integration (search torrents from all panels)
- ✅ Unmatched Panel (Fix Path, Rename, Manual Match)
- ✅ Explore Torrents panel:
  - ✅ TMDB Discover tab (6 lists, 15 genre filters, Load More)
  - ✅ Browse Indexers tab (all Prowlarr indexers, deduplication, variant pills)
  - ✅ Global TMDB search
  - ✅ Find Torrent modal
  - ✅ Stream button (playimdb.com)
- ✅ Windows EXE build (pywebview + PyInstaller + Inno Setup)
- ✅ Settings panel (all integrations configurable from UI)
- ✅ **Pick My Movie** panel (v1.7):
  - ✅ Natural language / mood / memory prompt via Ollama local LLM
  - ✅ Returns 5 AI recommendations with a one-sentence reason each
  - ✅ Each recommendation enriched with TMDB (poster, genres, rating, plot)
  - ✅ Cards with purple 💡 reason badge, Find Torrent + Stream buttons
  - ✅ **"In Your Library" detection** — after picks arrive, silently fires `POST /api/library/check`; cards for owned films show a green ✓ badge (resolution + file size), a ▶ Play from HDD button, and Stream button hidden
  - ✅ Ollama settings section (URL + model name, Test + Save)
  - ✅ Config persisted: `ollama_url`, `ollama_model` in `config.json`
  - ✅ Ctrl+Enter submits prompt

### What Does Not Exist Yet

- No user authentication (by design — local only app)
- No TV show support (movies only)
- No automated download / torrent client integration (only provides magnet/torrent links)
- No subtitles management
- No scheduled tasks / background workers
- No database (everything is file-system + in-memory)

---

## 17. How to Continue Development in Codex

1. **Read this document first** — it replaces all the unfilled `context/` template files.
2. **The main files to edit are:**
   - `app.py` — all backend logic and routes
   - `templates/index.html` — all frontend (HTML + CSS + JS)
3. **Do NOT touch `winapp/`** during active development. The winapp sync happens in a dedicated pass before an EXE build is needed — not during feature work.
4. **After every completed feature, update this handover document** (`immigration docs/HANDOVER.md`) — update the Current State section (Section 16), the API endpoints table if new routes were added, and any data model or function changes.
5. **Update `context/progress-tracker.md`** with what you built (Agent.md requires this).
6. **Test by running** `python app.py` then visiting `http://localhost:5000`.

### Adding a new panel/feature

Pattern to follow:
1. Add a new Flask route in `app.py` under the appropriate section comment.
2. Add the HTML panel in `templates/index.html` following the existing panel structure.
3. Add a button/link in the header nav to open the panel.
4. Wire up the JS fetch to your new route.
5. Mirror both files to `winapp/`.

### Adding a new setting

1. Add the field to `config.json` schema (just add it — the file is plain JSON).
2. Add a module-level global in `app.py`: `_my_setting = _cfg.get('my_setting', 'default')`.
3. Add a GET/POST route pair following the `prowlarr/config` pattern.
4. Add `_my_setting` to the `_all_config()` return dict so it gets saved.
5. Add the input to the Settings panel in `templates/index.html`.

---

## 18. External Service URLs

| Service | Default Local URL | Key Location |
|---|---|---|
| Plex Media Server | `http://localhost:32400` | Plex → Settings → General → Advanced → X-Plex-Token |
| Prowlarr | `http://localhost:9696` | Prowlarr → Settings → General → API Key |
| TMDB | `https://api.themoviedb.org/3/` | Free key at themoviedb.org/settings/api |
| playimdb.com | `https://www.playimdb.com` | No key needed (streaming only) |
| Ollama | `http://localhost:11434` | No key needed — local LLM service |
