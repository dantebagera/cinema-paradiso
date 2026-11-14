# Shared desktop UI owners

**Mandatory:** reuse these owners for every new feature. Different functionality stays in caller callbacks; it is not permission to copy presentation. Extend the owner when a supported variant is missing. See [AGENTS](../../AGENTS.md#4-follow-the-whole-cp-design-and-reuse-its-components) and [approved plan](../plans/2026-11-14-shared-ui-standardization.md).

| Family | Authoritative production owner | Use and limits |
| --- | --- | --- |
| Actions | [Button](../../src/components/ui/Button.jsx) | `primary`, `secondary`, `play`, `stream`, `danger`, `upgrade`, `ai`, `source`; `regular`, `compact`, `icon`. Preserve native `type`, disabled/loading policy, events and ref. |
| Streaming | `StreamButton` in Button | Green outline plus standard icon. Caller chooses movie/episode/provider and owns playback. |
| Navigation styled as action | `ActionLink` in Button | Real anchor; preserve href, target, download and rel. Do not replace navigation with click handlers. |
| Badges/chips | [Badge](../../src/components/ui/Badge.jsx) | Metadata, status or owned; regular or compact. Caller supplies labels and meaning. Following/owned/warning/danger/neutral/missing and certification are explicit tones. |
| Paging | [Pagination](../../src/components/Pagination.jsx) | Previous / page + caller summary / Next. Known and unknown totals. `showSinglePage` retains an always-visible summary. No feature copy. |
| Selection | [WorkspaceSelectionBar](../../src/components/WorkspaceSelectionBar.jsx), [SelectionCheckbox](../../src/components/SelectionCheckbox.jsx) | Feature owns identities and payloads. AI's zero-count/disabled actions use explicit props on this owner. |
| Empty/error/loading messages | [WorkspaceEmptyState](../../src/components/WorkspaceEmptyState.jsx) | Regular result areas; compact inline areas. Preserve text, roles, loading vs incomplete vs empty distinction and recovery callbacks. Use `actions` for the action row; title/description or composed content. |
| Fields | [FormField, Input, Select, Textarea](../../src/components/ui/FormField.jsx) | Native value, validation, options, events, form membership and ref. Checkbox/radio/file/range retain their specialized native semantics. |
| Search | [SearchField](../../src/features/search/SearchField.jsx) | Composition of icon and Input; optional caller-provided clear action retains focus. Query interpretation remains in existing search owners. |
| Section navigation | [SectionTabs / SectionTab](../../src/components/ui/SectionTabs.jsx) | Children compose existing icons/labels. Pass existing roles, selected/pressed attributes, tabIndex and key/navigation handlers. No new navigation policy. |
| Dialog presentation | [DialogShell / DialogHeader / DialogActions](../../src/components/ui/DialogShell.jsx) | Movie treatment; regular, source, poster, wide, plot, biography, poster-review and match-review preserve established content widths. `as` preserves section/form/native dialog boundaries. Feature retains portal, backdrop, Escape, focus and submission. |
| Cards and rails | [MovieCard](../../src/components/movie-card/MovieCard.jsx), [SharedMovieCards](../../src/components/SharedMovieCards.jsx), [PersonCreditCard](../../src/components/PersonCreditCard.jsx), [HorizontalCardRail](../../src/components/HorizontalCardRail.jsx) | Compose these existing semantic owners; never clone their markup or artwork/interaction logic. |

Core appearance lives in [ui.css](../../src/components/ui/ui.css), imported once by `main.jsx`. Existing shared workspace/search layout stays in `styles.css`. Feature placement may determine layout and available width; it must not repaint shared controls. Explicitly selected UI changes do not authorize changing domain behavior.

## Enforcement

- `npm run check:ui-reuse` runs [the gate](../../tools/check_ui_reuse.mjs); `predev` and `prebuild` run it automatically.
- New raw action/field markup, copied family shells, missing component imports and feature CSS that repaints a shared family fail. Native anchors styled as actions also use the shared owner. Inline appearance overrides fail.
- [Specialized-owner inventory](../../tools/ui-specialized-owners.json) records exact existing signatures and occurrence counts. It has no per-feature wildcard. Copying an existing control to a new file or adding another occurrence fails.
- The inventory is not an opt-out mechanism. An agent must not refresh it to silence a failure. First move the caller to the owner or improve the owner. A genuinely new semantic owner must be documented and reviewed; an exception to reuse requires Dante's specific decision.
- Automated checks do not prove arbitrary visual similarity. Review remains mandatory: identify the owner before coding, inspect desktop output, and verify original callbacks and states. Do not promise that a Markdown instruction alone makes violations impossible.

## Intentionally distinct compositions

Poster overlays, playable/selected cards, portrait actions, rail arrows, sidebar navigation, popover menu rows, local segmented choices, removable list/keyword tokens, provider source rows and availability indicators retain their existing semantic owners and required geometry. Their callbacks or DOM roles are different from an ordinary action. Common actions inside those compositions use the shared primitives when applicable. Rating/awards, media stages and native player controls remain specialized. The inventory bounds these existing owners; it does not allow a future feature to reproduce them.

`StyleGuide` renders [UIReference](../../src/features/styleguide/UIReference.jsx), which uses production components with local example state. Card Lab actions also use Button. They are consumers, not alternate style definitions.

## Verification

[Rendered component contracts](../../tests/shared-ui.test.mjs), [gate regression tests](../../tests/ui-reuse.test.mjs), and [desktop reference tests](../../tests/e2e/ui-standardization.spec.js) cover native attributes, labels, loading/disabled policy, unknown totals, zero selection, retry, dialog form boundaries, shared appearance and two desktop widths. Affected workspace, streaming, lists and TV integration cases cover real callers. Source implementation and isolated verification do not imply installed-bundle activation.
