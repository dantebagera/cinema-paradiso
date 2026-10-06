# Discover card-page contract verification

Approved source repair on master at baseline 7e7cda5a24ee579f38a7c1095f41d39944d18345. Normal Movie Discover and Advanced Discover now use one ordered unique-result window in app.py. No frontend layout or card markup changed.

## Contract comparison

| Approved result | Observed isolated result |
| --- | --- |
| Expanded fullscreen: three columns, 39 cards on each nonfinal page | 39, 39, 3 across 81 unique matches; Previous returns the same cards |
| Collapsed fullscreen: four columns, 40 cards on each nonfinal page | 40, 40, 1 across the same stream |
| Finite results and final pages show all remaining matches | Three Lord of the Rings fixture movies show together in both layouts, without pagination; final remainders remain visible |
| Sidebar changes repaginate complete rows | Two repeated collapse/expand cycles pass with stable identities |
| Navigation preserves page contents | Page 2 survives Library navigation, browser Back/Forward and subsequent final-page navigation |
| Explicit filtered sorting preserves unique page membership | Title A-Z traverses all 80 source-unsorted movies in stable 39, 39, 2 slices |
| Smaller desktop still follows measured full rows | At 1920x1080, both sidebar states fit three columns and return 39 cards, including page 2 |

Fullscreen proof uses 3345x1084, the original investigation's desktop viewport. Screenshots use deterministic provider fixtures, not live TMDB film data. API contract tests exercise real Flask GET/POST endpoints; desktop tests consume their actual output, replacing only the upstream provider response. Card counts, computed columns, identities, navigation and final-page controls are asserted.

## Verification results

- Focused Python: 52/52 passed; see python-focused.log.
- Full Python: 1576 tests in 187.981 seconds, one failure. The unchanged test `test_qbittorrent_ui.QBittorrentUiTests.test_streaming_modal_shows_loading_feedback_until_iframe_loads` asserts the obsolete source variable `streamLoaded`; unchanged stream code uses `streamStatusVisible`. Its isolated rerun also fails. This suite is not reported as green. Full log retained at `C:/Users/dante/AppData/Local/Temp/cp-discover-final-suite-ff1a868fb32f4b0a881492fa2b24efc2/suite.log`.
- Full Node: 119/119 passed.
- Compiled desktop contract suite: 7/7 passed in one final run; see desktop-contract.log. A focused Advanced-sort rerun also passed; see desktop-sort.log.
- Broader desktop smoke, movie relationships and awards suites: 110/110 passed in one run (1.7 minutes); see desktop-regressions.log. Total final desktop coverage: 117 passing tests.
- Isolated production frontend build passed; existing index-vJjXGZME.js output remained identical because frontend source did not change.
- Independent review found unstable sorting of a growing filtered prefix and expiry replacing active cache entries. Both were reproduced with failing tests, then corrected. Regression coverage also checks idle eviction, expiry, concurrency, failed-batch retry, local filtering, exact multiples, empty results and the 500-provider-page limit.
- `git diff --check` passed.

Commands: unique OS-temporary `CP_TEST_ROOT`, `CP_TEST_MODE=1`, `.venv/Scripts/python.exe -m unittest tests.test_discover_paging_contract tests.test_tmdb_details_transform tests.test_advanced_discover_api -v`; full `unittest discover -s tests -p test_*.py -v`; `node --test` with explicitly expanded tests/*.test.mjs; `tools/run_playwright_e2e.ps1 tests/e2e/discover-paging.spec.js` with `CP_DISCOVER_PAGING_E2E=1`; normal runner for app-smoke.spec.js, movie-relationships.spec.js and movie-awards.spec.js.

## Desktop evidence

- expanded-page1.png and expanded-page2.png: three-column full pages; expanded-final.png: all three remaining matches.
- collapsed-page1.png and collapsed-page2.png: four-column full pages; collapsed-final.png: final remaining match.
- finite-three-movies.png: all three finite matches with a fourth empty column permitted.

Visually inspected the expanded and collapsed second pages, collapsed final page and finite-three-movies screenshot. Existing card geometry, spacing and controls remain consistent. Navigation scrolls second-page screenshots to the bottom controls, where the final full row is visible; automated counts cover the entire DOM grid.

## Limits and live boundary

Provider overlap removal can require extra TMDB calls. A cold direct deep-page jump reconstructs preceding provider pages, up to the existing 500-page cap. Large explicitly sorted filtered searches can require Retry while the existing 10-page scan budget finishes collecting their stable order. Query snapshots use a 120-second idle TTL and 64-entry bound; active/queued users pin their entry until finished.

Live TMDB latency was not measured. Production port 5000 remains owned by PID 38404; the running Python process was not restarted and has not loaded this repair. Production dist, config and catalog were not changed. Served index was checked again and exactly matches local production dist/index.html. Its SHA-256 is 8E090E71C4F6CEA9F17571703571B01DF0DA82BE90401322CE77D140F03B5914. No commit, push, packaging or release performed. Result is source plus isolated compiled-desktop verification; live activation remains a separate authorization gate.
