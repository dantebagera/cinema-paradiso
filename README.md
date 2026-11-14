# Cinema Paradiso

**A desktop home for your movie and TV library, discovery, IPTV, playback, downloads, and AI-assisted curation.**

Cinema Paradiso runs locally on Windows. Browse the media you own, discover what to watch next, follow movies and TV episodes, review downloads, repair metadata, and play titles through the native player or configured streaming sources. Connect Plex, TMDB, Prowlarr, Xtream IPTV, Ollama, or ChatGPT for the features you want.

**Latest release: [v3.0.0 — November 15, 2026](https://github.com/dantebagera/cinema-paradiso/releases/tag/v3.0.0)**

[Download Windows portable ZIP](https://github.com/dantebagera/cinema-paradiso/releases/download/v3.0.0/Cinema-Paradiso-3.0.0-Portable.zip) · [SHA-256 checksum](https://github.com/dantebagera/cinema-paradiso/releases/download/v3.0.0/Cinema-Paradiso-3.0.0-Portable.zip.sha256) · [What's new](#whats-new-in-v300) · [Installation](#installation) · [Changelog](CHANGELOG.md)

Your catalog and settings stay on your machine. Configured online integrations contact their respective services; optional ChatGPT features send only their permitted task evidence.

## What's new in v3.0.0

This is the first stable release of the work developed through the 3.0 betas. Compared with v2.8.5, CP adds a complete TV workflow, ChatGPT integration, a redesigned desktop, substantially expanded IPTV matching, richer movie details, and new playback and streaming choices.

### TV becomes a full part of Cinema Paradiso

- **TV Library and Discover:** browse series, seasons, episodes, cast, and available files, with TV-specific search, filters, lists, poster editing, and bulk actions.
- **Import an existing TV collection:** discover show folders, assign series identities, match episodes, and review ambiguous or conflicting files in TV Maintenance. Movie and TV catalogs remain separate.
- **Follow missing and future episodes:** save the scope and quality you want, then explicitly Start the task. Persistent tasks search for missing releases and newly aired episodes, retain their progress, and expose review and cancellation controls.
- **Season-pack support:** eligible missing-season tasks search complete season packs as well as individual episodes, while checking episode coverage, identity, and quality.
- **Download and import review:** inspect candidate releases before manual submission; track transfer, verification, and Library publication separately, with recovery for interrupted imports.
- **TV playback and Continue Watching:** play the selected local episode version and retain episode progress in the TV catalog.

### A redesigned desktop and Home

- Reworked sidebar, workspace headers, search controls, filters, cards, lists, dialogs, and selection bars across Movies, TV, IPTV, and Settings.
- Shared buttons, badges, tabs, fields, empty states, and dialog components give common actions a consistent appearance. The Style Guide renders those same production components.
- A projector-themed Home header and revised dashboard bring Continue Watching, followed releases, trailers, Trending, and Upcoming together.
- Following has clearer filters, availability counts, expanded details, and a Download action that opens review for available movies.
- Home retains resolved content during refresh; Trending and Upcoming can finish independently. Upcoming is a preview of up to 20 eligible films, with View all opening Discover.
- Continue Watching adds View card and keeps only one action menu open at a time. Shared horizontal rails and reveal-on-interaction scrollbars improve navigation.

### ChatGPT alongside Ollama

- Choose ChatGPT or Ollama in Settings. ChatGPT has account sign-in, model selection, connection checks, and feature-readiness messages; existing Ollama workflows remain available.
- **Pick My Movie:** request a number of recommendations, inspect progress, and continue saved ChatGPT jobs. CP verifies suggested titles against TMDB and reports shortfalls instead of filling the list with duplicates or uncertain matches.
- **AI Control:** ask for catalog information or prepare Movie, TV, and IPTV actions. Changes use the corresponding native review and confirmation workflows.
- **Movie Smart Match:** ChatGPT can assist with identity proposals, while CP checks candidates and presents changes for review.
- **IPTV assistance:** ChatGPT can classify listings and suggest candidate identities, including the resumable bulk workflow below.
- **Explicit evidence permissions:** Movie identity hints and IPTV title samples have separate opt-in settings. Full file paths, stream URLs, and credentials are excluded from model evidence.

### A larger IPTV metadata and browsing workflow

- Manage multiple configured Xtream providers with separate catalogs, lists, history, and metadata state.
- Improved first-pass enrichment checks provider IDs and falls back to title/year matching when needed. Accepted identities and manual locks are protected during catalog refresh.
- Maintenance brings unresolved titles into one Unmatched queue, with filters and consistent selection for follow-up work.
- Bulk ChatGPT matching has saved progress, request budgets, pause/continue/cancel controls, and recovery after interruption. New bulk jobs automatically apply independently verified matches; uncertain results remain for review.
- Continue can resume eligible unfinished work after provider sync. Saved search-limited proposals can be rechecked against TMDB without asking ChatGPT to interpret them again.
- Cast portraits browse movies in the selected provider. The separate Filmography action opens full Movie Discover credits, including titles outside that provider.
- Discover cards can show IPTV availability from saved provider catalogs. A badge means the title is listed in the saved catalog; it is not a live stream-health check.

### More useful movie cards and discovery

- **Rotten Tomatoes ratings through Plex:** critic and audience scores appear when Plex supplies them. Saved scores for owned movies remain usable offline; missing scores do not block cards or become invented ratings.
- **Movie awards:** verified film wins appear on supported cards and detail views, with navigation to winning films and role-specific people results.
- **Collections and related movies:** richer collection browsing, owned-part counts, Recommended/Similar rails, and View all navigation.
- **People and filmography:** contextual credit browsing and a separate full-filmography action, with return navigation that restores the originating browse state.
- **Arabic movie defaults:** Arabic films use their Arabic presentation by default where metadata is available, with English still selectable.
- **Upcoming date filtering:** Home and Discover exclude titles whose known release date is already in the past.

### More playback and streaming choices

- Native player **0.1.37**, up from **0.1.26** in v2.8.5, adds playlists, Previous/Next file controls, visible settings, and a cancellable Up next countdown.
- Episode queues keep season order and stop at a missing immediate next episode rather than silently skipping it. Playlist controls are hidden for a single item.
- Native-player menu dismissal, scrolling, Windows window controls, and Unicode file-path handling were improved.
- Movie Stream opens a source chooser across Home, Library, Discover, and Lists. Configured IPTV sources remain selectable even when web streaming is disabled.
- Web streaming supports the saved StreamIMDB or VSEmbed choice and custom templates; TV keeps exact episode targeting.
- **YouTube movie search:** search from Movie Stream using the movie title and runtime. Results must be within ±5% of the known runtime; Arabic films use Arabic search names. Search more and optional Use GPT controls are available. Ordinary search does not invoke GPT, and a duration match alone does not prove that a video is the correct film.

### Loading, downloads, and recovery

- Shared artwork scheduling loads visible posters before backdrops and defers offscreen artwork.
- Library search coalesces superseded requests; TV prioritizes visible-card enrichment. List filtering and sorting happen before pagination.
- Completed Movie downloads refresh Library and Following after catalog publication. Import retries retain progress instead of treating transfer completion as proof that a movie is ready.
- Hybrid torrent identifiers receive more reliable ownership and recovery handling.
- Embedded qBittorrent Content and Peers requests preserve their query parameters.

For the version history, see [CHANGELOG.md](CHANGELOG.md). For feature decisions, code ownership, and dated verification evidence, see the [CP knowledge index](docs/README.md).

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

### TV Library, Discover, and Follow

TV has its own series, season, episode, file, and playback records. Browse TV Discover, import existing folders, review unmatched files, manage TV lists, and play available episodes. Follow tasks can cover missing or future episodes; save the task and explicitly Start it. Manual download controls open release review without creating a continuing Follow task.

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
- **Pick My Movie:** ChatGPT or Ollama recommendations enriched with TMDB metadata and archive-aware actions.
- **AI Control handoff:** AI-created find and list results reuse the same card-ready metadata and list workflows used by Discover.

### AI Control

AI Control is a review workspace for natural-language requests, using the selected ChatGPT or Ollama provider. Available capabilities depend on the provider and feature readiness.

- Supports find, create-list, download-planning, and delete-planning flows.
- Shows a preview plan before any action runs.
- Requires reviewed plan IDs for execution and extra confirmation for large delete plans.
- Uses trusted Prowlarr indexers for download planning.
- Keeps blocked rows visible with the reason they were blocked.
- Never runs a vague command automatically; it asks for clarification.

### Downloads

Downloads uses the original qBittorrent WebUI inside Cinema Paradiso. The embedded client is isolated from any qBittorrent installation already registered as the operating system's default torrent client.

- The v3.0.0 portable ZIP includes qBittorrent 5.2.2, FFmpeg 8.1.1, and native player 0.1.37.
- Cinema Paradiso submissions are tagged `cinema-paradiso` and download to an incomplete staging folder.
- Removing an unfinished CP submission in qBittorrent is treated as a normal cancellation; CP does not move its data or update the catalog.
- Transfer completion, moving the unchanged payload, torrent cleanup, and Library publication are separate steps. A completed transfer can still require import or metadata review; recovery reuses the existing job.
- A blank movie destination uses the first configured library folder.
- The incomplete folder must remain outside every movie library so Plex and Cinema Paradiso cannot index partial files.
- Settings can switch torrent handling back to the operating system's default client.
- Settings can update the isolated portable qBittorrent runtime from the latest official GitHub release without installing or changing the system torrent client.

### IPTV

IPTV is a provider-agnostic Xtream workspace, separate from the owned Movie and TV catalogs.

- Supports multiple configured Xtream providers, one selected at a time, with Live TV, Movies, Series, Favorites, provider-scoped custom lists, watch history, and provider categories in provider order.
- Stores catalogs in provider-scoped IPTV databases under the user-data folder. IPTV titles never become owned library records.
- Keeps IPTV Favorites and custom lists separate from Cinema Paradiso Movie Lists, with mixed channels, movies, and series plus manual ordering.
- Retains a saved item's title and artwork when it disappears from the current provider catalog, while marking it unavailable instead of silently deleting it.
- Keeps saved credentials on the Flask backend and returns only redacted configuration state to React.
- Loads movie and series details lazily from the provider, including Arabic text without requiring Ollama or another AI service.
- Uses tokenized local playback sessions. FFmpeg receives a loopback URL rather than the credential-bearing Xtream URL.
- Remuxes provider streams to local HLS without transcoding by default. Unsupported source codecs can still fail in the browser.
- Cinema Paradiso does not provide IPTV subscriptions or content. Users connect their own authorized provider account in Settings.

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
- Xtream IPTV server and credentials
- Ollama URL/model
- ChatGPT accounts, selected model, recommendation count, and evidence permissions
- TV library roots, acquisition profiles, and Follow settings
- Web streaming provider/templates, native-player preferences, and YouTube configuration

User lists, Watched and Watchlist states, edited collections, followed releases, manual metadata matches, metadata corrections, identity audit state, and poster overrides are persistent user data. TMDB detail caches are rebuildable cache.

---

## Requirements

- Windows 10/11 x64 for the bundled qBittorrent portable release
- Python 3.10+
- Node.js 18+ for building the React frontend
- Optional: Plex Media Server
- Optional: Prowlarr
- Optional: TMDB API key
- Optional: Ollama or a connected ChatGPT account for AI features
- Optional: Xtream IPTV subscription
- FFmpeg for integrated IPTV playback (included in the v3.0.0 portable ZIP)

---

## Installation

### Windows Quick Start

1. Install Python 3.10+ and Node.js 18+ with npm if they are not already available.
2. Download [Cinema-Paradiso-3.0.0-Portable.zip](https://github.com/dantebagera/cinema-paradiso/releases/download/v3.0.0/Cinema-Paradiso-3.0.0-Portable.zip) and its [SHA-256 file](https://github.com/dantebagera/cinema-paradiso/releases/download/v3.0.0/Cinema-Paradiso-3.0.0-Portable.zip.sha256).
3. Verify the ZIP, extract it into its own folder, and run `run.bat`.
4. The launcher creates a Python environment, installs dependencies, builds the frontend, starts Flask, and opens [http://localhost:5000](http://localhost:5000). Keep its console open to see errors.
5. Open Settings to configure your library folders and the integrations you need.

The portable ZIP includes native player 0.1.37, qBittorrent 5.2.2, and FFmpeg 8.1.1. It does **not** include Python, Node.js, your credentials, or a preconfigured catalog. First-run dependency installation requires internet access.

For an existing installation, back up `config.json` and your configured user-data folder before upgrading. Keep your existing data separate from the extracted release and check the configured paths before scanning.

The GitHub **Source code** archives and a Git clone are for development; they do not include the packaged native runtimes.

### Manual Setup

```bash
git clone --branch main https://github.com/dantebagera/cinema-paradiso.git
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

The v3.0.0 portable release bundles qBittorrent, FFmpeg, and the first-party native player. Settings retains the user-triggered qBittorrent update control. Torrent mode and completed/incomplete folders remain configurable.

---

## Local Data and Cache

The app separates persistent user data from rebuildable cache:

- `data/` stores user lists, viewing states, edited collections, followed releases, poster overrides, metadata corrections, identity audit state, app metadata records, provider-scoped IPTV catalogs/configuration, TV catalog and Follow state, saved AI jobs, and the isolated qBittorrent profile/jobs when the default user data folder is used.
- `runtime/` in the portable release stores bundled third-party runtimes such as qBittorrent and FFmpeg.
- `cache/` stores rebuildable TMDB detail/collection cache.
- Measured media-file facts are stored in the SQL catalogue. A pre-existing
  `res_cache.json` may remain on disk for rollback history, but the runtime
  neither reads nor writes it.
- `config.json` stores local settings and secrets.

These files are user-specific and should not be committed.

---

## Safety

- File deletes default to Windows Recycle Bin via `send2trash`.
- Permanent deletion is treated as dangerous and must be explicit where exposed.
- File operations are restricted to configured movie library roots.
- Cleanup workflows show paths and affected files before action.
- Torrent-file retrieval is restricted to the configured Prowlarr origin; arbitrary browser-supplied download URLs are rejected.
- IPTV images can only be fetched through URLs already stored in the provider catalog; the browser cannot supply an arbitrary proxy URL.
- IPTV stream credentials remain behind a tokenized loopback relay and are not placed in browser or FFmpeg command-line URLs.
- Completed downloads are never renamed automatically.

---

## Tech Stack

- **Backend:** Python, Flask
- **Frontend:** React 19, Vite, CSS custom properties
- **Icons:** Lucide React
- **Metadata:** Plex API, TMDB API
- **Source search:** Prowlarr API
- **Downloads:** qBittorrent WebUI API and original qBittorrent WebUI
- **AI:** Ollama and optional connected ChatGPT workflows
- **Native playback:** Qt Quick and libmpv
- **Resolution probing:** pymediainfo
- **Delete safety:** send2trash

The desktop application uses the React frontend; the built-in media player has its own Qt Quick interface.

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

Basic verification (run the checks relevant to your change):

```bash
python -m py_compile app.py
python -m unittest discover -s tests -p "test_*.py"
node --test tests/discoverUtils.test.mjs
npm run check:ui-reuse
npm run test:shared-ui
npm run build
```

See the [knowledge index](docs/README.md) for feature-specific checks. The v3.0.0 publication passed the production build, shared UI reuse gate, 15 shared UI tests, 9 packaging tests, and package integrity/hash checks. A full regression run and fresh-machine installation/playback test were not performed for that publication.

---

## Earlier screenshots

The [screenshots folder](screenshots/) contains images from earlier desktop versions. They are retained for reference and do not represent the full v3.0.0 redesign.

## License

MIT
