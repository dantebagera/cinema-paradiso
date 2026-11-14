# Pick My Movie plain-language status

**Status:** Implemented and verified in isolation, 2026-11-03; not live activated. Dante requested removing the cryptic section and replacing it with one status line; earlier instruction authorizes continued coding and tests without repeated approval. Results: `docs/verification/chatgpt/pick-status-line-2026-11-03/report.md`.

## Problem and decision

- Current F1 `AIJobStatus` shows model, budget, internal message, and four actions in a large card. The screenshot's `scope changed during operation` does not explain recovery.
- Show one text line with accurate progress, a readable outcome, and saved-result counts. Reuse the main Ask AI button for Stop while running and Continue for resumable requests. Move New conversation into the prompt form. No permanent action row in the status.
- Confirmed: current API only distinguishes queued/running, so precise stages require runtime progress hints. Unknown: historical live job failure cause; this change does not claim to repair it.
- Scope: F1 desktop presentation and truthful progress reporting. Other feature layouts, Ollama, provider choice, inference limits, target counts, matching and publication remain unchanged. Production restart/build activation, data/config edits, commits, and releases are separate.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| User's status request | One readable status line | Pick My Movie GPT | Replace card and internal diagnostics | Yes, explicitly requested presentation | One-line status requested 2026-11-03 |
| Existing saved progress and explicit continuation | No automatic resume or provider switch; exact positive targets and saved cards persist | F1 | Move actions, preserve service behavior | No | Preserved |
| Independent AI features and Ollama | Separate prompts, wire formats, matching and review controls | F2-F5/Ollama | Existing full status panel unchanged | No | Preserved |

## Current design and ownership

| Responsibility | Current authoritative file/component/service | Entry point and callers | Behavior to preserve | Competing or obsolete paths |
| --- | --- | --- | --- | --- |
| Job status | AIJobStatus.jsx | Discover, AI Control, IPTV | Full panel outside F1 | Remove redundant F1 loading/model/error display |
| Prompt submission | DiscoverWorkspace.jsx | Pick My Movie form | Follow-ups, count validation, cancellation, resume, handoff | Existing disabled main button |
| Job state | services/ai_jobs.py | Shared job API | Durable state, revisions, budgets, cancellation | None |
| Response stages | chatgpt_transport.py / chatgpt_recommendations.py | Transport and verified matching | Terminal validation before publication | None |

Checkout master at be511f98846a67a182e5b371ad087938e9344362; extensively dirty tracked/untracked work predates this amendment. Preserve it. Production process/bundle are separate from source and will not be restarted or replaced. Tests use disposable OS-temp data and compiled bundles.

## Exact behavior contract

### Frontend

Extend existing AIJobStatus with inline mode. At the existing F1 status position render a small spinner while running and one plain sentence; no card background, heading, model, request budget, raw error or buttons. Use CP inline status spacing/color. Outcomes show exact counts. Unknown stages use generic wording instead of invented timing. Retain accessible region and live status/alert.

Main form button: Ask AI normally; Stop for active job; Continue for unchanged/restored resumable request; Open in AI Control for its existing handoff. Editing the prompt/count starts a new request. Invalidated skill/scope requires a fresh request, not continuation of invalid context. New conversation stays available in the form outside active runs. Keep failed-provider choice manual. Preserve Ollama form/result messages.

### Backend

Optional `progress_phase` in job snapshots. Runtime-only entry per active run, guarded by a lock and run identity; updates do not write SQLite or change revisions. Preparing at run start, connecting at transport start/retry, retrieving on first response bytes, matching after final response validation. Missing/foreign-process entries return no stage. Terminal/cancel/disconnect paths discard hints. Stale callbacks cannot change a later run. No migration, request payload, retry or inference-budget changes.

## Implementation sequence

1. Add regression tests for runtime phase lifecycle and transport events, then implement existing owners.
2. Add a pure F1 status/action formatter, inline variant, and form actions; remove duplicate F1 messages.
3. Exercise real offline fixture path in compiled desktop UI, plus shared backend and Ollama preservation checks. Inspect screenshots. Record source-only result.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| Motivating scope failure with 18 cards | Restore | Friendly stopped message with saved count; new request possible; no raw code or budget | F1 | Formatter + compiled UI |
| Queued/running | Submit | Preparing/connecting/getting suggestions/checking matches reflects actual events | Transport/store/UI | Unit + fixture desktop |
| Completed | Receive final cards | Count ready, no status buttons or large panel | F1 | Compiled paging tests |
| Budget pause/partial/interruption | Continue | Same job/target and saved results, explicit action only | F1/store | Existing budget desktop test |
| Running | Stop | Cancel current run; no future work or automatic resume | F1 | Desktop cancellation |
| Provider failure | Rate limit | Friendly visible failure, provider unchanged | F1 | Desktop failure test |
| Restored unknown phase | Poll | Generic working message, never fabricated phase | Shared store/formatter | Unit |
| Stale run callback | Resume later run | Old callback ignored | Store | Unit |
| F2-F5 and Ollama | Existing actions | Existing panel, prompts and contracts preserved | Shared callers | Relevant suites + full AI desktop file |

## Verification and rollout

- Baseline: existing source implements large panel shown in screenshot. No new baseline failure asserted.
- Focused: node status/client tests; isolated Python job/transport/recommendation tests. Unique CP_TEST_ROOT, CP_TEST_MODE=1, embedded test qBittorrent.
- Broader: AI routes, feature matrix, provider preservation, shared suites.
- Compiled UI: offline Playwright wrapper builds fresh temp dist; desktop widths 1280/1600 only. Verify status geometry/actions and actual backend result counts.
- Live: no restart or served-dist mutation in this amendment. No live claim.
- Report counts, failures, screenshot evidence and contract differences. No known approved business contract changes.
