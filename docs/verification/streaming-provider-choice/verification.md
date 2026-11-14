# Streaming provider choice — 2026-10-24

Implemented in source and verified using isolated data and a separate compiled desktop bundle. The running installation was not rebuilt, restarted or reconfigured. No commit, push or release was performed.

## User-visible result

Settings > Streaming Link now offers **StreamIMDB (default)**, **VSEmbed**, and the existing **Custom URL** capability. Save Streaming applies the chosen provider to movies and TV episodes through the existing Stream buttons and shared player. An unsaved draft does not change playback. Existing custom URLs, IMDb resolution, TV overrides, labels, enabled/disabled state, exact episode targeting and watched-state rules remain.

VSEmbed uses `https://vsembed.ru/embed/movie/{tmdb_id}/` and `https://vsembed.ru/embed/tv/{tmdb_id}/{season_number}-{episode_number}`. This is the direct embed investigated earlier, not the Yify catalogue or VidSrc outer advertising page. No claim of permanent ad-free playback, CAPTCHA bypass or newly verified external provider availability is made.

The backend owns the preset catalogue. The saved movie/TV URL pair remains the only persisted streaming target; provider selection is derived from it, avoiding a second saved flag. API metadata is additive and old template-only callers remain supported. Unknown providers, malformed URLs, and non-object JSON fail before saving or runtime mutation.

## Verification

- Baseline focused backend/default checks: **5 passed**.
- Feature tests were observed failing before implementation; review validation cases were also reproduced before fixing them.
- Final focused Python (`test_streaming_config_api`, `test_tv_stabilization`, `test_qbittorrent_ui`): **54 passed**. Includes two real backend processes proving file persistence and provider inference on restart.
- All Node `tests/*.test.mjs`: **140 passed**.
- Final compiled desktop (`streaming-providers`, `stream-player`, `native-tv`): **14 passed**, Chromium 1600×1000. Real Settings/TV APIs; only external movie metadata and embed pages are intercepted.
- Same-session sidebar navigation verifies saved choice reaches Movies and TV without reload; unsaved draft preserves the previous movie provider. Separate reload checks persistence. Exact URLs for movie 864168 and series 900001 S01E02 were asserted for both providers. TV watched/completed state stays unchanged.
- Custom edit/save/error recovery and disabled streaming pass. Existing delayed-load, slow hint, provider 404, shared modal Close/focus and native TV regressions pass.
- Visual inspection: preset selector reuses the shared dialog control styling, 42px height and keyboard focus outline; no cloned player or new mobile UI.
- Independent review: two validation findings fixed and covered; requested same-session coverage added. No remaining feature finding was reported.

Two intermediate desktop runs encountered Windows `UNKNOWN` errors opening old generated native-TV screenshot paths. The same 14 tests passed when run with an OS-temp working directory, leaving native-TV test assertions unchanged. Build outputs and fixture data were outside live `dist`/data.

### Full Python discovery boundary

The final full discovery run completed **1,848 tests in 311.634 seconds**, reporting **4 failures, 12 errors, 5 skipped**. This is not a green full suite.

- Ten errors are in `test_final_card_publication.FinalCardPublicationTests`: `test_complete_no_poster_terminal_card_is_publishable`, eight adverse-case subtests in `test_probe_metadata_and_poster_failures_cannot_publish`, and `test_verified_local_poster_is_publishable`. Their mock candidate lacks `path_key`, producing `KeyError` in the unchanged catalogue owner.
- One failure is `test_trailer_modal_ui.TrailerModalUiTest.test_home_playlist_videos_reuse_the_same_youtube_modal`, which searches for the old `function openYouTubeVideo(` source text. `src/App.jsx` was already dirty before this task and was not edited by this feature.
- The other three failures (crash-boundary subtests) and one error in `test_movie_remaining_qualification` require `CP_TEST_QBT_MODE=embedded`. Another error, `test_tv_library_read_performance.TVLibraryReadPerformanceTests.test_local_rows_preserve_binding_encounter_order`, requires `CP_TV_PERF_BASELINE_SOURCE`. Rerunning those **three test methods with their declared environment passed all three**; the TV baseline path was read from the existing `active-run.json`, not invented.
- The catalogue publication errors and trailer assertion were reproduced with this task's saved **pre-change `app.py` and streaming service**, confirming they do not originate in provider selection. No unrelated catalogue/trailer assertions or implementation were changed to conceal these results.

An earlier full discovery run was stopped when final review changed the source; the complete run reported above used the final backend and API tests. Diagnostic logs: `C:\Users\dante\AppData\Local\Temp\cp-streaming-before-failures.log` and `C:\Users\dante\AppData\Local\Temp\cp-streaming-environment-check.log`.

## Live boundary and recovery

Before the requested computer shutdown, localhost:5000 still belonged to Python PID 51992. It returned the original StreamIMDB movie/TV URLs and served `index-CwW9dSyz.js` / `index-3_nuXu-W.css`, exactly as before this task. Source changes require the normal frontend build/backend startup to become live; no live activation was performed here.

Relevant pre-task source copies and status are retained under `C:\Users\dante\AppData\Local\Temp\cp-streaming-options-6c0d29810f3149b1ae4754b758dc89de`. Full-suite log: `C:\Users\dante\AppData\Local\Temp\cp-streaming-final-full-21233eeed40f47a6b53320672ecb16f2\unittest.log`. Final desktop fixtures/build: `C:\Users\dante\AppData\Local\Temp\cp-streaming-desktop-4c061995b99146efa3c18c87983d5626`; its server on 5118 was stopped after verification.

Screenshots: [StreamIMDB](streamimdb-settings.png), [VSEmbed](vsembed-settings.png).
