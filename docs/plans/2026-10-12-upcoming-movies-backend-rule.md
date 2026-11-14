# Upcoming movies: shared backend date rule

**Status:** Implemented and verified in isolation, 12 October 2026; not live. Dante approved the recap and confirmed that selecting Upcoming directly in Discover must apply the same check, then said “go”. Scope: source changes, regression tests, isolated desktop verification. No production restart, catalog changes, commit, push, packaging, or release.

## Problem and decision

- **What happens now:** Home requests `/api/tmdb/discover?list=upcoming&page=1&page_size=100`, then filters past dates in `src/utils/homeMovies.js`. View all selects Upcoming in Discover, whose `/api/tmdb/discover/advanced` results bypass that frontend check. Live API investigation on 12 October returned 37 past-date movies among 40 Discover results.
- **What Dante wants:** Home and Discover both return only movies with a known valid release date today or later; preserve full logical pages and Home presentation.
- **Confirmed:** Both native and advanced routes can use TMDB `/movie/upcoming`. Advanced criteria can switch to `/discover/movie`, title search, or person credits without any future-date rule.
- **Open decisions:** None in approved scope. Use the backend's local calendar date, matching the existing local-calendar Home rule. No regional release calendar is introduced.
- **Scope:** Movie Upcoming native and advanced APIs, shared pagination, Home's obsolete date check, and desktop proof. Other feeds and TV semantics stay intact.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and exceptions | Areas | Proposed behavior | Changes contract? | Dante's decision |
| --- | --- | --- | --- | --- | --- |
| Upcoming recap and direct Discover confirmation in this chat | Known release date today or later, including additional filters | Home and movie Discover | Backend owns the check | Explicitly approved correction | “i agree”, direct-filter confirmation, then “go” |
| Discover full-page contract | Nonfinal logical pages are full; only proven final pages may be short; unfinished scans are retryable | Native and advanced Upcoming | Remove ineligible rows before deduplication/slicing and collect replacements | No | Preserve |
| Home presentation | Nearest release first; no duplicates or Trending overlap | Home | Keep presentation; remove duplicate date rule | No | Preserve |
| Non-Upcoming feeds and TV | Existing dates and filtering retained | Movie non-Upcoming, TV | No date gate | No | Preserve |

## Current design and ownership

Baseline: main checkout `C:\Users\dante\Desktop\cinema paradiso`, `master`, commit `be511f98846a67a182e5b371ad087938e9344362`. Existing tracked/untracked TV changes recorded by `git status --short`; none overlap the planned production files. Production listener port 5000 is PID 100356; main checkout parent uses `.venv\Scripts\python.exe`. Configuration is `config.json` next to `app.py`; `_user_data_dir` and `_tmdb_cache_dir` are independently configured. Production serves `dist/assets/index-pJcXpaa4.js`, built 11 October. Verification builds into a unique OS-temporary root and never overwrites this bundle.

| Responsibility | Authoritative owner | Entry/callers | Preserve | Obsolete path |
| --- | --- | --- | --- | --- |
| Upcoming eligibility | Backend TMDB date predicate, called by shared window and person-credit path | Native route and advanced query feed | Inclusive today, reject unknown/invalid dates | Home frontend date filter |
| Ordered unique pages | `app.py::_tmdb_discover_window` | Both Discover routes | Deduplication, scan budget/retry, provider cap, concurrency, final metadata | None |
| Advanced requests | `services/tmdb_advanced_search.py`, `app.py::_tmdb_advanced_url` | `DiscoverWorkspace::loadDiscover` | Existing criteria and requested sort | None |
| Home display | `src/utils/homeMovies.js::buildUpcomingHomeMovies` | `App.jsx` | Deduplication, Trending exclusion, release ordering | Local-date argument/check |

## Exact behavior contract

### Frontend

Reuse existing `HomeWorkspace`, Upcoming cards, `DiscoverWorkspace`, `DiscoverResultGrid`, and pagination unchanged. Home keeps nearest-date ordering and Trending exclusion. Both Home View all and directly selecting Discover Upcoming use existing navigation and requests. Do not add markup, CSS, mobile behavior, or a new visual owner.

### Backend

Evaluate a strict valid `YYYY-MM-DD` release date against one local backend date per request. Upcoming applies only to `list=upcoming` or normalized `query.feed=upcoming`. Apply eligibility before shared window deduplication and slicing, including native advanced criteria, title searches, local ownership filters, and person credits. General Discover provider requests receive a date lower bound intersected with any existing year lower bound; final eligibility still checks returned data. Person-credit results are filtered before sorting/counting/slicing.

Upcoming cache identity includes the calendar day so yesterday's movies cannot leak after midnight. Filtered totals must describe retained matches, not raw provider counts; expose bounded/unknown totals until exhaustion and exact totals afterward. Use the existing bounded scan/retry behavior. Native provider sorting must not require scanning the whole catalog; retain complete local-order scanning only where existing local sorting needs it. Provider errors remain errors; retry retains successfully gathered matches. No database migration, persistence, or catalog modification.

## Implementation sequence

- [x] Write failing backend regressions for past/unknown/invalid dates, today, replacement paging, all query paths, rollover, retry, and unaffected feeds; run and confirm actual failures.
- [x] Add the backend eligibility predicate and wire existing window, native and advanced routes, and person credits. Intersect provider lower bounds where applicable.
- [x] Remove Home's obsolete date check/argument and retain its presentation tests.
- [x] Exercise compiled desktop Home → View all, direct selection, repeated navigation, Back/Forward, later pages, and additional Upcoming criteria against a real isolated backend with provider fixtures. Compare response identities with rendered cards.
- [x] Run focused/broader Python and Node suites, desktop checks, isolated build, diff review, and document results and limitations here.

## Acceptance matrix

| Scenario | Action | Expected result | Owner/proof |
| --- | --- | --- | --- |
| Past/unknown/invalid dates mixed with future/today | Native and advanced Upcoming requests | Only valid today/future dates | API regression |
| Interspersed past rows, duplicates, 81 valid matches | Request 39/40-card consecutive pages and revisit | 39,39,3 or 40,40,1; no missing/repeated IDs; exact final metadata | Shared window regression |
| Genre/year/sort/title/availability/person criteria | Upcoming query | Dates and criteria both enforced | API/planner regressions |
| Midnight with retained snapshot | Repeat same query next day | Yesterday's dates excluded | API rollover regression |
| No eligible rows within scan budget | Request/retry | No short nonfinal page; explicit retryable result; eventual final remainder | Shared window regression |
| Provider fails after collected page | Retry | Error then successful complete matching page | API regression |
| Empty/final exact multiple | Fetch final page | No phantom Next; exact retained totals | API regression |
| Other movie feed | Same historical fixture | Historical dates retained | API regression |
| Home presentation | Deduplicate/sort backend eligible data | Same Trending exclusion and nearest-date ordering | Node test |
| Motivating desktop path | Home → View all, direct Upcoming, later page | Backend eligible IDs equal rendered card IDs | Real compiled desktop check |
| Navigation | Repeat, Back/Forward | Restored Upcoming selection/results; can continue paging | Desktop check |

## Verification and rollout

- **Baseline:** 32 Discover-related Python tests and 2 Home Node tests passed before edits. No current full-suite baseline inferred from previous runs.
- **Focused:** Unique temporary `CP_TEST_ROOT`, `CP_TEST_MODE=1`, Python unittest Upcoming/Discover suites; no external providers. Node Home suite.
- **Broader:** Full `unittest discover -s tests -p test_*.py`, expanded `tests/*.test.mjs`; report any failures by name. Existing dirty TV work is preserved.
- **Compiled UI:** Build using Vite `--outDir` under temporary root; run desktop Chromium against isolated real Flask routes. Fixtures replace only provider access, not CP's route/date/paging code.
- **Live:** Not approved. Leave production process and served `dist` untouched. Source rollback consists of reverting only this task's named changes.
- **Reporting/contract comparison:** Record actual outcomes and counts; separate isolated compiled proof from live activation.

## Execution decisions and review

- Implemented in the current checkout, touching no pre-existing dirty TV files. Existing dependencies were reused; no install, worktree, commit, or production action.
- Date-only native/provider queries retain the existing provider walk (up to 500 pages), so Home's one 100-result request can finish a sparse finite Upcoming feed. Existing locally filtered/title/ownership scans retain their ten-page budget and retry semantics. Date filtering alone does not force a full scan for provider-native sorts.
- Existing navigation behavior is preserved: reopening an already-selected Upcoming feed retains its current page. Initial View all changes the feed; Back/Forward restores the page. The first new desktop test incorrectly expected a repeat click to reset page one; corrected after observing real CP behavior, without changing product navigation.
- Independent review found person-credit deduplication could discard an eligible second copy when an earlier credit had an unknown/past date. Added a failing regression, moved the same eligibility gate before deduplication, then passed the regression. Reviewer confirmed resolution and no remaining actionable issues.

## Final verification

69 final focused Python checks, 119 Node checks, 9 combined Upcoming/pagination desktop checks, and 110 broader desktop checks passed. A final two-test Upcoming evidence rerun also passed after positioning the Home screenshot at the Upcoming panel. Isolated Vite builds and `git diff --check` passed.

Full Python run: 1,728 tests in 576.240 seconds, two unrelated failures; this is not a green full suite. IPTV's `test_movies_get_is_pure_and_projection_is_nonblocking_progressive` exceeded its one-second GET budget during the full run and passed in isolation. `test_streaming_modal_shows_loading_feedback_until_iframe_loads` still asserts obsolete `streamLoaded` in unchanged stream UI. The full run began before the review's duplicate-credit correction; the final 69-test focused run and all compiled desktop proof include that correction, plus the new credit/failure-retry tests. See `docs/verification/upcoming-movies/2026-10-12/verification.md` for exact boundaries.

The broader awards tests regenerated six existing tracked screenshots; restored only those test-generated changes to the recorded clean baseline. Pre-existing dirty TV files remain untouched. Production listener PID 100356 and served `index-pJcXpaa4.js` are unchanged. Configuration owner verified as main-checkout `config.json`, data as `data`, and TMDB cache as `cache`; isolated tests used separate temporary roots.
