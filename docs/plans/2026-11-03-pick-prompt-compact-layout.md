# Compact Pick My Movie prompt controls

**Status:** Implemented and verified in isolation, 2026-11-03; not live activated. Dante requested a three-line prompt box with scrolling/manual expansion, recommendation count on the Ask AI row, and removal of the provider/info section in screenshot 2. Evidence: docs/verification/chatgpt/pick-compact-layout-2026-11-03/report.md.

## Problem and decision

The existing Discover prompt form uses five rows plus a 150px minimum, a full-width provider/model/Settings strip, a separate count label/input/help block, and a full-width submit button. This consumes excessive desktop space.

Implement a three-line textarea with vertical scrolling and the existing manual resize handle. Move the count input and Ask AI control onto a single compact row. Remove the provider/model strip, count heading and explanatory paragraph. Keep the count's accessible label, numeric validation and default placeholder; show a concise visible “Count” label inline. Place the existing New conversation control on the same row when applicable. Preserve actionable setup failure feedback only when the provider is not ready. No open product decisions: the count is retained because Dante explicitly requested moving it.

Scope is this desktop form only. No backend behavior, prompts, default counts, provider switching, saved jobs, Stop/Continue, Settings screen, other AI layouts or mobile-specific code changes. No live activation/restart/production build is included.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| Prompt size/layout | Smaller three-line default with scroll and resizing | Discover Pick form | Replace oversized layout | Requested presentation change | Explicit latest request |
| Count selection | Exact positive whole-number override, blank uses existing default logic | GPT F1 | Same input/value/validation on action row | No | Preserve |
| Saved request actions/status | Stop, explicit Continue, New conversation, readable one-line status | GPT F1 | Same controls/actions; compact form placement | No | Preserve |
| Other providers/features | Existing inference/wire/review behavior | Ollama/F2-F5 | No backend/shared-status changes | No | Preserve |

## Current design and ownership

| Responsibility | Current authoritative file/component/service | Entry point and callers | Behavior to preserve | Competing or obsolete paths |
| --- | --- | --- | --- | --- |
| Prompt/action markup | DiscoverWorkspace.jsx | Pick My Movie form | Submit shortcuts, counts, action selection | Remove F1 AIProviderStatus invocation and obsolete help block |
| Prompt geometry | src/styles.css, .pick-prompt-panel textarea | Same form for GPT/Ollama | CP typography/padding, resize handle | Replace 150px minimum rather than add override |
| Count layout | Existing ai-count-field in ai.css | F1 only | Accessible input and numeric text semantics | Retire unused block-specific rule after moving to common form layout |

Baseline: master be511f98846a67a182e5b371ad087938e9344362, extensively dirty checkout; relevant source snapshots in OS-temp cp-pick-layout-baseline-7534473decb84744bd3e8d5f99a5f8d2. Live port5000/PID16180, served dist index hash 2a0dcb446ffccfa403c998c11be3437bc25947050aa094aaec84a843c30f3916; production config hash c0e95344829e363e104e758b89b71a6e3c17bf9972afe8a19863f8c20a8b7e7c. Existing screenshot is older live layout; previous status changes are source-only.

## Exact behavior contract

### Frontend

Reuse the existing form, textarea, count input and CP btn controls. Set rows=3; minimum height equals three text line-heights plus existing 12px top/bottom padding and border. No fixed height blocks user resize; overflow-y auto, resize vertical retained. The action row uses flex alignment, a narrow count input and natural-width buttons. No full-width provider strip or explanatory count block. Count remains accessible under “Recommendation count for this request”. The field uses the same CP input border/background/typography as adjacent controls. Preserve heading/description and existing result/status area; no unrelated design changes.

### Backend

No changes. The same recommendation route receives the same prompt/count/session fields, and returns the same persisted job/results.

## Implementation sequence

1. Add desktop geometry/scroll/resize and real submission assertions to the existing offline AI fixture suite.
2. Modify the current form and authoritative CSS; remove unused import/count block rule.
3. Build a disposable bundle and run focused/current AI desktop regression checks; inspect screenshots at 1280/1600. Report source-only status.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| Empty GPT form | Expand controls | Three-line textarea under100px, count and Ask AI share vertical center, no provider strip/help paragraph | F1 desktop | Geometry tests at1280/1600 |
| Long prompt | Enter many lines | Text scrolls without increasing default box height | Textarea | scrollHeight/clientHeight assertion |
| More editing room needed | Drag resize handle | Textarea becomes taller | Textarea | Real desktop mouse drag |
| Count=3 | Submit request | Backend target3, rendered status/cards3 | Full F1 path | Real offline fixture |
| Blank/invalid/large counts and saved requests | Existing actions | Unchanged validations and Stop/Continue/session behavior | F1 | Existing suite |
| Provider not ready | Load form | Submit remains disabled with concise actionable feedback | F1 | Existing readiness behavior retained |
| Other AI surfaces | Existing workflows | Unchanged layout/review behavior | Shared callers | Existing desktop suite |

## Verification and rollout

Focused and broader checks use tools/run_playwright_e2e.ps1 -AIProviderOffline tests/e2e/ai-provider.spec.js, unique OS-temp root and disposable Vite dist, no real inference. Node status/client tests cover unchanged action selection/exact count semantics. No backend suite expansion for markup-only edits. Production bundle/config hashes are observed separately; no restart or production writes. Report actual counts and inspect desktop screenshots before completion.
