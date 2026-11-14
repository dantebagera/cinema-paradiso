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

## 2026-11-13 · IPTV cast, Discover badges, and Movie source choice

Updated the IPTV, Movie/TV details, Search/Discover, and Playback/Streaming decision guides and Atlas maps from Dante's explicit approval, the isolated candidate sources, and [2026-11-13 isolated verification](../verification/iptv-cast-discover-streaming-2026-11-13/report.md). Recorded the approved Movie chooser contract change, preserved direct TV streaming, separate read-only provider databases, shared cast/session owners, lazy badges, and exact-source playback. The candidate has not been activated; real external playback remains unverified.

## 2026-11-13 · Correct IPTV Filmography destination

Dante corrected the distinction: portrait opens provider-local movies; the small Filmography control opens full Movie Discover filmography. "Yes go" approved correction, tests and activation. Updated IPTV/detail Second Brain and Atlas, removed the obsolete provider-local full-filmography branch, and reused the shared Movie navigation owner. [Plan](../plans/2026-11-13-iptv-filmography-discover-correction.md) · [Evidence](../verification/iptv-filmography-discover-2026-11-13/report.md).

Filmography correction activation verified: main bundle `index-rEoonoEd.js`, PID32136, unchanged configuration/data owner. Production desktop browser clicked Brad Pitt's small button from Lionz and reached Movie Discover with115 credits and correct IPTV breadcrumb; compiled regression47/47 passed.

## 2026-11-14 · Discover posters load before backdrops

Recorded Dante's decision and the shared scheduling path in the [decision guide](search-and-discover.md) and [code map](../atlas/search-and-discover.md#discover-card-artwork). The compiled candidate passed the desktop artwork and TV checks and reduced median visible Movie poster time by 89 ms in the paired benchmark. The live app still served the baseline bundle. [Implementation and timing](../plans/2026-11-14-discover-poster-priority.md)

## 2026-11-14 · Poster priority extended across CP and activated

Moved the shared scheduling scope to the app shell and connected the existing related-title poster markup. Updated the Search and Discover guides. All ten main workspaces loaded the live frontend without a restart. Movie Discover verified poster-before-backdrop order with real artwork. [App-wide implementation and verification](../plans/2026-11-14-app-wide-poster-priority.md)

## 2026-11-14 · IPTV bulk matching continues after sync

Recorded the approved Resume scope and preparation bar placement in the [IPTV decisions](iptv.md#approved-bulk-matching-decisions) and [code map](../atlas/iptv.md#chatgpt-matching-and-apply). A read-only check confirmed 861 eligible unfinished Lionz sources. The desktop acceptance checks use synthetic data and an offline provider. [Plan and verification](../plans/2026-11-14-iptv-resume-after-sync.md)

## 2026-11-14 · IPTV focused TMDB recheck

Recorded the approved search change and explicit saved-results recheck in the [IPTV decisions](iptv.md#approved-bulk-matching-decisions) and [code map](../atlas/iptv.md#chatgpt-matching-and-apply). The read-only replay verified eight of the 20 sampled search-limit rows. All ten sampled conflict cases stayed in review. [Plan and verification](../plans/2026-11-14-iptv-focused-tmdb-recheck.md)


## RT main-folder application — 2026-11-14

Dante approved the4px exception for crowded collapsed cards without TMDB/awards, and applying the feature to main. He then instructed not to test; he will handle testing. Applied21feature files while preserving current main changes and rebuilt main dist successfully. No tests, runtime restart or live verification were performed. Collapsed RT shares the bottom row with TMDB; votes label is omitted there, numeric count retained. Expanded RT sits between awards and TMDB; long titles wrap. Optional-Plex persistence and lazy-loading behavior are unchanged. [Application record](../verification/plex-rotten-tomatoes-2026-11-14/report.md).
# 2026-11-14 YouTube Movie source

Dante approved duration-first YouTube search (±5%), Arabic names for Arabic films, explicit optional GPT, Search more, and no uploader filtering. Updated Playback/Streaming decisions and Atlas plus AI Atlas. Implemented and verified in isolation; 72 focused Python, 21 Node and 18 desktop/integration scenarios passed; broader Python retains two confirmed baseline source-string failures. No live activation. [Plan](../plans/2026-11-14-youtube-movie-stream.md) · [Report](../verification/youtube-stream-2026-11-14/report.md).

## 2026-11-14 · Saved TMDB recheck after provider sync

Recorded the approved catalog-refresh behavior in the [IPTV decisions](iptv.md#approved-bulk-matching-decisions) and [code map](../atlas/iptv.md#chatgpt-matching-and-apply). Read-only Lionz inspection found all 1,363 saved hints still fit the prepared catalog. The live recheck was not dispatched. [Follow-up and verification](../plans/2026-11-14-iptv-focused-tmdb-recheck.md#approved-follow-up--start-a-saved-recheck-after-sync)

## 2026-11-14 · Shared desktop UI visual choices

Dante chose all eight recommended families from the side-by-side comparison and limited unification to UI. Recorded the selections in Settings/shared-infrastructure Second Brain and Atlas and prepared [the implementation plan](../plans/2026-11-14-shared-ui-standardization.md). No product code or runtime changed in this planning step; implementation and activation remain unapproved.


## 2026-11-14 · Mandatory UI reuse and approved family implementation

Dante explicitly approved adding the permanent reuse rule and proceeding with the selected families. Added the hard gate to AGENTS, the [shared UI registry](../atlas/shared-ui.md), build/dev checks, production primitives and caller migrations. StyleGuide now renders production owners. Updated Settings/shared-infrastructure decisions and Atlas. [Verification](../verification/shared-ui-2026-11-14/report.md) separates passing targeted checks, known baseline failures and source-only status. No installed-bundle activation, restart or commit.

## 2026-11-14 · Shared UI bundle activated

Dante separately authorized installation of the reviewed frontend. Installed the exact tested candidate, preserved a full rollback backup and previous assets, verified live JS/CSS byte hashes, and visually checked the live StyleGuide including green Play/Stream. Existing CP windows need refresh; backend and data were unchanged. [Activation evidence and rollback](../verification/shared-ui-2026-11-14/report.md#authorized-live-installation--2026-11-14-1753-cairo).
