# Cinema Paradiso

> **Local-first movie archive command console** for Plex collectors, large Windows libraries, TMDB discovery, Prowlarr source search, and local Ollama recommendations.

Cinema Paradiso is a self-hosted movie library manager for people with hundreds or thousands of local movie files. It helps you browse what you own, clean duplicates and low-quality copies, fix unmatched metadata, discover movies online, search torrent indexers, stream titles, and ask a local AI curator what to watch.

Everything runs on your machine. No cloud account. No subscription. No remote database.

**Current version: v2.6.0** - June 2026

---

## Screenshots

### Home Command Center

![Cinema Paradiso Home](screenshots/react-home-desktop.png)

### Library Movie View

![Library Movie View](screenshots/react-library-movie-view.png)

### Library File View

![Library File View](screenshots/react-library-file-view.png)

### Discover Movies

![Discover Movies](screenshots/react-discover-desktop.png)

### Browse Indexers

![Browse Indexers](screenshots/react-discover-browse-loaded.png)

### Styleguide

![Cinema Paradiso Styleguide](screenshots/styleguide-page-wide.png)

---

## What Changed in v2.6

Cinema Paradiso v2.6 is the current stable baseline for the React/Vite movie archive console. It includes the black/gold interface, the redesigned Home/Library/Cleanup/Discover/Settings workspaces, and the newer metadata architecture that makes Plex optional instead of mandatory for rich local library browsing.

- New app metadata layer stores file facts, Plex metadata, TMDB metadata, manual matches, and conflicts separately under user data.
- Movie View now shows files with accepted Plex or TMDB metadata, while File View remains the complete local-file management view.
- Cleanup now uses **Unmatched Metadata** instead of Plex-only unmatched handling, with TMDB search/apply, optional Plex matching, rename, fix-path, and refresh workflows.
- Plex remains supported and read-only by default, but TMDB can now enrich local library files and provide canonical movie identity.
- Discover/Home ownership matching now prefers stable IDs such as TMDB/IMDb before title/year fallback, reducing false "not in library" results.
- Discover adds TMDB vote-count preservation and minimum vote filters so low-confidence ratings can be filtered out.
- Browse Indexers now loads Prowlarr indexer sources before search/load and can scope searches or latest feeds to one selected indexer such as YTS.
- Browse Indexers renders raw Prowlarr rows first and enriches TMDB details progressively, so cards are not hidden just because TMDB metadata is missing.
- Home release watchlist remains compact, supports a full list view, checks for proper WEB/Blu-ray releases, ignores CAM/TS/HDCAM/screener copies, and removes movies once they are owned locally.
- Library keeps 40-item pagination, local title-first search ranking, simplified resolution buckets, real stream-resolution probing, user lists, edited collections, cast/director filters, trailers, and archive-aware actions.
- Settings manages library roots, user data, cache folders, and optional Plex, Prowlarr, TMDB, and Ollama integrations.

---

## Core Workspaces

### Home

The Home page is the command center. It shows library health, followed release alerts, trending movies, and a selected movie detail panel. The release watchlist is intentionally compact: the Home widget shows only slim rows, while `View all` opens the full followed list.

### Library

Library is the offline archive browser.

- **Movie View:** for choosing what to watch from files with accepted metadata.
- **File View:** for managing every local video file, including files without accepted metadata.
- Filters include quality, resolution bucket, source, genre, language, country, year, rating, Plex state, and size.
- Actions include Play, Find Sources, Find Upgrade, Trailer, Rename, Delete, Add to List, and collection/list filtering.

### Cleanup

Cleanup is the safe maintenance area for local files.

- Duplicates
- Smart Clean recommendations
- Low-quality files
- Unmatched Metadata fixes
- Rename, Fix Path, TMDB match, optional Plex match, source search, and Recycle Bin delete flows

Destructive actions are explicit and confirmed. Delete defaults to the Windows Recycle Bin.

### Discover

Discover is the online activity area.

- **Explore Movies:** TMDB lists, genres, search, trailers, stream, sources.
- **Browse Indexers:** Prowlarr latest/search results with selectable indexer source, resolution, seeders, size, and torrent/magnet/page links.
- **Pick My Movie:** local Ollama recommendations enriched with TMDB metadata and archive-aware actions.

### Settings

Settings manages:

- Movie library folders
- User data folder
- TMDB cache folder
- Plex URL/token
- Prowlarr URL/API key
- TMDB API key
- Ollama URL/model

User lists, edited collections, followed releases, and manual metadata matches are persistent user data. TMDB detail caches are rebuildable cache.

---

## Requirements

- Windows 10/11
- Python 3.10+
- Node.js 18+ for building the React frontend
- Optional: Plex Media Server
- Optional: Prowlarr
- Optional: TMDB API key
- Optional: Ollama

---

## Installation

### Windows Quick Start

Download the source ZIP or clone the repository, then double-click `run.bat`.

The launcher creates `.venv`, installs Python dependencies, installs frontend dependencies, builds the React app when `dist/` is missing, starts Flask, and opens [http://localhost:5000](http://localhost:5000).

### Manual Setup

```bash
git clone https://github.com/dantebagera/cinema-paradiso.git
cd cinema-paradiso
pip install -r requirements.txt
npm install
npm run build
```

Then start the Flask app:

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000).

---

## Configuration

Settings are saved in `config.json`, which is intentionally ignored by git.

Example:

```json
{
  "movies_dir": "E:\\Movies",
  "movies_dirs": ["E:\\Movies", "F:\\Archive"],
  "plex_url": "http://localhost:32400",
  "plex_token": "your-token",
  "prowlarr_url": "http://localhost:9696",
  "prowlarr_key": "your-api-key",
  "tmdb_key": "your-tmdb-key",
  "ollama_url": "http://localhost:11434",
  "ollama_model": "llama3",
  "user_data_dir": "C:\\Path\\To\\CinemaParadiso\\data",
  "tmdb_cache_dir": "C:\\Path\\To\\CinemaParadiso\\cache"
}
```

Only a movie library folder is required. Integrations are optional.

---

## Local Data and Cache

The app separates persistent user data from rebuildable cache:

- `data/` stores user lists, edited collections, followed releases, and app metadata records for files, manual matches, Plex metadata, TMDB metadata, and conflicts.
- `cache/` stores rebuildable TMDB detail/collection cache.
- `res_cache.json` stores local resolution probe cache.
- `config.json` stores local settings and secrets.

These files are user-specific and should not be committed.

---

## Safety

- File deletes default to Windows Recycle Bin via `send2trash`.
- Permanent deletion is treated as dangerous and must be explicit where exposed.
- File operations are restricted to configured movie library roots.
- Cleanup workflows show paths and affected files before action.

---

## Tech Stack

- **Backend:** Python, Flask
- **Frontend:** React 19, Vite, CSS custom properties
- **Icons:** Lucide React
- **Metadata:** Plex API, TMDB API
- **Source search:** Prowlarr API
- **AI:** Ollama local chat API
- **Resolution probing:** pymediainfo
- **Delete safety:** send2trash

Cinema Paradiso v2.6 uses the React frontend as the only public interface.

---

## Development

Run the frontend dev server:

```bash
npm run dev
```

Build the frontend for Flask:

```bash
npm run build
```

Run the Flask backend:

```bash
python app.py
```

Basic verification:

```bash
python -m py_compile app.py
python -m unittest discover -s tests -p "test_*.py"
node --test tests/discoverUtils.test.mjs
npm run build
```

---

## License

MIT
