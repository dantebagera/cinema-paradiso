# My Library Organizer — Documentation

> A local web application for managing, cleaning, and enriching a Plex movie library.  
> Runs entirely on your own machine — no cloud, no accounts, no internet required (except for Prowlarr search).

**Version 1.0**

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
