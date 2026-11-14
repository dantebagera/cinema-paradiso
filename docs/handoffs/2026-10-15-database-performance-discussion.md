# Database performance investigation and discussion handover

**Date:** 2026-10-15, Africa/Cairo.

**Authorization:** Dante explicitly requested a separate task with a proper handover, covering only database-related performance issues and discussion. Read-only investigation and discussion are authorized. No product implementation is authorized. This handover document is the only file created by the sending task for this request.

**Objective:** Establish whether CP's Movie, TV and IPTV database designs and query paths cause avoidable delays; distinguish architectural defects from query inefficiencies, contention and safe opportunities for reuse; discuss a durable, evidence-based correction with Dante before implementation.

**Do not start with “add caching.”** First determine which data is authoritative, whether filtering and display derive the same effective information, and where work or rules are duplicated. Audit the existing architecture before selecting an optimization. A structurally healthy SQLite file does not prove a sound application design.

## Strict boundaries for the receiving task

- Read root `AGENTS.md` and follow Dante's communication and permission rules. Explain findings in plain English and distinguish confirmed facts, hypotheses, historical evidence and recommendations.
- Begin with read-only investigation and discussion. Do not edit source, tests, plans, configuration or data; create scripts/artifacts; build; start/restart services; commit; push; package; or migrate without a new applicable request. The existing plans are proposals, not approval.
- Do not instantiate production store/service owners or import the Flask app merely to inspect them. Several constructors initialize schemas, migrate, configure journal mode, start workers or clean files. Read source first.
- Inspect active SQLite files through explicit read-only URI connections (`mode=ro`) and `PRAGMA query_only=ON`. Do not use `immutable=1` for a live WAL database: it can omit current WAL state. Do not set WAL/synchronous/checkpoint modes or run ANALYZE, VACUUM, REINDEX, repair or cleanup against live data.
- Keep diagnostics bounded. Start with schema, indexes, existing measurements and EXPLAIN QUERY PLAN; avoid long read transactions that pin WAL growth. An explicit read transaction used for coherent observations should be short. Production workers may continue writing independently; do not claim byte identity of all live files across the investigation.
- No UI work or investigation of rendering, CSS, image decoding/rasterization, wallpaper fetching, Home rails, scrolling, expansion geometry, mobile layout or client rerender optimizations. An API's database calls and server-side SQL/projection are in scope; browser work is not needed for this discussion.
- No provider requests, metadata refresh, live scan, download, playback, data backfill or acquisition action. Separate database time from any external wait visible in existing evidence; do not trigger external work to measure it.
- Preserve Movie, TV, IPTV and provider isolation. Do not infer that similar UI cards imply shared storage or merge databases because there are several files. Preserve Movie Follow startup/manual Scan and TV five-hour retry rules; investigate their database impact without changing them.
- No new task delegation or automatic messaging back to the sending chat is needed. This is a user-owned discussion task; report to Dante here.

## Read these sources in order

1. Root `AGENTS.md`, and `docs/plans/_template.md` if Dante later requests a plan.
2. `docs/sql-investigation/current-sql-architecture-audit.md`. Read the repair update before the historical baseline: its old absence-of-canonical-owner diagnosis does not describe the entire current system.
3. `docs/sql-investigation/catalog-read-performance-and-local-artwork-implementation-plan.md` and `catalog-read-performance-stage-report.md`. Separate dated historical performance/acceptance from current proof. The original full-library reader was already replaced in important paths; do not propose repairing it again without verifying today's caller.
4. `docs/plans/2026-10-14-cp-performance-findings.md`, specifically F6–F10 and the corrections table. UI/artwork sections are background only and out of scope here.
5. `docs/plans/2026-10-14-library-database-query-plan.md`. This Movie-only draft was saved before the subsequent architecture concern was fully articulated. It excludes TV/IPTV implementation and is not an exhaustive database audit. Do not execute it or mechanically apply its assumptions to the other stores.
6. `docs/tv-contracts.md`, current TV/store design and current IPTV provider/metadata design as needed. The broader `2026-10-14-cp-performance-plan.md` is background, not this task's work list.

Existing diagnostic owners include `tools/catalog_read_performance.py`, `tools/library_sql_shadow_compare.py` and `tools/catalog_parity_audit.py`. Read their side effects and isolation assumptions before considering execution; their existence is not permission to run them on production. Reuse appropriate existing tooling if later authorized instead of introducing a competing benchmark system.

## Baseline and ownership seeds — reverify, do not assume current

- Checkout: `C:\Users\dante\Desktop\cinema paradiso`; `master` at `be511f98846a67a182e5b371ad087938e9344362`; package version observed earlier `3.0.0-beta.2`.
- Immediately before this handover document: 80 tracked modified files and 388 untracked files. Existing source edits include Movie/API, TV/acquisition, curation and IPTV work. Preserve all of it. HEAD alone is not the running source baseline.
- Prior observation during the Movie plan: port 5000 PID 46012, Python312 `app.py`; served HTML matched Desktop `dist/index.html`, referencing `index-B51l7aON.js` and `index-DFMDe_8_.css`. This is a historical observation, not current process proof. Source, process working directory, loaded configuration, databases and served dist must be established separately.
- Desktop config names `C:\Users\dante\Desktop\cinema paradiso\data` as user-data root. Config alone does not prove which data root an existing process loaded.
- Old comparison checkout: `C:\Users\dante\Desktop\cinema paradiso - Copy`. Its configuration was found to point at main's data. Do not launch it as an isolated old system.

### Database file inventory observed while preparing the handover

These are file-existence/size observations, not proof that every file is active or a contributor to latency. Sizes exclude separate WAL/SHM files. Large size is not evidence of corruption or bloat.

| Domain | Candidate file / location | Observed main-file bytes | Ownership to trace |
| --- | --- | ---: | --- |
| Owned Movies | `C:\Users\dante\AppData\Local\Cinema Paradiso\Catalog\catalog-read-cb30c1d963c88463.sqlite` | 171737088 | `catalog_repository.py`, `catalog_store.py`, `canonical_catalog.py`, relevant `app.py` routes |
| Native TV | `data\tv-catalog.sqlite` under the checkout | 27738112 | `tv_services.py`, `tv_routes.py`, `tv_catalog_repository.py`, `tv_catalog_store.py`, `tv_read_model.py` |
| IPTV provider A raw catalog | `data\iptv\providers\2d44d898e1284947b8eb1a64df18af28\iptv.sqlite` | 72822784 | Provider manager, `iptv_service.py`, `iptv_store.py` |
| IPTV provider A enriched movies | Same provider directory, `movies.sqlite` | 921571328 | `iptv_movie_service.py`, `iptv_movie_store.py` |
| IPTV provider B raw catalog | `data\iptv\providers\55219f5721c44255aeff300451a404b4\iptv.sqlite` | 32632832 | Same raw owners; independent provider identity |
| IPTV provider B enriched movies | Same provider directory, `movies.sqlite` | 60026880 | Same enriched owners; independent provider identity |
| Acquisition dependency | `data\acquisition.sqlite` | 276709376 | `acquisition_store.py`, relevant Movie/TV services and database work by background workers |
| Awards dependency | `data\awards\awards.sqlite` | 3289088 | Locate actual readers/writers before assigning relevance |

Other `.sqlite` files exist in AppData and backup/rehearsal directories. Do not treat every old, restored or backup file as a live database. Verify active provider selection through `iptv_provider_manager.py` and the provider registry without printing credentials, tokens, server URLs or private provider configuration. Raw IPTV Live/Series data and enriched IPTV Movies data are separate responsibilities; native TV is another domain entirely.

Source-confirmed composition: `TVServices.__call__` constructs the TV repository at `<effective-data-root>\tv-catalog.sqlite`. `IPTVService` takes a provider root and owns its `iptv.sqlite`; `IPTVMovieService` exposes `movies.sqlite` in that provider root. Provider manager uses `iptv\providers` and `providers.json`. Effective runtime roots and enabled/active providers still need verification.

## What the Movie investigation actually established

1. `CatalogStore.library_page` repeatedly runs an exact count and ordered page-key query through `_library_effective_cte`, then projects selected page entries. Facets/stats already have a generation-aware summary cache. Both advanced and legacy card routes reach this owner; full-selection and collection/keyword callers share relevant logic.
2. Earlier unprofiled read-only file-owner calls were about 186–193 ms warm, approximately 483 ms first call with initial summary work. Count alone was about 77–85 ms and page selection 104–114 ms in distinct probes. Do not add unrelated-run times or claim all of that latency is recoverable.
3. One real page revisit made zero image requests yet waited roughly 471 ms for page data. The entire route's remaining work was not fully decomposed. It is wrong to equate that whole response time with SQL execution.
4. Earlier bounded quick check returned `ok`; freelist was zero; existing indexes were present. A disposable RAM-copy ANALYZE experiment and one snapshot covering index gave modest gains, not a selected production fix. No live maintenance/schema change was made.
5. The old UI bundle tested against the same current responses/backend did not show a large consistent UI-only pagination gap. Relevant old/current backend functions were identical. Current database cost is real; its role in the historical new-UI regression remains unproven.
6. Existing low-SQL-statement-count tests do not establish bounded rows examined, bounded sorting work or inexpensive callbacks. Existing historical parity passes are valuable but not proof of every current edge case.

No comparable deep performance audit of current native TV or IPTV databases has been completed in this chat. Do not assign Movie findings or proposed remedies to them without evidence.

## Architecture concern raised after saving the Movie-only plan

Current source implements effective-provider/override selection both in `CatalogStore._library_effective_cte` and `CanonicalCatalog.project_paths`. The former supplies filtering/sorting data; the latter constructs displayed card metadata. This duplication is confirmed. Its complete semantic equivalence is not established.

One concrete difference: SQL separately selects title/year from the latest matching metadata override row, then falls back when the selected field is empty. Canonical projection iterates matching overrides in order and applies each nonempty field, potentially retaining an older nonempty value. Provider selection also needs comparison: canonical projection restricts selected TMDB snapshots by canonical TMDB identity, while the Library CTE's shown selection uses movie/provider/path preferences. Reachability and intended exceptions must be checked against writer invariants and existing contracts.

These are source-level discrepancies/risks, not proof of a currently affected live movie. Do not “fix” them by choosing whichever branch is fastest or whichever old test passes. Determine the agreed authority and expected adverse-case result first. Do not freeze a wrong response into a cache or a stored browsing representation.

Historical architecture audit: the old system lacked a clear relational movie owner; the documented schema-v6 repair introduced one. Today's current canonical schema/contract versions must be rechecked. Distinguish a repaired historical defect, remaining duplicate interpretation and proven present-day performance costs.

## Questions the receiving task must answer

1. **Inventory and authority:** Which databases are active, who owns each, and which actual request/background paths use them? Include auxiliary stores only when a dependency or resource-contention path is demonstrated.
2. **Fundamental design:** Are identity, provider choice, overrides, publication/visibility and displayed values interpreted once or independently in multiple paths? Where does intended ownership differ from implementation? Verify the Movie discrepancy before selecting caching.
3. **Read cost:** Which reads perform whole-collection reconstruction, repeated nested queries, per-row Python callbacks, JSON extraction/decoding, count/sort, or expensive filtering after retrieval? What is justified by the query versus avoidable? Inspect default and selective queries independently.
4. **Writes and contention:** Do scans, metadata enrichment, progress/operational polling or acquisition bookkeeping cause avoidable database writes, long transactions, contention, WAL/checkpoint pressure or expensive work while holding application locks? Explain effects without changing schedules or live workloads.
5. **Read consistency and freshness:** Do counts, selected IDs, projected metadata and reported generation describe the same database version? Audit media/curation/catalog/asset and provider-specific generations and all relevant writers before recommending reuse.
6. **Database condition:** Check schema/version/index/statistics health and evidence for fragmentation/free pages or integrity problems separately from query design. Bounded checks only; no cleanup recommendation based solely on file size.
7. **Domain-specific cases:** Native TV series/season/episode aggregation and progress; IPTV raw Live/Series browse/search/favorites; IPTV enriched Movies filters/classification/provider isolation. Locate actual owners such as `TVReadModel.library`, repository episode reads, `IPTVStore.list_items/list_entries` and `IPTVMovieStore.list_movies`, rather than assuming Movie Library architecture applies.
8. **Appropriate repair:** For each proven bottleneck, compare correcting existing ownership/query structure, targeted indexes, derived read representations and bounded result reuse. Explain tradeoffs, migration risk and fresh-data correctness. Use established techniques and avoid a second authority.

This list defines the investigation coverage, not a claim that every issue exists. If a store/path is healthy, say so with supporting evidence. If read-only evidence cannot establish runtime causality, state the limitation and propose a separately scoped isolated measurement; do not manufacture certainty.

## Expected discussion deliverable

Give Dante a database-only assessment, ordered by user impact and confidence, with:

- A verified active-store/owner/dependency map and explicitly uninspected areas.
- For each finding: user-visible database-related delay; file/function/query; evidence and method; whether it is an architectural defect, query inefficiency, contention issue or hypothesis; affected domains; and existing contracts at risk.
- An explanation of what was fundamentally wrong, what prior work repaired, and what remains wrong today. Do not generalize “the database is healthy” from a quick check or “the architecture is broken” from one slow query.
- A recommended durable direction per owner, alternatives, expected scope and measurement needed to substantiate benefits. No promised percentage or universal millisecond target.
- A clear statement of what caching would solve and what it would merely conceal. Preserve exact totals/order, post-edit freshness and failure truthfulness.
- Open product/contract decisions surfaced separately using AGENTS.md's required contract-change notice when applicable.

Discuss findings with Dante before requesting any implementation scope. If a new plan is requested, use the CP template and separate architecture correctness from performance optimization and rollout. No UI recommendations or unrelated fixes belong in this task.

## Transfer state

The sending task has performed no product implementation, schema/index change, maintenance, production restart or new database benchmark for this handover. Existing plans and source are unchanged. This handover supersedes neither prior contracts nor their approval boundaries. All earlier measurements are leads to reverify, not acceptance evidence for a future change.
