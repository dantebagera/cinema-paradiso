# 🎬 10K Movie Library Organizer

A local web application for managing, cleaning, and enriching a large Plex movie library. Runs entirely on your own machine — no cloud, no subscriptions, no data leaves your PC.

Built with Python + Flask. Designed for libraries with thousands of files.

---

## Screenshots

> Duplicate Scanner · Low Quality Scanner · Library Browser · Dashboard

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
