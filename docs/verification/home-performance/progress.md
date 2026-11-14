# Execution record — docs/plans/2026-10-20-home-loading-performance.md

2026-10-20: Explicit dispatch authorizes Tasks 1–3 source implementation and focused isolated verification, one worker, one temporary build, ten active minutes, no retries or automatic extension. Task 4 baseline complete; no live work. Existing dirty master checkout at be511f98846a67a182e5b371ad087938e9344362 retained as instructed. No commits, worktree reset or delegation.

Pre-flight: Task 1 tests consume Task 2 lifecycle/selector and Task 3 memo/observer behavior; interfaces agree. Upcoming selection is provider order → exclusions/deduplication → twenty → existing sort. Discover backend remains authoritative for eligibility.

Ruling: Run helper tests red before source edits, then compile once and run desktop coverage against final source. A compiled desktop red/green cycle requires two builds and conflicts with the explicit one-build limit. Cost: desktop regressions have no observed pre-change failing run.

Isolation: Unique OS-temp root cp-home-performance-99a74cc6bf9a476c8eeeaf74cb5b2a5d, test mode 1, embedded qBittorrent mode, temporary dist, port 5139. Existing test mode redirects config/media/data/cache and blocks urllib provider calls; importing app does not start background services. Direct fixture launch avoids the system-qBittorrent wrapper.

Task 1: complete — helper red reproduced 23 instead of 20; final helper/model/cache checks 10/10. Added 23 behavioral desktop cases, updated Home-only expectations in the real Discover fixture. Compiled desktop red unrun per the ruling above. New desktop cases passed as a 20-case clean run plus two boundary cases and one actual-unmount case on identical compiled source.

Task 2: complete — independent retained feed operations, incremental Upcoming fill, scoped ownership publication with catalog-event revalidation, trailer base/append exclusion. Motivating response gates, navigation/Back/Forward counts, empty/error/Retry, canonical metadata and deletion races passed.

Task 3: complete — stable Home-facing callbacks and selected projection, ordinary memo boundary, persistent shared rail monitoring with DOM membership reconciliation. Power-only update: zero Home renders and zero unchanged rail registrations/disconnections, all 90 groups retained. Actual App unmount: all three rail observers disconnected and zero remaining rail scroll listeners; held feeds did not start ownership requests. Shared Movie, TV and IPTV consumers passed.

Task 4: previously completed baseline retained; no new live observation, backend optimization, artwork or startup-scan scheduling.

Final review: inspected the changed owners and callback dependencies directly, confirmed no backend/API/cache-policy changes, read compiled browser results and inspected desktop screenshots. No reviewer delegation or commit, per the explicit execution boundaries. No deferred minor findings.

Verification: 85 unique focused browser cases, 10 Node cases, 19 Python cases passed. The initial skipped completion fixture case later passed in dedicated mode. Earlier harness failures are listed in results.md and are not hidden by the final counts. One temporary build; 221.92 seconds timed commands plus 60 seconds conservatively charged for setup/cleanup and visual inspection, total 281.92/600 seconds. Fixture processes stopped; artifacts retained under the unique temporary root. Full-project suites, live activation and live performance comparison unrun.
