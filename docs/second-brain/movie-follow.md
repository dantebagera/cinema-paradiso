# Movie Follow decisions

[Movie Follow code map](../atlas/movie-follow.md) · [Second Brain index](README.md) · [Update log](log.md)

## Approved behavior

| Decision | Rule | Authority |
| --- | --- | --- |
| Startup and Scan, 2026-10-13 | Check pending movies afresh on startup and each Scan. Actual qualifying source evidence decides Available. Legacy retry timestamps and cinema dates have no veto. Existing trust, release-quality, IMDb identity, and bounded provider checks apply. Movie Follow alerts Dante. TV Follow has its own scheduling rule. | [Startup and Scan contract](../plans/2026-10-13-movie-follow-startup-scan-fix.md#exact-behavior-contract) · [TV timing](tv-follow.md#approved-behavior) |
| Catalog reconciliation, 2026-10-14 | Committed Library ownership removes the follow. Successful import and reconnect refresh ownership without requiring Force scan. A late full scan must preserve newer state, and an alert belongs only to a still-current follow instance. | [Import and Following contract](../plans/2026-10-14-automatic-download-library-following-refresh.md#exact-behavior-contract) |
| Home filters and download, 2026-10-14 | All, Available, Monitoring, and Awaiting release share one list. Available and Owned take precedence over date classification. The result count follows the selected filter, the available badge is global, and Download opens the shared review for every Available movie. Submission requires explicit confirmation. | [Following card contract](../plans/2026-10-14-following-card-filters-and-download.md#exact-behavior-contract) |

## Evidence and limits

- **Superseded** · Earlier scheduling through `next_check_at` and release-date gates is historical. The compatibility fields can still appear in responses and storage. [Movie Follow verification](../verification/movie-follow/2026-10-13/verification.md#contract-comparison)
- **Observed in source on 2026-11-13** · Startup and manual Scan share the source path. Catalog events use a separate ownership route and the shared store protects against stale scan writes. [Movie Follow code map](../atlas/movie-follow.md#entry-points)
- **Verified in isolation on 2026-10-13 and 2026-10-14** · The final startup/Scan fixture run records 160 relevant tests and two real-route desktop cases with fixture providers. Separate results cover completion refresh and global Available review. [Startup report](../verification/movie-follow/2026-10-13/verification.md#results) · [Completion ledger](../plans/2026-10-14-automatic-download-library-following-refresh.md#execution-ledger) · [Card results](../plans/2026-10-14-following-card-filters-and-download.md#results)
- **Live status unverified** · Current provider credentials, indexer trust, catalog readiness, served bundle, and visible Home state were outside this documentation pass. An Available badge and acquisition readiness are separate decisions.

## Cold-start questions

- **Why did Scan miss a known release?** Compare saved IMDb identity, enabled trusted providers, release quality, and failure counters before considering the date. [Scan and data](../atlas/movie-follow.md#scan-data-and-failure-paths)
- **Why is a finished movie still followed?** Trace catalog publication and the ownership event before running another provider scan. [Ownership scenario](../atlas/movie-follow.md#scenario-pointers)
