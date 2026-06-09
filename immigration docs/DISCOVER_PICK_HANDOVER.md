# Cinema Paradiso Handover: Discover + Pick My Movie

Date: 2026-06-09

This handover is for a new Codex chat dedicated only to the React Discover workspace. The goal is to build one cohesive Discover UI that includes TMDB movie discovery, Prowlarr/indexer browsing, per-movie source search, live streaming actions, and Pick My Movie AI recommendations.

Do not restart the whole app redesign discussion. Library, Settings, and Cleanup have already had React migration work. Use their current visual language and interaction patterns.

## Read First

Read these files before implementation:

- `PRODUCT.md`
- `DESIGN.md`
- `.github/skills/impeccable/SKILL.md`
- `.github/skills/impeccable/reference/product.md`
- `Agent.md`
- `README.md`
- `context/progress-tracker.md`
- `immigration docs/HANDOVER.md`
- `immigration docs/SETTINGS_CLEANUP_HANDOVER.md`
- `src/App.jsx`
- `src/styles.css`
- `app.py`

Ignore `winapp/`.

## Current State

- `/discover` currently falls through to `MigrationWorkspace`; it is still a placeholder in React.
- The Home page already shows a small trending TMDB feed, but this is not the full Discover workspace.
- A reusable torrent/source modal already exists in React as `TorrentModal`.
- Home and Library already use shared actions:
  - `streamMovie(movie)` calls `/api/tmdb/imdb_id` and opens live streaming through `playimdb.com`.
  - `findTorrent(movie, upgrade)` calls `/api/explore/search` and opens the torrent/source modal.
  - `playLocal(path)` opens owned local files.
- The next chat should wire these actions into Discover cards instead of duplicating action logic.

## Product Direction

Discover is the online activity area. It is separate from offline library management.

It should include:

- TMDB movie discovery.
- Browse indexers / latest torrent activity from Prowlarr.
- Search TMDB manually.
- Search torrents manually.
- Pick My Movie AI recommendations through Ollama.
- Per-card archive-aware actions:
  - If owned locally: Play from HDD remains primary.
  - If not owned: Stream and Find Sources are primary online actions.
  - If owned but low quality: Play still exists, and Find Upgrade is secondary.
  - Trailer should be available when TMDB trailer data exists; fallback can search YouTube.
  - Follow release/watchlist can be included if implemented carefully.

Do not create separate pages for every online tool unless the user explicitly asks later. Use a single Discover workspace with clear tabs or segmented sections.

## Recommended UI Structure

Use one Discover page with three main tabs:

1. `Explore Movies`
   - TMDB-driven.
   - Lists: Trending Week, Trending Today, Now Playing, Upcoming, Popular, Top Rated, Best All Time.
   - Genre filter.
   - Search bar for TMDB movie search.
   - Load more.
   - Cards should be wide/proportional, not skinny.
   - Cards show poster, title, year, rating, genres, language/country, plot preview, and actions.

2. `Browse Indexers`
   - Prowlarr-driven.
   - Uses latest/trending torrent files from enabled indexers.
   - Filters: resolution, indexer, sort by seeders/quality/title.
   - Search bar for manual torrent search.
   - Cards should group variants by movie where backend already groups them.
   - Show best resolution, best seeders, indexer, variant pills, size where useful.
   - Actions: Magnet if available, `.torrent` if available, Page as fallback.

3. `Pick My Movie`
   - Ollama-driven.
   - Prompt textarea.
   - Ask AI action.
   - Result cards enriched by TMDB.
   - Each recommendation shows AI reason clearly.
   - Cards must still have archive-aware actions:
     - Owned: Play.
     - Not owned: Stream, Find Sources.
     - Low quality owned: Play plus Find Upgrade.

## Backend Endpoints Already Available

TMDB discovery/search/details:

- `GET /api/tmdb/discover?list=trending_week&page=1`
- `GET /api/tmdb/discover?list=trending_today&page=1`
- `GET /api/tmdb/discover?list=now_playing&page=1`
- `GET /api/tmdb/discover?list=upcoming&page=1`
- `GET /api/tmdb/discover?list=popular&page=1`
- `GET /api/tmdb/discover?list=top_rated&page=1`
- `GET /api/tmdb/discover?list=best_all_time&page=1`
- Optional genre filter: `&genre=<tmdb_genre_id>`
- `GET /api/tmdb/search?q=<query>&page=1`
- `GET /api/tmdb/details?tmdb_id=<id>`
- `GET /api/tmdb/imdb_id?tmdb_id=<id>`

Prowlarr/indexers:

- `GET /api/explore/browse`
- `GET /api/explore/search?title=<title>&year=<year>`
- `GET /api/prowlarr/search?q=<manual query>`

AI recommendations:

- `POST /api/ollama/recommend`
  - Body: `{ "prompt": "..." }`
  - Returns enriched `results` and `model`.

Ownership/local actions:

- `POST /api/library/check`
  - Body: `{ "movies": [{ "title": "...", "year": "..." }] }`
  - Use this to mark Discover/Pick cards as owned and decide Play vs Stream/Find Sources.
- `POST /api/open-file`
  - Used through existing `playLocal(path)` helper.

## Card Behavior Requirements

Discover cards should share a consistent action model:

- Owned and known local path:
  - Green owned badge.
  - Primary: Play.
  - Secondary: Details / Trailer / Find Upgrade if quality is low.
- Not owned:
  - Primary: Stream.
  - Secondary: Find Sources.
  - Optional: Follow.
- Search/source result:
  - Prefer magnet link if backend returns `magnet_url`.
  - Else use `.torrent` download URL.
  - Else use source page/info URL.

Use existing `TorrentModal` behavior for detailed source results, unless the Discover page needs a specialized inline indexer browser. Do not create two incompatible torrent result UIs.

## Existing React Pieces To Reuse

From `src/App.jsx`:

- `fetchJson`
- `formatCount`
- `movieKey`
- `resolutionRank`
- `isLowQuality`
- `getUniqueOptions`
- `torrentSizeBytes`
- `TorrentModal`
- `SmartMovieCard` patterns for archive-aware actions
- `MovieInspector` patterns if detailed selected-movie panel is useful
- `streamMovie`
- `findTorrent`
- `playLocal`

Important: if Discover needs `findTorrent`, `streamMovie`, or `playLocal`, pass them from `ArchiveApp` into the new `DiscoverWorkspace`, the same way Home and Library receive shared actions.

## Design Direction

Use the approved Cinema Paradiso style:

- Black/gold identity.
- Gold is focus, not decoration everywhere.
- Violet belongs naturally to AI/Pick My Movie.
- Prowlarr/indexer browsing can use gold/amber accents, but must stay clean and scannable.
- Owned/local actions use green.
- Destructive actions are not central here.
- Avoid cluttered torrent-indexer tables.
- Do not make a static landing page.
- Do not duplicate sidebar navigation inside the hero/header.
- Cards should be wide and proportional, with readable plot text.
- Subtle animation is fine: hover lift, border focus, loading shimmer, tab transition. No noisy motion.

## Implementation Boundaries

Expected frontend work:

- Add `DiscoverWorkspace` in `src/App.jsx`.
- Replace the Discover placeholder in `MigrationWorkspace` or route directly from `ArchiveApp`.
- Add Discover-specific CSS in `src/styles.css`.
- Reuse shared modals/actions instead of duplicating code.

Expected backend work:

- Prefer no backend changes at first.
- Add backend only if the React page needs data that existing endpoints cannot expose.
- If backend is touched, add or update tests where practical.

Do not touch `winapp/`.
Do not redesign Library, Settings, or Cleanup unless a small shared helper change is required.

## Verification

At minimum:

- Run `npm.cmd run build`.
- Run `python -m py_compile app.py` if backend changes.
- If backend behavior changes, run relevant pytest tests.
- If browser tooling is available, visually verify `/discover` on desktop and mobile.

## Copy-Ready Prompt For New Chat

Use this prompt in the new Codex chat:

```text
You are continuing the Cinema Paradiso React/Vite redesign in the same project.

First read:
- PRODUCT.md
- DESIGN.md
- .github/skills/impeccable/SKILL.md
- .github/skills/impeccable/reference/product.md
- Agent.md
- README.md
- context/progress-tracker.md
- immigration docs/HANDOVER.md
- immigration docs/SETTINGS_CLEANUP_HANDOVER.md
- immigration docs/DISCOVER_PICK_HANDOVER.md
- src/App.jsx
- src/styles.css
- app.py

Ignore winapp/.

The goal of this chat is only to build the Discover UI in the new React app.

The Discover page must include:
- Explore Movies using TMDB discovery/search.
- Browse Indexers using Prowlarr latest/search results.
- Pick My Movie using Ollama recommendations.
- Archive-aware movie actions on cards: Play if owned, Stream and Find Sources if not owned, Find Upgrade if owned but low quality.
- Trailer support through TMDB details, with YouTube fallback if needed.
- Manual TMDB search and manual torrent search.

Current state:
- /discover is still a React placeholder.
- Backend endpoints already exist for TMDB discovery/search/details, Prowlarr browsing/search, Ollama recommendations, library ownership checks, and streaming IMDB lookup.
- Existing React helpers and modals should be reused, especially TorrentModal and the shared play/stream/find-source actions.

Design:
- Use the black/gold Cinema Paradiso visual language from DESIGN.md and /styleguide.
- Keep cards wide, readable, and proportional.
- Avoid duplicated sidebar navigation inside the page.
- Avoid cluttered torrent tables; make indexer results scannable with hierarchy.
- Keep motion subtle and modern.

Before implementation, summarize the Discover plan and ask me for approval. Do not implement until I approve.
```
