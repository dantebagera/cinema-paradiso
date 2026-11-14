# Home dashboard hybrid — measured implementation specification

**Status:** Ready for implementation in a separate chat after Dante explicitly authorizes product implementation there. Prepared 2026-10-19. This is the normative technical annex to [the main plan](2026-10-19-home-dashboard-hybrid.md); read both. No product code was changed during preparation.

## Measurement method and limits

- Rendered the existing old and current Home components independently in installed Chromium through Playwright, using their existing source CSS and the main project's installed React runtime. Browser requests were blocked; fixture rows were invented and no live data/backend was used. esbuild bundled existing components in memory, without a Vite build or writing product output.
- Measured at 1600×1080 and 1920×1080 CSS pixels with a 220px sidebar. Separately constrained the existing current toolbar to the old column proportions with 20px panel padding, and measured the old header text in a 190px sizing box. These are layout-fit checks, not verification of an implemented hybrid dashboard.
- [Raw measurements](assets/2026-10-19-home-dashboard-hybrid/08-existing-layout-measurements.json). `toolbarAtOldPanel` records an isolated width constraint, not final page placement; its absolute x coordinates are not target coordinates. The meaningful checks are width, overflow and label fit. `slimHeaderSizing` records a sizing probe, not a product edit.
- The attachments are scaled screen crops. Old 156px posters appear about 117 image pixels wide, implying approximately 75% scaling. The 190px header corresponds to approximately 142.5 image pixels, matching the supplied 142px-high header reference. This scale is inferred; target values below are CSS pixels measured against source, not blindly copied PNG dimensions.
- Keep the existing main project's shell, 16px workspace padding, typography stack, theme tokens and 1760px maximum content width. Do not import the old shell's 33.6px right padding or replace global theme tokens. At the measured native scrollbar configuration, Home widths are 1340px and 1660px. Test proportions from the actual container as well as these reference values; OS scrollbar preferences can alter available width.

## Exact desktop geometry

### Composition and spacing

Use the existing HomeWorkspace root/grid ref with one full-width column. Its children, in DOM order, are: hero; `.home-status-grid` containing HealthPanel and `.home-followed-section`; HomeTrailersPanel; ContinueWatchingRail when history exists; `.home-poster-stack` containing the existing Trending and Coming soon sections. The latter is a layout-only wrapper, not another feature implementation.

- Gap between major old-base sections: 18px, matching the old Home. Gap within `.home-status-grid`: 18px. Gap between the retained current Trending and Coming soon sections: 12px inside `.home-poster-stack`, matching current Home's section gap. Expanded details stay inside their existing section.
- Status columns at viewport widths ≥1440px: `minmax(0, 1.1fr) minmax(340px, .72fr)`. Main frame reference: Health/Following widths approximately 799.02/522.98px at 1600 and 992.42/649.58px at 1920. These are source proportions, not fixed panel widths.
- Desktop 981–1439px: stack Health above Following using the old layout's existing single-column pattern. Its old threshold was 1280px; move this Home-specific desktop fit threshold to 1439px because the new toolbar requires more minimum width. This prevents five health cards or the toolbar escaping their column. Keep five health cards across on these desktop widths. No mobile redesign/testing is included; do not modify ≤980px-specific rules beyond removing selectors made obsolete by the new composition.
- Use `align-items: start` on the status row; normal Health and Following panel minimum height is 287.2px. Health may grow for current stale/error/long-count content; it must not force Following's three-row viewport taller. Following details can extend its existing right-hand wrapper without stretching the health panel or changing ReleasePanel height.
- Old-base panels use 1px existing border, 8px panel radius, old gradient and shadow. Scope restored old styles to Home. Current Trending/Coming soon retain their existing panel/card styles and 16px panel padding; do not apply old 20px padding to them.

### Header

- Hero minimum height: **190px** (old minimum was 262px, reduction 72px). Padding: **0 34px 8px**. One content column; preserve old bottom alignment, overlay gradients and existing `src/assets/header.png` at cover/right-center/opacity .96.
- Hero copy max-width 760px. H1 Home: 27.2px, line-height 1.1, margin 0. Kicker: 10.88px, line-height 1.2, margin `0 0 5px`. Slogan H2: 36px, line-height 1.12, max-width 680px, margin 0. Body: 16px, line-height 1.65 (26.4px), max-width 62ch, margin `12px 0 0`; preserve the exact old paragraph from reference 1.
- Measured copy height 179.45px; body width 534.75px and height 79.17px (three lines) at both target widths. The 190px hero fits without clipping. Use min-height rather than an overflow-clipping fixed text height so exceptional font substitution cannot hide text.
- H1 Home retains `id="home-banner-title"`/section accessible naming. Remove current hero-only Explore movies markup and its unused Compass import. This requested old header replaces that shortcut; Open Discover remains on Trending.

### Library health

- Restore the old five cards and their exact labels/details/tones as described in the main plan. Panel padding 20px. Old kicker/title sizes 10.88px/16.8px; title line-height 1.3; heading-to-cards gap 16px.
- Cards: five columns `repeat(5, minmax(120px, 1fr))`, gap 12px; padding 16px, minimum height 132px, internal gap 5px, 8px radius, 1px border, old card gradient/inset shadow. Values 24.8px/1.1, labels 11.52px bold uppercase, details 12.48px. Source-measured card height varies with content (141.27–157.27px in the old frame); do not incorrectly fix every card to 132px or clip detail text.
- Keep current unavailable/retry/empty/stale/freshness behavior. With no stats, show the current truthful state rather than rendering healthy zero counts. Loading while existing stats remain must retain last-known values. Put stale/retry above the cards and freshness below; allow panel growth rather than hiding either.

### Following — three rows plus current toolbar

- Panel padding 20px. Kicker Release watchlist: 11px/1.2, margin `0 0 4px`. Keep exact current H3 **Followed movies**, 16.8px/1.3. Heading/action line: 34px high; gap between title and actions 8px; margin below 4px. Total normal panel height: 42px padding/borders + 13.2px kicker + 4px + 34px controls + 4px + 190px viewport = **287.2px**. This is within 1px of the measured old 287.88px panel.
- Keep current toolbar order, icons, accessible names, functionality and sizes: download 32px; bell box 32px; scan 32px; matching count minimum 18px; filter 136×34px; four 4px inter-control gaps. Actual toolbar width is **266px** for a short count. Title measured 132.22px; together with the 8px title gap they need 406.22px. At 1600, the old-proportion panel has 480.98px inside its padding/borders, leaving approximately 74.76px spare. At 1920 it has 607.58px inside.
- Filter padding `0 24px 0 8px`, font 12.16px/weight 800, current popup option styles retained. Awaiting release measured **99.76px** against **102px** usable selected-label width. Preserve these values; do not shrink fonts or change wording to solve fit. Check count 0, 39 and 9999; count growth uses available heading slack.
- List viewport exactly **190px** for populated/short lists; three 58px rows + two 8px gaps. Use a flex column with nonshrinking rows; `height/min-height/max-height:190px`, `overflow-y:auto`, `overflow-x:hidden`, stable 8px native gutter. A 2px right inset accommodates the old hover translation without horizontal overflow. All matching rows remain mounted/reachable. Empty state fits the same viewport.
- Rows: 58px border-box height, 1px old border, 8px radius, padding `0 14px`, grid `12px minmax(0,1fr) auto`, gap 12px; old card background and hover. Title 14.4px, one line with ellipsis/full text available to accessibility; year 12.48px with 3px top margin. Keep current status classification, text and green/gold/muted colors; old badge shape/padding can be restored without changing status meaning. Available retains old green treatment.
- ReleasePanel itself remains fixed to this geometry while selected details use the existing wrapper beneath it. Preserve current selection/scroll/focus logic. No Following View all or drawer. Coming soon View all is untouched.

### New Trailers — old appearance with current grouping

- Existing HomeTrailersPanel remains the sole component. Keep its props, `source` state, `groupHomeTrailers`, version dialog state/effects, playback/retry/load-more callbacks and original video identities.
- Reuse HorizontalCardRail in header-arrow mode; remove its fixed `cardWidth="min(240px, 100%)"` for this surface. Home-scoped track columns are `(100% - 4*12px)/5` above 1600px, `(100% - 3*12px)/4` at desktop widths ≤1600px. No mobile work. Track gap 12px, padding 0. The existing rail continues to own scrolling, edge state, keyboard/native access and page-sized arrow steps; do not restore the old duplicate page-number state, useCardGridMetrics pager, or 680px scroll function.
- Panel padding 20px; border/radius/gradient old. Title block: old Trailer channels kicker and New Trailers H3. Reuse header arrows, styled 36×36px with 8px gap, top right. Keep current More videos in the header, immediately before the arrow group, including loading/disabled behavior; no footer action row. Source pills occupy a full-width second header row, gap 8px, bottom gap 16px. Pills operate existing `source` state and clear version selection; active state uses `aria-pressed`. No duplicate hidden select.
- Pills: old 30px minimum height, `5px 11px` padding, 11.2px/800, fully rounded border. Video cards: 7px padding, 1px transparent border, 8px radius, 9px internal gap, old hover/focus treatment. Thumbnail 16:9, 1px border, 8px radius; circular YouTube icon control 52×52px. Card title 14.08px/1.28, two-line clamp; source pill 9.92px with `3px 7px` padding and 4px bottom margin; published metadata 11.52px/750.
- Keep current group title/type presentation and representative-video identity; full original video titles remain in playback labels/version choices. Preserve the existing `Choose from N videos for TITLE` trigger and dialog. Style that trigger as a compact old-style control beside published metadata; it may consume a metadata row, but do not discard versions to force a uniform fixed card height. Keep stale/error/retry states and More videos in their existing owners.
- At 1600/1920 main frame, panel inner widths are approximately 1298/1618px; four/five cards respectively have widths approximately 315.5/314px, with thumbnail widths 299.5/298px. These follow from padding/borders/gaps; assert 16:9 geometry rather than hard-coding thumbnail height.

### Continue Watching — old cards, widened panel, old scrollbar

- Keep the existing ContinueWatchingRail and shared ContinueMovieCard; no duplicate history state or player handler. Full Home content width, panel padding 20px, old Your screening room kicker/Continue Watching title, header controls 36×36px/gap 8px; header-to-track gap 16px.
- Reuse HorizontalCardRail with `arrowPlacement="header"`, `cardWidth="156px"`, native scrollbar enabled as described below. Track gap 16px, padding `2px 2px 12px`, scroll-snap proximity. Do not use current seven-large-poster sizing for this section.
- Scope old visual geometry under this Home section: cards 156px width/min-width, no added card padding/border/background, grid rows `234px 4px auto auto`; poster 156×234px, border 1px and top radius 8px, contain framing; progress 4px, fill end radius 2px; title 14.4px/1.25, margin top 10px, one-line ellipsis; remaining label 12.16px with 4px top margin. Native old fixture card height is 286px. Ellipsis trigger 30px circle at top/right 8px; retain current menu items, exclusive grouping, keyboard and click-dismiss behavior.
- Full width shows more unchanged-size cards, rather than stretching six old posters. At the measured frame, viewport outer width is 1298/1618px; its 1294/1614px content fits seven/nine complete 156px cards with 16px gaps, plus any partially visible next card. Native scrollbar height is browser-controlled; do not fix panel height to suppress it.
- **Shared rail interface:** extend existing HorizontalCardRail with `nativeScrollbar = false`. Add `horizontal-card-rail-track-native-scrollbar` only to its track when true. Move the existing `scrollbar-width:none` and `::-webkit-scrollbar {display:none}` rules to the track selector excluding that modifier. All other rails retain the default false. This changes the authoritative rail hiding rule instead of adding a stronger Home override around it.
- **Paint owner:** add the explicit native-rail variant in `src/styles/scrollbars.css`: thin scrollbar, constant `#d4af3766` thumb and transparent track, including idle. The source reference uses `scrollbar-width:thin; scrollbar-color:#d4af3766 transparent`. In Chromium this native non-auto color uses browser-controlled thin painting; verify real native rendering with `--hide-scrollbars` removed. Do not reuse the 2px Reveal line or add scroll listeners/widgets. Existing scrollbar activity capture remains unchanged; it must not change this variant's idle color. Following keeps Reveal line; Trending/Coming soon stay hidden.

## Files, ownership changes and retirement

| File | Future change |
| --- | --- |
| `src/features/home/HomeWorkspace.jsx` | Restore header, old five-card HealthPanel, status-row wrapper and old-style full-width ContinueWatchingRail; wrap existing lower rails for their 12px gap; preserve ReleasePanel logic/current inline details/source review. Add the old health icons from lucide; remove unused hero Compass. Remove `home-without-playback` geometry/class after updating its tests; keep actual history conditional rendering. |
| `src/styles.css` | Replace current Home root grid-area rules with the specified one-column composition; remove resume/followed and trailers/health area pairing and the obsolete Home-without-playback variant. Keep main shell tokens/padding and all other workspaces. |
| `src/features/home/home.css` | Own the restored Home-specific panel/header/health/row/trailer/CW geometry. Replace conflicting existing rules, including Continue Watching-dependent `contain:size`, release-list flex-growth/max-height-none, current flat row overrides and current stretched poster rules. Remove the obsolete Home two-column override in its ≤1200px block; keep changes scoped to the agreed desktop fit. Preserve lower poster rails and inline-card styles. |
| `src/features/home/HomeTrailersPanel.jsx` | Restyle existing grouped cards, change source select to old pills, use header arrows and calculated column widths, retain More videos/version lifecycle. No model/API change. |
| `src/components/HorizontalCardRail.jsx` / `horizontalCardRail.css` | Add only the nativeScrollbar modifier interface/default above. Reuse existing header-arrow/cardWidth/scroll state; do not duplicate it in Home. |
| `src/styles/scrollbars.css` | Own the explicit old native-rail paint variant; preserve generic Reveal line. |
| Tests below | Add complete compiled-path layout/interaction coverage and replace only assertions explicitly superseded by Dante's new visual contracts. |

Do not modify App, backend, model, shared ContinueMovieCard JSX/CSS, theme JSON/generated playerTheme, acquisition or persistence unless investigation proves a genuine new dependency. Scoped Home styling handles its special card size without changing other shared-card consumers. Do not copy the old Home file or import old standalone inspector/drawer code. Keep the current function named MovieInspector: it supplies current inline details.

## Regression changes and acceptance checks

Create `tests/e2e/home-dashboard-hybrid.spec.js` using the existing fixture styles in following-card/continue-watching tests. Mock Home stats, followed rows, movie/TV history, trailer groups and movie feeds; keep the real compiled UI/selection/actions. Cover:

1. 1600×1000 and 1920×1080: DOM order, full-width sections, no inspector column, 190px header/no text clipping, normal 287.2px Following panel/190px viewport, three complete 58px rows/8px gaps, all 12 follows reachable, fixed toolbar and Awaiting release label fit. Geometry tolerance 1 CSS px (2px for native font/baseline comparison), not screenshot image pixels.
2. 1280×720, 1366×900 and 1440×900 desktop fit: status cards stack below 1440 and sit side by side at 1440; no document horizontal overflow; same toolbar control sizes/labels and three-row list. Sidebar expanded and collapsed at 1600/1920. No mobile viewports.
3. Zero/one/three/twelve follows, long title, count 9999, filter reset and scan/import state changes. Exact current filter membership and counts; no Following View all, Coming soon View all still works. Opening Following details must not enlarge the list viewport or stretch Health.
4. Five old-style health cards with current counts, cleanup tab navigation, loading with/without stats, unavailable/retry, cached-stale/retry and empty library. High counts/detail wrapping must remain readable; distinguish actual zero from missing stats.
5. Four/five old-looking trailer cards at 1600/1920 with current movie grouping; all sources and each source pill; representative/alternate playback identity; two-version chooser/Escape/focus recovery; More videos and no duplicate footer; loading/error/stale, channel change while chooser is open, navigation away and late response. Preserve actual player/follow behavior assertions from app-smoke.
6. Full-width CW with exact 156×234 posters/4px progress/old header arrows/30px menus, native old scrollbar at idle and after scroll, pointer/native drag/keyboard reach to final item, no inspector gap. Current movie/TV resume/restart/remove/View card, exclusive menus, missing identity and missing episode explanations. Empty history omits the section without an empty row.
7. Current Trending and Coming soon visuals/functionality and per-rail inline expansion: repeated selection/close, switching rails, actual canonical metadata/action eligibility, Back/Forward and scroll/focus recovery. Preserve these owners; no alternative inspector or popup.
8. Other horizontal rails retain hidden native bars; Following retains 2px Reveal line; reduced-motion stays correct; selectors/default rail API retain existing behavior.

Update `tests/e2e/following-card.spec.js` only for the new header vertical position (kicker and heading gap total is smaller) and independent three-row height; keep exact same-row title/control assertions and all filter/download/cancel/error checks. Update `app-smoke.spec.js` cases currently named Home uses scrolling poster rails, paired sections and inline movie details, release watcher fills the Continue Watching height, Home without playback history, and Continue Watching uses compact uncropped posters. Replace obsolete pairing/height and trailer select assertions with new order/fixed viewport/source pills. Keep grouping/version/playback/source-review/canonical-details/availability assertions. Update `tests/test_continue_watching_ui.py::ContinueWatchingUiTests.test_home_pairs_resume_followed_and_trailers_health_with_optional_history` to assert the new order and no obsolete pairing/class, retaining actual conditional history rendering and shared card/rail reuse. Do not broadly delete source assertions or relax unrelated suites.

## Executable isolated verification recipe — future implementation chat

The checked-in `tools/run_playwright_e2e.ps1` overwrites `CP_TEST_QBT_MODE` with **system** and builds its own server/root. Do **not** use `npm.cmd run test:e2e` or that wrapper for this work. Use the following direct setup from the main project, preserving evidence rather than deleting roots. Each case gets a fresh OS-temp root and its own copy of the isolated compiled bundle; never point tests at port 5000 or production dist/data.

```powershell
$ErrorActionPreference = 'Stop'
$cpRepo = (Get-Location).Path
if ($cpRepo -ne 'C:\Users\dante\Desktop\cinema paradiso') { throw 'Wrong checkout' }
$cpPython = Join-Path $cpRepo '.venv\Scripts\python.exe'
$cpRunRoot = Join-Path ([IO.Path]::GetTempPath()) ('cp-home-hybrid-' + [guid]::NewGuid().ToString('N'))
$cpBuildDist = Join-Path $cpRunRoot 'dist'
New-Item -ItemType Directory -Path $cpRunRoot | Out-Null
& npm.cmd run build -- --outDir $cpBuildDist
if ($LASTEXITCODE) { throw 'Isolated Vite build failed' }

function Invoke-CpHomeSuite {
    param([string]$Name, [int]$Port, [string]$Module, [string[]]$TestFiles,
          [string]$Grep = '', [string]$GrepInvert = '',
          [string]$Upcoming = '0', [string]$Completion = '0')
    if ($Port -eq 5000 -or (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) { throw 'Unsafe or occupied test port' }
    $cpCaseRoot = Join-Path $cpRunRoot $Name
    New-Item -ItemType Directory -Path $cpCaseRoot | Out-Null
    Copy-Item -LiteralPath $cpBuildDist -Destination $cpCaseRoot -Recurse
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:CP_TEST_MODE = '1'
    $env:CP_TEST_QBT_MODE = 'embedded'
    $env:CP_TEST_ROOT = $cpCaseRoot
    $env:CP_TEST_DIST_DIR = Join-Path $cpCaseRoot 'dist'
    $env:CP_PORT = [string]$Port
    $env:CP_E2E_PORT = [string]$Port
    $env:CP_DISCOVER_PAGING_E2E = $Upcoming
    $env:CP_DOWNLOAD_COMPLETION_E2E = $Completion
    $env:CP_CAPTURE_INGESTION_EVIDENCE = '0'
    foreach ($cpSeeder in @('tests.seed_iptv_e2e','tests.seed_movie_awards_e2e')) {
        & $cpPython -B -m $cpSeeder $cpCaseRoot
        if ($LASTEXITCODE) { throw "Fixture seed failed: $cpSeeder" }
    }
    $cpServerArgs = if ($Module -eq 'app') { @('-B','app.py') } else { @('-B','-m',$Module) }
    $cpServer = Start-Process -FilePath $cpPython -ArgumentList $cpServerArgs -WorkingDirectory $cpRepo -WindowStyle Hidden -RedirectStandardOutput (Join-Path $cpCaseRoot 'server.out.log') -RedirectStandardError (Join-Path $cpCaseRoot 'server.err.log') -PassThru
    try {
        $cpReady = $false
        $cpTimer = [Diagnostics.Stopwatch]::StartNew()
        while ($cpTimer.Elapsed.TotalSeconds -lt 30) {
            if ($cpServer.HasExited) { throw 'Fixture exited before readiness' }
            try {
                $cpResponse = Invoke-WebRequest "http://127.0.0.1:$Port/api/library/status" -UseBasicParsing -TimeoutSec 1
                if ($cpResponse.StatusCode -eq 200) { $cpReady = $true; break }
            } catch { Start-Sleep -Milliseconds 150 }
        }
        if (-not $cpReady) { throw 'Fixture readiness timeout' }
        $cpTestArgs = @('test') + $TestFiles + @('--workers=1',"--output=$cpCaseRoot\artifacts")
        if ($Grep) { $cpTestArgs += @('--grep',$Grep) }
        if ($GrepInvert) { $cpTestArgs += @('--grep-invert',$GrepInvert) }
        & (Join-Path $cpRepo 'node_modules\.bin\playwright.cmd') @cpTestArgs
        if ($LASTEXITCODE) { throw "Browser suite failed: $Name; evidence: $cpCaseRoot" }
    } finally {
        if (-not $cpServer.HasExited) { Stop-Process -Id $cpServer.Id -Force -ErrorAction SilentlyContinue }
    }
}

Invoke-CpHomeSuite -Name core -Port 15160 -Module app -TestFiles @('tests/e2e/home-dashboard-hybrid.spec.js','tests/e2e/following-card.spec.js','tests/e2e/scrollbar.spec.js','tests/e2e/continue-watching.spec.js','tests/e2e/following-refresh.spec.js') -GrepInvert 'real import publication'
Invoke-CpHomeSuite -Name home-smoke -Port 15161 -Module app -TestFiles @('tests/e2e/app-smoke.spec.js') -Grep 'Home|release watcher|Continue Watching|Available followed movies'
Invoke-CpHomeSuite -Name upcoming -Port 15162 -Module tests.discover_paging_server -TestFiles @('tests/e2e/upcoming-movies.spec.js') -Upcoming '1'
Invoke-CpHomeSuite -Name completion -Port 15163 -Module tests.download_completion_server -TestFiles @('tests/e2e/following-refresh.spec.js') -Grep 'real import publication' -Completion '1'

$env:CP_TEST_ROOT = Join-Path $cpRunRoot 'unit'
$env:CP_TEST_DIST_DIR = Join-Path $env:CP_TEST_ROOT 'dist'
$env:CP_DISCOVER_PAGING_E2E = '0'
$env:CP_DOWNLOAD_COMPLETION_E2E = '0'
New-Item -ItemType Directory -Path $env:CP_TEST_ROOT | Out-Null
$cpNodeTests = @(Get-ChildItem -LiteralPath tests -Filter '*.test.mjs' | ForEach-Object FullName)
& node --test @cpNodeTests
if ($LASTEXITCODE) { throw 'Node regression failure' }
& $cpPython -B -m unittest tests.test_workspace_layout_ui tests.test_continue_watching_ui tests.test_watched_watchlist_ui tests.test_unified_movie_card_ui tests.test_ai_control_ui tests.test_movie_follow_contract tests.test_user_curation_store tests.test_upcoming_discover
if ($LASTEXITCODE) { throw 'Python regression failure' }
& git diff --check
if ($LASTEXITCODE) { throw 'Diff whitespace failure; distinguish pre-existing failures' }
Write-Output "Evidence retained at $cpRunRoot"
```

All current specialized fixture modules run with reloader disabled; stop only the process this runner created. Tests must intercept external providers/actions or use their disposable fixture implementation; test mode blocks ordinary urllib provider requests. Preserve the native-scrollbar launch options in scrollbar.spec.js and use the same `ignoreDefaultArgs:['--hide-scrollbars']` for the new native CW scrollbar tests. Upcoming and real-completion cases require their own fixture/flags; a skipped test is not evidence they passed.

## Preparation results and execution gates

- Existing-source baseline: `node --test tests/home-trailer-model.test.mjs tests/homeMovies.test.mjs`: **4 passed, 0 failed**. `.venv\Scripts\python.exe -m unittest tests.test_workspace_layout_ui tests.test_continue_watching_ui tests.test_watched_watchlist_ui`: **11 passed, 0 failed**. These checks precede all future product edits; they do not prove the redesign or a full suite.
- API bootstrap smoke: app.py, tests.discover_paging_server and tests.download_completion_server each returned HTTP 200 on `/api/library/status` under distinct OS-temp roots and ports 15160/15161/15162 with embedded mode requested. All three test processes were stopped and all three ports verified closed. This validates module startup/readiness, not full fixture semantics, frontend compilation or browser suites. The final verification recipe also includes seeders/build/per-suite gates which must actually run in the implementing chat.
- Smoke cleanup diagnostic: the initial shell command returned exit code 1 after readiness succeeded, during the Stop-Process/Wait-Process cleanup sequence. A subsequent explicit listener check passed for all three ports. This is not counted as a fully green end-to-end runner run; the final recipe avoids that Wait-Process race and remains subject to execution after implementation.
- Measurement browser runs: old/current source at both widths, zero page errors after ensuring one shared React runtime. The slim-header sizing boxes did not overflow. Current toolbar at old proportions had zero heading overflow and the longest selected label fit. No production frontend rebuild, production restart, live scan, download or data change was performed.
- Preparation evidence: [summary](assets/2026-10-19-home-dashboard-hybrid/09-preparation-baseline.txt) and raw measurements above. Temporary probe/log directory: `C:\Users\dante\AppData\Local\Temp\cp-home-plan-083ad50bc571485eb48ce3e3a9d30137`; saved evidence in this repository remains authoritative if temp files disappear.
- Gate 1 in the future chat: inspect actual checkout/dirty changes/current process and bundle; confirm this spec's referenced owners still exist and snapshot pre-existing work. Refresh baseline if code drifted. No historical PID/bundle is proof of the new task's current app.
- Gate 2: obtain Dante's explicit implementation instruction for this plan, then modify the named owners and tests. No additional design decisions remain outstanding; escalate only a genuinely new product conflict/risk, not routine CSS measurement.
- Gate 3: complete isolated checks, actual compiled desktop screenshots and interaction QA; report exact results, skips, baseline failures and remaining contract differences. Only a separate authorized live rollout can activate the changes. No commit, push, restart, release or production data action follows automatically.
