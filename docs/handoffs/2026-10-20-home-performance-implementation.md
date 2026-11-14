# Home performance: implementation handover

**Prepared:** 2026-10-20, Africa/Cairo. **User:** Dante. **Assistant name:** lam3y.

**Workspace:** `C:\Users\dante\Desktop\cinema paradiso`.

**Read first:** Root `AGENTS.md`, then `docs/plans/2026-10-20-home-loading-performance.md`. This handover adds the latest evidence and execution boundaries; it does not replace the plan's exact behavior or acceptance matrix.

## Purpose and authorization

Dante is leading CP performance work page by page. This task is Home only. He wants the saved recommendations implemented in a new chat; this chat prepared the handover and did not implement product changes.

The explicit preceding instruction was “dont implement yet.” The latest instruction requests a handover for a new task, not implementation in this chat. A receiving chat must distinguish a pasted handover from an instruction to implement. If Dante opens it with the implementation prompt below, proceed within that stated source/verification scope without asking again for each routine step. If this document is supplied as context only, remain read-only until he explicitly authorizes implementation. The 20-card Home Upcoming decision is already explicit; do not reopen it.

Restarts, production `dist` changes, live catalog/config writes, scans, downloads, deletion, commits, pushes, packaging and releases remain separately authorized actions. Approval to implement source is not approval to activate it live. Further live measurements are not automatically authorized by previous observations.

## Implement these recommendations

1. **Retain loaded Home content during refresh:** Trending, Upcoming and trailers keep their resolved cards/empty state visible while refreshing. Initial unresolved content still uses existing skeletons. Preserve settled error/fallback/stale/Retry semantics.
2. **Reuse active requests:** Home → Discover → Home and browser Back/Forward must not duplicate active requests or invalidate useful completion merely because Home is hidden. Preserve actual-unmount/stale-response guards. Trailer base refresh and More videos must not race or lose cursor/video identity.
3. **Make Trending independently ready:** Its response and its own ownership attempt must not wait for Upcoming. Preserve accepted canonical metadata and action eligibility. Upcoming still excludes the effective Trending identities.
4. **Exactly 20 Upcoming after filtering when enough eligible movies exist:** Replace the fixed Upcoming-100 request with existing API pages at `page_size=20`; fetch subsequent logical pages only as needed to replace duplicates/Trending overlaps. A proven exhausted source may display fewer. Do not fetch 100 and merely hide 80. Select the first 20 surviving candidates in provider traversal order and apply the existing release-date/popularity/title sort within that preview. View all opens the existing full Discover Upcoming list with unchanged pagination and totals. Trending remains 20; there is no approved trailer cap.
5. **Reduce unnecessary Home rendering and rail monitoring work:** Stabilize Home-facing props/callbacks and the selected-movie projection; memoize the existing Home boundary without suppressing real updates. Refactor the existing shared rail owner to retain its observer/listener lifetime and reconcile actual child-node additions/removals. Preserve all loaded trailers, groups/alternate versions, channel controls, More videos, scrolling, focus, resizing and arrows. Verify every affected rail caller; do not replace the rail or silently virtualize it.
6. **Assess remaining trailer delay from evidence:** The initial bounded baseline observation has now been completed (below). This recommendation is not an instruction to run it again. Further diagnostics need separate approval. Concurrent channel fetching is only a conditional investigation in the existing service if measured channel-fetch waits justify it, followed by a concrete separately approved implementation amendment.

Do not add startup-scan rescheduling, artwork changes, new cache lifetimes, a new dashboard endpoint, database tuning, provider changes, mobile work or other Home redesign. Those were ideas to assess, not agreed fixes. The new evidence favors the existing fixes first.

## What is confirmed

### Current source/compiled behavior

- `src/App.jsx:530–577`: Home activation sets both movie loading flags, awaits Trending and Upcoming together, then awaits a combined ownership check before clearing both flags. Home is retained/mounted, but loaded cards are replaced with skeletons. This shared dependency is confirmed, not a guess about image or database speed.
- `src/App.jsx:579–621`: Trailers refreshes on every Home activation and discards publication when leaving without cancelling or reusing the network operation. It is otherwise independent of both movie feeds. This trailer loader is identical to the saved HEAD, so the mechanism is not proof that the latest visual amendment introduced it.
- Current trailer UI mounts all loaded groups; the saved Git Home mounted roughly one five-card page. An earlier existing-window accessibility snapshot contained **90 trailer cards**, **20 Trending cards** and **99 Upcoming cards**. Lazy thumbnails do not imply 90 simultaneous image downloads. Extra rendering work exists; its elapsed cost was not profiled.
- App power polling updates top-level state every five seconds. Recreated rail children currently trigger observer teardown/re-registration. Those are the existing owners to correct, not grounds to disable power polling or copy state elsewhere.
- `YouTubeService.get_home_trailers` fetches two channel sources sequentially, with a 30-minute source-page cache; API pages contain up to 50 videos per channel. Source/API wrapper files have no tracked changes versus HEAD. The cached observation below does not exercise expensive channel fetching.

### Measurements already obtained

An explicitly requested direct feed query returned **100 eligible Upcoming movies in 3.453 s**, reporting **16 provider pages fetched**. Trending returned 20 in 0.578 s. Home filtering removed one overlap, **Clayface**, and no further duplicates, leaving 99. Existing-window inspection verified the 99 card entries, ending at **Victorian Psycho**. Reported provider pages can include cache hits; do not describe all 16 as uncached external requests.

Later Dante authorized checking startup competition/artwork. One warm Home → Discover → Home pass was observed in Edge's Network panel; navigation recording was stopped after **15 seconds**, caching stayed enabled and no throttling was enabled:

| Recorded item | Result | Interpretation and limit |
| --- | --- | --- |
| Upcoming-100 request | 3.49 s total; 3.45 s backend/server wait | Most of this request's time was before the response, not downloading posters |
| Trending request | 665 ms | Existing frontend still waits for Upcoming and combined ownership before displaying it |
| Subsequent combined movie ownership request | 534 ms | Adds to the shared movie readiness path, roughly four seconds before rendering; no post-response render-time measurement |
| Library statistics | 1.69 s | Concurrent Home work; not proof it caused another request's delay |
| Trailer request-list Time | About 289 ms | Not a slow channel fetch in this cached visit |
| Trailer detailed connection timeline | 7.88 ms queueing; 282.96 ms stalled; 3.50 ms response wait; 1.65 ms download; 297.12 ms including queueing | Browser-side connection delay exists; request-list and detailed totals have different queue accounting |
| Trailer backend headers | Server-Timing / X-CP-Route-MS: 1.7 ms | Do not implement concurrent channel fetching on the assumption this response spent hundreds of milliseconds fetching YouTube |
| Two subsequent Home `w342` posters | Disk cache, 24 ms and 3 ms | Artwork was not the main wait on this warm return; cold posters/YouTube thumbnails are unproved |

**Causal conclusion:** Strong evidence for decoupling Trending and reducing Upcoming work; evidence of a secondary browser connection stall, but not proof that the Following startup scan caused it or how much changing request order would save. Do not claim a full frontend/backend cause breakdown, a fivefold speedup, or proof against cold image delays. No controlled before/after, fresh-startup or channel-latency comparison has run.

**Diagnostic limits/cleanup:** Edge blocked console script entry with paste protection; it was left intact and no query executed. The successful measurement used ordinary Network UI, not a security bypass or custom remote-debugging connection. No application reload, repeated-load loop, restart or manually requested scan occurred. The 67-request Network total also contains setup/background polling and Discover traffic: it is not Home-only startup traffic. The temporary DevTools window was closed; CP was left on Home. Opening diagnostics can influence timing. No hardware stress, polling or resource-risk guarantee was made.

## Actual baseline and ownership

Checked in the source chat: branch `master`, HEAD `be511f98846a67a182e5b371ad087938e9344362`. There is extensive pre-existing dirty work across Movie, TV, Discover, Home, shared components, tests and plans. No product edits were made by this performance task; only the plan and handover were saved.

In particular, the current Home implementation depends on **untracked** `HomeTrailersPanel.jsx`, `homeTrailerModel.js`, `home.css`, `HorizontalCardRail.jsx` and other shared components. **A fresh worktree from HEAD alone is not the investigated app.** If isolation is used, preserve/reproduce the current working tree including required untracked files, and verify that baseline before editing. Do not commit, reset or discard unrelated work to make isolation easier. Recheck status/diffs because other chats can change the checkout.

Runtime snapshot: production PID 45316, parent 61112, launched through the checkout's `.venv`/`run.bat` on 2026-10-19 around 23:02 Cairo time. Configuration uses checkout `data` and `cache`. Last inspected frontend references `dist/assets/index-CHpNjZGR.js` and `index-C4xx5e9F.css`, built 2026-10-19. These are historical identities, not permission to restart and not guaranteed current. Recheck before any separately approved live claim.

| Responsibility | Existing authoritative owner |
| --- | --- |
| Feed requests, active operations, retained state and publication | `src/App.jsx` |
| Home rendering and memo boundary | `src/features/home/HomeWorkspace.jsx` |
| Trailer cards, channel/version controls and playback identity | `src/features/home/HomeTrailersPanel.jsx`, `homeTrailerModel.js` |
| Upcoming selection/exclusion/sort and planned cap | `src/utils/homeMovies.js::buildUpcomingHomeMovies` |
| Ownership caching and catalog invalidation | `src/api/library.js::fetchOwnershipChecks` |
| Scoped ownership map updates and canonical display | `src/discoverUtils.js` helpers |
| Shared rail scroll/resize/edge/reset behavior | `src/components/HorizontalCardRail.jsx` |
| Discover paging/release eligibility | `app.py::_tmdb_discover_window` and callers; unchanged by this implementation |
| Trailer channel fetching/cache/cursor merge | `services/youtube_playlist.py::YouTubeService`; conditional follow-up only |

Read the existing Home design and Upcoming contract plans linked from the implementation plan. Preserve strict backend-owned release eligibility, canonical metadata, ownership freshness/deleted-path handling, current Movie/TV/IPTV boundaries and desktop layout. Do not add duplicate date/selection logic or a second feed/ownership cache.

## Verification and completion gates

Use the implementation plan's Tasks 1–3 and acceptance matrix. The initial baseline observation under Task 4 is already done; no automatic additional live capture is authorized. Start with the motivating gated response/navigation tests, not another broad investigation or database benchmark.

- No tests or builds have run for this performance candidate. Historical passes are not a current green baseline.
- Before tests, prove `CP_TEST_MODE=1`, unique OS-temp `CP_TEST_ROOT`, temporary `CP_TEST_DIST_DIR` beneath it, unused nonproduction port and service isolation. Compile only to temporary dist. Never use production media/data or overwrite production `dist`.
- **Harness trap:** `tools/run_playwright_e2e.ps1` forces `CP_TEST_QBT_MODE=system` and seeds unrelated fixtures. Do not blindly run `npm.cmd run test:e2e` or assume setting a variable outside that wrapper fixes it. Verify a safe minimal fixture launch first; if it needs a harness amendment, describe the concrete change within the approved verification scope before using it.
- Proposed isolated functional budget: **one worker, one build, at most ten active minutes, no automatic retries or extension**. This becomes authorized only when Dante explicitly approves it (for example by using the prompt below). Respect any separately applicable resource/stop limits; do not add hardware polling to this work. If coverage does not fit, report the unrun gate instead of claiming completion.
- Focused Node checks: `tests/homeMovies.test.mjs`, `browser_ownership_cache.test.mjs`, `home-trailer-model.test.mjs`, `homeTrailers.test.mjs`.
- Focused isolated Python contracts: `tests.test_upcoming_discover`, `tests.test_home_trailers_api`.
- New compiled desktop cases: `tests/e2e/home-loading.spec.js` as specified in the plan, including held responses, retained content/empty states, per-feed readiness, exact request counts, top-ups, errors, ownership/catalog races, trailer cursor/version identity, real callback updates and avoided observer/render work.
- Existing real-API `upcoming-movies.spec.js` currently asserts 81 Home cards. Amend **Home** to the explicitly approved 20-card preview; preserve Discover's full 81-movie fixture and 39/39/3 page assertions. Do not shrink the fixture or weaken shared backend completeness tests, including the sparse finite feed beyond ten provider pages.
- Enumerate every shared rail importer and run its relevant existing scrolling/resize/arrow/focus regressions within the budget. Keep desktop-only scope and all loaded trailers/alternate versions. Render/observer counts prove avoided work, not a measured latency gain.
- Report exact pass/fail/skip/unrun results and remaining contract differences. No declaration of completion while required verification is unrun or unresolved. Source-only/isolated/live are separate statuses.

## Suggested opening message for the new chat

Paste this as Dante's instruction when ready to authorize source implementation and the bounded checks:

> Implement the Home performance changes in `docs/plans/2026-10-20-home-loading-performance.md`. Read `docs/handoffs/2026-10-20-home-performance-implementation.md` and root AGENTS.md first. I approve the planned Home source changes and focused isolated verification: one worker, one temporary build and at most ten active minutes, with no automatic extension. Preserve the current dirty working tree and required untracked components. Do not restart CP, overwrite production dist, change live data/config, trigger scans/downloads, commit, push or release. Do not add startup-scan scheduling, artwork changes or concurrent trailer channel fetching. The initial diagnostic is already done; do not repeat it automatically. Implement the named owners, preserve the agreed contracts and report actual isolated results plus any remaining gates.

This quoted prompt is a proposed future instruction, not approval to act while merely preparing or reading this handover.
