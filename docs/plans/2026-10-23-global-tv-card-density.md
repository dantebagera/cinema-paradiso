# Global TV card density and expanded layout

**Status:** Implemented and verified in isolation, 2026-10-23; not live activated. Dante: "yes go ahead implement these changes globally and make sure the cards dont leave empty space under the poster". Approval refers to the preceding confirmed six-point presentation specification.

## Problem and decision

- **Now:** `TVSeriesCard` renders a separate offline/watched paragraph and the preview service supplies a two-line library/download explanation. Expanded `TVSeriesPage` puts overview and actions alongside its poster, allowing long text to leave a large unused area under the image.
- **Wanted:** Compact standard cards, conditional green offline percentage beside date/season/episode counts, detailed offline/watched statistics in the expanded view, Returning Series red and Ended green everywhere these statuses appear. Expanded long text must flow below the poster row.
- **Confirmed:** Library, Discover, Lists and TV person/related result grids reuse `TVSeriesCard`; expanded views reuse `TVSeriesPage`. Related poster-only tiles have no status/count paragraphs and retain their existing design.
- **Open decisions:** None affecting the approved scope. Preserve unknown coverage rather than inventing a percentage: downloaded episodes with incomplete metadata display `Offline % unknown` in green; expanded totals retain the existing dash convention.
- **Scope:** Desktop presentation and removal of obsolete preview explanation at its service owner. No changes to coverage calculation, acquisition, playback, catalog/config, mobile design, restart, deployment, commit or push.

## Contracts affected and contract-change decision

| Contract/source | Agreed behavior/exceptions | Affected surfaces | Proposed behavior | Changes contract? | Decision |
| --- | --- | --- | --- | --- | --- |
| Dante's request and confirmation, 2026-10-23 | Remove explanation and detailed statistics from standard cards; green offline percentage only for available episodes; red returning/green ended; no text-driven poster gap | All TV standard cards and expanded detail | Implement exactly this presentation | Explicit requested amendment | Approved above |
| `TVReadModel.coverage` | Only complete released regular-episode coverage produces a percentage; incomplete coverage stays unknown | Cards, detail, lists | Preserve calculation and uncertainty | No | Existing rule retained |
| Existing TV controls/navigation | Watchlist, watched eligibility, poster edit, selection, Play, missing-next reason and review warnings | Shared standard card and detail | Preserve genuine diagnostic text and controls | No | Existing behavior retained |
| Shared Movie layout | Movie cards use `UnifiedMovieCard` and its existing dimensions/status tones | Movie/TV shared UI | Add a reusable danger tone without changing other tones or Movie geometry | No | Existing behavior retained |

## Current design and ownership

| Responsibility | Owner | Callers | Preserve | Obsolete path |
| --- | --- | --- | --- | --- |
| Standard TV presentation | `src/features/tv/TVWorkspace.jsx::TVSeriesCard` | `TVWorkspace`, `TVResultListing`, `TVListsWorkspace` | Metadata, actions, navigation, warnings | Standard statistics paragraph |
| Expanded TV header | `TVSeriesPage` in the same file | TV workspace navigation | Poster aspect, metadata, controls, translations | Long text alongside poster |
| TV layout | `src/features/tv/tv.css` | All TV surfaces | Shared grid/dimensions | Duplicate old header declarations replaced coherently |
| Shared badge tones | `src/components/movie-card/movieCard.css` | `UnifiedMovieCard` plus expanded TV badges | Existing Movie tones | None |
| Preview no-local action | `services/tv_metadata.py::preview` | Discover cards and preview detail | Disabled Play, label, stream target | Library/download explanatory reason |

Baseline: Desktop checkout, `master`, HEAD `be511f9`, extensively dirty before this task (including all four affected source files). Preserve unrelated edits and save task-local before copies in OS temp. Live port 5000 belongs to PID 25560, Python312 `app.py`. Runtime data/config and the running bundle's source provenance are not proven; no live behavior claim or process control is part of this task. Build only into a unique `CP_TEST_ROOT/dist`, leaving Desktop `dist` untouched.

## Exact behavior contract

### Frontend

Reuse `UnifiedMovieCard`, `ExpandedRating`, shared chips and the Movies Owned green (`#78f2a7`). Standard title metadata becomes `dates · N seas. · N eps. · X% offline` with only the final phrase green and only when `available_count > 0`; retain estimated episode counts. Zero available episodes have no offline phrase even if a stale percentage exists. No watched statistics in standard text. Use one TV status-tone mapping for standard and expanded views: Ended uses existing `owned` green, Returning Series uses new `danger` red, others stay neutral.

Expanded header retains the direct poster image and uses a grid with poster plus concise metadata in the first row. Overview, notices, runtime, external link and action buttons occupy a full-width row beneath both columns. Long overview does not increase the poster row height. Show the original offline and watched counts/percentages in expanded metadata for local series; preview-only series do not invent watched totals. Retain real missing-file/playback reasons. Do not crop or distort the poster.

Dense-card regression evidence: five genres, three countries, a quality chip and a two-line title produced 8.84px of extra height below the poster. The shared standard rating row added 8px padding on top of the body's existing 12px flex gap. Remove that redundant padding at the shared owner; ordinary cards retain their rating position through the existing automatic top margin. Do not add TV-only height/spacing patches or truncate metadata.

### Backend

Only remove the obsolete download/library explanation from `TVMetadata.preview().primary_action.reason`, keeping the field as an empty string. No storage, migrations, retries, failure-policy, physical availability or count-policy changes.

## Implementation sequence

- [x] Add rendered desktop regression tests first; run against the current build and confirm feature-specific failures.
- [x] Amend shared TV card metadata/status owner, expanded header layout and preview reason owner. Remove obsolete duplicate header styling.
- [x] Run new tests, related TV parity/navigation suites and relevant shared Movie layout coverage. Review the task-specific diff against before copies.
- [x] Inspect desktop screenshots and poster geometry at 1366 and 1920 widths; record verification and limitations here.

## Acceptance matrix

| Scenario | Action | Expected result | Surface | Evidence |
| --- | --- | --- | --- | --- |
| Complete local coverage | Browse real fixture | API offline percentage appears green in title metadata; no watched paragraph | Library, Discover, Lists | Browser/API assertions |
| No local episodes | Browse preview | No offline label; obsolete explanation absent in API and rendered UI | Discover and preview detail | Browser/API assertions |
| Partial metadata with downloads | Browse supplied adverse metadata | Unknown percentage is explicit; no invented zero/100 | Standard and expanded | Browser assertions |
| Returning/Ended/other | Browse cards and open details | Red/green/neutral respectively | Global shared owners | Computed CSS assertions |
| Long title and many metadata chips | Browse at 1366/1920 | No overflow; standard card stays bounded by poster plus ordinary padding for representative dense metadata | Standard grids | Bounding boxes/screenshots |
| Very long overview | Open series | Overview spans below poster row; no poster-column void alongside long text | Expanded | Bounding boxes/screenshots |
| Playback/review warning | Browse affected fixture | Real warning remains; actions and navigation still work | Shared cards/detail | Browser assertions and existing suites |
| Movie regression | Run shared Movie checks | Existing geometry/status behavior retained | Movie Library/Discover | Existing relevant suites |

## Verification and rollout

- **Baseline/focused:** `CP_TV_E2E=1` with `tools/run_playwright_e2e.ps1 tests/e2e/tv-card-density.spec.js`, unique OS temp root and isolated dist. The TV fixture server forces embedded qBittorrent mode before importing the app and stubs media/provider actions. No live clients are used.
- **Broader:** TV parity, expanded parity, native-TV navigation and shared Movie desktop card tests; focused Python preview/TV coverage tests. Avoid hardware benchmarks and full unrelated backend suites.
- **Compiled UI:** Vite production build in the disposable root; screenshots and geometric assertions on that build at desktop sizes.
- **Live:** Not authorized; no restart or served-dist replacement.
- **Reporting:** Record actual passes/failures, screenshots, known gaps and source-only versus isolated/live status. Compare each approved visual rule before completion.

### Results, 2026-10-23

- Baseline new browser checks failed on the missing inline green offline label (2 expected failures, remaining 12 stopped by the failure cap). A subsequent run caught a shared descendant color rule overriding green; the TV metadata selector now wins without changing other title metadata.
- Dense metadata checks then failed at both desktop widths with 8.84px added below the poster; removing the duplicate shared rating padding resolved both. No metadata truncation, poster cropping or TV-only height patch was added.
- Production build succeeded into OS temp. Combined browser command passed **58/58**, including 16 density checks, 8 expanded parity, 20 TV parity, 7 native TV and 7 shared Movie scroll-return checks. The final density suite rerun, with the expanded unknown-percentage assertion added, passed **16/16**.
- Relevant JavaScript suites passed **6/6** (`tv_card_enrichment.test.mjs`, `cardGrid.test.mjs`). Python command passed **54/55** across TV vertical slice, unified card UI, and full-row grid UI. The unrelated source-only Home expectation `FullRowCardGridUiTests.test_home_scrolling_rails_share_layout_and_group_trailers` still expects the old Upcoming URL in untouched `src/App.jsx`; no assertion or Home behavior was changed.
- Independent read-only review compared all four source files with their exact pre-task copies and found no actionable regressions. Expanded unknown coverage subsequently gained a dedicated adverse browser assertion.
- Inspected dense standard and real-poster preview screenshots. Standard geometry assertions allow at most the existing 4px structural allowance below the poster; long expanded overview begins within the normal 20px row gap and spans both columns. Posters remain uncropped at a 2:3 width/height ratio.
- Evidence and commands: [verification report](../verification/global-tv-card-density/report.md). Historical parity screenshot files written by existing tests were restored from pre-run copies.
- All requested presentation rules are implemented in the shared owners. Live process, catalog/config and Desktop `dist` were not changed. No commit, push, restart or deployment.
