# Compact Pick My Movie controls — 2026-11-03

Implemented and verified in a disposable compiled desktop app. Not activated in production.

## Changes

- Prompt starts at three lines (approximately91px rather than the previous150px minimum). Longer text scrolls vertically; the existing drag-to-resize handle still expands it.
- Count, Ask AI/Stop/Continue and New conversation share one action row. The count keeps its exact-number validation and accessible label; the input shows the existing default as its placeholder.
- Removed the normal provider/model/AI Settings strip, long count label and count-help paragraph. A concise Settings link appears only if configuration cannot load or the provider is not ready, so a disabled request is still explained.
- Modified the authoritative form/CSS; removed the unused ai-count-field rule. Other screens retain their shared provider component. No backend, prompt, target/default, session, publication, review or mobile-specific changes.

## Verification

- **16/16 compiled desktop tests passed in55.9s** with a fresh successful Vite build: `tools/run_playwright_e2e.ps1 -AIProviderOffline tests/e2e/ai-provider.spec.js`.
- **4/4 JavaScript tests passed**: `node --test tests/ai_pick_status.test.mjs tests/ai_provider_client.test.mjs`.
- `git diff --check` passed for changed tracked source and desktop tests.
- Before implementation, the new layout test failed because the unwanted provider strip still existed. After implementation, both new desktop scenarios passed at1600px and1280px.
- New scenarios assert prompt height under100px, count/button vertical alignment within3px, natural button width, removal of strip/help text, overflowing long text without box growth, and actual mouse dragging to enlarge the textarea. A real fixture submission with count3 produces backend target3, accepted count3, status3 and three rendered cards.
- Existing scenarios verify120-result paging/restoration at both widths, saved failure recovery, truthful stages, exact-target Continue, cancellation despite invalid input, provider switching, account isolation, Settings, AI Control Movie/TV, Smart Match, and IPTV review boundaries.

Test data and bundle root: `C:/Users/dante/AppData/Local/Temp/cinema-paradiso-playwright-8f80f3cfc793470fb73ea3730db00f00`. Offline synthetic inference; embedded test qBittorrent. No real provider requests or live catalogue writes.

## Visual proof and activation boundary

Inspected the1280px compiled screenshot: three-line prompt, compact Count/Ask AI row and no provider strip/help block. Screenshots:

- [1280px desktop](pick-compact-1280.png)
- [1600px desktop](pick-compact-1600.png)

Production remains separately running on port5000/PID16180; no restart or dist replacement performed. Production config hash remained c0e95344829e363e104e758b89b71a6e3c17bf9972afe8a19863f8c20a8b7e7c; dist/index.html remained2a0dcb446ffccfa403c998c11be3437bc25947050aa094aaec84a843c30f3916 across this amendment. All requested layout changes are present in the tested source; the running old build will retain its old layout until separately activated.
