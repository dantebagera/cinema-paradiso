# Automatic IPTV candidate recovery implementation plan

New bulk jobs now follow the [approved first-pass-only contract](2026-11-08-iptv-bulk-without-candidate-recovery.md). This plan records the earlier implementation and live trial.

**Status:** Approved for planning and implementation in a new task. Dante's instruction on 2026-11-08: “yes prepare a plan and implement it in a new task”. This follows the proposed flow of local matching, the current advanced GPT interpretation, one evidence-rich recovery pass for unresolved titles, independent verification, and automatic application of verified matches. Implementation and isolated validation are authorized; production activation, catalogue mutations during development, restarts, commits, pushes and releases are separate actions.

**Goal:** Recover defensible IPTV movie identities automatically without repeating the same unsuccessful matching loop or applying guesses.

**Architecture:** Extend the existing bulk runner, job checkpoint store, IPTV verification owner and Apply owner. GPT selects only from server-supplied TMDB candidates; the existing verification owner determines eligibility and the existing mutation path applies verified results. No second matching service or catalogue truth store.

**Tech stack:** Python services/SQLite, React/Vite, unittest and desktop Playwright.

**Execution:** Use the executing-plans skill for implementation. Follow AGENTS.md and this plan; no automatic commits. The user explicitly requested a new task, not a new worktree. Reuse the current local checkout and preserve its dirty work.

## Problem and decision

- The last Lionz job processed 2,661 sources, applied 1,673, left 985 review and 3 failed. The 2,509 Unmatched queue is a different source set; do not equate it with this job's residuals.
- Of 985 review rows, 809 had accepted GPT interpretations rejected by downstream verification. The previous owner-level correction recovered only 18/809 in a read-only replay. Its source changes already exist in this dirty checkout and must be preserved.
- The current advanced prompt cleans/interprets titles. It does not see the actual competing TMDB films or cached duration, cast, director and plot. Provider detail metadata sometimes describes a different film.
- A fixed, purposive 30-entry pilot gave GPT up to eight real candidates and supporting evidence. Two candidate orders produced the same 13 metadata-supported match recommendations, 16 review, and one no-candidate result. No wrong confirmations were found against predeclared references. All 23 rows with known reference identities selected that identity, but ten remained review. Seven rows had no defensible unique reference. This is not playback ground truth or a representative accuracy estimate.
- Current-prompt request: 33.842 seconds, 2,973 tokens. Candidate requests: 49.868/50.093 seconds, 34,697/34,700 tokens. These are 30-row GPT-only timings, not normal 100-title CP batches or cold-cache pipeline timings. The heavy input needs compaction and should be used only for leftovers.
- Pilot evidence: `C:/Users/dante/AppData/Local/Temp/cp-iptv-candidate-pilot-20261108/{report.txt,summary.json,experiment.json,reference.json,request-inputs.json,manifest.json,calls.json,candidate-a-response.json,candidate-b-response.json,evaluation.json}`. The reference hash is `27683667ce477ade4187bcbc25d1140b1fe971278510aca00c920b41ac38290f`. Preserve the pre-test references; do not relabel failures to make the implementation pass.
- Prior replay: `C:/Users/dante/AppData/Local/Temp/cp-iptv-recovery-20261107/`; previous plan: `docs/plans/2026-11-07-iptv-verification-recovery.md`.
- Scope: new bulk matching jobs, automatic recovery, validated automatic Apply, persisted diagnostics, desktop progress and queue refresh. Do not retrospectively run old jobs, scan Lionz/EgySat, or rewrite existing source metadata during development.
- No unresolved product choice blocks the stated scope. If implementation requires weakening a listed safeguard, raise that specific contract change and continue independent work. Do not ask again for the already approved recovery/automatic-Apply behavior.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior / exceptions | Affected callers | Proposed behavior | Change? / decision |
| --- | --- | --- | --- | --- |
| Dante's automatic matching flow | Local match, advanced GPT, then recovery for leftovers without asking for another stage | Bulk API/runner/UI | One automatic candidate-aware pass | Explicitly approved in current instruction and preceding discussion |
| Automatic Apply | Dante: “no need apply step after if it is confirmed then should be applied automatically” | New bulk jobs and existing Apply owner | Backend automatically applies verified film proposals, with durable receipts | Supersedes historical manual confirmation for these new jobs; explicitly authorized, do not request it again |
| Original title and release-year identity | Preserve meaningful title/sequel identity; primary year at most +/-1 when supplied | Bulk verifier | Richer corroboration may establish equivalence; never let GPT confidence waive year or sequel conflicts | Preserve; strict string equality is an implementation, not the agreed identity contract |
| Genuine rivals and incomplete search | Unresolved competing identities or search-cap exhaustion do not auto-confirm | Candidate preparation/verifier | Review with reason, even when GPT nominates a likely ID | Preserve |
| Manual locks and provider scope | Current source generation and locks govern mutations | Selection, verification, Apply | Recheck at inference admission and immediately before writing | Preserve |
| Cloud permissions and model | Existing account/model selection and sharing authorization | Transport/auth/provider | Reuse owners; no new credentials or silent model changes | Preserve |
| Bounded retries | No repeated substantive matching attempts until a guess wins | Runner/store | One recovery inference admission per source per new job; durable attempt tracking | Approved direction; technical failures do not reset attempts |

The former manual-Apply rule must not be reintroduced from old notes. Conversely, this authorization is not permission to apply to Dante's live catalogue as a development test. No global F5 single-source, Ollama, Movie or TV behavior change is intended.

## Current design and ownership

Baseline checked 2026-11-08: `C:/Users/dante/Desktop/cinema paradiso`, branch `master`, HEAD `be511f98846a67a182e5b371ad087938e9344362`, 385 dirty tracked/untracked paths before this plan. Configuration data root is checkout `data`; port 5000 is owned by PID 51196; HTTP serves `/assets/index-Cok6xiDI.js`. These facts do not prove that dirty source is active in the process. Recheck in the implementation task. No tests were rerun for this planning turn.

The knowledge index has no dedicated IPTV map. Use current code and the prior plan rather than manufacturing a knowledge-map claim.

| Responsibility | Authoritative owner and callers | Preserve / retire |
| --- | --- | --- |
| Launch and public snapshots | `services/ai_routes.py`, `ai_iptv_bulk_start`; `src/features/ai/useAIJob.js` or actual hook located from IPTV caller | Selection snapshots, request idempotency, provider/account authorization; update first-pass-only budget assumptions |
| Stage orchestration | `services/chatgpt_iptv.py`, `ChatGPTIPTVRunner._run_bulk` | Current advanced instructions, local path, pause/cancel; extend same state machine |
| GPT contracts | `services/chatgpt_skills.py` and bulk parser in `chatgpt_iptv.py` | Version/hash new recovery protocol separately; preserve other features |
| Checkpoints, request budgets, receipts | `services/ai_jobs.py`, `AIJobStore.add_results`, `reserve_inference`, `claim_bulk_apply`, `checkpoint_bulk_apply` | Atomic admission/checkpoint and idempotent writes; no parallel ledger |
| Provider facts, proposals, Apply | `services/iptv_movie_service.py`, `_source_title_evidence`, `bulk_source_proposal`, `apply_bulk_proposals`; `services/iptv_movie_store.py` | Read cached `detail_json` as well as normalized columns; no provider stream URLs in GPT payloads; existing lock/generation checks |
| Candidate search and identity verification | `services/iptv_tmdb.py`, `bounded_search_candidates`, `choose_automatic_match`, `_bulk_identity_conflict` | Hydrated real records, rival coverage and first-installment proof; replace overly literal bulk checks in this owner, not a runner bypass |
| Apply worker | `services/chatgpt_iptv.py`, `run_bulk_apply`; `AIJobStore.start_bulk_apply` | Reuse mutation/receipt semantics; support backend orchestration without an HTTP self-call |
| Desktop state | `src/features/iptv/IPTVBulkMetadataJob.jsx`, `IPTVMetadataProgress.jsx`, `IPTVProposalPanels.jsx`, `IPTVWorkspace.jsx` | Existing layout, controls, catalogue selection, optional review; remove new-job mandatory Apply confirmation |

## Exact behavior contract

### Backend: stage progression

1. Freeze selected keys and catalogue generation at Start. Process current local resolution first; retain the current advanced title interpretation for unresolved eligible sources.
2. Enqueue unresolved film candidates once for recovery after their first-pass result is durable. Include GPT uncertainty where source evidence still establishes a film context; do not promote uncertain classifications merely to run recovery. Exclude manual locks, explicit non-film categories, already verified/applied rows and permanently unavailable sources.
3. Reuse candidate searches/hydration already performed. Build evidence from the actual source and cached provider details. If no candidates exist, retain the explicit no-candidate outcome. A failed metadata fetch retains its error; do not fabricate an empty successful search. Search-cap and year-conflict rows may be diagnosed, but cannot auto-confirm.
4. Recovery returns one structured result per stable source index. Update the existing result identity rather than appending a second processed source. The processed count must never exceed selection total or double count a recovered row.
5. Independently verify each nomination in the TMDB owner. Persist original evidence, prior interpretation, chosen candidate, verification facts and final reason. A corrected model interpretation can supersede an earlier tentative interpretation, with history retained; it cannot overwrite or suppress conflicting original provider evidence.
6. Automatically apply eligible verified film proposals through the existing Apply owner after their batch checkpoint. Use backend-owned sequencing, not a frontend effect. Before completion, drain eligible pending writes. Partial successes remain durable on pause/cancel; no rollback of already confirmed writes. Apply failures appear separately from identity failures and must not trigger another GPT request.
7. Finish with applied/locked/skipped/failed and unresolved reasons. Recovery review/no-candidate is terminal for this job. No recursive recovery or automatic new job.

### Evidence and recovery protocol

- Add protocol/schema constants in `chatgpt_skills.py`; one recovery parser in `chatgpt_iptv.py`. Required output fields: string `id`, `decision` in `match/review/no_candidate`, integer-or-null `candidate_id`, numeric confidence, array of evidence-field names, and bounded factual reason. IDs must belong to that row's supplied candidate set. Reject duplicate IDs/JSON keys, unknown fields, invalid scalars, incomplete terminal streams and out-of-set nominations. Validate rows independently where structurally safe; malformed rows finish failed/review without another recovery call.
- Input contains original provider title/year, playlist context, detail title/year, duration, cast/director and plot; up to the existing eight candidate records with ID, title/original title/needed aliases, release year, runtime, language, credits and plot. Candidate order carries no authority. User/provider text is data, never instructions. No credentials, playback URLs or unrelated catalogue data.
- Compact redundant aliases/fields, retain eight cast names, directors, and plot excerpts sufficient for the conflict fixtures. Begin with provider plot <=360 characters, candidate plot <=240, up to four additional relevant aliases (canonical/original titles always separate). Never silently omit plausible competing candidates to fit a batch.
- Recovery batching is distinct from the 1–100 title first-pass control: at most 10 sources and 32,000 serialized Unicode characters per request. Split before admission. If one source cannot fit without losing material evidence, leave it review with `recovery_evidence_too_large`. Character limit is an engineering payload bound, not a claimed tokenizer measurement.
- Persist a hash of the submitted evidence/protocol and candidate IDs at admission. Completed decisions use that evidence version. If the catalogue changes, stop under existing generation rules; if metadata changes before Apply and invalidates verification, retain review/skip, not a stale nomination.

### Independent confirmation and conflicts

- Candidate must exist, belong to the submitted set, represent a film, and satisfy the original provider year +/-1 against primary release year when known. Regional release years may explain or preserve rivals but do not waive the primary-year rule.
- GPT confidence is advisory. Verify its claimed supporting fields against actual supplied/hydrated records. Copied cast/director/plot form one potentially contaminated metadata source, not three independent confirmations.
- Compare meaningful multilingual title identity against canonical/original/official aliases using existing normalization owners. Extend defensible equivalence in the owner with regression cases, including punctuation, Roman/Arabic part numbers and known subtitle forms. A shortened title needs independent corroboration and absence of a credible rival. Do not authorize arbitrary substring matches.
- Preserve sequel protection. `Student of the Year 1` requires the existing first-in-collection proof. Missing/additional installment numerals such as `Hellraiser III` or `Rendel 2` require actual subtitle/collection evidence establishing the same installment, not simply a close year or similar cast. If evidence cannot prove that, retain review even if the pilot recommended a match.
- Runtime supports identity and exposes contaminated metadata. Engineering comparison tolerance: max(3 minutes, 5% of the candidate runtime); unknown runtime supplies no corroboration. A larger unexplained difference prevents automatic confirmation in the recovery stage. This may correctly allow the prelabelled `Animal World` case (about five minutes on a 125-minute film); do not invent alternate cuts to excuse larger conflicts. A numerical tolerance never resolves evidence identifying another movie.
- Conflicting movie identities in source title/year/runtime versus detail title/cast/plot stay review: `Watching`, `Yesterday`, `Blues Brothers`, `Cars`, and `Sing` fixtures. Generic plots and a sole poorly documented candidate do not prove identity.
- Missing provider year is not a fabricated year: distinctive multilingual identity plus matching duration and specific supporting description may justify a nomination, as in `The Last Dance in Kippur`, provided no rival or conflict remains. Preserve any stricter established contract found during implementation and surface a genuine disagreement rather than weakening it silently.

### Persistence, limits and failure behavior

- Extend `bulk_work` in the existing cursor with versioned recovery pending/in-flight/completed state, evidence hashes, source attempt counts and current phase. Store nominations/facts in existing result evidence and mutation receipts in existing Apply records. Prefer additive JSON fields; no production migration script.
- New jobs explicitly record recovery-enabled and automatic-Apply semantics plus protocol hashes. Historical saved jobs retain their recorded semantics; loading history must never launch GPT or Apply. Preserve legacy explicit Apply for historical/manual proposals only, documented as compatibility with saved jobs, removable when those jobs no longer depend on it.
- Recovery has one admitted request per source/job and zero automatic recovery retries. Admission consumes the attempt durably before network I/O. On lost/incomplete response or crash after admission, show an interrupted/failed recovery result rather than silently spending another request. Resume can continue sources not yet admitted. Pause before admission spends nothing.
- Preserve first-pass repair limits (currently two invalid-output repairs) and bounded transient-error behavior; no successful row is resent for repair. All physical requests consume the same job-wide ledger. Keep the existing 10,000 absolute request ceiling.
- Compute automatic-stage allowance at Start rather than pausing merely because the former first-pass estimate was consumed. For selected count N, first-pass size B, repair size R=min(B,50), a conservative total ceiling is min(10,000, 3*(ceil(N/B)+2*ceil(N/R))+N): existing bounded transient attempts plus first-pass repairs plus at most one recovery admission per source. This is a maximum, not predicted consumption; actual packing/local successes use fewer calls. Do not silently expand a caller's explicit smaller call_budget. Show planned-stage estimates separately from this ceiling; pause with a precise reason at real account usage limits or an explicit exhausted ceiling.
- Respect pause/cancel/account switches and generation changes before each request/write. No new concurrency pool: existing inference slot, job lease and Apply serialization remain authoritative. A queued old Apply worker and new automatic Apply must not write concurrently.
- Auto-Apply is retry-safe: reuse stable operation IDs and receipts so a crash between write and checkpoint cannot duplicate a mutation. Failed writes remain visible and explicitly retryable through the existing control; never re-identify them with GPT.

### Desktop UI

- Extend `IPTVBulkMetadataJob` and `IPTVMetadataProgress` in their current locations; no new screen or mobile redesign. Keep Start beside selection details, existing spacing/buttons, optional proposal review, pause/resume/cancel.
- Show plain phases: checking local matches, interpreting titles, gathering recovery evidence, comparing remaining candidates, verifying selections, applying verified matches. Show per-stage source/request counts without incrementing total processed twice.
- State at launch that verified film matches apply automatically and one recovery pass is included. Label the current 100-title control as the first-pass size; do not imply recovery uses that size.
- New jobs need no Apply confirmation button for verified film matches. Preserve separate manual classification actions and historical/manual Apply functionality where still needed. Avoid removing shared ConfirmDialog code used by those actions.
- Completion distinguishes applied identities, unresolved identity review, missing candidates and write errors. Show an intelligible last-stage/reason in existing review rows. Optional review remains available.
- Refresh Catalogue review/counts on durable automatic Apply receipts, including partial jobs, and on completion. Current selection queue and previous-job scope remain separately labelled. Do not force unmatched and needs-review counts to equal one job's residuals.

## Implementation sequence

1. **Baseline and regression fixtures.** Re-read AGENTS, current owners and earlier dirty changes. Record baseline tests. Create sanitized minimal fixtures from the 30 pilot rows/references, removing real source identifiers and account data; preserve titles/candidates needed for the cases. Keep ordinary Movie/TV/Ollama/single-source contracts intact.
2. **Evidence preparation, schema and verifier.** Add failing tests for constrained IDs, malicious data, incomplete replies, mixed metadata, year/sequel/search guards and positive multilingual recovery. Implement compact preparation in the existing service, protocol/parser in their existing owners, and corroboration in `iptv_tmdb.py`. Do not accept the old strict veto in one branch and bypass it in another.
3. **Durable recovery stage.** Add runner/store tests for exactly-once admission, restart boundaries, invalid partial batches, pause/cancel, generation changes, usage limits and row replacement. Extend the existing state machine and public snapshots, including shared request accounting and finite allowance.
4. **Automatic Apply integration.** Add tests spanning verification -> durable result -> Apply -> provider store -> receipt -> public status. Refactor current Apply coordination for backend use; preserve locks, operation identities, revision safety, stop behavior and legacy job semantics. Completion cannot imply that pending or failed writes were applied.
5. **Desktop progress and count freshness.** Update the existing components/hooks and desktop e2e fixture. Test local-only success, recovery progress, automatic Apply with no confirmation, paused usage, cancellation, final unresolved reasons, write failure and catalogue count refresh. Retain history/manual paths explicitly.
6. **Evaluate compaction and complete verification.** Replay both stored candidate responses through the actual new verifier, not a standalone imitation. Compare compact versus full evidence on the fixed sample with a bounded isolated GPT evaluation if available: at most eight total physical requests, zero automatic retries, actual configured model/auth owner, no catalogue writes. Record latency/tokens separately for GPT, metadata retrieval and complete isolated pipeline. Preserve full candidate sets; if compact evidence loses correct decisions or accepts traps, correct preparation and report the limitation rather than expanding the live test budget.
7. **Report source-only delivery.** Update this plan with code/test evidence, explain any pilot nominations still rejected by justified contract guards, and name any remaining limitations. Stop before production activation/catalogue trials; no commit/push/release. No perpetual optional qualification loop.

## Acceptance matrix

| Scenario | Expected observable result | Owners / proof |
| --- | --- | --- |
| Easy local or advanced first-pass match | Zero recovery admissions; verified film auto-applies once | Runner/store/Apply integration |
| Bruiser, White Fox, Seire, Eden, Jacob's Ladder, Without Remorse, Arabic title, Code 8 II | Correct real candidate selected when supporting evidence satisfies guards; no arbitrary-ID nomination | Fixture verifier + runner |
| Rendel/Hellraiser/Student first-film label | Same installment independently proved; otherwise explicit review, never relaxed to cast/year alone | TMDB owner/collection fixtures |
| The Silly Boy versus 1936 nine-minute cartoon | No automatic match | Negative fixture |
| Watching, Yesterday, Cars, Blues Brothers, Sing mixed metadata | Review; swapping candidate order does not create an applied guess | Frozen traps + e2e reason |
| Clean 2020/2022, DDLJ 1955/1995, King's Daughter 2016/2022 | Preserve primary-year conflict despite plausible identity | Verifier/API assertions |
| El ott/Hero/Kingdom search limit | Preserve review until evidence actually establishes complete bounded search; GPT cannot waive cap | Search/runner fixtures |
| Frog Prince sparse record | No match from title/year plus generic plot alone | Negative fixture |
| Last Dance missing year, matching distinct titles/runtime/plot | Supported identity may verify without inventing provider year | Positive fixture |
| Animal World runtime ~130 vs 125 minutes | Small discrepancy alone is not a hard veto; same-year rival must still be excluded by actual evidence | Boundary +/- tolerance tests |
| Arabic comedy runtime 121 vs 95 minutes | Review with runtime discrepancy, no invented alternate cut | Negative fixture |
| Duplicate/foreign candidate ID or malformed/partial recovery response | Invalid rows not applied or automatically resent; completed valid rows retained | Parser + runner |
| Pause/cancel before and after request admission; crash after response/write | No repeated admitted recovery; no duplicate Apply; accurate interruption/receipt state | Fault injection/store integration |
| Provider/account/config/generation changes or manual lock added | No stale inference/application; clear stop/skip reason | Permission/store integration |
| Budget/usage cap, no candidates, failed TMDB fetch | Distinct terminal or paused reasons; no infinite retries | Runner/status/e2e |
| One source passes both stages | One result identity and one processed source; immutable history of stage decisions | Store counts/API |
| Automatic Apply receipt while UI open | Applied count and provider catalogue filters refresh; no mandatory confirmation dialog | Backend + desktop e2e |
| Old completed/paused/manual jobs loaded | No newly activated GPT/automatic writes; compatible explicit controls | Legacy regression |
| Unrelated ordinary matching, classification, Ollama, Movie and TV | Existing contracts remain intact | Existing focused/broader suites |

## Verification and rollout

- Tests must use `CP_TEST_MODE=1` and a unique temporary `CP_TEST_ROOT`; never instantiate production stores for a test. Read production evidence only through SQLite `mode=ro` if necessary. Do not import `app.py` against the real data root.
- Focused baseline and final: `.venv/Scripts/python.exe -m unittest tests.test_iptv_bulk_identity tests.test_iptv_chatgpt_bulk tests.test_chatgpt_iptv tests.test_ai_jobs tests.test_ai_routes tests.test_chatgpt_skills` with the isolated environment. Extend the existing test modules or add a focused recovery module and include it explicitly.
- Broader: relevant `test_chatgpt_transport`, `test_ai_provider_preservation`, existing IPTV service/store/selection tests located with `rg --files tests`, and all callers changed by Apply refactoring. Record pre-existing failures separately; never weaken expectations just to pass.
- Compiled desktop gate: use the repository `tools/run_playwright_e2e.ps1` isolated dist/data setup for `tests/e2e/iptv-chatgpt-bulk.spec.js`; inspect its arguments before invocation. Build with `npm.cmd run build -- --outDir <unique temporary dist>` if a separate build is needed. Do not replace the currently served production dist during this source-only task.
- Pilot success is at least preservation of the 13 supported nominations at the model-selection level, no unsafe confirmation among the 16 predefined caution cases, and honest reporting of any stricter production-verifier rejection. Do not claim all 13 auto-apply if independently verified installment evidence is still missing. Animal World's predeclared reference already allows a match, so a justified additional recovery is not relabelling the pilot.
- Runtime limits and payload size are engineering starting values, not evidence of production throughput. Report measured input/output/cached token counts and elapsed times; do not extrapolate 30 difficult cases to thousands as a guarantee.
- A new live scan, restart/activation, or catalogue Apply is not part of implementation qualification. For a separately approved live rollout, record provider-specific backup/recovery, process/config/bundle provenance, old-job behavior and visible confirmation before claiming live success.
- Final report: changed owners, approved contract comparison, exact test outcomes, model-evaluation results and remaining gaps; state whether source-only, isolated-tested, or live. Link this plan and bounded evidence report.

## Implementation evidence

- The work used the existing dirty `master` checkout at `be511f98846a67a182e5b371ad087938e9344362`. It had 386 dirty paths at handoff, including this plan. The corrected isolated baseline ran 90 tests in 327.463 seconds and passed. The initial invocation pointed at a temporary directory that had yet to be created. Its setup errors were superseded by the corrected run.
- New bulk jobs opt into a versioned recovery protocol and automatic Apply at launch. The existing title interpreter runs first for eligible leftovers, and the recovery admission and shared request debit are one SQLite transaction. A complete model response is saved before verification. The worker replaces the existing result and keeps its first-pass reason, submitted evidence hash, candidate set and independent verdict. A lost response settles the admitted source without resending it. The launch estimate describes first-pass batching while the ceiling includes repairs and recovery. An explicit smaller ceiling remains in force.
- The existing TMDB verifier and provider Apply owners enforce the release-year tolerance, installment proof, search bounds, competing identities, runtime and conflicting details. The bounded search also flags a plausible rival discarded by a per-query or hydration limit. A canonical sequel number takes precedence over a misleading unnumbered alias. A source-added part number with an exact official subtitle can verify only with an unambiguous collection release order. Existing first-film proof still requires all collection parts to be dated.
- Automatic Apply serializes with the existing bulk Apply worker and uses its receipt and retry path. It writes an automatic film match without creating a manual lock. It checks account, model, configuration and provider generation again, and compares source and match revisions inside the provider transaction. The chosen TMDB record and any localized-title or collection proof are checked again. A prior receipt is reconciled before considering any new write. Historical jobs retain explicit Apply and current manual classification and manual search remain available.
- Desktop Metadata shows stage counts, a cumulative automatic Apply summary, and terminal review reasons. A durable receipt refreshes the catalogue and current selection. The saved job still shows its own queue. The desktop regression for dropped status reads now binds its classification assertion to the actual saved checkpoint. The first run had six passes and a fixture timeout from a hardcoded count. The corrected nine-case run passed in 1.3 minutes. It covered automatic Apply and catalogue refresh, usage pause and cancel, an explicitly retried catalogue write with no extra GPT call, and the saved-job confirmation path.
- Independent code review reproduced two safety issues during implementation. An unnumbered alternate alias could hide a sequel number and an omitted sixth search result could hide a genuine rival. Both now have regression coverage. Crash and fault coverage includes a lost admitted recovery, a saved response across restart, partial replies, lock changes, configuration and generation changes, budget and usage pauses, cancellation after admission, provider metadata changes, provider commit before receipt checkpoint and the gap after the last receipt was checkpointed.
- Focused final command used `python -m unittest` with `test_iptv_candidate_recovery`, `test_iptv_bulk_identity`, `test_chatgpt_iptv`, `test_ai_jobs`, `test_ai_routes`, `test_chatgpt_skills`, `test_chatgpt_transport` and `test_ai_provider_preservation` under `tests`. All 107 tests passed in 33.696 seconds with a unique `CP_TEST_ROOT`. A separate 179-test run, before the final collection-order and first-pass-repair additions, passed in 96.030 seconds and also included IPTV service, routes, provider manager, movie enrichment and movie-gate suites.
- The broader run also included the full `test_iptv_chatgpt_bulk` lifecycle and large-selection suite. All 194 tests passed in 652.163 seconds. That process started before the final admission-lock, collection-order and first-pass-repair refinements. The 107-test final run covered those refinements on the final source.
- The final frontend build served `index-iYgNzJzz.js` in the isolated Playwright process. The nine desktop scenarios passed in 1.3 minutes. The [completed desktop screenshot](<C:/Users/dante/AppData/Local/Temp/cinema-paradiso-playwright-bc897796ff9d41f18b33f26dfc9bb646/iptv-recovery-completed.png>) shows the selected queue at one source and the saved job at three processed, with two automatic receipts and one missing candidate.

### Frozen pilot and compact payload

All eight physical requests used the configured `gpt-6.1-sol` account and transport with zero automatic retries. Each order used four batches of 9, 7, 10 and 4 rows. Every original candidate ID was retained. Serialized batch lengths were 30,646, 31,306, 21,525 and 22,236 Unicode characters. The final alias selection considers all language segments, and an offline comparison showed identical payloads for these 30 rows.

| Input and order | Valid rows | GPT seconds | Input tokens | Output tokens | Cached tokens | Known identities nominated | Verified match decisions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Original rich pilot A, one 30-row request | 30 | 49.868 | 32,362 | 2,335 | 0 | 23/23 | 11 |
| Original rich pilot B, one 30-row request | 30 | 50.093 | 32,363 | 2,337 | 0 | 23/23 | 11 |
| Compact A, four sequential requests | 30 | 71.536 | 29,261 | 3,123 | 0 | 23/23 | 11 |
| Compact B, four sequential requests | 30 | 74.103 | 29,264 | 3,116 | 0 | 23/23 | 10 |

- Both compact orders nominated the same 13 identities recommended by both original runs. Compact A recommended matching all 13. Compact B retained the correct Lebanese film `ع مفرق طريق` as a nomination but changed its decision to review. The independent verifier accepts that nomination when the model recommends matching. No predefined caution case was recommended for matching or verified in either compact order. There were 16 caution cases.
- The frozen evidence leaves **Student of the Year 1** and **Rendel 2** in review. Student's cached collection contains an undated third part, so it cannot prove the unique earliest film under the existing rule. The frozen Rendel set lacks collection chronology. An isolated collection fixture verifies an exact subtitle and the second release when both are proved. **Hellraiser III** passed through the distinctive official subtitle. **Animal World** was nominated for matching in both compact orders. Its 5.317-minute difference is within the 6.25-minute tolerance, but the available multilingual description and absent credits did not independently establish supporting evidence. It stays in review.
- Compact orders used about 6.7% fewer total tokens than the original 30-row requests and took longer sequentially. Batching, instructions and ordering varied, so this cannot isolate the effect of compaction on model decisions or predict production throughput. These were deliberately difficult metadata references, without playback ground truth.
- Qualification reused prehydrated evidence with zero TMDB HTTP requests. Reading the cached inputs and replies took 0.002235 seconds. Offline read, compaction and replay of all four response sets took 0.088849 seconds. A timed isolated two-source job took 0.260995 seconds through both provider receipts. It made eight in-memory TMDB calls taking 0.000008 seconds and two fake GPT transport calls taking 0.029364 seconds. The desktop suite also verified the provider-write path in isolated data. Cold-cache end-to-end latency remains unmeasured.
- Evidence is in [the original pilot report](<C:/Users/dante/AppData/Local/Temp/cp-iptv-candidate-pilot-20261108/report.txt>) and the [final offline replay](<C:/Users/dante/AppData/Local/Temp/cp-recovery-qualification-c188fac8-befe-4c8d-b8b6-c72254975e5f/final-replay.json>).

### Live boundary

The final read-only check still found PID 51196 serving `/assets/index-Cok6xiDI.js` on port 5000. Delivery is source plus isolated qualification. Production catalogue, live runtime and served bundle were outside this implementation gate.

## Approved live Lionz trial

Dante approved the separate production activation and one 100-title Lionz Needs review trial on 2026-11-08. The online SQLite backup captured 41,316 available Lionz sources and passed `quick_check`. The previous frontend was retained alongside it. CP stopped through its graceful application shutdown path and returned on PID 44856 with the desktop-qualified `index-iYgNzJzz.js` bundle. qBittorrent stayed on PID 16480 with both active downloads preserved at restart. The older Lionz job still reported completed, 27 requests and legacy Apply semantics after activation.

- The trial used a fixed-seed sample of 100 films from the 988-title Needs review queue. All 100 were review results in the previous job. This is one sample of that queue.
- Job `7923352b97b34ffd8b60c453571bbf07` completed all 100 titles in 542.083 seconds. The first ChatGPT admission was observed at 172.94 seconds and recovery preparation at 297.98 seconds. Recovery through completion took approximately 244 seconds.
- One match applied from the local pass and eight from recovery. The advanced title pass added zero. Twelve physical ChatGPT requests were recorded, one for title interpretation and 11 for the 98 recovery admissions. The advanced pass left one additional film-queue source outside recovery because its model interpretation classified it as Misc.
- All nine receipts matched provider catalogue records with automatic status and no manual locks. There were zero write failures. A metadata spot check of all nine supported their selected identities, including the installment proofs for Elite Squad 2, Death Race 4 and Attack on Titan 3. The spot check used provider and TMDB records.
- The queue fell from 988 to 979. The trial ended with 86 review results and five no-candidate results. The most common recovery reasons were primary-year conflict for 37 rows and incomplete rival search for 34.
- A retrospective check of the submitted evidence found 75 of 98 recovery admissions already barred from automatic confirmation. Thirty-six had incomplete searches and 41 had no candidate with a compatible primary release year. Two satisfied both conditions. This identifies avoidable GPT work if CP checks those conditions before admission. It does not predict the new batch packing or the time spent gathering evidence.

[Activation record](<C:/Users/dante/AppData/Local/CinemaParadiso/rollout-backups/iptv-recovery-20261108-005606-5db25490/activation.json>) · [Pilot results](<C:/Users/dante/AppData/Local/CinemaParadiso/rollout-backups/iptv-recovery-20261108-005606-5db25490/summary.json>) · [Metadata audit](<C:/Users/dante/AppData/Local/CinemaParadiso/rollout-backups/iptv-recovery-20261108-005606-5db25490/metadata-audit.json>) · [Lionz catalogue backup](<C:/Users/dante/AppData/Local/CinemaParadiso/rollout-backups/iptv-recovery-20261108-005606-5db25490/lionz-movies-before.sqlite>)
