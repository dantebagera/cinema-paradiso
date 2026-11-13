# Search and Discover decisions

[Search and Discover code map](../atlas/search-and-discover.md) · [Second Brain index](README.md) · [Update log](log.md)

## Approved behavior

| Decision | Rule | Authority |
| --- | --- | --- |
| Movie Advanced criteria, 2026-08-16 | Different criterion groups intersect. Repeatable values use their group's explicit AND or OR, defaulting to OR. Duplicate identities in the same role collapse, separate roles remain distinct, and active numeric filters require a known value. Library and Discover keep independent drafts and the approved modes have separate reset targets. | [Gate 1 decisions](../plans/advanced-search-gate-1-decision-record.md) |
| Movie Discover logical pages, 2026-10-05 | Deduplicate and apply filters before slicing. Fill each nonfinal desktop page to its measured size and show every reachable movie on the final page. Totals can stay unknown while the source scan is incomplete. This applies to normal and Advanced paths. | [Approved full-page contract](../plans/2026-10-05-discover-full-page-contract.md#exact-behavior-contract) |
| Upcoming, 2026-10-12 | Both Home and Movie Discover require a known valid release date on or after the backend's current local date, including when applying extra filters. Home's later 20-card preview amendment leaves the full Discover list available. | [Upcoming date rule](../plans/2026-10-12-upcoming-movies-backend-rule.md#exact-behavior-contract) · [Home preview amendment](../plans/2026-10-20-home-loading-performance.md#contracts-affected-and-contract-change-decision) |
| TV first visible load, 2026-10-23 | Preserve TV catalog behavior and prioritize visible card enrichment while retaining the rest of the page. Keep controls available during first load through their existing routes. | [TV visible-load contract](../plans/2026-10-23-tv-visible-load.md#exact-frontend-behavior) |

## Evidence and limits

- **Superseded in execution** · The initial Advanced Gate 1 description of local criteria acting on one loaded TMDB page predates the later dense logical page contract. Provider scope remains bounded. The count can be unknown until the relevant scan finishes. [Earlier decision](../plans/advanced-search-gate-1-decision-record.md) · [Later contract](../plans/2026-10-05-discover-full-page-contract.md#exact-behavior-contract)
- **Observed in source on 2026-11-13** · Movie simple and Advanced workspace queries share execution endpoints within their scopes. TV reuses the query builder but has TV-specific criteria, provider routes, and catalog data. Indexer browsing and title discovery have separate entry points. [Code map](../atlas/search-and-discover.md#entry-points-and-owners)
- **Verified in isolation on 2026-10-05, 2026-10-12, and 2026-10-23** · Dated reports record Movie full/final pages, Upcoming parity, and TV visible-card enrichment. The TV report records the distinction between materially improved Discover and a modest repeated complete-artwork improvement in Library. [Movie paging](../verification/discover-paging/2026-10-05/verification.md#verification-results) · [Upcoming](../verification/upcoming-movies/2026-10-12/verification.md) · [TV visible load](../verification/tv-library-performance/visible-load-final-2026-10-23.md#final-verification)
- **Live status unverified** · Current provider behavior, result timing, configuration, and the running desktop bundle were outside this documentation pass. The TV performance approval covers the specified behavior and does not establish parity for every Movie and TV criterion.

## Cold-start questions

- **Why does page two have gaps while the provider still has matches?** Trace the query snapshot and filters before changing the grid. [Paging scenarios](../atlas/search-and-discover.md#scenario-pointers)
- **Why does a title appear in Discover and fail to match Library?** Compare the provider facts, local catalog, scope, and active criteria. [Query and data boundaries](../atlas/search-and-discover.md#query-data-and-failure-boundaries)
