# 🎬 10K Movie Library Organizer

> **Alternative to Plex DupeFinder** · **Bulk Plex organizer** · **How to fix unmatched Plex files** · **Plex duplicate movie cleaner** · **Large movie library manager for Plex**

A local web application for managing, cleaning, and organizing a large Plex movie library on Windows. Runs entirely on your own machine — no cloud, no subscriptions, no data leaves your PC.

Built with Python + Flask. Designed for libraries with thousands of files — tested with 10,000+ movies.

**Current version: v1.15** — May 2026

---

## What problems does this solve?

- **"My Plex library has hundreds of duplicate movies"** — the Duplicate Scanner finds every film you own more than once and tells you exactly which copy to keep based on resolution, rip source, and file size.
- **"Plex won't match some of my movies"** — the Unmatched Panel finds files buried in deep subfolder structures that Plex can't identify, and lets you fix the path or manually match them to the correct Plex entry.
- **"I have hundreds of 720p/480p movies I want to replace"** — the Low Quality Scanner lists every sub-1080p file so you can prioritize upgrades.
- **"I want to see what's in my library without opening Plex"** — the Library Browser gives you a fully searchable, sortable table of every file with metadata.
- **"How do I bulk delete bad movie copies from Plex?"** — Smart Clean automatically flags the inferior duplicates for one-click bulk deletion, using the Windows Recycle Bin so nothing is gone permanently.

---

## Screenshots

> Duplicate Scanner · Low Quality Scanner · Library Browser · Dashboard · Unmatched Panel

---

## Features

| Feature | Description |
|---|---|
| 🔍 **Duplicate Scanner** | Finds every movie you own more than once. Ranks copies by resolution, rip source, and size so you always know which one to keep |
| ⚡ **Smart Clean** | One-click automated recommendations — safely flags inferior duplicates for deletion without touching anything you should keep |
| 📉 **Low Quality Scanner** | Lists every file below 1080p so you can find and replace your worst-quality movies |
| 📂 **Library Browser** | Full table view of your entire library with search, filters, sort, and bulk delete. Virtual scroll keeps it instant even with 3,000+ files |
| 📊 **Dashboard** | Library statistics with charts — resolution breakdown, rip source distribution, movies by decade, and Plex coverage |
| 🎬 **Plex Integration** | Automatically cross-references your files with Plex metadata. Shows Plex title, year, and genres on every file across all panels |
| 🔎 **Prowlarr Integration** | Search for 1080p+ torrent replacements directly from the Duplicates, Low Quality, and Library panels |
| 🗂️ **Unmatched Panel** *(v1.1)* | Finds files buried in deep subfolders that Plex can't match. Fix Path moves them up one level; Match lets you manually link them to a Plex entry |

---

## Who is this for?

- Plex users with a **large local movie collection** (hundreds to tens of thousands of files)
- Anyone who has accumulated **duplicate movie files** over years of downloading
- Users whose **Plex library has many unmatched or unidentified files**
- People who want to **clean up their movie folder** without losing anything accidentally
- Users looking for a **self-hosted, offline alternative** to online library managers
- Anyone who wants to **fix Plex metadata mismatches** without editing files or folder names manually

> **Related searches:** Plex movie library cleaner · Plex duplicate finder alternative · fix Plex unmatched movies · bulk delete Plex duplicates · Plex library organizer tool · movie folder cleanup Windows · how to remove duplicate movies from Plex · Plex 720p movie list · find low quality movies in Plex · Plex unmatched files fixer · local movie database manager · self-hosted media library tool

---

## What's New in v1.15

### Color-Coded Welcome Page
The home screen now shows a description for every panel button, each label styled in its exact matching nav-bar color — so new users immediately understand what each button does without opening anything.

### Play Button in All Panels
Every file row in the **Duplicates**, **Low Quality**, **Library**, and **Unmatched** panels now has a green **▶ Play** button. Clicking it opens the file in the system default video player (VLC, MPC-HC, etc.) via the new `/api/open-file` route.

### Manual Rename in Unmatched Panel
Each row in the Unmatched panel now has a purple **✎ Rename** button. Clicking it opens a modal pre-filled with the detected title and year. After editing, the file is renamed on disk — quality tags (resolution, rip source) are appended automatically. The panel refreshes instantly on success.

### Low Quality Panel Centering Fix
Fixed a missing CSS selector (`#lq-panel`) that caused the Low Quality panel to sit left-aligned instead of centered. The panel is now correctly centered on screen.

---

## What's New in v1.11

### Real File Resolution Detection
Resolution is now read directly from the video stream using **pymediainfo** (bundled `MediaInfo.dll` on Windows — no separate install). Files without a resolution tag in their filename (`Movie.mkv`) now show their true resolution (`1080p`, `4K`, etc.) instead of `Unknown`. Probed results are cached to disk in `res_cache.json` so each file is only ever probed once — restarts are fast from the second run onward.

### Library Browser — Virtual Scroll
The Library panel now uses **virtual scroll**: only ~30 rows exist in the DOM at any time regardless of library size. Opening a 3,600-file library is instant and fully interactive from the first frame. Scrolling swaps rows in and out smoothly. Checkboxes and bulk-delete work correctly across the full list via path-based selection tracking.

### Library Browser — Prowlarr Search Button
Every row in the Library panel now has a **🔍 Search Prowlarr** button, matching the existing buttons in the Low Quality and Duplicates panels.

### Library Load Cache
The Library panel result is cached server-side for 5 minutes. Closing and reopening the panel within that window is instant — no rescan. Cache is automatically invalidated when the movies directory changes, a file is deleted, or a Plex sync runs.

### Scan Progress Status
The loading bar now shows live progress while the library is scanning: `Reading metadata… 150 / 3600`. Users with large libraries can see exactly where the scan is up to instead of staring at a spinner.

---

## What's New in v1.1

### New Feature — Unmatched Panel
A dedicated panel for files that Plex cannot match because they are buried in deep subfolder structures. Per file you can:
- **Fix Path** — moves the file one level up and triggers a Plex rescan
- **Match** — search Plex agents by title/year and apply the correct match manually
- **Delete** — send directly to the Recycle Bin

Panel also shows file size, full folder path, Plex status, and quality badge per file.

### Improvements
- **Sort controls** in the Unmatched panel — sort by Name A–Z/Z–A or Size largest/smallest
- **Delete Selected** bulk action in the Unmatched panel
- **Full folder path** displayed with word-wrap (no more truncated paths)
- **Refresh List** button appears after Fix Path or Delete to reload the panel
- **Human-readable file sizes** shown in all panels (e.g. `2.3 GB`)
- **Force Scan Plex** button to trigger an immediate Plex rescan and reset the metadata cache

### Bug Fixes
- **False "Not in Plex" on Windows** — fixed a Windows path case mismatch where Plex returns paths with a lowercase drive letter (`e:\Movies\...`) while `os.walk` yields an uppercase drive letter (`E:\Movies\...`). Added `_norm()` helper using `os.path.normcase()` so all cache key lookups are case-insensitive. Files already matched in Plex now correctly show their Plex status.
- **Empty folder not removed after Fix Path** — common junk files (`desktop.ini`, `Thumbs.db`, `.DS_Store`, `folder.jpg/png`) are now silently removed before attempting `os.rmdir()` so empty folders are cleaned up properly.

---

## Requirements

- Python 3.10+
- Windows (tested on Windows 10/11)
- [Plex Media Server](https://www.plex.tv/) (optional, for metadata enrichment)
- [Prowlarr](https://prowlarr.com/) (optional, for torrent searching)

---

## Installation

```bash
git clone https://github.com/dantebagera/10k-movie-library-organizer.git
cd 10k-movie-library-organizer
pip install -r requirements.txt
```

---

## Usage

**Windows — double-click `run.bat`**

Or manually:

```bash
python app.py
```

Then open **http://localhost:5000** in your browser.

---

## How It Works

All detection is **filename-based** — no external APIs required to scan duplicates or find low quality files. It works on any movie folder regardless of naming convention.

**Plex integration** is layered on top: if you provide your Plex URL and token, the app automatically looks up each file in Plex and displays the real title, year, and genres. It refreshes the cache every 5 minutes in the background.

**Duplicate grouping** works by extracting a normalised `(title, year)` key from each filename. Files that resolve to the same title and year are grouped together and ranked by quality (4K > 1080p > 720p, BD Remux > Blu-ray > WEB-DL > DVDRip, etc.).

---

## Configuration

Settings are saved automatically to `config.json`:

```json
{
  "movies_dir": "E:\\Movies",
  "plex_url": "http://localhost:32400",
  "plex_token": "your-token-here",
  "prowlarr_url": "http://localhost:9696",
  "prowlarr_key": "your-api-key-here"
}
```

---

## Delete Safety

- **Recycle Bin mode** (default) — moves files to the Windows Recycle Bin via `send2trash`. Fully recoverable.
- **Permanent mode** — irreversible. Requires confirmation.
- The app will only delete files inside your configured movies directory. Any path outside it is rejected.

---

## Tech Stack

- **Backend:** Python 3, Flask
- **Frontend:** Vanilla HTML/CSS/JavaScript (no frameworks)
- **Charts:** Chart.js 4
- **Delete:** send2trash
- **External APIs:** Plex HTTP API, Prowlarr HTTP API

---

## License

MIT

---

## Requirements

- Python 3.10+
- [Plex Media Server](https://www.plex.tv/) (optional, for metadata enrichment)
- [Prowlarr](https://prowlarr.com/) (optional, for torrent searching)

---

## Installation

```bash
git clone https://github.com/dantebagera/10k-movie-library-organizer.git
cd 10k-movie-library-organizer
pip install -r requirements.txt
```

---

## Usage

**Windows — double-click `run.bat`**

Or manually:

```bash
python app.py
```

Then open **http://localhost:5000** in your browser.

---

## How It Works

All detection is **filename-based** — no external APIs required to scan duplicates or find low quality files. It works on any movie folder regardless of naming convention.

**Plex integration** is layered on top: if you provide your Plex URL and token, the app automatically looks up each file in Plex and displays the real title, year, and genres. It refreshes the cache every 5 minutes in the background.

**Duplicate grouping** works by extracting a normalised `(title, year)` key from each filename. Files that resolve to the same title and year are grouped together and ranked by quality (4K > 1080p > 720p, BD Remux > Blu-ray > WEB-DL > DVDRip, etc.).

---

## Configuration

Settings are saved automatically to `config.json`:

```json
{
  "movies_dir": "E:\\Movies",
  "plex_url": "http://localhost:32400",
  "plex_token": "your-token-here",
  "prowlarr_url": "http://localhost:9696",
  "prowlarr_key": "your-api-key-here"
}
```

---

## Delete Safety

- **Recycle Bin mode** (default) — moves files to the Windows Recycle Bin via `send2trash`. Fully recoverable.
- **Permanent mode** — irreversible. Requires confirmation.
- The app will only delete files inside your configured movies directory. Any path outside it is rejected.

---

## Tech Stack

- **Backend:** Python 3, Flask
- **Frontend:** Vanilla HTML/CSS/JavaScript (no frameworks)
- **Charts:** Chart.js 4
- **Delete:** send2trash
- **External APIs:** Plex HTTP API, Prowlarr HTTP API

---

## License

MIT
