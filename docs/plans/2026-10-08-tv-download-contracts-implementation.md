# TV download contracts implementation plan

> **For the implementing chat:** Use `superpowers:executing-plans`, read the root `AGENTS.md`, and implement the checklist below in order. Do not dispatch additional chats or subagents unless Dante authorizes them. This handover is the authorization to begin the bounded source/test implementation; do not ask again for the settled five-hour interval or manual release-review choice.

**Status:** Approved bounded implementation handoff, 2026-10-08. Dante requested saving the contract file, writing/saving an implementation plan, and creating a new task with the handover to start implementation. He explicitly confirmed five-hour retries and selected the existing release-review workflow for the lower all/selected-season buttons. This authorizes source changes, meaningful regression tests, disposable schema/config migration tests, and isolated compiled desktop verification. It does not authorize live activation.

**Goal:** Make the agreed TV download paths configurable, usable for new collections and multiple seasons, and truthful about automatic task progress.

**Architecture:** Keep `TVCatalogRepository` authoritative for TV homes, `TVAcquisition` for search/preparation/submission, and `TVMonitoring` for durable Follow scheduling. Extend the existing Settings selector and TV release review; keep qBittorrent and the verified-import journal authoritative for transfer/publication. Movie, TV and IPTV retain separate ownership.

**Tech stack:** Existing Python/Flask, SQLite, React/Vite, unittest/Node and Playwright. One small timezone-data dependency, `tzdata==2026.5`, for Windows `ZoneInfo`; no external scheduling provider. Modify `requirements.txt` in source, install only into disposable test dependency directories in this task, and leave the shared/live interpreter unchanged.

**Spec:** [TV contracts and decision log](../tv-contracts.md), bounded handoff section and TV-CHANGE-01 through TV-CHANGE-04. [Previous normal TV lifecycle](2026-10-05-tv-download-storage-cp-normal-behavior.md) and [Follow lifecycle](tv-library-completeness-maintenance-and-coverage-plan.md) remain authoritative where preserved.

**Execution record, 2026-10-08 (source work complete; checks classified, no live activation):** The bounded source slice is implemented in the named checkout. The baseline was 126 passing focused tests before edits. Final focused checks pass 172/172; Node passes 119/119. Full Python ran 1,667 tests: 1,666 pass and the unchanged streaming-overlay source assertion fails, also reproduced on an exported copy of baseline commit `78c60069`. The combined desktop run passed 39/40 (all nine new scenarios passed); an existing Library coordinate assertion failed once and passed the final targeted rerun, whose three checks include polling. The combined run is not claimed as green. Compiled desktop verification and scenario-level evidence are recorded in [the evidence ledger](../verification/tv-download-contracts.md). The no-agent handoff was followed; review was performed here. Required adjacent callers corrected within scope are the numeric-folder repair tool's schema-6 insert and the existing qBittorrent magnet retry owner for lost TV add acknowledgements. Neither was run against production. No live activation or commit.

## Global constraints

- Desktop only; extend existing CP layout/components rather than clone markup/styles.
- Five-hour unsuccessful-source retries are settled: **18,000 seconds** for Follow Missing/Future. They do not apply to lower manual buttons or Library one-shot bulk Download.
- Lower Download all/selected seasons opens **manual release review**. Opening a dialog, previewing or saving a Follow draft never queues transfers.
- Existing established homes, season style, episode filenames, safe identity/coverage/quality validation, move/cleanup, claims and recovery remain intact.
- No production `G:\TV`, `E:\Movies`, configuration, database, transfers or served `dist` mutations; no app restart, deployment, live download, commit, push, package or release.
- Unresolved flat collections, missing title/year, unsafe names, path collisions, and ambiguous roots/ownership remain visibly blocked. Do not invent a new naming/migration policy.

## Problem and decision

- **Confirmed:** Louie has a selectable season release but no approved home; the review disables Download without first-time destination setup. Existing storage explicitly excluded new-show creation.
- **Confirmed:** Movie bulk effectively uses YTS through release-trust mode. TV instead trusts the raw hidden empty `download_trusted_indexers` list. Settings cannot edit that TV trust list.
- **Confirmed:** The inspected Lucifer Follow task searched releases but accepted none. LimeTorrents/1337x candidates also lacked resolved torrent hashes; automatic selection happens before the existing prepare path can resolve supported links. Lucifer additionally has only a flat season-one collection, with no proved destination for later seasons.
- **Confirmed:** Follow's source retries currently use one hour; Future metadata refresh uses six hours. The panel does not poll and hides episode errors. The worker searches per episode, not necessarily using one torrent for a whole series.
- **Confirmed:** Lower direct controls scope only the displayed season. Dante wants all seasons or a checked set of seasons there, retaining release review.
- **Decided:** Separate Movie/TV automatic trust selectors; YTS initial Movie choice; LimeTorrents and 1337x for isolated TV testing; metadata show-name/start-year new homes; preserve established season styles; five-hour Follow retries; lower multi-season manual review.
- **Bounded exclusions:** Do not repair/move Lucifer or any existing flat collection. Do not redesign cancellation, upgrade ranking, Specials, movie watchlist trust, AI Control trust, or Library one-shot bulk lifecycle. Do not add IMDb/TVmaze scheduling. Do not add multi-season Future scope or automatic release picking to the lower buttons.
- **Open decisions:** None may be guessed inside the included happy paths. Deferred exceptions above return actionable blockers. If an agreed contract requires expansion, pause only that part and present the `AGENTS.md` contract notice.

## Review focus

- An explicitly empty or unavailable source list must not silently become YTS/all-enabled trust (Task 1).
- Concurrent reservations or an externally created same-name folder must not establish ownership of another show's files (Task 2).
- Provisional episode IDs in different seasons must not collapse multi-season coverage or submit unintended episodes (Task 3).
- Cairo midnight/daylight-saving transitions and a restart after missed searches must preserve five elapsed hours between unsuccessful searches (Task 4).
- Changed trust, destination, provider identity or scope must invalidate stale submission assumptions while navigation discards old responses (Tasks 1-4).

## Contracts affected and contract-change decision

| Contract and source | Existing agreement | Included behavior | Changes contract? | Dante's decision |
| --- | --- | --- | --- | --- |
| TV-BASE-03 / earlier storage exclusion | No first-time show-home creation | Genuinely new, unambiguous collections can use `Show Name (YYYY)\Season 01` from canonical metadata | Yes; TV-CHANGE-01 describes the change and notice | Dante proposed this tree and authorized this bounded implementation handoff; unresolved exceptions remain blocked |
| TV-BASE-02, 04-08 | Preserve established layout, names, verification and lifecycle | Preserve across all callers | No | South Park style confirmed acceptable |
| TV-CHANGE-02 | Lower controls currently review one season | Review all/checked regular seasons with the same explicit submission | Extends scope; does not turn downloads into Follow | Dante confirmed lower-control location and explicitly chose Open release review |
| TV-CHANGE-03 | Movie bulk has effective source policy; TV trust wiring is broken | Independent effective Movie/TV automatic-source lists with shared multi-select UI | Corrects wiring; makes download choice explicit | YTS for Movies, LimeTorrents + 1337x TV test selection |
| TV-CHANGE-04 / Follow | Retry unsuccessful sources; Future is separate from fixed Missing | Five hours for Missing/Future; Future first eligible at date boundary in Cairo | Exact retry interval resolved; older written contract had no numeric interval | Dante: "the 5 hors is resolved" |
| TV-FOLLOW-01, 03, 06, 07 | Explicit Start, Future completion, one-shot bulk and cancellation | Preserve | No | Existing agreement |

Do not retain tests asserting that every new metadata-backed collection must have a pre-existing folder. Split that obsolete assertion from the still-valid flat-layout/ambiguous-home safety checks. Hash validation is never removed to make unresolved links pass. Do not change tests into permission for a different product result.

## Current design and ownership

**Baseline checked during planning:** Checkout `C:\Users\dante\Desktop\cinema paradiso`, `master`, HEAD `78c60069bfec1184e43ec20ed01fa55bd2215f86`, package `3.0.0-beta.2`. Before these document edits, only `docs/tv-contracts.md` was untracked. Recheck dirty state before implementation and preserve other chats' work.

**Runtime/data, read-only evidence:** Root `config.json`; `data\tv-catalog.sqlite`; `data\acquisition.sqlite`; transfer journal `data\qbittorrent\jobs.json`; staging `data\qbittorrent\incomplete`; configured TV root `G:\TV`. Port 5000 was PID 48136, `C:\Program Files\Python312\python.exe app.py`, started 2026-10-08 01:01:52 Cairo. HTTP `/` served `/assets/index-BL38s9_4.js`, matching the script name in current `dist/index.html`. This is baseline identity, not proof of future deployment. Recheck if needed; never restart it for isolated tests.

| Responsibility | Authoritative owner | Callers / behavior to preserve | Retire or correct |
| --- | --- | --- | --- |
| Configuration/effective indexers | `app.py` configuration load, `_all_config`, `/api/prowlarr/config`, `_effective_download_trusted_indexer_ids`, TV composition | Movie bulk preparer; release-watchlist and AI Control remain separate | TV reading Movie's raw list; hidden custom mode as the UI's sole source choice |
| Source selector UI | `SettingsWorkspace.jsx`, existing `TrustedIndexerDialog` | Prowlarr section, existing trust dialogs | Scope-specific duplicated selector markup where the shared component can replace it |
| TV destinations | `tv_catalog_repository.py`, `tv_catalog_store.py` | Acquisition search/prepare/submit, completion and discovery | Requiring an existing directory for a reserved new metadata home |
| Search/preparation | `tv_acquisition.py`, existing `prepare`, `submit_batch`; `tv_routes.py` passes inputs through | Manual review, Follow and bulk; immutable hashes/tokens/coverage | Accepted-only auto selection before supported link preparation |
| Follow scheduler/state | `tv_monitoring.py`, task tables in `acquisition_store.py` | Preview/draft/Start, Missing/Future/Upgrade, history/cancel | One-hour Missing/Future source retries; hidden readiness/rejection errors |
| Series/download UI | `TVWorkspace.jsx` / `TVSeriesPage`; `TVAcquisitionReview.jsx` / `TVReleaseDialog`, `TVMonitoringControls` | Single-season and episode controls, navigation, preview/discover | One-season-only scope in lower all/selected actions; stale task display |
| Publication | `verified_import.py`, `TVAcquisition.complete_normal_import`, qBittorrent jobs | Verified move/import/cleanup and legacy jobs | No parallel publication or transfer store |

## Exact behavior contract

### Frontend

**Settings:** In Prowlarr -> Automation defaults, replace the misleading Download trusted indexers mode select with **Movie trusted indexers** and **TV trusted indexers** rows, each showing saved/effective names and a **Select indexers** button. Reuse existing settings-row spacing, buttons, `.small-dialog.trusted-indexer-dialog`, checkbox list, Save and Cancel. Refactor one selector to accept title, description, indexer choices and draft selected IDs; opening it copies saved IDs, Cancel discards local edits, Save closes only after successful persistence. Show empty, loading, unavailable-ID and save-error states. Do not reset explicitly empty selections to defaults. Release-watchlist and AI Control retain their own labels, values and responsibilities; if their identical selector markup is shared, verify those callers too.

**Lower controls:** Keep the displayed-season selector and existing Download season / episode-selection controls. Add **Download all seasons** and **Choose seasons…** beside Download season in the same lower control area. Choose seasons opens CP's existing small-dialog/checkbox pattern listing regular seasons and missing/released/owned counts, with a **Review downloads** button. No checked season disables it. Both new actions target released missing regular episodes only; the existing Include owned episodes (upgrade) affects only its existing episode/current-season paths, not these new all/checked actions. Season 0 is excluded from these new choices.

**Release review:** Extend `TVReleaseDialog`, sharing the existing release-row/summary rendering between one and many seasons. Show season groups, each destination and source results, plus total selected coverage and unresolved/blocked seasons. The existing explicit Download selected releases/Download available submission remains. A blocked destination disallows submission of its releases; available seasons may be explicitly submitted with the existing partial-coverage warning. No backend Follow task is created. Changing scope/profile/home clears stale tokens/request keys. Close/Escape/Back and reopened review do not leave requests running or stale selections.

**Follow:** Preserve Preview -> Save draft -> Start. Explain the two action labels as **Missing — download existing missing episodes** and **Future — follow new episodes** without changing stored action names. Show setup blockers in preview and on Start failure. Refresh active/history data every 15 seconds while mounted, with abort/sequence protection when series changes. Task rows show acquired/target counts, queued/waiting/review counts, last search, next eligible search in Cairo, and concise actionable episode errors. A source search yielding only rejected candidates must not be rendered as zero results. Keep notification deduplication and existing X/cancellation behavior.

### Backend

**1. Separate effective source policies.** Keep existing `download_trusted_indexers` as the explicit Movie automatic list, add `download_trusted_indexers_configured`, `tv_download_trusted_indexers`, and `tv_download_trusted_indexers_configured` to load/save/config responses. IDs are deduplicated strings from Prowlarr; never hardcode provider numeric IDs. Omitted fields preserve current values; explicit empty arrays disable automatic trust. POST validates list types and selected IDs against known enabled indexers; GET reports stored and effective IDs plus unavailable selections without silently dropping stored IDs.

For legacy Movie configs without a configured explicit selection, preserve their effective behavior: custom keeps its list (including empty), all resolves enabled IDs, release resolves release-watchlist IDs. Display the effective result; first explicit Movie save freezes the new independent list. New/unconfigured Movie setup uses enabled YTS/YIFY as the initial choice, never a replacement for an explicit saved list. Retain the legacy mode decoder only for unmigrated saved configurations; document/remove its UI and all TV dependencies. It can be removed after saved configs have explicit Movie IDs; do not rewrite production config now.

TV has its own effective list, with no fallback to Movie, release-watchlist, AI Control or all enabled indexers. Isolated test setup chooses actual fixture IDs for LimeTorrents and 1337x. No production configuration save/default installation-wide trust is authorized by the requested test selection. With no configured TV trust, readiness explains **Select TV trusted indexers in Settings**. Automatic TV searches use only the effective enabled TV list. Manual review keeps the current broad enabled-provider search and displays trust/validation warnings; trust selection does not waive other requirements. New source settings govern subsequent searches/preparation; queued jobs keep recorded hashes, destinations and policies. Removing source trust requires re-review before a stale automatic token can submit.

**2. New metadata destinations.** Extend `resolve_import_destination(series_id, season, roots, *, metadata=None)` so unsaved typed previews can supply canonical metadata without inserting catalog rows. Existing preferred/credible homes resolve first with unchanged season-style rules. Only a series with no existing bindings, folder assignments or reserved home qualifies for a new metadata home. Require one valid configured root, canonical saved/provider-normalized title, full first-air year and regular season. Use exactly `Title (YYYY)\Season NN` (minimum two digits) independent of torrent title and transient Arabic display toggles.

Return the current destination fields plus `origin:'existing'|'metadata'` and `requires_creation`; a safe proposal is `state:'ready'` even when its directories do not yet exist. Missing/invalid metadata, Windows-invalid/reserved/trailing-dot names, multiple roots, unowned existing directories, case-insensitive collisions, exclusions, another series' assignment or any existing flat-layout collection produce an actionable blocked destination. Do not sanitize or suffix names to invent an undecided policy. Preview/search/draft create no directories or ownership rows.

Add `reserve_import_home(series_id, destination, roots)` to the same repository for validated Download/Start only. Extend existing `tv_import_homes` with an `origin` column defaulting to `existing` (TV schema 6); use the existing `tv_path_assignments` relation to reserve the planned metadata path transactionally without changing `approve_path`'s existing-folder contract. Enforce same-series reuse and different-series conflict, including case-insensitive path equivalence. Existing homes remain stable after metadata edits. Resolver may recognize a reserved metadata home before its physical directory exists and derive later `Season NN` paths from its recorded origin.

New reserved-home support must pass through `TVAcquisition.prepare`, `_materialize`, submission and completion. Validate and snapshot before claims/transfer add; after materializing an unsaved preview, revalidate stable provider episode identities and the same proposed path, then reserve. Only verified publication creates physical show/season directories. Revalidate containment, ownership, exclusions and external filesystem collisions at publication; use the existing import journal for creation/recovery checkpoints. Cancellation does not delete unrelated folders or remove ownership another active job uses. Preserve old job destinations/policies; no live migration.

**3. Multiple-season manual review.** Add `TVAcquisition.search_seasons(series_id=None, *, tmdb_id=None, seasons, profile_id='safe-hd')` and `POST /api/tv/search/seasons`. Validate a nonempty deduplicated set of regular seasons belonging to the show, bound at 150 (existing metadata season bound). Compose the existing `search(..., manual=True, missing_only=True, upgrade=False)` sequentially with cancellation/bounded work; return `{season_reviews, selected_seasons, scope_counts, search}`. Do not duplicate release parsing/ranking. Each decision retains its original season request/token and destination.

Use stable composite episode keys `(tmdb_id, season_number, episode_number, provider_id)` in multi-season coverage summaries rather than assuming provisional preview IDs are unique across seasons. Supply those projections from the TV owner; the UI formats them. `submit_batch` remains the shared authoritative submitter and detects overlap across the chosen decisions, revalidates per-season destinations, and retries only unfinished members under the same request key. No acquisition occurs while searching/choosing/checking seasons. An unavailable season remains visible; no persistent background retry task is created.

**4. Supported automatic link preparation.** Add a bounded `TVAcquisition.select_automatic(review, *, resolution_limit=5)` method shared by Follow and one-shot bulk. In ranked order, consider already accepted candidates and candidates whose only hard rejection is unresolved `hash_invalid`, provided automatic trust, identity, coverage, transport and quality otherwise pass. Call the existing `prepare` for supported unresolved links, then select only a fully accepted re-evaluated decision. Limit resolutions to five per episode pass; preserve Prowlarr allowlist, hash-swap rejection, blocked hashes and immutable provider identities. Never set `manual=True` or confirm identity automatically. Wrong-show, untrusted transport, blocked/manual-only quality and source-unverified candidates never enter resolution. Return explicit accepted decision or a summary distinguishing no results, rejected sources, provider failure and preparation failure. Do not invent another torrent resolver or weaken `evaluate_release`.

**5. Follow readiness and scheduling.** Preview returns additive `readiness:{ready,blockers}` (enabled trusted sources, metadata and per-season destination setup) plus current target counts. Draft save is allowed while blocked; Start refreshes metadata and rechecks readiness before activation/reservation or intent creation. Failed Start leaves the draft and error intact. An existing running task encountering a configuration/destination blocker reports an actionable needs-review state rather than quietly calling it no-source; existing review-state worker eligibility lets it recheck after the setup is corrected without duplicate claims.

Inject one scheduling timezone/clock into `TVMonitoring` (default Africa/Cairo here); use `ZoneInfo('Africa/Cairo')` with the declared `tzdata==2026.5` dependency. The planning probe in the current Windows venv failed with `ZoneInfoNotFoundError` because timezone data is absent. Python's [official guidance](https://docs.python.org/3/library/zoneinfo.html#data-sources) recommends declaring tzdata for this Windows case; [the verified package release](https://pypi.org/project/tzdata/2026.5/) supplies that data. Do not implement a competing Windows timezone converter, hardcode UTC+2/+3, or silently use machine timezone. Missing timezone data produces actionable setup failure before activation. Future eligibility derives from 00:00 Cairo on the date-only episode `air_date`; this is a search policy, not a proven broadcast timestamp. The worker first checks that boundary, then searches on its next pass. Keep existing six-hour metadata refresh, fixed Missing target snapshots, explicit selected-episode behavior and Future/season-end completion rules. Test both Cairo DST transition dates as well as an ordinary midnight; retry timestamps always add 18,000 elapsed seconds.

After an unsuccessful Missing/Future source search set the episode's `last_search=now` and `next_retry=now+18000`; Future waiting-release records its actual eligibility time. A queued intent is monitored without another add; acquired means verified/imported, not merely queued. Preserve Upgrade and transfer/import retry intervals. A restart with an overdue target performs one next-pass search; do not replay missed intervals. Persisted task/episode times remain the source of truth; use existing fields and derived response counts, not a second scheduler table. A provider/validation error is displayed distinctly from ordinary source absence; no repeated unread notification every retry cycle. Prevent overlapping worker execution using the existing acquisition leases/claim owner and test idempotent submission.

## Implementation sequence

### Task 1: Source policies and shared Settings selector

- [x] Baseline relevant tests before edits; add `tests/test_tv_download_contracts.py` policy/config API cases and desktop selector scenarios below. Verify failures demonstrate the current empty-TV wiring, not provider network failures.
- [x] Modify `app.py` configuration/effective-policy composition and `SettingsWorkspace.jsx` shared selector/form/save owners exactly as specified. Audit every raw-list/mode caller, including `tests/qualify_tv_providers.py`; remove TV's dependence on Movie mode. Keep qualification tools opt-in and update their policy contract without running live provider probes.
- [x] Prove Settings save/read/effective search calls together: fixture Movie YTS, TV LimeTorrents+1337x, explicit empty, omitted fields, unavailable IDs, failed-save Cancel behavior, independent release/AI trust.

### Task 2: Safe new metadata homes

- [x] Add failing new-collection/preview/reservation/publication cases in `test_tv_import_destinations.py`, `test_tv_normal_import.py` and `test_tv_download_workflow.py`. Split the prior no-home test into new metadata-ready and still-blocked flat cases; keep ambiguity, exclusions and collision assertions.
- [x] Modify `tv_catalog_store.py`, `tv_catalog_repository.py`, and TV acquisition callers. Extend schema-5 migration/restore tests to 6 using only temp databases. No physical library directory before verified import; no mutation from review.
- [x] Test Louie-shaped unsaved preview -> explicit submit -> reserved home -> verified import -> catalog paths -> staging cleanup; repeat after reopen/concurrent reservations. Prove South Park style and legacy jobs unchanged.

### Task 3: Lower multi-season release review

- [x] Add owner/API tests for `search_seasons`, stable cross-season preview keys, exact missing-only scope, partial search and overlap; extend `tests/native_tv_server.py` with deterministic multi-season releases.
- [x] Modify `tv_acquisition.py`, `tv_routes.py`, `TVWorkspace.jsx`, and the existing `TVReleaseDialog` rendering to support all/checked seasons while retaining single-season and episode flows.
- [x] Verify checking seasons/opening review adds zero jobs/tasks; explicit batch submit queues only selected releases, preserves each destination and survives lost acknowledgements/retry without duplicate adds.

### Task 4: Automatic preparation, settled scheduling and visible task state

- [x] Add tests to `test_verified_tv_acquisition.py` and `test_tv_download_contracts.py` for supported unresolved links, bad hashes/identity/trust, readiness-blocked draft, Cairo midnight/DST boundaries, exactly five elapsed hours, restart and queued/acquired distinctions. Add `tzdata==2026.5` to `requirements.txt`; verify timezone loading in disposable test dependencies without changing the shared interpreter.
- [x] Implement the shared `select_automatic` owner and update `TVMonitoring` preview/Start/run path plus response projections. Preserve one-shot bulk completion and cancellation/history behavior.
- [x] Update `TVMonitoringControls` with explicit labels, readiness and safe 15-second polling. Verify rendered counts/times/errors against returned task state, including navigation to another series and Back/Forward.

### Task 5: Integrated verification and handback

- [x] Add `tests/e2e/tv-download-contracts.spec.js` using the disposable native-TV server; extend existing normal-import/parity tests where the same shared owner changed.
- [x] Run focused checks, broad relevant/full suites, compiled desktop scenarios and contract comparison below. Record evidence and exact failures in this plan or `docs/verification/tv-download-contracts.md`.
- [x] Report source-only result, deferred flat-layout limitation, TV test-only selections, and what would require separate live authorization. No automatic commit/deploy step.

## Acceptance matrix

| Scenario | Action | Exact expected result | Owner / evidence |
| --- | --- | --- | --- |
| Movie YTS / TV test Lime+1337 | Save each dialog; start isolated source search | Lists independent; backend uses matching effective IDs; manual review still sees enabled sources | Config API + compiled Settings + provider call capture |
| Explicit empty TV trust | Save empty / Start draft | No YTS/all fallback; draft remains blocked with Settings instruction; no add/claim | API and UI |
| Provider list/save fails | Open/edit/save dialog | Error visible; previous saved selection retained; Cancel discards draft | Compiled Settings |
| Louie-shaped genuinely new show | Search then explicitly submit/import | Preview path `Louie (2010)\Season 01`, zero preview mutation; verified media placed/bound there; staging cleaned | Filesystem, API review and normal-import integration |
| Established South Park hierarchy | New season import | Continue original saved home/padding; never numeric/title-created duplicate | Destination + publication regression |
| Existing flat Lucifer shape | Preview/Start | Clear destination-review blocker; existing media unchanged; no guessed new home | API/UI adverse case |
| Missing year/unsafe name/multiple roots/unowned collision | Preview/submit | Actionable blocked destination, zero intent/transfer/filesystem mutation | Repository and route integration |
| Concurrent first imports/restart | Reserve then submit/import twice | Same-series home stable; other-series overlap blocked; claims/journal prevent duplicate publication | Schema/recovery/lease tests |
| Lower all or seasons 2,3,5 | Open scope/review | Only released missing regular targets; season groups/destinations; no Follow task or transfer before submit | New route + compiled UI |
| Partial seasons/overlapping packs | Choose/download available | Explicit partial coverage; blocked releases cannot submit; no duplicate episode claims; retry only unfinished | Batch + rendered summary |
| Future dated Oct 15 | Worker at Oct 14 23:59 Cairo, then Oct 15 00:00 | No early search; first next eligible pass; date-only timezone policy displayed | Injected-clock tests + task UI |
| No source at time T | Worker before/at T+18000 | No retry before boundary; one search at/after it; next times survive restart | Scheduler + API |
| Trusted supported unresolved torrent link | Automatic pass | Prepared and revalidated before selection; correct hash queued once | Resolver mocks + source-to-submit integration |
| Wrong identity/hash swap/manual-only quality | Automatic pass | No bypass or transfer add; actionable rejection evidence | Decision/prepare regression |
| Queued/downloaded/imported | Repeated worker/UI refresh | No repeated submission; acquired increments only on verified import | Task+intent+catalog/UI path |
| Ended series Missing / Future | Preview/Start | Missing targets entire missing released snapshot; Future unavailable; Missing adds no later episodes | Existing Follow contract checks |
| Library one-shot no-source | Bulk action | Reports and finishes without five-hour retries or Future behavior | Existing bulk/Follow tests |
| Movie/watchlist/AI/IPTV shared surfaces | Save/view/use unchanged owners | Existing distinct settings and workflows preserved | Movie configuration tests, existing UI suites |
| Navigate/reopen/Back/Forward | Change series/scope/profile | Abort stale requests, no leaked polling or selections; correct new content and focus | Playwright desktop |

## Verification and rollout

**Baseline:** No implementation tests were run in this planning chat; no green suite is claimed. The implementing chat must establish current failures before edits. Prior historical failures are context only, not proof of current baseline.

Run commands in a fresh PowerShell with `CP_TEST_MODE=1` and `CP_TEST_ROOT` set to a unique directory under `[IO.Path]::GetTempPath()`. Provider access must be fixture/mocked; no production roots or credentials. Use `.venv\Scripts\python.exe` and recheck runtime ownership before starting any isolated service.

```powershell
$env:CP_TEST_MODE = '1'
$env:CP_TEST_ROOT = Join-Path ([IO.Path]::GetTempPath()) ('cp-tv-contracts-' + [guid]::NewGuid().ToString('N'))
$testDependencies = Join-Path $env:CP_TEST_ROOT 'python-deps'
& .\.venv\Scripts\python.exe -m pip install --target $testDependencies 'tzdata==2026.5'
$env:PYTHONPATH = $testDependencies
& .\.venv\Scripts\python.exe -m unittest tests.test_tv_download_contracts tests.test_tv_import_destinations tests.test_tv_normal_import tests.test_tv_download_workflow tests.test_verified_tv_acquisition tests.test_acquisition_decisions tests.test_tv_bulk_actions tests.test_tv_coverage_contract tests.test_source_search_service tests.test_user_curation_store
node --test tests/tv_search.test.mjs
$env:CP_TV_E2E = '1'
& npm.cmd run test:e2e -- tests/e2e/tv-download-contracts.spec.js tests/e2e/tv-normal-import.spec.js tests/e2e/tv-parity.spec.js tests/e2e/tv-expanded-parity.spec.js
```

The existing E2E runner builds into an OS-temp `dist`, uses disposable data and an isolated port. Inspect its current behavior before use; never run `npm run build` without an isolated `--outDir`. Compiled desktop gates include populated/empty/error/long-content Settings dialogs, new/blocked/ambiguous destinations, multi-season groups, truthful tasks, keyboard close/focus and repeated navigation. Capture screenshots and API/network assertions for the new motivating paths; a direct helper test alone is insufficient.

After focused checks pass, run `python -m unittest discover -s tests` in the isolated environment and `node --test tests/*.test.mjs` (expand file paths in PowerShell if necessary); record exact pass/fail/skip counts. Broad failures must be classified against baseline, never hidden by a focused rerun. Add any further existing shared Settings/UI regression suites identified during ownership inspection.

**Migration/recovery:** TV schema migration 5->6 and restore, omitted/explicit-empty config reads, legacy Movie mode decoding, queued job snapshots and reserved-home concurrency are isolated gates. Leave production files unchanged. Rollback in tests restores the disposable schema/data snapshot; live rollback is not authorized.

**Live gate:** Separate authorization is needed for live configuration selections, schema activation, restart/deployment or a real download. Do not alter/cancel the live Lucifer task. Future live work needs backups, current process/data/served-bundle identity and visible end-to-end evidence; it is not part of this handoff.

**Final contract comparison:** Report each included rule versus observed results, exact remaining differences, and the intentionally blocked flat-layout/metadata exceptions. Label all evidence isolated/source-only. Update this checklist and the contract file with actual implementation status without claiming a deployment.
