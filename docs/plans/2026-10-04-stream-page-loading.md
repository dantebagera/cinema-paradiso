# Correct the shared stream loading status

**Status:** Implemented and verified in isolation on 2026-10-04; staged for live installation. Dante authorized: “CHANGE EDGE DNS TO Google ... and fix the preparing stream message”. CP live bundle deployment remains a separate gate. Edge DNS was not changed because Windows denied the policy write.

## Problem and decision

- **What happens now:** `StreamPlayerModal` changes its overlay to “Preparing stream...” on the iframe's load event, retaining it until a 30-second timer. Runtime investigation observed the overlay covering an already playing MobLand episode.
- **What Dante wants:** Correct this misleading message for movie and TV streaming, and select Google DNS in Edge as the network workaround investigated separately.
- **Confirmed:** CP embeds the external player directly in Edge. An iframe load event reports a page load, not the video's playback state. CP cannot inspect the external player across origins.
- **Unknown:** Whether the external player subsequently buffers or fails. This fix must not claim that video playback is ready or successful.
- **Open decisions:** None required for this bounded correction; preserve the existing slow hint and 30-second overlay limit.
- **Scope:** Shared Movie/TV stream modal and obsolete compact overlay styling, regression tests, staged build. Keep URLs, permissions, playback controls, closing and focus return unchanged. No backend, IPTV, watch-history, catalog, release, restart, or live bundle changes.
- **Edge DNS:** Attempt the documented current-user Edge DNS policy with Google's `https://dns.google/dns-query`, preserving automatic fallback. Windows denied creation of the policy registry key; no DNS policy values were written. Manual Edge configuration is still required.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and exceptions | Affected callers | Proposed behavior | Changes the contract? | Dante's decision |
| --- | --- | --- | --- | --- | --- |
| Shared streaming modal, current implementation and requested correction | Movie/TV templates target the same external provider; streaming does not mark watched | Movie entry points and TV episode actions | Preserve target and watched state | No | Authorized correction, 2026-10-04 |
| Truthful stream status, requested correction | CP must not claim playback state it cannot observe | Same shared modal | Report page loading and remove overlay on page load | Corrects the approved defect; no other agreed contract changes | “fix the preparing stream message” |
| Dialog interaction, `usePlayerDialog` | Escape while CP has focus, Close/backdrop close and return focus to opener; provider-frame keyboard events do not reach CP | Same shared modal | Preserve | No | Preserve existing behavior |

## Current design and ownership

- Desktop checkout: `master`, `3c626b7fc5723a65145879b9bd185d446010ce0a`. Initial worktree: only untracked `tools/_debug_trace2.log` and `tools/_debug_trace4.log`; preserve both.
- Live backend: Desktop `app.py`, Python PID 13680, localhost:5000; existing Desktop config/data. Stream config points to `streamimdb.ru/embed/movie/{tmdb_id}` and `/embed/tv/{tmdb_id}/{season_number}/{episode_number}`.
- Live served frontend at baseline: `index-Bj6LDYuH.js`, independently verified through HTTP. Source edits and isolated builds do not change it.

| Responsibility | Authoritative owner | Entry points/callers | Preserve | Obsolete path |
| --- | --- | --- | --- | --- |
| Build external stream URL | `streamMovie` / `streamEpisode`, `src/App.jsx` | Home, Library, Discover, Lists movie actions; TV episode actions | Identifiers, templates, optional movie ID lookup | None |
| Stream status and iframe | `StreamPlayerModal`, `src/App.jsx` | Root `streamModal` state | Dialog size/header, iframe permissions, 12-second slow hint, 30-second status limit | Loaded-but-“preparing” state |
| Dialog/focus lifecycle | `usePlayerDialog` | Existing stream modal | Close interactions/focus restore | None |
| Stream styling | `src/styles.css` | Shared stream overlay | Existing initial loading design | Compact “preparing” rules |

## Exact behavior contract

### Frontend

- Keep the existing desktop stream dialog, header, player shell, loading spinner/bar, typography, spacing and close button.
- Initially show “Loading stream page...” and “The streaming page can take a moment to load.”
- On the iframe's first load event, immediately hide the CP overlay. Do not replace it with a playback-preparation or readiness claim.
- If the page has not loaded after 12 seconds, show “The streaming page is taking longer than usual. You can keep waiting or close the player.”
- Preserve the existing 30-second status limit, including when no page load event arrives. Hiding the overlay does not cancel the request or promise success.
- Closing/unmounting cancels the existing timers. Reopening starts fresh. A page load followed by old timer deadlines must not re-show the overlay.
- Delete compact loaded-state CSS because no caller remains.

### Backend

No backend behavior, persistence, retries, requests or migration changes. Movie/TV identity and progress contracts stay intact. External 404 and network failures remain the provider/browser's responsibility.

## Implementation sequence

1. Add compiled-browser regression tests and reproduce the lingering overlay against baseline.
2. Correct `StreamPlayerModal` itself: remove loaded/preparing state, hide status on iframe load, preserve pending timers with accurate page-loading text.
3. Remove unused compact CSS. Run focused Movie/TV loading and interaction tests, then existing affected movie/TV suites and streaming API tests.
4. Produce a staged frontend and rendered desktop evidence. Keep the live bundle unchanged until its separate authorization gate.

## Acceptance matrix

| Scenario | Action | Expected result | Owner | Verification |
| --- | --- | --- | --- | --- |
| Movie iframe loads quickly | Open Joy Ride fixture stream | CP status absent immediately after page load; provider controls accessible | Shared modal, movie path | Playwright movie page-load regression |
| TV iframe loads quickly | Stream S01E02 | CP status absent; exact typed episode URL unchanged; watched state unchanged | Shared modal, TV path | Playwright TV regression and existing native-TV case |
| Slow page | Hold response; advance 12 seconds | Accurate page-loading status and slow hint | Shared modal | Controlled network response and browser clock |
| Slow page eventually loads | Release response after hint | Overlay disappears immediately | Shared modal | Delayed page regression |
| Provider returns unavailable-media page | Return HTTP 404 HTML | Provider error remains visible; no CP preparation claim | Shared modal | Provider-404 regression |
| No page load within 30 seconds | Hold response; advance clock | Existing overlay time limit remains | Shared modal | Delayed/reopen regression |
| Close and reopen | Escape then stream again | New loading state; no stale slow hint; focus returns on close | Modal/dialog lifecycle | Movie delayed and fast tests |
| Loaded page crosses former deadlines | Advance past 12 and 30 seconds | Overlay stays absent | Shared modal | Movie fast test |

## Verification and rollout

- **Baseline:** Run new immediate-hide test against old compiled UI and record expected failure.
- **Focused:** `CP_TV_E2E=1 npm.cmd run test:e2e -- tests/e2e/stream-player.spec.js`, with runner-created unique temp config/data/dist.
- **Broader:** Existing movie stream/dialog smoke case, Movie relationship suite and native-TV suite, plus streaming config/template API tests in unique `CP_TEST_ROOT`.
- **Compiled UI:** Build into a unique temp staging directory; desktop loading, slow and loaded screenshots from actual compiled CP browser tests.
- **Live work:** Not authorized by this source-fix scope; proposed later deployment backs up live dist, copies verified staged output and checks served/visible behavior without restarting backend.
- **Reporting:** Report DNS failure separately; source/isolated/staged/live results independently. Never label provider page load as successful video playback.

## Verification results, 2026-10-04

- Expected baseline failure: movie iframe content loaded but CP's status remained present (expected count 0, received 1).
- Initial fix run passed the delayed-page and TV regressions. Its fast-page test exposed an incorrect test assumption: Escape inside an external iframe cannot reach CP's document. The test now exercises the existing Close button after interacting with the provider; other Movie/TV tests still exercise Escape with CP focused. No keyboard owner or product contract was changed.
- General compiled-browser suite: **120 passed, 38 skipped, 0 failed**. All 38 skips require the native-TV fixture environment and were covered by the following run.
- Native-TV/shared-stream compiled-browser suite: **41 passed, 0 skipped, 0 failed**, including all four new stream regressions (fast movie, delayed/reopened movie, provider 404, exact TV episode and unchanged watched state).
- Streaming config and TV backend regressions: **43 passed**. Ownership-cache tests: **2 passed**.
- Staged Vite production build succeeded. All **37 files** matched the general browser suite's compiled bundle byte-for-byte; native-TV tests used the same `index-BLiwytC2.js` and `index-DmKtwgPZ.css`.
- Desktop loading, slow, loaded Movie/TV and provider-404 screenshots are retained with the verification record in `C:\Users\dante\AppData\Local\Temp\cp-stream-fix-66c7e44842e84111ad2149b479824593`.
- Suite-generated tracked screenshots were retained in that temporary evidence folder, then restored to their clean baseline. The two pre-existing untracked debug logs were preserved.
- Live port 5000 still serves `index-Bj6LDYuH.js`, with the same backend PID 13680. No live config/data/dist deployment or restart occurred.
- DNS rollback record confirms the two Edge DNS policy values were originally absent. The policy key creation failed with Windows `Access denied`; both values remain absent. The Computer Use skill's required guidance forbids automating in-app security/privacy settings, including the alternative Secure DNS UI change. Provide the manual Edge step rather than bypassing this restriction.
