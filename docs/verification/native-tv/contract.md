# Native TV implementation contract

The 2026-09-18 plans and the current task authorization govern this work.
All implementation is independently written from CP requirements; no Sonarr or
Radarr code, fixtures, schema, or runtime is imported.

## Domain ownership

TV identity is `tmdb:tv:<id>`; an episode key appends aired season and episode
numbers. Movie identity and movie SQL remain unchanged. TV has its own versioned
SQLite schema, connections, backups, migrations, people, files, progress, and
review queue. No attached databases or cross-database foreign keys.

Metadata refresh upserts provider facts but never deletes local files, bindings,
or progress. Conflicting provider renumbering is quarantined. File publication
requires explicit episode bindings. Dates without a known released state cannot
be automatically downloaded or streamed. A shared multi-episode file cannot
automatically complete separate episodes without known segment boundaries.

Acquisition SQLite owns profiles, decisions, intent, events, blocks and leases.
It does not own transfer paths or progress. `QBittorrentJobStore` owns transfer
and import recovery, including TV jobs. The existing movie move path remains
the compatibility default. Hardlink/copy retains source files and copies.

## Isolation and rollout

TV capability is off by default. Fixtures enable it in temporary configuration.
Provider and client integrations use injected fakes in tests. Runtime tests use
unique OS-temp roots and non-production ports. Existing movie selection remains
authoritative while candidate decisions are evaluated in shadow mode.

The startup repair was authorized by Dante after the Phase 0 stop. The ongoing
authorization covers necessary in-scope repairs without more approval prompts.
Live pilot, production operations and Git publication remain excluded.

## Acceptance fixture matrix

`tests/fixtures/native_tv_cases.json` defines synthetic hierarchy, specials,
released/future episodes, multi-episode files, packs, daily/absolute ambiguity,
sample filtering, false source labels, unsafe paths and typed streaming targets.
Tests must prove repeated refresh, restart, copy retention, progress isolation,
safe failure recovery, duplicate suppression and movie parity at shared seams.
