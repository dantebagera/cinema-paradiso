# YouTube Movie streaming — isolated verification

Date: 2026-11-14. Status: implemented in managed worktree; **not activated** in desktop CP.

## Result and contracts

Movie Stream offers YouTube through the shared dialog while web streaming is enabled. Selecting it searches through the existing configured YouTube Data API owner. Actual video duration must be within the movie's TMDB runtime ±5%, inclusive; missing runtime/duration never bypasses the filter. Arabic films use Arabic titles/aliases, with Latin translation suffixes removed. No uploader legitimacy, channel/license, popularity or official-status filter/ranking is used. Results are possible matches, not assertions of complete/correct content.

Search more fetches real next pages/additional queries and deduplicates accumulated results. Use GPT is explicit, uses the existing selected ChatGPT account/model and durable job system (F6), and proposes at most three queries per click. It does not fabricate links, certify results, remove candidates or bypass duration checks. The same search owner executes its queries. Partial successes remain visible with later failures; failed/unattempted queries remain available for normal retry. Cancellation retains completed results, rejects late in-flight additions, and does not invoke further inference.

Results remain available when returning from playback. Non-embeddable videos stay in results with Open on YouTube. External playback has an always-visible YouTube link. Existing Movie chooser, IPTV version playback/cleanup, disabled streaming and exact TV episode behavior remain covered.

## Evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Pre-edit focused baseline | 38 passed | YouTube, Home trailers API, streaming config, AI provider/skills |
| Final focused Python | 72 passed | [focused-final.log](focused-final.log) |
| Broader affected Python | 329 ran: 327 passed, 2 baseline failures | [python-final.log](python-final.log) |
| Node regressions | 21 passed | [node-regression.log](node-regression.log) |
| Compiled desktop regression, TV enabled | 17 passed, no skips | [desktop-final.log](desktop-final.log) |
| Real CP HTTP → search owner → compiled UI | 1 passed, upstream TMDB/YouTube fixtures | [integration-final.log](integration-final.log) |
| Production frontend build | Passed; index-BIL_deZ4.js | [build.log](build.log) |
| Independent review | Three important findings reproduced and corrected | Tests in test_youtube_movies.py, test_chatgpt_youtube.py and youtube-movie-stream.spec.js |
| Rendered desktop inspection | English and Arabic/long-content results inspected at 1600×1000; header buttons separated; no horizontal overflow | [English](results.png), [Arabic](arabic-integrated.png) |

Final focused command: `.venv/Scripts/python.exe -m unittest tests.test_youtube_movies tests.test_chatgpt_youtube tests.test_youtube_movies_api tests.test_youtube_playlist tests.test_home_trailers_api tests.test_streaming_config_api tests.test_ai_provider tests.test_chatgpt_skills tests.test_ai_routes -q` with `CP_TEST_MODE=1` and a disposable temporary `CP_TEST_ROOT`.

Desktop command: `playwright test tests/e2e/movie-stream-sources.spec.js tests/e2e/stream-player.spec.js tests/e2e/streaming-providers.spec.js tests/e2e/youtube-movie-stream.spec.js` against disposable `tests.native_tv_server` on port 5141, with `CP_TV_E2E=1`. Separate `youtube-movie-integration.spec.js` uses `tests.youtube_movie_server` on port 5140 and `CP_YOUTUBE_INTEGRATION=1`. Only upstream movie metadata and YouTube HTTP are replaced in the latter; CP's real route/filter/result projection and compiled rendering are exercised together.

## Baseline failures and harness corrections

The broader suite is **not fully green**. Both remaining failures reproduce in the untouched desktop checkout:

- `test_iptv_movie_ui.IPTVMovieUITests.test_rich_people_localization_and_external_links_are_iptv_owned`: expects an old literal voteCount expression in unchanged IPTV view source.
- `test_trailer_modal_ui.TrailerModalUiTest.test_home_playlist_videos_reuse_the_same_youtube_modal`: expects `function openYouTubeVideo(` while the existing App uses a callback declaration.

Neither assertion was changed. The desktop baseline evidence is [desktop-baseline-failures.log](desktop-baseline-failures.log). Its credential test lacked a created temporary root; the separate corrected baseline credential rerun passed. The final broader run uses `python -m unittest` and passes that test.

Initial isolated build needed untracked/ignored frontend assets and librarySearchRequests.js from the actual desktop source. These were copied before UI editing. The first broad harness used stdin and omitted untracked tools, causing four missing-module errors and Windows subprocess bootstrap failure; copying the existing tools and running unittest normally resolved them. Integration test retry originally counted previous fixture-server calls; its assertion now measures only calls from the current test. These were harness issues, not relaxed product assertions.

## Scope and live boundary

Checkout: `C:/Users/dante/.codex/worktrees/youtube-movie-stream/cinema paradiso`, detached at 117526b with the preserved current dirty source plus this feature. Desktop baseline: master 117526b; running port 5000/PID 52396 serves index-hjeN8MRq.js. Existing YouTube configuration reports configured, region EG. No real API key/account was copied into fixtures.

No production restart, settings/catalog modification, commit, push, packaging, or deployment was performed. All new tests use synthetic metadata/videos/model replies. **Real YouTube availability/playback and a real GPT search have not been verified.** Search metadata and runtime provide candidates, not proof of film completeness. Session state is temporary (30 minutes, at most 128 sessions); expired searches require reopening YouTube. Known movie runtime and an Arabic title for Arabic films are required. These limits do not relax the approved rules.

Activation needs only the feature-specific changes from this worktree, rebuilt desktop assets and an authorized backend restart; preserve existing unrelated desktop changes. The whole dirty worktree must not be copied blindly. `feature.patch` and `feature-files.json` contain the incremental delivery against the desktop/baseline sources; check for subsequent desktop drift before applying. Roll back using pre-activation copies if the new source/runtime/bundle or visible behavior disagrees.

Final cancellation check: repeated terminal job polling initially caused a duplicate status read; the UI effect now depends on job identity/state/revision rather than response-object identity. The same failing assertion passed on three repeated runs, followed by all 17 desktop regressions and the integrated Arabic scenario. The incremental patch passed a read-only `git apply --check` against the desktop checkout.

## Installation update — 2026-11-14

Dante subsequently approved applying the feature to the main desktop installation ("go"), with Dante performing the restart. The 27-file incremental patch passed its drift check and was applied without replacing unrelated source. The 72 focused Python tests passed again in the desktop checkout. Its staged production build succeeded and the installed index-BIL_deZ4.js matches the isolated tested bundle by SHA-256. Every staged asset was verified against the installed copy; index.html was replaced last. Existing assets were retained so already-open tabs can continue using their previous bundle until restart.

The live port 5000 now serves the new frontend bundle. The existing backend process still returns 404 for the new read-only search-status endpoint, confirming that **a full CP restart is still required**. No backend process was stopped or restarted. Source and frontend are installed, ready for Dante's restart; real YouTube/GPT behavior remains unverified.

Rollback copies of all previously existing affected files, plus the previous dist directory and an existed/new-file manifest, are at `C:\Users\dante\AppData\Local\Temp\cp-youtube-activation-backup-5l8rydh8`. Installation details: [activation.json](activation.json), [installed tests](installed-tests.log), [installed build](installed-build.log).
