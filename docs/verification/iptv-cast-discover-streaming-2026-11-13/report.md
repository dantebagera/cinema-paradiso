# IPTV cast, Discover badges, and Movie streaming choice

Date: 2026-11-13. Status: implemented and verified in isolation; not activated.

## Delivered behavior and ownership

Dante explicitly approved every choice in the [plan](../../plans/2026-11-13-iptv-cast-discover-streaming.md) before implementation. IPTV credits now reuse CP's `PersonCreditCard`, biography modal and horizontal rail. Actor-card navigation retains compatible refinements; Filmography clears them within the current provider. Back restores context, Reset filters keeps the person, and explicitly choosing Provider View exits person scope.

Movie Discover renders independently of the saved-catalog lookup. A fixed 30px badge row shows up to two provider names and overflow. No online availability check, sync, enrichment, database merge, new persistent index or catalog migration was added. Only accepted, available Film sources establish a positive badge. Unknown catalog state is distinct from a successful negative result.

Every shared Movie Stream caller opens the player dialog synchronously and waits for the user's service choice, including one-source cases. StreamIMDB, VSEmbed, the saved custom template, and configured IPTV appear through their existing owners. Saved web preference sets order, not autoplay. Web availability remains unknown; missing required identity disables that source. IPTV selection re-resolves the accepted identity and exact version locally. The workspace and chooser share one session coordinator and source-version component. TV episodes retain direct saved-provider streaming and exact episode targeting. Provider history remains separate from owned Movie/TV progress.

## Baseline and environment

- Desktop source: `C:/Users/dante/Desktop/cinema paradiso`, master at `117526b`, with substantial existing dirty work. Snapshot preserved those changes, including ignored `src/features/library/librarySearchRequests.js` required by the current build.
- Candidate: `C:/Users/dante/.codex/worktrees/iptv-discover-streaming/cinema paradiso`, detached baseline `117526b` plus the captured dirty source and this implementation. The native worktree was delayed; a temporary isolated snapshot was used and then transferred when it completed.
- Review used the captured file baseline, not a Git diff against the older clean commit. No commits, pushes, releases, desktop-source overwrite or app restart.
- Python 3.12, Node 24.15.0, Vite 6.4.3, Chromium through the existing Playwright runner. Python uses `CP_TEST_MODE=1` and a new temporary `CP_TEST_ROOT`. The compiled UI runner seeds disposable local data, serves port 5117 and emits bundles into a temporary `CP_TEST_DIST_DIR`.
- Shared dependency directories are junctions to the desktop checkout; no dependency installation or deletion.
- Read-only final comparison found no drift in reviewed desktop implementation owners from the captured baseline. The running app still served `index-9d_Ds88k.js` and `index-BqgPLqsb.css`, not the candidate.

## Results

| Gate | Result | Evidence |
| --- | --- | --- |
| Broad IPTV/backend suite | 154 passed, 495.828s | [Log](logs/broader-python-final.log) |
| Final adverse/config/UI-owner checks, including added cases | 37 passed | [Log](logs/adverse-final.log) |
| All Node tests, explicit file list | 155 passed, zero failures/skips | [Log](logs/node-final.log) |
| Discover paging, Movie relationships, artwork and scroll restoration | 59 passed | [Log](logs/discover-regressions.log) |
| Native TV, streaming providers/loading and TV expanded parity | 22 passed | [Log](logs/tv-native-final.log) |
| New compiled features including delayed availability, reset, missing ID and density | 9 passed | [Log](logs/acceptance-final.log) |
| Final combined compiled run after the last source edit | 31 passed, 44.5s | [Log](logs/compiled-final.log) |
| Desktop visual inspection | Cast, badge and chooser screenshots inspected; measured portrait 106x132 CSS px and badge row 30px | Images below |

Counts from overlapping reruns are not summed as unique tests. These are the specified suites, not a claim that all repository Python discovery passed.

Broad command:

```powershell
python -m unittest tests.test_iptv_service tests.test_iptv_movie_gates_0_5 tests.test_iptv_movie_enrichment tests.test_iptv_chatgpt_bulk tests.test_iptv_movie_ui tests.test_iptv_ui tests.test_iptv_routes tests.test_iptv_provider_manager tests.test_streaming_config_api tests.test_iptv_movie_availability tests.test_iptv_people
```

Additional final command:

```powershell
python -m unittest tests.test_iptv_movie_availability tests.test_iptv_people tests.test_streaming_config_api tests.test_iptv_ui
$nodeTests = @(Get-ChildItem tests -Filter *.test.mjs | ForEach-Object { $_.FullName })
node --test $nodeTests
```

Compiled commands:

```powershell
$env:CP_DISCOVER_PAGING_E2E='1'
npm.cmd run test:e2e -- discover-paging.spec.js movie-relationships.spec.js card-artwork-performance.spec.js movie-scroll-return.spec.js
# In a separate process, without the paging fixture:
$env:CP_TV_E2E='1'
npm.cmd run test:e2e -- iptv-people.spec.js iptv-discover-availability.spec.js movie-stream-sources.spec.js native-tv.spec.js streaming-providers.spec.js stream-player.spec.js tv-expanded-parity.spec.js
```

## Performance

Real read-only benchmark uses Lionz (~932.6 MiB, schema 4) and EgySat (~57.2 MiB, schema 3). It queries 100 identities: 50 accepted Lionz Film IDs and 50 absent IDs. One first read and 30 warm samples per case; OS caches were not evicted. These measurements cover manager/SQLite lookup, not external playback or network round-trip time.

| Catalogs | First process read | Warm median | Warm p95 | Response JSON bytes |
| --- | ---: | ---: | ---: | ---: |
| Actual Lionz + EgySat | 7.68 ms | 6.31 ms | 6.94 ms | 3,017 |
| 1 small synthetic provider | 2.92 ms | 2.48 ms | 2.73 ms | 359 |
| 2 small synthetic providers | 3.43 ms | 3.16 ms | 3.57 ms | 579 |
| 10 small synthetic providers | 9.22 ms | 9.67 ms | 12.07 ms | 2,348 |

[Raw samples and conditions](performance.json). The 10-provider fixture tests fan-out, not ten 1-GiB databases. Real catalog scale was measured directly in read-only mode instead of copying or synthesizing a large live database.

The first implementation let SQLite start from all available sources and hit the 250ms read deadline on Lionz. `EXPLAIN QUERY PLAN` exposed that scan. The fixed query starts at `source_matches` through the existing `idx_source_matches_tmdb` index and joins source/classification keys. A regression asserts that plan. No database schema/index write was required.

The UI test holds availability for five seconds: movie content renders before release and badge arrival moves card bounds by at most 1 CSS pixel. With availability still held, the chooser opened in 5.4ms in the measured fixture and web selection worked immediately. One batch covers the current logical page; chooser reuse of the page cache is covered by Node tests. Requests never join the Discover page-loading promise.

## Acceptance coverage

| Plan scenarios | Evidence and observed result |
| --- | --- |
| Person, role, grouping, pagination, provider-local identity | Store tests filter saved credits before page slicing; actor/director results differ. Existing file boundary scopes the query to the chosen provider. Compiled filmography returns the expected movie and Back restores the expanded origin. |
| Context/refinements, Reset, explicit View change | Compiled test searches to an empty actor result, resets, verifies the actual request still has person 103, restores Back, then verifies Provider View removes person navigation. |
| Missing person ID or portrait; Biography | Shared avatar fallback measured. Missing ID renders disabled filmography explanation and local bio error. Explicit biography opens the shared modal; route normalization and IPTV-settings client wiring pass. |
| Accepted identities versus candidate/unavailable/non-Film | Store tests reject unavailable and sports sources, and ambiguous identities despite cached metadata. Shared SQL also owns grouped Film membership. |
| Schema 3/4, cold manager, WAL | Reads bypass constructors; missing files stay missing; committed WAL changes are visible. An independently built pre-v4-shaped fixture runs availability -> source resolution -> actual playback route/raw service with mocked FFmpeg only; exact source 7.mkv is selected and movie DB bytes remain unchanged, with no migration backup. |
| Missing, corrupt, unsupported, locked provider | Unknown state preserved; healthy providers remain present. Lock error is injected, not a claim about every real filesystem contention condition. Schema 1/2 lack source classification and remain unknown without migration. |
| Provider rename/removal, cache expiry/mutations | Registry changes appear on fresh reads; removed source lookup fails. Client tests cover TTL, no-mounted-screen invalidation, coalescing, isolated subscriber cancellation and old-generation cache protection. |
| Delayed lookup, long names, ten providers | Compiled cards remain visible during five-second hold; row geometry fixed; two names plus +8 opens all ten providers. |
| Immediate dialog, explicit choice, one source, disabled web | No iframe/session before selection. Web rows usable while IPTV pending. Disabled web retains the IPTV choice, even as the only selectable provider. Keyboard focus stays inside the dialog. |
| Web presets/custom/IMDb and missing identity | Configuration and URL-builder tests cover presets/custom and required IDs. Existing compiled provider test verifies saved ordering/target selection; IMDb resolution stays deferred until choice. |
| IPTV versions, session races and cleanup | Compiled exact-version selection starts item 8 and closing sends the token stop. Coordinator tests cover late start after close, owner switch, explicit IPTV-to-web takeover and retry after transient stop failure. Fresh source membership is checked before launch. |
| History and existing IPTV behavior | Existing service/routes suites cover provider-scoped history and playback; the unchanged `IPTVPlayer` posts provider/kind/item history. Coordinator retains explicit series history overrides. No claim of real watched-media playback from synthetic manifests. |
| Movie/TV regressions and design | Existing relationship, artwork, paging, scroll, streaming and TV parity suites passed. Shared Movie and TV controls were exercised alongside new IPTV controls; no parallel portrait/source-list implementation remains. |

The fixture tests and source trace support the approved behavior. Compound races across browser navigation, external catalog edits, disk contention and real upstream streaming are not exhaustive. Provider/catalog changes made outside CP become visible on the next active 15-second revalidation; they are not live probes.

## Review and failure disposition

One fresh reviewer examined the scoped baseline diff. Findings were fixed: explicit cross-surface stop before web playback; actor Reset/View mismatch; pending configured-provider rows; missing-ID explanation; and genuine schema-3 read-to-playback route coverage. The reviewer independently passed 10 availability/session tests after the first lifecycle fix. The executor ran the later fixes and final suites; no second review is implied.

Initial broad run: 153 tests, one failure in an old source-text assertion expecting `iptvApi.stopPlayback` directly in `IPTVWorkspace`. The shared coordinator now owns that call. The assertion was moved to the actual owner and supplemented by behavioral cleanup tests; broad rerun passed. Initial pre-change config restart baseline had an intermittent subprocess JSON parse error; the focused baseline rerun and later full config runs passed. A new adversarial test initially used the nonexistent state `uncertain`; it was corrected to the schema's actual `ambiguous` state. RED tests also exposed the missing cache invalidation, missing pending rows, keyboard focus problem and stale person heading before their fixes. No failing required check remains hidden.

The reviewer set aside live playback/activation, unrelated dirty baseline and in-progress final documentation/testing. The first two exclusions are within the authorized boundary. The final documentation/test work is included here.

## Desktop evidence and limits

- [Cast controls at 1600](iptv-cast.png)
- [Cast at 1920x1080, 1.5 display density](iptv-cast-1920-150.png)
- [Discover badge](discover-badge.png)
- [Source chooser](stream-chooser.png)

Playwright device scale factor 1.5 tests rendered display density; it is not a claim that Windows desktop scaling was changed or manually verified. Fixture portraits intentionally exercise the shared fallback. The regression suite includes its pre-existing small-viewport cases; no mobile code or redesign was added.

External TMDB biography/embed/media transports were fixture-controlled. Local availability/source APIs were real except the synthetic ten-provider layout case. Real IPTV service reachability, successful media playback and live visual behavior require separately approved activation. A saved-catalog badge never guarantees the provider is online.

## Final gate

Final combined compiled run passed all 31 tests. Candidate bundle: `index-ClUXqNff.js`. Build passed in 2.53s. New guide links were checked; the isolated snapshot was supplemented with the original historical reports referenced by these guides, without changing those reports. Candidate activation, restart, commit, push and release remain separate actions. The tested code, plan, guide updates and evidence are kept in the managed worktree.
