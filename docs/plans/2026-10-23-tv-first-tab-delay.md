# First TV-tab initialization and Discover fact reuse

**Status:** Approved for diagnosis, implementation and bounded verification by Dante: “keep investigating the first tv tab loading delay until you find the actual cause and fix it. preserve all existing behavior and stop asking me to approve every step”. This is continuation work after the earlier600-second isolated scope, whose ledger remains unchanged. No routine reapproval is needed for explained harness defects. No catalog/configuration/media edits, acquisition actions, commit or publication.

Implemented and verified in source/isolation; production activation not performed. Results, retained failures and the distinction between the complete45-case desktop gate and final two-case correction are recorded in [first-tab-fix-2026-10-23.md](../verification/tv-library-performance/first-tab-fix-2026-10-23.md).

## Problem and decision

The retained page cache works; cold TV initialization remains slower than switching to an already loaded Movie page. The86.7-second original capture lacked exact browser timings. A temporary localhost diagnostic proxy now observes the unchanged built frontend and existing backend without replacing assets or restarting it. Browser timeline: Library TV click6873.8ms, module loaded6981.4ms, first TV requests7283–7285ms,33 cards8086.6ms. About300ms follows module readiness before requests. React production scheduler contains the300ms fallback throttle. API716ms, JSON parse4ms and final card render43ms dominate the rest. Discover first click47205ms, request47222.6ms, response50278ms,40 cards50312.9ms; two later enrichment batches take about1.9s and remain independent of initial visibility.

One read-only actual-data owner profile (SQLite mode=ro/query_only, no constructors/migrations) shows local preparation283ms plus nine independent owned-card detail calls11–114ms each after provider retrieval. Those repeat facts already acquired. Provider latency also contributes and is not promised away.

Decision: remove only the unnecessary code-loading boundary in MediaWorkspace; retain TV's lazy **mount/data** behavior. Reuse one compact request context through Discover's current detail owner. Do not prefetch TV catalogs, add cross-request result caches, thin payloads or change provider paging/enrichment policies.

## Contracts affected and contract-change decision

| Contract | Current/agreed behavior | Change? |
| --- | --- | --- |
| First TV selection | Same results/actions; start fetching TV data on first selection | No; code becomes ready earlier, data mount remains selection-gated |
| Cached return | Retain mounted Movie/TV panels, filters/page/scroll/selection and no repeated catalog search | No |
| Library and Discover outputs | Complete existing fields/order/counts/coverage/actions and error policy | No |
| Physical availability and progress | Fresh per request; coherent request-local facts, no cross-request cache | No |
| Discover metadata enrichment | Every current visible-page item remains enriched; same paging/provider limits | No |

No product contract decision is open. Loading order of the JavaScript bundle is implementation detail; no TV service request may occur before selection.

## Current design and ownership

master/be511f98846a67a182e5b371ad087938e9344362,216 existing status entries before this continuation; preserve dirty source snapshots under OS-temp `cp-tv-first-tab-fix-317228b6-e92c-4665-97b4-028cfb3c2882`. Live backend31584 from this checkout, production data root `data`, TV media rootG:\TV, existing dist unchanged during diagnosis. Diagnostic proxy5128, no mutation endpoints. New phase uses a separate capped300-active-second verification ledger; original580.59/600 ledger is not reset or reinterpreted.

| Responsibility | Authoritative owner | Change |
| --- | --- | --- |
| Media selection/mount/cache/scroll | MediaWorkspace.jsx | Eager code import; same mounted gate/hidden panels/session state/callbacks |
| Compact TV facts and full details | TVCatalogRepository/TVReadModel | Existing APIs reused unchanged |
| Discover composition | TVSearch.discover | Create one context, pass to local_rows and matched owned-card detail; do not retain across calls |
| Diagnostics | tools/tv_tab_timeline.py | Temporary loopback proxy/console timeline, never installed frontend logic; stop proxy after verification |

## Exact behavior contract

### Frontend

Reuse the same TVWorkspace, MediaWorkspace, shared cards and controls. No geometry, typography, labels, cards, filters or navigation change. TVWorkspace must remain unmounted until selection/deep-link/media request; code import alone must not issue TV catalog requests. Subsequent returns reuse the same component/state and preserve scroll. Remove the obsolete inner Suspense/lazy code path rather than adding another loader/cache; outer section Suspense remains authoritative for section bundle loading.

### Backend

Same discover inputs/outputs/provider deadline/page limits/filter scan state. Acquire one TVLibraryReadContext at request start, feed local_rows, and use the same context for owned-card read.detail calls. The context must be released after the call and never enter scan-cache payloads. No schema/migration/persistence change, no provider parallelism increase and no playback rule change.

## Implementation sequence

1. Add a deterministic cold-code-delay desktop regression and a Discover one-snapshot/exact-field regression; observe both fail against baseline.
2. Replace the unnecessary inner lazy import with the existing component's eager code import; preserve selection/mounted gates. Pass one context through Discover preparation/detail.
3. Run focused Python/Node checks, before/after bounded synthetic Discover memory checks, compiled desktop cases (including cached returns, loading errors and exact Versions/Play) and a first-load browser timeline. Diagnose/fix explained harness issues within this approval; do not relax product assertions.

## Acceptance matrix

| Scenario | Exact expected result | Check |
| --- | --- | --- |
| First TV click with deliberately slow TV code fetch | Data request starts promptly after selection; code delay paid before the interactive parent, no300ms inner fallback | New desktop test with600ms module-route delay, request-start bound400ms |
| Before first selection | No TV catalog request | Same test request counter |
| Movie→TV→Movie→TV | Same results and selected controls; exactly one catalog load | Same test plus existing native/parity navigation |
| Owned Discover cards | Same public detail/action/count/poster fields; one snapshot/one check per path | New synthetic structural/parity test |
| Unowned/empty/filtered/partial/error/provider pages | Existing output semantics retained | Existing stabilization/list/filter/relationship suites |
| Request lifetime | Context collected; no scan-cache retention or memory regression beyond bounded comparison | Weakrefs and6/24-series synthetic service memory comparison |
| Other Movie/TV callers | Named desktop specs unchanged and pass | Full existing five specs plus new first-load spec |

## Verification and rollout

Fresh unique OS-temp roots, CP_TEST_MODE=1/embedded clients, one worker, zero flaky retries, bounded phases and under1GiB retained scope. Reuse the existing runner with explicit continuation-root/config inputs; never overwrite old evidence or reset its ledger. Named Python suites as in earlier report plus new regression; Node TV tests; temp Vite build; isolated native fixture5127, guarded player/provider transports and local artwork. No hardware/storage stress or growth tests.

First capture timings are single instrumented observations, not universal speedup guarantees. Keep the existing backend process and production dist unchanged during this continuation, respecting Dante's earlier restart boundary. Verify the compiled candidate through a temporary frontend proxy using the same running backend, and verify backend changes with isolated fixtures and SQLite mode=ro actual-data comparisons. This establishes source and isolated verification, not live activation. Ordinary startup/cache/background writes from the app cannot be represented as zero writes. No remaining minor review issue should create another routine approval stop.
