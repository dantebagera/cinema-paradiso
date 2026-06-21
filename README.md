# Cinema Paradiso

> **Local-first movie archive command console** for Plex collectors, large Windows libraries, TMDB discovery, Prowlarr source search, and local Ollama recommendations.

Cinema Paradiso is a self-hosted movie library manager for people with hundreds or thousands of local movie files. It helps you browse what you own, clean duplicates and low-quality copies, fix unmatched metadata, discover movies online, search torrent indexers, stream titles, and ask a local AI curator what to watch.

Everything runs on your machine. No cloud account. No subscription. No remote database.

**Current version: v2.6.3** - June 2026

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

## What Changed in v2.6.3

Cinema Paradiso v2.6.3 makes the local library identity the durable source of truth. Accepted movies remain accepted when Plex or TMDB is temporarily unavailable, while uncertain or conflicting matches are routed into review instead of silently changing a movie.

- **Authoritative movie identity:** accepted TMDB, Plex, and manual identities are resolved through one conflict-safe model used by Library, Discover, collections, lists, duplicates, posters, and ownership checks.
- **Safer automatic matching:** exact titles, official alternative titles, provider evidence, and small release-year differences can be handled automatically without allowing conflicting strong IDs to overwrite an accepted movie.
- **Identity Review:** Cleanup includes a dedicated review queue for uncertain matches, provider conflicts, and metadata discrepancies, with pause, resume, rescan, selection, and explicit apply controls.
- **Metadata health:** Home reports unmatched, pending, and identity-review counts, with direct links to the relevant Cleanup view.
- **Library reconciliation:** files missing from the metadata store are detected and reconciled, including files added before the current metadata checkpoint.
- **Manual metadata correction:** owned movies can have their local title and year corrected without changing Plex or renaming the movie file.
- **Durable poster editing:** choose from TMDB or Plex artwork, upload a local poster, or restore the provider default. Overrides survive metadata refreshes and apply safely to duplicate copies of the same identity.
- **Watched and Watchlist:** built-in protected lists add quick poster controls and Library filtering. Watchlist can include online movies; Watched is restricted to owned titles.
- **Safer Smart Match and Plex matching:** previews do not mutate metadata, stale proposals are rejected after identity changes, Plex tokens are kept out of errors, and manual Plex choices are stored locally without editing Plex.
- **Reliable metadata storage:** JSON writes use safer replacement and recovery behavior so interrupted writes can be repaired without demoting accepted movies.

---

## Core Workspaces

### Home

The Home page is the command center. It shows library health, unmatched and identity-review counts, followed release alerts, trending movies, and a selected movie detail panel. Health cards open the exact Cleanup queue that needs attention. The release watchlist is intentionally compact: the Home widget shows only slim rows, while `View all` opens the full followed list.

### Library

Library is the offline archive browser.

- **Movie View:** for choosing what to watch from files with accepted metadata.
- **File View:** for managing every local video file, including files without accepted metadata.
- Filters include quality, resolution bucket, source, genre, language, country, year, rating, Plex state, viewing state, and size.
- Actions include Play, Find Sources, Find Upgrade, Trailer, Rename, Delete, metadata correction, poster editing, Watched, Watchlist, Add to List, and collection/list filtering.
- A forced library scan reconciles stable files that do not yet have metadata records.

### Cleanup

Cleanup is the safe maintenance area for local files.

- Duplicates
- Smart Clean recommendations
- Low-quality files
- Unmatched Metadata fixes
- Identity Review for uncertain matches, provider conflicts, and metadata discrepancies
- Rename, Fix Path, TMDB match, optional Plex match, source search, and Recycle Bin delete flows

Identity Review scans can be paused and resumed. Metadata changes require explicit selection and confirmation. Destructive actions are explicit and confirmed, and Delete defaults to the Windows Recycle Bin.

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

User lists, Watched and Watchlist states, edited collections, followed releases, manual metadata matches, metadata corrections, identity audit state, and poster overrides are persistent user data. TMDB detail caches are rebuildable cache.

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

- `data/` stores user lists, viewing states, edited collections, followed releases, poster overrides, metadata corrections, identity audit state, and app metadata records for files, manual matches, Plex metadata, TMDB metadata, and conflicts.
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
