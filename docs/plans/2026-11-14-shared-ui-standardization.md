# Shared desktop UI standardization implementation plan

**Status:** Implemented, isolated-tested and installed after Dante's separate authorization on 2026-11-14. Dante selected all recommended visual families, then instructed: "after you add the rule go with the plan". The rule was added before implementation. He later explicitly requested installation of the reviewed frontend bundle; live installation and visible checks are recorded in the verification report. The earlier comparison's `implementationApproved: false` was superseded by his explicit instructions. No backend restart, commit, push or release was performed.

> **For implementers:** Use `superpowers:executing-plans` after implementation approval. Do not commit, activate, restart, or change live data under planning approval. Follow the repository's approval and contract-change rules.

**Goal:** Give repeated desktop controls one presentation owner using Dante's selected existing CP designs, while each feature retains its actions, data, validation, persistence, and interaction policy.

**Architecture:** Extend existing shared components first. Extract common button, badge, field, dialog-shell and section-tab presentation where no reusable owner exists. Features pass content, attributes and callbacks; shared presentation performs no API requests or domain decisions. Remove replaced markup and styles after verifying all consumers.

**Tech stack:** Existing React 19, Vite, CSS and Lucide; no new UI library or dependencies.

**Design evidence:** The side-by-side comparison in this chat, built from current source styles and representative component markup with sample content, is the selected appearance reference. Its local source is `C:/Users/dante/.codex/visualizations/2026/11/14/01a1da8d-18c9-7c31-9dcf-00018cd26fc7/cp-ui-versions.html`. This is a specimen comparison, not screenshots proving every live screen. Existing ownership contract: [2026-10-11 integration plan](2026-10-11-mostafa-ui-ux-integration-plan.md#exact-behavior-contract).

## Problem and decision

- **Observed:** Stream is repeated in SharedMovieCards, Discover, Home and TV. Its shared green CSS was overridden by secondary styles until the correction earlier in this chat. Settings has a private ActionButton. TV has a separate button family. IPTV pagination is duplicated in its workspace and Lists; AI has another implementation. Shared selection and empty-state owners coexist with copied markup. The Style Guide demonstrates its own button and badge designs.
- **User impact:** Appearance fixes must be repeated, and pages can drift in colour, size, spacing and visual state.
- **Confirmed:** Current source ownership and specimen appearance. The preview was inspected at desktop width, its eight sections rendered without specimen overflow, and choosing an option updated the selection summary.
- **Unknown:** Complete visual/state coverage of every affected live surface. No project tests were run during the audit or planning. Prior tests are not a baseline for this refactor.
- **Scope:** Repeated desktop buttons, badges/chips, pagination, selection bars, empty/error presentation, dialog shells, search/form field shells, and peer section tabs. Style Guide must consume the production owners.
- **Excluded:** Backend, network requests, domain logic, catalog writes, player behavior, selection scope, search semantics, automatic retries, dialog-dismissal policy, keyboard-navigation policy, page layout redesign, mobile/responsive redesign, native Qt player, third-party qBittorrent UI, packaging and release.
- **Open decisions:** None for source implementation. No unresolved choice among the eight presented visual families. Live activation remains separate.

### Dante's selected families

| Family | Approved visual reference | Application rule |
| --- | --- | --- |
| Buttons | Shared CP | Existing regular CP buttons; green Play/Stream, gold primary, neutral secondary; keep compact size in dense controls. Keep destructive and AI meanings/colours. |
| Badges and chips | Unified card plus compact size | Normal card chips use the unified family; dense/file-row chips use its explicit compact variant. Preserve labels and status meanings. |
| Pagination | Shared Pagination | Use the existing visible Previous/page-summary/Next family. Do not remove existing page/range/result information or manufacture totals. No optional arrow-only variant was selected. |
| Selection bars | Shared WorkspaceSelectionBar | Keep its visual family; caller retains actions, selected identities, counts and zero-selection behavior. |
| Empty states | Shared workspace plus compact size | Large result areas use the shared spacious state; small inline sections use compact presentation. Loading, empty, error and incomplete remain different states. |
| Dialogs | Movie dialog treatment | Existing Movie header, close control, body spacing and action-row visual treatment; retain appropriate existing content widths. The shell does not take over feature dismissal/focus rules. |
| Search/filter fields | Shared search and labelled fields | SearchField and the existing CP labelled form-field appearance; retain provider-specific labels, choices, validation, and submission timing. |
| Section tabs | Movie/TV section-tab appearance | Peer workspace sections share the existing media-section tab styling. Local segmented choices such as seasons and view modes remain local segmented controls. |

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior / exceptions | Affected callers | Proposed behavior | Changes contract? | Dante's decision |
| --- | --- | --- | --- | --- | --- |
| UI reuse, AGENTS section 4; 2026-10-11 integration | Reuse actual presentation owners; domain callbacks retain responsibility | Desktop workspaces and shared controls | Complete shared presentation ownership for selected families | No weakening | Selected all recommended visual families, 2026-11-14 |
| Existing inconsistent appearances | Competing implementations exist; existence alone is not an agreed visual contract | TV episode buttons, IPTV pagination/tabs, repeated badge/dialog/empty shells | Adopt selected visual references | Appearance changes explicitly selected | Same decision |
| Functionality varies, current chat | Different domains retain different behavior | Movie, TV, IPTV, AI, Maintenance, Settings | Visual extraction only; same callbacks, targets, labels, available actions and state conditions | No | "we only speak about ui" |
| Playback / streaming | Movie source chooser, TV episode streaming, IPTV provider sessions have distinct owners | SharedMovieCards, Home, Discover, TVWorkspace, IPTVWorkspace | Reuse action presentation without changing payloads or eligibility | No | Preserve |
| Keyboard/focus/dismissal | Existing implementations differ; broad behavior standardization was not selected | Dialogs, tabs, popovers, fields | Pass through current handlers, roles, focus and dismissal policy | No | Preserve; propose separately if a functional correction is needed |

Any newly discovered conflict with an agreed product contract requires the separate user-facing contract-change notice specified in AGENTS. Do not resolve it by updating tests or claiming visual approval includes functional changes.

## Current design and ownership

### Baseline, 2026-11-14

- Checkout: `C:/Users/dante/Desktop/cinema paradiso`; branch `master`; HEAD `117526b`.
- Before this plan: 174 modified, 2 deleted, 307 untracked status entries (untracked directories can represent many files). This is substantial pre-existing work; never reset or reconstruct files from HEAD.
- Current port 5000 listener: PID 52092. Earlier same-session process inspection identified Python 3.12 running `app.py`; its command line does not independently establish working directory.
- Read-only homepage check: `/assets/index-DARa9R-d.js` and `/assets/index-bBaF3XqR.css`, matching the checkout build previously checked. App-data endpoint reports `C:/Users/dante/Desktop/cinema paradiso/data`.
- These are runtime/bundle observations, not proof of all screen behaviors. Recheck drift immediately before implementation and activation.

| Responsibility | Existing owner | Callers / competing paths | Preserve |
| --- | --- | --- | --- |
| Theme and button appearance | `src/styles/playerTheme.css`, `src/styles.css` | Private Settings ActionButton; TV primary/secondary-button; Style Guide sg-btn | Theme values, intentional action colours, hover/disabled/focus states |
| Card badges | `src/components/movie-card/MovieCard.jsx`, `movieCard.css` | `.chip`, `.status-badge`, manual TV detail chips, Style Guide sg-chip | Status labels, owned/following meaning, metadata content and Arabic direction |
| Pagination | `src/components/Pagination.jsx` | Private IPTV Pagination, IPTV Lists copy, AIControlPagination | Known/unknown total, caller page state, page limits, summary information |
| Selection | `WorkspaceSelectionBar.jsx`, `SelectionCheckbox.jsx` | AIControlSelectionBar copy; feature actions inside shared bars | Loaded-vs-all selection, cross-page state, eligible counts, zero-selection state |
| Empty state | `WorkspaceEmptyState.jsx` | Manual base empty-state and IPTV empty-state | Exact state distinction, explanatory text, recovery action and layout placement |
| Dialog presentation | `.small-dialog`, `.dialog-header`, `.dialog-field`, `.dialog-actions` | Repeated markup in Movie/TV/IPTV forms and dialogs | Form ownership, modal stack, width appropriate to contents, existing event/focus policy |
| Search/form presentation | `SearchField.jsx`, `CatalogMetadataFilters.jsx`, `WorkspaceYearRange.jsx`, shared CSS | IPTV fields, repeated labelled inputs/selects | Choices, labels, IDs, errors, focus, submit timing |
| Section tabs | `.discover-tabs.media-section-tabs` | MediaWorkspace, ListsWorkspace, IPTV tabs, matching peer-section tabs | Navigation, roles, keyboard handlers, active state, history/session storage |
| UI reference | `StyleGuide.jsx` | Independent sg button/chip examples | Reference page becomes a consumer, not a second source of production appearance |

## Exact behavior contract

### Frontend

**Global rules:** Maintain outer page layout, card grid, sticky controls, component order, visible content, and available actions. Changes inside the selected controls may change colour, weight, border, padding and height to the chosen reference. Do not introduce a global CSS override that masks old owners.

**Buttons:** Create `src/components/ui/Button.jsx` by extracting the reusable presentation currently local to Settings and the shared `.btn`/`.mini-action` families. Interface: `Button({variant='secondary', size='regular', icon: Icon, iconSize, loading=false, children, className, ...nativeButtonProps})`. Supported variants: primary, secondary, play, stream, danger, upgrade, ai. Sizes: regular, compact, icon. Regular follows `.btn`: minimum 36px, 12px horizontal padding, 7px icon gap, 0.82rem/800. Compact follows `.mini-action`: minimum 28px, 8px padding, 5px gap, 0.72rem/800. Current icon-only geometry is represented by named variants for its existing placement, not arbitrary page CSS. `loading` selects the supplied spinner presentation; the caller still supplies `disabled` and the existing click guard. Preserve `type`, `aria-*`, `title`, `tabIndex`, event propagation and ref. Explicitly preserve native form-submit behavior where current buttons omit type.

Keep MoviePlayButton's pending-play guard with its current owner. It renders Button; it does not migrate that logic into Button. Add a presentation-only `StreamButton` export alongside Button to own the standard icon/green-outline variant, accepting children/label and native button props. Movie, TV and IPTV stream routing remains entirely outside it. No click handler is inferred from a label.

**Badges:** Create `src/components/ui/Badge.jsx` and `ui.css`, moving the selected chip/badge rules out of their competing owners. Interface: `Badge({kind='metadata', size='regular', tone='neutral', children, className, ...spanProps})`. Kinds: metadata, status, owned. Regular metadata preserves unified-chip minimum 30px, 12px padding and 0.82rem/900; compact metadata preserves current .chip minimum 24px, 9px padding and 0.74rem/700. Owned retains the existing unified-owned treatment; following, warning, danger and neutral retain current semantic colours. No strings or domain statuses are derived by Badge. Special provider availability, awards and rating components retain their meaning and existing owners; share their underlying visual pieces only where the selected design actually applies.

**Pagination:** Extend the existing component to accommodate all present caller summaries without assuming a known total. Keep its present props and add an explicit visibility option only where a caller currently shows a one-page summary. All callers supply their current page and paging handlers. Convert IPTV pageSize/total to totalPages/ranges in its existing pagination call sites; retain clamp/disabled conditions. AI keeps its pageLabel as summary. Preserve current paging placement; do not add or remove top/bottom page controls.

**Selection bars:** Extend WorkspaceSelectionBar with explicit presentation options for zero-selection count/actions and caller-provided disabled states. Default behavior remains unchanged. AI passes its existing always-visible disabled Clear/Add controls; do not silently change them to hidden controls. AI confirmation and busy guards remain in AIControlSelectionBar, which becomes a domain adapter rendering the shared bar.

**Empty states:** Extend WorkspaceEmptyState with `size='regular'|'compact'`, optional `icon`, and forwarded `role`/`aria-*`. Regular preserves its 160px minimum area, 24px padding, 18px title and 14px description. Compact preserves the base empty-state 18px padding and natural height. Default result areas use regular; inline people/keyword/help/auxiliary panels use compact. Existing error roles, text and Retry actions remain supplied by callers. Do not replace incomplete-filter or loading messages with definitive empty results.

**Dialogs:** Create `src/components/ui/DialogShell.jsx` using the Movie small-dialog/header/actions rules. Interface: `DialogShell({as='section', title, kicker, headerActions, children, footer, className, ...elementProps})`; export shared header/body/action subcomponents for callers with existing form boundaries. Default regular content width is the existing 560px; preserve established wider source/review/player widths via named sizes. The shell owns no backdrop, portal, Escape listener, focus trap, close callback, form submission or outside-click rule. Existing layers and hooks stay with callers. It may render a caller-supplied close control in the established Movie position. Media content/stages and native player are excluded from the shell redesign.

**Fields:** Keep SearchField as the search presentation owner. Add `src/components/ui/FormField.jsx` to own the existing dialog-field label/error layout and export styled native Input/Select presentation with forwarded native attributes/ref. Values, `onChange`, validation, errors and option lists stay with callers. Keep CatalogMetadataFilters and WorkspaceYearRange as their existing higher-level owners. Preserve whether a field has a clear action; the comparison did not authorize adding clear/submit behavior to other pages.

**Tabs:** Add `src/components/ui/SectionTabs.jsx` with `items`, `activeKey`, and caller-supplied container/button props and handlers. It owns the chosen media-section CSS and icon/label layout only. Preserve explicit role/aria-controls/aria-selected/aria-pressed/tabIndex and key handlers from each current owner. Do not impose Lists keyboard behavior on other tabs. Do not turn local season/view segmented selectors or sidebar navigation into section tabs.

**Style ownership:** Import `src/components/ui/ui.css` once in `src/main.jsx`. Move rules rather than duplicating them. Retain existing higher-level owners (`MovieCard`, `Pagination`, `WorkspaceSelectionBar`, `WorkspaceEmptyState`, `SearchField`) and migrate their internal primitives. No generic catch-all component that owns all UI or accepts domain records.

### Backend

No backend files, requests, responses, persistence, concurrency, retries or migrations change. A presentation control receives the same callback and event/payload as its old markup. A button that currently opens review must still open review; it must not initiate the action itself.

## Implementation sequence

Each phase is reviewable and testable. Implement natively in this chat unless Dante chooses another execution method. Source changes require approval of this plan; activation remains separate.

### 1. Button and badge owners

- [x] Capture the current working-file baseline and source inventory before editing. Recheck modified/untracked files and current installed bundle; preserve concurrent work.
- [x] Add focused rendered tests for the selected appearance, normal/hover/disabled/loading states, form-submit pass-through and long/Arabic labels. Use `tests/e2e/ui-standardization.spec.js` for this shared contract; do not assert implementation spelling instead of output.
- [x] Extract Button and Badge into the named files. Update private Settings ActionButton, SharedMovieCards, HomeWorkspace, DiscoverWorkspace, TVWorkspace and IPTVCards first. Verify the original Stream problem in actual rendered output.
- [x] Migrate ordinary action buttons/chips in remaining `src/components/*.jsx` and `src/features/**/*.jsx`, including Lists, AI, Maintenance, Settings, Downloads and notifications, to the same owners. Keep composed poster controls, portraits, sidebar links, rail navigation, ratings, player controls and selectable cards under their existing semantic components; use a shared primitive internally only when it preserves their selected geometry/behavior.
- [x] Remove replaced TV button and legacy chip rules only after searches show no remaining consumer. Do not delete unrelated dirty code or styles.

### 2. Pagination, selection and empty states

- [x] Extend `Pagination.jsx`, `WorkspaceSelectionBar.jsx`, `WorkspaceEmptyState.jsx` with the compatibility options specified above, preserving their current defaults.
- [x] Replace private pagination in `IPTVWorkspace.jsx`, the copy in `IPTVListsWorkspace.jsx`, and `AIControlPagination` in `AIControlResult.jsx`. Update the `IPTVBulkMetadataJob.jsx` pagination-prop contract at both ends if its injected component interface changes; do not leave mixed old/new props.
- [x] Convert `AIControlSelectionBar.jsx` to the existing shared owner while retaining its domain actions and zero-selection state.
- [x] Replace matching manual empty-state presentation in App, DiscoverResultGrid, IdentityReviewPanel, AIControlResult, CleanupWorkspace, DiscoverWorkspace, HomeWorkspace, IPTVListsWorkspace, IPTVWorkspace, LibraryWorkspace, MovieListsWorkspace, TVListsWorkspace, TVFileView and TVWorkspace.
- [x] Verify first/last/unknown page, zero/partial/all selection and empty/error/incomplete states; remove obsolete page/selection/empty visual markup and CSS.

### 3. Fields and section tabs

- [x] Extract FormField and SectionTabs using the selected CSS and forward all current native attributes/handlers.
- [x] Update SearchField consumers and repeated search shells in Library, Discover, Movie/TV Lists, TVSearchControls, TVFileView, IPTVWorkspace/IPTVListsWorkspace and ListsToolbar. Migrate labelled form-field presentation in Settings, TVSettings, acquisition profiles, advanced search and shared dialogs without changing values/options.
- [x] Migrate matching peer section tabs in MediaWorkspace, ListsWorkspace, DiscoverWorkspace, IPTVWorkspace and CleanupWorkspace. Keep local segmented controls distinct.
- [x] Verify current history, stored active tab, search submission, focus and validation behavior; remove obsolete styling only for migrated elements.

### 4. Dialog presentation

- [x] Extract the presentational shell; migrate ListEditorModal, TVPosterEditor and the existing Movie poster editor first.
- [x] Adopt the shell/header/actions in App dialogs, ExportCopyDialog, LibraryControls, MetadataCorrectionModal, PersonCreditCard biography, SharedMovieCards plot, SmartMatchPanel, SourceReviewDialog, CleanupWorkspace, IPTV dialogs, LibraryWorkspace, MovieListsWorkspace, SettingsWorkspace, TVAcquisitionReview and TVBulkActionBar where they perform the same presentation job.
- [x] Keep AnchoredPopover and its dismissal owner for popovers. Keep StreamPlayerModal's player hook and stage; adopt only matching shell pieces. Do not recast a popover as a modal.
- [x] Verify caller-owned submit, cancel, Escape, outside-click, focus and stacked-dialog behavior against its baseline. Any proposed behavior repair is a separate decision, even if accessibility would benefit.

### 5. Production reference and removal check

- [x] Replace separate StyleGuide button/chip examples with the actual production owners and examples of all selected families and states. Keep the guide's surrounding presentation; do not adopt its old sg styles as production.
- [x] Search all `src` consumers for retired classes/components and duplicate visual definitions. Record intentional remaining semantic components and any uncovered visual family; do not claim every raw button is automatically a defect.
- [x] Update the linked Atlas and Second Brain with actual new owners only after implementation. Record verification evidence and any remaining migration gap.

## Acceptance matrix

| Scenario | Action | Exact expected result | Check |
| --- | --- | --- | --- |
| Stream on expanded Movie, Home, indexer and TV | Render, hover, activate via stub | Same shared green-outline appearance; original label, eligibility and callback target retained | New desktop spec plus existing streaming specs |
| TV episode Play/Stream | Render and invoke via stubs | Selected shared green family; exact episode target and unavailable state unchanged | New spec + native TV coverage |
| Button inside a form | Keyboard submit and click | Existing submission occurs once; non-submit control still does not submit | New spec |
| Disabled/loading/long or Arabic label | Render state | No lost disabled state, no accidental activation, readable label/icon, correct direction | New spec |
| Owned/following/warning/provider match | Render representative records | Selected size/tone; no relabelled meaning or reclassification | New spec + unified-card coverage |
| Pagination known / unknown / zero / one / last page | Previous/Next | Current eligibility/clamping and summary information retained; selected shared appearance | New spec + paging tests |
| AI selection zero / three / busy | Render and select/clear | Existing visibility and disable rules retained; same selected identities | New spec + AI fixture |
| Incomplete filters or failed request | Render failure/empty states | Incomplete/error message remains distinct; Retry invokes only existing recovery callback | Existing Lists/controls fixture + new spec |
| Movie / TV / IPTV dialog | Open, submit, close with each supported path | Selected shell; original form and dismissal/focus behavior retained | Focused dialog scenarios |
| Search with draft/validation/provider choices | Type, clear if available, submit | Same value, options, errors and request timing; shared field appearance | Existing search/control scenarios |
| Tabs with history and keyboard navigation | Switch and Back | Same navigation/storage/key behavior; selected section appearance | Existing smoke/list scenarios |
| Dense and spacious placements | Render at desktop widths | Compact variants used only in compact placements; no clipped text or control overlap; outer page layout retained | 1600x1000 and one 1280x720 desktop check |
| Reference page | Render all families | Uses the same production components; shared appearance changes propagate to examples | New spec |

## Verification and rollout

- **Baseline:** Before product edits, run the focused existing UI checks once and record failures. The planning audit did not establish a green suite.
- **Source/contract baseline:** `python -m unittest tests.test_unified_movie_card_ui tests.test_library_action_ux tests.test_workspace_layout_ui`. Update obsolete source-string assertions only when rendered-output coverage proves the selected UI and preserved behavior; do not weaken product expectations.
- **Focused compiled desktop:** `npm.cmd run test:e2e -- tests/e2e/ui-standardization.spec.js tests/e2e/workspace-controls-empty-layout.spec.js tests/e2e/streaming-providers.spec.js tests/e2e/lists-layout.spec.js`. The existing runner creates isolated data and builds to its own dist. Review fixture requirements first; do not run against live catalog/player state.
- **Affected integration checks:** Run `app-smoke.spec.js`, `cross-page-selection.spec.js`, `native-tv.spec.js`, `tv-expanded-parity.spec.js`, and the applicable dialog/search/AI fixture cases once after their migration. Use targeted cases where an entire spec includes unrelated external or destructive operations. Document the exact cases and skips.
- **Proportion:** No full backend regression suite for a presentation-only refactor. No real downloads, provider playback, GPT jobs, matching, catalog mutations or repeated builds solely for reassurance. Extend checks only when changed ownership or a failure justifies them.
- **Compiled UI:** Compare to the selected source specimens and current desktop pages. Include disabled/loading/empty/error/long-content states and real caller composition, not just standalone primitive tests. Build output is isolated until live activation is authorized.
- **Live rollout:** Separate authorization required before replacing installed dist or restarting CP. Preserve previous installed index/assets, record current bundle/process/data owner, install only the reviewed candidate, and perform read-only visible checks. Revert to the saved bundle if controls/layout or callbacks differ from approval. No data rollback should be needed because this scope does not write data.
- **Reporting:** Separate planned, implemented, isolated-tested, compiled and live states. List exact test outcomes and remaining differences. Do not equate selected visual families with approval to change functionality.

## Plan self-review

- All eight submitted selections map to an owner and implementation phase.
- Shared components receive presentation data and callbacks; no backend/domain behavior moves into them.
- Zero-selection visibility, unknown totals, form button type, Arabic/long labels and dialog focus are explicitly preserved and covered in the matrix.
- Compact variants were selected only for badges/empty states and the already recommended dense-button size. Arrow-only pagination was not silently retained as the default.
- Source implementation is approved by the later explicit instruction. Live activation, commits and releases remain unapproved.

## Execution ledger

- 2026-11-14: Added the mandatory UI reuse gate to AGENTS before product changes.
- Ruling: Work in the approved current checkout, preserve a file snapshot of the dirty baseline, and build/test in isolated output/data directories. No suitable attached worktree exists; a clean HEAD checkout would omit the current uncommitted UI. This does not activate the frontend or permit resetting unrelated work.
- Ruling: Add a shared UI registry and an automated reuse check as requested with the permanent rule. These enforce owner adoption; they do not replace rendered behavior tests.

- Baseline: 100 focused source checks ran before changes; 3 existing card assertions failed. Snapshot preserves the dirty source used for comparison.
- Phases 1–5: shared owners and callers migrated, obsolete ordinary button/badge/pagination/selection/shell styles removed, production reference and reuse gate implemented. Native callbacks, labels, form/keyboard attributes and specialized compositions retained.
- Refinement: SectionTabs uses composable SectionTab children instead of an items array so caller roles, refs and keyboard handlers stay explicit. Pagination accepts caller-specific visible/accessibility labels while sharing appearance. EmptyState supports composed content and an actions slot. ActionLink shares Button presentation with native anchor semantics.
- Verification: see [the dated report](../verification/shared-ui-2026-11-14/report.md) for exact batches and unchanged baseline failures. A failed new Maintenance test was a test URL error (`/maintenance` instead of existing `/cleanup`), corrected without changing app routes.
- Final review: addressed both ownership findings (plot/biography shells and keyword-badge override), strengthened unnamed-dialog detection, migrated the poster/Smart Match shells it exposed, and verified affected rendered callers. No deferred findings.
- Ruling: keep the existing working tree uncommitted and the installed bundle untouched, as required by the approved scope. No branch integration menu, commit or full backend suite is appropriate for this UI-only source task; baseline failures are reported separately.
