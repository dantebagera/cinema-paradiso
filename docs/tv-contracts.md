# Cinema Paradiso TV contracts

**Status:** Bounded slice implemented in source; isolated verification and its exact limitations are recorded below. No live activation. Remaining discussion items are deferred.
**Created:** 2026-10-08.
**Owner of product decisions:** Dante.
**Scope recorded so far:** TV download destinations, folder structure, Follow task activation/lifecycle, download selection across seasons, and visible source settings for automatic acquisition. This is not yet a complete inventory of every TV contract.

## Purpose and authority

Use this file to discuss, amend, and record TV behavior before writing an implementation plan. Keep future discussion and decisions in this same file.

- Separate existing agreed rules, observed implementation, proposals, and approved amendments.
- A proposal becomes an agreed rule only after Dante explicitly decides it. Record the decision, date, and exact scope.
- Document approval does not authorize application implementation, live data changes, downloads, restarts, deployment, commits, or releases.
- Keep earlier decisions readable. When a rule changes, identify which rule it replaces rather than silently rewriting its history.
- Follow the contract-change notice required by `../AGENTS.md` before implementing any amendment to an agreed rule.

### Implementation handoff decision, 2026-10-08

Dante requested: save this file, make and save an implementation plan using the agreed actions, and create a new task with the plan/handover to start implementation. He then explicitly confirmed that five-hour retries are settled, clarified that all/selected-season download controls sit underneath Follow, and selected **Open release review** for those buttons.

The bounded slice is: metadata-derived homes for genuinely new collections using the saved canonical show title and first-air year; preserve established existing homes/season conventions; independent Movie/TV automatic-source multi-select dialogs; all/selected-season manual release review in the lower controls; the settled five-hour Follow source-search interval; and truthful readiness/progress plus supported link preparation needed for these paths. The implementation plan defines conservative blocked outcomes for unresolved naming/root/ownership cases instead of guessing. It does not authorize reorganisation of existing flat collections, different title-language policy, automatic lower-button release selection, new schedule providers, live configuration/data changes, downloads, deployment, restart, commit, or release.

Earlier Pending entries below remain the history of discussion. Only the bounded slice and explicitly settled decisions above are handed off; a deferred exception is not permission to invent product behavior. See [the implementation plan](plans/2026-10-08-tv-download-contracts-implementation.md).

### Source implementation record, 2026-10-08

The authorized slice now has independent Movie/TV Settings selectors and effective automatic-source policies; safe new metadata homes reserved at Download/Start and physically created only for verified publication; lower all/checked-season manual review; supported automatic link preparation; readiness-blocked drafts; five-hour Missing/Future source retries with Cairo date-boundary eligibility; and task polling with counts, times and rejection errors. Established homes/season styles, original filenames, verified move/cleanup, existing jobs, one-shot bulk and separate Movie/watchlist/AI/IPTV responsibilities are retained.

The new TV source choices are configured only in disposable tests (fixture LimeTorrents/1337x). Existing flat Lucifer-shaped collections still require destination review. No live config/catalog/task/library change, restart, deployment, commit or release occurred. See [implementation evidence and contract comparison](verification/tv-download-contracts.md) for exact test results, the reproduced pre-existing streaming-test failure, and the conservative folder-recovery exception. This record does not promote the historical open/deferred items into approved behavior.

## Terms

| Term | Meaning | Example |
| --- | --- | --- |
| TV library root | A configured directory inside which CP may store TV shows. | `G:\TV` in Dante's current configuration |
| Show home | A directory belonging to one specific TV series. | Proposed example: `G:\TV\Louie (2010)` |
| Approved show folder | An existing folder that CP has explicitly associated with a particular series. This is a CP ownership record, not Windows permission. | An approved existing collection folder |
| Season destination | The directory where verified episodes from a particular season enter the library. | Proposed example: `G:\TV\Louie (2010)\Season 01` |
| Start year | The year the series first aired, from series metadata. It is not the selected season's year or torrent release year. | `2010` for the Louie example |
| Torrent folder tree | The folders and files actually listed inside a torrent. The search result's release title alone does not establish this structure. | A release folder containing several episode files |
| Staging | Temporary storage used while downloading and verifying files, separate from the TV library. | CP's configured torrent staging directory |

## Existing storage contracts

These rules are carried forward from the approved [normal TV storage plan](plans/2026-10-05-tv-download-storage-cp-normal-behavior.md). They describe the existing agreement, not fresh implementation approval or new live verification.

| ID | Existing agreed rule | Boundary or exception |
| --- | --- | --- |
| TV-BASE-01 | Downloads must resolve a safe destination inside a configured TV library root. Staging and library storage remain separate. | A configured root alone does not currently establish a show home. |
| TV-BASE-02 | Continue an existing approved show collection and its established season-folder convention. Ask for a choice when valid show homes are ambiguous. | Do not silently select by root order, folder-title resemblance, or approval order. |
| TV-BASE-03 | A show without an approved, resolvable home cannot currently download. | New-show naming and creation were explicitly excluded from the earlier scope. This is the rule under discussion in TV-CHANGE-01. |
| TV-BASE-04 | Preserve episode filenames and validate selected episodes against the actual torrent files. | A search result claiming a whole season does not prove actual episode coverage. Separate unselected files are skipped; inseparable extra episodes require the existing explicit allowance. |
| TV-BASE-05 | New ordinary TV jobs download temporarily, verify the videos, publish them to the resolved season destination and TV catalog, then remove the completed torrent and its staged copies. | Partial or failed imports retain recovery material. Historic jobs retain their recorded destination and lifecycle. |
| TV-BASE-06 | Do not overwrite different existing content during an ordinary import. Identical content may be reused only with compatible episode ownership. | Explicit upgrades follow the existing separate-version behavior. Conflicting content or ownership requires review. |
| TV-BASE-07 | Manual downloads, bulk downloads, and Follow tasks use the same authoritative TV destination and lifecycle rules. | No separate route-specific destination rules. |
| TV-BASE-08 | Preserve TV identity, episode mapping, quality validation, retry protection, and recovery. | TV contracts do not silently change Movie or IPTV behavior. |

**Observed implementation, checked 2026-10-08:** The TV importer places each verified video's original filename directly in the chosen season destination. It does not reproduce the torrent's enclosing folder tree in the library. The approved-home requirement applies to both packaged torrents and loose episode files.

### TV-BASE-02 confirmation: Continue the established season style

**Confirmed by Dante, 2026-10-08:** After checking the rule and South Park's actual folders, Dante clarified that the names were `Season 27` and `Season 28`, and said "it is ok." Keep the existing rule: reuse the established season destination, or derive a missing season folder from the show's consistent existing season naming convention. This confirms the existing behavior; it is not a request to rename the collection or add another naming style.

**Current evidence:** South Park's saved home is `G:\TV\South Park`; its folders use `Season 01`, `Season 02`, and the same convention through later seasons. A read-only check of the current destination resolver selected `G:\TV\South Park\Season 27` and `G:\TV\South Park\Season 28`; the catalog's corresponding episode paths agree. The earlier numeric folder was the TMDB-ID path `G:\TV\2190` and must not replace this established home.

## TV-CHANGE-01: Metadata-based folders for new TV collections

**Status:** Proposed by Dante; the full amendment and its edge cases remain under discussion. Creating this document records the discussion and does not settle the unresolved choices below.

**Dante's proposal, 2026-10-08:** "we should make cp creats a tree depends on meta data, like the folder name should be the show name and start year."

### Problem and intended outcome

Louie's season search found a selectable 4.39 GB LimeTorrents release claiming all 13 selected episodes. The saved review had no approved destination, and Louie had no local catalog entry or approved folder. The dialog disabled downloading while saying to choose a folder, but supplied no first-time folder setup action.

Dante wants CP to establish a metadata-based folder tree so a new show can download into the configured TV library and later seasons can join the same collection.

### Proposed contract change

- **CURRENT RULE:** An approved, established show destination must already exist; first-time show-folder creation is excluded.
- **PROPOSED RULE:** CP can derive a new show home from the selected series' metadata using the show name and start year. The precise rules below require agreement before planning implementation.
- **WHAT DANTE WILL SEE:** A proposed destination such as `G:\TV\Louie (2010)\Season 01`; the absence of an existing Louie folder would no longer be a blocker by itself.
- **AFFECTED AREAS:** Manual episode/season/selection downloads, bulk downloads, Follow tasks, destination preview, folder ownership, import, and recovery.
- **REASON:** First-time TV downloads need a destination, and later seasons should continue the same collection.
- **COST OR RISK:** Missing metadata, unsafe Windows names, ambiguous existing folders, and different shows sharing a proposed folder name need defined outcomes. A folder name alone cannot prove series identity.
- **ALTERNATIVE:** Use the torrent's original enclosing release folder. Different releases and seasons can produce separate top-level folders for one show.
- **RECOMMENDATION:** Use metadata to establish new collections while preserving existing approved collection homes and their season conventions. Preserve episode filenames and the existing verified move/cleanup lifecycle.
- **DANTE'S EXPLICIT DECISION:** Pending confirmation of the complete amendment. No application changes authorized by this entry.

### Suggested folder tree

This is the proposed format, not an implemented or fully approved rule:

```text
G:\TV\
└── Louie (2010)\
    ├── Season 01\
    │   ├── original-episode-filename.mkv
    │   └── ...
    └── Season 02\
```

### Decisions still to settle

| Decision | Proposal or recommendation | Decision status |
| --- | --- | --- |
| Which collections receive the new naming rule? | New collections only; preserve existing approved homes and season conventions. No automatic library rename or migration. | Pending |
| Exact show-folder format | `Show Name (YYYY)`, using the series' first-air year. | Pending |
| Which metadata title/language? | Define which series title CP uses; do not let the selected torrent's release title choose the home. | Pending |
| New season-folder format and specials | `Season 01`, `Season 02`, etc. was proposed. Specials naming is not yet discussed. | Pending |
| Existing torrent tree or loose episode files | Both should use the same metadata destination rule, with episode filenames preserved. | Pending |
| Preview, confirmation, and creation timing | Show the destination before submission; create physical library folders only when verified files are ready to import. Decide whether the Download action alone confirms the proposed home. | Pending |
| Missing or uncertain title/start year | Define the user-visible resolution; do not invent a year. | Pending |
| Windows-invalid characters and name collisions | Define deterministic safe naming and conflict handling without assuming an existing directory belongs to this series. | Pending |
| Unassigned folder already at the proposed path | Define how ownership is established before reuse; do not merge merely because names match. | Pending |
| Metadata changes after a home is established | Keep the saved home stable; do not silently rename or relocate files. | Pending |
| More than one configured TV root | Define how CP selects or asks for a root. Dante currently has `G:\TV`. | Pending |
| Failure, cancellation, or concurrent first downloads | Define ownership persistence, folder creation/reuse, and recovery without overwriting or deleting unrelated content. | Pending |

## Existing Follow and download contracts

**Source:** [TV Library completeness plan: Follow and download agreed direction](plans/tv-library-completeness-maintenance-and-coverage-plan.md). Current UI and service behavior were inspected on 2026-10-08; no task was saved or started during this review.

| ID | Existing agreed rule | What it means for Dante |
| --- | --- | --- |
| TV-FOLLOW-01 | Choosing options and previewing targets do not start acquisition. Saving creates a draft. Only explicitly starting that saved draft activates it. | Current sequence: Preview targets -> Save draft -> Start on the saved task row. Start is rendered only for a draft row, not beside the preview controls. |
| TV-FOLLOW-02 | Whole series -> Missing targets released regular episodes currently missing across the series. Selected season -> Missing limits the same action to one season. | A started Missing task keeps retrying missing sources until its targets are acquired or it is cancelled. It does not follow later unreleased episodes. |
| TV-FOLLOW-03 | Future follows eligible newly released episodes in the chosen whole-series or single-season scope, refreshing metadata and retrying sources. | Whole-series Future can include later seasons. It completes only with ended-series evidence and eligible targets acquired. A season-only task may require explicit season-end confirmation. Future is unavailable for a series marked ended. |
| TV-FOLLOW-04 | Upgrade requires a provably better eligible source under the chosen quality profile. | Owned copies are protected until the replacement is verified; selecting Upgrade does not mean redownload everything. |
| TV-FOLLOW-05 | Selected episodes can span seasons; selected future episodes wait for release. | The Follow panel supports individual cross-season episode selection, but has no multi-season checklist. |
| TV-FOLLOW-06 | TV Library's selected-show bulk Download is a one-shot action for released missing episodes, distinct from a continuing Follow task. | Report unavailable sources without creating continuing Follow behavior. |
| TV-FOLLOW-07 | Explicit cancellation and task history remain part of the task contract. | Cancelling search does not silently authorize deletion of existing library files. |

**Screenshot reviewed, 2026-10-08:** Whole series -> Missing preview shows 80 released missing targets and 13 owned episodes. Tasks says "No active tasks" and history is empty, so there is no saved draft row on which the current UI can display Start. Seasons 2-6 each report a missing approved show destination; activation alone does not resolve those destination blockers.

**Current direct-download controls:** In the expanded series view, Download season, Select all released, Select missing, the owned-episode upgrade checkbox, and Download selected apply to the currently displayed season. Their target is built with that season. Whole-series Missing already exists in the separate Follow task workflow; a direct all-seasons action and season checklist are absent from these controls.

## TV-CHANGE-02: Clear activation and downloads across seasons

**Status:** Requested behavior recorded; exact interaction and lifecycle decisions pending. No application implementation approved.

**Dante's request, 2026-10-08:** Review the existing Follow and download rule, explain the absent activation button, and provide a way to download all seasons or select several seasons without doing them one by one.

**Scope clarified and confirmed by Dante:** Download all seasons and Download selected seasons refer to the lower direct-download controls beside the displayed season, underneath Follow and download. They are not new Follow tasks and must not inherit Follow's five-hour retry interval. The existing Library bulk action also remains one-shot. Dante explicitly selected **Open release review (recommended; preserves the current download workflow)**. Opening review does not queue downloads; explicit release submission does.

### Proposed contract change

- **CURRENT RULE:** Follow requires a saved draft before its Start control appears. The direct download controls address one displayed season. Follow supports whole series, one season, or individual episodes across seasons.
- **PROPOSED RULE:** Provide a clear way to download across all seasons or a checked set of seasons, and make the activation path understandable. Whether these are one-shot downloads, continuing tasks, or both remains Dante's decision.
- **WHAT DANTE WILL SEE:** A whole-series download choice and a way to select, for example, seasons 2, 3, and 5 together. An explicit action starts only the scope and lifecycle agreed below.
- **AFFECTED AREAS:** Expanded TV series controls, Follow configuration/preview/tasks, acquisition target selection, and destination preview for each selected season. Other callers of shared owners must preserve their existing behavior.
- **REASON:** Repeating the same manual download operation season by season is unnecessary, and hiding Start behind an uncreated draft makes activation hard to discover.
- **COST OR RISK:** A one-shot download and a continuing retry task have different effects. The labels must not silently create future following, redownload owned episodes, or submit duplicate overlapping acquisitions. Every targeted season still needs a valid destination.
- **ALTERNATIVE:** Use the existing Whole series -> Missing task workflow, or select individual episodes across seasons. Neither supplies the requested direct multi-season selection control.
- **RECOMMENDATION:** Keep the existing explicit-start safeguard. Give direct downloads an all-seasons/selected-seasons scope with clear preview and submission; retain continuing retry/future behavior as explicit Follow choices. This is a recommendation, not an approved change.
- **DANTE'S EXPLICIT DECISION:** Pending.

### Decisions still to settle

| Decision | Recommendation or question | Decision status |
| --- | --- | --- |
| One-shot or continuing action | Lower Download all/selected seasons stays separate from Follow; no persistent five-hour retry task is created. | Confirmed by Dante |
| Meaning of Download all | Recommend released missing regular episodes across the chosen seasons, skipping owned and already queued episodes. Upgrades remain a separate explicit action. | Pending |
| Scope controls | All seasons and a checklist for several selected seasons in the lower direct-download controls, without requiring episode-by-episode selection. Extending Follow scope is deferred. | Lower-control location confirmed; detailed interaction pending |
| Start visibility | Preserve Save draft -> Start, or add a separately explicit action that saves and starts the configured task. Preview or Save draft must never silently activate it. | Pending |
| Release review | Reuse manual release selection across seasons. No automatic release submission from the lower buttons. | Explicitly selected by Dante |
| Partial sources or destination blockers | Define how the preview reports each season, what can be submitted, and whether eligible seasons may proceed while others remain blocked. | Pending |
| Specials and future episodes | Define whether season 0 is selectable. Unreleased episodes must not enter a one-shot released-only download; waiting/following requires explicit scope. | Pending |
| Overlapping packs and active work | Preserve exact episode coverage and duplicate protection when season packs, individual releases, and existing transfers overlap. | Pending |

### Live investigation: Activated Lucifer task with no downloads

**Checked 2026-10-08; read-only investigation:** Dante saved and started a Whole series -> Missing task for Lucifer (local series 28, TMDB 63174), with 80 targets and Safe HD. Task ID: `22c584a07ec041d6ae80216c36a7189a`. The worker is active; the inspected snapshot had searched S02E01-S02E05, recorded 303 release decisions, accepted none, and created no acquisition intents. Five targets were in retry and 75 still waiting at that snapshot. These counts are observations, not a claim about later progress.

Confirmed causes and visibility gaps:

1. Automatic acquisition requires trusted-indexer, series-identity, and availability evidence. The current `download_trusted_indexers` configuration is empty. All 303 inspected candidates had `trusted_indexer=false` and an automatic-source rejection; other candidates also had transport, unresolved torrent identity, manual-only quality, or coverage objections. This is not evidence that no torrents exist. The worker collapses these candidate rejections to the episode error "No source found."
2. Lucifer's approved path is `G:\TV\Lucifer S01 Season 1 Complete HDTV XviD-AFG`, with no season subfolders and no saved preferred home. The current resolver returns `needs_home` for season 2. Even an eligible release would encounter this independent destination blocker. Defining only new-show naming does not settle how to continue an existing flat single-season collection.
3. Start marks the task running without rejecting the unresolved destination before activation. The task-level error remains empty while its episode records carry retry errors.
4. The Follow panel reads task data on mount and after local task actions, without background polling. It displays acquired counts and the task-level error, but omits episode search/retry errors and their detailed candidate rejection reasons. Recorded notifications say "No source yet" for those five episodes, but do not expose the trusted-indexer configuration blocker.

**Contract decisions still needed:** Define pre-Start readiness checks, truthful live task activity and rejection reporting, automatic source trust/setup, and destination resolution for an existing flat season collection. Do not silently relax automatic validation or reorganize existing files to address these gaps. No task, configuration, code, or live catalog was changed by the investigation.

## TV-CHANGE-03: Visible and effective automatic TV source settings

**Status:** Dante specified separate Movie and TV multi-select dialogs, YTS as the movie default, and LimeTorrents plus 1337x as the initial TV selection for testing. This product direction is recorded; remaining behavior decisions and an implementation plan are still required. No live settings or application code changed.

**Dante's request, 2026-10-08:** Check the remembered YTS default for movie bulk downloads and whether Settings clearly exposes equivalent source options for TV shows.

### Confirmed current behavior

The rendered desktop Settings page and its live configuration response were checked read-only:

| Settings surface | What is displayed and currently selected | Actual responsibility |
| --- | --- | --- |
| Prowlarr -> Release watchlist trust -> Trusted indexers | YTS is the only checked indexer. The dialog is titled "Trusted release watchlist indexers" and describes marking followed movies Available. | Edits `trusted_release_indexers`, currently `["1"]`, where indexer 1 is YTS. |
| Prowlarr -> Automation defaults -> Download trusted indexers | "Use release trusted indexers" is selected. The other displayed option is "Use all enabled indexers." | Movie bulk download resolves this mode through `_effective_download_trusted_indexer_ids`; current mode therefore resolves to YTS. |
| AI Control -> AI Control download trust | "YTS trusted" and a separate Trusted indexers dialog. | Edits AI Control's own movie-source trust selection. |
| Native TV library | Enable native TV and TV library roots, currently `G:\TV`. | No automatic TV source selector, effective-source summary, or missing-trust explanation. |
| Quality Profiles | Quality/source-format eligibility, cutoff, and related policy fields. | These fields do not select torrent indexers. |

**Confirmed ownership mismatch:** `app.py` supplies TV acquisition with raw `download_trusted_indexers` for automatic trust, rather than the effective selection used by movie bulk downloads. That raw list is currently empty. The Settings frontend neither displays, loads into its form, nor submits an editor for this list. TV searches restrict sources to that list only in backend `custom` mode; otherwise they search enabled TV-capable sources. The UI offers only `release` and `all`, with no custom selection. Search eligibility and automatic trust are therefore different in the current TV path.

Consequences: the UI can show "Use release trusted indexers" and YTS trusted while TV automatic trust remains empty. Switching the displayed mode to "Use all enabled indexers" does not populate the raw list used by TV trust. Merely selecting more movie release-watchlist indexers also does not populate it. A working TV source policy cannot be configured through the current controls.

### Dante's specified direction, 2026-10-08

| Setting | Selection interface | Default or initial selection |
| --- | --- | --- |
| Movie trusted indexers | A Settings button opens a checkbox dialog allowing one or several indexers. The user can add sources or replace the initial choice later. | YTS remains the movie default. |
| TV trusted indexers | A separate Settings button opens the same kind of checkbox dialog, with its own independent selection. | LimeTorrents and 1337x are the requested initial selection for testing. This does not establish a permanent default for every installation. |

Movie selections must not silently become TV selections, or vice versa. The settings displayed and saved must be the selections actually consumed by their respective automatic acquisition paths. Selecting an indexer establishes source trust; it does not waive episode identity, torrent identity, availability, quality, coverage, or destination checks.

**UI recommendation:** Extend/refactor the existing `TrustedIndexerDialog` into a shared selector with an explicit scope, title, description, selected IDs, and save owner. Use it for the two Settings choices, retaining CP's existing dialog layout, checkboxes, Save, and Cancel behavior. Show each saved selection beside its button. Do not clone a new popup implementation for TV. The current release-watchlist and AI Control selections have separate responsibilities; their relationship to the new Movie selection must be settled before replacing any controls.

**Testing caveat:** A later read-only inspection found that all inspected Lucifer candidates from LimeTorrents and 1337x also carried `hash_invalid`, meaning the automatic path lacked a valid torrent identity at that stage. The worker chooses accepted candidates before the submission path can resolve their links. Merely trusting these sources therefore does not make those inspected candidates eligible. The implementation investigation must account for supported link resolution and validation before automatic selection, while preserving validation requirements. Lucifer's unresolved season-2 destination is an independent blocker.

### Remaining decisions and boundaries

- Whether the selected trusted sources also restrict automatic searches, and whether they affect manual searches.
- How the Movie selection relates to release-watchlist trust and the separate AI Control selection.
- Empty selections, unavailable/disabled indexers, initial setup on existing installations, and changes while tasks are running.
- Exact placement and copy, plus readiness and truthful task progress reporting, belong in the reviewed implementation plan.
- Do not reset an explicitly saved Movie choice to YTS merely because YTS is the initial default. Do not treat the TV test selection as authorization to change live configuration or start downloads.
- The required contract-change notice and approved implementation plan remain prerequisites for application changes.

## TV-CHANGE-04: New-release following versus downloading an existing series

**Status:** Five-hour Follow source-search retries are agreed and included in the authorized implementation handoff. The original discussion used six hours; that retry recommendation is superseded. No live task change is authorized.

**Existing written contract:** The completeness plan explicitly separates Future from Missing. Whole-series Future follows releases from task activation onward across later seasons, retries missing sources, and remains active until confirmed series completion and acquisition of eligible targets. It is unavailable for a series already marked Ended. Whole-series Missing refreshes metadata at Start, freezes the released missing regular-episode targets, retries until acquired or cancelled, and does not add later releases. Missing applies to ended shows as well as ongoing shows. Owned episodes are skipped; Specials require explicit selection. An existing backlog and future releases may be handled by two separate tasks.

**Separate agreed bulk behavior:** TV Library's immediate selected-show Download searches released missing episodes once, queues eligible sources, reports episodes without a source, and finishes. It does not retry or follow future episodes. Do not silently convert this action into a persistent task.

**Timing evidence:** The written Follow contract requires retries and bounded metadata refresh but does not specify a six-hour source-search interval. Current `services/tv_monitoring.py` refreshes Future metadata after 21,600 seconds (six hours); source-search failures are scheduled for retry after 3,600 seconds (one hour). These are different operations. Dante's stated six-hour source-search rule is not currently implemented. Release eligibility is based on episode air dates, not an authoritative broadcast timestamp.

**Recommendation for discussion:** Keep one acquisition/task owner, with clearly named user choices: **Follow new episodes** (Future) and **Download missing episodes** (Missing), plus whole-series or selected-season scope. For an ended show, Download missing episodes can fill the entire regular series and finish after its targets are verified/imported. For an ongoing show, it catches up the fixed backlog; Follow new episodes handles later releases. Recommend a first search when eligible and a six-hour retry after an unsuccessful source search for both persistent actions, with visible last search, next search, remaining episodes, and actionable blockers. This recommendation does not change the separately agreed one-shot bulk behavior.

**Current decision state:** Five-hour retries apply to persistent Follow Missing/Future source searches; lower multi-season downloads open manual review without a Follow task. A combined backlog-plus-future action and extended Future scope are deferred. Setup/validation blockers must be visible and do not waive validation. Ended-show capability exists in the written contract and targeting code, but successful full-series acquisition is not proven by this review and remains subject to the source and destination blockers recorded above.

### First-search timing discussion

**Verified 2026-10-08:** CP refreshes TV episodes from TMDB and stores `air_date`; its current release check compares that date with the computer's local date. It has no episode airing-hour scheduling in this path. IMDb's [documented release-date fields](https://help.imdb.com/article/contribution/titles/release-dates/GVUUDEPJNAW6G35P) are country, day, month, and year; these do not provide a reliable broadcast-hour feed. [TVmaze's episode guidelines](https://www.tvmaze.com/faq/15/episodes) describe airing times and timezone-aware timestamps where available, but no airtime for global web channels.

**Agreed handoff rule:** With CP's existing date-only information, start Future source searches at 00:00 on the listed air date in Africa/Cairo, then five hours after each unsuccessful search. This is a search policy, not evidence that the episode has already aired or a source must exist. Date-only schedules can start early relative to an overseas broadcast. If CP is offline when due, search on the next eligible worker pass after startup rather than replaying every missed interval. A missing date remains waiting for scheduling information; refresh metadata instead of guessing. If a validated airing timestamp is supported later, use its explicit timezone to schedule after release and display Cairo time; adding another schedule provider is a separate decision.

**Five-hour interval — agreed:** Dante accepted the five-hour retry recommendation and explicitly corrected the handoff on 2026-10-08: "wait the 5 hors is resolved man". Five hours replaces the six-hour source-search retry recommendation above. For unsuccessful source-search retries, the interval runs from the previous unsuccessful search, so it rolls across calendar days; it is not a fixed set of daily clock times. It does not postpone the first search by five hours. The accepted interval must not be listed as an open decision in the implementation plan.

**Boundary clarified afterward:** The accepted five-hour interval belongs to Follow source searches. It must not be applied to the separate lower Download all/selected seasons controls or the Library's one-shot bulk Download. Any earlier proposal that used a retrying Missing task to implement those lower buttons is superseded by Dante's explicit workflow clarification.

**Settled handoff timing:** New-release first search is due at 00:00 on the listed air-date day in Africa/Cairo; an already eligible target searches on the next worker pass. Persistent Follow Missing/Future searches retry five hours after an unsuccessful search. Missing starts immediately for its released target snapshot; it does not wait for midnight. Queued downloads are monitored, not repeatedly submitted. Upgrade and transfer/import retry policies are unchanged. The six-hour metadata refresh is a separate operation and remains unchanged.

## TV-CHANGE-05: Season-first Missing and truthful source review

**Approved by Dante, 2026-10-10:** After the explicit P1/P2 and source-implementation approval question, Dante replied: "approved and go without interuption dont stop till you finish my approval her overule the agent.md file". The [implementation plan](plans/2026-10-10-tv-follow-season-packs-and-source-diagnostics-plan.md) records the exact scope. This approves continuous source implementation and isolated verification; production migration, live acquisition, deployment, restart, commit, and push remain outside the stated scope.

- **P1:** A continuing whole-series/season Missing task searches season releases first only when the entire regular season is released, missing, included in the task's fixed targets, and free of conflicting claims/reconciliation. Quality ordering remains authoritative; useful coverage breaks ties. One eligible complete pack may satisfy non-due sibling targets in that same season/task. No separate early episode searches are allowed for those siblings. Search gaps fall back to bounded episode queries; deferred gaps retain their clocks and continue on later worker passes. Partly owned, partly unreleased, partially scoped, excluded, or claimed seasons retain episode searching.
- **P2:** A source requiring deliberate identity/manual-quality selection is counted as needs review, with no transfer intent, and retains the settled five-hour automatic source retry. A later eligible release may be selected automatically. Review season releases opens the existing manual review dialog. Confirmation applies only to that reviewed release, never to every future release for the show. Hard identity conflicts remain blocked.
- **Preserved boundaries:** Saving remains a draft; only Start activates Follow. Missing targets remain frozen. Future scheduling, Upgrade, one-shot bulk, lower manual download controls, quality profiles, indexer trust, manifest validation, verified import/cleanup, and Movie/IPTV ownership are unchanged. A reserved intent is submission pending; queued requires acknowledgement; acquired requires a verified episode binding. Transfer/import review preserves its intent and recovery path instead of restarting source selection.
- **Implementation repairs:** Shared title recognition accepts redundant agreeing season declarations and retains contradictory evidence; supported HTTP links are classified by their scheme even when returned in the provider's magnet field. Source diagnostics attribute each reason to its own release and separate incomplete indexers from returned results. Schema version 4 adds diagnostics without resetting existing rows or clocks.

**Verification boundary:** Implementation evidence is retained under `verification/tv-follow-season-packs/`. Disposable real-owner desktop tests prove pack selection, single-intent queueing, verified episode publication, cleanup and Versions display. These tests do not establish whether the screenshot's live torrent is currently usable or change the running Louie task.

## Decision log

| Date | Item | Decision or authorization | Scope |
| --- | --- | --- | --- |
| 2026-10-08 | This document | Dante requested a Markdown file for TV contracts so further rules can be discussed and added before an implementation plan. | Create and maintain this contract discussion file. No application implementation. |
| 2026-10-08 | TV-CHANGE-01 | Dante proposed a metadata-based tree with show name and start year. | Proposal recorded; detailed amendment remains pending. |
| 2026-10-08 | TV-BASE-02 | Dante confirmed that South Park's new folders were named `Season 27` and `Season 28` and that this behavior is acceptable. | Preserve the existing rule of continuing the established season-folder style. No new naming support, renaming, or implementation authorized. |
| 2026-10-08 | TV-CHANGE-02 | Dante requested review of Follow activation and the ability to download all seasons or several selected seasons together. | Requested outcome recorded; interaction, one-shot versus retry behavior, and detailed rules remain pending. |
| 2026-10-08 | TV-CHANGE-03 | Dante requested clearly selectable source options in Settings and a check of the remembered movie YTS default versus TV. | Current Settings behavior verified and desired direction recorded; actual TV sources/default and detailed behavior pending. |
| 2026-10-08 | TV-CHANGE-03 selections | Dante specified independent Movie and TV multi-select Settings popups, with YTS as the movie default and LimeTorrents plus 1337x initially selected for TV testing. | Record these choices in the contract. No application implementation, live settings changes, or downloads authorized. Remaining scope and lifecycle details stay open. |
| 2026-10-08 | TV-CHANGE-04 | Dante restated release-day searching with six-hour retries and asked whether the feature should also download ended shows. | Existing Future, retrying Missing, and one-shot bulk contracts compared with code. Recommendations and timing mismatch recorded; no implementation or task changes authorized. |
| 2026-10-08 | TV-CHANGE-04 retry interval | Dante accepted five-hour retries, requested an implementation plan/new-task handover, then explicitly confirmed "the 5 hors is resolved". | Five-hour unsuccessful-source retry interval is settled. Do not reopen it during planning or implementation. Live actions remain separately bounded. |
| 2026-10-08 | TV-CHANGE-02 workflow separation | Dante clarified that Download all refers to the lower controls underneath Follow, then confirmed the separation. | Lower all/selected-season downloads are not Follow tasks and have no persistent five-hour retries. Manual release review versus automatic one-shot selection still needs a choice. |
| 2026-10-08 | TV-CHANGE-02 review choice | Dante selected Open release review for the lower all/selected-season download buttons. | Preserve explicit torrent/release review and submission; no persistent task is created by these buttons. |
| 2026-10-08 | Bounded implementation handoff | Dante requested a saved implementation plan and a new task to start implementation using this file and agreed actions. | Source/test implementation and isolated desktop verification of the slice above. Deferred exceptions and live actions remain outside authorization. |
| 2026-10-10 | TV-CHANGE-05, P1/P2 | Dante explicitly approved season-first Missing planning, review reporting with continued five-hour retries, and the implementation plan; requested completion without routine interruptions. | Source/test/docs implementation and isolated desktop verification. Existing validation and scheduling boundaries preserved; live activation remains separate. |

## Adding further rules

Give each amendment a stable ID such as `TV-CHANGE-02`. Record the requested behavior, current rule and source, proposed rule, visible result, affected areas, reason, risks, alternatives, recommendation, unresolved decisions, and Dante's final decision. Add only rules actually discussed; do not treat suggestions as approved requirements.

## Source references

- [Project work and contract-change rules](../AGENTS.md).
- [Approved normal TV storage plan and execution record](plans/2026-10-05-tv-download-storage-cp-normal-behavior.md), especially its bounded exclusions and exact destination/lifecycle contracts.
- [TV Library completeness plan](plans/tv-library-completeness-maintenance-and-coverage-plan.md), especially the agreed Follow and download scopes, explicit Start, retries, completion, and one-shot bulk Download distinction.
- `services/tv_catalog_repository.py`: approved folder ownership and destination resolution.
- `services/tv_acquisition.py`: search review, submission, and completion behavior.
- `services/verified_import.py`: publication, filename preservation, collision checks, and recovery.
- `src/features/tv/TVAcquisitionReview.jsx`: destination display and Download button eligibility.
- `src/features/tv/TVWorkspace.jsx`: per-season direct download controls.
- `services/tv_monitoring.py`: saved drafts, explicit activation, scope selection, retries, and task completion.
- `src/features/settings/SettingsWorkspace.jsx`: Prowlarr and AI Control trusted-source controls and save payloads.
- `src/features/settings/TVSettings.jsx`: current TV capability and root controls.
- `src/features/settings/AcquisitionProfiles.jsx`: quality policy, separate from indexer selection.
- `app.py`: effective movie download-indexer selection, Prowlarr configuration, and TV service composition.

Later implementation plans must cite the approved entries from this file and identify any remaining open decisions. Only the bounded source slice in the implementation record above is implemented; this document does not claim live activation or implementation of deferred amendments.
