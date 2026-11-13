# CP knowledge update log

Append material changes in date order. Record the affected pages, the source, what changed, and any remaining uncertainty.

## 2026-11-06 · TV Follow pilot

Created the [decision guide](tv-follow.md) and [code map](../atlas/tv-follow.md) from the [TV contract](../tv-contracts.md), the current checkout, and the [download contract](../verification/tv-download-contracts.md) and [season-pack](../verification/tv-follow-season-packs/README.md) evidence. Recorded the superseded retry proposal, the separate metadata refresh, and the legacy API that saves and starts in one request. Live Follow behavior remains unverified. The [pilot plan](../plans/2026-11-05-cp-second-brain-atlas-pilot.md) records the review and checks.

## 2026-11-06 · TV Follow Start caller found in cold-start check

The fresh chat found that ChatGPT confirmation calls the shared Start handler. Added the caller and its dispatcher-stub test to the [TV Follow Atlas](../atlas/tv-follow.md#separate-paths-and-shared-callers). The caller was verified in the current checkout. The test checks the confirmation sequence and task ID passed to Start. Live behavior remains unverified. [ChatGPT caller](../../services/chatgpt_domain_tools.py) · [Confirmation test](../../tests/test_chatgpt_domain_tools.py)

## 2026-11-07 · TV Downloads and Import

Added the [decision guide](tv-downloads-and-import.md) and [code map](../atlas/tv-downloads-and-import.md), and linked all three bulk-download entry points from the [TV Follow Atlas](../atlas/tv-follow.md#separate-paths-and-shared-callers). The new pages distinguish verification failure, partial publication, and post-publication cleanup failure. The scope covers import of downloaded episodes. Existing-file identity review has a boundary link. Live behavior remains unverified. [Approved lifecycle](../plans/2026-10-05-tv-download-storage-cp-normal-behavior.md) · [TV contract](../tv-contracts.md) · [Import and recovery tests](../../tests/test_tv_normal_import.py)

The read-only cold-start check found both guides from the knowledge index without file paths. It explained all three failure and recovery cases, located the associated test definitions, and found TV Library, TV Discover, and TV Lists in the Atlas before verifying their shared caller in source. Git status and the checked file hashes matched across that check.

## 2026-11-07 · TV Library and Maintenance

Added the [decision guide](tv-library-and-maintenance.md) and [code map](../atlas/tv-library-and-maintenance.md) for existing TV files. Both distinguish show assignment, episode matching, exclusion, and current availability. Linked the new pages from the Downloads and Import guides and separated historical proposals from observed behavior. [Historical inventory](../verification/tv-library-import-preview.md) · [Current scan owner](../../services/tv_ingestion.py) · [Import tests](../../tests/test_tv_library_import.py)

The read-only cold-start check found both guides from the knowledge index without supplied paths. It distinguished unassigned, unresolved or conflicting, excluded, and unavailable files, and found the corresponding code and test definitions. Git status and the checked file hashes matched across the check. The source trace also found that the assigned scan can skip an unchanged file whose catalog availability was cleared. The Atlas records the separate series-scoped scan and binding update for that case.

## 2026-11-07 · Movie Library and Identity Review

Added the [decision guide](movie-library-and-identity-review.md) and [code map](../atlas/movie-library-and-identity-review.md) for Movie files and cross-linked the TV guides. The new pages distinguish a file outside the scan, a cataloged file awaiting publication, a ready card excluded by the current query, and provider identity versus a display override. [Approved ingestion plan](../plans/online-library-ingestion-final-card-zero-regression-plan.md) · [Publication owner](../../services/catalog_repository.py) · [Manual correction tests](../../tests/test_sql_migration_parity.py)

The read-only cold-start check found both guides from the knowledge index without supplied paths. It separated scan, publication, filtering, provider identity, and display override, then located the related test definitions. It also found the direct full-reconcile and provider-migration tests for manual locks, which were added to the Atlas. Git status and the checked file hashes matched across the check.

## 2026-11-07 · Movie Downloads and Import

Added the [decision guide](movie-downloads-and-import.md) and [code map](../atlas/movie-downloads-and-import.md) for Movie releases and linked them to the Movie Library and TV Downloads guides. Recorded the separate transfer and Library completion states, the recovery paths for the existing job, and the README's conflicting move/removal order. [Handoff contract](../plans/2026-10-23-movie-library-search-and-retry-performance.md#completed-download-bridge-and-completion-refresh) · [Move-order test](../../tests/test_qbittorrent_service.py) · [Library handoff tests](../../tests/test_qbittorrent_api.py)

The read-only cold-start check found both guides from the knowledge index without supplied paths. It distinguished move, cleanup, and Library recovery, identified the same-hash magnet guard and its limits, and located the relevant test definitions. Git status and the checked file hashes matched across the check. The Atlas now includes the monitor status and cleanup-replay test the check found in source.

## 2026-11-13 · First edition

Added nine topic pairs, from Movie Follow through Settings and Shared Infrastructure. All 14 pairs are reachable from the knowledge index and link back to their companion. The audit checked local links, heading anchors, and named test references. [Knowledge index](../README.md) · [Scope and acceptance matrix](../plans/2026-11-13-cp-knowledge-first-edition.md)

- **Movie transfer to Following removal** · A reader traced the existing qBittorrent job through transfer and atomic Library publication, then found the catalog-ready or reconnect path that reconciles Following against committed Movie ownership. The walkthrough exposed the alternate torrent ID case, which now has a direct recovery pointer in both Movie Downloads guides. [Movie Follow](../atlas/movie-follow.md) · [Transfer and hybrid IDs](../atlas/movie-downloads-and-import.md#finished-in-qbittorrent-pending-in-cp) · [Library publication](../atlas/movie-library-and-identity-review.md)
- **TV version to Home** · A reader traced an exact file ID through the TV play endpoint and native player events to the TV catalog and Home Continue Watching. The guides point to separate checks for saved file selection, progress persistence, and Home presentation. The walkthrough found no single test spanning all three. [TV Library](../atlas/tv-library-and-maintenance.md) · [Playback](../atlas/playback-and-streaming.md) · [Home](../atlas/home-lists-and-notifications.md)
- **Decision and evidence gaps** · Recorded source differences from earlier Playback and Movie Maintenance decisions, plus the Pick My Movie correction verified in a separate checkout. The walkthroughs were read-only source checks. App tests were referenced, and current live feature behavior remains unverified. [Playback decisions](playback-and-streaming.md) · [Maintenance decisions](movie-maintenance.md) · [AI decisions](ai-features.md)
