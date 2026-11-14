# Resumable ChatGPT bulk job for IPTV Metadata

**Status:** Implemented and verified in isolation on November 5, 2026. Dante approved source implementation and isolated verification when he asked, “ok sounds like a plan, make the plan and implement it in a new task.” The handoff records the decisions below.

## Problem and decision

- **What happens now.** The review workspace and `IPTVMovieStore.resolve_selection` reject more than 5,000 sources. The existing F4 and F5 jobs reserve up to 24 ChatGPT calls per explicit Continue. A filtered selection of 6,413 therefore cannot start, and splitting it would require repeated launches and continuations.
- **What Dante wants.** Start one job for the fixed provider selection with an explicit call budget. CP runs automatically, checkpoints review proposals, and shows progress against the original total. Pause, Resume, Cancel, and Apply are distinct actions.
- **Confirmed.** In the offline-scored Lionz pilot, title-only batches of 25, 50 and 100 took 17.922, 28.766 and 54.719 seconds and reported 1,755, 3,278 and 6,237 tokens. Both 100-row variants classified 100/100 and independently verified 76/80 films with zero wrong verified matches. Asking for IDs cost 65.219 seconds and 6,843 tokens, saved eight TMDB lookups, recovered no extra matches, and returned two wrong real IDs that CP rejected. At that mix, 6,000 titles extrapolate to 60 requests and about 374,000 tokens before retries or local shortcuts. The pilot's rough weekly-usage projection is not a known quota.
- **Open decisions.** None in the approved scope. Implementation choices are listed below. The exact quota and refresh time depend on the account and upstream response.
- **Scope.** IPTV Metadata desktop and the provider-local backend. Source work and isolated verification only. Live inference, production build replacement, restart, live catalog changes, commits, pushes and releases are separate.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| Handoff and existing IPTV selection | Legacy actions cap selection at 5,000 | IPTV review and AI Control | A separate bulk Start accepts larger snapshots. Legacy actions retain their limit. | Approved bulk exception | Fixed provider selection of 6,413 or tens of thousands |
| Existing AI job reservation | Legacy jobs reserve 24 calls per explicit run | F1–F5, including nested calls | Bulk reserves against the user-entered cumulative ceiling and never renews it automatically | Approved bulk exception | One Start and explicit budget |
| IPTV title sharing and provider ownership | Account consent, provider isolation and source generation bind the job | Start, requests, Resume and Apply | Same checks through the existing owners | No | Preserve |
| IPTV metadata categories and locks | Sports and Music use provider metadata. Plays retain source identity with explicit TMDB lookup. Manual decisions remain protected. | Native review and catalog | Bulk categorizes non-Film sources. Verified Film and category proposals require Apply. Play search uses the existing manual path. | No | Preserve |
| Existing F5 verification | Use real candidates and deterministic title, year, ambiguity and lock checks | IPTV match proposals | Provider IDs must pass the current ID check. Model titles and aliases seed searches only. Suggested years remain advisory so a guess cannot narrow the set of competing releases. Only CP evidence can verify a candidate. | No | No GPT IDs, unchanged thresholds |
| Completed Responses transport | Existing tool callers require terminal function calls | All ChatGPT features | Add opt-in text reconciliation only for the bulk request. Require a genuine successful completion and validate the JSON in the IPTV owner. | No | Recover completed text-only responses for bulk |

## Current design and ownership

| Responsibility | Current authoritative owner | Entry point and callers | Behavior to preserve | Competing or obsolete paths |
| --- | --- | --- | --- | --- |
| Provider selection | `IPTVMovieStore.resolve_selection`, `review_queue` | Metadata selection routes | Provider DB, source keys, queue filters and generation | Keep legacy mode. Bulk reads filtered keys in one provider DB snapshot. |
| Job scheduling, inference reservations and results | `ai_routes.py`, `AIJobService`, `AIJobStore` | Local AI API and `app.py` composition | Ownership, idempotent start, inference slots, explicit continuation and cancellation | Bulk adds a job mode on F5 without a separate scheduler or database. |
| GPT prompt and validation | `chatgpt_iptv.py`, `chatgpt_skills.py`, `chatgpt_transport.py` | IPTV job and OAuth transport | Strict legacy tools, existing response limits, title redaction | Bulk uses a versioned compact text contract and the same transport. |
| Classification, TMDB and catalog writes | `iptv_movie_classifier.py`, `iptv_tmdb.py`, `IPTVMovieService`, `IPTVMovieStore` | Provider-local preview and manual actions | Locks, source generation, existing TMDB verification and Play flow | Reuse these owners. Save bulk review rows in the existing AI results table. |
| Desktop | `IPTVWorkspace.jsx`, `IPTVProposalPanels.jsx`, shared AI job hook | IPTV Metadata | Existing queue, toolbar, metadata progress styling, review and Apply controls | Keep legacy actions and add the distinct bulk action. |

The working checkout is `C:\Users\dante\Desktop\cinema paradiso`, branch `master` at `be511f9`. Baseline status had 144 modified, two deleted and 217 untracked paths. The relevant ChatGPT work is uncommitted. The running backend was Python PID 24684 on port 5000, launched with `app.py`. The configured data root is the checkout's `data` directory and the served entry was `/assets/index-Eu1d5VGM.js`. Source edits use the current checkout. Runtime verification uses a temporary test root and separate build output.

## Exact behavior contract

### Frontend

Add a ChatGPT bulk Start form in the Metadata review workspace under the selection and legacy actions. Require an integer budget with no prefilled authorization. Label the 5,000 warning as a legacy limit. Display one whole-job progress track using the Metadata dashboard's track and legend classes. Show processed/total, verified proposals, unmatched, categorized only, needs review and failed. Surface the call budget and waiting, backoff, plan-usage, pause and interruption reasons next to the controls. Resume keeps the remaining budget unless Dante explicitly adds calls. Keep the current job visible across queue changes and restore it by account and provider on reload. Render results in pages using the native classification and match panels. Explicit Apply operates on checked proposals from the visible page. Plays use existing Manual search after classification is applied.

### Backend

Add provider-scoped `POST /movies/ai/bulk-jobs` and a read endpoint for the latest bulk job. Start accepts the existing selection fields plus `call_budget` and `request_key`. The fixed source keys and catalog generation are stored once. Resource guards allow up to 100,000 sources and an explicitly authorized cumulative ceiling of up to 10,000 calls. Start is idempotent and a second active bulk job for the same account and provider is rejected. The scheduler runs one bulk worker alongside the regular AI workers, all using the same inference slots. Generic AI status provides paged results and compact bulk progress. Bulk Pause and Resume require the current run or revision. Cancel stops work and retains review results. Resume never raises the budget by default. Bulk Apply resolves IDs against saved results for that provider/job and checks category, locks and generation at the write. Both reads and writes reject a provider projection in progress, when rows can have changed before the next generation becomes visible.

Reuse local classification and existing TMDB parsing and verification before requesting interpretation where practical. Send up to 100 compact rows with a stable short ordinal ID, title, optional playlist and year. Require category, cleaned title, year, aliases, confidence and uncertainty, with no external IDs. Reject duplicate and foreign IDs. Validate each remaining row. Commit valid rows and split repair groups into at most 50, with at most two repairs per source. Missing or invalid rows after repair become failed. Valid uncertain rows become needs review. Sports, Music, Plays and Misc receive category proposals, with no automated identity change. Only independently verified Film identities are selectable as match proposals.

The existing SQLite job owns the cumulative reservation counter and batch cursor. Persist valid model output and the bulk prompt protocol identity before TMDB processing. Insert proposals keyed by source and advance the cursor and counters in the same transaction. Read progress and results from one database snapshot. An explicit Resume after restart uses the unfinished checkpoint. An interruption between request dispatch and durable receipt can repeat only work whose response was never recorded. Reserve one call per upstream attempt, including throttled or lost requests. On temporary ChatGPT throttling, wait up to 30 seconds between attempts and pause after three consecutive temporary failures. Pause is cooperative at a safe checkpoint. Plan exhaustion pauses immediately with a provider-usage reason. Results remain reviewable. Source generation change invalidates remaining work and stale proposals.

No migration of existing job rows or IPTV databases is needed. For example, 6,413 selected sources remain the denominator after the first 100 finish, after a 24-call budget pause, and after a process restart. Resuming with ten extra calls raises the cumulative ceiling by ten and leaves already recorded proposals alone.

## Implementation sequence

1. Add failing tests for completed stream reconciliation, bulk admission and checkpoint/budget semantics. Implement the existing transport's scoped text recovery and the bulk prompt/row validation.
2. Extend the selection, job and provider metadata owners. Add the runner and explicit Apply using the existing provider transaction checks.
3. Wire the existing desktop workspace, job polling and native panels. Add browser assertions on a temporary compiled build with offline fixture inference.
4. Run focused and broader checks, compare the acceptance matrix, and report remaining differences before any separately approved activation.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| 6,413 and 25,001 filtered sources | Select all and Start | Fixed total above 5,000; legacy actions still reject it | Selection store and API | Synthetic provider DB and desktop |
| Budget smaller than workload | Start then Resume with extra calls | Automatic batching, exact ceiling, same job and original total, no duplicated proposals | Job store and runner | Offline transport fixture |
| Temporary or plan throttling | Return upstream throttle or usage error | Bounded automatic wait for temporary errors, explicit pause for plan usage | Transport and runner | Offline error fixtures |
| Process interrupted after a checkpoint | Resume | No repeat of committed sources or recorded interpretation | Job store and runner | Interrupted-job fixture |
| Missing, invalid, duplicate or foreign output rows | Complete stream and repair | Safe rows survive, repairs at most 50, exhausted rows visible as failures | Row validation and runner | Offline transcript fixtures |
| Terminal text absent or inconsistent | Stream deltas then complete or truncate | Accept only consistent text after successful completion, reject truncation and mismatch | Transport | SSE fixture and legacy tool regressions |
| Cross-provider or changed generation | Resume or Apply | No title disclosure or catalog write to another provider, no stale Apply | API, service and store | Two providers and stale snapshot |
| Sports, Music, Play and manual locks | Review and Apply selected proposals | Classification only for Sports/Music/Play. Existing explicit Play lookup preserves Play. Locked decisions survive. | Native panels and provider store | Service and desktop fixtures |

## Verification and rollout

- **Baseline.** Run targeted AI jobs, ChatGPT IPTV and transport, IPTV gates, enrichment and UI tests under an isolated `CP_TEST_ROOT`.
- **Focused tests.** Run `python -m unittest tests.test_iptv_chatgpt_bulk tests.test_chatgpt_transport tests.test_chatgpt_iptv tests.test_ai_jobs` in test mode with an empty temporary root.
- **Broader tests.** Run relevant ChatGPT and IPTV unittest modules and the IPTV JavaScript tests with offline fixtures.
- **Compiled UI.** Use Vite's explicit temporary output directory and desktop Playwright against loopback fixtures. Assert selection, budget, control transitions, counts, progress and explicit Apply.
- **Live work.** Requires separate approval.
- **Reporting and contract comparison.** Report exact isolated pass/failure counts and state which behaviors were exercised on the built desktop. Record any gaps and confirm the live baseline separately.

### Isolated verification results

- The targeted pre-edit baseline passed 92 Python tests. The final bulk suite passed all 10 cases, including a full 25,001-source run with 251 offline model requests and one saved outcome per source. The run completed automatically under the explicitly supplied 251-call budget.
- CP's virtual environment passed all 344 broader AI, ChatGPT and IPTV Python tests. A system-Python run passed the bulk cases and could not load two auth modules because PyJWT was absent there. Both auth modules passed in the virtual environment. The IPTV JavaScript suites passed all seven tests.
- The temporary Vite build passed all 19 compiled desktop Playwright scenarios with the offline AI fixture server. The bulk test started from 6,413 sources, retained the original total across budget pause, reload, Resume, Pause and Cancel, rejected a cross-provider Apply, and explicitly applied both categories and a verified film. It also exercised result paging. Earlier fixture runs exposed two seeding issues, unstable ordering across projection batches and mismatched counters from direct SQL. The final fixture sets match states through the IPTV store.
- The running CP process and served bundle matched the baseline during verification. Upstream plan exhaustion, throttling, and completed text recovery were exercised with offline fixtures.
