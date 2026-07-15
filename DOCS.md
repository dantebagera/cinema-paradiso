# Cinema Paradiso — Documentation

> A self-hosted movie library command centre: duplicate cleaner, quality scanner, full library browser, TMDB discovery suite, Prowlarr torrent finder, and AI-powered film recommendations.  
> Runs entirely on your own machine — no cloud, no accounts, no data leaves your PC.

**v2.0** — June 2026

---

## Changelog

### v2.0 (June 2026)

#### 🎨 Cinema Paradiso — Full Cinematic UI Redesign

The entire interface has been rebuilt around a **fixed left sidebar navigation** and a deep cinematic dark theme.

- **New name:** Cinema Paradiso
- **Sidebar navigation** (220px) replaces the old top button bar. Icon+label nav items with per-feature accent colours on hover. "Cinema / Paradiso" two-line logo wordmark at the top, Settings pinned at the bottom.
- **Cinematic home screen** — bold hero heading ("Your Movie Library, Mastered."), gold accent line, and an 8-card responsive grid. Each card has a colour-coded 2px top bar, icon badge, 2–3 sentence feature description, and a direct action button.
- **Deep dark background** (`#0a0a10`) — near-black canvas throughout with subtle card surfaces (`#10101e`).
- **Per-feature colour identity:** Scan Duplicates (gold `#fdcb6e`), Smart Clean (green `#2ecc71`), Low Quality (orange `#e5a00d`), Library (blue `#74b9ff`), Dashboard (pink `#fd79a8`), Unmatched (purple `#a29bfe`), Explore/Pick (gold/purple).
- Settings dropdown repositioned to `bottom: 20px; left: 228px` — adjacent to the bottom of the sidebar.

#### 🤖 Pick My Movie — AI Film Recommendations (Ollama)

New full-screen panel powered by a local Ollama installation:

- Type any mood, era, actor, or half-remembered plot → press **🤖 Ask AI**
- Ollama returns 5 picks with a one-sentence reason for each
- Cards enriched with TMDB: poster, genres, rating, plot
- **"In Your Library" detection** — after results arrive, the app silently fires `POST /api/library/check`. Cards for owned films show a green **✓ In Your Library · 1080p · 2.4 GB** badge and a **▶ Play from HDD** button. Stream button hidden for owned films.
- Find Torrent on every card for immediate Prowlarr search
- Ctrl+Enter submits the prompt
- Configured in ⚙ Settings → Ollama (URL + model name, Test + Save)
- Requires [Ollama](https://ollama.ai) running locally — free, no API key
- New `config.json` fields: `ollama_url`, `ollama_model`

#### New Backend Route (v2.0)

| Method | Route | Description |
|---|---|---|
| POST | `/api/ollama/recommend` | Send a mood/description prompt → 5 AI recommendations enriched with TMDB |
| GET | `/api/ollama/config` | Get saved Ollama URL + model |
| POST | `/api/ollama/config` | Save Ollama URL + model |
| GET | `/api/ollama/test` | Test Ollama reachability |
| POST | `/api/library/check` | Check which of a list of `{title, year}` movies exist in the local library |

---

### v1.5 (May 2026)

#### 🔍 Explore Torrents Panel — Full Movie Discovery & Torrent Hub

A completely new full-screen panel accessible from the **🔍 Explore Torrents** button in the header. Replaces the earlier "Trending" panel and expands it significantly.

##### Global TMDB Search
- A search bar sits above the tabs. Type any movie title and press Enter (or click 🔍 Search) to search the entire TMDB database instantly.
- Results appear as poster cards — same card layout as the Discover tab.
- **Load More** fetches additional pages (up to 10 pages / 200 results per search).
- **✕ Clear** returns to the tab view.

##### TMDB Discover Tab
Browse curated TMDB lists with poster cards, TMDB ratings, genre tags, and language/country badges.

**Available lists:**
| List | Description |
|---|---|
| Trending Today | What's hot on TMDB right now |
| Popular Now | All-time most popular on TMDB |
| Now Playing | Currently in cinemas |
| Top Rated | Highest-rated movies on TMDB |
| Upcoming | Movies releasing soon |
| Best of All Time | Top-rated by vote count (>1000 votes) |

**Genre filter:** Filter the active list by genre (Action, Comedy, Drama, Horror, Sci-Fi, Thriller, Animation, Crime, Romance, Documentary, Family, Fantasy, History, Music, Mystery).

**Load More:** Each list loads 20 results at a time; click Load More to append the next page (up to 200 results total).

**Movie cards include:**
- Poster image (from TMDB, lazy-loaded)
- Resolution badge (on Browse tab)
- Title + year
- Up to 3 genre tags
- ⭐ TMDB rating
- Language + country flag tag (e.g. 🇰🇷 Korean, 🇯🇵 Japanese) — derived from TMDB `original_language`
- Plot summary with **▾ more / ▴ less** expand/collapse toggle
- **▶ Stream** — opens the movie on [playimdb.com](https://www.playimdb.com) for instant streaming (requires TMDB key; fetches the IMDB ID first)
- **🔍 Find Torrent** — searches all your Prowlarr indexers for that movie and shows a full results table in a modal

##### Find Torrent Modal
Clicking **Find Torrent** on any card opens a modal showing **all 1080p+ and 4K** torrent results from every Prowlarr indexer, sorted 4K-first then 1080p by seeders. Columns: Quality · Title · Size · Seeds · Indexer · Action (Magnet / Torrent file).

##### Browse Indexers Tab
Browse the latest torrents directly from your Prowlarr indexers in the same poster-card format.

- Fetches all results for category 2000 (Movies) from every enabled indexer.
- Cards are enriched with TMDB metadata (poster, rating, genres, plot) asynchronously.
- Each card shows **variant pills** — one pill per resolution variant (e.g. 4K / 1080p / 720p) with seeder count. Click a pill to switch which variant the action buttons target.
- **Filters:** Quality (4K/1080p/720p/480p/Unknown) · Indexer (all registered Prowlarr indexers) · Sort (Seeders, Title, Year).
- **Indexer dropdown** is populated from every enabled indexer registered in Prowlarr — not just those that returned results.
- Stream + Find Torrent buttons work exactly the same as on Discover cards.

##### New Backend Routes (v1.5)
| Route | Description |
|---|---|
| `GET /api/explore/browse` | Fetch latest movie torrents from all Prowlarr indexers |
| `GET /api/explore/search?title=&year=` | Find ALL 1080p+ torrents for a specific title across all indexers |
| `GET /api/tmdb/discover?list=&genre=&page=` | Fetch TMDB curated list with language/country enrichment |
| `GET /api/tmdb/search?q=&page=` | Full TMDB movie text search |
| `GET /api/tmdb/imdb_id?tmdb_id=` | Look up IMDB ID for a TMDB movie (used for streaming) |

##### New `config.json` field
```json
{ "tmdb_key": "your-tmdb-api-key" }
```
Get a free key at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api). Configure it in ⚙ Settings.

---

### v1.17 (May 2026)

#### Rename in Library Browser
Every row in the **Library Browser** now has a purple **✎ Rename** button, matching the Unmatched panel. Clicking it opens the rename modal pre-filled with the detected title and year. After saving, the row updates **in-place** immediately — no need to reopen the panel.

---

### v1.16 (May 2026)

#### Plex-Metadata Duplicate Detection
The Duplicate Scanner now uses `_plex_cache` title/year as the grouping key when available. Files matched by Plex to the same TMDB/TVDB entry are grouped as duplicates regardless of their filename. Files not in Plex still fall back to `parse_movie_title()` filename parsing.

#### Plex Bulk Mis-match Guard
Maintenance audit groups with more than four Plex-derived copies are re-bucketed by filename identity before they can be treated as duplicates. Legitimate duplicate pairs remain unaffected.

#### Fix Path — Whole Folder Move
`fix_path()` now counts video files in the parent folder before moving. If the parent contains only one video file, the **entire folder** is moved one level up so the folder name (e.g. `Batman (2010)`) is preserved. Plex uses the folder name as a metadata hint, so it re-matches cleanly after rescan. If the parent contains multiple video files, the original file-only move is used as a fallback.

#### Fix Path — Depth Threshold
Changed `fixable_path: rel_depth > 2` to `rel_depth > 1`. Files at depth 2 (one subfolder under the movies root) now also show the Fix Path button.

#### Fix All Paths Button
Added `fixAllPaths()` JS function and `#fix-all-paths-btn` button to the Unmatched panel toolbar. The button is shown automatically when any fixable items exist. Iterates all fixable items sequentially, updates button text with live progress, shows a summary toast, and auto-shows the Refresh button on completion.

---

### v1.15 (May 2026)

#### Color-Coded Welcome Page
The home screen now displays one line per panel button, each rendered in its matching nav-bar color. Descriptions are hidden automatically when a scan begins.

#### Play Button in All Panels
A green **▶ Play** button is shown on every file row in the Duplicates, Low Quality, Library, and Unmatched panels. Clicking it calls `os.startfile()` to open the file in the OS default video player.

#### Manual Rename in Unmatched Panel
Each row in the Unmatched panel has a purple **✎ Rename** button. Clicking it opens the rename modal pre-filled with the detected title and year. The server appends quality tags, strips invalid filename characters, renames the file, and triggers a Plex rescan.

---

### v1.11 (May 2026)

#### Real File Resolution Detection
Resolution is now read directly from the video stream using **pymediainfo** (ships with a bundled `MediaInfo.dll` on Windows). Files with no resolution tag in their filename now report their true stream resolution. Results are cached in `res_cache.json`; each file is probed at most once.

#### Library Browser — Virtual Scroll
The Library panel renders only ~30 visible rows at a time. All rows are kept in a JavaScript array; the DOM updates on scroll. The table opens instantly regardless of library size.

#### Library Browser — Prowlarr Search Button
A **🔍 Search Prowlarr** button is present on every Library row, consistent with the Low Quality and Duplicates panels.

#### Library Load Cache
The `/api/library` response is cached server-side for 5 minutes. Cache is invalidated on directory change, file deletion, and Plex sync.

#### Scan Progress Status
`/api/library/status` exposes a string updated every 50 files during scan. The frontend polls this and updates the loading bar message (`Reading metadata… 150 / 3600`).

---

### v1.1 (May 2026)

#### New Feature — Unmatched Panel
A dedicated panel for video files buried in deep subfolder structures that Plex cannot match. Per-file actions: Fix Path, Match (Plex agent search), Delete. Bulk delete with Recycle Bin safety.

---

### v1.0 (initial release)
- Duplicate Scanner with quality ranking and Smart Clean
- Low Quality Scanner (< 1080p)
- Library Browser with filters, sort, and bulk delete
- Dashboard with charts (resolution, source, decade, Plex coverage)
- Plex integration (auto-cache, 5-minute TTL)
- Prowlarr integration (1080p+ torrent search)
- Recycle Bin and permanent delete modes
- Windows launcher (`run.bat`)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Requirements & Installation](#2-requirements--installation)
3. [Starting the App](#3-starting-the-app)
4. [Interface Tour](#4-interface-tour)
5. [Features](#5-features)
   - 5.1 [Duplicate Scanner](#51-duplicate-scanner)
   - 5.2 [Smart Clean](#52-smart-clean)
   - 5.3 [Low Quality Scanner](#53-low-quality-scanner)
   - 5.4 [Library Browser](#54-library-browser)
   - 5.5 [Dashboard](#55-dashboard)
   - 5.6 [Plex Integration](#56-plex-integration)
   - 5.7 [Prowlarr Integration](#57-prowlarr-integration)
   - 5.8 [Unmatched Panel](#58-unmatched-panel)
   - 5.9 [Explore Movies *(v1.5)*](#59-explore-movies-v15)
   - 5.10 [Pick My Movie — AI Recommendations *(v2.0)*](#510-pick-my-movie--ai-recommendations-v20)
6. [Delete Modes](#6-delete-modes)
7. [How Titles Are Detected](#7-how-titles-are-detected)
8. [How Resolution Is Detected](#8-how-resolution-is-detected)
9. [How Rip Source Is Detected](#9-how-rip-source-is-detected)
10. [Configuration File](#10-configuration-file)
11. [API Reference](#11-api-reference)
12. [File Structure](#12-file-structure)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Overview

**Cinema Paradiso** is a Flask-based web app that is your complete personal movie library command centre:

- **Duplicate detection** — finds every film you own more than once and ranks each copy by quality
- **Smart Clean** — automated one-click cleanup of inferior duplicates
- **Low Quality scanner** — lists every file below 1080p for targeted upgrades
- **Library browser** — full table or poster-grid of every file with search, filters, play, rename, and bulk delete
- **Dashboard** — live stats, charts, and insights about your entire collection
- **Plex integration** — cross-references files with Plex metadata; grouping uses Plex TMDB/TVDB identity
- **Prowlarr integration** — search 1080p+ torrent replacements from any panel
- **Explore Movies** *(v1.5)* — TMDB discovery, global search, Browse Indexers, Find Torrent, Stream
- **Pick My Movie** *(v2.0)* — describe a mood to your local Ollama AI, get 5 personalised picks with posters; green badge + Play button if you already own the film

All detection is **filename-based** — the app works even when Plex cannot identify a file. Plex data is layered on top as optional enrichment.

The full layout is a **fixed left sidebar** (220px) + scrollable content area. All feature panels are full-screen overlays that cover the entire viewport.

---

## 2. Requirements & Installation

### Prerequisites

| Software | Version | Purpose |
|---|---|---|
| Python | 3.10+ | Runtime |
| Flask | ≥ 3.0.0 | Web server |
| send2trash | ≥ 1.8.0 | Recycle Bin support |
| pymediainfo | ≥ 6.0.0 | Real video resolution detection |

### Install dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` contains:
```
flask>=3.0.0
send2trash>=1.8.0
pymediainfo>=6.0.0
```

No other external packages are required. The app uses only Python standard library modules (`os`, `re`, `stat`, `shutil`, `urllib`, `json`) for everything else.

---

## 3. Starting the App

### Windows (recommended)

Double-click **`run.bat`**.

This will:
1. Navigate to the app folder
2. Automatically open `http://localhost:5000` in your default browser
3. Start the Flask server (using `.venv\Scripts\python.exe` if a virtual environment exists)

### Manual start

```bash
python app.py
```

Then open `http://localhost:5000` in your browser.

The server listens on port **5000** and is only accessible from your local machine.

---

## 4. Interface Tour

```
┌──────────────┬─────────────────────────────────────────────────────────────┐
│   CINEMA     │  🎬 CINEMA PARADISO                                         │
│   PARADISO   │  Your Movie Library, Mastered.                              │
│              │  Scan, clean, explore and discover — everything your        │
│  🎬 Scan     │  collection needs, in one place.                            │
│  🔍 Low Q.   │                                                             │
│  📂 Library  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  📊 Dashboard│  │🎬 Scan Dupes │ │⚡ Smart Clean│ │🔍 Low Quality│       │
│  🔗 Unmatched│  │ description  │ │ description  │ │ description  │       │
│  🌐 Explore  │  │ Run Scan →   │ │ Open Smart → │ │ View LQ →    │       │
│  🤖 Pick Me  │  └──────────────┘ └──────────────┘ └──────────────┘       │
│              │  ┌──────────────┐ ┌──────────────┐ ...                     │
│  ⚙ Settings  │  │📂 Library    │ │📊 Dashboard  │                         │
└──────────────┴─────────────────────────────────────────────────────────────┘
```

### Sidebar controls

| Nav Item | Description |
|---|---|
| 🎬 **Scan Duplicates** | Scans the library for duplicate films |
| ⚡ **Smart Clean** | Auto-recommendations for safe duplicate deletion (appears after scan) |
| 🔍 **Low Quality** | Opens the sub-1080p file scanner |
| 📂 **Library** | Opens the full library browser |
| 📊 **Dashboard** | Opens the statistics overlay |
| 🔗 **Unmatched** | Opens the unmatched metadata fixer |
| 🌐 **Explore Movies** | Full-screen TMDB discovery, torrent finder, and streaming |
| 🤖 **Pick My Movie** | AI-powered film recommendation panel (Ollama) |
| ⚙ **Settings** | Pinned at the bottom — configure Plex, Prowlarr, TMDB, Ollama |

---

## 5. Features

### 5.1 Duplicate Scanner

Click **Scan for Duplicates** to scan your movies directory recursively.

**How duplicates are found:**  
Files are grouped by a `(normalized_title, year)` key extracted from their filename. Two files are considered duplicates if they resolve to the same title and year — regardless of resolution, codec, or rip source. If Plex data is available, the Plex-matched title/year is used as the grouping key instead.

**Within each group, files are ranked by quality (best first):**
1. Resolution rank (4K > 1080p > 720p > 480p > Unknown)
2. Rip source rank (BD Remux > Blu-ray > WEB-DL > WEBRip > DVDRip > CAMRip…)
3. File size (larger is assumed better for same resolution/source)

**The first file in each group is marked with a green stripe** — that is the best copy.

**Plex data** is shown automatically per file (if Plex is configured).

**Stats bar** (appears after scan):
- **Duplicate Groups** — number of movies with more than one copy
- **Extra Copies** — total number of redundant files
- **Wasted Space** — combined size of all non-best copies

**Search bar:** Type to filter duplicate groups in real time by movie title.

**🔎 Search Prowlarr** — each file row has a Prowlarr search button to find a better replacement.

---

### 5.2 Smart Clean

Click **⚡ Smart Clean** after a scan to get automated recommendations.

**Rules applied:**

| Situation | Action |
|---|---|
| File has lower resolution than best copy | ✅ Recommended for deletion |
| Same resolution but worse rip source AND size difference < 5% | ✅ Recommended for deletion |
| Same resolution but worse rip source AND size difference ≥ 5% | ⚠ Flagged for manual review (skipped) |
| File is the best copy in its group | Never flagged |

**Panel controls:**
- **Select All / Deselect All** — toggle all checkboxes
- **Delete Selected (N)** — deletes all checked items (respects Recycle Bin toggle)
- **Close** — dismiss without deleting

Skipped/manual-review items appear dimmed with a dashed border and cannot be checked.

---

### 5.3 Low Quality Scanner

Click **🔍 Low Quality** to list every video file in your library with a resolution below 1080p.

**Flagged resolutions:** 720p, 480p, Unknown  
**Not flagged:** 1080p, 4K

**Filter bar:**
- **Resolution** — filter to a specific resolution (720p, 480p, Unknown)
- **Source** — filter by rip type (WEBRip, DVDRip, etc.)
- **Sort by size** — Default (A-Z), Smallest first, Largest first

**Per-item controls:**
- Checkbox — select for bulk delete
- **▶ Play** — open the file in your default video player
- **🔎 Search Prowlarr** — opens a Prowlarr torrent search for that title

**📋 Copy Titles** — copies all (filtered) movie titles to clipboard.

---

### 5.4 Library Browser

Click **📂 Library** to open a full table of every video file in your library.

**Columns:**

| Column | Description |
|---|---|
| ☐ | Checkbox for selection |
| Title | Detected movie title + **▶ Play**, **🔎 Search Prowlarr**, **✎ Rename** buttons |
| Resolution | 4K / 1080p / 720p / 480p / Unknown badge (from real video stream via pymediainfo) |
| Source | Rip type badge (Blu-ray, WEB-DL, etc.) |
| Size | Human-readable file size |
| Plex Title & Genres | Title/year from Plex + genre tags (if Plex configured) |
| Path | Full file path on disk |

**Filter controls:**
- **Search** — live text filter on title or filename
- **Resolution** dropdown
- **Source** dropdown
- **Plex** dropdown — All / Matched ✓ / No Plex data ⚠
- **Sort** — Name A→Z/Z→A, Size largest/smallest, Resolution best/worst, Source best/worst

**Virtual scroll** — only ~30 rows are rendered at a time; the full library is kept in memory. Instant even with 3,000+ files.

**✎ Rename** — opens a rename modal pre-filled with the detected title and year. The row updates in-place on save.

**Bulk delete:**
- Check rows (or use the header checkbox to select all visible)
- Click **🗑 Delete Selected** in the select bar

---

### 5.5 Dashboard

Click **📊 Dashboard** to open the statistics overlay.

**Stat cards:** Total Files · Unique Titles · Library Size · Dup. Groups · Wasted Space · Low Quality · Plex Matched · No Plex Data

**Charts:**
- **Resolution donut** — 4K / 1080p / 720p / 480p / Unknown distribution
- **Source/Rip donut** — rip type distribution
- **By Decade bar** — movies per decade
- **Plex Coverage donut** — matched vs unmatched (after Plex sync)

**Top 10 Largest Files** table.

---

### 5.6 Plex Integration

Click **⚙ Settings** and expand the Plex section to configure.

| Field | Example |
|---|---|
| Plex URL | `http://localhost:32400` |
| X-Plex-Token | `xxxxxxxxxxxxxxxxxxxx` |

**How to find your Plex token:**

**Method 1:** In Plex Web → click any movie → ··· → Get Info → View XML. The URL contains `?X-Plex-Token=YOUR_TOKEN`.

**Method 2 (Windows):** Open `C:\Users\[YourUsername]\AppData\Local\Plex Media Server\Preferences.xml` and find `PlexOnlineToken`.

**How matching works:**  
The app calls `GET /library/sections/{id}/all` for every movie section. It builds a lookup: `normalized_path → {plex_title, plex_year, plex_genres}`. This cache auto-refreshes (TTL: 5 minutes) on every scan. When Plex data is available, the Plex-matched title/year is used for duplicate grouping — so files Plex tagged as the same movie are always grouped together.

---

### 5.7 Prowlarr Integration

Click **⚙ Settings** and expand the Prowlarr section.

| Field | Example |
|---|---|
| Prowlarr URL | `http://localhost:9696` |
| API Key | Prowlarr → Settings → General |

> **Important:** In Prowlarr → Settings → General, make sure **URL Base** is **blank** (not `/prowlarr`).

**Searching for replacements (from any panel):**  
Click **🔎 Search Prowlarr** on any file row. The app fetches all enabled indexer IDs from Prowlarr first, passes them explicitly to the search API so every indexer is queried, and returns results filtered to **1080p and above only**.

**Result filters:** Text search · Resolution dropdown · Indexer dropdown · Sort (Size, Seeders, Resolution, Title)

**Per-result actions:** 🧲 Magnet · ⬇ Torrent file

---

### 5.8 Unmatched Panel *(v1.1)*

Click **🔧 Fix Unmatched** (visible after Plex sync) to find files buried in deep subfolder structures that Plex cannot match.

**Per-file actions:**
- **Fix Path** — moves the file one level up, removes empty/junk folders, triggers Plex rescan. If the parent folder contains only that one video file, the whole folder is moved (preserving the folder name as a Plex hint).
- **Match** — search Plex agents by title/year and apply the correct match manually.
- **Delete** — send to Recycle Bin immediately.
- **✎ Rename** — rename the file with corrected title and year.
- **▶ Play** — open in default video player.

**Bulk controls:** Select All · Delete Selected · Fix All Paths (fixes every fixable item in sequence with live progress) · Refresh List

---

### 5.9 Explore Movies *(v1.5)*

Click **🌐 Explore Movies** in the sidebar to open the full-screen explore panel.

This panel is a self-contained movie discovery and torrent hub. It does not interact with your local library — it is purely for finding and streaming movies.

#### Global Search Bar

At the top of the panel, before the tabs:

- **Search input** — type any movie title, press Enter or click 🔍 Search
- Hides the tab view and shows a grid of TMDB search results
- **Load More** appends additional pages (up to 10 pages)
- **✕ Clear** dismisses results and restores the active tab

#### TMDB Discover Tab

Browse curated TMDB movie lists.

**List selector:**

| Option | Source |
|---|---|
| Trending Today | TMDB `/trending/movie/day` |
| Popular Now | TMDB `/movie/popular` |
| Now Playing | TMDB `/movie/now_playing` |
| Top Rated | TMDB `/movie/top_rated` |
| Upcoming | TMDB `/movie/upcoming` |
| Best of All Time | TMDB `/discover/movie` sorted by vote average (min 1000 votes) |

**Genre filter:** Narrow results to a single genre using the dropdown (15 genres available).

**Load More:** Appends the next page of results. Up to 10 pages / 200 results per list.

**Refresh:** Re-fetches the current list + genre combination.

#### Browse Indexers Tab

Browse the latest movie torrents directly from your Prowlarr indexers.

- On load, fetches all enabled indexer IDs from Prowlarr and queries category 2000 (Movies).
- Results are deduplicated by title+year. Each unique movie card shows **resolution variant pills** (4K / 1080p / 720p / 480p). Click a pill to switch the active variant.
- TMDB metadata (poster, rating, genres, plot) is loaded asynchronously per card.
- **Indexer dropdown** lists every indexer registered in Prowlarr — not just those that returned results.
- Up to 100 results, sorted by seeders (most first) by default.

**Filters:**

| Control | Description |
|---|---|
| Quality | Filter cards by resolution |
| Indexer | Filter to a specific Prowlarr indexer |
| Sort | Seeders (most), Seeders (least), Title A→Z, Year (newest) |

#### Movie Cards (both tabs)

Every card displays:

| Element | Description |
|---|---|
| Poster | TMDB poster image (lazy-loaded) |
| Year | Release year |
| Genre tags | Up to 3 genres |
| ⭐ Rating | TMDB vote average |
| Language / Country | ISO flag emoji + language name (e.g. 🇰🇷 Korean, 🇯🇵 Japanese) |
| Plot | Expandable synopsis — click **▾ more** to expand, **▴ less** to collapse |
| ▶ Stream | Opens the movie on playimdb.com in a new tab. Looks up the IMDB ID via TMDB first. |
| 🔍 Find Torrent | Searches all Prowlarr indexers for this movie and shows all available 1080p+ and 4K results in a modal |

#### Find Torrent Modal

Opens when clicking **Find Torrent** on any card.

- Searches Prowlarr using the movie title and year.
- Returns **all** 1080p+ and 4K results across every enabled indexer.
- Results sorted: 4K first (by seeders), then 1080p (by seeders).
- Table columns: Quality · Title · Size · Seeds · Indexer · 🧲 Magnet / ⬇ Torrent
- Close button or click outside to dismiss.

#### TMDB Key Configuration

Required for: poster images, ratings, genres, plot, Stream button, all Discover/Search features.

1. Get a free key at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)
2. Open ⚙ Settings in the app → TMDB section → paste the key → Save & Test

---

### 5.10 Pick My Movie — AI Recommendations *(v2.0)*

Click **🤖 Pick My Movie** in the sidebar to open the full-screen AI recommendation panel.

This panel uses your local [Ollama](https://ollama.ai) installation to recommend films based on a natural-language description. It does not send any data to external AI services — everything runs on your machine.

#### How it works

1. Type any description in the text box — a mood, an era, an actor, a half-remembered plot
2. Press **🤖 Ask AI** (or Ctrl+Enter)
3. Ollama returns 5 film titles with reasons. The app then enriches each with TMDB metadata (poster, genres, rating, plot)
4. Cards appear immediately. In the background, the app fires `POST /api/library/check` to see which films you already own.

#### Card layout

Each recommendation card shows:

| Element | Description |
|---|---|
| Poster | TMDB poster (lazy-loaded) |
| **✓ In Your Library** badge | Green pill — shown only for films found in your local folder. Shows resolution + file size (e.g. `· 1080p · 2.4 GB`) |
| 💡 Reason badge | Purple pill — the AI's one-sentence reason this film fits your description |
| Title, year | |
| Genre tags | Up to 3 genres from TMDB |
| ⭐ Rating | TMDB vote average |
| Plot | Expandable synopsis |
| **▶ Play from HDD** | Green button — shown only when the film is in your library. Opens the file in your default video player |
| **🔍 Find Torrent** | Prowlarr torrent search (always shown) |
| **▶ Stream** | Opens playimdb.com (shown only when NOT in your library) |

#### In-Library Detection

After the cards render, the app sends all 5 `{title, year}` pairs to `POST /api/library/check`. Matching strategy (in order):

1. **Plex-matched title + year** — most reliable; uses `plex_title` and `plex_year` from the Plex cache
2. **Filename-parsed title + year** — fallback when Plex is not synced

Both the AI result title and the library titles are normalised before comparison: lowercased, punctuation stripped, leading article (`the/a/an`) removed. A year-agnostic second pass catches cases where TMDB and Plex disagree on the release year by ±1.

If `movies_dir` is not configured, all results gracefully return `found: false` — no crash.

#### Ollama Configuration

1. Install [Ollama](https://ollama.ai) and pull a model: `ollama pull llama3`
2. Open ⚙ Settings → Ollama section → set URL (default `http://localhost:11434`) and model name → Test + Save
3. New `config.json` fields: `ollama_url`, `ollama_model`

---

## 6. Delete Modes

The **delete mode toggle** at the top of the main view controls how all deletions work throughout the app.

| Mode | Behaviour | Visual |
|---|---|---|
| **Recycle Bin** (default) | Moves file to Windows Recycle Bin via `send2trash`. Recoverable. | Green indicator |
| **Permanent Delete** | Calls `os.remove()`. Cannot be undone. Also removes the parent folder if it becomes empty of video files. | Red indicator |

**Security:** The app will only delete files inside the configured movies directory. Any attempt to delete a file outside that path is rejected with a 403 error.

**Read-only files:** The app automatically clears the read-only flag before deletion.

**Confirmation dialog:** Every delete action requires explicit confirmation in a modal dialog.

---

## 7. How Titles Are Detected

The `parse_movie_title(filename)` function:

1. Strips the file extension
2. Finds a 4-digit year matching `19xx` or `20xx` surrounded by separators or brackets
3. Everything before the year becomes the title
4. If no year is found, everything before the first quality keyword (`1080p`, `bluray`, `x264`, etc.) is used
5. Dots, underscores, and hyphens are replaced with spaces
6. The result is lowercased and stripped
7. Returns `(normalized_title, year)`

**Examples:**

| Filename | Detected Title | Year |
|---|---|---|
| `The.Dark.Knight.2008.1080p.BluRay.mkv` | `the dark knight` | `2008` |
| `Dune.Part.Two.(2024).WEB-DL.mkv` | `dune part two` | `2024` |
| `Scarface_1983_BDRemux.mkv` | `scarface` | `1983` |
| `some.random.movie.x264.mkv` | `some random movie` | `` |

---

## 8. How Resolution Is Detected

Resolution is determined in two stages:

1. **Filename check** (`get_resolution(filename)`) — looks for keywords like `2160p`, `4k`, `1080p`, `720p`, `480p`
2. **Real stream probe** (via `pymediainfo`) — if the filename gives `Unknown`, the actual video stream height is read from the file. Results are cached in `res_cache.json`.

| Resolution | Detected by (filename) |
|---|---|
| **4K** | `2160p`, `4k`, `uhd` |
| **1080p** | `1080p`, or `1080` surrounded by separators |
| **720p** | `720p`, or `720` surrounded by separators |
| **480p** | `480p`, or `480` surrounded by separators |
| **Unknown → probed** | None of the above — pymediainfo reads the stream |

**Resolution rank (used for sorting/comparison):**

| Resolution | Rank |
|---|---|
| 4K | 4 |
| 1080p | 3 |
| 720p | 2 |
| 480p | 1 |
| Unknown | 0 |

---

## 9. How Rip Source Is Detected

| Source | Keywords detected | Rank |
|---|---|---|
| BD Remux | `bdremux`, `bd remux` | 9 |
| Remux | `remux` | 8 |
| Blu-ray | `bluray`, `blu-ray` | 7 |
| BDRip | `bdrip` | 6 |
| WEB-DL | `web-dl`, `webdl` | 5 |
| WEBRip | `webrip`, `web-rip` | 4 |
| HDRip | `hdrip` | 3 |
| HDTV | `hdtv` | 2 |
| DVDRip | `dvdrip`, `dvd-rip` | 1 |
| DVDScr | `dvdscr`, `dvd-scr` | 0 |
| CAMRip | `camrip`, `cam-rip` | -1 |
| HDCAM | `hdcam` | -2 |
| Unknown | nothing matched | -3 |

---

## 10. Configuration File

Settings are automatically saved to `config.json` in the app folder whenever you click Save in any settings dialog.

```json
{
  "movies_dir": "E:\\Movies",
  "prowlarr_url": "http://localhost:9696",
  "prowlarr_key": "your-prowlarr-api-key",
  "plex_url": "http://localhost:32400",
  "plex_token": "your-plex-token",
  "tmdb_key": "your-tmdb-api-key",
  "ollama_url": "http://localhost:11434",
  "ollama_model": "llama3"
}
```

Only `movies_dir` is required. All other fields are optional — features that require them will show a "not configured" message in the app.

This file is loaded on startup so all settings persist across restarts. You can also edit it manually in a text editor while the app is not running.

> **Note:** The Plex metadata cache lives only in memory and resets on restart. The app automatically refreshes it (TTL: 5 minutes) whenever any panel is opened. The resolution probe cache (`res_cache.json`) is saved to disk and survives restarts.

---

## 11. API Reference

All endpoints return JSON. Base URL: `http://localhost:5000`

### Configuration

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/config` | Get current movies directory |
| POST | `/api/config` | Set movies directory `{"directory": "E:\\Movies"}` |

### Library

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/maintenance/audit` | Return catalog-backed storage, upgrade, and identity maintenance queues |
| GET | `/api/library` | Return all video files with metadata |
| GET | `/api/library/status` | Return current scan progress string |
| GET | `/api/stats` | Return full library statistics (for Dashboard) |
| POST | `/api/delete` | Delete a file `{"path": "...", "trash": true}` |
| POST | `/api/open-file` | Open a file in the OS default player `{"path": "..."}` |
| POST | `/api/rename-file` | Rename a file `{"path": "...", "title": "...", "year": "..."}` |

### Plex

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/plex/config` | Get saved Plex URL and token |
| POST | `/api/plex/config` | Save Plex URL and token |
| GET | `/api/plex/test` | Test connection, returns library count |
| GET | `/api/plex/sync` | Fetch all file paths from Plex into memory cache |
| POST | `/api/fix-path` | Move a file one level up + trigger Plex rescan |
| POST | `/api/plex/force-scan` | Trigger Plex section rescan and reset local cache |
| GET | `/api/plex/match-search` | Search Plex agents `?rating_key=&title=&year=` |
| POST | `/api/plex/match-apply` | Apply a Plex agent match `{"rating_key": "...", "guid": "..."}` |

### Prowlarr

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/prowlarr/config` | Get saved Prowlarr URL and key |
| POST | `/api/prowlarr/config` | Save Prowlarr URL and key |
| GET | `/api/prowlarr/test` | Test connection, returns indexer count |
| GET | `/api/prowlarr/search?q=title` | Search for torrents, 1080p+ only |

### Explore Movies *(v1.5)*

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/explore/browse` | Latest movie torrents from all Prowlarr indexers. Returns `results`, `all_indexers` list, `tmdb_enabled` flag |
| GET | `/api/explore/search?title=&year=` | All 1080p+ torrent variants for a specific title across all indexers. Returns `variants[]` sorted 4K-first then 1080p by seeders |
| GET | `/api/tmdb/discover?list=&genre=&page=` | Fetch a TMDB curated list. `list` values: `trending`, `popular`, `now_playing`, `top_rated`, `upcoming`, `best`. Returns `results[]` with `tmdb_id`, `title`, `year`, `poster_url`, `genres`, `tmdb_rating`, `plot`, `language`, `country`, `country_flag` |
| GET | `/api/tmdb/search?q=&page=` | Full TMDB text search. Same response shape as discover. Supports up to 10 pages |
| GET | `/api/tmdb/imdb_id?tmdb_id=` | Looks up IMDB ID for a TMDB movie. Returns `{"imdb_id": "tt1234567"}` |
| GET | `/api/tmdb/config` | Get saved TMDB key |
| POST | `/api/tmdb/config` | Save TMDB key `{"key": "..."}` |
| GET | `/api/tmdb/test` | Test TMDB connection |
| GET | `/api/metadata?title=&year=` | Fetch TMDB metadata for a title (used internally for Browse Indexers enrichment). Returns `tmdb_id`, `poster_url`, `genres`, `tmdb_rating`, `plot` |

### Ollama / Pick My Movie *(v2.0)*

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ollama/recommend` | Send a prompt → 5 AI picks enriched with TMDB. Body: `{"prompt": "..."}`. Response: `{"results": [{title, year, reason, poster_url, genres, tmdb_rating, plot, tmdb_id}], "model": "..."}` |
| GET | `/api/ollama/config` | Get saved Ollama URL + model |
| POST | `/api/ollama/config` | Save Ollama URL + model. Body: `{"url": "...", "model": "..."}` |
| GET | `/api/ollama/test` | Test Ollama reachability |
| POST | `/api/library/check` | Check which of a list of movies exist locally. Body: `{"movies": [{"title": "...", "year": "..."}]}`. Response: `{"results": [{title, year, found, path, resolution, size_human}]}` |

---

## 12. File Structure

```
filebotx/
├── app.py                  # Flask backend — all routes and logic (~1700 lines)
├── run.bat                 # Windows launcher (opens browser + starts server)
├── requirements.txt        # Python dependencies
├── config.json             # Auto-created — persists all settings
├── res_cache.json          # Auto-created — resolution probe cache (survives restarts)
├── DOCS.md                 # This file
├── README.md               # Public-facing overview and quick-start
├── context/                # Project context docs (architecture, progress tracker, etc.)
├── static/                 # Static assets (logo, etc.)
└── templates/
    └── index.html          # Single-page frontend (~3500 lines of HTML + CSS + JS)
```

### `app.py` — key functions

| Function | Purpose |
|---|---|
| `parse_movie_title(filename)` | Returns `(title, year)` from a filename |
| `get_resolution(filename)` | Returns resolution string (4K, 1080p, etc.) from filename |
| `probe_resolution(path)` | Reads true resolution from video stream via pymediainfo |
| `get_resolution_rank(res)` | Returns numeric rank 0–4 |
| `get_rip_source(filename)` | Returns rip type string |
| `get_rip_rank(rip_source)` | Returns numeric rank -3 to 9 |
| `build_maintenance_audit(candidates)` | Projects storage, upgrade, and identity maintenance queues from catalog records |
| `format_size(size)` | Formats bytes as human-readable string |
| `_auto_sync_plex()` | Auto-refreshes Plex cache if stale (>5 min TTL) |
| `_fetch_plex_library()` | Queries Plex API and returns `{path: metadata}` dict |
| `_country_flag(code)` | Converts ISO 3166-1 alpha-2 code to flag emoji (e.g. `'KR'` → `🇰🇷`) |
| `_ensure_tmdb_genres()` | Fetches genre list from TMDB once and caches in `_tmdb_genres` dict |
| `_load_config()` / `_save_config()` | Read/write `config.json` |

### `index.html` — key JS functions

| Function | Purpose |
|---|---|
| `scanMovies()` | Triggers duplicate scan, renders results |
| `openLowQuality()` | Fetches and renders Low Quality panel |
| `openLibrary()` | Fetches and renders Library panel |
| `openDashboard()` | Fetches stats and renders Dashboard |
| `prowlarrSearch(title, year)` | Searches Prowlarr, shows results panel |
| `openExplore()` | Opens the Explore Movies panel |
| `searchExplore()` | Runs a TMDB text search and shows card grid |
| `clearExploreSearch()` | Clears search results and restores tab view |
| `loadSearchMore()` | Appends next page of TMDB search results |
| `loadDiscover()` | Fetches TMDB Discover tab (selected list + genre) |
| `loadDiscoverMore()` | Appends next page of Discover results |
| `loadBrowse()` | Fetches Prowlarr Browse Indexers tab |
| `applyBrowseFilters()` | Filters/sorts Browse Indexers cards |
| `streamMovie(tmdb_id)` | Fetches IMDB ID then opens playimdb.com |
| `openTorrentModal(title, year)` | Searches Prowlarr and shows torrent results modal |
| `closeTorrentModal()` | Closes the Find Torrent modal |
| `togglePlot(el)` | Expands/collapses the plot summary on a card |
| `_discoverCardHtml(m, i)` | Renders a TMDB discover/search card as HTML string |
| `renderBrowseCards(results)` | Renders Browse Indexers card grid |
| `openPickMyMovie()` | Opens the Pick My Movie panel |
| `closePickMyMovie()` | Closes the Pick My Movie panel |
| `sendPickPrompt()` | Sends Ollama prompt, renders cards, fires library check in background |
| `_renderPickCards(results, libMap)` | Renders pick result cards; shows green badge + Play button for owned films |
| `_normPickTitle(t)` | Normalises a title for library matching (lowercase, no punct, no leading article) |
| `playFile(path)` | Opens a local file in the OS default video player via `/api/open-file` |
| `showToast(msg, isError)` | Shows bottom-right notification toast |
| `escHtml(s)` / `escAttr(s)` | XSS-safe HTML/attribute escaping helpers |

---

## 13. Troubleshooting

### App won't start
- Make sure Python is installed: `python --version`
- Install dependencies: `pip install -r requirements.txt`
- Check if port 5000 is already in use — close any other Flask apps

### No movies found after scan
- Check the folder path is correct and contains video files
- Supported extensions: `.mkv .mp4 .avi .m4v .mov .wmv .flv .ts .m2ts .iso`

### Prowlarr "not configured" or "cannot reach Prowlarr"
- Verify Prowlarr is running at the configured URL
- In Prowlarr → Settings → General, ensure **URL Base** is **blank** (not `/prowlarr`)
- Check the API key: Prowlarr → Settings → General → API Key

### Prowlarr returns no results
- Check that indexers are configured and enabled in Prowlarr
- Try a manual Prowlarr search first to confirm indexers are working
- Some indexers require a keyword to search — they will appear in the Indexer dropdown but return no Browse results. Use Find Torrent on a specific movie instead.

### Explore Torrents — "TMDB key not configured"
- Open ⚙ Settings → TMDB section → paste your key → Save & Test
- Get a free key at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)

### Explore Torrents — no posters / blank cards
- Posters are loaded from `image.tmdb.org`. If your network blocks it, posters won't load (the card still works without them).
- Check your TMDB key is valid: Settings → TMDB → Test.

### Stream button does nothing
- The Stream button fetches the IMDB ID from TMDB first. If TMDB returns no IMDB ID for that title, a toast error is shown.
- Ensure your TMDB key is configured (the Stream button requires TMDB).

### Language/country tag missing on Discover cards
- TMDB list endpoints return `original_language` (e.g. `'ko'` for Korean) but not `origin_country`. The app uses an internal `_LANG_COUNTRY` fallback map to convert language codes to country codes. For any language not in the map, the flag is omitted but the language name still shows.

### Plex connection fails (401 Unauthorized)
- Re-obtain your token — see [Section 5.6](#56-plex-integration)
- Use the **local Plex URL** (`http://localhost:32400`), not `app.plex.tv`

### Plex sync shows 0 files / low match rate
- Plex must have already scanned and matched the files
- Make sure your configured movies folder matches the library section Plex manages
- Check that Plex and the app use the same path format (drive letter casing is normalized automatically)

### Cannot delete a file (permission error)
- The file may be open in Plex Media Server — pause Plex, then try again
- The app automatically clears read-only flags but cannot override locks held by another process


---

## Changelog

### v1.5 (May 2026)

#### 🎬 Trending Panel — Browse Latest Movie Torrents
A brand new **Trending** panel lets you browse the latest and most-seeded movie torrents from your Prowlarr indexers, enriched with TMDB movie metadata.

- **New nav button** — "🎬 Trending" button added to the header bar.
- **YTS-style poster grid** — Movies displayed as cards with poster image, resolution badge, genres, TMDB rating, plot summary, seeder count, indexer name, and a Magnet link button.
- **Prowlarr integration** — Queries all enabled Prowlarr indexers for category 2000 (Movies), returns top 50 results sorted by seeders.
- **TMDB enrichment** — Posters, genres, ratings, and plot are fetched from The Movie Database API. Metadata is cached in memory to avoid repeat lookups.
- **Filters & sort** — Filter by quality (4K/1080p/720p/480p/Unknown) and indexer; sort by seeders, title, or year.
- **Manual refresh** — Refresh button re-fetches latest results from Prowlarr.
- **TMDB Settings** — New section in Settings to enter and test your TMDB API key. Get a free key at themoviedb.org/settings/api.
- **Zero changes to existing features** — All existing panels, workflows, and routes are completely untouched.

---

### v1.17 (May 2026)

#### Rename in Library Browser
Every row in the **Library Browser** now has a purple **✎ Rename** button, matching the Unmatched panel. Clicking it opens the rename modal pre-filled with the detected title and year. After saving, the row updates **in-place** immediately — no need to reopen the panel.

---

### v1.16 (May 2026)

#### Plex-Metadata Duplicate Detection
The Duplicate Scanner now uses `_plex_cache` title/year as the grouping key when available. Files matched by Plex to the same TMDB/TVDB entry are grouped as duplicates regardless of their filename. Files not in Plex still fall back to `parse_movie_title()` filename parsing.

#### Plex Bulk Mis-match Guard
Maintenance audit groups with more than four Plex-derived copies are re-bucketed by filename identity before they can be treated as duplicates. Legitimate duplicate pairs remain unaffected.

#### Fix Path — Whole Folder Move
`fix_path()` now counts video files in the parent folder before moving. If the parent contains only one video file, the **entire folder** is moved one level up (`os.rename(parent, dest_folder)`) so the folder name (e.g. `Batman (2010)`) is preserved. Plex uses the folder name as a metadata hint, so it re-matches cleanly after rescan. If the parent contains multiple video files, the original file-only move is used as a fallback.

#### Fix Path — Depth Threshold
Changed `fixable_path: rel_depth > 2` to `rel_depth > 1`. Files at depth 2 (one subfolder under the movies root) now also show the Fix Path button.

#### Fix All Paths Button
Added `fixAllPaths()` JS function and `#fix-all-paths-btn` button to the Unmatched panel toolbar. The button is shown automatically when `fixItems.some(it => it.fixable_path)`. Iterates all fixable items sequentially, updates button text with live progress, shows a summary toast, and auto-shows the Refresh button on completion.

---

### v1.15 (May 2026)

#### Color-Coded Welcome Page
The home screen now displays one line per panel button, each button name rendered in its exact matching nav-bar color (`#e5a00d` amber for Scan/Low Quality, `#74b9ff` blue for Library, `#fd79a8` pink for Dashboard, `#a29bfe` purple for Unmatched, `#636e72` grey for Settings). Descriptions are hidden automatically when a scan begins.

#### Play Button in All Panels
A green **▶ Play** button is now shown on every file row in the Duplicates, Low Quality, Library, and Unmatched panels. Clicking it POSTs `{path}` to the new `/api/open-file` route, which calls `os.startfile()` to open the file in the OS default video player. If the file is not found, a toast error is shown.

#### Manual Rename in Unmatched Panel
Each row in the Unmatched panel now has a purple **✎ Rename** button (`.btn-fix-rename` CSS class). Clicking it opens the `#rename-modal` pre-filled with `suggested_title` and `suggested_year` from the scan data. On confirm, POSTs `{path, title, year}` to the existing `/api/rename-file` route. The server appends quality tags (resolution, rip source), strips invalid Windows filename characters, renames the file, and triggers a Plex rescan. The Unmatched panel refreshes automatically on success.

#### Low Quality Panel Centering Fix
The `#lq-panel` CSS block was missing its selector line, causing the Low Quality panel to render left-aligned. The `#lq-panel {` selector has been restored so the panel is correctly centered on screen.

---

### v1.11 (May 2026)

#### Real File Resolution Detection
Resolution is now read directly from the video stream using **pymediainfo** (ships with a bundled `MediaInfo.dll` on Windows — no PATH setup, no separate install required). Files that have no resolution tag in their filename (e.g. `Movie.mkv`) now report their true stream resolution (`1080p`, `4K`, `720p`, etc.) instead of `Unknown`. Results are cached in `res_cache.json` next to `app.py`; each file is probed at most once and the cache survives app restarts.

#### Library Browser — Virtual Scroll
The Library panel now renders only the visible rows (~30 at any time). All 3,600+ rows are kept in a JavaScript array; the DOM is updated on scroll via `requestAnimationFrame`. The table opens instantly and is immediately interactive regardless of library size. A fixed-height spacer div maintains the correct scrollbar proportion. Checkbox selection is tracked by file path in a `Set` so selections survive rows leaving the DOM while scrolling.

#### Library Browser — Prowlarr Search Button
Added a **🔍 Search Prowlarr** button to every row in the Library panel, consistent with the Low Quality and Duplicates panels.

#### Library Load Cache
The `/api/library` response is cached server-side (`_library_cache`) for 5 minutes (`_LIBRARY_TTL = 300`). A cached response is served when: the same movies directory is configured, `force_plex` is not set, and the TTL has not expired. Cache is invalidated on: directory change (`set_config`), file deletion (`delete_file`), and Plex sync (`_auto_sync_plex`).

#### Scan Progress Status
A new `/api/library/status` endpoint exposes `_library_status` — a string updated every 50 files during the scan. The frontend polls this endpoint every 600 ms while the library request is in-flight and updates the loading bar message (`Reading metadata… 150 / 3600`).

#### Dependency: pymediainfo
`pymediainfo>=6.0.0` added to `requirements.txt`. `run.bat` updated to prefer `.venv\Scripts\python.exe` so all dependencies resolve from the virtual environment.

---

### v1.1 (May 2026)

#### New Feature — Unmatched Panel
A dedicated panel for video files buried in deep subfolder structures that Plex cannot match. Access it from the **🔧 Fix Unmatched** button in the header after loading Plex data.

Per-file actions:
- **Fix Path** — moves the file one level up in the folder hierarchy and triggers a Plex rescan
- **Match** — search Plex agents by title/year and apply the correct match manually (uses Plex's own agent search)
- **Delete** — sends the file to the Recycle Bin immediately

Panel controls:
- **Search** — filter files by filename or detected title in real time
- **Show** — filter by Plex status (All / Not in Plex / In Plex)
- **Sort** — Name A–Z, Name Z–A, Size (largest first), Size (smallest first)
- **Select All / Delete Selected** — bulk delete with Recycle Bin safety
- **Refresh List** — reloads the panel after Fix Path or Delete operations
- **Force Scan Plex** — triggers an immediate Plex section rescan and resets the metadata cache

Columns: Filename + quality badge + depth note · Size · Full folder path · Plex status · Actions

#### Improvements
- File sizes shown as human-readable strings (`2.3 GB`, `850 MB`) across all panels
- Full absolute folder path shown in Unmatched panel with word-wrap (no truncation)
- Refresh List button appears after any Fix Path or Delete to prompt a panel reload

#### Bug Fixes
- **False "Not in Plex" on Windows** — Plex returns paths with a lowercase drive letter (`e:\Movies\...`) but `os.walk` yields an uppercase letter (`E:\Movies\...`). Added `_norm()` helper (`os.path.normcase` + `os.path.normpath`) applied to every cache key and lookup. Files already in Plex now show the correct status.
- **Empty folder not cleaned up after Fix Path** — junk files (`desktop.ini`, `Thumbs.db`, `.DS_Store`, `folder.jpg`, `folder.png`) are silently removed before `os.rmdir()` so empty parent folders are properly deleted.

---

### v1.0 (initial release)
- Duplicate Scanner with quality ranking and Smart Clean
- Low Quality Scanner (< 1080p)
- Library Browser with filters, sort, and bulk delete
- Dashboard with charts (resolution, source, decade, Plex coverage)
- Plex integration (auto-cache, 5-minute TTL)
- Prowlarr integration (1080p+ torrent search)
- Recycle Bin and permanent delete modes
- Windows launcher (`run.bat`)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Requirements & Installation](#2-requirements--installation)
3. [Starting the App](#3-starting-the-app)
4. [Interface Tour](#4-interface-tour)
5. [Features](#5-features)
   - 5.1 [Duplicate Scanner](#51-duplicate-scanner)
   - 5.2 [Smart Clean](#52-smart-clean)
   - 5.3 [Low Quality Scanner](#53-low-quality-scanner)
   - 5.4 [Library Browser](#54-library-browser)
   - 5.5 [Dashboard](#55-dashboard)
   - 5.6 [Plex Integration](#56-plex-integration)
   - 5.7 [Prowlarr Integration](#57-prowlarr-integration)
   - 5.8 [Unmatched Panel](#58-unmatched-panel)
6. [Delete Modes](#6-delete-modes)
7. [How Titles Are Detected](#7-how-titles-are-detected)
8. [How Resolution Is Detected](#8-how-resolution-is-detected)
9. [How Rip Source Is Detected](#9-how-rip-source-is-detected)
10. [Configuration File](#10-configuration-file)
11. [API Reference](#11-api-reference)
12. [File Structure](#12-file-structure)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Overview

**My Library Organizer** is a Flask-based web app that scans a folder of movie files and gives you:

- **Duplicate detection** — finds multiple copies of the same film and identifies which one to keep
- **Smart Clean** — automated recommendations for which duplicates are safe to delete
- **Low Quality scanner** — lists every file below 1080p
- **Library browser** — full table view of every movie file with filters and bulk delete
- **Dashboard** — statistics, pie charts, and top-10 lists about your library
- **Plex integration** — cross-references your files with Plex metadata (title, year, genres)
- **Prowlarr integration** — search for 1080p+ torrent replacements directly from the app

All detection is **filename-based**, not metadata-based. This means the app works even when Plex cannot identify a file. Plex data is layered on top as an optional enrichment.

---

## 2. Requirements & Installation

### Prerequisites

| Software | Version | Purpose |
|---|---|---|
| Python | 3.10+ | Runtime |
| Flask | ≥ 3.0.0 | Web server |
| send2trash | ≥ 1.8.0 | Recycle Bin support |

### Install dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` contains:
```
flask>=3.0.0
send2trash>=1.8.0
```

No other external packages are required. The app uses only Python standard library modules (`os`, `re`, `stat`, `shutil`, `urllib`, `json`) for everything else.

---

## 3. Starting the App

### Windows (recommended)

Double-click **`run.bat`**.

This will:
1. Navigate to the app folder
2. Automatically open `http://localhost:5000` in your default browser
3. Start the Flask server

### Manual start

```bash
python app.py
```

Then open `http://localhost:5000` in your browser.

The server listens on port **5000** and is only accessible from your local machine.

---

## 4. Interface Tour

```
┌─────────────────────────────────────────────────────────────────┐
│  [logo]  My Library Organizer  [folder path] [Set Folder]       │
│          [Scan for Duplicates] [⚡ Smart Clean] [🔍 Low Quality] │
│          [📂 Library] [📊 Dashboard] [🎬 Plex] [⚙ Prowlarr]    │
├─────────────────────────────────────────────────────────────────┤
│  Duplicate Groups: 12   Extra Copies: 18   Wasted Space: 47 GB  │
├─────────────────────────────────────────────────────────────────┤
│  [🔁 Recycle Bin ●]  Delete mode: Recycle Bin                   │
├─────────────────────────────────────────────────────────────────┤
│  Search by movie title...  [12 of 45 groups]                    │
├─────────────────────────────────────────────────────────────────┤
│  ▼ The Dark Knight (2008)          2 copies · 8.2 GB wasted     │
│    ● The.Dark.Knight.2008.1080p.BluRay.mkv  [1080p] [Blu-ray]  │
│    ○ The.Dark.Knight.2008.720p.mkv          [720p] [Unknown]   │
└─────────────────────────────────────────────────────────────────┘
```

### Header controls

| Control | Description |
|---|---|
| Folder path input | Type or paste the full path to your movies directory |
| **Set Folder** | Saves the folder path (persists across restarts) |
| **Scan for Duplicates** | Scans the folder and shows duplicate groups |
| **⚡ Smart Clean** | Opens automated cleanup recommendations (appears after a scan) |
| **🔍 Low Quality** | Opens the low quality files panel |
| **📂 Library** | Opens the full library browser |
| **📊 Dashboard** | Opens the statistics dashboard |
| **🎬 Plex** | Opens Plex configuration |
| **⚙ Prowlarr** | Opens Prowlarr configuration |

---

## 5. Features

### 5.1 Duplicate Scanner

Click **Scan for Duplicates** to scan your movies directory recursively.

**How duplicates are found:**  
Files are grouped by a `(normalized_title, year)` key extracted from their filename. Two files are considered duplicates if they resolve to the same title and year — regardless of resolution, codec, or rip source.

**Within each group, files are ranked by quality (best first):**
1. Resolution rank (4K > 1080p > 720p > 480p > Unknown)
2. Rip source rank (BD Remux > Blu-ray > WEB-DL > WEBRip > DVDRip > CAMRip…)
3. File size (larger is assumed better for same resolution/source)

**The first file in each group is marked with a green stripe** — that is the best copy.

**Plex data** is shown automatically per file (if Plex is configured): matched files show the Plex title, year, and genre tags; unmatched files show an amber ⚠ No Plex data indicator.

**Stats bar** (appears after scan):
- **Duplicate Groups** — number of movies with more than one copy
- **Extra Copies** — total number of redundant files
- **Wasted Space** — combined size of all non-best copies

**Search bar:** Type to filter duplicate groups in real time by movie title.

**Deleting duplicates:**
- Check the boxes next to files you want to delete
- Click **Delete Selected** that appears on the group
- Or click **Delete** on a single file row
- Confirm in the dialog

**🔎 Search Prowlarr** — each file row has a Prowlarr search button to find a better replacement (requires Prowlarr configured).

---

### 5.2 Smart Clean

Click **⚡ Smart Clean** after a scan to get automated recommendations.

**Rules applied:**

| Situation | Action |
|---|---|
| File has lower resolution than best copy | ✅ Recommended for deletion |
| Same resolution but worse rip source AND size difference < 5% | ✅ Recommended for deletion |
| Same resolution but worse rip source AND size difference ≥ 5% | ⚠ Flagged for manual review (skipped) |
| File is the best copy in its group | Never flagged |

**Panel controls:**
- **Select All / Deselect All** — toggle all checkboxes
- **Delete Selected (N)** — deletes all checked items (respects Recycle Bin toggle)
- **Close** — dismiss without deleting

Skipped/manual-review items appear dimmed with a dashed border and cannot be checked.

---

### 5.3 Low Quality Scanner

Click **🔍 Low Quality** to list every video file in your library with a resolution below 1080p.

**Flagged resolutions:** 720p, 480p, Unknown  
**Not flagged:** 1080p, 4K

**Filter bar:**
- **Resolution** — filter to a specific resolution (720p, 480p, Unknown)
- **Source** — filter by rip type (WEBRip, DVDRip, etc.)
- **Sort by size** — Default (A-Z), Smallest first, Largest first

**Per-item controls:**
- Checkbox — select for bulk delete
- **🔎 Search Prowlarr** — opens a Prowlarr torrent search for that title (requires Prowlarr configured)

**Plex data** is shown per item automatically (if Plex is configured): matched files show the Plex title, year, and genre tags; unmatched files show an amber ⚠ No Plex data indicator.

**Select bar** (appears when items are checked):
- Select All / Deselect All
- **🗑 Delete Selected** — deletes all checked files

**📋 Copy Titles** — copies all (filtered) movie titles to clipboard for use elsewhere.

---

### 5.4 Library Browser

Click **📂 Library** to open a full table of every video file in your library.

**Columns:**
| Column | Description |
|---|---|
| ☐ | Checkbox for selection |
| Title | Detected movie title from filename + **🔎 Search Prowlarr** button |
| Resolution | 4K / 1080p / 720p / 480p / Unknown badge |
| Source | Rip type badge (Blu-ray, WEB-DL, etc.) |
| Size | Human-readable file size |
| Plex Title & Genres | Title/year from Plex + genre tags (if Plex configured) |
| Path | Full file path on disk |

**Filter controls:**
- **Search** — live text filter on title or filename
- **Resolution** dropdown
- **Source** dropdown
- **Plex** dropdown — All / Matched ✓ / No Plex data ⚠
- **Sort** — Name A→Z/Z→A, Size largest/smallest, Resolution best/worst, Source best/worst

**Unmatched Plex rows** are highlighted with an amber left border.

**Bulk delete:**
- Check rows (or use the header checkbox to select all visible)
- The select bar appears at the bottom showing count
- Click **🗑 Delete Selected** to delete

---

### 5.5 Dashboard

Click **📊 Dashboard** to open the statistics overlay.

**Stat cards:**
| Card | Description |
|---|---|
| Total Files | Number of video files scanned |
| Unique Titles | Distinct `(title, year)` keys |
| Library Size | Total disk space + average per file |
| Dup. Groups | Count of duplicate groups + extra copies % |
| Wasted Space | Space used by non-best duplicate copies |
| Low Quality | Count of files below 1080p + percentage |
| Plex Matched | Files successfully matched in Plex (after sync) |
| No Plex Data | Files with no Plex match (after sync) |

**Charts:**
- **Resolution donut** — distribution of 4K / 1080p / 720p / 480p / Unknown by file count
- **Source/Rip donut** — distribution of rip types
- **By Decade bar** — how many movies per decade (1970s, 1980s, …2020s)
- **Plex Coverage donut** — matched vs unmatched (only after Plex sync)

**Top 10 Largest Files** table — ranked list of your biggest files with resolution, source, and size.

---

### 5.6 Plex Integration

Click **🎬 Plex** to configure the connection.

**Configuration:**
| Field | Example |
|---|---|
| Plex URL | `http://localhost:32400` |
| X-Plex-Token | `xxxxxxxxxxxxxxxxxxxx` |

**How to find your Plex token:**

**Method 1 (easiest):** In Plex Web → click any movie → ··· → Get Info → View XML. The browser URL will contain `?X-Plex-Token=YOUR_TOKEN`.

**Method 2 (Windows file):** Open with Notepad:
```
C:\Users\[YourUsername]\AppData\Local\Plex Media Server\Preferences.xml
```
Find the `PlexOnlineToken` attribute.

**How matching works:**  
The app calls `GET /library/sections/{id}/all` for every movie library section. Plex returns the exact file path for each media item. The app builds a lookup table: `normalized_path → {plex_title, plex_year, plex_genres}`. Every scan (Duplicates, Low Quality, Library, Dashboard) **automatically refreshes** this cache if it is more than 5 minutes old — no manual sync step is needed.

This means:
- ✅ Works perfectly even if your filename is completely different from the movie title
- ✅ Handles foreign language filenames, year mismatches, typos in filenames
- ✅ Plex data appears in **all panels** — Duplicates, Low Quality, Library
- ⚠ Only works if Plex has analysed the file (i.e. the file is in a Plex-managed library section)

**Plex data is shown everywhere automatically** — no Sync button needed. When you open any panel, the app checks whether the Plex cache is stale and refreshes it in the background. After saving new Plex credentials, you can force an immediate refresh by saving and re-opening any panel.

**Match percentage** is shown in the Library panel header after data loads.

---

### 5.7 Prowlarr Integration

Click **⚙ Prowlarr** to configure the connection.

**Configuration:**
| Field | Example |
|---|---|
| Prowlarr URL | `http://localhost:9696` |
| API Key | Found in Prowlarr → Settings → General |

> **Important:** In Prowlarr → Settings → General, make sure the **URL Base** field is empty (blank), not `/prowlarr`.

**Searching for replacements:**  
In the Low Quality panel, each file has a **🔎 Search Prowlarr** button. Clicking it searches all your configured Prowlarr indexers for that movie title and shows results filtered to **1080p and above only**.

**Result filters:**
| Control | Description |
|---|---|
| Text search | Filter results by title keyword |
| Resolution dropdown | 4K / 1080p only (auto-populated from results) |
| Indexer dropdown | Filter to a specific indexer |
| Sort | Size largest/smallest, Seeders most/least, Resolution best, Title A→Z |
| Result count | Shows "24 of 87 results" when filtered |

**Per-result actions:**
- **🧲 Magnet** — opens the magnet link directly (opens your torrent client)
- **⬇ Torrent** — downloads the `.torrent` file

---

### 5.8 Unmatched Panel *(v1.1)*

Click **🔧 Fix Unmatched** in the header (visible once Plex data is loaded) to open the panel.

This panel finds video files that are buried inside subfolder structures deeper than expected — typically files in `Movies/Category/Subfolder/movie.mkv` instead of `Movies/Subfolder/movie.mkv`. Plex often fails to match these automatically.

**Panel columns:**

| Column | Description |
|---|---|
| ☐ | Checkbox for bulk selection |
| Filename & Quality | Detected filename + resolution badge + depth note (`depth X`) |
| Size | Human-readable file size (e.g. `2.3 GB`) |
| Folder | Full absolute path of the containing folder (wraps if long) |
| Plex Status | Whether the file is known to Plex (`In Plex (unmatched)` / `Not in Plex`) |
| Actions | Fix Path / Match / (fixable indicator) |

**Filter & sort controls:**

| Control | Description |
|---|---|
| Search | Live filter on filename or detected title |
| Show | All / Not in Plex / In Plex (unmatched) |
| Sort | Name A–Z, Name Z–A, Size (largest first), Size (smallest first) |

**Actions per file:**

- **Fix Path** — moves the file one directory level up (e.g. from `Movies/Action/Films/movie.mkv` to `Movies/Action/movie.mkv`), silently removes junk files from the vacated folder, deletes the folder if empty, then triggers a Plex rescan. The row is marked done and a **Refresh List** button appears.
- **Match** — opens a search dialog. Enter a title and optional year, click Search, and pick the correct Plex entry from the results. The app calls Plex's agent search and applies the match + triggers a Plex refresh on that item.
- **Not fixable** — shown when the file is already at depth 1 (no parent to move up to). Use Match instead.

**Bulk actions:**

- Check multiple rows (or use the header checkbox to select all visible)
- **🗑 Delete Selected** appears in the bar — sends all checked files to the Recycle Bin, marks rows done
- **↻ Refresh List** appears after any Fix Path or Delete — reloads the full panel from the server

**Force Scan Plex** — button in the panel header that triggers an immediate Plex library rescan (`/library/sections/{id}/refresh`) and resets the local metadata cache so newly matched files are picked up right away.

> **Tip:** After using Fix Path on several files, wait ~30 seconds for Plex to finish scanning, then click **Force Scan Plex** and finally **Refresh List** to see the updated Plex status.

---

## 6. Delete Modes

The **delete mode toggle** at the top of the main view controls how all deletions work throughout the app.

| Mode | Behaviour | Visual |
|---|---|---|
| **Recycle Bin** (default) | Moves file to Windows Recycle Bin via `send2trash`. Recoverable. | Green indicator |
| **Permanent Delete** | Calls `os.remove()`. Cannot be undone. Also removes the parent folder if it becomes empty of video files. | Red indicator |

**Security:** The app will only delete files inside the configured movies directory. Any attempt to delete a file outside that path is rejected with a 403 error.

**Read-only files:** The app automatically clears the read-only flag before deletion to handle files that Plex may have marked as read-only.

**Confirmation dialog:** Every delete action (single file, bulk, or Smart Clean) requires explicit confirmation in a modal dialog that also shows a permanent-delete warning when applicable.

---

## 7. How Titles Are Detected

The `parse_movie_title(filename)` function:

1. Strips the file extension
2. Finds a 4-digit year matching `19xx` or `20xx` using the pattern:  
   `[\.\s_\-\(\[\{]((19|20)\d{2})[\.\s_\-\)\]\}]`  
   (year must be surrounded by separators or brackets)
3. Everything before the year becomes the title
4. If no year is found, everything before the first quality keyword (`1080p`, `bluray`, `x264`, etc.) is used
5. Dots, underscores, and hyphens are replaced with spaces
6. The result is lowercased and stripped
7. Returns `(normalized_title, year)` — remakes with the same name but different years are kept separate

**Examples:**

| Filename | Detected Title | Year |
|---|---|---|
| `The.Dark.Knight.2008.1080p.BluRay.mkv` | `the dark knight` | `2008` |
| `Dune.Part.Two.(2024).WEB-DL.mkv` | `dune part two` | `2024` |
| `Scarface_1983_BDRemux.mkv` | `scarface` | `1983` |
| `some.random.movie.x264.mkv` | `some random movie` | `` |

---

## 8. How Resolution Is Detected

The `get_resolution(filename)` function checks the filename (lowercased) for these patterns in order:

| Resolution | Detected by |
|---|---|
| **4K** | `2160p`, `4k`, `uhd` |
| **1080p** | `1080p`, or `1080` surrounded by separators (`. - _ [ (`) |
| **720p** | `720p`, or `720` surrounded by separators |
| **480p** | `480p`, or `480` surrounded by separators |
| **Unknown** | None of the above matched |

**Resolution rank (used for sorting/comparison):**

| Resolution | Rank |
|---|---|
| 4K | 4 |
| 1080p | 3 |
| 720p | 2 |
| 480p | 1 |
| Unknown | 0 |

---

## 9. How Rip Source Is Detected

The `get_rip_source(filename)` function checks for keywords in the lowercased filename:

| Source | Keywords detected | Rank |
|---|---|---|
| BD Remux | `bdremux`, `bd remux` | 9 |
| Remux | `remux` | 8 |
| Blu-ray | `bluray`, `blu-ray` | 7 |
| BDRip | `bdrip` | 6 |
| WEB-DL | `web-dl`, `webdl` | 5 |
| WEBRip | `webrip`, `web-rip` | 4 |
| HDRip | `hdrip` | 3 |
| HDTV | `hdtv` | 2 |
| DVDRip | `dvdrip`, `dvd-rip` | 1 |
| DVDScr | `dvdscr`, `dvd-scr` | 0 |
| CAMRip | `camrip`, `cam-rip` | -1 |
| HDCAM | `hdcam` | -2 |
| Unknown | nothing matched | -3 |

---

## 10. Configuration File

Settings are automatically saved to `config.json` in the app folder whenever you click Save in any settings dialog.

```json
{
  "movies_dir": "E:\\Movies",
  "prowlarr_url": "http://localhost:9696",
  "prowlarr_key": "your-prowlarr-api-key",
  "plex_url": "http://localhost:32400",
  "plex_token": "your-plex-token"
}
```

This file is loaded on startup so all settings persist across restarts. You can also edit it manually in a text editor while the app is not running.

> **Note:** The Plex cache (path → metadata lookup table) is **not** saved to disk — it lives only in memory and resets on restart. The app automatically refreshes it (TTL: 5 minutes) whenever any panel is opened, so you rarely need to think about it. After a restart, the cache will be refreshed on the first scan or panel open.

---

## 11. API Reference

All endpoints return JSON. Base URL: `http://localhost:5000`

### Configuration

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/config` | Get current movies directory |
| POST | `/api/config` | Set movies directory `{"directory": "E:\\Movies"}` |

### Library

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/maintenance/audit` | Return catalog-backed storage, upgrade, and identity maintenance queues |
| GET | `/api/library` | Return all video files with metadata |
| GET | `/api/stats` | Return full library statistics (for Dashboard) |
| POST | `/api/delete` | Delete a file `{"path": "...", "trash": true}` |

### Plex

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/plex/config` | Get saved Plex URL and token |
| POST | `/api/plex/config` | Save Plex URL and token `{"url": "...", "token": "..."}` |
| GET | `/api/plex/test` | Test connection, returns library count |
| GET | `/api/plex/sync` | Fetch all file paths from Plex into memory cache |
| POST | `/api/fix-path` | Move a file one level up + trigger Plex rescan `{"path": "..."}` *(v1.1)* |
| POST | `/api/plex/force-scan` | Trigger Plex section rescan and reset local cache *(v1.1)* |
| GET | `/api/plex/match-search?rating_key=&title=&year=` | Search Plex agents for matching entries *(v1.1)* |
| POST | `/api/plex/match-apply` | Apply a Plex agent match `{"rating_key": "...", "guid": "..."}` *(v1.1)* |

### Prowlarr

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/prowlarr/config` | Get saved Prowlarr URL and key |
| POST | `/api/prowlarr/config` | Save Prowlarr URL and key `{"url": "...", "key": "..."}` |
| GET | `/api/prowlarr/test` | Test connection, returns indexer count |
| GET | `/api/prowlarr/search?q=title` | Search for torrents, returns 1080p+ results only |

---

## 12. File Structure

```
filebotx/
├── app.py                  # Flask backend — all routes and logic
├── run.bat                 # Windows launcher (opens browser + starts server)
├── requirements.txt        # Python dependencies
├── config.json             # Auto-created — persists all settings
├── DOCS.md                 # This file
├── static/
│   └── logo.svg            # App logo (white "db" in circle, 64×64)
└── templates/
    └── index.html          # Single-page frontend (HTML + CSS + JS)
```

### `app.py` — key functions

| Function | Purpose |
|---|---|
| `parse_movie_title(filename)` | Returns `(title, year)` from a filename |
| `get_resolution(filename)` | Returns resolution string (4K, 1080p, etc.) |
| `get_resolution_rank(filename)` | Returns numeric rank 0–4 |
| `get_rip_source(filename)` | Returns rip type string |
| `get_rip_rank(rip_source)` | Returns numeric rank -3 to 9 |
| `build_maintenance_audit(candidates)` | Projects storage, upgrade, and identity maintenance queues from catalog records |
| `format_size(size)` | Formats bytes as human-readable string |
| `_auto_sync_plex()` | Auto-refreshes Plex cache if stale (>5 min TTL), called by every scan endpoint |
| `_fetch_plex_library()` | Queries Plex API and returns `{path: metadata}` dict |
| `_load_config()` / `_save_config()` | Read/write `config.json` |

### `index.html` — key JS functions

| Function | Purpose |
|---|---|
| `scanMovies()` | Triggers duplicate scan, renders results |
| `renderDuplicates()` | Renders duplicate group cards with Plex data + Prowlarr buttons |
| `filterGroups()` | Live search filter on duplicate results |
| `openSmartClean()` | Fetches and renders Smart Clean panel |
| `smartProceed()` | Deletes all checked Smart Clean items |
| `openLowQuality()` | Fetches and renders Low Quality panel |
| `lqDeleteSelected()` | Bulk delete from Low Quality panel |
| `openLibrary()` | Fetches and renders Library panel |
| `applyLibFilters()` | Filters/sorts the library table |
| `renderLibTable(items)` | Renders library rows with Plex data + Prowlarr buttons |
| `syncPlexLibrary()` | Force-refreshes Plex cache (called after saving new config) |
| `openDashboard()` | Fetches stats and renders Dashboard |
| `renderDashboard(data)` | Renders stat cards + Chart.js charts |
| `prowlarrSearch(title)` | Searches Prowlarr, shows results panel |
| `applyPrFilters()` | Filters/sorts Prowlarr results |
| `doGenericDelete()` | Handles all delete confirmations (LQ + Library) |
| `showToast(msg, isError)` | Shows bottom-right notification |

---

## 13. Troubleshooting

### App won't start
- Make sure Python is installed: `python --version`
- Make sure dependencies are installed: `pip install -r requirements.txt`
- Check if port 5000 is already in use — close any other Flask apps

### No movies found after scan
- Check the folder path is correct and actually contains video files
- Supported extensions: `.mkv .mp4 .avi .m4v .mov .wmv .flv .ts .m2ts .iso`
- Make sure the folder is accessible (not a network path that's offline)

### Duplicate groups missing expected files
- Files must share the same detected title and year to be grouped together
- Check that both filenames contain the year in a parseable format
- Files with completely unrecognisable names may be skipped

### Prowlarr "not configured" or "cannot reach Prowlarr"
- Verify Prowlarr is running and accessible at the configured URL
- In Prowlarr → Settings → General, make sure **URL Base** is **blank** (not `/prowlarr`)
- Check the API key: Prowlarr → Settings → General → API Key

### Prowlarr returns no results
- Check that your indexers are configured and enabled in Prowlarr
- Try searching manually in Prowlarr first to confirm indexers are working
- Some indexers may have rate limits — wait a minute and try again

### Plex connection fails (401 Unauthorized)
- Your token is wrong or expired — re-obtain it (see [Section 5.6](#56-plex-integration))
- Make sure you're using the **local Plex URL** (`http://localhost:32400`), not `app.plex.tv`

### Plex sync shows 0 files / low match rate
- Make sure the movies in Plex are from the same library section as your configured movies folder
- Plex must have **already scanned and matched** the files — unmatched items in Plex will not appear
- If Plex stores files on a mapped network drive, the path Plex reports may differ from what the app sees — both must use the same path format

### Cannot delete a file (permission error)
- The file may be open in Plex Media Server
- Pause/stop Plex, then try again
- The app automatically clears read-only flags, but cannot override locks held by another process

### Delete button does nothing
- Check that the app started without JavaScript errors (open browser DevTools → Console)
- Make sure you're on the same machine as the server (the app only accepts requests from localhost)
