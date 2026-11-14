# Cinema Paradiso work rules

These rules apply to every future Cinema Paradiso investigation, plan, and implementation. Read them before proposing work. The user's instructions and explicit decisions take precedence. Do not treat a previous plan, a passing test, or this file as permission to make a change.

## CP knowledge guides

Start with the [CP knowledge index](docs/README.md) when reviewing or changing a mapped feature. Use the Second Brain to find decisions and the Atlas to trace code and tests. Check their references against the current checkout before relying on them. Follow the linked maintenance workflow within the scope Dante approved.

## 1. Understand the request before deciding

- Restate the requested behavior in concrete terms. If a detail would change the product behavior or implementation, ask Dante a focused question before deciding it. Do not fill a consequential gap with an invented default.
- When disagreeing, first state Dante's proposal accurately, then identify the precise point of disagreement, the evidence, and the alternative. Say explicitly which parts you agree with. Do not reject a proposal and then present the same proposal in different words.
- Separate confirmed behavior, hypotheses, recommendations, open decisions, and approved decisions. Use plain language; explain internal terms when needed. State what you will do and what you need from Dante unambiguously.
- Do not ask Dante to diagnose CP when the answer can be found in its code, design, configuration, logs, tests, or running app.

## 2. Establish the real baseline

- Before a plan or change, identify the actual checkout, branch/commit, tracked and untracked changes, relevant configuration/data owner, and the version the running process and served frontend bundle use. Source, runtime data, and served `dist` are separate facts.
- Read the existing CP design and the current implementation of the requested behavior. Compare with the latest intended behavior, including refinements from prior versions. A historical tag is evidence of prior behavior, not permission to restore it.
- Preserve dirty work and unrelated behavior. Record existing failures and unknowns before changing code. Do not describe older verification as proof of the current checkout or live app.

## 3. Change the authoritative owner, not an override

- Trace the full behavior path from UI or API entry point through its service, store, configuration, and output. Find every competing branch, legacy rule, default, fallback, and caller that could produce the old behavior.
- Identify one authoritative owner for each responsibility. Improve or refactor that owner. Do not stack a new override on old logic, copy business rules into another route, or maintain competing sources of truth.
- When replacing a rule, account for callers and data dependencies, remove obsolete paths after verifying they are unused, and add regression coverage that proves both the new behavior and the later CP behavior that must remain. If a temporary compatibility path is genuinely required, document its dependency and removal condition in the plan.
- Keep Movie, TV, IPTV, shared, acquisition, and transfer ownership boundaries intact unless a reviewed plan explicitly changes them.

## 4. Follow the whole CP design and reuse its components

### Mandatory reuse gate for every new feature and UI change

- **Reuse is a hard requirement, not a preference.** Every new feature, amendment, prototype intended for production, and refactor must use CP's existing shared UI owners. Different feature functionality is not permission to duplicate its visual elements.
- Before writing UI, read the [shared UI component registry](docs/atlas/shared-ui.md), inspect the actual owner and existing callers, and name the components that will be reused in the plan or implementation notes.
- Buttons, icon buttons, badges, chips, fields, search controls, pagination, selection bars, empty states, dialog shells, tabs, cards, rails, and tooltips must be composed from their shared owners. Do not copy their JSX/CSS, create a page-local lookalike, or override their appearance in a feature stylesheet.
- If an existing owner lacks a necessary visual variant, extend that owner and verify its existing callers. If no owner exists, create one reusable owner in the shared UI layer before using it. Keep feature-specific data, permissions, actions, validation, and navigation in their current feature owners.
- Specialised compositions may have their own component when their semantics differ, but must still reuse common primitives. Document the distinction in the registry; do not use a generic "custom" escape hatch to bypass standardisation.
- The Style Guide must render the production shared components. It must never maintain independent copies of their designs.
- Completion requires the shared-UI reuse check to pass, meaningful rendered-state checks for affected owners/callers, and an audit of any new component or style. Record the owner reused, variants added, obsolete copies removed, and exceptions explicitly approved by Dante. Do not claim completion while knowingly introducing duplicate UI ownership.
- Run `npm run check:ui-reuse`; development and production builds also run it automatically. Never edit `tools/ui-specialized-owners.json` just to silence a failure. Its bounded entries identify existing semantic owners, not permission to copy them.
- An exception requires Dante's explicit approval for that specific exception. Deadlines, a small change, a new page, a different backend, or an AI-generated feature do not waive this rule. Only Dante may change or waive it.

- Every frontend amendment must follow the existing CP design in layout, grid, spacing, sizing, typography, color, controls, states, navigation, and interaction. Matching fonts or colors alone is insufficient.
- Before adding UI, identify the existing screen and component that performs the same job. Reuse it when semantics match. If it needs to serve another surface, extend or refactor the shared owner and verify every surface that uses it. Do not clone JSX/CSS to imitate a component or introduce a second visual implementation for the same behavior.
- Where semantics truly differ, document the difference and use a separate component only for that difference. Remove obsolete duplicate markup or styles when the shared owner replaces them.
- For parity requests, compare the actual rendered desktop screens and interactions side by side, including empty, loading, error, populated, and long-content states. Verify grid behavior, spacing, card geometry, controls, and navigation, not just a screenshot's general appearance.
- Default to desktop work. Do not add mobile or responsive redesign unless Dante asks or the requested change directly requires existing mobile-specific code.

## 5. Write implementation plans that can be executed without guessing

Use `docs/plans/_template.md` for every new implementation plan. A plan must specify:

1. The observed problem, user impact, evidence, intended behavior, and open decisions.
2. The current execution path, authoritative owners, prior-version behavior that must remain, and affected surfaces/callers.
3. Exact frontend component reuse, placement, layout, states, and interactions, when UI is involved.
4. Exact backend inputs, outputs, persistence, failure behavior, concurrency/retry behavior, and migration or rollback needs, when backend work is involved.
5. Implementation steps that change existing owners and retire obsolete paths, plus explicit scope boundaries.
6. A scenario-by-scenario acceptance matrix covering the motivating case, other affected surfaces, edge cases, and regressions.
7. Verification commands/environments and distinct gates for isolated tests, compiled UI, and live behavior when approved.

Words such as "match CP," "handle errors," "reuse components," or "zero regression" are goals, not specifications. Replace them with named components, exact behavior, and observable acceptance criteria. Label unresolved decisions; resolve any that affect implementation before coding. Do not silently expand an approved plan.

## 6. Verify honestly and respect action boundaries

- Before implementation, investigation is read-only. Do not edit code, files, configuration, data, or tests until Dante explicitly approves implementation. Approval of a plan covers only its stated scope. Ask again only for material expansion or new risk.
- Add meaningful automated regression coverage for changed behavior and existing behavior exposed by the same owner. Run the relevant focused checks, then the appropriate broader suites. Do not weaken assertions, hide failures, or call a focused rerun a green full suite.
- For UI work, verify the compiled bundle and actual rendered desktop behavior. For live claims, identify the running process, configuration/data owner, served bundle, and visible result. A source edit or isolated test does not make a change live.
- Treat live catalog changes, downloads, deletions, app restarts, commits, pushes, tags, packaging, and releases as separate actions requiring the authorization applicable to each. Preserve recovery options for approved live changes.
- Report what changed, why, what passed, what failed, what remains uncertain, and whether the result is source-only, tested in isolation, or live.

## 7. Make contract changes visible and test the actual result

- Before changing an authoritative owner, identify each affected product contract: the agreed behavior, its source, affected surfaces and callers, and genuine exceptions. Distinguish an agreed contract from behavior that merely exists in code. Mark uncertainty instead of inventing a rule.
- If a fix, feature, refactor, or test would change or weaken an agreed contract, stop the affected work and present Dante with a separate, prominent user-facing notice headed `## ⚠️ CONTRACT CHANGE — DANTE'S DECISION REQUIRED`. State **CURRENT RULE**, **PROPOSED RULE**, **WHAT DANTE WILL SEE**, **AFFECTED AREAS**, **REASON**, **COST OR RISK**, **ALTERNATIVE**, and **RECOMMENDATION** in plain language. Ask for an explicit decision on that contract change before implementing it. Do not bury the notice in a plan, test diff, or progress update. If the conflict appears during approved work, pause that part of the work and raise the notice then; continue only work that does not depend on the decision.
- A general request to fix or implement a feature, a passing test, or approval of a broader plan does not silently approve a contract change. Record Dante's explicit decision and its scope in the plan before coding the changed behavior.
- Tests must assert the agreed user-visible result, including relevant adverse cases. If an existing or proposed test accepts a contract violation, report the conflict. Do not preserve, add, or revise that assertion as though it settles the product decision.
- When multiple owners produce one visible result, verify the complete path as well as individual units. Assert what the backend returns and what the frontend renders, rather than only the requested input or an isolated calculation. Cover affected callers and meaningful boundary cases.
- Before reporting completion, compare the implemented and observed behavior with each approved contract. State any remaining difference and its impact explicitly; a passing suite does not erase that difference.
