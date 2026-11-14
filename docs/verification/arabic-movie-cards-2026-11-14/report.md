# Arabic Movie card defaults — verification

**Status: implemented and tested in the youtube-movie-stream worktree. NOT installed in main CP.** Dante approved implementation with “go”. No main source edits, catalog mutations, restart, commit or push were performed for this feature. Desktop baseline remains the previously installed YouTube/RT source and served index-BIL_deZ4.js.

## Result
Arabic Movie cards use the original Arabic title by default across the shared Library, Discover/indexer, Lists/Following, Maintenance and AI result cards. Home compact cards, Continue Watching, Home inspector, related Movie tiles and the list search picker use the same display rule. Expanded cards fetch available Arabic details through the existing TMDB route; browsing collapsed cards does not issue individual translation requests. Successful requests share a bounded 128-entry, 30-minute session cache, with concurrent calls deduplicated. Failed requests retain source text and offer retry.

English remains immediately available, including during a slow Arabic request. The selection survives close/reopen of the same mounted card; a newly mounted card starts with its language default. Late responses cannot replace a different movie or undo an English selection. TV behavior and IPTV's existing provider-owned Arabic defaults remain unchanged.

Canonical IDs, paths, source/provider selection, ratings, collection membership and owned/custom artwork are preserved. Original metadata survives existing backend summaries, compact SQL card projections, curated entries and Continue Watching; Plex-selected artwork can coexist with the matching TMDB snapshot's Arabic original title. English canonical catalog fields are not rewritten. No schema migration is needed.

**Missing metadata:** CP uses the text it actually has. A movie with no saved Arabic title keeps the available title until normal detail loading supplies Arabic. TMDB may not translate every plot or person's name; missing fields retain available source text. No GPT translation was introduced.

## Evidence
| Gate | Result | Evidence |
| --- | --- | --- |
| New original-field regressions | Missing fields reproduced before correction | tests/test_arabic_movie_cards.py |
| Backend focused/broader regression | 144 passed | python-tests.log |
| Entire existing Node suite plus new display/cache cases | 170 passed | node-tests.log |
| New compiled desktop Arabic scenarios | 8 passed, included below | desktop-final.log |
| Broader desktop regression | 77 passed, 1 confirmed baseline failure | desktop-final.log |
| Real CP API-to-render integration | 1 passed | integration-tests.log |
| Production build | Passed | build.log |
| Independent review | One P2 corrected; no minors or declined items | review.md |
| Incremental installation patch | Read-only apply check passed against current main | feature.patch / feature-files.json |

Python command: `.venv/Scripts/python.exe -m unittest tests.test_arabic_movie_cards tests.test_canonical_catalog tests.test_playback_history tests.test_tmdb_details_transform tests.test_movie_relationships tests.test_user_curation_store tests.test_curation_routes tests.test_iptv_movie_enrichment tests.test_iptv_movie_gates_0_5 -q`, with CP_TEST_MODE=1 and disposable CP_TEST_ROOT.

Node command: `node --test tests/*.test.mjs`.

Desktop command: `playwright test tests/e2e/arabic-movie-cards.spec.js tests/e2e/movie-relationships.spec.js tests/e2e/home-dashboard-hybrid.spec.js tests/e2e/lists-layout.spec.js --grep-invert 390px`, against disposable tests.native_tv_server on 5142. Actual-route integration uses tests.arabic_movie_server on 5143 with CP_ARABIC_INTEGRATION=1; it replaces upstream TMDB HTTP only and verifies the actual Discover projection, details route, rendered Arabic, English switching and unchanged canonical English response. Upstream translation quality was not tested.

Rendered 1600×1000 Arabic Discover and Library cards were inspected: existing geometry and controls remain, Arabic headings/plot/cast are legible, and horizontal overflow assertions pass. [Discover](discover-arabic.png) · [Library](library-arabic.png).

## Review correction and baseline failure
The reviewer found the old loading control disabled English during automatic Arabic fetch. A gated-response desktop regression failed against the pre-fix bundle, then passed after changing the existing control. TV still disables its initial Arabic request because its Arabic state becomes active only on success. All eight Arabic scenarios pass in the final compiled bundle.

The broad suite is not fully green: `lists-layout.spec.js:271` expects `1.5K votes`; current CP shows `1.5K` after the separate RT card layout change. The same assertion failed against the unchanged running main frontend on port 5000, with identical expected/actual text. The test was not weakened. See main-baseline.log and desktop-final.log.

Initial harness corrections: two guessed Python module names did not exist and were replaced with the actual test modules. The first broad UI invocation included two inherited 390px tests; it was interrupted and the final run excluded them. No mobile code was changed. Initial patch checking exposed CRLF/LF differences only; the delivery patch now preserves each main file's existing line endings and passes the read-only check.

## Installation boundary and recovery
The worktree baseline is detached 117526b plus substantial preserved pre-existing changes. baseline.json records the exact backup directory and affected owners. No semantic drift from that baseline was found in current main source. feature.patch contains only the incremental feature; do not copy the whole dirty worktree to main. Main installation and restart remain separate approved actions under AGENTS.md. Before an approved application, recheck drift, back up exact destination files and dist, apply the delta, build staged assets, verify copies, replace index last, and preserve rollback files. A full CP restart is needed for backend projection changes.

Contract comparison: requested Arabic defaults and English access are verified where Arabic metadata exists. Identity, artwork overrides, collection membership and existing TV/IPTV behavior are preserved by code and focused regressions. Real provider coverage and live installation remain unverified; restarting current main alone will not add this new feature until its source/frontend are installed.

## Main installation — 2026-11-14

Dante approved applying the feature to main, with Dante performing the restart. Applied the checked incremental patch and rebuilt main frontend; installed and verified the staged assets with index replaced last. The main build differs from the worktree build due to other checkout differences, so the installed main build was tested independently: 20 Python, 19 Node, and 9 desktop/API integration tests passed. No CP restart or live behavior verification was performed. Backup of affected files and previous dist: `C:\Users\dante\AppData\Local\Temp\cp-arabic-activation-dr6718sy`. A full restart is required for the backend projection changes.
