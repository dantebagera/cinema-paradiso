# Home performance implementation — 2026-10-20

Source implementation and focused isolated checks are complete. This is not live activation or a measured production speedup. CP was not restarted, production dist was not built or overwritten, and the earlier live diagnostic was not repeated.

## Source changes

| Owner | Change |
| --- | --- |
| `src/App.jsx` | Replaced the coupled movie publication barrier with one active operation per feed. Retains successful snapshots, including empty results, during refresh. Navigation joins active work; actual App unmount invalidates publication. Trending has its own ownership attempt and never waits for Upcoming. |
| `src/App.jsx` ownership publication | Uses existing scoped map replacement, preserving unrelated ownership entries. Catalog changes invalidate pending ownership acceptance; a current read is obtained through the existing cache owner before publishing. Deleted paths are removed immediately. No new cache or cache lifetime. |
| `src/App.jsx` Upcoming lifecycle | Requests logical pages of 20 sequentially only as needed, retains raw candidates and page position, and handles exhausted, incomplete/retryable and failed responses separately. `has_next` takes precedence over provider exhaustion because cached logical pages can remain. A Trending change reprojects the active raw pool without restarting its pages. |
| `src/utils/homeMovies.js` | Exports the shared size constant. Deduplicates/excludes in provider traversal order, selects the first 20 survivors, then applies the existing release-date/popularity/title sort. No frontend release-date eligibility rule. |
| `src/App.jsx`, `HomeWorkspace.jsx` | Stable Home-facing callbacks, memoized selected details projection and ordinary React memo comparison at the existing Home boundary. Power polling and Sidebar controls remain current. |
| `src/App.jsx`, `HomeTrailersPanel.jsx` | Retains resolved trailer content/source/position while refreshing. One active base-or-append operation survives navigation. More videos is disabled during base refresh or append, and successful appends still deduplicate by video ID and advance the existing cursor. Settled error/stale/Retry behavior remains. |
| `src/components/HorizontalCardRail.jsx` | Keeps one ResizeObserver and scroll listener for the mounted track. Reconciles added/removed DOM child nodes without re-registering unchanged nodes. Preserves sizing, arrows, scroll distance, resetKey, native scrollbar and unmount cleanup. |
| Tests | Added `tests/e2e/home-loading.spec.js`; extended `tests/homeMovies.test.mjs`; amended only Home's preview expectation in `tests/e2e/upcoming-movies.spec.js`, retaining the full Discover fixture. |

The checkout remained `master` at `be511f98846a67a182e5b371ad087938e9344362`. Existing dirty tracked files and required untracked components were retained; this task's edits are layered on them. The overall Git diff therefore includes prior work and is not this task's patch alone. No reset, commit, push, package, release or product-data/configuration change occurred.

## Final focused results

| Check | Pass | Fail | Skip | Notes |
| --- | ---: | ---: | ---: | --- |
| Home helpers, browser ownership cache, trailer grouping/title/identity model | 10 | 0 | 0 | `node --test --test-concurrency=1 tests/homeMovies.test.mjs tests/browser_ownership_cache.test.mjs tests/home-trailer-model.test.mjs tests/homeTrailers.test.mjs` |
| Upcoming backend + trailer API contracts | 19 | 0 | 0 | `.venv/Scripts/python.exe -m unittest tests.test_upcoming_discover tests.test_home_trailers_api` |
| New Home loading/navigation cases | 23 | 0 | 0 | A clean 20-case run, then two added boundary cases and one added unmount case on unchanged compiled source; not a single 23-case full-file run. |
| Existing Home hybrid dashboard | 24 | 0 | 0 | Desktop geometry, Following details, history, health, trailer channel/version/loading/Retry and menus. |
| Real Upcoming/Discover integration | 2 | 0 | 0 | Home 20; Discover 81, pages 39/39/3; direct filters and Back/Forward continuity. |
| Real Discover pagination | 7 | 0 | 0 | Expanded/collapsed sidebars, sparse titles, sorting and browser history. |
| Movie scroll return | 7 | 0 | 0 | Discover, Library, lists, AI, pick and browse. |
| Following refresh | 6 | 0 | 0 | Five route-gated cases plus the real import/catalog/SSE/reconnect case in its dedicated disposable fixture. |
| Selected shared Movie rail cases | 10 | 0 | 0 | Cast/related arrows, hover/keyboard focus, async updates, full loaded credits and cross-surface expansion/return. |
| IPTV shared-card consumer | 1 | 0 | 0 | Provider-local grouping, credits, localization and fallback using synthetic seeded providers. |
| Selected TV rail/Home cases | 5 | 0 | 0 | Actor/related rails, Full Credit, biography/filmography and Movie/TV navigation/resume boundaries. |
| Temporary Vite build | 1 | 0 | 0 | Exactly one build; production dist untouched. |

Browser total: **85 unique cases passed**. Node total: **10 passed**. Python total: **19 passed**. The initial combined regression run reported 45 passes and one environment-gated skip; that skipped import-publication case was subsequently run and passed in its proper fixture. No selected case remains skipped or unrun.

The selected Movie rail command used `movie-relationships.spec.js --grep "expanded movie rails|stable async rail|director and cast rail|uses shared rail|related posters reveal"`. IPTV used `app-smoke.spec.js --grep "IPTV Movies keeps"`. TV used `tv-expanded-parity.spec.js native-tv.spec.js --grep "expanded TV cast|TV Full Credit|TV badges|TV library uses|TV Home keeps"`. Every browser run used one worker and zero Playwright retries, with output beneath the temporary root.

## Observed contracts

- Held Upcoming response or ownership did not block ready Trending or trailers. Initial unresolved sections used existing skeletons; successful empty/populated snapshots remained resolved on return.
- Repeated sidebar and browser history navigation reused held feed operations. Append navigation produced exactly the base request and one `next` cursor request, with no conflicting base refresh or duplicated video.
- No-overlap Upcoming used one 20-item logical page. Overlap replacements used two; the duplicate fixture used three, without restarting on navigation. Each completed preview contained exactly 20 unique non-Trending movies, with no ownership scope larger than 20. Proven depletion rendered 0 or 13; incomplete/top-up failures exposed Retry. All twenty cards were reachable with existing arrows.
- A Trending change during a pending fill admitted a previously excluded raw candidate and retained the same `[1, 2]` page traversal. The helper separately pins selection-before-sort and re-projection without overwriting raw candidates.
- Canonical accepted titles appeared after their ownership attempt. Ownership failure in Upcoming did not clear accepted Trending ownership. A deletion during a pending older check did not restore the deleted file/action.
- The 90-group trailer fixture retained all 90 groups and its alternate version. Channel changes, exact alternate video playback, More videos, cursor progression, scroll and source retention passed.
- A power-only update changed Sidebar control eligibility while the Home subtree recorded **zero renders** and unchanged rail nodes recorded **zero observer registrations/disconnections**. Actual child removal/addition generated unobserve/observe calls without disconnecting the track observer. These counts establish avoided work, not milliseconds saved.
- Actual App unmount disconnected all three mounted Home rail observers, removed all rail scroll listeners and ignored held feed completions without starting ownership checks.
- Every direct rail importer was accounted for: HomeWorkspace and HomeTrailersPanel; SharedMovieCards; RelatedMovieRail; TVSeriesCredits. Their affected Movie, TV, IPTV and history consumers were included in the focused checks. Desktop screenshots of retained refresh and 90-group trailers were inspected; existing geometry cases covered 1280–1920 desktop widths. No mobile work.

No observed contract mismatch remains in these focused cases. They are not exhaustive proof for every real provider/catalog or the entire repository.

## Isolation, budget and artifacts

Root: `C:/Users/dante/AppData/Local/Temp/cp-home-performance-99a74cc6bf9a476c8eeeaf74cb5b2a5d`. Environment: `CP_TEST_MODE=1`, unique `CP_TEST_ROOT`, `CP_TEST_DIST_DIR=<root>/dist`, embedded qBittorrent mode, unused nonproduction port 5139. The default system-qBittorrent wrapper was not used.

Existing fixture servers were launched directly behind a temporary guard asserting config/media/data/cache/dist isolation, blocking outgoing server socket connections and subprocess launches, and omitting runtime background-service startup. Browser external DNS was blocked, and the new Home cases also aborted external requests. Synthetic IPTV/TV/completion fixtures used temporary files only; no real download, media scan or provider request was run. The completion fixture's additional TemporaryDirectory paths were constrained beneath the same root. All task-owned fixture processes were stopped.

One build, one worker, no automatic retries. The stopwatch wrapper recorded **221.92 seconds** across all test/build commands, including failing runs. A further **60 seconds** is conservatively charged for setup/teardown, static checks and visual inspection: **281.92/600 seconds** total charged budget. No extension, hardware polling, thermal measurement, storage benchmark or stress test. CPU, physical writes and hardware temperature were not measured; no hardware-risk guarantee or production latency estimate is claimed.

Production `dist/index.html` SHA-256 before/after remained `3AB89CA33082FD92BBA343D5E36FE0CC279131C5B2726229C65F17CF1E42B6E4`. Product source was unchanged after the temporary build. Existing tracked target diffs passed `git diff --check`.

Temporary artifacts include `home-final`, `home-boundaries`, `home-unmount`, `home-regressions`, `shared-rails`, `iptv-regression`, `tv-rails`, `completion-regression`, the build, configuration/guard/stopwatch scripts and fixture logs. Earlier failing traces and the partial synthetic TV fixture are retained, rather than deleted. No persistent harness change was made outside the new/updated tests.

## Failures and remaining limits

- Expected helper red: the uncapped selector returned 23 survivors instead of 20. It passed after the selector change.
- First browser fixture attempt: three failures, remainder stopped, because the notification mock omitted required `items`. Corrected the mock, not product code.
- A subsequent test-only locator failed once after a local script decoded an ellipsis with the wrong text encoding. Replaced that locator with the stable existing loading label prefix.
- Two test-only scroll assertions sampled before scroll/snap completion. The final test waits for the browser's `scrollend` event, retaining the exact position assertion.
- The first TV fixture launch stopped before tests because the process-launch guard replaced a class with a function needed by Python's asyncio import. A blocking subclass fixed the guard. The partial synthetic fixture was preserved under another name. An attempted temporary-fixture deletion was rejected automatically and did not execute; preserving it avoided deletion.
- No product source correction was needed after the single temporary build. Final focused results above all passed; earlier failed executions are not counted as passing.
- Full-repository suites, exhaustive provider cases, independent reviewer delegation, live activation and live before/after performance measurements remain unrun. Delegation and live work were expressly outside this dispatch. The source implementation does not establish a production latency improvement until separately activated and measured.

## Rulings I made

- Helper red first, then one compiled desktop build: the explicit single-build limit superseded a compiled pre-change/final red-green cycle. Cost: the desktop cases were not observed failing against a baseline build.

Deferred minors: none.
