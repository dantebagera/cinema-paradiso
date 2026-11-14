# Shared Reveal line desktop verification

2026-10-14: source implemented; isolated compiled desktop verified; live bundle unchanged.

Approved design: Reveal line, 2px visible ink, transparent track, no arrows, hidden at idle, CP gold on hover/focus/scroll. Native scrollbar area is 8px for dragging. Activity expires 900ms after the last scroll event; intentionally hidden card rails stay hidden.

## Environment

- Desktop checkout: master / be511f9 with preserved pre-existing dirty work.
- CP_TEST_MODE=1, CP_TEST_QBT_MODE=embedded.
- CP_TEST_ROOT=C:\Users\dante\AppData\Local\Temp\cp-scrollbar-e3361f5642d74c2d93aa9e947f7c6ea8.
- CP_TEST_DIST_DIR is that root's dist directory; test server port 15144. Production port 5000 and its data/config/bundle were unchanged. The isolated server was stopped afterward.
- New scrollbar tests launch Chromium without its default --hide-scrollbars argument to verify actual native paint and dragging.

## Commands and observed results

```powershell
npm.cmd run build -- --outDir "$env:CP_TEST_DIST_DIR"
# Passed, Vite 2.30 seconds. See isolated-build.log.

$env:CP_E2E_PORT='15144'
npx.cmd playwright test tests/e2e/scrollbar.spec.js tests/e2e/app-smoke.spec.js --grep 'scrollbar|release watcher|desktop sidebar|sidebar popups|Home without|Followed releases Sources|static CP surfaces|IPTV' --output '<isolated-root>/final-results'
# 13 passed in 22.4 seconds.

npx.cmd playwright test tests/e2e/scrollbar.spec.js --output '<isolated-root>/native-results'
# Four native-paint/drag tests passed in 7.2 seconds after enabling visible native paint.

node --test 'tests/*.test.mjs'
# 133 passed; no failures. See node-suite.log.

# With CP_TEST_MODE=1 and a separate OS-temp CP_TEST_ROOT:
.venv\Scripts\python.exe -m unittest tests.test_workspace_layout_ui tests.test_unified_movie_card_ui tests.test_iptv_ui tests.test_watched_watchlist_ui
# 47 passed; no failures.
```

The baseline's four new tests failed because native scrollbar paint/activity was absent. The first implementation's hover repaint failure was reproduced and corrected in the shared CSS owner; final checks passed without weakening the agreed behavior. A temporary fixture selector also needed a stable ID after its rail class was removed; production behavior was unaffected.

following-hover.png shows the actual compiled Following panel's 2px gold thumb, without arrows or visible track. following-idle.png shows the same scroller after activity expires, with the thumb hidden. Screenshots were inspected at native size.

No full Python or full browser-suite claim. Fallback browsers retain native thin widths, which were not visually verified. Production still serves index-ClMEnn3C.js and index-Cz-Bcnef.css; activating this change requires a separately authorized production frontend build.
