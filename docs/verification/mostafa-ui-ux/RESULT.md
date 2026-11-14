# Mostafa desktop UI integration — isolated result

Approved scope: Dante's “go” permits source implementation and isolated verification. This work adopts Mostafa's actual shared frontend implementation from private PR #1, head `92f88e8a9af63a1ed4e708d3a3b6c11c6aff5272`, onto Dante's repaired source at `be511f98846a67a182e5b371ad087938e9344362`, including the newer dirty TV work. It does not replace the project folder or merge the friend's installation.

The reviewable, uncommitted result is on `codex/mostafa-ui-ux` in `C:\Users\dante\.codex\worktrees\mostafa-ui-ux\cinema paradiso`. The original installation remains separate. Verification below uses compiled isolated servers, fake provider responses and temporary test data; it is not evidence of live production playback or downloading.

## Implementation

- Actual shared Sidebar, workspace controls/chrome, selection bar, metadata filters, list toolbar, horizontal card rails, card artwork/geometry and Home trailer components are reused across the approved desktop surfaces. Home, Library, Discover, Movie/TV Lists, TV credits and supplied IPTV presentation changes use those owners.
- Desktop rules are adopted; new portrait drawers, orientation behavior and mobile redesign are excluded. Original narrow-width rules are retained.
- Backend additions are restricted to `services/tv_routes.py`, `services/tv_read_model.py` and `services/tv_metadata.py`: validated TV list criteria reuse the existing search predicate/sort before pagination, and creative-credit portraits use existing credit storage. No schema migration or operational backend transplant is included.
- Existing acquisition, qBittorrent, player, import, monitoring and identity owners remain the foundation. The ten protected dirty service/review/test files retain their original literal hashes. Source guards compare all original text sources with their frozen snapshot, normalizing only line endings.

## Corrections made during integration

| Issue | Result |
| --- | --- |
| TV “Select all results” only selected loaded cards | Label now says “Select all loaded TV shows”; explicit cross-page selection and frozen review IDs remain |
| Portaled reviews/editors survived a hidden owning workspace | Shared dismissible-popover owner closes them on workspace hide; collapsing controls alone retains an active review; late preview responses cannot reopen it |
| Failed or partial movie metadata looked like completed filter results | Active fields determine metadata completeness; failed candidates show incomplete results and Retry; unknown years cannot satisfy an upper-bound filter |
| Owned list popularity had no SQL score | Uses the existing cache-only card-projection endpoint; no owned-title provider request; absent cache scores expose incomplete ordering |
| Selected feed summaries overrode canonical rating/votes | Original canonical precedence retained |
| Missing CirclePlus import crashed list Add movie | Existing icon imported; actual search/add path covered |
| Native Followed dialog obscured Sources review | Closes before handing control to the existing torrent review |
| Redesigned TV card omitted its no-target explanation | Backend `primary_action.reason` retained |

Fresh whole-change review completed; substantive findings were corrected in one pass with actual failing/passing browser paths. Fixture mistakes (wrong labels or payload assumptions) are recorded separately and are not described as product bug reproductions.

Ruling: the experimental AI indication remains inside the AI workspace. Mostafa's Sidebar omits the duplicate navigation badge. Cost: Sidebar alone provides less experimental-status context; feature behavior is unchanged. No reviewer minors are deferred. The reviewer deferred rendered/test proof to the executor; the gates below supply that evidence.

## Verification

Source implementation and isolated verification are complete, with the explicitly recorded suite exceptions below. The running installation is unchanged. Final logs are retained in this folder's `logs/`; scratch also preserves earlier RED runs and intermediate failures.

Confirmed completed gates:

| Gate | Result | Evidence |
| --- | --- | --- |
| Node owner/model tests | 126 passed | `logs/node-verified.log` |
| Focused frontend owner assertions | 156 passed | `python-owner-final.log` |
| Protected TV backend suites | 188 passed | `tv-protected.log` |
| Narrow TV filter/portrait additions | 7 passed, including invalid criteria and persisted portrait behavior | RED backend log and focused run |
| Shared credit card geometry | 4 desktop sizes passed, with 106×132 portraits and unclipped awards | `geometry-final.log`, desktop/awards screenshots |
| Stateful navigation and award Back restoration | 3 passed | `navigation-final.log` |
| Full Python suite with isolated compiled dist | 1,723 run; 3 failures | `python-final.log` |
| Broad compiled desktop suite | 221 passed, 1 failed, 1 skipped; failed case passes independently, skipped TV case passes on its required fixture | `logs/desktop-verified.log`, `logs/collection-final.log`, `logs/tv-stream-final.log` |
| Compiled native TV, per-group fresh data | 57 passed: 7 native TV, 9 download contracts, 8 expanded parity, 3 season-pack Follow/import, 6 normal import, 19 desktop parity, 5 stabilization | Passing group logs in `logs/` |
| Discover real API paging/history | 7 passed, including repeated sidebar changes, final remainder, and Back/Forward | `logs/discover-paging-complete.log` |
| TV series inset regression | Native navigation passes after hidden Movie chrome stops influencing the active TV series page; layout owner checks 3 passed | `logs/native-tv-verified.log`, `logs/layout-owner-final.log` |

The broad desktop run's single failed case hit Chromium `net::ERR_NO_BUFFER_SPACE` while loading `SharedMovieCards`. Its parent module returned HTTP 200, but the workspace showed a module-load error. The identical collection/list geometry case passes independently against the same build. This is retained as a broad-run failure, not relabeled a green full run. Its skipped TV stream-page case separately passes on the native-TV fixture; provider-page loading is not claimed as successful real playback.

The first combined TV run shared mutable acquisition/catalog data across seven test groups (47 passed, 10 failed). Earlier tests queued/imported episodes used by later groups, so their original expectations were no longer valid for that shared state. `baseline-tv-state.json` demonstrates this on the unchanged frozen backend: both seasons are initially accepted, queuing the season-one episode succeeds, and only season two remains accepted afterward. Final groups each start a fresh temporary data root. Operational assertions retain two releases, season destinations, explicit-submit boundaries and verified import; they were not relaxed. Legacy UI test steps were adapted to expanded shared controls, portaled criterion pickers and the approved abbreviated card labels.

One first independent TV parity run measured a 12-pixel filter-row difference at 2048 pixels (18 passed, 1 failed). An unchanged diagnostic rerun measured exactly matching boxes, and the full 19-case parity rerun passes. The earlier measurement remains recorded; no layout assertion or tolerance was weakened. The two obsolete “Open filters” steps in stabilization were replaced with the approved shared-controls interaction, after which all five tests pass.

Rendered fixture evidence covers populated and empty Home at 1280/1920, shared Library/Discover/Lists, long award/credit content at four desktop sizes, and TV review/import states. New renders are retained under `desktop/` and `evidence-copies/`. The 33 older verification images overwritten by test defaults were restored byte-for-byte from the frozen baseline; `restored-prior-evidence.json` records them.

### Acceptance comparison

| Approved contract | Observed isolated result |
| --- | --- |
| Actual unified Mostafa components | Shared controls/cards/rails used across Home, Library, Discover, Lists and TV; compiled layout and owner tests pass |
| Canonical movie metadata and truthful filtering | Canonical rating/votes win; partial/failed metadata displays incomplete status with Retry; owned popularity uses cache only; list membership stays unchanged |
| TV filter semantics | Full membership filtered/sorted before pagination; invalid/null criteria rejected; no criteria retains alphabetical baseline |
| Stateful desktop navigation | Sidebar, media changes, repeated expansion/collapse, browser history and award/related-card return paths pass |
| Follow and lower manual controls remain separate | Preview/draft starts no transfer; explicit start and lower-season submission retain their respective owners; native and protected suites pass |
| Identity, destinations and import safety | Existing/proposed/ambiguous destinations, season bindings, safe cleanup, retry/error states and fixture imports pass; protected source hashes unchanged |
| Operational backend preservation | Exactly three approved TV support files differ; acquisition, monitoring, qBittorrent and player sources are preserved; original source, served bundle and running PID match baseline |
| Desktop scope and activation boundary | New portrait/mobile behavior excluded; all observed renders are desktop fixtures; no production activation or real transfer performed |

The full Python suite is **not green**. Failures are:

1. `test_pinned_offline_inputs_reproduce_complete_seed_and_bootstrap_both_organizations`: pinned awards input produces a null seed; also fails in the original frozen baseline.
2. `test_streaming_modal_shows_loading_feedback_until_iframe_loads`: obsolete source assertion expects `streamLoaded`; also fails in the original frozen baseline. Compiled stream-player behavior is checked separately.
3. `test_movies_get_is_pure_and_projection_is_nonblocking_progressive`: unchanged IPTV projection exceeds its one-second threshold (4.37s in the full run). Focused integration and original-baseline reruns both fail (1.01s and 1.36s). The original initial full run passed this case; that variability remains explicit. No IPTV backend or threshold was changed.

The original frozen full suite ran 1,716 tests with four failures: the first two above and two missing compiled-dist route failures. The final compiled integration run resolves the environment's missing-dist route failures. Earlier integrated/browser failures and stale owner/layout expectations are retained in scratch logs; only final rebuilt gates are used for completion claims.

## Boundaries

No production catalog/configuration/data changes, live restart, activation, real download, merge, commit, push, release or packaging occurred. The source result and its isolated evidence remain available for review. Real player/qBittorrent smoke tests require the separately authorized activation path.
