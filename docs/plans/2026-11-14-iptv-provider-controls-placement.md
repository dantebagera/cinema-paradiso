# IPTV provider controls placement

**Status:** Implemented and isolated-verified. Approved by Dante with “go”, 2026-11-14, following the explicit layout proposal. Not installed in live CP.

## Problem and decision

Remove the IPTV title, Provider television subtitle, update timestamp and header space. Move the existing provider selector and sync button below IPTV sections, right-aligned beneath My Lists. Desktop only. No open product decisions; preserve provider selection and sync behavior.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior | Surface | Proposed behavior | Changes contract? | Decision |
| --- | --- | --- | --- | --- | --- |
| Dante's screenshots and approved proposal | Remove header; controls below tabs | IPTV workspace | Exact requested placement | Explicit requested visual change | “go” |
| Shared UI reuse rule | Shared Select and Button own visuals | Provider controls | Move existing instances | No | Preserve |
| Provider and sync ownership | Current callbacks and states | IPTV | Unchanged | No | Preserve |

## Current design and ownership

`IPTVWorkspace.jsx` owns sections, provider selection, sync callbacks and the removable header. `iptv.css` owns placement. `IPTVMaintenance.jsx` also uses `.iptv-header-status`, so retain that shared layout and scope the new right alignment to a workspace control-row class. Remove only the unused header styles and timestamp formatter.

Baseline: desktop checkout, master `117526b`, 527 dirty/untracked entries before this change; preserve all unrelated work. Port 5000 PID 4892 serves `index-CD1fO69d.js` (reviewed shared-UI build). Test against isolated data and a separate compiled bundle; no catalog changes or app restart.

## Exact behavior contract

Reuse `SectionTabs`, `SectionTab`, `Select` and `Button size="icon"`. Tabs become the first content row; provider controls follow at the existing workspace section gap, right-aligned, selector before sync. Preserve no-provider message, configured-only sync visibility, busy spinner and disabled state, errors and sync banner. Maintenance is unchanged. Backend and persistence are unchanged.

## Implementation sequence

1. Move existing controls after tabs; remove header and unused formatter/styles.
2. Add only flex-end placement for the new row.
3. Check reuse gate via isolated build and one desktop regression covering geometry, provider switching and mocked sync. No broad suites for this layout edit.

## Acceptance matrix

| Scenario | Expected result | Check |
| --- | --- | --- |
| Populated IPTV | No header; controls below tabs at right edge | Desktop DOM and bounding boxes |
| Provider switch | Existing selection updates | Isolated fixture |
| Sync | Existing callback still sends selected provider's request | Intercepted request; no external sync |
| Missing provider / busy | Existing branches preserved | Diff review |
| Maintenance | Shared styles unaffected | Scoped CSS and diff review |

## Verification and rollout

Build into OS temp with the standard isolated Playwright runner; preserve installed dist. Capture rendered desktop evidence. Activation of this newly changed bundle is separate from the previous bundle installation authorization. Report source/tested/live status honestly. No commits, pushes or restarts.


## Results

- Shared UI reuse gate and production build passed.
- Focused compiled desktop test: 1 passed (1.9s), including header removal, below-tabs/right-edge geometry, provider switching and intercepted sync request.
- Initial test incorrectly asserted no nested header anywhere in the workspace, catching the existing Recent IPTV section header. Corrected the assertion to the direct workspace header; product code did not change for this correction.
- Visually inspected [desktop screenshot](../verification/iptv-provider-controls-2026-11-14/desktop.png).
- Candidate: `C:/Users/dante/AppData/Local/Temp/cinema-paradiso-playwright-17fa49bd4fa0452a96409085812c209a/dist`, entry `index-qATvgm0U.js`, IPTV stylesheet `iptv-Dy3U6Pgv.css`.
- Temporary test server stopped. Live CP remains on `index-CD1fO69d.js`. No downloads, live sync, app restart, commit or push.
- Contract comparison: requested layout implemented; shared controls and callbacks preserved; Maintenance remains unchanged. No remaining layout differences observed.
