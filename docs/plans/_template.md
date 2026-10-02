# [Specific CP change]

**Status:** Draft / approved for implementation / implemented / live verified. Record the date and Dante's exact approved scope. A draft plan is not implementation approval.

## Problem and decision

- **What happens now:** Give the reproducible behavior and user impact. Cite current code, logs, test output, or rendered UI evidence.
- **What Dante wants:** State exact observable behavior, not a slogan such as "match CP."
- **Confirmed / suspected / unknown:** Keep these separate.
- **Open decisions:** List questions that affect behavior. Resolve them with Dante before implementation; record the answer here.
- **Scope:** State the surfaces and behavior included. State material exclusions and separate live actions.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| | | | | Yes / No / Uncertain | Pending / exact decision and date |

Distinguish an agreed product contract from behavior that merely exists in code. Resolve uncertainty that affects implementation before coding. For any proposed contract change, send Dante a separate user-facing notice headed `## ⚠️ CONTRACT CHANGE — DANTE'S DECISION REQUIRED` before implementation. State **CURRENT RULE**, **PROPOSED RULE**, **WHAT DANTE WILL SEE**, **AFFECTED AREAS**, **REASON**, **COST OR RISK**, **ALTERNATIVE**, and **RECOMMENDATION**; ask for an explicit decision. A plan entry alone is not the notice or approval. If a conflict emerges during approved work, pause the affected work, send the notice, and record Dante's decision here before continuing that part.

Identify any existing or proposed test that accepts behavior contrary to an agreed contract. Explain the conflict and the corrected assertion; never treat a passing test or an updated expectation as authority to change the product contract.

## Current design and ownership

| Responsibility | Current authoritative file/component/service | Entry point and callers | Behavior to preserve | Competing or obsolete paths |
| --- | --- | --- | --- | --- |
| | | | | |

Record the checkout, branch/commit, dirty state, runtime configuration/data owner, running process, and served bundle where relevant. Compare the current behavior with the latest intended CP behavior and any older rule at risk of resurfacing.

## Exact behavior contract

### Frontend, if affected

Name the existing CP reference screen and components. Specify reuse or refactoring, placement, grid and spacing, sizing, visual states, controls, navigation, and interactions. List every shared surface to verify. If a separate component is needed, explain the semantic difference. Include desktop screenshots or measurable UI assertions when appearance matters.

### Backend, if affected

Name the entry points and authoritative service/store. Specify request inputs, response outputs, persisted state, validation, error behavior, transaction/concurrency/retry behavior, migration, and recovery. State how old branches, defaults, or fallbacks will be retired. Include a concrete before/after example.

## Implementation sequence

1. [Change the existing owner and preserve the named behavior.]
2. [Update callers/shared surfaces and remove verified obsolete paths.]
3. [Add regression coverage and perform the required isolated/build/live gates.]

Identify dependencies and any step that requires separate authorization. Do not make product decisions during implementation that this plan leaves open.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| Motivating failure | | | | |
| Existing behavior to preserve | | | | |
| Another affected Movie/TV/IPTV/shared surface | | | | |
| Complete user-visible path across affected owners | | | | |
| Relevant adverse data that could violate a contract | | | | |
| Empty/loading/error or missing data | | | | |
| Relevant edge/conflict/retry case | | | | |

## Verification and rollout

- **Baseline:** Record existing test results and known failures before edits.
- **Focused tests:** Name commands, isolated environment, and expected checks.
- **Broader tests:** Name the full relevant suites and what their failures block.
- **Compiled UI:** State how the built desktop UI will be checked against the reference design and interactions.
- **Live work, only if approved:** State backup, process/config/data/bundle checks, visible verification, and rollback trigger.
- **Reporting:** Separate source changes, isolated verification, and live verification. Report exact counts, skips, failures, and remaining uncertainty.
- **Contract comparison:** Compare implemented and observed results with each approved contract. State any remaining difference and its user impact even if tests pass.
