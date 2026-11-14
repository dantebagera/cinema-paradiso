# Upcoming movies backend ownership verification

Source implementation approved by Dante on 12 October 2026. Production has not been activated.

## Behavior and ownership

`app.py::_tmdb_filter_upcoming_movies` owns eligibility: a strict valid `YYYY-MM-DD` release date today or later. Native Home requests and advanced/direct Discover requests apply it before deduplication and logical paging. Person-credit queries apply the same gate before credit deduplication. Discover provider criteria receive an intersected future-date lower bound, while returned rows remain independently checked. Snapshots include the backend calendar day.

`src/utils/homeMovies.js` retains only Home presentation: Trending exclusion, deduplication, nearest release ordering. Its obsolete date check and clock argument were removed. No JSX, CSS, navigation contract, TV behavior, or other movie feed was changed.

## Approved contract comparison

| Approved behavior | Observed result |
| --- | --- |
| Upcoming directly selected in Discover uses backend check | Real advanced route excludes past/unknown/invalid provider dates; rendered card titles match returned movie identities |
| Home View all shares eligibility | Native Home API returns 81 eligible fixture movies; Discover begins with the same first 39 identities |
| Today included, past/unknown/invalid excluded | Both native and advanced route tests assert exact retained IDs |
| Collect replacements before paging | 81 valid matches mixed with past rows and duplicates produce 39,39,3 and 40,40,1, no omitted/repeated valid identities |
| Extra criteria retain Upcoming meaning | Genre, sort, year floor, title, ownership and person-credit API checks; compiled Advanced genre/ownership/sort UI check |
| Midnight invalidates yesterday's selection | Same request on next calendar day drops the earlier day's release |
| Retry and final totals remain truthful | Failed batch is not committed; retry fills page; unfinished local scan reports retryable/unknown count; exhausted stream reports exact eligible count and no phantom Next |
| Existing navigation preserved | Second page survives Library and browser Back/Forward; reopening already-selected feed preserves current page and allows Previous |
| Other feeds and desktop layout preserved | Historical dates retained in other feeds; existing seven real-API pagination tests and 110 broader desktop checks pass |

## Verification results

- Baseline before edits: 32 Discover Python checks and 2 Home Node checks passed.
- Backend regressions were observed failing before implementation. Home presentation was observed failing while the obsolete browser-date gate remained, then passing after removal.
- Final focused Python: **69 passed**; `python-focused.log` includes final code and the duplicate-credit review fix.
- Node: **119 passed**, zero failures.
- Compiled real-backend desktop: **9 passed** (2 new Upcoming checks and 7 existing Discover pagination checks), final combined run in 12.2 seconds.
- Broader desktop: **110 passed**, covering app smoke, movie relationships, and awards, in 2.2 minutes.
- Full Python: **1,728 tests in 576.240 seconds, 2 failures**. This is not a green full suite. The run started before the duplicate-credit review correction; the final focused 69-test run and compiled desktop proof include that correction and both newly added credit/retry regressions.
- Final Upcoming evidence rerun: **2 passed** after positioning the Home screenshot at the Upcoming panel; `desktop-upcoming.log` includes build and test output.
- Independent reviewer found one duplicate-credit bug; reproduced RED, fixed before deduplication, GREEN. Follow-up review found no remaining actionable issues.
- Isolated Vite builds passed. The existing out-of-project temporary-output warning is expected; no production `dist` was overwritten.

Commands: unique OS-temporary `CP_TEST_ROOT` and `CP_TEST_MODE=1`; `.venv/Scripts/python.exe -B -m unittest tests.test_upcoming_discover tests.test_discover_paging_contract tests.test_advanced_discover_api tests.test_unreleased_movie_gate tests.test_tmdb_details_transform -q`; full `unittest discover -s tests -p test_*.py`; explicit `rg --files tests -g '*.test.mjs'` expansion for `node --test`; `npm.cmd run test:e2e -- tests/e2e/upcoming-movies.spec.js tests/e2e/discover-paging.spec.js` with `CP_DISCOVER_PAGING_E2E=1`; normal isolated runner for app-smoke, movie-relationships and movie-awards specs.

### Full-suite failures

1. `test_iptv_movie_gates_0_5.ProjectionAndWorkerTests.test_movies_get_is_pure_and_projection_is_nonblocking_progressive`: GET took 3.999 seconds against a one-second limit in the full run. Isolated rerun passed. No IPTV owner or test was changed by this task; the full run overlapped desktop verification, so the timing cause is not established beyond that observation.
2. `test_qbittorrent_ui.QBittorrentUiTests.test_streaming_modal_shows_loading_feedback_until_iframe_loads`: source assertion expects `streamLoaded`, while unchanged stream UI uses `streamStatusVisible`. This stale assertion was already recorded in earlier CP verification; neither owner nor test was changed here.

Full log retained at `C:/Users/dante/AppData/Local/Temp/cp-upcoming-full-9b3d00bb1a1b482089cbb978931dca7a/full-suite.log`. Assertions were not weakened and these unrelated areas were not amended.

## Desktop evidence and limits

Screenshots use deterministic mixed-date provider fixtures with the real CP backend and compiled UI. Reviewed Discover first-page and Advanced-filter screenshots; Home screenshot is positioned at the Upcoming section in the final evidence rerun. API identities are compared with rendered titles, and complete card counts are asserted across all pages.

Date-only provider requests retain the existing walk up to TMDB's 500-page cap so a sparse finite Home feed can finish. Existing local/title filtering retains the ten-page budget and retry behavior. Cold Upcoming requests can therefore need more provider calls; real TMDB latency was not measured. This is TMDB's recorded release date, not an Egypt-specific release calendar.

Production port 5000 remains PID 100356 and serves `index-pJcXpaa4.js`. Configuration is main-checkout `config.json`; data and TMDB cache owners are main-checkout `data` and `cache`. Configuration, catalog, production bundle, and running process were not changed. Existing dirty TV files were preserved. The broader awards suite regenerated six tracked screenshots; restored only those test-generated files to their recorded clean baseline. No commit, push, package, tag, or release. Live activation requires a separately authorized frontend build and CP restart.
