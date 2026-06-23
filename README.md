# Cinema Paradiso

> **Local-first movie archive command console** for Plex collectors, large Windows libraries, TMDB discovery, Prowlarr source search, and local Ollama recommendations.

Cinema Paradiso is a self-hosted movie library manager for people with hundreds or thousands of local movie files. It helps you browse what you own, clean duplicates and low-quality copies, fix unmatched metadata, discover movies online, search torrent indexers, stream titles, and ask a local AI curator what to watch.

Everything runs on your machine. No cloud account. No subscription. No remote database.

**Current version: v2.6.5** - June 2026

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

## What Changed in v2.6.5

Cinema Paradiso v2.6.5 improves large-library metadata matching, trusted followed-release availability, and bulk list workflows while preserving the local-first v2.6 library identity model.

- **Smarter metadata acceptance:** dominant exact TMDB title/year matches can be accepted automatically while strong provider conflicts still go to review.
- **Trusted release availability:** followed releases only become Available from trusted Prowlarr indexers and approved WEBRip/Blu-ray/BDRip/BRRip sources.
- **Cleaner Prowlarr settings:** trusted release indexers live in a compact Settings popup, with YTS/YIFY selected by default when available.
- **Bulk list workflows:** Library and Discover can select filtered results and add them to new or existing lists.
- **Copy list exports:** list selections can be copied to another folder, drive, or network share through a folder browser.

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
- **Browse Indexers:** Prowlarr latest/search results with selectable indexer source, resolution, seeders, size, and direct submission to the embedded qBittorrent client.
- **Pick My Movie:** local Ollama recommendations enriched with TMDB metadata and archive-aware actions.

### Downloads

Downloads uses the original qBittorrent WebUI inside Cinema Paradiso. The embedded client is isolated from any qBittorrent installation already registered as the operating system's default torrent client.

- The v2.6.5 portable release ZIP includes a tested bundled qBittorrent runtime.
- Cinema Paradiso submissions are tagged `cinema-paradiso` and download to an incomplete staging folder.
- At 100%, Cinema Paradiso pauses and removes the torrent without deleting its data, then moves the unchanged payload into the selected movie destination.
- A blank movie destination uses the first configured library folder.
- The incomplete folder must remain outside every movie library so Plex and Cinema Paradiso cannot index partial files.
- Settings can switch torrent handling back to the operating system's default client.
- qBittorrent install and update are not exposed in v2.6.5; runtime upgrades come through future Cinema Paradiso releases.

### Help

Help is the static setup guide for optional dependencies. It explains why Plex, Prowlarr, TMDB, Ollama, and qBittorrent may be useful, links to official downloads/docs, describes where to find tokens or API keys, and provides shortcuts back to the matching Settings cards. Settings remains the only place that shows Ready/Missing states and runs connection tests.

### Settings

Settings manages:

- Movie library folders
- User data folder
- TMDB cache folder
- Plex URL/token
- Prowlarr URL/API key
- Embedded or system torrent handling
- Completed movie destination and incomplete download folder
- TMDB API key
- Ollama URL/model

User lists, Watched and Watchlist states, edited collections, followed releases, manual metadata matches, metadata corrections, identity audit state, and poster overrides are persistent user data. TMDB detail caches are rebuildable cache.

---

## Requirements

- Windows 10/11 x64 for the bundled qBittorrent portable release
- Python 3.10+
- Node.js 18+ for building the React frontend
- Optional: Plex Media Server
- Optional: Prowlarr
- Optional: TMDB API key
- Optional: Ollama

---

## Installation

### Windows Quick Start

For normal use, download the `Cinema-Paradiso-2.6.5-Portable.zip` artifact from GitHub Releases, extract it, and run Cinema Paradiso from that folder. The portable release includes the tested bundled qBittorrent runtime.

The GitHub Source ZIP remains developer-oriented. If you download the source ZIP or clone the repository, double-click `run.bat`.

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
  "tmdb_cache_dir": "C:\\Path\\To\\CinemaParadiso\\cache",
  "qbt_mode": "embedded",
  "qbt_download_dir": "",
  "qbt_incomplete_dir": "",
  "qbt_webui_port": 8686
}
```

Only a movie library folder is required. Integrations are optional.

The v2.6.5 portable release uses bundled qBittorrent. Settings lets you choose embedded qBittorrent or the system default torrent client, plus completed and incomplete folders. qBittorrent install/update controls are intentionally not part of v2.6.5.

---

## Local Data and Cache

The app separates persistent user data from rebuildable cache:

- `data/` stores user lists, viewing states, edited collections, followed releases, poster overrides, metadata corrections, identity audit state, app metadata records, and the isolated qBittorrent profile/jobs when the default user data folder is used.
- `runtime/` in the portable release stores bundled third-party runtimes such as qBittorrent.
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
- Torrent-file retrieval is restricted to the configured Prowlarr origin; arbitrary browser-supplied download URLs are rejected.
- Completed downloads are never renamed automatically.

---

## Tech Stack

- **Backend:** Python, Flask
- **Frontend:** React 19, Vite, CSS custom properties
- **Icons:** Lucide React
- **Metadata:** Plex API, TMDB API
- **Source search:** Prowlarr API
- **Downloads:** qBittorrent WebUI API and original qBittorrent WebUI
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
