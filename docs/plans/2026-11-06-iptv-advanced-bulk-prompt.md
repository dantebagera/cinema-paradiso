# IPTV advanced bulk prompt

**Status:** Implemented and verified offline on 2026-11-06; not live activated. Dante: “ok so lets go with the advanced prompt”. This implements the exact prompt compared in the 100-title timing experiment, without changing verification or launching a live job.

## Problem and decision

- **What happens now:** `services/chatgpt_skills.py` supplies short classification/title instructions to the bulk runner. Prefixes, alternate languages, collection labels, and differing release years need explicit guidance.
- **What Dante wants:** Use the tested advanced instructions on the first GPT request, avoiding a routine second pass just to supply better instructions.
- **Confirmed:** The 100-title standalone comparison used the exact current basic prompt. Two requests per prompt averaged 72.0875 seconds / 7,075 tokens for basic and 73.13 seconds / 7,418 tokens for advanced. These exclude CP preparation, TMDB verification and application, and do not prove accuracy on Egysat.
- **Evidence:** `C:/Users/dante/AppData/Local/Temp/cp-iptv-100-title-timing-aowpf4ya/experiment.json` and `RESULT.txt`. Approved advanced prompt SHA-256: `a281c1445f51ccbeed985352df62fc8d7a080f3a75523942a0bc6a1185abaee4`.
- **Open decisions:** None for the prompt substitution.
- **Scope:** Bulk GPT instructions and focused regression coverage. No UI, batch-size, model, retry, verifier, catalogue-write, activation, commit or release changes. Dante's earlier decisions about automatic recovery and automatic application remain pending implementation in their own work; this change does not revoke those decisions.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| First GPT instructions, this conversation | Handle provider noise and multilingual identities immediately | IPTV bulk metadata | Exact benchmarked advanced instructions | Yes, explicitly requested instruction change | “ok so lets go with the advanced prompt”, 2026-11-06 |
| Structured output and independent verification | Return title/category/year/aliases, not invented database IDs; verification decides eligibility | Bulk runner and movie service | Unchanged | No | Preserve |
| Persisted prompt version | A job pinned to different instructions cannot silently resume with the new protocol | Bulk jobs | Existing hash mismatch rejection remains | No | Preserve |
| Existing apply and recovery code | This scoped patch does not implement the separately discussed workflow changes | Bulk results/application | Unchanged in this patch | No | Pending separate implementation of earlier decisions |

The instruction change was explicitly selected after its exact text was tested. No additional approval is inferred for relaxed TMDB scoring or automatic writes. Existing tests of manual application remain regression coverage for the code currently outside this patch, not a rejection of Dante's newer automatic-application decision.

## Current design and ownership

| Responsibility | Current authoritative file/component/service | Entry point and callers | Behavior to preserve | Competing or obsolete paths |
| --- | --- | --- | --- | --- |
| Bulk prompt/schema fingerprint | `services/chatgpt_skills.py` | `IPTVJob._run_bulk` | Compact schema, input-as-data rule, no IDs | Replace the current prompt in place; no second production prompt |
| Batch execution/checkpoints | `services/chatgpt_iptv.py` | `IPTVJob.run` | 100-title default, repairs, budget, locks, resume guards | None added |
| Independent match verification | `services/iptv_movie_service.py`, `services/iptv_tmdb.py` | `bulk_source_proposal` | Candidate verification and existing review results | Known strict title/year limitations are not fixed here |

Baseline checkout is `master` at `be511f9`, with substantial existing dirty work. The prompt owner and bulk test module are existing untracked project files. Reuse this checkout and preserve unrelated changes. Data owner is the checkout's `data` directory. Current server child PID 38916 listens on 127.0.0.1:5000 and serves `index-BR6h-hEp.js`; source and loaded runtime remain separate. The recorded Lionz job is completed, with no unfinished F5 job found during inspection.

## Exact behavior contract

### Frontend

No frontend changes or new controls. No desktop layout or mobile work.

### Backend

Replace `IPTV_BULK_INSTRUCTIONS` with the exact tested advanced text, retaining the existing first paragraph. Guidance covers movie playlists including shorts/documentaries, provider labels and their misspellings, multilingual/slash aliases, meaningful sequel/title numbers, actor/director/character collection prefixes, official alternate titles, one-year release variation, and genuine identity uncertainty. Straightforward titles should be resolved directly. The model must not claim independent database verification.

For example, `Feel The Beat (2020) Malti Audio And Subtitle` should be interpreted as `Feel the Beat`, preserving the year. This instruction does not guarantee stochastic output or change whether the downstream verifier accepts it. In particular, the existing strict year/title gate remains a known separate limitation.

Keep input/output schemas, batch sizes, inference budget, repair behavior, provider/generation checks, manual locks and application logic unchanged. The existing prompt-plus-schema hash changes automatically. A job pinned to the previous hash must stop with `bulk_protocol_changed` before inference and retain its saved results. Completed job results remain readable. No migration or legacy prompt fallback is introduced. Rollback is restoring the prompt text and restarting only under separate live authorization.

## Implementation sequence

1. Record baseline tests and add a failing approved-prompt fingerprint test.
2. Add bulk-path coverage for the actual dispatched prompt, verified/review outcomes, no implicit application, and preserved results on old protocol rejection.
3. Replace the prompt in its authoritative owner with the measured text.
4. Run focused and broader offline tests, then review the scoped changes. No extra real GPT calls are needed because the exact text already has recorded real-provider measurements.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or evidence |
| --- | --- | --- | --- | --- |
| New bulk request | Dispatch | Exact benchmarked advanced prompt reaches transport | Bulk runner | Captured transport payload fingerprint |
| Deterministically resolved Film plus uncertain GPT interpretation | Process both fixture sources | Verified result skips GPT; unresolved source receives approved prompt and remains review; no catalogue application | Runner/service/store | Complete offline run |
| Uncertain interpretation | Process | Review outcome, no forced match | Runner/service | Complete offline run |
| Previous prompt job with saved results | Resume | `bulk_protocol_changed`, zero new inference, saved result preserved | Runner/job store | Resume regression |
| Input instructions or invented IDs | Validate | Input remains data; unchanged schema rejects extra fields | Prompt/schema | Existing schema and bulk validation suite |
| Locks, repairs, budgets, restarts and large batches | Run regressions | Existing behavior retained | Bulk owner | Existing bulk suite |
| Other GPT features | Load/run fixtures | Existing F1–F5 protocols remain valid | Shared skill owner | Broader GPT suites |

## Verification and rollout

- Baseline: 19 tests passed in `tests.test_chatgpt_skills` and `tests.test_chatgpt_iptv` before edits.
- Focused: new fingerprint and bulk integration tests, first red then green.
- Broader: offline `test_chatgpt_*`, `test_iptv_chatgpt_bulk`, and `test_ai_jobs` suites with a dedicated temporary `CP_TEST_ROOT`.
- Compiled UI: not applicable; no frontend changes.
- Live work: no restart, live matching, catalogue write or Egysat trial in this scope. The running server must reload the changed backend before it uses the new prompt.
- Reporting: distinguish source-only implementation and offline validation from the earlier real GPT prompt measurements. Do not claim the known verifier issue or automatic workflow changes are implemented.

## Execution record

- Baseline: 19 tests passed before changes.
- Red: all three new checks failed against the old prompt for the expected fingerprint/protocol change.
- Fixture corrections: identify uncertain response rows by source ID (the resolved source correctly skips GPT); request the review snapshot before asserting its applied count.
- Green: 22 focused checks passed. The production prompt exactly equals the measured advanced prompt.
- Initial broader run: 157 tests, 156 passed and one Windows multiprocessing credential-test launcher failure (`<stdin>` cannot be imported in the spawned process). Full log retained; this run is not described as a green full suite.
- Corrected normal `python -m unittest` runner: all 138 core ChatGPT/job tests passed. All 19 bulk tests passed in the initial run, including 40,000-proposal application and 25,001-source matching. No skips.
- Final independent review: no blocking findings; corrected the acceptance matrix to describe deterministic verified plus GPT review coverage accurately.
- Evidence and benchmark summaries: `docs/verification/chatgpt/iptv-advanced-prompt-2026-11-06/`.
- Live status: backend not restarted, no matching job launched, no catalogue changes, Egysat untouched. Prompt-only implementation; independent verification improvements and automatic application/recovery remain pending.
