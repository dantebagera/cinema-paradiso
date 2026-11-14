# Global TV card density verification

Date: 2026-10-23. Scope: source implementation and disposable compiled desktop UI, not live activation.

## Observed result

- Library, Discover and Lists render the same shared TV card. Offline ownership is an inline green percentage after date/season/episode metadata, hidden for zero available episodes. Incomplete episode coverage with downloads explicitly says `Offline % unknown`.
- The obsolete library/download explanation is removed from the preview service's action reason. Detailed offline/watched counts and percentages appear in expanded local-series metadata, including honest unknown totals/percentages. Genuine playback and identity-review reasons remain.
- Returning Series is red; Ended is green, using one mapping for standard and expanded status chips. Other statuses retain their neutral treatment.
- Dense standard cards do not gain text-driven height below the poster in the checked fixtures. Expanded overview and actions occupy the full width below the poster/metadata row, so even a very long overview cannot leave a large unused poster column.
- Existing poster aspect/framing, actions and TV/Movie navigation checks pass.

## Environment and action boundaries

Checkout: `C:\Users\dante\Desktop\cinema paradiso`, branch `master`, HEAD `be511f9`. The checkout was extensively dirty before this task; task source changes are restricted to `TVWorkspace.jsx`, `tv.css`, shared `movieCard.css`, and `services/tv_metadata.py`. Exact pre-task copies were used for review. New files are the density E2E suite, plan and this evidence folder.

Each browser run uses a unique OS-temp `CP_TEST_ROOT`, `CP_TEST_MODE=1`, disposable port 5117 and `CP_TEST_DIST_DIR=<temporary root>/dist`. `tests.native_tv_server` forces embedded mode before importing the app and supplies synthetic media/provider fixtures. Only disposable test clients are used. Existing test helpers may queue synthetic fixture records, never real transfers.

No production config/catalog change, download, restart, deployment, commit or push. Desktop `dist` was not rebuilt. Live port 5000 was not used for test traffic or process control. No mobile or hardware/performance testing.

## Commands and results

```powershell
$env:CP_TV_E2E='1'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/run_playwright_e2e.ps1 tests/e2e/tv-card-density.spec.js tests/e2e/tv-parity.spec.js tests/e2e/tv-expanded-parity.spec.js tests/e2e/native-tv.spec.js tests/e2e/movie-scroll-return.spec.js --max-failures=4
# 58 passed (1.2 minutes), including successful isolated production build.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/run_playwright_e2e.ps1 tests/e2e/tv-card-density.spec.js
# Final version: 16 passed (9.3 seconds), including expanded unknown coverage.

node --test tests/tv_card_enrichment.test.mjs tests/cardGrid.test.mjs
# 6 passed.

$env:CP_TEST_MODE='1'
$env:CP_TEST_ROOT=Join-Path $env:TEMP ('cp-tv-card-python-'+[guid]::NewGuid().ToString('N'))
$env:CP_TEST_QBT_MODE='embedded'
.venv/Scripts/python.exe -m unittest tests.test_tv_vertical_slice tests.test_unified_movie_card_ui tests.test_full_row_card_grids_ui
# 55 run: 54 passed, 1 unrelated Home source expectation failed.
```

The Python failure is `tests.test_full_row_card_grids_ui.FullRowCardGridUiTests.test_home_scrolling_rails_share_layout_and_group_trailers`: it expects `/api/tmdb/discover?list=upcoming&page=1&page_size=100` in `src/App.jsx`. That test reads the untouched Home/App source, so its inputs are unchanged by this task. It was not weakened or hidden. This is not a green full Python suite. Full unrelated backend and entire browser suites were not run.

## Layout evidence

At desktop widths 1366 and 1920, tests cover Library/Discover/Lists, zero availability, stale percentages, unknown coverage, status tones, representative dense metadata and very long expanded text. Standard poster gap is at most the existing 4px structural allowance after normal padding/border is excluded. Expanded text begins below the poster within the normal row gap (at most 28px asserted; layout uses 20px), spans both columns, and the image retains a 1.5 height/width ratio.

- [Dense standard TV card, 1366px](dense-1366.png)
- [Dense standard TV card, 1920px](dense-1920.png)
- [Discover cards, 1366px](discover-1366.png)
- [Expanded preview with a real poster, 1366px](expanded-preview-1366.png)
- [Expanded long overview, 1366px](expanded-1366.png)
- [Expanded long overview, 1920px](expanded-1920.png)

The dense-card fixture deliberately exercises five genres, three countries, quality, a long title and returning status. It has no poster URL and therefore shows the existing shared fallback. The expanded-preview image demonstrates actual poster framing. Historical parity images overwritten by existing tests were restored to their exact pre-run versions; current evidence is kept here separately.

Independent review was read-only and found no actionable regressions against the exact four-file pre-task baseline. There are no known differences from the approved visual behavior in the checked scenarios. Live behavior and arbitrary malformed/unbounded metadata are not claimed verified.
