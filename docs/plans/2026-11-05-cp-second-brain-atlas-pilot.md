# CP Second Brain and Atlas pilot

**Status** · Proposed in chat on 2026-11-05. Dante selected TV Follow and explicitly approved the documentation pilot, including the Karpathy workflow, on 2026-11-06. The pilot is in the working checkout. The goal after the pilot is coverage across CP, one area at a time.

## Problem and decision

Decisions, plans, code, and verification already exist in CP. Reviewers need a starting point that distinguishes what Dante approved, where the code lives, and what evidence covers it. The pilot provides a linked Second Brain page and an Atlas map for TV Follow. Codex will use the [maintenance workflow](../knowledge-workflow.md) to update them from their sources. Git-versionable Markdown is the storage format, Mermaid supplies the flow diagram, and Obsidian is an optional reader.

## Contracts affected and contract-change decision

| Contract | Authority | Pilot impact |
| --- | --- | --- |
| Draft and explicit Start, target scopes, retry timing, packs and review, one-shot paths | [TV contract and decision log](../tv-contracts.md#decision-log) | Document the agreed rules and the corresponding code. Product behavior is outside the documentation scope. |
| Evidence and approval boundaries | [CP work rules](../../AGENTS.md) | Add a navigation pointer and a maintenance procedure. Record evidence at its actual scope. Existing authorization rules apply to future edits. |

## Current design and ownership

- **Checkout observed on 2026-11-06** · `C:/Users/dante/Desktop/cinema paradiso`, `master`, `be511f9`. Git status before edits showed 145 modified entries, two deletions, and 226 untracked entries, including local TV Follow code, contract, and tests. The pilot uses that checkout because the map must describe those sources. Its new documentation paths were absent, and `AGENTS.md` was clean before the pointer was added.
- **Source owners** · `TVMonitoringControls` and `tv_routes.py` lead to `TVMonitoring`. `TVAcquisition` owns TV release selection and publication. The qBittorrent manager owns transfers. `AcquisitionRepository` and `TVServices` open separate SQLite stores from the user data directory selected by `app.py`. The Atlas covers the legacy immediate-monitoring API and separate manual and bulk paths. [Code map](../atlas/tv-follow.md)
- **Live baseline** · A read-only observation on 2026-11-06 found `python.exe` PID `38916` listening on `127.0.0.1:5000`. The homepage served `/assets/index-BR6h-hEp.js`. Follow tasks, effective live data/config values, and live acquisition behavior were outside that observation.
- **Historical evidence** · The download contract and season-pack reports document isolated results and full-suite limitations. [Download contracts](../verification/tv-download-contracts.md) · [Season packs](../verification/tv-follow-season-packs/README.md)

## Exact behavior contract

From `AGENTS.md`, the knowledge index leads to both topic pages. The Second Brain links each decision to its authority and distinguishes approved, superseded, observed source, isolated evidence, and live evidence. The Atlas uses file links and stable symbols to connect entry points, owners, stores, and scenario-specific checks. The pages link to one another. Codex uses the documented update, query, and drift-check steps and appends one log entry per material update. The existing desktop and backend behavior remain the subject of the guide. The pilot modifies documentation only.

## Implementation sequence

1. Write the Second Brain index and TV Follow decision page. Cite the current rule, the superseded retry proposal, and the limits of verification.
2. Write the Atlas index and TV Follow map. Trace Preview, Save, Start, status, scheduling, source review, transfer and import, and adjacent flows through their existing owners.
3. Link both through `docs/README.md` and `AGENTS.md`. Put the shared procedure in `docs/knowledge-workflow.md` and the chronological record in `docs/second-brain/log.md`.
4. Check links, named symbols, routes, tests, and the review scenarios below. This approval covers documentation in the current checkout. App changes, runtime actions, dependencies, commits, and publishing are outside the pilot.

## Acceptance matrix

| Scenario | Expected result |
| --- | --- |
| Start a review from `AGENTS.md` | Reach both TV Follow pages and the maintenance procedure from the index. |
| Save appears to do nothing | Locate the agreed draft behavior and trace Save and Start to separate route handlers and tests. Recognize the legacy API as a separate entry point. |
| An old note says six hours | Mark the source-retry proposal superseded. Find the approved five hours, separate six-hour metadata refresh, Cairo first-search rule, and regression tests. |
| Follow chose a pack or asked for review | Find the approved conditions, source and transfer review boundaries, and verified import path. Identify the pack and review tests. |
| Someone selects Download all | Reach lower manual release review and identify the separate Library one-shot path and its tests. |
| Someone asks whether the rule is live | Find the dated scope of source inspection and historical isolated evidence. Report live Follow behavior as unverified. |
| New evidence disagrees with a page | The workflow explains where to record the difference and its sources. The superseded retry proposal demonstrates the distinction. |

## Verification and rollout

Use read-only Python and `rg` checks for local Markdown targets, heading anchors, and Atlas symbols, then walk each acceptance scenario from the index. Use `git diff --check` and inspect the scoped status to confirm the pointer and documentation changes. Existing regression and desktop tests are mapped for future behavior changes. This documentation gate does not exercise the app, compiled desktop, or live Follow tasks. Product-wide expansion is a later phase.

**Pilot verification, 2026-11-06** · The documentation check initially reported the missing deliverables. With the pilot in place, it passed across eight new Markdown files, 63 local link targets, 32 named definitions, and 11 route bindings. It checked the approved retry, separate metadata interval, navigation, and whitespace. A fresh read-only review walked all seven acceptance scenarios and found no issues in scope. The verification covers the guides and their references. Current live Follow behavior remains unverified.
