# Home, Lists, and Notifications decisions

[Home, Lists, and Notifications code map](../atlas/home-lists-and-notifications.md) · [Second Brain index](README.md) · [Update log](log.md)

## Recorded decisions

| Decision | Rule | Authority |
| --- | --- | --- |
| Home desktop layout, 2026-10-19 | Keep the agreed projector header and Home section order. Preserve trailer grouping, source filtering, all loaded videos, alternate playback versions, scrolling, and load-more while reusing existing presentation owners. The design register records individual visual decisions and a separate implementation gate. | [Design register and resolution](../plans/2026-10-19-home-dashboard-hybrid.md#decision-register) |
| Home loading, 2026-10-20 | Retain resolved content during refresh and join active requests when returning Home. Trending can finish independently. Home chooses up to 20 eligible Upcoming movies after removing duplicates and Trending overlaps. Fewer are valid after proven exhaustion. View all goes to full Discover Upcoming. Keep existing trailer behavior and shared rail interactions. | [Loading contract](../plans/2026-10-20-home-loading-performance.md#exact-behavior-contract) |
| Following on Home, 2026-10-14 | The count follows the selected filter while the available badge represents all Available follows. Download opens review for all available films. Movie availability alerts and TV Follow lifecycle are separate flows. | [Following decisions](movie-follow.md#approved-behavior) · [TV Follow decisions](tv-follow.md#approved-behavior) |
| Movie and TV Lists, 2026-10-12 and 2026-10-14 | Apply filters and sorting before pagination. Preserve canonical Movie Library metadata, show incomplete refinements when required facts could not load, and offer Retry. TV uses its own membership and criteria validation within the adopted shared desktop layout. | [Movie Lists performance contract](../plans/2026-10-12-mostafa-performance-plan.md#contracts-affected-and-contract-change-decision) · [Approved main integration](../plans/2026-10-14-new-ui-main-integration.md#authoritative-owners) |

## Existing behavior and evidence

- **Observed in source on 2026-11-13** · Movies and TV have separate list stores and routes, with shared desktop controls. Movie Watched requires ownership while Watchlist accepts an unowned title. TV Follow publishes durable notification history. App toasts have their own lifetime and Movie availability uses that path. A separate approval for persisting Movie availability toasts or merging the two list stores was not located. [Lists and notification owners](../atlas/home-lists-and-notifications.md#lists-and-notifications)
- **Verified in isolation on 2026-10-20** · The Home loading report records 85 desktop, 10 Node, and 19 Python cases within the selected scope. It covers retained data, capped Upcoming, alternate trailer videos, and shared rail behavior. It measures avoided renders and observer work. Elapsed improvement on the running app remains unverified. [Home results](../verification/home-performance/results.md#final-focused-results)
- **Dated Lists and TV evidence** · The 2026-10-14 main integration report records the compiled desktop gate and activation of the integrated UI at that time. The TV contract report records lifecycle tests. Current Lists and Sidebar notification rendering were outside this pass. [Main integration record](../plans/2026-10-14-new-ui-main-integration.md#final-completion-record) · [TV contract verification](../verification/tv-download-contracts.md) · [Scenario pointers](../atlas/home-lists-and-notifications.md#scenario-pointers)
- **Live status unverified** · Current feeds, ownership, playback history, badge counts, served bundle, and user data were outside this documentation pass.

## Cold-start questions

- **Why is Coming soon slow or short while Trending is ready?** Check the two feed operations, provider exhaustion and deduplication before attributing the delay to artwork. [Home owners](../atlas/home-lists-and-notifications.md#home)
- **Why did a toast appear but the notification history has no row?** Determine whether App published a transient message or an acquisition task wrote a durable event. [Notification owners](../atlas/home-lists-and-notifications.md#lists-and-notifications)
