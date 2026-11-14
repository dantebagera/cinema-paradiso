# Home header: slim layout and film-reel projector

**Status:** Implemented and isolated desktop verified, 2026-10-19. Dante approved the final long-beam B mockup with "ok thats it go", then specified "implementin main". Source changes and isolated desktop verification only; not deployed live.

## Problem and decision

- **Now:** Home's 190px header stacks Home, the kicker, slogan and a three-line description; the description overemphasizes Plex. Its modern projector and short/bent beam do not match the selected direction.
- **Approved result:** Compact Home/kicker row, unchanged slogan, exact new line "A richer movie library. More to discover. AI to guide you. Ready to stream.", vintage twin-reel projector rendered in restrained gold engraving, and a long golden beam fading left behind readable text.
- **Reference:** `C:/Users/dante/.codex/generated_images/01a155a1-9fbd-7f33-93f3-fb33f25e2a31/exec-103e0489-b82e-4e69-8ccf-fe46e20d9a36.png`.
- **Confirmed:** Existing Home owner and styles; shared original artwork also serves Style Guide. No backend changes required.
- **Open decisions:** None affecting implementation. Generated artwork must be visually checked against the reference before use.
- **Scope:** Home banner only. Preserve all dashboard work, cards, controls, navigation, loading/error behavior, original Style Guide artwork and mobile-specific rules. No live build/restart, data/config changes, downloads, commits or publishing.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior | Affected surface | Proposed behavior | Changes contract? | Dante's decision |
| --- | --- | --- | --- | --- | --- |
| Home header; final mockup in this chat | Slim banner with B projector and extended ray | Home | Implement selected design and exact copy | Explicitly approved visual/copy replacement | "ok thats it go", 2026-10-19 |
| Existing Home hybrid dashboard plan | All other layout, controls and interactions | Home cards/rails | Preserve; only header height changes | No | Existing scope preserved |
| Original shared artwork | Style Guide retains existing hero image | Style Guide | Use a separate Home asset, retain original | No | Unchanged |

The previous 190px measurement in the hybrid dashboard geometry test described the prior approved header. Update only that header expectation to this newly approved design; preserve every other assertion.

## Current design and ownership

| Responsibility | Authoritative owner | Entry/callers | Preserve | Retirement |
| --- | --- | --- | --- | --- |
| Home banner content | `src/features/home/HomeWorkspace.jsx` | App Home workspace | Heading/section accessible name, existing dashboard below | Replace only obsolete header paragraph/import |
| Home geometry/type | `src/features/home/home.css` | Existing Home import | Other dashboard rules and desktop breakpoints | Replace existing header declarations |
| Banner artwork/overlay | `.hero-panel`, `.home-hero-art` now consolidated in `src/features/home/home.css` | Home only | Decorative/noninteractive image semantics | Retire former header-specific rules in `src/styles.css` rather than layer another override |
| Original artwork | `src/assets/header.png` | Style Guide and former Home | Style Guide | Keep because still used |

Baseline: Desktop checkout `C:/Users/dante/Desktop/cinema paradiso`, branch `master`, commit `be511f98846a67a182e5b371ad087938e9344362`, extensive existing tracked/untracked work including Home files. Dante explicitly selected this checkout. Task-specific baseline copies/status are in `C:/Users/dante/AppData/Local/Temp/cp-home-header-e736a4bcdb6b4abeba9d89f59813814d/baseline`.

Live baseline: port 5000 belongs to Python PID 39204 (launcher PID 33000), `app.py`; repository config/data owners are `config.json` and `data`. Served index matches repository `dist/index.html`, JS `index-Df2COV8Y.js`, CSS `index-REAV18mQ.css`. These are separate from the source and isolated build. Do not replace live dist.

## Exact behavior contract

### Frontend

- Reuse the current hero section, copy block and decorative image. Add only an inline title/kicker wrapper; no new shared component needed for this static Home-only composition.
- Banner minimum height 156px (34px below prior 190px), padding 20px 32px, vertically centered, existing panel border/radius. Let text grow rather than clip with fixed height.
- Home title 24px/1.2; gold kicker retains 10.88px/1.2, inline gap 12px. Main slogan 32px/1.12 with 8px top gap. New supporting line 14px/1.5 with 8px top gap. Copy max-width 900px, bounded to keep approximately 220px free on the right for the projector at target desktop widths.
- New decorative artwork contains no text, border or baked UI. Vintage twin reels stay fully visible in the central banner band, on the right, with long soft light reaching left. Use existing absolute image layer, cover/right-center, maximum rendered width 1360px; softly fade the left image edge with a CSS mask so its boundary cannot create a vertical seam on wide screens. Remove the opaque old overlay that would erase the approved long ray, retaining a gentle readability gradient.
- Body copy and headings remain real selectable/accessible HTML. Missing artwork cannot remove text or interactions.
- No buttons or additional behavior. Existing Home/Library/Discover navigation and browser Back/Forward continue to work.

### Backend

No request, response, persistence, network, concurrency or migration changes. Test backend uses `CP_TEST_MODE=1`, a unique OS-temp `CP_TEST_ROOT`, `CP_TEST_DIST_DIR` inside it and non-production port 5129; external provider requests are blocked. Do not use the existing wrapper that forces system qBittorrent mode. Import fixture server without normal startup workers.

## Implementation sequence

1. Record baseline; run existing Home checks against isolated compiled baseline. Add a browser geometry/content/accessibility regression and observe failure on old header.
2. Generate clean artwork from approved mockup using imagegen, inspect, copy into `src/assets/home-film-projector.png`. Update only existing header JSX/style owners and the old 190px test measurement.
3. Build to isolated temp dist; run focused header and broader Home suites plus Node tests and relevant Python UI checks. Inspect desktop screenshots at 1280/1600/1920; test navigation and missing-artwork resilience. Review only task deltas against baseline, record evidence/results here.

## Acceptance matrix

| Scenario | Action | Exact result | Evidence |
| --- | --- | --- | --- |
| Desktop at 1280, 1600, 1920 | Open Home | 156px header, inline title/kicker, readable slogan/body without clipping or projector overlap | Browser geometry + screenshots |
| Approved copy | Open Home | Exact supporting line and original slogan; no Plex in banner | Browser text assertions |
| New artwork | Load asset | Decoded image, twin reels and long ray visible | Image check + rendered screenshot |
| Data empty/loading/error | Header renders while independent feeds change | Banner copy and size stable | Existing Home state tests + header tests |
| Navigation | Home to Library/Discover, Back/Forward | Banner returns correctly, shared surfaces unchanged | Browser regression |
| Missing artwork | Abort image request | Accessible heading/body remain visible and unclipped | Browser regression |
| Other Home panels | Run existing dashboard suite | Same card geometry, controls and interactions | Existing suite with header-height expectation updated |
| Style Guide | Open page | Original hero artwork still used | Browser asset check |

## Verification and rollout

- Baseline and test results recorded below as commands finish. Build only into the task's OS-temp `dist`; preserve live bundle hash.
- Focused: Playwright `home-header.spec.js`. Broader: `home-dashboard-hybrid.spec.js`, `following-card.spec.js`, relevant Home/scrollbar tests; enumerate Node `.test.mjs` files for `node --test`; isolated relevant Python UI modules.
- Compiled UI: actual Chromium screenshots and measured desktop geometry, real built CSS/assets, no production API use.
- Completion is source-only and isolated-tested. Live activation requires separate approval. No commit/push.

## Execution evidence

- Baseline source and live dist hashes saved before changes. Plan is the execution record for this small task; no separate implementation subsystem or parallel agent work.
- Baseline isolated Vite build passed; existing dashboard geometry passed 5/5 widths (1280, 1366, 1440, 1600, 1920).
- New header browser regression first failed on missing approved copy. First compiled implementation passed all 6 header tests. Visual review found an artwork edge and tight reel clearance at 1920; an added clearance check failed with 0.2px versus required 4px. Limiting image width to 1360px and fading its left edge corrected both without modifying the artwork or UI text.
- All 133 enumerated Node tests passed. All 50 focused Python UI/layout/player-theme checks passed in isolated test mode. Production build passed into OS-temp dist only.
- Initial broader browser run: 42 passed, 1 failed. Failure: existing native-scrollbar drag test at `home-dashboard-hybrid.spec.js:119`. Unchanged baseline bundle passed. Diagnostic measurements proved the shorter header exposed a test target bug: the drag was attempted at y=1005.421875 in a 1000px-high browser viewport, outside the window. Playwright's `scrollIntoViewIfNeeded` did not reveal the native scrollbar. Corrected the test to center the actual track before dragging and assert the target lies within the viewport; preserved the exact real native drag and `scrollLeft > 50` assertion. Focused corrected test passes on both unchanged baseline and new header. No production scrolling code changed and no assertion was weakened.
- Independent read-only review found no actionable issues in the source delta, screenshots or test correction. Other existing dirty work was excluded from the review.
- Artwork generated with the built-in imagegen tool, then copied to `src/assets/home-film-projector.png` (763,944 bytes). Full asset prompt and provenance: `docs/verification/home-header/artwork-prompt.txt`. Approved mockup and actual rendered desktop captures are saved alongside it.
- Final complete relevant browser rerun: **43/43 passed**, zero failures/skips, 44.9s; includes all six new header tests, full dashboard hybrid suite, Following card, shared scrollbars and Continue Watching. Baseline and updated header both pass the corrected native-drag test. Node **133/133**, Python focused checks **50/50**, isolated Vite build passed. No remaining difference from the approved desktop header contract was observed.
- Final live bundle SHA-256 remained `43DC73161376ED4EC3F49788E20AC59FF8C81FF7794959397AE07E2E11159CE7`; production port5000 remained owned by PID39204. Original Style Guide image hash unchanged. No live activation/restart, data/config modification, commit or push.
