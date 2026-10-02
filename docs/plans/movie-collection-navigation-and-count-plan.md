# Movie collection navigation and count

**Status:** Implemented, verified in isolation, and deployed to the local port-5000 app on 2026-10-01. Dante separately approved live deployment and restart. Commit and publication remain pending.

## Problem and decision

- **What happens now:** Discover can display zero or one movie after opening a collection whose TMDB response contains four parts. In the live app, a search for `resident evil` remained active while opening Mortal Kombat Legends Collection. `/api/tmdb/collection?collection_id=848690` returned four parts, but Discover showed zero and falsely said TMDB returned no members. The owned collection count also takes several seconds: `/api/library/collection/133352` took 5.6 seconds and `/api/library/collection/848690` took 5.3 seconds on the current live process.
- **What Dante wants:** Clicking a collection opens its complete member set, independent of an earlier title search; explicit Discover filters still apply and are accurately described. Collection membership and owned count appear promptly without changing their meaning.
- **Confirmed:** `filterFiniteDiscoverResults` applies `simpleDiscoverQuery`, which includes the retained title search, to TMDB collection parts. The count route projects all library files and details before selecting one collection.
- **Suspected:** The all-library projection is the dominant count cost. A read-only query using the catalog's effective collection relation found the same local collection path set in about 80 ms and the full lightweight identity set in about 90 ms on this machine. End-to-end improvement must still be measured.
- **Open decisions:** None for this approved scope. A collection view clears the prior title search while retaining explicit Discover controls; Back restores the prior search and context.
- **Scope:** Movie collections opened from Discover, Library, Lists, AI Control, and Pick My Movie; shared collection count; collection edit and owned-membership parity. No TV/IPTV changes or unrelated UI redesign.

## Current design and ownership

| Responsibility | Current authoritative file/component/service | Entry point and callers | Behavior to preserve | Competing or obsolete paths |
| --- | --- | --- | --- | --- |
| Collection tile and loading | `src/components/SharedMovieCards.jsx`, `src/hooks/useMovieCollectionCache.js`, `src/api/movieDetails.js` | Discover, Library, Lists, AI Control cards | Loading/error/owned counts; source-aware cache; retry | No new per-route cache |
| Collection navigation and finite filtering | `src/features/discover/DiscoverWorkspace.jsx` | Discover and App relationship request; Pick My Movie | History, explicit filters, ownership, pagination, errors | Retained title search must not filter collection membership |
| TMDB membership and curation | `app.py`, `services/curation_store.py` | `/api/tmdb/collection` | Four provider parts and any user-edited parts | Do not create a parallel collection source |
| Local membership and count | `app.py`, `services/catalog_store.py`, `services/identity_decision.py` | `/api/library/collection/<id>` and shared card cache | SQL-owned local parts, edited members, identity precedence, conflicts, missing-file exclusion | Retire the full-library detailed projection from this route after parity proof |

Baseline: Desktop checkout `master` at `c62b3f3f153e8e22a9a862ee4b1ac1beacd64291`, one commit ahead of `origin/master`, with substantial unrelated tracked and untracked work. `app.py`, Discover, and app-smoke already have uncommitted edits. Port 5000 belongs to Python `app.py` PID 26888, launched from this checkout. Runtime configuration is root `config.json`, data is root `data`, TMDB cache is root `cache`, and Flask serves root `dist`. The live bundle was built 2026-09-30. No pre-edit suite result is claimed; the live failure and endpoint timings are the baseline.

## Exact behavior contract

### Frontend

- Continue using `MovieExpandedCuration` in the shared movie card. No new collection component or styling.
- Opening a collection from a movie-title search stores the current Discover snapshot, clears that title from the visible search field, and displays all TMDB parts before applying deliberate genre, country, year, rating, vote, availability, sort, or advanced criteria. Back restores the earlier search, cards, expansion, and controls.
- A nonempty provider response filtered to zero says that active Discover filters hid the members. An empty provider response says TMDB returned no members. A request failure uses the existing error state and preserves the previous result context.
- Collection navigation from Pick My Movie continues to use the same provider parts and Pick history. All collection entry surfaces use the same Discover owner.

### Backend

- `/api/tmdb/collection?collection_id=<id>` continues to return the cached or fetched curated provider payload; no change to its request/response contract.
- `/api/library/collection/<id>` continues to return `id`, `name`, sorted `parts`, `owned_paths`, `unresolved_parts`, `conflicts`, `owned_count`, `unresolved_count`, source, and generation fields. Valid local files only count as owned. Collection overrides can add parts outside the native collection; their owned identities must still resolve. Duplicate identity conflicts remain conflicts.
- Use the existing SQLite catalog's effective collection relation to fetch only detailed records for the requested collection. Use lightweight catalog identity rows for owned-member reconciliation; check filesystem existence only for matching candidates. Keep `resolve_collection_membership` as the matching authority. No schema/data migration or live catalog mutation is planned. TMDB fallback remains for a collection absent locally; provider errors retain current status behavior.
- If the targeted catalog path cannot preserve existing fixture parity, stop and revise this plan rather than keeping a hidden full-library fallback.

## Implementation sequence

1. Scope finite collection filtering in `DiscoverWorkspace.jsx`, clear the prior title search on entry, restore it through existing history, and correct empty text based on provider part count.
2. Add targeted collection and lightweight identity reads to `CatalogStore`, route them through `app.py`, preserve `resolve_collection_membership`, and remove the obsolete all-library collection read after parity checks.
3. Add focused Python and desktop regressions, run focused and broader isolated checks, build to an isolated test distribution, inspect rendered desktop behavior, and compare endpoint timings.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| `resident evil` search, then Mortal Kombat movie | Open Mortal Kombat Legends Collection | Four TMDB parts appear; no false empty message | Discover | Desktop regression |
| Search matches only one member | Open its four-part collection | All four parts appear | Discover | Desktop regression |
| Collection with explicit filter | Open collection | Matching members appear; if none, filter-specific empty message | Discover | Desktop regression |
| Collection with zero provider parts | Open collection | Genuine TMDB-empty message | Discover | Desktop regression |
| Prior search and expanded card | Back from collection | Prior query, result list, and history return | Discover | Desktop regression |
| SQL-owned collection and edited part | Load count | Same parts, owned paths/count, unresolved/conflict status as baseline | Catalog/route | Python fixture tests |
| Missing file or duplicate matching identity | Load count | Missing file excluded; duplicate remains conflict | Resolver/route | Python fixture tests |
| Library, Lists, AI Control, Pick My Movie | Open a collection | Shared tile and navigation work without route-specific copies | Shared/Discover | Existing and focused desktop checks |
| Slow cached local collection | Load count | No detailed full-library projection; median cached response under one second on representative local catalog | Catalog/route | Timed endpoint comparison |

## Verification and rollout

- **Baseline:** Live UI reproduced zero after a four-part TMDB response. Local collection routes measured 5.3-5.6 seconds. Current dirty files recorded before edits.
- **Focused tests:** Unique OS-temp `CP_TEST_ROOT` with `CP_TEST_MODE=1`; run collection and SQL migration Python tests and focused Playwright collection cases using isolated `CP_TEST_DIST_DIR`.
- **Broader tests:** Relevant Python suite and desktop Playwright suite; report full-suite failures separately from focused recovery.
- **Compiled UI:** `npm.cmd run build` to isolated test dist; inspect desktop collection, Back, filtered empty, and error behavior. No mobile work.
- **Live work, only if separately approved:** Back up existing dist and confirm process/config/data/bundle, deploy build, visually recheck the motivating chain, and roll back if collection parity or navigation fails.
- **Reporting:** State source-only, isolated-test, and live status separately, with exact failures and remaining uncertainty.

## Implementation and verification record — 2026-10-01

- `DiscoverWorkspace.jsx` now excludes the prior simple movie-title search from collection filtering, clears the visible search on entry, and restores it through the existing Back snapshot. Provider-empty and filter-empty states use distinct text.
- `CatalogStore.collection_lookup` reads targeted detailed members plus lightweight identity rows from the existing effective catalog relation. `app.py` no longer projects detailed records for the full library on this route. `resolve_collection_membership` remains the identity authority and checks filesystem existence only for matched candidates.
- The read-only catalog trial returned four Resident Evil local members and one Mortal Kombat local member in 278 ms and 275 ms respectively. This is lookup timing, not a live endpoint latency claim; the under-one-second endpoint target remains to be checked after any approved live rollout.
- Focused Python checks passed, including edited owned parts, missing files, duplicate identity conflict, blank ID validation, and the SQL-only route. The relevant collection/curation/identity/UI Python group passed 133 tests before the last duplicate and blank-ID additions; both added cases passed in focused reruns.
- The full isolated Python suite first reported one failure from an obsolete test fixture that populated only the retired in-memory library cache. The fixture now seeds the authoritative SQL catalog and retains its owned/unresolved assertions. The latest full run passed **1399 tests** in 225.434 seconds. A later focused run passed the two collection API tests, including the new blank-ID case.
- The isolated production build succeeded. The focused desktop regression passed. The default full desktop Playwright run passed **86 tests** with **37 TV-specific tests skipped** by its default configuration. No live bundle was replaced and the running port-5000 process was not restarted.

## Live deployment and verification — 2026-10-01

- Before restart, only the collection fix files had changed after the running Python process started and the served frontend bundle was built. Other dirty source work predated those live baselines. The prior 37-file `dist` was copied and SHA-256 checked at `C:\Users\dante\.codex\backups\cp-collection-live-20261001-050742\dist`.
- The normal `run.bat --restart` path rebuilt the frontend and restarted the backend. Port 5000 moved from PID 26888 to PID 27972. The served `/discover` HTML SHA-256 matched the new `dist/index.html`: `A3E1B5B8AC9F23B0896F127CDDC3CC0B8EDE94AC3B10B3CE94CBBE580EAC10C8`.
- Live Playwright against port 5000 opened Resident Evil (Animated) Collection from a `resident evil` search and rendered all four members, cleared the visible search, then Back restored the search. Eight further member-to-collection transitions each rendered all four members. A separate `mortal kombat legends` search opened Mortal Kombat Legends Collection from Snow Blind and rendered all four members without a false empty message. Screenshots are in the backup directory.
- Seven subsequent warm HTTP samples per local count route returned median 319 ms for Resident Evil (Animated) and 299 ms for Mortal Kombat Legends, versus the pre-change 5.6 and 5.3 second observations. Immediately after restart, background startup activity produced slower outliers, including 1.7 seconds; the under-one-second target is met for the warm median, not guaranteed for every request.
- No live catalog migration, commit, push, tag, or release was performed.
