# Cinema Paradiso

> **Local-first movie archive command console** for Plex collectors, large Windows libraries, TMDB discovery, Prowlarr source search, and local Ollama recommendations.

Cinema Paradiso is a self-hosted movie library manager for people with hundreds or thousands of local movie files. It helps you browse what you own, clean duplicates and low-quality copies, fix Plex-unmatched files, discover movies online, search torrent indexers, stream titles, and ask a local AI curator what to watch.

Everything runs on your machine. No cloud account. No subscription. No remote database.

**Current version: v2.5.0** - June 2026

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

## What Changed in v2.5

Cinema Paradiso v2.5 is the major migration from the old all-in-one HTML interface to a modern React/Vite frontend served by the Flask backend.

- New black/gold cinematic interface based on the Cinema Paradiso styleguide.
- Persistent left sidebar with larger brand presence and simplified navigation.
- New Home command center with library health, trending discovery, selected movie inspector, and a backend-backed release watchlist.
- Release watchlist now stores followed movies in user data, checks Prowlarr for proper WEB/Blu-ray releases, ignores CAM/TS/HDCAM/screener copies, highlights available releases, and auto-removes movies once they are owned locally.
- Library now has separate **Movie View** and **File View**.
- Movie View focuses on watching decisions: poster cards, metadata, rating, genres, country/language, plot, director, cast, trailer, collections, and user lists.
- File View focuses on management: filename, path, Plex state, resolution, source, size, rename, delete, and source search.
- Library search now searches locally on the Library page and ranks title matches above plot-only matches.
- Library pagination now renders 40 results per page instead of growing the DOM with endless "show more" cards.
- Library resolution filter is simplified to `4K`, `1080p`, `720p`, and `Below 720p`.
- Added user lists and edited TMDB collection overrides stored separately from disposable TMDB cache.
- Added Settings as a real system console for library paths, app data paths, Plex, Prowlarr, TMDB, and Ollama.
- Added Cleanup as an offline maintenance center with duplicates, smart clean, low quality, and unmatched Plex workflows.
- Added Discover workspace with Explore Movies, Browse Indexers, and Pick My Movie.
- Discover cards are archive-aware: Play if owned, Stream and Find Sources if missing, Find Upgrade if owned but low quality.
- Expanded cards now include TMDB details, trailers, directors, cast, collection context, and list controls.
- Real video stream resolution probing is used so cropped 1080p files are not mislabeled as 720p.

---

## Core Workspaces

### Home

The Home page is the command center. It shows library health, followed release alerts, trending movies, and a selected movie detail panel. The release watchlist is intentionally compact: the Home widget shows only slim rows, while `View all` opens the full followed list.

### Library

Library is the offline archive browser.

- **Movie View:** for choosing what to watch.
- **File View:** for file management.
- Filters include quality, resolution bucket, source, genre, language, country, year, rating, Plex state, and size.
- Actions include Play, Find Sources, Find Upgrade, Trailer, Rename, Delete, Add to List, and collection/list filtering.

### Cleanup

Cleanup is the safe maintenance area for local files.

- Duplicates
- Smart Clean recommendations
- Low-quality files
- Unmatched Plex fixes
- Rename, Fix Path, Plex match, source search, and Recycle Bin delete flows

Destructive actions are explicit and confirmed. Delete defaults to the Windows Recycle Bin.

### Discover

Discover is the online activity area.

- **Explore Movies:** TMDB lists, genres, search, trailers, stream, sources.
- **Browse Indexers:** Prowlarr latest/search results with resolution, seeders, size, indexer, and torrent/magnet/page links.
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

User lists, edited collections, and followed releases are persistent user data. TMDB metadata is disposable cache.

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

```bash
git clone https://github.com/dantebagera/10k-movie-library-organizer.git
cd 10k-movie-library-organizer
pip install -r requirements.txt
npm install
npm run build
```

Then start the Flask app:

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000).

On Windows you can also double-click `run.bat` after dependencies are installed and the frontend has been built.

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

- `data/` stores user lists, edited collections, and followed releases.
- `cache/` stores TMDB metadata cache.
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

The old Flask template remains available at `/legacy` during migration, but the React app is the primary interface.

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
python -m unittest tests.test_user_curation_store
npm run build
```

---

## License

MIT
