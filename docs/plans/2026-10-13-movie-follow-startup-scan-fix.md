# Movie Follow startup and Scan repair

**Status:** Implemented and verified in isolation on 2026-10-13; not live activated. Dante confirmed that Movie Follow checks pending films at every CP startup and every Scan click, then said: "ok now fix the follow movies". TV Follow and Download is a separate feature; its five-hour Missing/Future retries remain unchanged.

## Problem and decision

- **What happens now:** Home triggers a startup scan and manual Scan, but `MovieAcquisition.check_followed` skips pending films using saved retry dates and a calendar release-date gate. The retry delay grows from one to seven days. The shared movie matcher rejects title/year differences before verifying YTS IMDb identity.
- **Evidence:** Read-only production inspection found qualifying YTS releases with matching IMDb identities for Practical Magic 2, Northspur, The Uprising/The Rage, Hope/Hopeu and Sheep in the Box/Hako no naka no hitsuji. All five remained watching with future retry dates. A read-only replay skipped all five; four failed the title/year prefilter.
- **What Dante wants:** Fresh searches of pending followed movies at startup and manual Scan, no movie retry cooldown, correct verified identity matching, availability alerts without automatic movie downloads.
- **Scope:** Existing Movie search/Follow owners, regression tests, a disposable desktop fixture and verification records. No TV changes, live scans/catalog/config changes, production build replacement, restart, commit, push or downloads.
- **Open decisions:** None for this bounded repair. Existing source trust, quality restrictions and ownership rules remain.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior | Affected areas | Implementation | Changes agreed contract? | Decision |
| --- | --- | --- | --- | --- | --- |
| Dante's Movie Follow clarification in this chat | Startup and Scan freshly check pending movies; no cooldown | Home and Follow API | Remove retry and calendar gates from pending source searches | No; restores confirmed rule | Approved 2026-10-13 |
| Correct movie identity; existing YTS tests | Exact verified IMDb identifies the film; wrong IMDb must be rejected | Movie search, RSS and Follow | Verified YTS identity decides matching before descriptive title/year fallback | No; corrects matching | Approved fix scope |
| Existing quality/trust/alert/ownership behavior | Trusted qualifying HD source; no camera releases; alerts only; owned films leave Follow | Movie Follow, Home, movie search callers | Preserve existing owners and guards | No | Preserve |
| TV contract | Persistent Missing/Future retries after 18000 seconds, explicit Start and episode lifecycle | TV | No implementation changes | No | Preserve |

The existing test that accepts skipping recently checked movies conflicts with Dante's confirmed Movie contract. Update that assertion to require a fresh search. A previously retained compatibility schedule in the acquisition adoption plan is historical implementation evidence, not authority over Dante's correction.

## Current design and ownership

Baseline: Desktop `master`, `be511f98846a67a182e5b371ad087938e9344362`, ahead nine commits, with fourteen previously modified tracked files and existing untracked TV/Upcoming work. Preserve those changes. Source snapshots and hashes are recorded in an OS-temporary verification root before edits. Running Python PID 32648 serves Desktop port 5000 and `index-BjHCB4GJ.js`; production data is Desktop `data`, with the authoritative catalog in LocalAppData `catalog-read-cb30c1d963c88463.sqlite`. These are investigation observations, not rollout proof.

| Responsibility | Owner | Caller / behavior to preserve | Obsolete path |
| --- | --- | --- | --- |
| Startup/manual UI triggers, alerts, scan serialization | `src/App.jsx`, `HomeWorkspace.jsx` | Existing controls and desktop layout; do not add timer or auto-download | None |
| Pending scans and RSS/Prowlarr orchestration | `services/movie_acquisition.py` | Owned removal, verified identity, parallel bounded source queries, available results | Movie due-date eligibility |
| Identity and source policies | `app.py` existing helpers | YTS page IMDb authority; other providers and unverified manual title/year matching | Title/year rejection before verified identity |
| Follow persistence and race protection | `services/curation_store.py`, catalog | Existing followed-at snapshot guard, timestamps and response shape | Scheduling significance of legacy retry fields |

## Exact behavior contract

### Frontend

Reuse Home's ReleasePanel, FollowedReleasesDrawer and App's existing startup/Scan callback. No frontend source or layout change. Verify compiled desktop startup, Scan, repeated scans/reload and visible Available/Watching states against real isolated routes. Following does not enqueue a download.

### Backend

- `POST /api/user/followed-releases/check` and its existing startup caller search all pending, unowned, identity-resolved films each invocation. A metadata release date does not prove or disprove a torrent's availability; retain metadata for display/priority, not a hard source-search gate.
- Continue skipping already verified available entries except when their YTS page proves an identity mismatch. Missing IMDb remains unverified and cannot become automatically Available.
- YTS movie-page IMDb confirmation takes precedence over title/year differences. A confirmed different IMDb rejects the candidate. If identity cannot be read, normal manual movie search retains existing title/year fallback; Follow still requires verification. Non-YTS matching remains unchanged.
- Preserve approved HD source restrictions, trusted indexers, bounded query deadlines/parallelism, RSS batching, catalog ownership reconciliation and lock behavior.
- Verification exposed two related existing failures: negative YTS identity reads were cached for 24 hours, and the RSS-to-Prowlarr candidate adapter omitted normalized torrent links. Clear only failed identity-cache entries at each fresh Follow scan (retain within-scan deduplication and successful identities), and map RSS magnet/download/hash fields into the existing candidate input. Both repairs have failing regression evidence and remain within Movie Follow scope.
- Fresh review identified that accepting verified aliases must not allow sequential identity reads to multiply the scan duration. RSS identity resolution shares the existing three-second RSS budget across all rows and pending films, then proceeds to Prowlarr fallback. Movie source-result identity reads consume the existing remaining query/global deadline (25 seconds for Follow). Positive cached identities remain usable without a new network read. Timed-out/unverified evidence cannot become Available. Two 100-result outage regressions proved the delay before the correction and passed afterward.
- A further adverse-case regression proved that a short RSS timeout must not poison the longer source-search fallback. Failed cache entries record the attempted timeout; a larger available verification budget may retry the page within the same scan. Equal/smaller budgets reuse the failed result, and a fresh scan clears failures. This preserves both bounded repeated work and eventual identity confirmation.
- Misses remain Watching, recording a completed check; provider failures do not claim a successful check. Neither schedules a future Movie cooldown. Legacy `next_check_at` values are ignored and reset to zero when the next scan updates an entry; preserve diagnostic miss count and API shape without a schema migration.
- Remove unused Movie retry constants, eligibility helpers and wiring. Do not change TV retry helpers. No live data migration is required.

## Implementation sequence

1. Run the focused Movie/TV baseline with `CP_TEST_MODE=1`, unique OS-temp `CP_TEST_ROOT`, blocked providers; preserve source hashes and logs.
2. Add failing route/service regression tests for repeated scans, future retry dates, metadata dates, five real identity/title variants, wrong/unverified identities and quality/trust rejection.
3. Correct existing Movie matching and Follow orchestration; retire obsolete movie scheduling. Update conflicting tests to the confirmed rule.
4. Add a disposable fixture server and desktop test proving startup, manual Scan, repeated Scan and reload through the real Follow API and rendered Home states.
5. Run focused then broader Movie/source/curation and TV timing suites, compile the frontend to OS-temp, verify desktop, and compare protected hashes. Review the diff without committing or deploying.

## Acceptance matrix

| Scenario | Action | Exact expected result | Check |
| --- | --- | --- | --- |
| Practical Magic 2 with next-check seven days ahead | Startup/Scan | Qualifying source is searched and becomes Available now | Real route and desktop |
| Northspur 2021 vs YTS 2022 | Search | Matching verified IMDb accepted | Real matcher/provider fixture |
| Uprising/Rage, Hope/Hopeu, Sheep in the Box/Japanese title | Search | Exact IMDb accepted despite descriptive differences | Real route/provider fixtures |
| First search misses; second invocation finds release | Scan again | Second invocation searches immediately, becomes Available | Route and desktop |
| Metadata date is future but a verified release exists | Scan | Source evidence decides availability | Route |
| YTS page proves different IMDb | Scan | Remains Watching; wrong film never selected | Route/RSS |
| Unreadable identity, no IMDb, untrusted source, 720p or camera release | Scan | Cannot auto-mark Available | Adverse route cases |
| Owned film / existing verified available film | Scan | Owned removed; available preserved | Existing/new regressions |
| Provider failure | Scan again | Not falsely counted as checked; no cooldown blocks retry | Route |
| Refollow or overlapping scan | Apply old result / scan concurrently | Preserve snapshot race guard and scan lock | Existing regression suites |
| TV persistent source miss | Worker passes before/after five hours | Existing timing tests unchanged and passing | TV contracts and season planning |

## Verification and rollout

Use `.venv/Scripts/python.exe -B -m unittest` (pytest is absent; no dependency installation). Store logs in the recorded OS-temporary root. Focused baseline: user curation, YTS, curation routes, TV download contracts and season planning. Expand to relevant source-search, movie acquisition and curation suites. Build with `npm.cmd run build -- --outDir <OS-temp>/dist` and run only the new desktop spec against a fixture server on a nonproduction port with provider calls replaced by explicit fixtures. Do not replace served `dist` or touch port 5000. Live activation requires separately authorized restart; report source/isolated status and remaining live gate honestly.

Completed gates: 100-test baseline; reproduced failures before fixes; fresh review identified and corrected an identity-read duration risk; final combined regression suite 160/160 passed; compiled desktop startup/consecutive Scan/reload checks 2/2 passed; protected hashes unchanged; `git diff --check` passed. Evidence: `docs/verification/movie-follow/2026-10-13/verification.md`. Production PID 32648 was not restarted and no live Movie Follow scan was run. No commits or deployment were performed.
