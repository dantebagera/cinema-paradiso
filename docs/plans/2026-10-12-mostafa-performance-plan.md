# Mostafa desktop performance repair

**Status:** Implemented, compiled and verified in the private preview on 2026-10-12, with full-suite exceptions and live-state differences explicitly recorded in `docs/verification/mostafa-performance/RESULT.md`. Approved for autonomous investigation, implementation, builds, isolated tests and preview restarts. Dante explicitly said to change code to achieve the goal, continue without asking while he sleeps, and shut down the device only after completion and verification. The original Desktop installation is read-only. No merge, commit, push, release, provider operation or real media mutation is part of this task.

## Problem and decision

- **What happens now:** Dante reports reduced responsiveness in the Mostafa worktree compared with the Desktop project. Fresh Library measurements are similar (approximately 0.9 seconds cold; sidebar switches 0.1–0.2 seconds). Card backgrounds request extra artwork eagerly and list filters repeat metadata reconstruction inside every sort comparison.
- **What Dante wants:** Fix actual causes in the existing worktree while keeping Mostafa's integrated design, list filter support and Dante's repaired operational backend. Verify measurable improvement rather than stopping at diagnosis. Save a report and then shut down the PC.
- **Confirmed:** Branch `codex/mostafa-ui-ux`, HEAD `be511f98846a67a182e5b371ad087938e9344362`, with protected prior tracked/untracked integration work. Source text comparison confirms only `tv_metadata.py`, `tv_read_model.py`, `tv_routes.py` differ among services. Main process child 100356 has Desktop venv parent 94368; preview child 34632 has worktree venv parent 71392 and owned supervisor 17092. Ports 5000 and 15000 serve their respective dist indexes. Preview uses private data/cache and qBittorrent 18686.
- **Measurements:** Original/preview real Library samples and interactions are recorded under `docs/verification/mostafa-performance/`. Default list helper reads all 10,000 metadata objects unnecessarily; genre/rating/popularity sort repeats about 250,000 reads, median 134 ms. Styles apply CSS background URLs to all 39 cards; `loading="lazy"` governs the img tag only.
- **Unknown:** The precise interaction Dante experienced was not specified. Compare representative cold loads, scrolling, expansion/collapse, repeated navigation, lists and TV. Avoid attributing all delay to one root cause without evidence.
- **Open decisions:** None needed for the measured performance repairs; existing user-visible contracts remain.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior | Affected surfaces | Proposed behavior | Changes contract? | Decision |
| --- | --- | --- | --- | --- | --- |
| Approved Mostafa integration design | Keep actual shared owners, visible artwork, desktop layout and controls | Movie cards, Home rails, related cards | Defer offscreen artwork work until needed; preserve visible styling | No | Autonomous performance repair approved |
| List filter plan and tests | Evaluate full membership before paging, stable sorting, canonical owned metadata, truthful incomplete metadata and Retry | Movie Lists | No inactive constraint work; build metadata once per row when needed | No | Approved |
| TV operational rules | Five-hour Follow retry, lower manual controls, validation/import safety | TV and acquisition | Preserve owners and behavior | No | Existing contract |
| Workspace/history rules | Repeated expansion and return preserve scroll/state/focus; hidden panels dismiss portals | Shared cards and workspaces | Verify existing lifecycle after performance changes | No | Existing contract |
| Source/runtime boundaries | Worktree only; main remains protected | Launcher, data, runtime | Build and restart only verified preview; read-only hash and DB count comparison | No | Explicit approval includes necessary preview restarts |

## Current design and ownership

| Responsibility | Authoritative owner | Entry/callers | Preserve | Obsolete work |
| --- | --- | --- | --- | --- |
| Card artwork style | `cardArtwork.js` and shared card roots in `MovieCard.jsx`, `RelatedMovieRail.jsx`, `IPTVWorkspace.jsx` | Unified Movie/TV, Continue and Upcoming cards, related tiles and IPTV series tiles | Same gradient/image choice and visible layout, immediate expanded artwork, fallback when IntersectionObserver absent | Eager background requests for offscreen cards |
| List predicates and sorting | `filterListRows` in `listCatalogFilters.js` | MovieListsWorkspace full membership | Constraint semantics, canonical adapter, stable input order ties, source array unmutated | Repeated metadata construction and disabled predicates |
| Backend operations | Existing services in worktree and main | Existing routes | Three previously approved support differences only | No backend change anticipated |

## Exact behavior contract

### Frontend

Keep desktop geometry, typography, navigation and controls. Offscreen collapsed artwork must not request a backdrop until the card approaches the viewport; visible/expanded cards retain the existing image and gradient. Loading must use one shared hook/owner rather than duplicated per-surface rules. Observer cleanup must not leak or update unmounted cards. Absence of IntersectionObserver falls back to existing eager rendering. Poster loading and accepted SQL metadata remain unchanged.

`filterListRows(rows, filters, genres, metadata)` retains its signature. With no effective constraints and default sort, return unchanged row order without consulting metadata. When constraints/sort require metadata, evaluate at most once per candidate row per invocation; decorate sort keys outside the comparator. Don't enrich extra provider records, change unknown-field treatment, mutate membership/source order, or hide incomplete metadata errors.

### Backend

No changed API, persistence, schema, retries or operational owner. Read-only baseline checks record hashes and SQLite integrity/counts. Tests use `CP_TEST_MODE=1`, unique OS-temp `CP_TEST_ROOT`, blocked providers and independent dist. Live benchmark blocks mutating requests including automatic Follow checks. Original main never receives an implementation/build/restart.

## Implementation sequence

1. Capture process/config/data/bundle baseline and comparable measurements. Keep initial evidence distinct from final evidence.
2. Reproduce eager offscreen artwork in compiled fixture UI, add failing regression, repair existing shared artwork owner, verify visible artwork and lifecycle.
3. Reproduce list reconstruction cost, add failing behavioral tests, optimize existing helper, retain all predicate and sort regressions.
4. Independently inspect final diffs, run all Node tests, relevant Python UI/backend tests and full isolated Python suite. Run compiled desktop navigation/list/artwork/TV checks. Record unchanged failures explicitly.
5. Build worktree dist, stop/restart only verified preview supervisor, compare served bundle and desktop performance. Compare protected original hashes/settings/databases after testing. Save report with measurable results and limitations.
6. Only after verified completion, close task-owned test resources, save final report, and request Windows device shutdown without forcing unsaved apps closed.

## Acceptance matrix

| Scenario | Action | Expected result | Owner | Evidence |
| --- | --- | --- | --- | --- |
| Large default list | Evaluate 10,000 rows | Original order, no metadata reads | list helper | Node behavioral test + benchmark |
| Constraints plus sort | Filter/sort full 10,000 rows | Same matching identities/order, at most one metadata build per row, reduced time | list helper | All existing/new Node tests + median measurements |
| Missing year/country/rating | Apply constraints | Existing missing-field behavior, no fabricated matches | list helper | Existing filter tests |
| Incomplete metadata/retry | Apply list filter then retry | Incomplete message retained; no definitive false empty result; Retry restores matches | Movie Lists | Existing compiled lists-layout tests |
| Offscreen cards | Load and inspect requested backdrop identities | Offscreen backgrounds deferred; visible cards retain artwork | shared artwork | New compiled fixture regression |
| Scroll toward cards | Scroll through list/rail | Artwork appears before/when card needed, no unbounded observer leak | shared artwork | New browser test + request counts |
| Expand, collapse, change card, repeat/history | Mouse/keyboard/Back/Forward | Existing geometry, centered expansion, scroll return/state retained | shared card | movie-scroll-return and navigation tests |
| Shared consumers | Library/Discover/Lists/Home/TV | No blank visible background, controls/selection intact | cards and shared layout | Desktop fixture regressions/screenshots |
| Real preview after build | Compare main/preview under same viewport and safe operations | No new browser errors; measurements reflect actual new bundle; fixed costs reduced | dist/runtime | before/after JSON and screenshots |
| Original preservation | Compare source/config/jobs/data baseline | Original untouched; all DB integrity checks ok | baseline tool | protection comparison |

## Verification and rollout

- **Baseline:** Current observed Library timings; historical full-suite exceptions are offline awards seed, obsolete streamLoaded assertion, IPTV progressive projection timing. Recheck current full suite and report exact results.
- **Focused:** `node --test tests/list-catalog-filters.test.mjs tests/list-catalog-performance.test.mjs`; artwork browser regression on isolated compiled server.
- **Broader:** All `tests/*.test.mjs`; Python unittest discovery with isolated compiled dist and provider-blocked temp data. Appropriate source ownership, TV filter and preview launcher tests.
- **Compiled UI:** Existing Playwright runner; artwork, list layout, scroll return, workspace controls, smoke, relationships/history, relevant native TV groups with fresh data.
- **Live:** Worktree build and verified supervisor restart only; no real download/import/delete/player task. Original main comparison stays read-only. Validate owner root/command chain and dist hash.
- **Report:** Save `docs/verification/mostafa-performance/RESULT.md` and machine-readable timings, exact pass/fail counts and protected-source comparison before shutdown.
