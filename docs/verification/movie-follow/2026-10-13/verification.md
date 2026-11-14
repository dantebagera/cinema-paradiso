# Movie Follow source and isolated verification

Date: 2026-10-13, Africa/Cairo. Approved scope and implementation are recorded in `docs/plans/2026-10-13-movie-follow-startup-scan-fix.md`.

## Results

- Baseline: 100 tests passed before source edits (Movie curation/YTS/routes and TV download/season planning).
- Red: new real-route tests reproduced nine failing assertions across scheduling, repeated scans, alternate titles/years, RSS and future metadata dates. An additional failing test proved that a cached unsuccessful YTS identity read suppressed the next manual scan.
- Focused final suite: 118 tests passed: `tests.test_movie_follow_contract`, `tests.test_user_curation_store`, `tests.test_yts_option2`, `tests.test_curation_routes`, `tests.test_source_search_service`, `tests.test_tv_download_contracts`, `tests.test_tv_follow_season_planning`, `tests.test_tv_source_diagnostics`.
- Broader suite: 39 tests passed: `tests.test_acquisition_decisions`, `tests.test_download_monitor`, `tests.test_movie_identity_service`, `tests.test_identity_verification`, `tests.test_authoritative_identity`.
- Fresh review found one important issue: cold/outage YTS identity reads could multiply RSS and source-result processing time. Two controlled 100-result outage tests failed with 1000 seconds of simulated identity work before the correction, then passed with the existing three-second RSS budget and 25-second Follow deadline. A further failing regression identified short-RSS-timeout poisoning of fallback identity verification; failed cache entries now allow a retry with a larger remaining budget. These are verified source repairs, not real network timing benchmarks.
- After the review timing correction, the combined 159-test suite and both desktop tests passed. After the fallback-cache repair, the final combined suite passed **160/160 tests in 144.417 seconds**, and the real-route desktop suite passed **2/2 in 15.0 seconds**. Final logs: `final-verified-tests.log` and `desktop-verified-tests.log`.
- Vite compiled successfully to the OS-temporary test root. Its usual outside-project output-directory notice is not a compilation failure. Production `dist` was not replaced.
- Desktop: two Playwright tests passed against real Movie Follow routes and persistence with explicit provider fixtures on port 5118. Startup checked a saved future-retry entry, consecutive manual scans found translated-title/year variants without waiting, and a subsequent app reload checked remaining pending films. API state and rendered Home Available labels were asserted together.
- `movie-follow.png` was visually inspected at 1600 x 1000; Home shows Northspur, The Uprising and Practical Magic 2 as Available. Other empty fixture panels do not establish live provider health.
- `git diff --check` passed. Recorded hashes confirmed TV source/docs, configuration, frontend source and other previously dirty files remained unchanged. The pre-existing Upcoming changes in `app.py` were preserved by comparing to its pre-task snapshot.

## Isolation and live boundary

All tests used `CP_TEST_MODE=1`, unique OS-temporary roots, and fixture provider/transfer responses. No production scan, catalog/config mutation, download, restart, deployment, commit or push was performed. The live application still had PID 32648 on port 5000 after verification. The disposable fixture server was stopped after desktop tests.

The fix is source-only until a separately authorized backend restart. A production Movie Follow scan will persist availability results and therefore remains a separate live action. The full repository Python suite was not run; the listed relevant suites are the completed gates.

## Contract comparison

Movie startup/manual scans no longer obey movie retry timestamps or metadata release dates. Actual verified qualifying source evidence decides availability. YTS identity mismatch/unreadability, unresolved target identity, untrusted sources and excluded quality/source types cannot auto-mark Available. Movie Follow remains alerts-only. TV five-hour source retry and lifecycle tests passed without TV edits.

Legacy `next_check_at` API/storage fields remain at zero after updated scans; they no longer control behavior. Existing skipped `unreleased`/`not_due` metrics remain zero to preserve the response shape. No schema or live data migration is required.
