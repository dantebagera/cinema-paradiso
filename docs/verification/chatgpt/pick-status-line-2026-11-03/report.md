# Pick My Movie status line verification — 2026-11-03

Implemented and tested in isolation. Production has not been restarted or its frontend replaced.

## Result

F1 uses the existing AIJobStatus owner in inline mode. It renders a plain sentence with no card, background, border, heading, model, request budget, internal error or action row. The existing main form button supplies Stop while running, Continue for an unchanged resumable request, Ask AI for a new request, and the existing AI Control handoff where applicable. New conversation is in the form.

Stages reflect backend events: preparing, connecting, receiving the response, and completing movie matching. Hints live in memory, are bound to the active run, and do not write SQLite or advance revisions. Restored/foreign-process jobs with no live hint display generic working text. Final validated results remain the only source of cards.

The screenshot failure is now: “The request requirements changed. 18 of 50 movies ready. Start a new request.” Starting again uses a fresh session and retains the requested target. This improves presentation/recovery; it does not establish or repair the cause of the historical failure.

## Final verification

- **91 Python tests passed**, 61.872 seconds: `tests.test_ai_jobs`, `tests.test_chatgpt_transport`, `tests.test_chatgpt_recommendations`, `tests.test_ai_routes`, `tests.test_ai_feature_matrix`, `tests.test_ai_provider_preservation`, `tests.test_chatgpt_agent`, `tests.test_chatgpt_matching`, `tests.test_chatgpt_iptv`, `tests.test_chatgpt_recommendation_stream`.
- **4 JavaScript tests passed**: `node --test tests/ai_pick_status.test.mjs tests/ai_provider_client.test.mjs`.
- **14 compiled desktop tests passed**, approximately one minute: `tools/run_playwright_e2e.ps1 -AIProviderOffline tests/e2e/ai-provider.spec.js`. Fresh Vite build succeeded. Desktop widths 1280 and 1600; no mobile work.
- Unique OS-temp roots, CP_TEST_MODE=1, embedded fixture qBittorrent, synthetic accounts/movies and offline transport. No real inference calls used.
- Desktop source root: `C:/Users/dante/AppData/Local/Temp/cinema-paradiso-playwright-0638ba0bac84489fa04d5b79f30d9795`.
- Independent read-only review found two issues, both corrected: browser validation blocking Stop after an invalid count edit, and clearing an explicit count incorrectly offering Continue. Regression coverage verifies cancellation with count `1.5`, clearing 500 to blank, untouched restored blanks, and fresh sessions after invalidated scope/skill.

Tests verify backend phase and zero accepted cards at each held response stage, then the rendered matching card count after completion. They assert a status height under 40 px, no action/link/header in the line, zero border and transparent background. Saved-18 failure rendering uses real fixture cards and an explicitly simulated restored failure snapshot; a subsequent fresh backend request returns 50 verified cards.

Preservation checks cover 120-result paging/restoration, exact large targets and budget pause/Continue, explicit cancellation, manual provider switching, Settings, AI Control Movie/TV lists, Smart Match, IPTV review/apply boundaries, account isolation, and frozen Ollama prompts/wire behavior. No approved business contract was weakened.

## Earlier runs and limits

- Initial red tests failed on missing runtime phase support/status formatter and absent transport phase events, as expected before implementation.
- One desktop assertion initially matched “500 movies ready” inside “480 of 500 movies ready”; corrected to exact final-text equality, preserving the same-job completion assertion.
- A later concurrent backend/desktop run timed out at the existing 15-second limit while the synthetic 500-target job was still progressing (416 accepted). Deadline and product logic were not changed. The final complete desktop run was sequential and passed all 14 scenarios.
- These checks verify UI behavior and preservation, not a new real-provider latency benchmark.

## Source versus live

Production remains PID 16180 on port 5000. Repository `dist/index.html` remains SHA256 `2a0dcb446ffccfa403c998c11be3437bc25947050aa094aaec84a843c30f3916`. This task did not restart production, copy a build into production dist, or deliberately edit production configuration/data.

Production config hash changed during the session (observed mtime 15:59:48 local); its source was not established. Isolated tests use their own config files under OS-temp roots. No production configuration was restored or overwritten, and no claim that live config was unchanged is made.

## Screenshots

- [Receiving suggestions](pick-status-retrieving.png)
- [Completed](pick-status-completed.png)
- [Restored failure with saved results](pick-status-saved-failure.png)
