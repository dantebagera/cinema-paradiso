# Cinema Paradiso Handover: Settings + Cleanup

Date: 2026-06-09

This handover is for a new Codex chat dedicated only to the Settings page and Cleanup page. Do not restart the full redesign discussion. The Library section has already had a large React pass and should be treated as the current reference for behavior, styling, and interaction density.

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
- `src/App.jsx`
- `src/styles.css`
- `app.py`

Ignore `winapp/`.

## Current Architecture

- Backend remains Flask in `app.py`.
- React/Vite frontend lives in `src/`.
- Flask serves the built React app from `dist/`.
- Legacy Flask template remains available at `/legacy` and is useful as behavior reference only.
- Do not copy the legacy visual design. Use the current black/gold Cinema Paradiso design system from `/styleguide`, `DESIGN.md`, and the newer React Library workspace.

## Current UI State

- `/library` is the most developed React workspace.
- `/settings` exists but is incomplete. It currently only exposes App Data paths:
  - User data folder
  - TMDB cache folder
- `/cleanup` is still a placeholder under `MigrationWorkspace`.
- Sidebar already groups Cleanup under offline maintenance and Settings under system/integrations.
- The topbar search behavior was intentionally changed:
  - Home keeps broad/TMDB-style command search.
  - Library searches the offline library only.

## Design Direction

Use the Cinema Paradiso styleguide:

- Background: near black.
- Surfaces: restrained raised dark panels.
- Accent: gold used sparingly for focus, active states, and primary commands.
- Functional colors:
  - Green: safe/success/owned/offline.
  - Amber: warning/low quality/attention.
  - Red: delete/destructive.
  - Cyan: Plex/system connectivity.
  - Violet: AI or matching workflows.
  - Blue: library/info.
- Use Lucide icons.
- Do not make static marketing pages.
- Do not use generic SaaS dashboard styling.
- Keep dense maintenance workflows scannable and calm.
- Risky file actions must be explicit, controlled, and recoverable.
- Motion should be sleek and light: subtle transitions, hover elevation, focus line, loading shimmer/spinner where useful. No noisy animation.

## Backend Endpoints Already Available

Settings/config endpoints:

- `GET /api/config`
- `POST /api/config`
- `GET /api/app-data/config`
- `POST /api/app-data/config`
- `GET /api/plex/config`
- `POST /api/plex/config`
- `GET /api/plex/test`
- `GET /api/plex/sync`
- `POST /api/plex/force-scan`
- `GET /api/prowlarr/config`
- `POST /api/prowlarr/config`
- `GET /api/prowlarr/test`
- `GET /api/tmdb/config`
- `POST /api/tmdb/config`
- `GET /api/tmdb/test`
- `GET /api/ollama/config`
- `POST /api/ollama/config`
- `GET /api/ollama/test`

Cleanup/library maintenance endpoints:

- `GET /api/duplicates`
- `GET /api/smart-scan`
- `GET /api/low-quality`
- `GET /api/fix-unmatched`
- `POST /api/delete`
- `POST /api/rename-file`
- `POST /api/fix-path`
- `GET /api/plex/match-search`
- `POST /api/plex/match-apply`
- `GET /api/prowlarr/search`

Use these before adding backend routes. Add backend only if the React UI needs a capability that the legacy UI already had but no API exposes cleanly.

## Settings Page Target

The Settings page should become a real system/integrations console, not a small form.

Recommended structure:

1. Header
   - Title: `Settings`
   - Status phrase: local-first system configuration.
   - Include small system summary chips for configured/missing integrations.

2. Library Location
   - Movies/library directory from `/api/config`.
   - Save action.
   - Clear copy that this is the offline library root.

3. App Data
   - User data folder from `/api/app-data/config`.
   - TMDB cache folder from `/api/app-data/config`.
   - Save action.
   - Explain through labels, not long paragraphs:
     - User data contains lists and edited collections.
     - TMDB cache is disposable metadata cache.

4. Integrations
   - Plex card:
     - URL
     - token
     - save
     - test
     - sync
     - force scan
     - show connected/error state
   - Prowlarr card:
     - URL
     - API key
     - save
     - test
     - show indexer count if returned
   - TMDB card:
     - API key
     - save
     - test
     - show connected/error state
   - Ollama card:
     - URL
     - model
     - save
     - test
     - show connected/error state

5. Behavior requirements
   - Mask secrets by default if practical, with a reveal toggle.
   - Save and Test should be separate actions.
   - Show per-card loading and status, not one global vague message.
   - Avoid disabling the whole page when one integration is testing.
   - Preserve current backend config format in `config.json`.

## Cleanup Page Target

The Cleanup page should be the offline maintenance center. It is not a movie browsing page.

Recommended structure:

1. Header
   - Title: `Cleanup`
   - Green `Offline` badge.
   - Summary of duplicate groups, low-quality files, unmatched Plex items, and smart-clean recommendations.

2. Workspace tabs
   - `Duplicates`
   - `Smart Clean`
   - `Low Quality`
   - `Unmatched Plex`

3. Duplicates tab
   - Uses `GET /api/duplicates`.
   - Group by movie.
   - Show best copy clearly.
   - Show duplicate copies with resolution, source, size, path, Plex title/year if available.
   - Allow selecting files.
   - Delete selected through `POST /api/delete`.
   - Default delete mode should move to Recycle Bin if backend supports `trash: true`.
   - Permanent delete should require explicit confirmation if exposed.

4. Smart Clean tab
   - Uses `GET /api/smart-scan`.
   - Show recommendations with keep/delete comparison.
   - Skipped recommendations must be visually different and not selectable for delete.
   - Delete selected recommendations through `POST /api/delete`.

5. Low Quality tab
   - Uses `GET /api/low-quality`.
   - Show files below 1080p or otherwise ranked low by backend.
   - Include filters for resolution, source, title, and Plex state if data exists.
   - Each row should include:
     - file/movie name
     - resolution
     - source
     - size
     - path
     - Plex metadata
     - Find Sources/Upgrade action using existing torrent modal pattern if reusable.
     - Delete action with confirmation.

6. Unmatched Plex tab
   - Uses `GET /api/fix-unmatched`.
   - Show reason/hint from `plex_hint`.
   - Actions:
     - Rename via `POST /api/rename-file`
     - Fix Path via `POST /api/fix-path`
     - Plex match search via `GET /api/plex/match-search`
     - Apply Plex match via `POST /api/plex/match-apply`
     - Delete via `POST /api/delete`
   - Keep Plex matching role-specific and explicit. Do not silently apply a match.

7. Safety requirements
   - Every destructive action needs a confirmation dialog.
   - Bulk actions must show exactly how many files will be affected.
   - File paths are appropriate here; unlike Movie View, Cleanup is a file-management surface.
   - Never auto-delete.
   - Never silently move files without showing the destination/result.

## Reuse From Library

Reuse existing frontend helpers/components/patterns where possible:

- `fetchJson`
- `notify`
- confirmation dialog pattern
- torrent/source search modal pattern
- buttons/chips/status classes
- local loading state patterns
- CSS variables and visual tokens

Do not refactor Library unless strictly required for shared helpers.

## Known Dirty Worktree Context

There are many current modified/untracked files from the React migration. Do not revert unrelated changes. Treat them as user/current-session work.

Notable current files:

- `src/App.jsx`
- `src/styles.css`
- `app.py`
- `tests/test_tmdb_details_transform.py`
- `tests/test_user_curation_store.py`
- `data/`
- `cache/`
- `dist/`

`cache/` and `data/` are intentionally ignored in `.gitignore`.

## Verification

At minimum after implementation:

- Run `npm.cmd run build`.
- Run relevant Python tests if backend behavior changes:
  - `python -m pytest tests/test_user_curation_store.py`
  - `python -m pytest tests/test_tmdb_details_transform.py`
- If Cleanup backend routes are changed or new route tests are added, run those tests too.
- If browser tooling is available, visually verify:
  - `/settings`
  - `/cleanup`
  - mobile and desktop layouts

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
- src/App.jsx
- src/styles.css
- app.py

Ignore winapp/.

The goal of this chat is only to build the Settings page and Cleanup page in the new React UI.

Important context:
- Library has already been heavily redesigned and approved; use it as the interaction/style reference.
- Do not redesign Library unless a small shared helper is truly required.
- /settings is currently only an App Data path form.
- /cleanup is currently a placeholder.
- Backend endpoints already exist for config, Plex, Prowlarr, TMDB, Ollama, duplicates, smart scan, low quality, unmatched Plex, rename, fix path, Plex match, delete, and torrent search.
- Use the black/gold Cinema Paradiso design system from DESIGN.md and /styleguide.
- Settings should become a proper system/integrations console.
- Cleanup should become the offline maintenance center with tabs for Duplicates, Smart Clean, Low Quality, and Unmatched Plex.
- File paths and delete controls belong in Cleanup/File-management views, not Movie View.
- Destructive actions must be explicit and confirmed.

Before implementation, summarize the plan for Settings and Cleanup and ask me for approval. Do not implement until I approve.
```
