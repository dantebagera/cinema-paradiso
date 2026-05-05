# 🎬 10K Movie Library Organizer

A local web application for managing, cleaning, and enriching a large Plex movie library. Runs entirely on your own machine — no cloud, no subscriptions, no data leaves your PC.

Built with Python + Flask. Designed for libraries with thousands of files.

**Current version: v1.1**

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
| 📂 **Library Browser** | Full table view of your entire library with search, filters, sort, and bulk delete |
| 📊 **Dashboard** | Library statistics with charts — resolution breakdown, rip source distribution, movies by decade, and Plex coverage |
| 🎬 **Plex Integration** | Automatically cross-references your files with Plex metadata. Shows Plex title, year, and genres on every file across all panels |
| 🔎 **Prowlarr Integration** | Search for 1080p+ torrent replacements directly from the Duplicates, Low Quality, and Library panels |
| 🗂️ **Unmatched Panel** *(v1.1)* | Finds files buried in deep subfolders that Plex can't match. Fix Path moves them up one level; Match lets you manually link them to a Plex entry |

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
