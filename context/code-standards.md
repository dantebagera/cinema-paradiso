# Code Standards

## General

- Keep changes scoped to the workspace or API boundary being modified.
- Prefer existing helpers and component patterns before introducing new abstractions.
- Preserve local-first behavior and user control.
- Do not silently perform destructive file operations.
- Do not modify `winapp/` unless the user explicitly resumes that project.

## React

- Keep shared helpers near the top of `src/App.jsx` unless a future refactor introduces modules.
- Use stable keys for movie/file rows where possible.
- Keep cards readable and proportional; avoid the old skinny-card pattern.
- Reset pagination and expanded state when filters/search/mode change.
- Use controlled inputs for filters, forms, and settings.

## Styling

- Use CSS variables from `src/styles.css`.
- Keep gold as a focus/identity accent, not a blanket decoration.
- Use functional colors consistently: green owned/success, amber quality warning, red destructive, violet AI, cyan Plex/system, blue library.
- Maintain responsive layouts for desktop and mobile.

## API Routes

- Validate required request fields before doing work.
- Return JSON with either useful result data or an `error` string.
- Keep file actions constrained to configured library roots.
- Bust caches when file paths, settings, or Plex metadata change.

## Data and Storage

- User data belongs under `data/` or the configured user-data folder.
- Rebuildable metadata cache belongs under `cache/` or the configured cache folder.
- `config.json`, `data/`, `cache/`, and `res_cache.json` are local/user-specific and should not be committed.

## Verification

Before release-level changes:

```bash
python -m py_compile app.py
python -m unittest tests.test_user_curation_store
npm run build
```
