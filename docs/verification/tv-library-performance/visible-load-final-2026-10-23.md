# TV first-load continuation — 2026-10-23

Discover improved materially in the isolated first-selection measurements. Library card data improved, but repeated measurements do **not** demonstrate a substantial improvement in its complete visible artwork. Do not describe both pages as instant or the normal launched app as verified.

## Measured outcome

Fresh Chromium process/profile per sample, desktop 1365×900, visible document lifecycle, first TV selection after opening the Movie shell. The diagnostic server uses canonical TV routes, serializers and current read owners against actual TV/acquisition facts through SQLite `mode=ro` and `query_only=ON`. Real provider GETs and real CDN artwork are used. Baseline is the source preserved at the start of this continuation, including the earlier TV improvements; it is not an old release.

| First-selection stage, median | Baseline | Candidate | Samples per version |
| --- | ---: | ---: | ---: |
| Library cards in committed DOM | 408ms | 348.5ms | 5 |
| Library complete visible metadata, posters and backgrounds | 1517.9ms | 1431ms | 5 |
| Library server processing | 356.4ms | 297.8ms | 5 |
| Discover cards in committed DOM | 923.2ms | 598.9ms | 2 |
| Discover complete visible metadata, posters and backgrounds | 3039.5ms | 1388.4ms | 2 |
| Discover server processing | 883.8ms | 536ms | 2 |

Library showed the same 33 cards and six visible cards. Discover showed 40 cards and four visible cards. Median poster requests after the click fell from 24 to six in Library and from 24 to five in Discover. Backgrounds retain the same URLs and quality. All pending Discover identities still receive full enrichment; splitting the visible group changes two local HTTP batches to three in this case without increasing simultaneous batch capacity or remote detail identities.

The first Library pair was 4.03s versus 1.19s. Reversing order and collecting five samples exposed substantial network variation: baseline complete-artwork range 1.45–4.03s, candidate 1.19–1.87s. Use the medians, not the most flattering pair. The Library median artwork reduction is about 6%, and these samples do not establish statistical significance. Its card-DOM reduction is about 15%. Discover's two samples per version show about 54% lower complete-viewport time; this is a small observational sample, not a guaranteed speedup on every connection.

Resource evidence shows the remaining Library wait includes remote artwork: in `repeat-candidate-library`, six posters and six backgrounds finish after the card data, with the first two recorded w1280 background requests taking about 897/899ms. These are real resource timings, not server-query timings. No image resolution, asset URL or visible card detail was reduced to obtain the result.

## Changes and authoritative owners

- `TVWorkspace`, `TVSearchControls`, `TVLibraryImport` and `TVBulkActionBar`: allow the initial Library catalog to settle before starting auxiliary choices, review count and list names. Opening controls releases that work immediately even if the catalog is stalled. Initial failure also releases it, and Retry remains usable. Bulk actions fetch list descriptors without unrelated watchlist contents.
- `TVWorkspace` and `tvCardEnrichment.js`: prioritize cards actually intersecting the desktop viewport, with a first-row fallback for hidden/unmeasurable grids. Every pending identity is attempted once, batches stay at most 20, capacity stays at the prior `ceil(pending/20)`, independent failures do not stop the queue, and abort suppresses queued requests and late merges. Existing full metadata merge and local ownership/progress/watchlist preservation remain authoritative.
- `TVSearch.discover`: overlap local snapshot/projection preparation with independent provider work using one request-scoped worker. No SQLite connection crosses threads. Preserve local validation/projection error precedence, provider limits, filtering/scan continuation, complete output and request-context release. The context does not enter the retained scan state or a new cross-request cache.
- Shared `cardArtwork.js` and `UnifiedMoviePoster`: use the existing artwork observer and replacement/cleanup owner for poster activation too. Native lazy loading had fetched multiple screens ahead. Expanded cards, data/blob URLs and browsers without IntersectionObserver retain eager fallback. Already activated images remain loaded; distant images activate on scroll. URLs, error fallback, image fitting, overlays and geometry remain unchanged. No Home/Movie/IPTV business logic or layout was modified.

The reusable rule is to make the visible result independent of unrelated auxiliary and offscreen work, while retaining one visibility owner, complete page enrichment and fresh request-local facts.

## Final verification

- **59 desktop tests passed**, one worker, no retries/skips, against the final compiled candidate. Covers TV parity, expansion/playback, controls and alignment, retained navigation, first-selection scheduling and shared artwork. Screenshot inspection confirmed populated Library and Discover desktop viewports.
- **One separate existing IPTV Movies smoke passed**, with providers seeded only in its temp fixture. Provider/list/group/unmatched/metadata controls remained usable.
- **96 Python tests passed** across TV read-performance, stabilization, coverage, catalog, list filters and unified-card contracts.
- **Six Node tests passed** across enrichment scheduling and existing TV search/stream targeting.
- Four fresh-process Discover memory observations passed existing peak/residual bounds, complete output hashes and request-context collection. Candidate peak adds about 9KiB over the current baseline for the worker/future; this is bounded Python allocation evidence, not a claim of lower RSS. Six-series baseline/candidate peaks 289991/299073 bytes, residuals 11762/12786. Twenty-four-series peaks 1043914/1052748, residuals 13074/13202. No late imports were measured.
- Actual-data fixed-provider comparison of 40 owned cards produced identical complete-output SHA256 `987e5f4ebb67a0a3114d63e61d31dd632d6c44b808bd789be34737c77b372eb3`. Both versions used one connection, 13 SELECTs and one physical check per distinct path (1193 paths). Earlier iteration query-count reductions are not attributed to this continuation.

An exploratory broader Python run remains **failed** on `test_home_scrolling_rails_share_layout_and_group_trailers`: it expects a literal upcoming request with `page_size=100`; current pre-existing Home source uses `HOME_UPCOMING_PREVIEW_SIZE=20`. App.jsx and that Home helper were not changed here and predate this turn. Do not call the whole repository suite green. The final 96-test selection does not include that stale source-text assertion.

Test corrections preserve user-visible assertions: the old Discover exact `[19,20]` batch partition was replaced by checks of all 39 rendered results, exact identity coverage, bounded batch size/capacity and completion with background held. Existing Home artwork tests incorrectly asserted CSS backgrounds despite current Home deliberately using `background:none`; they now exercise its actual posters, including hidden replacement and observer reuse. No Home production change was made to satisfy those tests.

## Probe integrity and retained failures

The initial hidden-IAB `requestAnimationFrame` viewport sampling was throttled and is diagnostic only. Final captures use MutationObserver/microtask samples plus resource completion and record visible lifecycle. Results measure committed DOM/layout, not physical screen-paint time. Final full-artwork readiness requires every visible poster to have natural dimensions and every visible background resource to finish. Provider/CDN and OS filesystem caches were not flushed. The normal app's startup workers were excluded and Movie shell results are empty fixtures, so these runs establish neither Movie/TV speed parity nor real normal-launch performance. Action-blocking diagnostic toasts in screenshots are expected: startup mutation requests are refused, not executed.

All failed phases are retained. These include useful RED regressions, the old exact-batch assertion, stale Home artwork assumptions, a `.cmd` regex pipe interpretation (fixed by invoking Node directly), legacy PowerShell lacking Get-FileHash (fixed with .NET SHA256), and missing IPTV fixture seeding/module setup. A mistaken additional IPTV control-opening step was reverted; the existing smoke then passed. No failed run was overwritten or counted as passing.

## Cost, evidence and activation

Evidence root: `C:\Users\dante\AppData\Local\Temp\cp-tv-visible-load-af71d22f-388b-4b6a-861e-590500b9af75`. `comparison-final.json` enumerates every final/repeated capture, medians and case root. Each case includes source/build identity, browser events, server logs and a full-viewport screenshot. `budget.json`, individual phase logs and `final-source-hashes.json` retain verification provenance. The final compiled candidate is `b1c938db-ae2c-4280-83b0-5f8d356ba7f7/dist`; `desktop-shared-final` reused that unchanged build.

Checks/captures used **695.612 of 900 active command seconds**, with approximately **285.2MB** retained before this report. This is command execution cost, not total investigation wall time. One early overlapping RED caused a ledger last-write collision; it is conservatively charged 1.6s and explicitly recorded. Final suites and captures were sequential. Earlier task ledgers were not reset. No stress benchmark or filesystem-cache flush was run.

Changes are **source plus isolated verification**. The normal app was closed at the turn's start; it was not launched/restarted. No production catalog, configuration or media mutation was performed. Read-only SQLite access may still coordinate ordinary WAL/SHM files; this is not a claim of zero filesystem activity. Owned test servers were stopped; final listener inspection found none on 5000, 5127 or 5130–5135. Unrelated dirty work remains preserved, and nothing was committed/pushed.

Production dist remains the earlier `index-DsShgokM.js`/`index-BDcZM567.css`. A normal future `run.bat` build/start activates this source. Current evidence supports a strong Discover improvement, earlier Library card data and fewer competing downloads; it does not support declaring the remaining Library artwork wait eliminated.
