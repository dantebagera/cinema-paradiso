# End new IPTV bulk jobs after the title pass

**Status** Live verified on 2026-11-08. Dante approved the targeted change, isolated tests, and live activation with “go” following the explicit contract-change notice.

## Problem and decision

The live 100-title Lionz trial took 9 minutes 2 seconds. Candidate recovery added approximately 4 minutes 4 seconds and eight additional verified matches. New IPTV bulk jobs should run local matching and the existing ChatGPT title pass, then settle automatic Apply and finish. Unresolved titles stay available for review. See the [live trial](2026-11-08-iptv-candidate-recovery.md#approved-live-lionz-trial).

The activation does not include a live scan or a catalogue write. The nine completed trial matches and the saved trial evidence are historical records.

## Contracts affected and contract-change decision

| Contract and source | Proposed behavior | Dante's explicit decision |
| --- | --- | --- |
| Approved recovery pass for new IPTV bulk jobs | End matching after the current title pass and its existing bounded repairs | “go” after the contract-change notice on 2026-11-08 |
| Automatic Apply and provider/account binding | Apply independently verified films through the existing receipt owner and enforce the pinned account, model, provider and generation | Included in the approved proposal |
| Historical jobs | Present and reconcile saved jobs under their pinned request contract | Targeted to future jobs |

## Current design and ownership

The existing checkout is `master` at `be511f98846a67a182e5b371ad087938e9344362` with 388 pre-existing changed paths. Port 5000 is served by PID 44856, `index-iYgNzJzz.js`, and the workspace `data` root.

| Responsibility | Owner | Change |
| --- | --- | --- |
| New jobs and status | `services/ai_routes.py` | Omit the recovery protocol pin on new starts. Expose recovery as a historical job property. Calculate the first-pass-only ceiling. |
| Matching and automatic writes | `services/chatgpt_iptv.py` and `services/ai_jobs.py` | Use the existing branch for jobs without a recovery pin. Continue to enforce automatic-job binding and progress. |
| Desktop launch and progress | `src/features/iptv/IPTVBulkMetadataJob.jsx` | Update the existing launch copy and ceiling. Show recovery counters only for jobs that recorded the recovery protocol. |

The existing recovery runner is compatibility for persisted jobs pinned to its protocol, including interrupted jobs with an admitted request. Retire that path when those saved jobs no longer depend on execution. The verifier also supports automatic first-pass safety checks, and saved results retain their diagnostic evidence.

## Exact behavior contract

- Calculated launch retains the first-pass size and expected count checks. The ceiling is `min(10000, 3 × (ceil(N/B) + 2 × ceil(N/min(B,50))))`. A 100-source job at size 100 has a ceiling of 15. Explicit smaller budgets are retained.
- Local and verified first-pass results apply through the existing receipt path. Uncertain results remain review rows. New jobs make zero candidate-recovery admissions. The saved-job status remains additive and continues to expose historical recovery totals.
- The current desktop layout, stage progress, Apply retries, provider queue refresh and separate explicit historical Apply controls use the existing components.

## Implementation sequence

1. Add launch-route and runner regression assertions, then observe the old behavior fail.
2. Change the launch owner and preserve runner binding, then update the desktop copy, status and fixture tests.
3. Run the focused backend tests and compiled desktop flow with temporary data. Stage the verified build and activate it through graceful CP shutdown and restart. Verify the live bundle and saved Lionz job through read-only checks.

## Acceptance matrix

| Scenario | Expected result |
| --- | --- |
| New job with one local match, one verified first-pass film and one uncertain film | Two automatic receipts, one review row, one physical ChatGPT request and zero recovery admissions |
| Configuration changes before a first-pass request | The original binding rejects the request and no call is admitted |
| Usage pause after a local receipt | The write remains recorded and the job can be cancelled |
| Failed verified write | Existing retry completes the write without another ChatGPT request |
| Existing recovery job and earlier manual-Apply job | The pinned recovery path and historical explicit Apply remain testable |
| Live activation | Port 5000 serves the new build and the completed Lionz trial still reports its nine receipts |

## Verification and rollout

- The current route baseline passed 10 tests. Run the route, bulk identity, automatic/recovery runner, AI job, transport and provider-preservation tests under `CP_TEST_MODE=1` and a unique temporary `CP_TEST_ROOT`. Run the repository's offline compiled IPTV desktop suite.
- Preserve the live bundle before activation. Check for active playback and jobs, stop CP gracefully with qBittorrent left running, start the existing backend from the workspace, and verify its process, asset and saved-job status. If the bundle swap fails, restore the prior bundle.

## Results

- The three new regression assertions failed against the old launch and runner. The focused backend run passed all 111 tests in 30.712 seconds after the change.
- All nine offline desktop tests passed against `index-gmdWYNEr.js`. A three-source job issued one title-interpretation request, made zero recovery admissions, applied two verified films and left the uncertain film in review. The write retry test also finished with one total ChatGPT request.
- CP restarted from PID 44856 to PID 35000. The live HTTP checks loaded the qualified bundle and the updated IPTV launch text. The existing Lionz trial reported all nine receipts and each corresponding provider row still had the recorded TMDB ID, automatic match state and no manual lock. Needs review was 979 before and after activation. The count of saved bulk jobs stayed at six. The qBittorrent process remained PID 16480 with two active downloads.
- The [activation record](<C:/Users/dante/AppData/Local/CinemaParadiso/rollout-backups/iptv-first-pass-20261108-012125-aa130852/activation-http.json>) and [previous frontend](<C:/Users/dante/AppData/Local/CinemaParadiso/rollout-backups/iptv-first-pass-20261108-012125-aa130852/previous-dist/index.html>) are retained. Runtime savings were established by removing the stage. End-to-end behavior for a fresh production job was verified in the isolated desktop fixture.
