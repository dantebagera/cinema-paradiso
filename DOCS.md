# My Library Organizer — Documentation

> A local web application for managing, cleaning, and enriching a Plex movie library.  
> Runs entirely on your own machine — no cloud, no accounts, no internet required (except for Prowlarr search).

**Version 1.11** — May 2026

---

## Changelog

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
| GET | `/api/duplicates` | Scan and return duplicate groups + stats |
| GET | `/api/library` | Return all video files with metadata |
| GET | `/api/low-quality` | Return files with resolution below 1080p |
| GET | `/api/smart-scan` | Return Smart Clean recommendations |
| GET | `/api/stats` | Return full library statistics (for Dashboard) |
| POST | `/api/delete` | Delete a file `{"path": "...", "trash": true}` |

### Plex

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/plex/config` | Get saved Plex URL and token |
| POST | `/api/plex/config` | Save Plex URL and token `{"url": "...", "token": "..."}` |
| GET | `/api/plex/test` | Test connection, returns library count |
| GET | `/api/plex/sync` | Fetch all file paths from Plex into memory cache |
| GET | `/api/fix-unmatched` | Return files in deep subfolders that Plex may not match *(v1.1)* |
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
| `scan_duplicates(movies_dir)` | Returns grouped duplicates + wasted-space stats |
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
