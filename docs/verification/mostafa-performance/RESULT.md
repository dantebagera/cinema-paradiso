# Mostafa worktree performance repair — 2026-10-12

The measured frontend regressions are repaired and active in the rebuilt preview. The operational backend was preserved. Ordinary Library loading and sidebar navigation are comparable to the Desktop installation in paired measurements; the measurable excess costs were eager offscreen artwork and repeated list metadata construction. The full Python suite is not green; its exceptions are recorded below.

Dante authorized autonomous investigation, source changes, builds, tests and necessary preview restarts, with device shutdown only after the repair and verification. Work was confined to `C:\Users\dante\.codex\worktrees\mostafa-ui-ux\cinema paradiso`, branch `codex/mostafa-ui-ux`, HEAD `be511f98846a67a182e5b371ad087938e9344362`. The original Desktop project was inspected read-only. No commit, merge, push, release or real download/import/delete action was performed.

## Causes and code changes

| Cause | Existing owner repaired | Observable result |
| --- | --- | --- |
| Inline CSS background URLs requested every card's artwork immediately; native lazy poster loading does not govern backgrounds | `src/components/movie-card/cardArtwork.js` owns a shared visibility observer and unchanged style builder; callers in `MovieCard.jsx`, `RelatedMovieRail.jsx`, `IPTVWorkspace.jsx` reuse it | Offscreen collapsed cards defer artwork; visible and expanded cards retain the same gradients, images and geometry. Scrolling activates artwork and keeps it loaded. Browsers without IntersectionObserver retain eager behavior. |
| Default list browsing constructed unused filter metadata; sort comparators repeatedly reconstructed canonical metadata | `src/utils/listCatalogFilters.js` | Default browsing reads no filter metadata. Active filtering/sorting resolves metadata once per member and sorts precomputed keys. Canonical precedence, stable ties, missing-year handling and full membership before paging remain. |

One observer serves shared Movie/TV cards, Upcoming and Continue Home cards, related Movie/TV tiles, and IPTV series tiles. URL replacements receive their own visibility check. Review reproduced a stale-notification race, both after observer retirement and within a reused observer; observer ownership and registration timestamps now reject those old notifications. Regression tests prove a fresh notification still loads the replacement, cleanup does not unregister a newer replacement, and hidden retained Home does not eagerly fetch it.

There were no CSS changes, no visual redesign, no dependency/version changes and no new API or persistence behavior. The three previously approved TV support differences (`tv_metadata.py`, `tv_read_model.py`, `tv_routes.py`) remain the only service differences against the current Desktop source after normalizing line endings. Acquisition, monitoring, player and qBittorrent sources were not changed.

## Measurements

Compiled desktop fixtures use real browser network requests, fake artwork/providers and disposable OS-temp data. They assert visible artwork and subsequent scroll loading, rather than only inspecting source strings.

| Initial backdrop requests | Before | After |
| --- | ---: | ---: |
| Library, 40 supplied cards | 40 | 6 |
| Home, 60 supplied cards across rails | 60 | 5 |
| Related rail, 20 supplied tiles | 20 | 13 |

The Library reduction is 85%; Home is approximately 92%. The related rail intentionally shows more tiles at this desktop width. All returned cards remain reachable; offscreen artwork is deferred, not removed.

| List helper, 10,000 members | Before | After |
| --- | ---: | ---: |
| Default browsing, independent median | 7.13 ms / 10,000 metadata reads | 0.010 ms / zero reads |
| Filtering plus popularity sort, independent median | 126.67 ms / 249,720 reads | 12.20 ms / 10,000 reads |

The independently repeated filtered benchmark is approximately 10.4 times faster and asserts identical identities/order. The implementer's separate five-run median was 134.16 → 13.04 ms. These are synthetic helper measurements with realistic canonical object spreads, not claims that every screen is ten times faster. The saved real lists contain approximately 166–167 members in the largest system list, so their helper savings are smaller.

The original and preview were also measured through their actual running bundles in fresh Chromium desktop contexts, with mutating API calls—including automatic Follow checks—blocked. Both displayed 39 Library cards. In the final interleaved samples (`after.json`):

- Original cold Library readiness: 904 and 926 ms; preview: 889 and 946 ms. Medians are 915 and 917.5 ms, effectively equal at this sample size.
- Twelve sidebar transitions per version: original median 195 ms; preview 196 ms. No page errors were observed.
- A second 120-frame scroll after artwork activation recorded zero style recalculations on both versions; script work was 104.8 ms original and 101.6 ms preview (`warm-after.json`). Deferred image activation adds one-time work on the first pass, not continuing observer churn.
- Repeated expansion/collapse, sidebar return, selection and browser history are covered by compiled regressions. Expansion timings in the diagnostic script include a deliberate 800 ms settlement period and must not be interpreted as pure input latency.

Initial real Library measurements were already similar at about 0.9 seconds. The evidence does not support claiming a general backend slowdown. The repair addresses confirmed added frontend work. Timing samples are small, headless and host-load dependent; they establish measured parity and regression removal for the checked paths, not a universal guarantee for every provider, dataset or interaction.

The optional `identical-before.json` replay supplies matching Library data to both UIs. Its first request fetches the fixture from main and later contexts replay it, so its cold-load times are deliberately excluded from comparative readiness claims. Its renderer metrics remain useful diagnostic evidence.

## Verification

| Gate | Result |
| --- | --- |
| All top-level Node tests on final source | 133 passed, zero failed |
| New list regressions plus existing filter tests | 11 passed; seven new tests observed failing before the fix |
| Independent list review | 2,400 combinations preserve membership/order and canonical resolver precedence |
| Final artwork, scroll return and Continue compiled browser regressions | 18 passed, including seven new artwork tests; eager-request and stale-notification failures observed before fixes |
| Independent artwork review | No remaining findings; both stale-entry harnesses pass 13 assertions |
| Focused final Python UI, TV support and launcher checks | 128 passed |
| Additional IPTV and Movie/TV relationships Python checks | 31 passed |
| Broad compiled desktop suite | 224 passed, zero failed; one TV case skipped on this fixture |
| Proper native-TV streaming fixture | The skipped case passed, 1/1 |
| Native-TV navigation/actions | 7 passed |
| TV expanded-card parity | 8 passed |
| TV desktop parity | Initial 18 passed / 1 failed; unchanged fresh-data rerun 19 passed |
| Final worktree build and served bundle | Build passed, HTTP 200, served index exactly matches final dist |
| Diff whitespace check | Passed |

The initial TV parity failure measured a 12-pixel difference between sequential bounding-box reads of sibling mode/refresh controls. The same transient measurement was documented before this task in the integration result. No CSS, test assertion or tolerance was changed; the complete 19-case rerun passed. The initial failed run remains in `tv-parity.log`. Its default disposable browser artifacts were replaced by the following streaming run; the failure log remains. Final rerun artifacts use a dedicated task output path. Fifteen prior TV screenshots were backed up, fresh copies were saved under this task's `desktop/native-tv`, and prior screenshots were restored.

### Full Python suite exceptions

The complete isolated run executed **1,734 tests in 693.103 seconds**, with **7 failures and 3 errors**. This is not a green full-suite claim.

Three failures arose because the runner explicitly set `CP_TEST_QBT_MODE=system`, whereas the power/proxy tests expect the embedded fixture:

- `test_status_and_after_download_action`
- `test_turn_off_forwards_the_embedded_qbittorrent_choice`
- `test_qbittorrent_webui_has_a_separate_proxy_route`

The affected Power API and React route modules passed **8/8** with a fresh isolated root, copied compiled dist inside that root, and embedded fixture mode. The reusable runner now uses the expected embedded fixture mode. No product source or test assertion was changed for these failures. One attempted focused rerun was correctly rejected because its dist was outside the new test root; the corrected inside-root rerun passed. The original full result is retained.

Three failures are the already documented unchanged baseline issues:

- `test_movies_get_is_pure_and_projection_is_nonblocking_progressive`: unchanged IPTV projection exceeded its one-second threshold (3.30 seconds in this run).
- `test_pinned_offline_inputs_reproduce_complete_seed_and_bootstrap_both_organizations`: pinned offline awards input produced a null seed.
- `test_streaming_modal_shows_loading_feedback_until_iframe_loads`: obsolete source assertion expects `streamLoaded`; compiled loading behavior is covered separately.

Four production-launcher assertions conflict with the previously approved private preview launcher:

- `test_launcher_bootstraps_source_zip_before_starting_flask` — expects `stop_stale_backend.ps1` (error).
- `test_launcher_opens_browser_after_frontend_build` — expects the production `cp_window.ps1` browser helper (error).
- `test_launcher_reports_and_runs_flask_after_build` — expects direct production `app.py` launch (error).
- `test_launcher_closes_only_its_owned_edge_window_and_does_not_pause_on_success` — expects the production window closer (failure).

`run.bat` and these tests were unchanged during this performance task; the pre-task hash proves these are not introduced by the repair. Restoring the production shutdown/launcher calls would violate the approved preview boundary. The dedicated preview launcher tests passed. These legacy assertions were neither weakened nor silently removed.

## Live activation and preservation

The final preview index SHA-256 is `B4563154186A74173DB5D395105BE50BFEFB6AEDDDA30AB90C9C422398B5D4C5`. Before device shutdown, the verified ownership record names supervisor 12148, CP wrapper 91812 (listening child 52692) and private qBittorrent 71004. Their absolute command paths point to this worktree. Original CP remains listener 100356 on 5000; original qBittorrent 9236, Prowlarr 7768, FlareSolverr 57224 and Ollama 1608 retained their owners. Only the verified preview was restarted, with `--no-browser`.

Of 223 captured original files, 222 hashes remained identical, including source, config, dependency files, original dist and launcher. The sole changed hash was the live `data/qbittorrent/jobs.json`. Original acquisition lease count changed from zero to one. The original server and its workers remained running; these differences are consistent with ordinary live monitoring, but the exact writer was not instrumented. No manual journal/lease edit, scan, transfer, import or delete operation was issued. Runtime byte identity is therefore **not** claimed and live state was not rolled back.

All four original and four preview databases report integrity `ok`. Movie, TV and awards table counts are unchanged; original acquisition counts differ only in the transient lease table. All preview table counts and preview `config.json` remained unchanged. Compared with the initial source manifest, exactly the five production files listed above changed. No backend source changed in this task.

An automatic policy check rejected removal of empty incorrectly URL-encoded diagnostic directories beside the worktree. The actual report files were moved into the correct worktree; empty folders remain. No further cleanup bypass was attempted.

## Completion and shutdown

The confirmed performance regressions are repaired, the final code is compiled and active in the private preview, relevant behavior and history paths pass, and remaining suite exceptions are separated from the repair. The original production sources/settings remain protected. The report and supporting evidence are saved before requesting the device shutdown Dante authorized. Normal Windows shutdown will be requested without forced application closure; shutdown dispatch outcome is recorded separately in `shutdown-dispatch.json`.

Primary evidence: `list-performance.json`, `list-benchmark-independent.json`, `artwork-performance.json`, `node-final.log`, `python-focused-final.log`, `python-shared-final.log`, `python-full.log`, `python-environment-rerun.log`, `desktop-regression.log`, native-TV logs, `after.json`, `warm-after.json`, `live-process-proof.json`, `protection-comparison.json`, and desktop PNGs.
