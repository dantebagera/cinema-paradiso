# Plex Rotten Tomatoes ratings for owned and unowned movies — implementation plan

**Status:** Approved for isolated implementation and thorough testing by Dante on 2026-11-14; live activation is not approved. Original plan request: Dante requested: “good write the implementation plan for this, owned and unowned movies, with no slowdown to the cards”. Dante subsequently approved isolated product implementation and thorough testing. Live data changes, restart, commit and deployment remain outside this approval.

**Latest clarification, 2026-11-14 — authoritative:** Plex is optional. Missing/disconnected/unavailable Plex must never surface a user-facing error. CP saves owned Library movies' Plex RT scores and continues displaying those saved scores if Plex later goes away. Unowned movies show no RT scores when Plex is disconnected/unavailable, even if an online score was cached earlier. RT loading is lazy; no card, poster, detail view or user action waits for it. This explicit clarification supersedes this draft's earlier general stale-cache display policy and its local-server-offline online fallback. This clarification governs the approved isolated implementation.

> **For agentic workers:** After implementation approval, use `superpowers:executing-plans` for inline execution, or `superpowers:subagent-driven-development` if Dante chooses delegation. Follow the checkboxes and stop at a failed acceptance gate. Preserve unrelated dirty work. Do not commit automatically.

**Goal:** Display separate Rotten Tomatoes critics and audience percentages on existing full Movie cards, using saved Plex Media Server ratings for owned movies and Plex's online metadata catalog for unowned movies, without making cards or posters wait for ratings.

**Architecture:** One optional Movie ratings service owns Plex score normalization, a small independent persistent cache, and bounded background retrieval. Existing catalog and detail responses do not depend on it. One shared frontend cache and one shared ratings presentation serve every opted-in full Movie card; TV remains separate.

**Tech stack:** Existing Flask/Python standard library, SQLite, React, CSS/SVG, unittest, Node tests, and compiled Chromium Playwright. No new package or paid provider.

**Spec:** The agreed design is recorded in this document's [problem and decision](#problem-and-decision) and [exact behavior contract](#exact-behavior-contract). Project authority: [AGENTS.md](../../AGENTS.md), [plan template](_template.md), [Movie details decisions](../second-brain/movie-and-tv-details.md), [Movie details Atlas](../atlas/movie-and-tv-details.md), and [app-wide poster priority](2026-11-14-app-wide-poster-priority.md). These sources and this plan travel together.

## Problem and decision

- **What happens now:** `_fetch_plex_library` in [app.py](../../app.py) reads `rating` or, as a fallback, `audienceRating` into one `plex_rating`. It does not retain source markers or separate RT scores. Shared cards display the existing generic star rating. CP has no online Plex ratings lookup for unowned movies.
- **What Dante wants:** Owned and unowned movies show both scores, fresh tomato/rotten splat and upright/tipped popcorn as appropriate, on collapsed and expanded full cards. Cards stay immediately usable. Ratings arriving later must not move their contents.
- **Recorded decisions:** Dante accepted the bottom ratings-area placement for collapsed cards, upper-right placement for expanded cards, retention of the existing star rating/votes, reserved score slots, and missing-score dashes. He explicitly requested the rotten tomato and fallen popcorn variants. The percentage boundary discussed was 60%; special certification must not be inferred from a percentage.
- **Confirmed by read-only requests on 2026-11-14:** The configured Plex server has 3,999 movies. Its responses identify RT critics/audience separately. The online `metadata.provider.plex.tv/library/metadata/matches` endpoint accepts the existing token and exact TMDB IDs, returning RT scores without library ownership. Jeanne Dielman (TMDB 44012) returned 95%/77%, New York, New York (12637) 58%/58%, and Tokyo Story (18148) 100%/93%. All three were absent from the Plex library by Plex GUID and title/year. These are sampled Plex observations, not a promise of current RT-site parity or universal coverage.
- **Additional confirmed detail:** `/library/sections/1/all` omits `Guid` external IDs on this server. Adding `includeGuids=1` returned TMDB and IMDb IDs for all three sampled local titles, with the same source-tagged scores. This parameter must not silently enrich CP's existing identity/matching input.
- **Unknown:** Catalog-wide online coverage, score age at Plex, long-term endpoint stability, sustained service limits, and grid performance with the feature implemented. Three online ID lookups took 0.25–0.28 seconds each; this is not grid performance evidence. Existing credentials worked without buying another service; no universal free-account entitlement is inferred.
- **Open product decisions:** None needed to prepare this draft. The engineering values below (cache age, request bounds, dimensions and measurement tolerances) are proposed by lam3y and become the implementation specification only when this plan is approved. A layout or performance failure is not permission to weaken the agreed behavior.

### Scope and alternatives

Use Plex, not MDBList/OMDb or RT website scraping. A local-library-only solution was tested but cannot cover unowned movies. Plex's exact-ID online lookup solves that gap with the existing credentials.

Included: full Movie cards in Library, Discover metadata results, Discover torrent/indexer results with established movie IDs, Movie Lists, Home expanded details, AI result cards, and matched IPTV movie cards. Owned/unowned copies of the same accepted movie share scores. Unmatched/non-film IPTV entries do not request ratings.

“Owned” means accepted ownership in **CP's Movie Library**, not the current page, Plex membership alone, a list entry or IPTV availability. A Library-owned movie shown in Discover still receives its saved offline scores. Online cache entries for unowned movies are an optimization, not permission to display them offline.

Excluded: TV shows/seasons/episodes; compact Home Continue/Upcoming tiles; poster-only related/collection tiles; acquisition/file rows without full cards; new filters or sorting by RT; changing star-rating meaning; changes to movie matching, ownership, catalog publication, playback, downloads, or manual corrections. Opening a full Movie card from an excluded compact tile shows ratings there. No mobile redesign or mobile testing. Live catalog refreshes, Plex refreshes, restarts, installs, commits, pushes and releases need their applicable separate approval.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior / exceptions | Affected callers | Proposed behavior | Changes contract? | Dante's decision |
| --- | --- | --- | --- | --- | --- |
| This conversation: two RT scores and icon states | Critics and audience separate; 60% positive boundary; missing is not zero | Full Movie cards | Add two clearly identified percentages | Explicit requested addition | Design and isolated implementation approved |
| This conversation: no card slowdown | Cards/posters/actions do not wait for ratings | All opted-in cards | Deferred local reads and background Plex work; measured gates below | No weakening permitted | Explicit requirement |
| Dante's latest optional-Plex clarification | Saved owned scores survive disconnect; unowned scores disappear while Plex unavailable; no user-facing failure | All Movie surfaces, including cached/revisited cards | Ownership-aware visibility and quiet unavailable states; no offline online-provider bypass | Supersedes earlier draft cache/fallback proposal | Explicit decision in this chat, 2026-11-14; no further decision needed for this amendment |
| App-wide poster priority plan | Visible posters finish/fail before deferred collapsed backdrops; expanded artwork remains immediate | Movie, TV, Home, IPTV, rails | Extend the existing scheduling owner for deferred ratings without altering artwork policy | No | Preserve |
| Existing Movie identity/manual-match contracts | Accepted identity and manual locks remain authoritative | Library, Discover ownership, IPTV | Ratings are keyed by verified IDs and cannot modify identity | No | Preserve |
| Current star rating, votes, awards and actions | Keep their current values and behavior | Shared Movie cards; TV shares `ExpandedRating` | Add RT slots; leave existing rating choice and TV presentation intact | No | Preserve |
| CP desktop design and density | Preserve grid/card/poster geometry, titles, artwork and controls | All shared surfaces | Fit within existing rating areas; no new card height, hidden awards or reduced poster sizes | No | Preserve |

No existing test was established to contradict these agreed contracts in this investigation. New tests must assert both the returned payload and rendered result. If implementation discovers a conflict or needs to hide existing information, raise the separate `## ⚠️ CONTRACT CHANGE — DANTE'S DECISION REQUIRED` notice required by AGENTS.md; do not approve it through a changed assertion.

## Current design and ownership

### Baseline recorded during planning

- Checkout: `C:\Users\dante\Desktop\cinema paradiso`, branch `master`, HEAD `117526b`.
- Before this plan: 169 tracked changed/deleted files and 1,680 individual untracked files (`--untracked-files=all`). Several owning files and guides already have unrelated edits. Preserve them; an older clean commit is not the correct performance baseline.
- Config owner: checkout `config.json`; configured user data and TMDB cache are checkout `data` and `cache`. Never put tokens in this plan, evidence fixtures or logs.
- Runtime: port 5000 was owned by PID 31268, `Python312\python.exe app.py`, with checkout `.venv` launcher PID 30104 observed earlier in this investigation. Served frontend entry: `/assets/index-XKXIpEzP.js`, matching checkout `dist/index.html` at inspection. Python source loaded at startup is not proven identical to all current dirty files.
- Earlier poster-priority documentation names a different PID. That is historical evidence; use the observed current PID above and recheck at execution/activation.
- No product tests/builds were run during this documentation-only task. Current baseline suite failures are unknown. No source change is live because of this plan.

| Responsibility | Authoritative owner | Callers / behavior to preserve | Decision |
| --- | --- | --- | --- |
| Local Plex catalog sync | `app.py::_fetch_plex_library`, `_auto_sync_plex`, `AppMetadataStore`, `CatalogRepository` | Existing file matching, `plex_rating`, metadata projection, sync timing | Reuse transport and feed already-fetched score facts asynchronously; do not alter identity payloads |
| Accepted Movie identity | `services/authoritative_identity.py`, `canonical_catalog.py`, canonical frontend data | Manual matches, ID corrections, IPTV accepted-film state | Consumers supply accepted IDs; ratings never write these owners |
| Full card layout | `src/components/movie-card/MovieCard.jsx::UnifiedMovieCard`, `ExpandedRating`, `movieCard.css` | Movie wrappers and TV callers | Add optional Movie ratings identity; default absent leaves TV unchanged |
| Movie wrappers | `SharedMovieCards.jsx`, `DiscoverWorkspace.jsx`, `HomeWorkspace.jsx`, `IPTVCards.jsx` | Library/Discover/Lists/AI, indexer results, Home details, matched IPTV | Pass authoritative identity to the same card owner, no copied rating markup |
| Artwork eligibility | `cardArtwork.js::createCardPosterPriority`; `App.jsx` supplies its context | Visible/clipped/hidden cards, poster failures, immediate expanded artwork | Extend this owner with a deferred-work subscription, not a competing poster-ready detector |
| Optional display enrichment precedent | `MovieAwardsContext.jsx`, `movie_awards_routes.py`, `movie_awards_store.py` | Separate optional data and non-blocking presentation | Follow the separation pattern; do not put ratings in awards or duplicate its business logic |
| Tooltips | `src/components/Tooltip.jsx` | Existing hover/focus behavior | Reuse for source, score type and retrieval time |

## Global constraints

- The existing movie list, search, ownership-check and detail APIs acquire no ratings dependency, database join, await, network call or catalog-generation change.
- Do not call `_auto_sync_plex` from a ratings route; it can perform substantial existing catalog work.
- No requests in render functions, no suspense boundary around cards, no per-card polling, no full-app rerender per score.
- Plex absence/failure is an expected optional-feature state, not an app error. No banner, toast, modal, card error, notification or connection prompt. Owned saved RT scores remain; otherwise the RT content is hidden without changing card geometry.
- No new whole-library index/scan to show ratings. Reuse score facts from an already-running normal Plex sync; any extra local metadata lookup is for a visible owned movie only. No startup prefetch or offscreen enrichment queue.
- Reuse the existing Plex URL/token server-side; online requests go only to the fixed Plex metadata host. New browser responses never expose the token. Do not broaden the existing settings API as part of this work.
- No autonomous whole-online-catalog crawl, no commercial rating service, no new provider configuration UI or permanent feature flag.
- Tests use isolated temporary data and mocked provider transport; production `dist`, catalog and configuration remain untouched until separately authorized activation.

## Exact behavior contract

### Frontend

**One presentation owner.** Create `MovieRatings.jsx` inside `src/components/movie-card/`, used only by `UnifiedMovieCard` when `ratingsIdentity` is supplied. `ratingsIdentity` contains validated Movie identity hints: `{tmdb_id, imdb_id, plex_guid}`; preference order is TMDB, then IMDb, then an accepted Plex Movie GUID. Do not derive IDs from a title, filename, translated text or a torrent's release name. Wrappers use accepted canonical owned metadata before provider summaries. IPTV opts in only for `movie.matched` and an accepted TMDB Movie ID. A TV ID is never treated as a Movie ID.

**Optional Plex and saved scores — visibility matrix.** Resolve CP ownership using the existing accepted ownership result on the card, with server confirmation from the existing catalog owner in the deferred ratings request. Do not create a second persistent ownership index. The backend returns `owned`, `display_allowed` and the applicable saved score; the shared renderer applies that decision consistently on every surface.

| CP ownership / saved data | Plex state | Display |
| --- | --- | --- |
| Owned, valid locally captured RT scores saved by CP | Any state, including removed credentials and restart offline | Show saved scores; no Plex request required to show them |
| Owned, no saved local RT score | Missing/disconnected/unavailable | No RT content, no error; never invent a score |
| Unowned, even with prior online cache | Missing/disconnected/unavailable or availability not yet established | No RT percentages, verdict icons or error text; retain invisible layout reservation |
| Unowned | Configured and available | Show eligible cached scores or fill them lazily after exact-ID lookup |

Plex failure does not erase owned saved scores. Removing a movie from CP's Library revokes its owned exception; a retained cache row alone never grants offline display. Newly owned movies do not turn an old online observation into a saved local-Plex observation: obtain/retain verified local scores when available. Availability is observed asynchronously, not guaranteed instantaneously: once a failure/config change is detected, hide unowned scores across subscribed cards immediately. Never block rendering to prove availability.

**Placement and dimensions.** Preserve existing grid columns, padding, poster width/height, title area, star value/vote count, award sizes and controls. Collapsed: put the RT pair in `.unified-rating-row` between the existing star block and awards. Expanded: keep the star/vote block upper-right and put the labelled RT pair beneath it within the existing header metadata area; awards and IMDb/expand controls remain accessible. Refactor shared layout rather than adding workspace-specific CSS overrides. Scope new styling under a Movie-ratings class; `ExpandedRating` without ratings stays identical for TV.

- Collapsed RT pair: two fixed 64px cells with an 8px gap; 16px icons; 4px icon-to-text gap; 13px, weight 800, tabular percentage numerals; each cell fits `100%`. Use CP text and spacing variables. Keep icons' red/green identity colors; do not turn all icons gold.
- Expanded pair: 18px icons, 13px text, explicit `Critics` and `Audience` labels, 12px gap; reserve the pair's full dimensions before results arrive. Use the existing header's two-line arrangement; do not widen its maximum width by silently squeezing the title.
- Existing votes and awards may retain their existing wrapping behavior. The added pair cannot increase the baseline outer card box at the tested desktop widths. If the dimensions cannot satisfy that condition, stop this UI task and present measured alternatives to Dante rather than shrinking existing content or omitting a score.
- Use one set of four small, locally bundled SVG depictions in `RottenTomatoesIcons.jsx`: red fresh tomato, green rotten splat, upright popcorn, and tipped/spilled popcorn. These must be recognizable artwork, not emoji or a generic star. Create CP vector depictions; do not copy a remote logo without checking its asset terms. All icon paths are bundled with the UI; no runtime icon download or icon font.
- `critics >= 60` selects fresh, `< 60` rotten; `audience >= 60` upright, `< 60` spilled. Missing/invalid values render a neutral em dash with no verdict icon. Zero is a real score and shows `0%` with the negative icon. Do not render Certified Fresh or Verified Hot badges in this scope.
- Hover/focus labels: `Rotten Tomatoes® critics: 95%` / `Rotten Tomatoes® audience: 77%`; description `Via Plex · Retrieved <localized date/time>`. This is retrieval time, not an invented RT publication/update time. Offline owned scores say `Saved in CP · Retrieved <localized date/time>`; do not add a failure message.
- When Plex is available, neutral dashes can represent a genuinely missing score type, with `No critics score available` / `No audience score available` tooltips. While waiting for eligibility/availability or when optional Plex is unavailable, hide RT content and its focus targets with the same reserved geometry; no visible unavailable/loading/error label. No spinner, toast, shimmer, animation, retry button or extra expanded panel. Suppression also applies to old unowned browser-cache results.
- The score pair is informational; no click-to-filter, playback action or external navigation is introduced. Keyboard focus opens tooltips without triggering card expansion. Accessible names include source, score type and value; decorative SVGs are hidden from assistive technology.

**Eligibility and scheduling.** Add one `MovieRatingsProvider` under the existing root `CardPosterPriority.Provider` in `App.jsx`. It owns one shared `IntersectionObserver`, one client scheduler and per-identity subscriptions via `useSyncExternalStore`. Reuse workspace and horizontal-rail clipping rules. Hidden retained workspaces and fully offscreen cards neither enqueue work nor poll. Unmount/identity change removes registration and pending work; React StrictMode must not double-fetch.

Extend `createCardPosterPriority` with `subscribeDeferredReady(listener)`, `isDeferredReady()` and `deferUntilVisiblePosters(element, callback)` (returns cancellation). The readiness predicate is owned there and checks actual visible unsettled posters. Keep `watchPoster` and existing backdrop semantics. Ratings release only after visible posters have loaded/failed and the existing backdrop-start callbacks have been issued, followed by an idle callback with a 250ms fallback. Recheck visibility, identity epoch and readiness immediately before dispatch. No synthetic “ready” timeout overrides a genuinely pending visible poster. If an image stays hung, its card and actions still work; ratings can wait. With no IntersectionObserver/requestIdleCallback, use guarded post-paint scheduling; never fetch synchronously during render.

Additionally pause new ratings dispatch and defer response publication during scrolling, active keyboard/pointer input, and route transitions; resume only after 150ms without such activity and a fresh poster/visibility check. The 250ms fallback only schedules another eligibility check, never forces work through a busy UI. Use bounded per-identity updates after paint; no synchronous parsing of a full ratings catalog or DOM-wide scan on each score. Card rendering and user interaction always win, even if scores appear much later or never during continuous interaction.

The pause applies to fetching and adding/updating score content. A small ownership/connection invalidation that hides disallowed stale content is immediate; it does not wait for idle and must not invoke a full-grid rerender.

Browser-session owned saved scores display synchronously when accepted ownership and the cache owner still agree. Unowned session hits additionally require current availability permission; never flash them while that permission is unknown/expired. A fresh page's disk-cached results need one deferred, local CP batch read; do not call that first-render instant. This small delay in scores is intentional to keep cards/posters first.

After eligibility: coalesce within 50ms, up to 40 distinct identities per request. Allow one ratings HTTP request in flight per browser tab. Read cache once, submit missing/stale identities once, then poll only pending visible identities every 1 second, up to 15 polls per demand cycle. Stop polling when hidden, after terminal states, on generation change, or at the cap. Revisit/focus can resume after server `retry_at`; no continuous polling for a completed grid. A newly visible poster pauses subsequent polling/dispatch. Never cancel an already-used shared result because one of several cards unmounted.

Use a bounded 1,000-entry in-memory LRU for unobserved results; subscribed entries stay alive. Notify only subscribers of changed identities. Cached results are independent of card expansion and Arabic display, but visibility permission is re-evaluated on accepted ownership, Plex availability, config/root and workspace changes. Consume existing ownership/config events rather than polling another catalog copy. A visibility-permission notification can suppress scores, never rerender the whole card grid.

### Backend

**Owners and public interfaces.** Add:

- `services/movie_ratings.py`: `MovieRatingsService`, local/online retrieval and its single score normalizer. Interfaces: `normalize_plex_ratings(item) -> dict`; `read(identities) -> dict`; `request(identities) -> dict`; `offer_local_snapshot(rows, section_ids) -> None`; `invalidate_config() -> None`; `stop() -> None`. Constructor injects data-root/config providers, existing ownership resolver, clock and HTTP transport for tests. `read` never performs provider I/O or starts workers; `request` enqueues bounded work and returns immediately.
- `services/movie_ratings_store.py`: `MovieRatingsStore` with `read_many(keys)`, `publish(records, expected_epoch)`, and `read_state()`. It alone writes `<user_data_dir>/ratings/movie-ratings.sqlite` and owns schema version 1, WAL, short transactions and score-cache generation. Reads use a separate connection with a 50ms busy timeout; unavailable/locked/corrupt caches return a ratings-only unavailable result. Do not hold any catalog lock or network call inside a transaction.
- `services/movie_ratings_routes.py`: `register_movie_ratings_routes(app, get_service)`; wires the two bounded endpoints below. App wiring owns a lazily created service per resolved data root/config epoch, stops it on config changes and `_shutdown_library_background_services`, and does not start network work on import or app startup. A successful already-running Plex sync may create the lightweight persistence worker to save owned scores without a card visit; this starts no additional network fetch.

**Identity and payload.** Normalize validated identifiers to `movie:tmdb:<positive integer>`, `movie:imdb:tt<digits>`, or `movie:plex:<24-hex-id>`. Reject malformed IDs, TV types, bodies above 32KiB, more than 40 distinct items, and empty identities with HTTP 400. IDs identify metadata, not ownership. Cross-ID aliases are published only when a single Plex Movie payload explicitly confirms them; title/year matching is forbidden. If submitted TMDB and IMDb IDs conflict, return `identity_mismatch`, not the first search result. If a response lacks the queried ID or yields ambiguous matches, publish no score.

Both routes accept `{"items":[{"tmdb_id":"44012"}]}`. Each item may additionally carry `priority: "visible" | "expanded"` (default `visible`); this affects queue ordering only, never identity keys or score data. The read route ignores that priority. Both return:

```json
{
  "schema_version": 1,
  "owner": "opaque-root-and-config-epoch",
  "generation": 7,
  "plex": {"state": "available", "valid_until": "2026-11-14T12:05:00Z"},
  "items": {
    "movie:tmdb:44012": {
      "state": "ready",
      "owned": false,
      "display_allowed": true,
      "critics": 95,
      "audience": 77,
      "source": "plex_catalog",
      "retrieved_at": "2026-11-14T12:00:00Z",
      "stale": false,
      "retry_at": null
    }
  }
}
```

Timestamps/generation above are illustrative. `state` is one of `missing`, `pending`, `ready`, `not_found`, `unavailable`, `identity_mismatch`; these are internal states, not user-facing errors. `plex.state` is `not_configured`, `unknown`, `available`, or `unavailable`. Partial scores use `null` for the missing type and `ready` for the present one. Persist raw validated 0–10 score, normalized integer percentage, type, source marker, exact aliases, retrieval/expiry times and bounded failure code; do not persist raw provider bodies, tokens or file paths in this cache. Retain two source observations under one identity in this same store: durable `local_saved` from the owned local-Plex path and replaceable `online_cache` from Plex's catalog. They share one parser/schema, not two implementations. Online refreshes never overwrite or delete `local_saved`; merely caching an unowned score does not qualify it for offline display. Round using decimal half-up after multiplying by ten; compare the displayed integer percentage to 60 for icon selection. Cache responses and browser merging carry `owner` and per-record revision so old-root/old-credential and out-of-order responses cannot replace current state.

Resolve ownership in a batch through the existing accepted Movie catalog owner, using `CatalogStore.owned_identity_candidates` (via an injected current-owner accessor), without scanning files, creating/migrating a catalog or decoding full provider documents. Adapt ratings namespace keys to the existing owner’s key format, never invent a parallel ownership index. Browser hints are not authoritative. An unavailable ownership result permits no offline-owned exemption; do not block cards while resolving it. Return no numeric scores when `display_allowed=false`, and clear any previously displayed unowned session values on that permission change. Source and ownership are distinct: a movie being on Plex alone does not make it CP-owned.

- `POST /api/movie-ratings/read`: local snapshot and current ownership/availability projection only, HTTP 200; missing cache is empty, not a reason to create/migrate the catalog. No worker, Plex sync, network lookup or filesystem scan. Expected missing-config, outage or store-unavailable states return HTTP 200 with `display_allowed=false` where needed, not an `error` payload consumed by CP's generic error handling. Valid owned saved scores are allowed without an availability check.
- `POST /api/movie-ratings/resolve`: enqueue only eligible missing/expired visible demands or a coalesced availability validation, HTTP 202 if work is pending, otherwise 200. With no Plex configuration, return the quiet local result and start no provider work. Never wait for completion. Queue full/provider/store trouble returns a quiet per-item unavailable state with `retry_at`, retaining owned saved scores when readable; do not run inline. Malformed client requests may still return 400. An unexpected HTTP/transport failure is caught locally by the ratings client, suppresses unowned scores and produces no global error UI. Responses use `Cache-Control: private, no-store`; shared in-app caching is explicit.

**Availability without blocking.** Connection state is separate from saved scores. Missing URL/token means `not_configured` and zero probes. A configured connection starts `unknown` on each backend/config epoch; a persisted “available” flag cannot authorize an offline startup. Reuse recent successful normal-sync connectivity evidence where available. Only visible unowned demand can schedule a background validation otherwise: one authenticated, bounded local `/library/sections` read, followed by a needed exact-ID online lookup; with all online scores cached, revalidate one demanded cached title to establish online access. Coalesce this across cards/tabs, never one health check per card. Success grants a 5-minute availability lease; source-specific not-found responses confirm reachability without inventing scores. Until confirmed, unowned RT stays hidden and cards remain usable. Local PMS failure forbids the online bypass, even if the metadata host is independently reachable.

On detected connection failure or credential removal, revoke the lease and suppress unowned scores immediately on the next shared response/config event; owned `local_saved` remains. A single lease-expiry timer can invalidate display permission and schedule revalidation only while eligible unowned cards are visible, after poster/idle/interaction gates. No recurring heartbeat with no visible demand, no probes just to display owned saved scores, and no attempt to prove availability during card rendering. Backoff below controls reconnect attempts. Recovery restores unowned scores lazily after a fresh successful validation. Availability cannot detect an outage before observing it; expired/unknown permission defaults to hidden, never blocks CP.

**Score parsing.** Use source-tagged `Rating[]` entries when present. Otherwise use `rating` only with a matching RT critic `ratingImage` and `audienceRating` only with an RT audience `audienceRatingImage`. Accept finite decimal numbers in [0,10], including zero; reject booleans, NaN, infinity, out-of-range and blank/N/A values. An IMDb/TMDB or generic Plex star value is never re-labelled as RT. A non-RT rating entry cannot replace an RT entry. Conflicting duplicate entries for the same RT type are unavailable for that type and produce a bounded diagnostic. Icon source markers are evidence of source/type; the agreed displayed percentage rule owns icon selection.

**Owned movie path.** Preserve the existing `_fetch_plex_library` projection and return contract. Extract its small local HTTP helper into `services/plex_library.py::fetch_plex_json(base_url, token, path, *, params=None, open_url=None, timeout=15)`, reused by existing sync and ratings reads, with header authentication and redacted failures. This is a transport extraction, not another library matching implementation.

At the end of a successful normal Plex movie fetch, offer minimal immutable score facts (Plex GUID, local rating key, any already-present external IDs, values/markers) to the ratings owner's coalesced persistence inbox. Start its lightweight persistence worker if needed so scores can survive a later disconnect even if their cards were never opened. Do not await disk writes, add network requests or add source fields to canonical metadata; keep the old `plex_rating` behavior. Process persistence in bounded chunks outside request/catalog locks. Only successfully committed scores are promised to survive restart; tests must await that commit before simulating shutdown.

Save observations under their exact Plex Movie GUID even when the normal list lacks external IDs. Reuse a cross-ID mapping only when provider evidence or the existing accepted Plex identity confirms it; a filename/path coincidence or a stale `plex_guid` attached to a later TMDB manual correction is insufficient. A movie's saved observation must never migrate to a different accepted identity. This may leave a score unavailable until its mapping can be verified, which is preferable to an incorrect score.

For a **visible owned movie** without a verified saved score/mapping, obtain its existing local `rating_key` from the current catalog/Plex records and issue one background `GET /library/metadata/<rating_key>` through the shared helper. Validate the returned Movie GUID and external IDs against the accepted identity, then save `local_saved`. Do not discover all Plex IDs, scan a library, refresh Plex metadata or run `_auto_sync_plex` to service the card. If there is no existing local rating key or the identity conflicts, quietly leave RT absent. A provider that omits IDs cannot be worked around by title guessing. No new whole-library ratings read is permitted.

Normal successful Plex syncs refresh saved observations by verified GUID. Plex disappearance, credential removal, local membership removal or a failed refresh never delete those observations. CP's current accepted ownership decides whether they remain eligible to display offline. Root change reads only the new root's saved data; credential/server change invalidates connectivity and local rating-key mappings, not verified historical scores stored for this CP Library. Owned saved cache hits require no availability probe or online request. If no saved local score exists and Plex is unavailable, show no RT content; do not fall back to the online host.

**Unowned / uncached online path.** Only when the configured Plex connection is available and the card remains eligible, use `GET https://metadata.provider.plex.tv/library/metadata/matches?guid=tmdb://<id>&type=1`, or the exact IMDb ID when no TMDB ID exists. For accepted Plex-only Movie GUIDs, use the same fixed host's `/library/metadata/<id>` and validate the returned GUID. Header `X-Plex-Token` stays server-side. Exact-ID match responses already contained both scores in the investigation: do not add a second detail request when unnecessary. Never use `/api/plex/match-search`, which is CP's file-matching feature, or add a movie to Plex to obtain ratings. Reuse online cache only while the availability lease permits display; retained data stays hidden during outages.

**Work bounds and failures.** One dedicated worker owns retrieval/persistence, with at most one Plex request in flight and online starts spaced at least 500ms apart. Queue cap: 200 distinct identities; single-flight by canonical key and aliases across browser tabs. Demand entries expire after 15 seconds unless renewed by visible polling; expanded and most recently visible demands precede older ones. Local already-fetched sync updates are coalesced, bounded to 10,000 movie records and committed in chunks of at most 50, yielding between chunks; oversized snapshots use bounded producer chunks, not an additional provider scan. Bound provider response bodies to 1MiB per title and the sections response to 1MiB. Socket timeout 5 seconds. Never hold service locks during HTTP calls.

- Ready observations are refresh-eligible on visible demand after 7 days; missing/partial observations retry after 24 hours when connected. Normal Plex sync also updates local saved observations. A saved owned score has no display expiry and is not deleted because refresh is due. An owned refresh uses only the existing local rating key; absent local RT data does not substitute a generic star value or promote an online result into `local_saved`. Unowned cache age and connection permission are separate checks: freshness never overrides disconnection.
- Publish both score types as one validated source observation, never a critic/audience blend from different movies or responses. Order publications within each source by observation sequence. A delayed response cannot overwrite a newer observation, and online/local slots cannot overwrite each other. Failed/non-RT local refreshes preserve previously saved owned scores; explicit successful source corrections are applied only after identity validation.
- HTTP 429: respect `Retry-After` (seconds or HTTP date), default 15 minutes if absent/invalid, pause online dispatch globally for that credential epoch and suppress unowned RT quietly. Do not cap a valid longer wait downward.
- HTTP 401/403: mark unavailable and pause that provider until credentials/config epoch changes. Hide unowned RT; do not erase owned saved scores.
- Timeouts, invalid JSON and 5xx: retries only on renewed visible demand, at 1 minute, then 5 minutes, then 30 minutes; no tight automatic retry loop. A failed refresh must not overwrite a valid score with null.
- Cache store failure: quietly suppress unavailable RT; keep a still-valid owned session observation, but do not expose an unowned cached value without availability/ownership permission. No canonical database recovery/migration on this path, no error UI.
- Root/credential change: increment epoch, cancel queued work, reject old in-flight completions, reset backoff, notify browser owner change on next read. No network work required to switch roots; old callbacks cannot write into the new root.

**Before/after example.** Currently Plex returns critic `9.5` and audience `7.7`, while CP retains a generic `9.5`. After this change that old field remains untouched, and the separate ratings owner supplies critics `95` and audience `77` to the RT slots. A Discover movie absent from the local library uses the same normalized result from the online match response. Neither source is allowed to overwrite the existing star value or affect sorting.

### No-slowdown acceptance contract

This is an observable requirement, not a claim of mathematically zero CPU cost. Enforce the structural gates first and compare compiled desktop timings. The tolerances below are measurement allowances, not permission to introduce a perceptible delay.

1. Hold every ratings endpoint for 30 seconds: cards, visible posters, expand/collapse, selection and playback/stream action initiation still work. Ratings endpoints are not ancestors of card/list/detail completion in the request dependency graph.
2. Hold a visible poster: no ratings read/resolve/poll starts; other visible/hidden/clipped poster cases obey the existing scheduler contract. Release/error the poster, observe backdrop scheduling, then ratings eligibility.
3. Zero provider requests to display saved owned scores, including with missing credentials and after restart. Fresh cached unowned entries need no per-title lookup while a valid availability lease exists; a coalesced lease validation is counted and disclosed separately. With Plex unconfigured, zero probes and zero online lookups. No offscreen-card/hidden-workspace flood, additional whole-library read or ratings-triggered sync.
4. Record baseline and candidate at 1366×768, 1600×1000 and 1920×1080. All existing card/poster boxes and grid column counts match within 1 CSS pixel for identical fixtures; score arrival causes zero attributable layout shift and no card-box change. Long titles, `100%`, large vote counts and both awards must fit.
5. At 1600×1000, run 20 alternating baseline/candidate pairs for cold browser + cold ratings, warm browser + persistent ratings, 5-second provider delay, and unavailable provider. Measure from the same navigation/user action to first visible card, last visible poster load/error, and next paint after an expand action. Also record long tasks and request counts during 10 seconds of scrolling.
6. Any repeatable ratings-caused slowdown in card/poster display, navigation, typing, scrolling or action response fails acceptance, even if small. Differences above 16ms median or 33ms p95 automatically trigger investigation; these are diagnostic noise thresholds, not permitted regressions. A new ratings-attributed main-thread task over 50ms, observed interaction stall, or structural dependency fails regardless of aggregate timings. Repeat under controlled conditions to distinguish noise; if inconclusive, report inconclusive and investigate rather than claiming “no slowdown”. Never relax the requirement to make tests pass.
7. Backend read/resolve route p95 under 50ms for 40 identities against a 10,000-record cache on the test machine, while provider transport is held and under repeated-tab demand. No full table scan per batch. Existing library search timing and response-shape checks must still pass. Record asynchronous saved-score persistence load separately; it may not stall normal library/card reads. Compare no-Plex baseline and candidate as a separate performance case; an absent optional integration must not add health checks or UI work beyond lightweight eligibility handling.

## Review focus

1. Incorrect Plex matches or stale cross-ID aliases must never attach another movie's scores. Tasks 1/2/4 test ID conflicts and identity changes.
2. A retained hidden workspace, React StrictMode or duplicate movie copies must not multiply requests. Tasks 3/5 test visibility and single-flight behavior.
3. A valid zero, a 59/60 boundary or partial source data must render the correct percentage/icon. Tasks 1/4 test backend normalization through actual UI output.
4. A Plex outage must preserve saved owned scores, suppress cached unowned scores and show no error; credential/root changes and late responses cannot bypass that rule. Tasks 2/3/5 exercise those failures and offline restart.
5. Lazy local metadata reads must not alter identity inputs, turn into a whole-library scan or undo current poster priority. Tasks 2/3/5 compare legacy Plex projections and held-image/interaction request order.

## Implementation sequence

### Task 1 — Normalize and persist one ratings record

**Create:** `services/movie_ratings.py`, `services/movie_ratings_store.py`, `tests/test_movie_ratings.py`, `tests/test_movie_ratings_store.py`, `tests/fixtures/movie_ratings/plex_local.json`, `tests/fixtures/movie_ratings/plex_catalog.json`.

**Interfaces:** Produce `normalize_plex_ratings`, strict identity key/alias validation and `MovieRatingsStore` methods specified above. Fixtures contain only minimal synthetic/sanitized movie metadata, never credentials or filesystem paths.

- [ ] Add failing tests `test_rt_sources_and_two_types_stay_separate`, `test_zero_and_59_60_100_boundaries`, `test_invalid_scores_and_conflicting_duplicates`, `test_exact_id_confirmation_required`, `test_cache_survives_restart_without_catalog`, `test_online_observation_cannot_overwrite_owned_local_saved`, `test_config_removal_does_not_delete_owned_saved_scores`, `test_alias_conflict_does_not_merge_movies`, `test_locked_or_missing_cache_is_optional`. Assert raw Plex 5.9/6.0 produces 59/60 and explicit null never becomes zero. Persistence alone does not authorize offline display without current ownership.
- [ ] Run `.venv\Scripts\python.exe -m unittest tests.test_movie_ratings tests.test_movie_ratings_store`; confirm failures are for missing behavior.
- [ ] Implement normalization and schema-v1 store, indexed aliases, epoch-checked atomic publication and no-write reads; do not create a second canonical metadata store.
- [ ] Rerun the same command; all tests must pass before proceeding.

### Task 2 — Retrieve owned and unowned ratings without blocking callers

**Create:** `services/plex_library.py`, `services/movie_ratings_routes.py`, `tests/test_movie_ratings_api.py`. **Modify:** `services/movie_ratings.py`, `app.py`, `tests/test_plex_manual_match.py`, `tests/test_sql_migration_parity.py`.

**Interfaces:** Consume Task 1 store/normalizer. Produce `MovieRatingsService` public methods and the read/resolve endpoints exactly as specified. The transport helper remains injectable; existing Plex tests patch that helper after extraction rather than weakening their assertions.

- [ ] Add failing API/worker tests: `test_read_and_resolve_return_while_provider_is_held`, `test_owned_saved_scores_display_offline_without_probe`, `test_visible_owned_metadata_fetch_is_targeted_and_identity_checked`, `test_unowned_exact_tmdb_match_returns_both_scores`, `test_normal_sync_saves_scores_without_card_visit_or_extra_network`, `test_normal_sync_projection_unchanged`, `test_duplicate_demand_is_single_flight`, `test_queue_and_retry_limits`, `test_local_unavailable_does_not_bypass_to_online`, `test_unconfigured_returns_quiet_200_and_zero_provider_calls`, `test_cached_unowned_scores_suppressed_after_disconnect_and_restart`, `test_removed_ownership_revokes_offline_exception`, `test_availability_validation_is_coalesced_and_lazy`, `test_root_switch_discards_old_completion`, `test_credentials_never_enter_payload_or_error`, `test_local_snapshot_does_not_change_identity_or_catalog_generation`.
- [ ] Run `.venv\Scripts\python.exe -m unittest tests.test_movie_ratings_api tests.test_plex_manual_match tests.test_sql_migration_parity`; confirm the new behavior fails first and record unrelated baseline failures separately.
- [ ] Extract the existing local transport, add asynchronous persistence of normal-sync score facts and targeted visible-owned metadata reads; preserve the exact existing legacy sync result on identical payloads. Wire bounded service lifecycle, current ownership resolution, availability permissions and both routes. Do not add `includeGuids=1` to canonical sync or introduce a new whole-library ratings query.
- [ ] Verify both sources publish the same schema, a missing local ID cannot produce a filename/title match, queue full and provider failure return promptly, config changes isolate old workers, and no existing list/detail endpoint calls the ratings owner.
- [ ] Rerun Task 1/2 suites plus `tests.test_metadata_authority`, `tests.test_canonical_catalog`, `tests.test_library_search_performance`, and `tests.test_plex_match_service`.

### Task 3 — Share deferred ratings loading across cards

**Create:** `src/api/movieRatings.js`, `src/components/MovieRatingsContext.jsx`, `tests/movie_ratings.test.mjs`. **Modify:** `src/App.jsx`, `src/components/movie-card/cardArtwork.js`, `tests/e2e/card-artwork-performance.spec.js`.

**Interfaces:** `createMovieRatingsCache({read, resolve, clock, schedule})` exposes `subscribe(key, listener)`, `getSnapshot(key)`, `register(element, identity, {expanded}) -> cleanup`, and `dispose()`. `useMovieRatings(identity, cardRef, {expanded})` returns the immutable per-key snapshot; it consumes the one provider and the existing poster-priority owner.

- [ ] Add failing Node tests for batching at 40, one HTTP flight, per-key notifications, cache eviction, owner/revision changes, polling cap, visibility cancellation, duplicate identities and StrictMode acquire/release. Include availability expiry/disconnect suppressing unowned session values, saved-owned survival, silent ratings transport failure, no probes when unconfigured, and no heartbeat without visible unowned demand. Add held-image and active-input tests proving ratings dispatch follows poster/backdrop scheduling and idle interaction gates, including hidden workspaces and clipped rails.
- [ ] Run `node --test tests/movie_ratings.test.mjs`; run the compiled artwork suite with the isolated runner once its frontend fixture exists. Confirm missing scheduling behavior fails.
- [ ] Extend the existing readiness owner; implement one observer/cache/provider and deferred endpoint requests. Bind new root provider within the existing artwork provider. Keep existing movie details fetching and awards cache independent.
- [ ] Rerun Node tests and existing compiled artwork tests; Movie and TV request ordering, immediate expanded artwork and fallback images must remain correct.

### Task 4 — Render both scores and all four icons in the shared card

**Create:** `src/components/movie-card/MovieRatings.jsx`, `src/components/movie-card/RottenTomatoesIcons.jsx`, `tests/test_movie_ratings_ui.py`, `tests/e2e/movie-ratings.spec.js`.

**Modify:** `MovieCard.jsx`, `movieCard.css`, `SharedMovieCards.jsx`, `features/discover/DiscoverWorkspace.jsx`, `features/home/HomeWorkspace.jsx`, `features/iptv/IPTVCards.jsx`; use paths under `src/` as mapped above. Modify shared awards layout styling only if needed to preserve awards placement, and verify its other consumers.

**Interfaces:** `UnifiedMovieCard` accepts optional `ratingsIdentity`; its shared ratings row consumes Task 3. `MovieRatings({snapshot, expanded})` owns labels/states; `RottenTomatoesIcon({kind})` accepts `fresh`, `rotten`, `upright`, `spilled`. Threshold selection is a pure tested presentation function, not duplicated in wrappers.

- [ ] Write failing tests for all score/icon boundaries, partial and missing scores, saved-owned tooltips, invisible optional-Plex states, exact dimensions, keyboard focus and no accidental card toggle. Assert no banner/toast/modal/card error or dangling focus target on any Plex failure. Include RT scores on a movie without a star rating and TV with a colliding numeric TMDB ID remaining unchanged.
- [ ] Write wrapper cases for owned Library, unowned Discover, indexer results, Movie Lists (both card types), Home expanded details, AI results and matched IPTV; rejected/unmatched IPTV supplies no identity. Corrected canonical identities must replace old subscriptions and never briefly show the former movie's result.
- [ ] Run the new UI/unit cases and compiled `movie-ratings.spec.js` to confirm failures before rendering changes.
- [ ] Implement the single shared presentation and four local SVGs; pass accepted identities/ownership context from wrappers and apply the central `display_allowed` decision. Preserve all existing star ratings, vote counts, awards, card sizes, interaction and navigation behavior. Do not copy the owned/unowned policy into workspace-specific renderers.
- [ ] Rerun new tests, `tests.test_unified_movie_card_ui`, `tests.test_movie_awards_api`, and compiled Movie awards/relationships/TV parity tests. Capture before/after screenshots and exact box comparisons at the three desktop widths.

### Task 5 — Verify the complete path and performance; document the result

**Create:** `tests/movie_ratings_server.py`, `tests/e2e/movie-ratings-performance.spec.js`, `docs/verification/plex-rotten-tomatoes-ratings/report.md` during approved implementation. **Modify:** `tools/run_playwright_e2e.ps1` with an isolated `-MovieRatingsOffline` fixture option; keep existing modes/defaults. Update the existing Movie details Atlas, Second Brain and log after verified implementation, clearly separating candidate and live status.

**Interfaces:** The fixture requires `CP_TEST_MODE=1` and temp `CP_TEST_ROOT`, uses the real new endpoints/store/worker, injects a deterministic Plex transport, and seeds both owned and unowned examples. In browser end-to-end tests, do not intercept the ratings API being verified. Fixture-only controls may hold/fail provider responses and inspect call counts; none ship in production app routes.

- [ ] Record baseline suites and preserve a source-and-bundle baseline including current dirty work, using an isolated suitable checkout/artifact and temporary build output. Do not overwrite production `dist` to obtain a baseline.
- [ ] Add full-path cases from raw Plex payload through service/store/API to percentage, tooltip and SVG. Include source collisions, local/online failure, two browser pages, root change, identity correction and restart persistence.
- [ ] Run the complete matrix and 20-pair timing experiments, including never-configured Plex and disconnected Plex with persisted owned/unowned scores. Validate task counts, query plans, cache latency, normal-sync persistence load and held-provider response timing. Assert no whole-library ratings requests. A failing geometry or performance gate blocks completion.
- [ ] Run the broader suites and compiled desktop checks below. Investigate new failures; distinguish established baseline failures. Do not call a focused pass a full green suite.
- [ ] Self-review each contract row against actual output, record exact results/limitations and update the guides. Deliver candidate evidence for Dante's review. Do not restart or activate production as part of this task.

## Acceptance matrix

| Scenario / starting state | Action | Exact expected result | Owner / automated evidence |
| --- | --- | --- | --- |
| Owned movie, local Plex RT scores available | Normal sync then visible card | Both percentages from local data, zero online calls; old canonical payload unchanged | Sync/API tests + real fixture/UI |
| Owned movie, normal list lacks external IDs | View the card | Reuse verified saved GUID mapping or target its existing local metadata key; no whole-library scan, no guessed ID | API fixture + legacy projection regression |
| Unowned movie with exact TMDB identity | Open Discover/full card | Single exact-ID match; correct two scores; no Plex library/write operation | Full-path fixture |
| Same movie in Library, Lists and Discover | Navigate and revisit | One shared result; duplicate online demand coalesced | Node + two-page browser case |
| Critics/audience: 0, 59, 60, 100 | Render responses | Correct percent and negative/positive icon at the exact boundary | Unit + full API-to-SVG browser |
| IMDb/TMDB ratings only; missing one RT type | Resolve | Other-source values never shown as RT; dash only for missing type | Normalizer + browser |
| Wrong ID, duplicate conflicting matches, TV response | Resolve | No incorrect score or identity write | Service + API + display |
| Existing manually corrected owned identity | Late prior response arrives | Current identity retained; no former score shown | Browser identity switch + authority tests |
| Cold disk cache / session cache hit | Render cards | Cards first; deferred local batch for disk, synchronous session score reuse | Timing/request-order checks |
| Ratings API held 30 seconds | Browse, expand, select, initiate play | Cards/posters/actions operate before ratings completion | Performance/browser |
| Visible poster held/error/missing; clipped rail | Browse or scroll | Existing poster priority preserved; ratings only after eligibility | Existing artwork suite extended |
| Hidden workspace, rapid scroll, StrictMode | Mount/unmount/switch | No hidden requests or per-card timers; bounded active queue | Node + browser |
| Owned local scores committed; Plex disconnected; restart CP | Open Library and Discover copy | Saved scores show on both because CP owns the movie; zero provider probes; no error | Store/service + real fixture/UI restart |
| Unowned online cache present; Plex disconnected; restart CP | Open/revisit card | No RT score/icon/error, no cached-score flash; ordinary card immediate | API-to-UI + browser-session tests |
| Expired owned score and Plex timeout/429/401 | View movie | Saved owned score stays; unowned scores suppressed; bounded demand retries; no error UI | Fake-clock worker + browser |
| No Plex config, never saved a score | View movie | No RT content, zero provider work, no connection prompt; ordinary CP behavior intact | API + browser |
| Locked ratings DB / unexpected ratings HTTP failure | View movie | Quiet suppression except still-valid owned session data; no app error | API + browser |
| Local PMS unavailable, online metadata works | View unowned identity | No RT; no online bypass and no sync triggered from route | Worker/API |
| Movie removed from CP Library, cached local score remains | View it in Discover while disconnected | Offline-owned exemption revoked; no RT displayed | Current ownership + API-to-UI |
| Normal Plex sync succeeds before any card visit | Save, disconnect and restart | Committed verified local scores survive; no added provider fetch in sync | Persistence + offline fixture |
| Plex recovers after outage | Visible idle card requests again after backoff | Unowned scores appear lazily; no card reload/wait; no polling when hidden | Worker + browser |
| Active scroll/input or new visible posters | Queued ratings ready to publish/fetch | Defer RT work; cards/actions stay responsive; no forced timeout bypass | Interaction + timing tests |
| Change data root or token with work in flight | Complete former request | Old callback cannot write/update current owner; cached valid data not destroyed | Service + Node |
| Long titles, both awards, large vote counts, 100% | Load at all desktop widths | No lost text/control, no baseline card-box growth, no arrival shift | Measured geometry + screenshots |
| TV / compact Home / related tiles | Navigate affected app | Existing display unchanged, no unintended Movie ratings requests | Compiled regression suites |

## Verification and rollout

**Baseline and environments:** Before implementation, record focused regression status in an isolated temporary data root and baseline compiled bundle. Never import the live app in a test process without `CP_TEST_MODE=1`, `CP_TEST_ROOT` set to a new OS-temp path, and network transports patched. Use `.venv\Scripts\python.exe`; use the established isolated Playwright runner. Record retained evidence paths. No arbitrary clean-checkout comparison substitutes for the actual dirty baseline.

**Focused Python:** In the isolated environment:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_movie_ratings tests.test_movie_ratings_store tests.test_movie_ratings_api tests.test_movie_ratings_ui
.venv\Scripts\python.exe -m unittest tests.test_plex_manual_match tests.test_plex_match_service tests.test_sql_migration_parity tests.test_metadata_authority tests.test_canonical_catalog tests.test_library_search_performance tests.test_unified_movie_card_ui tests.test_movie_awards_api
node --test tests/movie_ratings.test.mjs tests/movieDetails.test.mjs tests/browser_ownership_cache.test.mjs
```

**Broader Python:** With the same isolation and provider mocks, run `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`. Record baseline/new failures, exact counts and skipped tests; any new relevant failure blocks delivery. Do not weaken identity, ownership, publication or performance tests.

**Compiled desktop:** New fixture invocation after Task 5:

```powershell
npm.cmd run test:e2e -- -MovieRatingsOffline movie-ratings.spec.js movie-ratings-performance.spec.js
npm.cmd run test:e2e -- card-artwork-performance.spec.js movie-awards.spec.js movie-relationships.spec.js continue-watching.spec.js lists-layout.spec.js iptv-people.spec.js iptv-discover-availability.spec.js
```

Use the existing TV fixture mode (`CP_TV_E2E=1`, then unset) for `tv-expanded-parity.spec.js` and `tv-visible-load.spec.js`, with the existing `CP_TV_E2E_ARTWORK` fixture convention where those suites require it. Use the existing isolated Discover paging mode for `discover-paging.spec.js`/`upcoming-movies.spec.js`. The runner builds to OS temp; a source-only UI check is insufficient. Benchmark baseline and candidate with identical fixture API responses, titles, image resources, browser settings and machine load. Report real-image timing separately from deterministic provider-held tests.

**Live work, only if later approved:** Reconfirm process/PID, effective config/data roots and currently served assets. Back up the touched source and current frontend index/assets and preserve the optional ratings database using SQLite's backup API if it exists. Install only the tested source/bundle, restart only with authorization, and verify the actual served hashes and desktop cards. Sample an owned movie and the three previously verified unowned identities; scores may legitimately have changed. Check all four icon states using safe isolated fixtures rather than falsifying live scores. No Plex metadata refresh or library mutation is required.

**Rollback:** Restore previous source/bundle and restart if authorized. The optional ratings DB can remain unused; no rollback migration of Movie/TV/IPTV catalog data should be necessary. Never delete unrelated user data or undo existing dirty work. Roll back on wrong identity/score source, lost controls, increased card dimensions, poster-priority regression or failed performance gates.

**Reporting:** Clearly distinguish plan, source implementation, isolated tests, compiled desktop evidence and live verification. Include timing distributions, request counts, screenshot/geometry evidence, unresolved coverage and rate-limit uncertainties. Compare every contract above with the implemented behavior; explicitly report differences even if tests pass.

## External references and evidence limits

- [Plex developer forum: exact IMDb/TMDB metadata lookup](https://forums.plex.tv/t/android-universal-linking-watch-plex-tv-links/932340) describes the tested online match endpoint and token header. This is not a published unlimited-use or uptime commitment.
- [Plex Media Server API](https://developer.plex.tv/pms/) documents metadata objects, source-specific rating markers, authentication and pagination. The online provider is a distinct service; do not infer all its guarantees from local PMS documentation.
- [Rotten Tomatoes score icon guidance](https://www.rottentomatoes.com/help_desk/licensing) describes positive/negative icon states and special certification. This plan uses four CP vector depictions; acquiring/reusing official brand assets or distributing a product with them requires checking applicable asset terms rather than assuming the Plex token grants that permission.

## Plan self-review (recorded before implementation)

- [x] Every requested behavior has a task and an acceptance case, including both ownership paths, four icons, missing/zero scores and performance.
- [x] One normalized ratings owner, one persistent cache and one shared renderer; current canonical identity and generic star-rating behavior are preserved.
- [x] Optional Plex has no user-facing error path: owned locally saved scores survive offline; unowned cached values cannot bypass connectivity permission.
- [x] Local external-ID lookup is limited to visible owned demand and separated from matching input; the earlier whole-library ratings index and offline online-provider bypass have been removed.
- [x] Interfaces, states, keys, generations and scheduling rules agree across tasks.
- [x] Desktop layout failure and measurable slowdown block completion; neither can be hidden by passing unit tests.
- [x] No implementation or live activation is represented as approved or completed.

## Execution status — 2026-11-14

Implementation is in managed worktree `codex/plex-rt-ratings`, based on `117526b` plus the preserved dirty desktop source. No commit, production build replacement, runtime restart, live catalog refresh or activation occurred. See the [current verification record](../verification/plex-rotten-tomatoes-2026-11-14/report.md) for actual test names, commands and completed gates; the task checklists above preserve the original planned sequence.

Backend persistence/normalization, optional routes, worker, shared deferred client and all opted-in card wrappers are implemented. The transport helper is named `services/plex_transport.py::plex_json`; the existing poster owner exposes the readiness subscription/predicate directly, avoiding an unused second deferral API. Public timestamps use UTC epoch seconds. These are implementation details, not product-contract changes.

**Historical UI gate, subsequently resolved:** The original below-star expanded placement increased height at1366/1600px. Implementation of that placement was paused, and Dante approved the metadata-row amendment below. Later crowded-content checks found a separate collapsed-row wrap, resolved through his second explicit amendment. Neither card-size assertions nor original text/icon/control sizes were weakened.

## Approved placement amendment — 2026-11-14

Dante explicitly selected **Use metadata row (recommended)** in response to the expanded-placement contract notice. For expanded full Movie cards, place the labelled RT pair at the right of the existing metadata/chip row immediately before its language/actions control. Keep the existing star/votes and awards in the header. This supersedes the below-star expanded placement; collapsed placement and every optional-Plex/performance/geometry contract remain. Implement the measured shared-component change, remove the obsolete header wrapper/style, and finish geometry, crowded-content and performance qualification. Live activation is still not approved.

### Follow-up qualification

The approved expanded placement passed the simple geometry comparison at all three desktop sizes. Adding crowded metadata then exposed a collapsed-layout failure: the RT pair made awards wrap, increasing the1920px case by29px (1366px also failed). The original card-size rule remained authoritative. A second contract notice proposed a collapsed poster strip; Dante approved it below.

Final backend review also corrected partial/missing refresh to the specified24hours. An empty refresh retains the previous saved score pair and retrieval time, while a separate persisted refresh deadline prevents repeated provider work, including after restart. Two regressions failed before the fix; the combined parser/store/API/app suite now passes49tests. True HTTP-cache performance fixtures distinguish cold,warm,actively delayed,unconfigured,configured outage and disconnected saved ownership states; final evidence is tracked in the verification report.

### Approved collapsed placement amendment — 2026-11-14

Dante explicitly selected **Use poster strip (recommended)** for collapsed full Movie cards. Place the existing fixed-size RT pair in a152px dark strip9px from the poster's left and54px above its bottom, clearing existing controls. The background appears only when scores are allowed; absent RT leaves no visible empty strip. Restore the original collapsed star/awards row, including its absence when both are missing. Expanded RT remains in the previously approved metadata-row location. All card/poster dimensions, original text/control sizes, optional-provider behavior and performance requirements remain authoritative. Live activation remains unapproved.

### Latest placement instruction — 2026-11-14 (supersedes both amendments above)

Dante rejected the previewed poster strip and metadata-row placement. He explicitly instructed collapsed RT to share the bottom TMDB rating row, and expanded RT to sit between TMDB and awards in the header. Expanded long movie names must wrap before reaching that group. Implement through MovieCard and its shared MovieRatings owner; remove the superseded placement rules. Preserve all existing values, icons and text sizes. Check narrow desktop cards with both awards and 100% scores, title wrapping, score-arrival stability, and the existing lazy-loading regressions. This authorizes the isolated layout revision and updated screenshots; it does not authorize activation in the main folder.

The latest preview preserves existing text/icon sizes but does not satisfy the earlier exact collapsed-height rule in crowded narrow cards: existing awards wrapping adds up to29px; introducing the RT row where star/awards were absent can add about4px. No geometry assertions were weakened. The collapsed-height exception is pending Dante's explicit decision; main-folder activation remains blocked independently. Expanded title wrapping is explicitly approved by the latest instruction.

### Previous implementation qualification (before latest layout revision)

Both approved placements are implemented. Expanded cells use53px each plus the unchanged12px gap (118px total); icons18px and score text13px remain unchanged. This removes unused space and fits the fractional848.67px metadata row in the crowded1366px case. All9 geometry comparisons pass: normal,crowded and no-star/no-award cards at3desktop sizes. All24ratings browser tests and13artwork tests pass. JavaScript44pass; Python160of162pass, with only the same2baseline source-text failures. All50ratings-specific backend/app tests pass within that run.

Observer and cache-subscription registration now wait behind the same poster/idle gate as requests. A pending subscription returns no cached value until it can receive invalidation notifications. Browser idle callbacks have no forced timer bypass; the250ms fallback exists only without that browser API. Held-poster,cached-duplicate/disconnection and held-idle regression cases pass. Final timing evidence and limits are maintained in the report.

Final performance qualification is complete: controlled loading comparisons, corrected delayed-provider setup, fixed-window score-publication observation and sustained scrolling are recorded in the report. No repeatable card/poster loading regression was established after balancing the delayed fixture. Final scrolling produced no RT requests, score changes or long tasks; both versions had p95 frame intervals of16.7–16.8ms. This is isolated evidence, not a promise of literally zero CPU cost or live performance. All approved implementation work is complete; live activation remains separate.


### Approved compact count amendment — 2026-11-14

Dante instructed removing the word "votes" from collapsed Movie cards to make room. Keep the compact numeric count, existing font/icon sizes, expanded labels, and TV presentation. Extend the existing formatVoteCount owner with an optional label choice and use the existing expanded state in Movie callers. Recheck the bottom row at1366/1600/1920px with100% scores and both awards; preserve lazy-loading checks and refresh screenshots. This supersedes proposing extra height as the first solution; it does not approve main activation.


### Approved activation and narrow height exception — 2026-11-14

Dante explicitly accepted up to4px extra height for crowded collapsed cards lacking both TMDB rating and awards, then approved applying the feature to the main CP folder. He immediately clarified: "apply it to the folder , dont test i will". Apply only the feature changes, preserve current main edits, retain a rollback backup and build the main frontend. Do not run tests, probe live behavior or restart CP; Dante will handle testing/restart. Exact geometry remains authoritative outside this specific collapsed exception and the already-approved expanded title wrapping. Record application/build status separately from tests and runtime activation.
