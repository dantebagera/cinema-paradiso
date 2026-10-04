# Restore missing movie plots after award navigation

**Status:** Implemented and verified in isolation, 2026-10-04; not deployed. Full Python suite has one independently confirmed unrelated pre-existing streaming assertion failure, documented below. Dante: "ok shall we fix?" following the proposed shared plot fallback, Arabic preservation, regression coverage, and isolated desktop verification. Source/tests/documentation only; no deployment, restart, live data edits, commits, or database consolidation.

## Problem and decision

- **What happens now:** Christian Bale's Golden Globe results return Vice (`429197`) with an empty plot. Its existing TMDb details cache contains the full English plot. `mergeTransientMovieLanguage(movie, details, null)` ignores detail plots and `DiscoverMovieCard` renders the empty result's placeholder. A read-only assertion using the actual award response and cache fails.
- **What Dante wants:** Opening the same movie through search, awards, or a longer navigation path displays its available plot.
- **Confirmed:** Missing display merge, rather than lost cached data. Awards GETs intentionally return cache/minimal facts without provider enrichment. Navigation depth is not required to trigger this example.
- **Unknown:** Other unreported bugs; they are outside this fix.
- **Open decisions:** None for the agreed missing-plot correction.
- **Scope:** Shared regular-movie display helper and regression coverage; preserve current components, desktop geometry, canonical identity, existing plots, and backend ownership. TV/IPTV, awards storage/details expansion, and live actions are excluded.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected callers | Proposed behavior | Changes contract? | Decision |
| --- | --- | --- | --- | --- | --- |
| Movie details; Dante's report and approval | Available plot displays regardless of navigation; genuinely absent plot retains placeholder | DiscoverMovieCard, LibraryMovieCard, IndexerMovieCard through useTransientMovieLanguage | Fill a missing display plot from already loaded details | No; repair | Approved 2026-10-04 |
| Accepted metadata; canonicalOwnedMovie and existing awards plan | Valid accepted card plot keeps priority | Library, owned Discover, Lists, AI Control | Preserve valid movie summary/plot over detail text | No | Preserve |
| Transient language; MovieLanguageToggle | Arabic overlays display only; English restores original language without persistent writes | Shared movie cards | Localized plot first, resolved English plot if translation is missing | No | Preserve |
| Awards navigation/storage; original awards plan | Exact winning identities/role, counts, pagination, history; awards GETs do not enrich catalog | Awards API and Discover | No backend/navigation changes | No | Preserve |

Existing award browser tests validate navigation but do not assert that expanded winning results display the detail response's plot. Add that assertion rather than changing any existing contract.

## Current design and ownership

| Responsibility | Owner | Entry/callers | Preserve | Obsolete path |
| --- | --- | --- | --- | --- |
| Retrieve/cache movie details | src/api/movieDetails.js fetchCanonicalMovieDetails; DiscoverWorkspace loadDiscoverDetails | Expansion, trailers, restored navigation | Same requests and cache keys | None |
| Compose display/language view | src/api/movieDetails.js mergeTransientMovieLanguage; MovieLanguageToggle.jsx | DiscoverMovieCard, LibraryMovieCard, IndexerMovieCard | Identity, original inputs, valid plot priority, language states | Early English return that ignores missing plot in details |
| Render plot | SharedMovieCards.jsx; IndexerMovieCard in DiscoverWorkspace.jsx | Discover, Library, Lists, AI Control, Pick, Browse | Existing markup/styles/actions/placeholder | No new renderer |
| Resolve winning films | movie_awards_store.py/routes.py; app.py _project_awards_movie | Person award controls | Counts, exact IDs, read-only API | None |

Baseline: Desktop checkout, `master`, `3c626b7` (beta.2). Existing tracked changes: src/App.jsx and src/styles.css. Existing untracked stream plan/test and two debug logs are preserved. Live port 5000 is Python PID 19344. Runtime data/cache owners were read from `/api/app-data/config`: Desktop data and cache directories. Served `index-BLiwytC2.js` matches local dist SHA-256 `DE520A609E5FC69590EBB7C3A2E8C717D89D76337FA610C5B7AD984B5F2C1785`; dist/index.html hash `A112A1DFF776ADDA88B35BA330E8E0D4A003713510CD4F0CAD22BDDB13AB8634`. Live has not been changed.

## Exact behavior contract

### Frontend

Modify the existing display helper only. Prefer the first nonblank movie summary/plot; if both are absent/blank, use the first nonblank loaded detail summary/plot. Preserve the supplied text without trimming its displayed content. Fill both display summary and plot when adding the fallback, without mutating either input. Normalize a blank truthy summary that would otherwise hide an existing valid plot. Preserve the original movie object when its summary-or-plot rendering already resolves usable text, and preserve the details object in English. Arabic uses its available plot first, otherwise the resolved English plot. Switching back recomputes the English display from original movie/details. Never spread full detail metadata over the movie identity/title/poster.

Use existing MovieLanguageToggle, DiscoverMovieCard, LibraryMovieCard, IndexerMovieCard, UnifiedMovieCard, and plot markup unchanged. No CSS, new controls, mobile work, layout changes, or extra network requests. Loading/failed/empty detail records retain existing card text or placeholder; when valid details arrive, the missing plot appears.

### Backend

No request/response, persistence, retry, concurrency, migration, or store changes. Awards results remain sparse offline-capable identities. Example: Vice's initially empty plot is filled for display from its already loaded TMDb detail plot; the awards database is not modified.

## Implementation sequence

1. Add failing unit assertions for sparse records, detail-only plots, preserved valid/accepted plots, input immutability, blank translations, and loading/error/empty details. Add browser scenarios that open actual sparse award API results and assert loaded plot text.
2. Correct the existing display helper's missing-plot composition and localized fallback. Retire its English missing-data omission; do not add route-specific fallbacks.
3. Verify Node tests, full Python suite with isolated CP_TEST_ROOT, focused and broader desktop awards/relationship/shared-card scenarios, isolated Vite build, and preservation hashes. Redirect existing awards screenshot evidence to OS-temp to avoid overwriting committed reference images.

## Acceptance matrix

| Scenario | Action | Expected result | Owner/check |
| --- | --- | --- | --- |
| Sparse winning film, detail plot present | Expand from Oscars or Golden Globe | API result lacks plot; rendered plot equals detail response | Browser + unit |
| Search result already has plot | Expand with different detail plot | Existing card plot survives | Unit + existing browser fixtures |
| Accepted Library plot | Open owned card | Accepted plot survives provider fallback | Unit + owned/surface awards browser tests |
| Repeated award navigation | Open a winning movie, select another award, open another result | Each result's detail plot displays | Browser |
| Back/Forward | Restore previous expanded winning card | Correct plot and identity restore | Browser |
| Arabic/English | Toggle Arabic then English | Arabic plot appears, then resolved English plot returns | Browser + unit |
| Missing Arabic description | Toggle Arabic | Resolved English plot remains available | Unit |
| Both summary/plot absent or whitespace | Supply nonblank detail summary/plot | Detail text displays without input mutation | Unit |
| Loading/error/empty details | Expand card | Existing valid plot survives; truly absent plot stays absent | Unit + existing browser error cases |
| Library/Lists/AI/Pick/Browse | Open/return through awards | Existing identity, plot, awards, and navigation remain correct | Existing awards suite |
| TV/IPTV boundary | Run existing relevant checks | No award or movie-language behavior leakage | Full Node/Python + awards IPTV test |

## Verification and rollout

- **Baseline:** Full Node suite: 110 passed. Focused Python awards API, TMDb details transform, shared-card tests: 65 passed. Six existing detail tests pass despite the failing real-data plot probe.
- **Focused:** `node --test tests/movieDetails.test.mjs`; new plot tests in tests/e2e/movie-awards.spec.js against isolated Flask/seed/Vite bundle.
- **Broader:** Full Node suite; `.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_*.py` with CP_TEST_MODE=1 and unique OS-temp CP_TEST_ROOT; complete awards browser suite plus relationship and shared-card checks.
- **Compiled UI:** Build with `npm.cmd run build -- --outDir <CP_TEST_ROOT>/dist`; run Playwright at isolated port, desktop viewport only. Capture restored winning-card screenshot in test artifacts.
- **Live:** Not authorized. Keep process, served dist, config/cache, and awards data untouched; no restart, build into live dist, downloads, commit, or push.
- **Reporting:** Record red/green, exact suite results, warnings/failures, independent review, preservation checks, and source-only status here. A live verification needs separate deployment approval.
- **Contract comparison:** Completion requires restored missing plots and unchanged valid/canonical/localized behavior; no silent database or navigation contract changes.

## Execution evidence

- Working in the approved Desktop checkout; no Git operations or unrelated source changes. Evidence root: `C:/Users/dante/AppData/Local/Temp/cp-award-plots-f4cf8ac6884a42dabc232904209a8efa`.
- **Red:** New unit scenarios initially produced 5 expected missing-plot failures. Both browser award scenarios failed at the visible plot assertion: expected full English detail plot, received `No plot summary is available yet.` A later whitespace-summary masking case was separately demonstrated red and corrected within the shared helper.
- **Green:** Detail unit tests: 15/15. Complete Node suite: 119/119. Final isolated desktop Playwright awards + relationships suite: 47/47 in 45.0s. All viewports in these suites are desktop; `720` refers to desktop height. Isolated Vite compilation succeeded in 2.19s, then again for the final browser run.
- **Complete path:** Real isolated awards GET results lack a plot; expanding them displays detail-only plot text through Oscars/Golden Globes, Arabic/English, a second award navigation, Back, and browser Forward. Existing normal-search plot priority is asserted. Library, Lists, AI Control, Pick, Browse, owned canonical metadata, geometry, snapshot errors, and relationship history remain covered.
- **Actual Vice data:** Re-ran the original read-only probe against the live award response plus on-disk cached detail record using the updated helper; the resulting displayed summary exactly equals Vice's cached full English plot, with its initial movie plot still empty afterward. This verifies source composition, not deployed UI.
- **Browser test setup correction:** Initial green attempt: 24 old tests passed, 2 new tests failed later because the origin's old fixture details had been cached before its replacement route was installed. Installed the detail route before origin expansion; retained all original visible-text assertions. A subsequent runner attempt was blocked by Windows `.cmd` treating a regex pipe as a shell separator before tests ran; reran with a pipe-free filter.
- **Independent review:** Fresh read-only reviewer found no issues, checked all three shared helper callers, and independently confirmed 15 detail tests passing.
- **Visual inspection:** Reviewed final restored-winning-card screenshot; plot text and existing actions/credits layout visible. Existing awards screenshot references were redirected to OS-temp, not overwritten.
- **Full Python suite:** Ran 1,563 tests in 228.371s: 1,562 passed, 1 failed, no skipped tests. Failure: `test_qbittorrent_ui.QBittorrentUiTests.test_streaming_modal_shows_loading_feedback_until_iframe_loads`, tests/test_qbittorrent_ui.py:113. It expects the deleted `streamLoaded` variable in the existing dirty StreamPlayerModal in App.jsx. This fix never changed App.jsx; its hash matches the captured baseline. Reproduced the assertion against current source, then substituted HEAD's App.jsx text in memory and the same assertion passed. No source/test changes made for this unrelated failure. The full suite is not reported as green.
- **Final preservation:** All 11 baseline hashes match, including Dante's dirty/untracked work, served dist, config, live TMDb cache, and awards database. Port 5000 remains Python PID 19344; isolated port 5117 is stopped. Served live bundle SHA-256 still `DE520A609E5FC69590EBB7C3A2E8C717D89D76337FA610C5B7AD984B5F2C1785`. Final evidence stored in preservation-final.json under the evidence root.
- **Warnings:** Browser runner reports pre-existing NO_COLOR/FORCE_COLOR conflict. Git reports LF-to-CRLF normalization warnings; focused diff check has no whitespace errors. Full Python run reports two non-failing ResourceWarnings for unclosed temporary/dist file handles.
- **Final contract comparison:** Missing plots are restored from already loaded details in English and after language/history changes. Existing usable/canonical plots, identities, backend requests, awards counts/membership/storage, and desktop components remain unchanged. No remaining difference found in the approved plot contract. Deployment and any unrelated streaming correction remain separate work.
