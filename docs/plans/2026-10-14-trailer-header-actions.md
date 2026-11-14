# Trailer header actions and paired card height

**Status:** Implemented and compiled desktop verified, 2026-10-14. Dante requests moving More videos next to the channels filter, removing its footer space, and aligning Library health with the shorter trailers card.

## Problem and decision

- HomeTrailersPanel renders More videos after HorizontalCardRail; home.css adds 12px top margin. This increases the trailers/health grid row height.
- Move the existing button into a header actions group immediately before the channel filter. Retire its footer margin. The existing shared grid naturally keeps Library health aligned.
- Scope: desktop Home markup/CSS and focused existing browser coverage; no backend or data changes. No open decisions.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| Button placement, current request | Header beside channel filter, no footer space | Home trailers | Move button | Requested amendment | Approved in request |
| Existing pagination/filter/state handling | Preserve click callback, disabled loading label, has_more/error visibility and filtering | HomeTrailersPanel/App | Preserve | No | Preserve |

## Current design and ownership

- Desktop checkout, master at be511f98846a67a182e5b371ad087938e9344362; extensive existing dirty work. Preserve prior amendments.
- HomeTrailersPanel owns the button; home.css owns its styling. Shared Home grid in styles.css owns trailers/health alignment. App owns pagination data and callbacks.
- Live backend remains PID 55580/port 5000 with Desktop data. Frontend was rebuilt in the preceding amendment. This task needs no restart.

## Exact behavior contract

### Frontend

Reuse the existing More videos button and select inside a flex header actions group with an 8px gap. Keep the button before the select, match their heights, and preserve channel selection and loading/error behavior. Remove .home-load-trailers footer-margin rule. Trailer rail remains the last ordinary content with existing panel padding below it; stale/error messages remain when applicable. Library health follows the shared grid row height.

### Backend

No changes to pagination requests, response cursors, persistence, retry or concurrency.

## Implementation sequence

1. Extend existing Home desktop browser regression with has_more data and header/padding/paired-height assertions; confirm failure before editing source.
2. Move the button into the existing header, group actions, remove footer rule.
3. Build and run the single relevant browser test, inspect desktop screenshot, rebuild served frontend for refresh.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| Populated trailers with more pages | Open Home | Button beside filter, equal heights, no former footer gap | Trailers header/CSS | Existing Home browser regression |
| Paired populated cards | Open Home | Trailers and health top/bottom align | Shared Home grid | Same regression |
| Channel filter and video interactions | Filter/play/choose versions | Existing behavior remains | HomeTrailersPanel | Same regression |
| Loading/error/exhausted feed | Existing state conditions | Same button label/disabled/visibility rules | HomeTrailersPanel/App | Preserve original conditional and callback |

## Verification and rollout

- Isolated OS-temp CP_TEST_ROOT, CP_TEST_MODE=1, embedded fixture mode, port 15114 and temporary dist. No production operations during browser tests.
- One existing Home browser regression and compiled screenshot; no broad suite for this small UI amendment.
- Rebuild served frontend and compare live index with dist/index.html. Browser refresh activates it; no backend restart, commit or push.

## Results

- Updated existing Home regression failed before implementation because the button was outside the header.
- Final isolated compiled browser check: 1 passed (6.0s). Verifies button/filter alignment, absence of footer space, matching trailers/health top and bottom, desktop rails, filtering, video versions and existing Home interactions.
- Inspected desktop screenshot at 1920x1080; the same test also checks desktop 1280x720. Existing panel padding remains, with no button row below the rail.
- Production frontend build passed and served index matches rebuilt dist. Browser refresh loads the amendment. Test-owned processes stopped; backend/data unchanged.
