# TV Follow season packs, release recognition, and source diagnostics

**Status:** Implemented in the source checkout and verified in isolation, 2026-10-10; production activation remains pending separate authorization. After the explicit P1/P2 and source-implementation approval question, Dante replied: "approved and go without interuption dont stop till you finish my approval her overule the agent.md file". P1/P2 and the implementation scope below are approved. Live migration, real download, deployment, restart, commit, and push remain outside this source-only plan's scope. Exact passing gates and full-suite limitations are recorded in the [verification report](../verification/tv-follow-season-packs/README.md).

> **For agentic workers:** After Dante approves the exact contract decisions and implementation scope, use `superpowers:executing-plans` for inline execution. Use `superpowers:subagent-driven-development` only if Dante explicitly chooses delegation. Complete the checklist tasks and their checks in order. This document follows `docs/plans/_template.md`; do not substitute a generic plan or silently expand the scope.

**Goal:** Recognize valid season-pack releases correctly and let a started TV Missing task consider them before filling gaps with episode searches, with one acquisition per selected torrent and truthful task diagnostics.

**Architecture:** Correct the existing TV parser and acquisition owner. Reuse the existing release planner, preparation, episode claims, transfer manager, manifest validation, verified import, and task store. The Follow worker groups search work but retains durable per-episode targets and outcomes; it does not become another torrent or import engine.

**Tech stack:** Python/Flask, SQLite, the existing qBittorrent manager, React, unittest, Node tests, and desktop Playwright. No new runtime dependency or provider.

**Design sources:** This document's exact behavior contract; `docs/tv-contracts.md`; `docs/plans/tv-parity-and-download-workflow-plan.md`, sections 5–7; and `docs/plans/2026-10-08-tv-download-contracts-implementation.md`. The Follow grouping and source-review decisions are now recorded as approved TV-CHANGE-05 in docs/tv-contracts.md.

## Problem and decision

### What happens now

1. The started Louie Whole series → Missing task searches individual episodes. Its inspected automatic results included 1,282 saved evaluations, all manual-only under CP Compatibility. This was a snapshot of that search path, not proof that no permitted Louie release exists.
2. Manual Download season finds permitted 1080p BluRay packs. The same profile successfully acquired season 1 as one LimeTorrents torrent, `Louie 2010 S01 1080p BluRay x265`, approximately 4.39 GiB. The job `5a1fbf45a72d5fa5547b47a240ebe776cbfab347` has 13 verified/published files, measured 1080p HEVC, successful cleanup, and catalog bindings matching all 13 existing files.
3. The screenshot's Pirate Bay S02 FGT pack is recognized as season 2, covers 13 requested episodes, and is preferred quality. It is blocked by identity uncertainty and an HTTP link incorrectly classified as a magnet.
4. The screenshot's LimeTorrents `Louie 2010 S01 ...` result is season 1 returned during a season-2 search. Its zero season-2 coverage is a legitimate rejection.
5. `Louie (2010) Season 2 S02 (1080p BluRay x265 HEVC 10bit AAC 5.1 Garshasp)` is preferred quality, but `parse_episode_name` returns absolute episode 2 before reaching its S02 rule. `series_identity` includes `Season 2` in the show title and loses the year. This creates false coverage and identity failures.
6. A Prowlarr HTTP download endpoint can occur in `magnetUrl`, with no `downloadUrl`. `_release_decisions` assumes that the former is a magnet, so the transport fails verification despite being an allowed Prowlarr URL. The inspected task had 372 such Pirate Bay evaluations; a fresh provider response reproduced the field layout.
7. `select_automatic` prioritizes an overall partial-provider flag over the presence of rejected releases. It then combines reasons from different releases. `TVMonitoring` stores rejection outcomes as retry, so identity/manual-selection requirements appear as waiting rather than review.

**What Dante wants:** A valid 1080p release with the correct year and season must not be rejected because of its naming layout or provider field layout. When a whole season is missing, Follow should consider a suitable season pack instead of relying only on episode queries. Keep acquisition safety, explicit activation, and the agreed five-hour source retries.

**Confirmed:** The defects and season-1 provenance above were established from stored decisions, transfer recovery, catalog records, pure parser probes, and provider responses. The season-2 torrents' actual file manifests and playability have not been verified. A search title claiming a full season is not verified file coverage.

**Scope:** Parser/identity recognition; TV provider transport normalization; shared TV claimed-coverage planning; season-first search for continuing Missing tasks; durable pack-to-task association/recovery; source diagnostics and existing desktop review UI; meaningful regression coverage.

**Exclusions:** No quality-profile edits, broader automatic quality allowance, automatic identity confirmation, new providers, Movie selection-policy changes, IPTV changes, library repair/rename, cancellation redesign, automatic upgrades, new Future targets, or changes to bulk one-shot lifecycle. Future, Upgrade, explicit selected-episode tasks, and Library bulk retain their current search scheduling/grouping; they receive the shared parser/transport/diagnostic corrections where they already call those owners. Mobile work is excluded.

### Approval and open decisions

There are no implementation defaults to invent. The design below records the two product choices explicitly approved by Dante on 2026-10-10:

- **P1 — Season-first Missing planning:** Apply grouping to `kind='follow'`, `action='missing'`, `scope in {'series','season'}`. When an entire regular season is released, absent locally, inside the frozen Missing target set, and free of conflicting acquisition claims/reconciliation, a due search considers its season releases first. Among otherwise eligible releases, preserve the existing manual planner's quality ordering and prefer useful coverage at equal quality. A complete pack may satisfy other released missing targets in that same season/task even when their individual retry timestamp is later; do not issue separate early episode searches for them or reset their unsuccessful-search clocks. On a failed season search update only the due members. Partially owned, partly unreleased, excluded, or partially scoped seasons retain per-episode automatic search in this slice.
- **P2 — Review reporting without stopping retries:** A source result needing deliberate identity or manual-quality selection becomes an episode `needs_review` outcome with no transfer intent. It remains eligible for the existing five-hour unsuccessful-search retry. A later fully eligible release may be acquired automatically. A confirmation in manual review applies only to that reviewed release; it never creates persistent trust for all releases of that show or changes Follow's automatic policy.

The required separate contract-change notice was delivered with the plan. Dante explicitly approved P1/P2 and source implementation on 2026-10-10. This does not authorize deployment or live task/configuration changes. Terminal transfer/import failures keep their existing review/recovery behavior; episode fallback means filling search-plan gaps, not silently bypassing a failed manifest or retrying a failed torrent.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| TV-BASE-04/08, `docs/tv-contracts.md`; download workflow sections 5–6 | Preserve show/episode identity and verify actual torrent files. A season title establishes a claim only. | Manual episode/season/multi-season review; Follow; bulk; TV import | Recognize the demonstrated title forms and normalize transport before existing checks. Contradictions remain blocked. | No; repairs existing supported behavior | Approved for source implementation, 2026-10-10 |
| Manual download workflow section 6 | Season searches first; compare packs/individuals by profile and useful coverage; prevent overlap | Existing manual review and recommendation list | Extract the existing planner into one TV acquisition method and preserve its recommendation ordering and explicit submission | No | Approved for source implementation, 2026-10-10 |
| TV-FOLLOW-01/02 | Draft then explicit Start; Missing freezes released missing regular targets; retry until acquired/cancelled | Whole-series/season continuing Missing | P1 groups source work and may queue one pack for several frozen targets. No new targets, redownload, or implicit Start | New Follow selection rule; record explicitly | P1 explicitly approved, 2026-10-10 |
| Five-hour retry agreement, TV-CHANGE-04 | Unsuccessful Missing/Future source searches retry after 18,000 elapsed seconds; Future release date boundary is Cairo midnight; metadata refresh is separate | Task/episode scheduler and display | Keep intervals. P1 permits shared successful coverage of non-due sibling targets without independent early searches; failed searches preserve non-due clocks | Grouping exception needs an explicit decision | P1 explicitly approved, 2026-10-10; interval stays settled |
| Truthful readiness/progress, prior implementation plan sections 4–5 | Distinguish no results, rejection, provider failure, and preparation failure; visible actionable errors | Follow task API/UI and existing review | P2 counts actionable review and retains source retries; show candidate-specific reasons and partial source status separately | Reporting repair plus explicit review/retry rule | P2 explicitly approved, 2026-10-10 |
| Quality profiles and source trust, TV-CHANGE-03 | Indexer trust does not waive quality, identity, coverage, transport, destination, or availability | All TV acquisition paths; shared evaluator | Preserve profile data, ranking inputs, allowlist, and automatic restrictions | No | No amendment proposed |
| TV-BASE-05/06/07 | Verified publication, no ordinary overwrite, established destinations, cleanup only after verification; partial failures retain recovery | Transfer, import, tasks, cancellation | One intent covers the selected pack's episodes; task completion requires the existing per-episode verified result | No | No lifecycle amendment proposed |
| TV-FOLLOW-03/04/05/06/07 | Future, Upgrade, selected episodes, bulk one-shot, and explicit cancellation have distinct behavior | Those callers and history/notifications | Preserve scheduling/grouping/targeting and cancellation choices; shared bug repairs only | No | Excluded from behavioral expansion |

**Test-contract audit:** Existing tests cover simple `S01` packs and same-title/year safety, not the demonstrated redundant `Season 2 S02` syntax or HTTP-in-`magnetUrl` response. A test that records those supported forms as an identity conflict is not authority to keep the defect. Preserve genuine wrong-year/provider-ID conflicts, manifest validation, terminal-failure recovery, and existing manual planner ordering. The historical streaming source-shape failure must not be changed or hidden to obtain a green suite.

## Current design and ownership

### Baseline verified while writing this plan

- Checkout: `C:\Users\dante\Desktop\cinema paradiso`; branch `master`; commit `be511f98846a67a182e5b371ad087938e9344362` (`Update TV download contracts, destinations and Follow tasks`). `git status --short` was clean before this document was created.
- Configuration: checkout `config.json`; user-data root `C:\Users\dante\Desktop\cinema paradiso\data`; TV root `G:\TV`. Live settings expose 20 effective TV trusted indexers and no unavailable selected IDs. Do not put provider credentials or complete download URLs into evidence.
- Runtime: port 5000 is owned by PID 8068, previously inspected as Python executing `app.py`. Its loaded source modules are not proven byte-identical to files on disk merely because the checkout is clean. Re-identify PID, executable, command line, and loaded behavior before any later live claim.
- Served frontend: live `/` matched checkout `dist/index.html` byte-for-byte while preparing the plan. SHA-256 `3f945e569c5a68a3de480394a502b98a04aa9e912927a5b3c578449013b15a5f`; entry asset `index-D8PgOuRU.js`. Source, this served build, and future isolated builds are separate facts.
- Acquisition DB is schema version 3. Louie's active task is `dfda586ec1a64cae907a710ff047a021`, continuing whole-series Missing, CP Compatibility. Do not cancel, restart, recreate, or edit it as part of source implementation.
- No current test suite was run for this documentation-only request. Historical verification records a pre-existing streaming assertion failure at an older baseline. Reproduce/record the actual execution checkout's baseline before editing application code; historical counts are not current proof.

| Responsibility | Authoritative owner | Entry point/callers | Preserve | Obsolete/competing path to retire |
| --- | --- | --- | --- | --- |
| Numbering and title/year evidence | `services/tv_filename_parser.py`: `parse_episode_name`, `series_identity`, `resolve_episode_claim` | TV ingestion, acquisition review, manifest mapping | Episode ranges, daily/absolute names, samples/extras, aliases, conflicting IDs/years | Generic absolute-number matching must not preempt an explicit supported season declaration; identity and numbering must consume the same recognized declaration |
| Prowlarr searches | `services/source_search.py`: `ProwlarrClient.search_tv_report` | `TVAcquisition.search` | Independent source results, TV categories, enabled/trusted selection, bounded work | No new provider search client |
| TV release normalization, decisions and coverage plan | `services/tv_acquisition.py`: `_release_decisions`, `search`, `search_seasons`, `prepare`, `select_automatic` | `services/tv_routes.py` search/prepare endpoints; monitoring | Fair source merge, deduplication, profile checks, exact selection context, destination-bound tokens | HTTP-as-magnet assumption; inline recommendation loop becomes the single `plan_releases` owner; automatic batch coverage must not require the whole target from every individual candidate |
| Torrent resolution/transfer | `app.py`: `_resolve_prowlarr_download`, `_resolve_tv_candidate`, `_submit_qbittorrent_candidate`; `services/qbittorrent.py` | Acquisition prepare/submit | Configured-origin allowlist, real hash extraction, hash mismatch rejection, stop-after-metadata/file priorities, transfer identity | No TV-specific second resolver; no eager resolution of every result |
| Claims, intents and diagnostics persistence | `services/acquisition_store.py`: `AcquisitionRepository.intent`, `event`, `transaction`, schema initialization | TV/Movie owners; Follow store | Atomic per-episode claims, request-key idempotency, WAL/recovery, existing Movie data | No separate pack-jobs table or alternate source of acquisition truth |
| Submission and verified import | `services/tv_acquisition.py`: `submit`, `validate_manifest`, `import_completed`; verified-import owner | Manual, bulk, Follow, qBittorrent domain handler | Existing homes, season style, filenames, staging, measured facts, collision checks, cleanup/recovery | Extract one intent-reservation phase from `submit`; do not duplicate its checks in monitoring |
| Task schedule/group association | `services/tv_monitoring.py`: `_run_once`, `task`, `_settle`, `cancel_task` | Existing task routes and worker | Fixed targets, excluded seasons, locks/leases, Cairo scheduling, notification deduplication | Per-episode source loop remains only for excluded grouping cases and other actions; covered group members must not fall through to that loop |
| Desktop review/task UI | `src/features/tv/TVAcquisitionReview.jsx`: default review and `TVMonitoringControls` | `TVWorkspace.jsx` expanded series | CP dialog, sticky summary, reason details, explicit identity/Download actions, 15-second polling, navigation cancellation | No cloned pack dialog, duplicate list, or generic Force download |
| Desktop geometry/styles | `src/features/tv/tv.css`; existing `.tv-follow-task` rule in `src/styles.css` | Same components | Current desktop spacing, typography, controls, task card border/padding and release row layout | Add only narrowly scoped diagnostic wrapping/spacing if needed; do not create competing task-card styles |

## Exact behavior contract

### Frontend

Reuse the current expanded-series Follow panel and `TVAcquisitionReview`; retain all existing controls in place. No new page, layout redesign, or mobile rules.

- Review summary explicitly says **`N selected releases · M of T episodes · size`** so zero selected is not confused with zero results. Keep the sticky summary, destination, extras choice, and current Download selected/available behavior.
- A correctly recognized season pack says **Season pack**, has claimed episode coverage, and enters the existing eligible/resolve state when its identity and other rules pass. A no-year same-title pack enters **identity_review**, with the existing **Confirm this is the selected series** action. A genuine wrong show/year/provider conflict remains blocked behind the existing filter.
- Source diagnostics display **returned results**, **automatic eligibility/review**, and **partial source failures** separately. A failure of an unrelated indexer does not replace the explanation for known returned releases. Reuse existing `<details>` and source list presentation.
- Task counts are mutually exclusive: acquired, queued, waiting, review. A transient `submitting` row counts as waiting and says **Submission pending** until the transfer is acknowledged; reservation alone never counts as queued. Source-related `needs_review` rows with no intent remain scheduled and display **Review required; next automatic search: [Cairo time]**. Transfer/import failures display their distinct existing recovery message; do not promise automatic source reselection for a terminal transfer.
- Render a bounded, expandable source summary per season/episode search, with up to five release titles, indexer names, quality, and each release's own reason codes/messages. The summary may say **21 results returned; none automatically eligible. Some indexers failed.** It must never join unrelated reasons as though they describe one release.
- For source-related review, a **Review season releases** button opens the existing `TVAcquisitionReview` with `{series_id, season, missing_only:true, profile_id:task.profile_id}`. It does not automatically submit, reset task retry times, replace owned episodes, or turn a manual confirmation into Follow trust. Existing manual Download remains the acquisition authorization for any manually chosen release.
- On manual review Close/queued outcome, retain normal task polling and refresh data. Import completion is observed through the existing catalog/task owner, not optimistic UI acquisition. Restore focus to the invoking button; Escape closes the review unless the existing busy rule applies.
- Verify desktop 1366×768 and 1920×1080, long titles/reasons, zero results, loading, partial provider errors, genuine conflicts, identity review, queued packs, and completion. Assert no horizontal overflow, correct disabled/enabled choices, and navigation/Back/Forward without stale task results. Keep existing `.tv-release-summary`, `.tv-release-row`, dialog controls, and task card geometry.

### Backend: release recognition and transport

Keep `parse_episode_name(name)` and `series_identity(release, series, *, ambiguous=False)` public signatures.

1. Introduce one pure internal season-declaration extractor in `tv_filename_parser.py`, used by both functions. Recognize bounded `S02` and `Season 2` declarations after a title, including redundant agreeing `Season 2 S02`. Explicit episode/daily patterns retain precedence. Numeric words in a show title (`1923`, `The 100`) must not become season/episode evidence.
2. Agreeing explicit declarations establish season 2 and end the identity prefix before the declaration. Contradictory declarations (`Season 2 S03`) produce explicit contradictory evidence and no claimed coverage, never a guessed season. Preserve genuine absolute numbering when no explicit season/episode declaration exists. `parse_episode_name` adds `contradictory` defaulting to false; `series_identity` returns conflict for contradictory declarations.
3. For the Garshasp title, return scope `season`, season 2, title `Louie`, year `2010`, matched identity when consistent with canonical metadata, and claimed coverage of the requested regular season-2 episodes. For the FGT title, return season 2 with review identity if same-title ambiguity remains. For an S01 title during S02 review, return zero S02 coverage and `coverage_missing`.
4. Add `TVAcquisition._candidate_transport(row, provider_origin)` as the sole TV field-normalization helper. Classify both provider fields by URI scheme, not field name. Keep valid `magnet:` values as magnets; recognize HTTP(S) values as download links only through `is_allowed_prowlarr_url`. Prefer a valid `downloadUrl` HTTP link over an equivalent allowed HTTP link in `magnetUrl`; preserve a real magnet as fallback. An unsupported HTTP field is not ignored to hide a conflicting usable transport.
5. Normalize `infoHash` and compare it with any real magnet's hash. A conflicting supplied hash stays unverified and blocked; do not discard the supplied identity to make the magnet pass. An allowed HTTP link can be transport-verified before its hash is known, then the existing resolver must establish the real hash. Both fields pointing to different allowed HTTP resources require resolution against the selected known hash; do not infer equivalence from field names.
6. Preserve resolver allowlist, timeout/size limits, hash-swap rejection, and automatic trust recheck at submission. No network fetch in the pure normalization helper. No new identity override, no automatic `confirm_identity=True`, and no profile mutation.

### Backend: one TV coverage planner

Extract `TVAcquisition.plan_releases(decisions, wanted_episode_ids)` from the current recommendation loop. It returns `{recommended:[decision_token], covered_episodes:[int], missing_episodes:[int]}` and is used by manual `search`/`search_seasons` and the new automatic group-selection path. Preserve manual semantics; profile eligibility and current explicit upgrades remain authoritative.

- Eligibility is established before coverage preference. Quality equivalence uses the current manual planner's `sort_key[1:4]`: preferred/allowed status, resolution rank, and custom-format score. At equivalent quality prefer the largest useful disjoint coverage, then retain the remaining existing release-order tie breakers. Do not invent a new source-quality hierarchy, a new size cap, or a globally preferred codec.
- A complete pack wins over equivalent-quality singles covering the same wanted season. A higher-ranked eligible individual release stays ahead of a lower-ranked pack. A selected release's coverage must be within the wanted set and cannot overlap another selected release.
- Use candidate-specific subset targets for manual and automatic season batch decisions: for a release with positive coverage and `episode=None`, `candidate_request.episode_numbers` is its covered subset. The existing automatic behavior incorrectly asks each singleton to cover the whole season if used in a season query; repair that existing target composition rather than bypassing `evaluate_release`.
- Do not silently shrink an already persisted decision after planning. Overlapping/lower-ranked packs that no longer fit the remaining wanted set are not selected; uncovered episodes use the bounded episode fallback. This preserves the current disjoint greedy planner, not a new optimization engine or automatic partial-pack retargeting policy.
- Extend `select_automatic(review, *, resolution_limit=5)` with optional `excluded_episode_ids=()` and `deadline=None` for group fallback. Add `select_automatic_plan(review, *, due_episode_ids, excluded_episode_ids=(), resolution_limit=5, deadline=None)` returning `{decisions:[prepared_decision], covered_episodes:[int], missing_episodes:[int], diagnostics:object}`. Before planning or preparation, exclude selected/actively claimed episodes and releases covering non-due members unless that release covers the complete eligible group under P1. Prepare only identity/transport/trust/availability/quality-eligible candidates whose remaining rejection is an unresolved hash. Resolve in planner order, deduplicate by selected hash, and rerank/recheck after preparation. Existing single-target callers keep their one-decision response and preparation bound; no non-due singleton may be resolved or queued by the group path.

### Backend: Missing season search and bounded work

Add `TVAcquisition.search_missing_season(series_id, season, episode_numbers, profile_id, *, budget=30, query_episode=None)` using existing `search` and `ProwlarrClient.search_tv_report`; it is not a second search implementation. Extend `search` with optional `budget=30`, `query_episode=None` and `preserve_scope=False`, clamp 1–30 seconds, and pass the remaining budget to the provider. Manual callers retain their existing bounds/fallback behavior. Each automatic group has one shared 30-second provider-search allowance: subtract elapsed season search and pass the remainder to each due gap search, stopping when less than one second remains. Each uncovered due episode is searched at most once. Grouped searches set `preserve_scope=True`: query parameters may narrow the provider search, but the original authorized season remains the coverage-evaluation scope. Existing claimed/owned targets are excluded by the planner and reservation rather than removed from a pack claim. A pending fallback resumes through this same grouped owner, never through a second single-target continuation path. Accept completed results when another source fails. Torrent preparation is a separate bounded phase, with at most five resolutions across the group's season and gap selection, using the existing 30-second resolver bound.

Keep the existing 1,800-second monitor-pass lease. Give each worker invocation a 900-second monotonic work deadline, checked before starting a group/query and before each preparation; do not start a 30-second preparation with less than 30 seconds remaining. This deadline and `limit` can defer work but never label it searched or alter its retry clock. Pass the deadline through both selection methods and the remaining resolution allowance through gap fallback; do not reset either bound per gap. Verify that one worker pass cannot outlive its lease. Use an injectable clock in tests rather than real long sleeps.

`TVMonitoring` first settles existing transfers, availability, release eligibility, pending reconciliation, and exclusions through the existing logic. Only then form group work:

- P1 grouping requires an entirely released/missing regular season, complete metadata, every episode inside the task's frozen targets, no queued/claimed member, no excluded member, and a ready destination. At least one member must be due. Other actions/kinds or a season failing these conditions retain per-episode source work.
- Search the full eligible season target set once. A selected full pack may queue all covered group members under P1; single/partial releases from the group may queue only due members. Never issue an independent episode search for a non-due member. If a season result would queue a non-due sibling without covering the entire group, exclude it from that pass.
- After group selection, query only due, uncovered episode gaps. Count each season search or fallback episode query as one work unit against `run_once(limit=...)`; a single pack may cover 13 episodes without being split to satisfy a five-result limit. Leave never-searched deferred gaps' timestamps unchanged. Persist completed work before yielding at the limit.
- Retry timestamps remain per episode. For a failed search, set `last_search` to that search's observed time and `next_retry=last_search+18000` only for due members included in that attempted work. Non-due members and work deferred by budget retain their clocks. A successful shared pack clears source diagnostics and queues its covered members; it does not cause future redundant submissions.
- Future's Cairo midnight and six-hour metadata refresh stay unchanged. Missing target snapshots never absorb episodes aired after Start. Partially owned or partly unreleased seasons are not new grouping cases in this slice. Owned versions are never included in an ordinary intent.
- Keep legacy group-independent outcomes readable. Do not reset existing live retry timestamps, activate drafts, or immediately search at migration time.

### Backend: reservation, association, recovery, and concurrency

Refactor the existing `TVAcquisition.submit` into one authoritative pre-transfer reservation phase and the existing transfer phase:

- Add `reserve_intent(token, request_key)` returning `{intent:dict, decision:dict}`. Extract—not copy—submission validation, current availability/trust/profile/claims/destination checks, materialization, home reservation, and `AcquisitionRepository.intent`. It makes no qBittorrent add. Existing `submit(token, request_key)` uses this same phase and preserves its public response.
- Reject an ordinary automatic batch if a selected episode became owned; do not rely on `owned` resolution ranking to protect a low-quality owned copy. Recheck all selected members immediately before reservation.
- Monitoring uses an idempotency key `task:{task_id}:season:{season}:{prepared_decision_token[:24]}` for a pack; retain the current per-episode key for unchanged single-target paths. The selected decision records the exact requested/covered IDs, profile version, and destination as today.
- Under the acquisition lock, recheck task active state/target membership before reservation. Reserve one intent with atomic claims for every covered episode, then attach that same `intent_id` and state `submitting` to every covered `tv_task_episodes` row in one store transaction before calling the transfer phase. After an acknowledged owned transfer, atomically mark the associated members queued. Reservation/association does not itself prove a transfer exists. One intent and one transfer serve the whole pack.
- Reuse the existing monitor pass lease and acquisition submission lock. Serialize cancellation with reservation/association through the same acquisition lock; retain cancellation's current preview token and manager completion-lock semantics. Do not hold an SQLite transaction open during network work.
- Recover a crash between intent reservation and task association by matching the exact task request-key prefix and the persisted decision's covered IDs before any new search. Attach/recover only the same active task/profile/target coverage. Uncertain ownership becomes review, not adoption by title/hash resemblance.
- Recover a crash after association but before transfer through the existing selected-intent submission path, extended to include `submitting` rows. Exclude any intent-associated row from new source planning. After lost acknowledgement, adopt only the qBittorrent job owned by that intent; repeated passes/restarts must not add again. Retain review with the intent attached when transfer ownership/acknowledgement is uncertain. Deduplicate processing/submit retries per intent within a worker pass even though multiple episode rows reference it.
- For partial verified imports, only actually available, correctly bound/covered episodes become acquired. Retain the existing transfer/import recovery outcome for others. Do not mark all pack members acquired because the intent is ready. Hash/ownership/manifest terminal failures retain review and blocklist protections; never silently retry the same failed hash.
- Cancellation preview already deduplicates intent IDs; include reserved but unassociated intents only when the exact task request-key prefix and persisted target coverage prove task ownership. A selected intent with no possible submitted job may be cancelled and its claims released. Uncertain remote submission remains protected for review; never infer absence from an unavailable qBittorrent response. Verify cancellation still shows/stops one pack transfer, protects unrelated tasks/files, and applies the chosen existing cancellation mode once. This is coverage of the new reservation phase, not a new deletion permission or mode.

### Backend: diagnostics schema and response

In `services/acquisition_store.py`, migrate acquisition schema 3 → 4 by adding `tv_task_episodes.source_diagnostics TEXT NOT NULL DEFAULT '{}'`. Use the existing store initializer, an atomic version-aware migration, and refusal of newer schemas; remove the unconditional version-3 reset. Make migration idempotent. Existing task/episode states, timestamps, profile payloads, claims, intents, events, and all Movie tables are retained. Old rows receive an empty diagnostic object, not an invented classification.

Define a version-1 diagnostic object:

```text
{version:1, state:accepted|no_results|rejected_sources|provider_failed|preparation_failed|review_required,
 result_count:int, automatic_eligible_count:int, resolution_count:int, review_required:bool,
 search_scope:season|episode, query_episode:int|null, season:int, episode_ids:[int], searched_episode_ids:[int], fallback_pending?:bool,
 sources:[{id,name,state,count}], partial:bool,
 candidates:[{title,indexer,quality,coverage:[int],reasons:[{code,message}],review_action:identity|manual_quality|null}],
 summary:string}
```

- `searched_episode_ids` are the due members whose retry clocks may be updated; `episode_ids` are the whole result/pack consideration scope. Bound candidates to five relevant releases, summaries to 500 characters, and source entries to the returned source set. Never include credentials, provider URLs, torrent bytes, or a complete decision payload in diagnostics.
- Build diagnostics in `TVAcquisition.summarize_search(review, *, selected=(), preparation_errors=())`. Keep codes and messages per candidate. Include a review action only when deliberate identity confirmation or manual quality selection could make an otherwise supported, relevant release eligible. A wrong-show/wrong-season/real contradiction is not an identity-confirmation opportunity.
- Precedence: accepted selections first; preparation errors separately; returned relevant reviewable candidates → review_required; other returned decisions → rejected_sources; zero decisions plus failed/timed-out sources → provider_failed; otherwise no_results. Partial source status remains independent in every case. `result_count` counts evaluations, not unique torrents across different searches.
- Existing single-target `select_automatic` fields remain compatible, with additive `diagnostics`; group planning uses the same summary owner. Keep a bounded legacy `error` string for old consumers, generated from the structured summary rather than flattened cross-release reasons.
- In `TVMonitoring.task`, decode diagnostics and expose them on each episode. P2 uses source `needs_review` without an intent plus a five-hour `next_retry`; transfer/import `needs_review` with an intent remains its existing recovery path. `_settle` can report task needs_review while scheduled source searches continue. Counts remain mutually exclusive and their sum equals the number of represented target rows.
- Review completion does not clear an unrelated task failure by UI fiat. A later worker pass can clear source review after a successful source selection or verified manual acquisition. Notifications remain deduplicated and do not create an unread event on every unchanged retry.

### Migration and rollback

Source implementation and disposable-schema migration tests are allowed only after implementation approval. Production DB migration occurs only during separately authorized live activation, because the store initializes in the running application. Before such activation, stop the approved process and take coherent recoverable backups of config, acquisition DB including WAL consistency, TV catalog, jobs, served dist, and source revision.

Version 4 must be refused by an older application. Rollback is not just copying old code over a running upgraded process: stop the approved process, preserve current recovery data, and use a reviewed consistent backup/restore strategy. Once new transfers exist, do not restore an old DB independently of jobs/torrents. A plan/source-only rollout must not open the live store with the new initializer.

## Global constraints

- Change existing owners; no second TV planner, resolver, acquisition ledger, import engine, or cloned release dialog.
- Preserve Movie/TV/IPTV boundaries and original episode filenames/destination conventions.
- Keep quality profiles, automatic trust/identity/availability/manifest checks, explicit Start/Download, and no-seeding verified move/cleanup unchanged.
- Keep unsuccessful Missing/Future retries at exactly 18,000 elapsed seconds; no early independent source retry, silent timing reset, or new Future schedule provider.
- Use `CP_TEST_MODE=1`, one unique OS-temporary `CP_TEST_ROOT`, fake providers/qBittorrent, synthetic media, and a non-production port for implementation verification. Never use live `G:\TV`, `E:\Movies`, or production data in tests.
- Desktop only. Preserve current UI owners/styles and unrelated dirty work present at execution time.
- Commits, pushes, live migrations/task edits, downloads, restarts, deployment, and packaging remain separate authorized actions. No per-task automatic commits despite generic skill examples.

## Review focus

1. Redundant season declarations and number-bearing titles: explicit valid season evidence wins over a generic absolute-number pattern; contradictory declarations stay blocked. Task 1.
2. Prowlarr HTTP links in unexpected fields and hash disagreement: normalization reaches the existing resolver without trusting arbitrary HTTP or losing a conflicting hash. Task 2.
3. Due/non-due sibling targets and a fixed Missing snapshot: a successful approved full pack can satisfy authorized siblings, while failed/deferred searches preserve non-due clocks and do not add future targets. Tasks 3–4.
4. A crash/lost acknowledgement around multi-episode reservation: one intent survives, all covered task rows recover, and qBittorrent receives one add. Task 4.
5. Partial providers and partial import: diagnostics attribute reasons to releases; only verified episodes are acquired; hard transfer failures are not recast as harmless source absence. Tasks 4–5.

## Implementation sequence

P1/P2 and the implementation scope were explicitly approved on 2026-10-10. At execution start re-read `AGENTS.md`, this plan, contract sources, and current dirty state. If implementation exposes another agreed contract conflict, stop that affected portion and raise its separate notice.

### Task 1 — Correct explicit season/title recognition

**Files executed:** modify `services/tv_filename_parser.py`; add shared-owner regressions in `tests/test_tv_follow_season_planning.py` and run existing `tests/test_tv_download_workflow.py` and `tests/test_tv_catalog.py`. No production-title special case.

**Interfaces:** existing parser/identity signatures remain; pure shared season declaration extraction and additive contradictory evidence as defined above.

- [x] Add failing tests for `Louie (2010) Season 2 S02 ...`, S02-only packs, S01 during S02 search, agreeing/contradictory season declarations, `1923`, `The 100`, real absolute numbering, daily/multi-episode/sample names, same-title missing year, wrong year, and conflicting provider ID. Assert exact title/year/season/scope and final release coverage/state, not only a regex match.
- [x] Run `tests.test_tv_download_workflow` and `tests.test_tv_catalog`; record the demonstrated failure before editing the owner.
- [x] Correct the shared parsing/identity owner; preserve episode/daily precedence and retire the conflicting generic-before-season interpretation.
- [x] Rerun those modules and existing ingestion/manifest parser users; the Garshasp-shaped release has matched identity and claimed season-2 coverage, while genuinely conflicting cases remain blocked.

### Task 2 — Normalize TV transport fields and preserve validation

**Files executed:** modify `services/tv_acquisition.py`; add regressions in `tests/test_tv_follow_season_planning.py` and preserve/run existing contract, workflow and resolver tests. Keep `app.py` resolver behavior unchanged unless a demonstrated failure in that owner requires a separately described correction.

**Interfaces:** `_candidate_transport(row, provider_origin)` produces normalized magnet/download/hash/verified facts; public prepare/submit routes keep their contracts.

- [x] Add failing manual/automatic tests for allowed HTTP in `magnetUrl`, magnet in `downloadUrl`, both real magnet and HTTP fallback, wrong-origin HTTP, a conflicting supplied hash, and resolver hash swaps. Assert candidate state, preparation call, final eligibility, and zero adds during review/preparation.
- [x] Run the focused modules and record the HTTP-field failure.
- [x] Normalize by URI scheme in the acquisition owner and route HTTP through the existing resolver. Do not alter source trust or quality to make a test pass.
- [x] Verify the no-year Pirate Bay season pack reaches identity review with a usable confirmation action; after explicit confirmation it can resolve, while automatic selection never confirms it.

### Task 3 — Reuse claimed-coverage planning for season-first Missing

**Files:** modify `services/tv_acquisition.py` and `services/tv_monitoring.py`; extend `tests/test_tv_download_workflow.py`; create `tests/test_tv_follow_season_planning.py`, reusing `TVAcquisitionTests` disposable fixtures.

**Interfaces:** `plan_releases`, budgeted `search`, `search_missing_season`, and `select_automatic_plan` as specified. Preserve single-target `select_automatic` callers.

- [x] Write failing tests: one complete permitted pack plus equal-quality singles selects the pack once; higher-ranked singles are not displaced by inferior pack coverage; automatic season results get per-candidate coverage targets; claimed gaps use bounded episode fallback; partial source failure retains useful results.
- [x] Add P1 boundaries: due/non-due sibling pack coverage, no early independent episode query, unsuccessful/non-due clocks unchanged, owned/queued/partly scoped/unreleased seasons excluded from grouping, fixed snapshot excludes later aired targets, and other actions/kinds keep their grouping.
- [x] Run the new module plus `tests.test_tv_download_workflow` and capture failures.
- [x] Extract the existing recommendation loop into the authoritative planner; extend existing search/selection for automatic batch subsets and budget propagation; add Missing-only grouping. Remove the duplicate inline recommendation implementation.
- [x] Verify work-unit limits, one season query per group, disjoint selected coverage, due filtering before preparation, shared search/resolution budgets, the pass deadline staying below lease expiry, no download while planning, and unchanged manual recommendations/selection freedom.

### Task 4 — Persist grouped association and recover exactly once

**Files:** modify `services/tv_acquisition.py`, `services/tv_monitoring.py`; extend `tests/test_tv_follow_season_planning.py`, `tests/test_verified_tv_acquisition.py`, and `tests/test_tv_download_contracts.py`.

**Interfaces:** `reserve_intent(token, request_key)` reused by submit and monitoring; existing claims/intents/jobs remain the only ownership records.

- [x] Add failing complete-path tests: one pack gives one intent/one add/multiple task associations; correct manifest selects intended videos; all verified files publish once and task counts reflect them; owned/collision cases are protected.
- [x] Inject crashes before association, after association/before add, and after a lost acknowledgement. Restart store/monitor instances and assert one recovered intent, one add, exact task membership, truthful submitting/queued counts, cancellation of proven unsubmitted reservations, and no unrelated job adoption.
- [x] Cover overlapping manual requests/tasks, a member becoming owned between selection and reserve, trust/profile/destination changes, cancellation while search is in flight, shared-intent cancellation deduplication, partial import, and terminal hash/manifest failures.
- [x] Refactor submission's reservation phase into one owner and atomically attach all covered task members before transfer. Reuse existing locks/leases; check lock order and persist before yielding work limits.
- [x] Verify existing single-episode and bulk workflows and normal move/cleanup/recovery suites. A ready intent or title claim alone must never make every pack member acquired.

### Task 5 — Store and display truthful source outcomes

**Files:** modify `services/acquisition_store.py`, `services/tv_acquisition.py`, `services/tv_monitoring.py`, `src/features/tv/TVAcquisitionReview.jsx`; narrowly amend `src/features/tv/tv.css` only if required. Extend `tests/test_tv_download_contracts.py`; create `tests/test_tv_source_diagnostics.py`; extend `tests/native_tv_server.py`; create `tests/e2e/tv-follow-season-packs.spec.js`.

**Interfaces:** schema version 4 `source_diagnostics`; `summarize_search`; additive task/selection diagnostics; source review action reuses existing review endpoint/component.

- [x] Add failing version-3 migration/reopen tests preserving task states, timings, profiles, claims, intents, notifications and Movie data; reject version 5 and prevent unconditional version reset. Test legacy empty diagnostics without guessed reason classification.
- [x] Assert exact backend classifications for 21 results plus three failed sources, zero results/all-successful sources, zero results/failed sources, identity-review candidates, manual-quality candidates, real conflicts, unresolved supported links, and preparation errors. Assert no credential/URL leakage and five-candidate bound.
- [x] Add P2 tests: needs_review count rather than waiting, retry at exactly 18,000 seconds, unchanged unread notification count on repeated identical failures, automatic recovery from a later valid source, manual confirmation not reused automatically, and transfer review remaining distinct.
- [x] Implement schema migration and the authoritative summary; update legacy strings/counts/scheduling projection from those persisted facts.
- [x] Extend the existing Follow/review UI with attributed expandable outcomes and Review season releases; clarify selected-release summary text. Keep layout/control owners and existing confirmation/submission boundaries.
- [x] Assert real fixture backend JSON and compiled desktop rendering for the three screenshot release cases, identity confirmation, partial sources, source review, pack queue/import, long content, Close/Escape/focus restoration, repeated navigation and Back/Forward. Do not rely solely on route mocks for the motivating path.

### Task 6 — Complete verification and contract comparison

**Files:** implementation evidence under `docs/verification/tv-follow-season-packs/`; update this plan's executed checkboxes/results and `docs/tv-contracts.md` only for Dante's explicitly approved decisions.

- [x] Run baseline/focused/broader/build/desktop gates below and record exact outcomes, skips, and unrelated failures.
- [x] Compare each observed behavior against P1/P2 and the unchanged contracts. Record any deviation prominently; do not weaken tests to claim completion.
- [x] Present source-only and isolated results. Leave production app/task/DB/dist untouched until separately authorized live activation.

**Execution result, 2026-10-10:** Source delivered from managed branch `codex/tv-follow-season-packs` to the original checkout with SHA-256 comparison. All six important review findings were corrected in the authoritative owners. The final TV gate passed 184 checks plus a separate 13-episode import/cleanup regression; all 34 new Python regressions also passed from the original checkout. Node passed 119 tests, the isolated frontend build succeeded, and 30 compiled desktop tests passed without skips. The complete Python run executed 1700 tests with six failures: five recorded baseline failures plus an IPTV timing failure in unchanged code. The verification report retains exact logs, acceptance evidence and investigation of that extra failure. This is source/isolated completion; no live migration, restart, download, dist activation, commit or push was performed.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Check |
| --- | --- | --- | --- | --- |
| S01 known successful shape, 13 missing episodes | Manual season review → explicit Download → synthetic completion | One 1080p BluRay pack, 13 selected/verified bindings, one add, verified cleanup; no Follow task created | Search/submit/import/manual UI | Workflow + normal-import + real fixture desktop |
| Garshasp S02 title with year and redundant agreeing season | Manual and automatic review | Preferred quality, matched Louie/2010 identity, season 2 and 13 claimed targets, supported hash preparation; actual files still verified later | Parser/acquisition | Exact parsed values plus decision/API/UI |
| No-year FGT S02 with HTTP in `magnetUrl` | Manual review | 13 claimed S02 episodes, identity_review with confirmation; HTTP reaches allowed resolver; no add before Download | Parser/transport/UI | Real-style provider fields plus desktop |
| Same FGT result | Automatic Missing | No automatic identity confirmation; source review outcome and five-hour retry unless another eligible source wins | Selection/monitor | Policy/call assertions + counts |
| S01 returned during S02 search | Show blocked | coverage_missing, no S02 claim, cannot select | Coverage/UI | Backend decision and disabled checkbox |
| Wrong year/provider ID or contradictory seasons | Search/prepare | Conflict retained; no confirmation bypass, no add | Shared identity/evaluator | Negative regression fixtures |
| Number-bearing title, daily/range/absolute/sample fixtures | Parse and existing ingestion/manifest path | No accidental season claim; established meanings/ignored samples preserved | Shared parser users | Catalog + workflow + verified acquisition |
| Allowed HTTP versus wrong-origin HTTP or conflicting hashes | Review/prepare/submit | Allowed scheme-normalized resolver succeeds; hostile/disagreeing transport rejected | TV transport/resolver | Manual + automatic + hash-swap tests |
| Fully missing released season, equal-quality pack/singles | Due Follow Missing pass | Season query first; complete pack selected, one intent/add, all covered task rows attached | Planner/monitor/store | Full integration test |
| Higher quality eligible single plus lower quality pack | Plan | Quality precedence preserved; no forced inferior pack; disjoint combination/gaps displayed | Shared planner | Exact recommended coverage/order |
| Some group members have later retry times | Due group pass | Full successful pack may satisfy authorized siblings under P1; no independent early episode queries; failure leaves non-due clocks unchanged | Scheduler/planner | Timestamp/request assertions |
| Partial ownership, unreleased episode, partial task scope, exclusion or claim | Follow pass | Grouping not enabled; no redownload, future-target expansion, or cross-owner acquisition | Monitor/claims | Boundary tests |
| Pack claim or manifest incomplete | Plan then metadata verification | Search gaps get episode fallback; actual invalid manifest stops payload and retains existing failure/recovery protection | Search + manifest | Files/priorities/failure assertions |
| Budget exhausted or work limit reached | Worker pass | Completed work persisted; deferred work is not marked searched and clocks stay unchanged; one pack not split | Worker | Fake clock/provider calls/restart |
| Crash/lost acknowledgement across reservation/association/add | Restart | Same intent and exact multi-episode association recovered; one add; no independent duplicate jobs | Store/monitor/qBittorrent | Fault-injection integration |
| Manual/task overlap, changed ownership/trust/profile/home | Reserve/submit | Revalidate and block stale selection; unrelated claims/media preserved | Acquisition/claims | Concurrency/revalidation tests |
| Partial import, ready intent without verified binding | Monitor | Only proven episodes acquired; others show recovery review; no fabricated completion | Import/monitor | Job/catalog/API/UI assertions |
| Cancel task with one shared pack intent | Existing cancellation mode | One transfer handled once, token rechecked, shared/unrelated/playing media protected | Cancellation | Existing suite + shared pack case |
| 21 candidates and three failed sources | Follow display | Returned/rejected/review results attributed per release; partial failures separate, no zero-results claim | Diagnostics/API/UI | Stored JSON + rendered assertions |
| Reviewable result, no intent | Wait then manual review or later source retry | Review count; exact five-hour retry; no silent profile/trust changes; confirmation applies only to reviewed release | Review/monitor | Backend + real fixture UI |
| Empty/loading/long content/partial failure | Desktop navigation and review | Clear states, existing geometry, no horizontal overflow, usable focus/Escape/Back/Forward | UI | Two desktop viewports |
| Version-3 data with legacy tasks and Movie intents | Initialize disposable upgraded store twice | Version 4 once, unchanged existing rows/times/profiles/claims; old diagnostic unknown, future schemas refused | Acquisition store | Migration/reopen snapshots |
| Future/Upgrade/selected/bulk/Movie/IPTV and manual multi-season | Existing user paths | Targeting, scheduling, profile data and action boundaries retained; bulk remains one-shot | Affected shared callers | Focused broader suites + existing E2E |

## Verification and rollout

### Execution baseline and isolated commands

Do not run these commands for the planning request. At approved execution, establish current Git/runtime/data baseline and use a disposable environment before any application edit. Keep test outputs/evidence outside live data and compile UI outside served dist.

```powershell
$env:CP_TEST_MODE = '1'
$env:CP_TEST_ROOT = Join-Path ([IO.Path]::GetTempPath()) ('cp-tv-follow-packs-' + [guid]::NewGuid().ToString('N'))
$env:CP_TEST_QBT_MODE = 'system'
$env:CP_TEST_DIST_DIR = Join-Path $env:CP_TEST_ROOT 'dist'
$env:CP_TV_E2E = '1'
$env:CP_E2E_PORT = '5117'
```

Use `.venv\Scripts\python.exe`, whose existence was confirmed. Confirm timezone dependencies in that interpreter; do not install new dependencies or use a fallback timezone to hide a failure. Each check's exit code and summary must be recorded.

**Baseline:** Before code changes run the existing focused modules and relevant full Python suite in this isolated environment. Record known failing tests with actual current output. The earlier evidence's `test_streaming_modal_shows_loading_feedback_until_iframe_loads` failure is a lead to check, not permission to assume or fix it.

**Focused gates (new modules exist only after approved implementation):**

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_tv_download_workflow tests.test_tv_download_contracts tests.test_tv_follow_season_planning tests.test_tv_source_diagnostics tests.test_verified_tv_acquisition
& .\.venv\Scripts\python.exe -m unittest tests.test_tv_catalog tests.test_tv_library_import tests.test_tv_import_destinations tests.test_tv_normal_import tests.test_tv_numeric_repair tests.test_tv_coverage_contract tests.test_tv_bulk_actions tests.test_native_tv_safety_baseline
```

**Broader gates:**

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
$tvPlanNodeTests = @(rg --files tests -g '*.test.mjs')
& node --test @tvPlanNodeTests
& npm.cmd run build -- --outDir $env:CP_TEST_DIST_DIR
```

A full-suite failure must be reported separately from focused passes. New failures in affected parser/acquisition/store/transfer/UI callers block completion. A demonstrably pre-existing unrelated failure must be reproduced/identified and left visible, not weakened or relabeled as passing.

**Compiled desktop gate:** Reuse `tools/run_playwright_e2e.ps1` with `CP_TV_E2E=1`; it creates its own unique OS-temp root, builds there, uses fake TV fixtures and port 5117, and manages only its isolated process. Verify the port is free first. Extend the new spec with desktop viewport-specific tests; do not change the global config to mobile.

```powershell
$tvPackDesktopSpecs = @('tv-follow-season-packs', 'tv-download-contracts', 'tv-normal-import', 'tv-stabilization', 'native-tv')
foreach ($tvPackSpec in $tvPackDesktopSpecs) {
    & npm.cmd run test:e2e -- ('tests/e2e/' + $tvPackSpec + '.spec.js')
    if ($LASTEXITCODE -ne 0) { throw ('Desktop gate failed: ' + $tvPackSpec) }
}
```

Retain meaningful screenshots/logs under `docs/verification/tv-follow-season-packs/`, redacted and linked to fixture state. The full motivating gate must use actual compiled UI and real fixture backend/store/transfer transitions, then assert available episode paths in Versions. Browser-only mocked responses are supplementary diagnostics tests.

**Execution refinement:** Run each complete spec against a fresh disposable server. Existing specs leave queued fixture claims behind when combined into one server; separate runs preserve their original assertions and prevent inherited test state from blocking later scenarios. Production lifecycle rules are unchanged.

### Live activation, only with separate authorization

1. Present source/isolated results and obtain the authorization applicable to deployment, restart, schema migration, and the existing running task. A plan approval is not live approval.
2. Re-identify process/checkout/config/data/dist ownership. Back up the consistent recovery set described above. Record task targets, retry times, profile/version/trust selections and schema version.
3. Explain that restarting an already active Missing task can start real downloads on its next eligible worker pass. Do not use a passive live UI check as hidden permission to download.
4. Deploy/build only the authorized bundle/process and verify HTTP hashes plus rendered desktop results. Do not assume a browser refresh loads changed Python source.
5. If real acquisition is authorized, trace one actual pack through search → selection → one intent → metadata/files → payload → measured import → per-episode counts → cleanup. Report unavailable source/manifests honestly; do not promise the screenshot torrent is usable from its title alone.
6. Roll back/preserve recovery on ownership, duplicate submission, incorrect target selection, unsupported migration, lost diagnostics, or verified-import regressions. Use a consistent plan for new transfers; never restore just one stale recovery file.

**Reporting:** State source-only, isolated, and live status separately; exact test counts/skips/failures; migrated environments; pack/episode acquisition proof; remaining uncertainties; and any difference from approved contracts. No completion claim based solely on a parser helper or selected request parameters.


