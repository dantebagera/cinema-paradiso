# Following card desktop verification

2026-10-14: approved source implemented and compiled desktop verified in isolation. Live frontend unchanged.

The card now owns the whole scrolling set. View all and its drawer are removed. The approved toolbar order is download, bell with total available count, scan, filtered count and filter. All/Available/Monitoring/Awaiting release reuse the existing release-status/date rule. Monitoring badges are gold, Awaiting badges muted gray and Available badges green. A transient Owned row remains in All until existing reconciliation removes it.

Download always sends all available followed movies, irrespective of filter, to the existing shared source-preview API. It opens SourceReviewDialog using backend defaults, retains blocked rows and quality/selection controls, and submits only on the existing explicit user action. Backend policy, jobs, persistence and live data were not changed.

## Isolation and commands

OS-temp root: C:\Users\dante\AppData\Local\Temp\cp-following-header-45e75fa15bcb4308be15a2070cec781f. CP_TEST_MODE=1, CP_TEST_QBT_MODE=embedded, isolated dist under that root, port 15145. Production remains on 5000. Provider network is blocked by CP test mode. Browser source-preview/submission fixtures capture requests without starting downloads.

```powershell
npm.cmd run build -- --outDir '<isolated-root>/dist'
# Passed, Vite 2.29s. See build.log.

$env:CP_E2E_PORT='15145'
npx.cmd playwright test tests/e2e/following-card.spec.js tests/e2e/scrollbar.spec.js tests/e2e/app-smoke.spec.js --grep 'Following filters|download previews|scan refreshes|empty filter|cancelled pending|failed source|scrollbar|native dragging|release watcher|Available followed|Home without|sidebar popups|multi.*source|source review|Sources' --output '<isolated-root>/complete-results'
# 16 passed, 22.2s.

node --test 'tests/*.test.mjs'
# 133 passed. See node.log.

# With CP_TEST_MODE=1, embedded mode and a separate OS-temp test root:
.venv\Scripts\python.exe -m unittest tests.test_library_action_ux tests.test_workspace_layout_ui tests.test_continue_watching_ui tests.test_unified_movie_card_ui tests.test_qbittorrent_api tests.test_user_curation_store
# 165 passed. See python-final.log.
```

Baseline browser regression failed on the absent filter. Initial verification also caught a loading-trigger focus race, corrected with frame/generation/visibility checks. A stale Python source assertion demanded the old three-row preview and removed drawer; it contradicted approved behavior even in the task's baseline snapshot. Manual-scan/reconciliation assertions remain, while real compiled browser coverage verifies the approved whole-list behavior.

Screenshots following-header.png, following-monitoring.png and following-awaiting.png were inspected at native size. Toolbar fit/control ordering is asserted at 1600px; existing aligned-height/full-list/source/navigation regression runs at 1920px. Native scrollbar tests retain actual paint and thumb dragging. Deferred previews are resolved and awaited while Home is hidden, then Back/Forward verifies no reopening.

These are relevant suites, not a claim of the full repository Python/browser suites. No production source preview, queue submission, catalog modification, restart, rebuild, commit or push was performed. A normal run.bat launch rebuilds the frontend before CP starts.
