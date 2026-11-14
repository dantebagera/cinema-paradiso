# Movie search/retry controlled activation plan

**Status:** Activated and focused verification passed. Execution approved by Dante on 2026-10-24: “the whole current checkout. preserve all existing changes, prepare and verify the backup and rollback first, then activate it.” This supersedes the planning-only gates below. Whole current source, normal startup writes, consistent backup, isolated restore rehearsal, one staged build/focused desktop rehearsal if needed, and controlled activation are approved. No dependency installation, manual repair/scan/download, commit or release is included.

**Execution amendment:** CP was absent at the initial execution check, but an external `run.bat` invocation subsequently started launcher 15240 / backend 44576 and embedded qBittorrent 54412 on October 24 at 18:32. Its rebuilt index already matches corrected candidate SHA256 695e94fc071215559545e280c896f3eddd17016c23b6d64dadce22f1651146fa; config is unchanged. This pass did not issue that start or build. Exact pre-existing loaded-code rollback is unavailable. The recovery target is the exact current checkout, bundle, configuration and stopped active state captured after the approved graceful shutdown, not an invented earlier live-code snapshot. The existing lifecycle shutdown was requested and completed successfully, including CP-owned embedded qBittorrent (two active downloads reported). Media/payload bytes stay in place. New verification is a separate finite activation allowance: one staged build, at most four focused desktop tests in disposable OS-temp state, then one start and at most five active minutes of live checks. Historical backup trees, dependencies, release archives and actual media payloads are excluded explicitly in the recovery inventory; they remain untouched.

**Goal:** Put the approved Movie search/retry implementation into use only after the complete activation unit, recovery set and normal startup side effects have been explicitly accepted.

**Architecture:** Keep the existing Desktop checkout and configured data owners. Promote a complete hash-pinned frontend bundle, not a single hashed chunk. Use the existing lifecycle owner for an orderly stop, take a stopped-writer-consistent recovery set, then start the pinned backend once without dependency installation or an automatic rebuild.

**Spec:** [Implementation and contracts](2026-10-23-movie-library-search-and-retry-performance.md); [isolated verification](../verification/movie-search-retry/README.md); [bounded final evidence](../verification/movie-search-retry/bounded-final.json). This document follows `docs/plans/_template.md`. Implementation, if later approved, stays inline using the executing-plans workflow; no new task, commit, release or worktree is implied.

## Historical planning findings and decisions (superseded by execution amendment)

- **What happens now:** Source and the temporary corrected bundle have isolated evidence for all seven additional functional checks, but the original live process and old production bundle remain in use. A Python-only restart would leave the frontend old; `run.bat` would install dependencies, rebuild the entire frontend, force-stop the backend and start normal background owners.
- **What Dante wants:** A reviewable activation with preservation of existing behavior, a reliable recovery option and bounded live checks. No live action has been approved in this planning turn.
- **Confirmed:** The six task product files still match final isolated source hashes. Production index is unchanged, and the initial listener matched the prior observation; the final runtime changed as recorded below. The tested candidate is a complete bundle with differences beyond the Library chunk. Normal startup resumes persisted work and can write production state.
- **Final runtime observation:** During this read-only planning pass the listener disappeared: port 5000 is clear, PID 56296 and launcher PID 9800 no longer exist, and no `python.exe app.py` process was found. This pass issued no process-control or live HTTP/API command. The cause is unknown. The earlier PID/start facts below are the initial observation, not the current state. **Do not start CP merely to restore availability:** a start would load the changed backend and is an activation action requiring its own approval.
- **Unknown:** There is no verified complete source manifest for code already loaded in the live Python process. Current dirty source is not automatically the live source. The October 14 integration recovery directory is documented, but it has not been established as a matching rollback for the process started on October 23. Exact backup byte cost has not been measured by walking production data. No production SQLite database was opened in this preflight.
- **Decision required — activation unit:** Does Dante want the **entire pinned current candidate** (including other existing working-tree changes and the complete candidate bundle), or a **strict fix-only candidate** reconstructed against a verified live baseline? Do not infer the first from approval of this Movie fix. A strict fix-only candidate cannot currently be certified from available source evidence.
- **Decision required — recovery:** Identify and verify a runnable matching fallback, or explicitly review a separately reconstructed pre-fix fallback and its differences before approval to stop live CP. Copying current on-disk source alone is not proof of an exact old-runtime rollback.
- **Startup authorization:** Any eventual normal activation must explicitly allow existing pending-job recovery, observers, Movie reconciliation, TV startup scan/monitor and other ordinary startup writes. A promise to restart normal CP while keeping production data unchanged would be false. No new startup-disable flag or policy change is proposed.
- **Recommendation:** Hold live activation at these gates. First choose the activation unit and pin a verified fallback; then approve the concrete backup/stop/promotion/start/check scope below. Do not use `run.bat` or swap a single chunk as a shortcut.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior | Proposed activation behavior | Contract change? | Decision |
| --- | --- | --- | --- | --- |
| Movie search/selection, implementation plan | Same membership, order, count, fields and canonical authority; newer search intent wins | Serve the corrected complete bundle with the pinned backend | No | Source fix approved; live activation pending |
| Publication and durable retry owner | Existing readiness gates, attempt limits, due order and admission FIFO; operational writes do not fabricate media generations | Normal coordinator recovery, without clearing flags or rearming failures by hand | No | Startup production writes need explicit activation approval |
| Native TV/IPTV/acquisition/player boundaries | Preserve their existing owners and behavior | No new migration, provider reconfiguration, native-player build or task-specific repair | No intended change | Other current source changes are not silently included in Movie-only approval |
| Lifecycle and rollback | Existing shutdown checkpoint protects active work | Graceful owned shutdown; no force-stop fallback | No | Stop of CP-owned playback/embedded qBittorrent requires inclusion in the activation decision |

No contract weakening is proposed. If activation preparation requires changing a startup, identity, publication, acquisition or rollback policy, stop that part and use the project's separate contract-change notice. Do not revise acceptance assertions to accept changed behavior.

## Current design and ownership

Evidence: [preflight manifest](../verification/movie-search-retry/activation-2026-10-24/preflight.json). It contains names/hashes and sanitized owner paths, not credentials. Capture time is recorded in UTC with the client date/timezone separately.

| Owner | Observed value / responsibility |
| --- | --- |
| Checkout | `C:\Users\dante\Desktop\cinema paradiso`, `master`, HEAD `be511f98846a67a182e5b371ad087938e9344362` |
| Dirty state before writing this plan | 114 tracked dirty entries and 597 individual untracked files; 85 dirty runtime input files among 243 fingerprinted runtime inputs. These are comparisons to Git HEAD, not proof of differences from loaded live code. |
| Six task product files | `app.py`, `services/catalog_store.py`, `services/catalog_repository.py`, `services/library_ingestion.py`, `src/features/library/LibraryWorkspace.jsx`, `src/features/library/librarySearchRequests.js`; no hash drift from bounded final evidence |
| Initial live listener | `127.0.0.1:5000`, Python PID 56296; venv launcher PID 9800; actual executable `C:\Program Files\Python312\python.exe`, command `app.py`; process creation recorded as October 23 18:55:02 +03:00 |
| Final runtime state | Port 5000 has no listener; those two PIDs are absent. No stop/start was issued in this pass; cause unknown. |
| Production frontend | Checkout `dist`; index SHA256 `5670d875c3b70b760e7e785637905872e374bed4751e830b6b0c181727362614`; 35 files |
| Tested candidate frontend | `C:\Users\dante\AppData\Local\Temp\cp-search-retry-1792774509070\dist-corrective`; index SHA256 `695e94fc071215559545e280c896f3eddd17016c23b6d64dadce22f1651146fa`; 35 files; 15 same-path payloads match production, 20 do not |
| Bundle scope examples | Library, Home, Discover, IPTV and Lists module filenames differ. Vendor React is identical. A changed hash can reflect imports as well as behavior; this does not prove a new product change in every different file. |
| Configured data root | `C:\Users\dante\Desktop\cinema paradiso\data`; on-disk configuration, not a newly queried live profile |
| Movie SQL | `C:\Users\dante\AppData\Local\Cinema Paradiso\Catalog\catalog-read-cb30c1d963c88463.sqlite`, file listing about 172 MB |
| Other primary SQL | Data-root `acquisition.sqlite` (about 435 MB), `tv-catalog.sqlite` (about 28 MB); provider-local IPTV state below `data\iptv` |
| Other configured state | `config.json`; `cache`; `data\app_metadata`, `awards`, `power`, `qbittorrent`, `runtime`; lists/collections/followed-release JSON; LocalAppData `Cinema Paradiso\Metadata` assets |
| Media / downloads | Configured Movie root `E:\Movies`, embedded qBittorrent mode. Media and torrent payloads are not a database backup and are not to be moved, scanned, downloaded or deleted by this plan. |
| Capacity sample | C: reported 326,728,597,504 free bytes. This is a single planning sample, not a reservation, backup-size measurement or hardware diagnosis. |

The current source's `app.py::_start_background_services()` starts retry recovery, reconciliation, awards refresh, the filesystem observer, offline catch-up, the qBittorrent import monitor, TV library scan, and the TV monitor when enabled. `services/frontend_routes.py` uses production `dist` outside test mode. `run.bat` installs Python requirements, conditionally installs npm packages, rebuilds `dist`, and invokes `tools/stop_stale_backend.ps1`, whose stop is forced. None of those launcher actions was run here.

## Exact behavior contract

### Frontend

Use the existing desktop Library layout/components and the exact tested bundle. No visual redesign or mobile work. The request scheduler, Movie/File return navigation, errors, loading state, selection and paging retain the verified behavior. Promote all 35 candidate files together only if that complete candidate is the approved activation unit. Do not replace just `LibraryWorkspace-*.js`; HTML and module dependencies must stay paired. Preserve production `dist` until a successful stop and verified recovery set exist. A new build requires a new explicit allowance; it is not needed for a byte-identical promotion of the preserved candidate.

### Backend and production state

Keep the pinned existing owners and configured roots. No identity edits, manual Rescan, retry-ledger initialization/backfill, database repair, publication flag clearing or forced acknowledgment. Existing pre-sequence ledgers have a deterministic legacy tie fallback until updated/retired; their lost historical admission order cannot be reconstructed.

The approved fixed source will be loaded only by the later new process. Normal startup can reserve attempts, update journals/SQL/assets, resume imports and trigger existing TV work. These are real writes even without clicking a repair button. An old source rollback can restore the old repeated-retry defect; preserve ledger/error evidence and do not erase it to make a rollback appear clean.

## Original gated sequence (execution amendment and completion record govern)

### 1. Pin scope and a runnable fallback before downtime

- [ ] Record Dante's exact activation-unit and startup-write decision here. No mutable moving target: recheck the six verified task hashes, all approved runtime input hashes, config hash, candidate/production bundle hashes, PID/command and owner paths against the preflight manifest. Any drift stops preparation for review; do not overwrite concurrent chats' work.
- [ ] Resolve the fallback source provenance. Search/reconcile only named source snapshots and manifests; a historical Git tag, current source copy, or October 14 archive is not automatically a matching live fallback. Do not reset or check out over the dirty Desktop tree. If no exact fallback exists, present the specific alternative and its behavioral risk for a separate decision.
- [ ] Propose a fresh finite allowance before any new fallback rehearsal or test. The previous 600-second/1-GiB test allowance is closed and may not be reused. Do not run a new broad suite or build under this planning approval.
- [ ] After approval of staging, copy the exact candidate bundle, approved source inputs, dependency lockfiles/version facts and chosen fallback into `C:\Users\dante\Desktop\CP-Recovery\movie-search-retry-2026-10-24-<UTC-id>`. Generate a SHA256/length manifest and validate copies. Keep credentials/data local; do not commit or publish the recovery set. Do not reinstall dependencies or rebuild the native player.

### 2. Approve the concrete activation window

- [ ] Present the final immutable candidate/fallback IDs, backup inventory and measured space/time estimate, permitted stop/start actions, startup writes and verification budget. Obtain explicit live activation approval. Until then leave CP, qBittorrent, production data/config/cache/assets and `dist` untouched.
- [ ] Proposed window: one graceful shutdown/checkpoint (60 seconds maximum), one start (30 seconds to bind), then at most five active minutes of observation and three named Library search reads. Backup time/bytes must be estimated from the selected active state and approved separately; do not invent a downtime estimate before measuring it. No automatic retry or extension after a failed checkpoint/backup/start/check.
- [ ] If included in that approval, capture a baseline of one agreed existing Library query/page while the old process is still running (40 cards: exact IDs/order/count/page and media generation). This is not authorized now. Preserve that response for the later comparison; do not start the stop step until the capture finishes or is explicitly omitted.
  - The final observation above means the old process is currently unavailable for this capture. Do not launch current changed source to manufacture an "old runtime" baseline. Record the unavailable baseline or use a separately verified archived source/data pair under an explicitly approved isolated allowance.

### 3. Stop writers and take the recovery set

- [ ] Reconfirm exact process ownership. Only after the approved maintenance window starts, use the existing lifecycle request `POST /api/power/actions` with `{"action":"cp","after_download":false,"close_qbittorrent":true}` **if closing the verified CP-owned embedded client and playback is explicitly included in approval**. This performs the existing checkpoint; it is not an ordinary read. A pending power plan or unsupported live route blocks this step; do not cancel plans or fall back to force-killing processes silently. Use `cp`, not `restart`, so the launcher does not auto-restart before backup/promotion.
- [ ] Wait for the actual backend/launcher and approved embedded client to stop and port 5000 to clear. Confirm no other owners hold the selected databases/journals. Windows Restart Manager resource enumeration can identify open owners; any unrelated/unknown owner is a stop condition, not permission to kill it. A single free HTTP port does not prove every writer is stopped.
  - If CP is still absent at execution time, omit its stop request; independently verify remaining embedded-client/other writer ownership. The already-clear port does not authorize promotion, backup or startup by itself.
- [ ] Snapshot the approved source/fallback and complete production bundle; `config.json`; all active state below configured `data`; the exact external Movie SQLite database and any WAL/SHM companions; LocalAppData metadata assets; configured cache; and the verified embedded qBittorrent recovery/profile root if outside `data`. Determine that client's actual root from its owner before approval, not an invented default. Existing historical backup trees can remain in place and be excluded only when enumerated explicitly; do not delete them. Media/payload roots are excluded and must remain untouched.
- [ ] Copy raw SQLite database plus existing journal companions only while all relevant writers are stopped. Hash/length-verify every copy. Validate **the copied databases** using SQLite `PRAGMA quick_check`, not by opening/checkpointing the originals. Do not copy only `.sqlite` while ignoring a WAL. Validate source/config/journal recovery files and manifests. Any missing/corrupt file or insufficient space blocks promotion; retain evidence and restore service using the approved fallback rather than improvising.

### 4. Promote one complete bundle and start one owner

- [ ] With verified backups and explicit approval, replace `dist` with the byte-identical staged candidate as a complete directory. Resolve every move target absolutely and confirm it is the intended checkout/recovery path. Retain the old bundle outside the served directory; do not delete it or merge old/new asset sets. No source checkout/reset, dependency update or data migration.
- [ ] Launch the approved pinned source with `.venv\Scripts\python.exe app.py`, the checkout as working directory, hidden window and dedicated activation stdout/stderr logs. Use a child-only environment that has no test-root/test-dist/portable-data overrides and explicitly selects port 5000 with the existing configured roots. Do not invoke `run.bat`, `pip`, npm or the broad stale-backend stopper. Do not launch the UI window helper unless explicitly included.
- [ ] Within 30 seconds identify the new launcher and actual listener PID, command and startup log. Verify the resolved data/config/catalogue owner and served index hash against the approved set. Abort on a second owner, wrong root, lease/schema/provider error, unexpected migration or missing bundle. Do not claim activation solely because an HTTP request returned 200.

### 5. Bounded live acceptance

- [ ] After startup compare the baseline query from step 2 at the recorded generation where possible; if normal recovery changed generation, explain changes from committed job evidence rather than calling different counts equivalent or running a repeated benchmark. If the baseline was explicitly omitted, report that limitation instead of claiming production parity.
- [ ] Proposed named read set: first page for `christmas`, broad `m`, and a unique no-match string; once each, no catalogue growth matrix or full production pagination sweep. Verify the ordinary response contract and absence of stale results; no universal production latency threshold is inferred from the synthetic 452 ms result.
- [ ] One desktop Library visit: type a bounded query, check result/loading/error state and Movie → File → Movie return navigation; verify the actual served candidate chunk. No mobile work, manual Rescan, Force scan, metadata lookup, playback test, download, deletion or import trigger.
- [ ] Observe existing catalogue notifications passively for the remainder of the five-minute window. If a naturally completing job produces an event, verify that card/ownership change without editing its journal. Do not manufacture a completion for proof. Do not open Home solely to force Following verification: existing Home startup can invoke `/api/user/followed-releases/check`, and historical local logs contain multi-minute checks. `/api/user/followed-releases/reconcile-owned` also writes Following state and needs explicit inclusion if used; it is not a read-only shortcut. If no natural completion occurs, report live refresh unobserved, with isolated end-to-end evidence retained.
- [ ] Stop on unexpected identity/publication changes, retry renewal, duplicate workers, wrong membership/order/count without explained committed changes, errors or unapproved writer activity. Record exact owner/generation/evidence; do not begin ad hoc repairs or prolong the window.

## Acceptance matrix

| Scenario | Exact expected result / evidence | Gate |
| --- | --- | --- |
| Source or bundle drift | Hash mismatch blocks staging/activation; no dirty work is discarded | Preflight |
| Scope broader than Movie fix | Entire candidate and its known limitations explicitly accepted, or fix-only baseline reconstruction completed | Dante's decision |
| Recovery source uncertain | No downtime/promotion until a runnable fallback and its provenance/limits are accepted | Recovery readiness |
| Active writer/checkpoint failure | No raw inconsistent backup or force-stop fallback; stop and report | Offline backup |
| Production bundle promotion | All 35 approved payloads match; old bundle retained; no mixed chunks | Promotion |
| New runtime | Exactly one intended listener using the correct configured owners; no test data or accidental new profile | Startup |
| Movie search/navigation | Exact scoped IDs/order/count and settled loading; no stale response overwrites latest intent | Bounded desktop/API |
| Native TV/IPTV/acquisition/player | No manual action, build, migration or reconfiguration; existing startup side effects occur only if explicitly approved | Scope + logs |
| Missing/empty/error | Agreed empty/error behavior persists; no guessed identity or false publication | Scoped query + isolated evidence |
| Natural completion during window | Existing commit/event/ack/Library/Following contract observed; otherwise live refresh remains unobserved | Passive observation |
| Regression before external media effects | Stop new writers and use the verified complete fallback/data/bundle set, retaining failed state evidence | Rollback |
| Background work already moved media/payloads | Preserve both states and journals; no blind restore of old SQL/jobs over changed physical files | Stop for recovery decision |

## Verification and rollback

- **Existing evidence:** 451-test owner batch before the bounded FIFO correction; 46 distinct Python methods with successful additional runs; two larger compiled desktop checks; nine actual crash boundaries; final dispatch/queue 15/15 and affected storage/canonical/rollback 12/12. The full 451 batch was not rerun after the bounded fix. Historical missing broader baseline, old diagnostic writes and CPU scheduling equivalence remain unavailable.
- **This planning turn:** No tests, build, live HTTP/API request, production SQLite open, restart, backup or promotion. Only file/config/log/source reads, process/listener facts, hashes, one disk-space sample and documentation were performed. Candidate bundle comparison and source inventory are in the preflight manifest.
- **Rollback triggers:** Wrong profile/source/bundle/lease; failed startup; unexplained result/identity/publication changes; renewed exhausted retries or duplicate execution; newly exposed cross-domain regression. Stop the new runtime through its verified lifecycle owner. Preserve its post-failure data/logs before any restore.
- **Rollback execution:** Use only the approved verified source fallback and matched bundle/dependencies. Restore the stopped consistent data/config/SQL/assets/journals as one approved recovery set **only when physical media/payload state has not diverged**. Never reset Git, delete unrelated dirty files, erase the new retry ledger, or restore an old job journal over media moved after activation. If physical effects occurred, retain both states and get a specific recovery decision; there is no honest automatic database-only rollback then.
- **Reporting:** Separate staged, isolated-qualified, activated and live-observed results. Record new PID, exact source/bundle/recovery IDs, configured owners, bounded query outputs, existing startup writes, elapsed time and any unobserved refresh. Neither an old test result nor activation approval is permission for a scan, download, cleanup, repair, commit, push, package or release.

## Current disposition

Completed under Dante's whole-checkout authorization. The external restart, subsequent graceful checkpoint, verified 6.28 GB snapshot, complete restore rehearsal with 48 SQLite checks, fresh byte-identical staged build, four focused desktop tests, one controlled startup, three named live API reads and actual rendered desktop navigation are recorded in [activation evidence](../verification/movie-search-retry/activation-2026-10-24/README.md). Backend PID 55244 owns port 5000 and its writer lease; embedded qBittorrent PID 42656 owns port 8686; the installed CP window was reopened. Source and existing dirty work were preserved. The complete production bundle already matched all staged bytes, so no replacement was necessary. No contract change was introduced.

Recovery target is the exact captured stopped current state, not the earlier unavailable loaded runtime. All restored bytes and copied databases passed; no real-media application execution was performed during recovery rehearsal. No natural completion occurred during passive observation, and no exhaustive regression or production speedup claim is made. Ordinary startup can resume existing work and change physical media/payload state, so a later data rollback must account for that state rather than blindly replacing SQL/jobs. No manual repair/scan/download/deletion, dependency change, commit, push, package or release was performed.
