# TV stabilization — implementation and qualification

Implementation checkout: `C:\Users\dante\.codex\worktrees\0870\cinema paradiso`.

Launch entry point for Dante: `run.bat` in that directory. Normal CP was not launched or restarted. All application tests used disposable OS-temporary roots, fake acquisition/player adapters, and isolated ports. No live catalog, media file, settings, monitoring rule, or transfer was changed. No commit, push, or release was made.

## Delivered scope

1. Reconciled all 43 Desktop changes, including uncommitted More Like This, library publication/startup changes, richer movie details, expanded-card positioning, and native-player source/runtime. Four overlapping files were merged against the common ancestor; see `reconciliation.md`. Both original dirty trees were backed up before reconciliation.
2. TV Library and Discover use the existing AdvancedSearchBuilder and query normalization. TV query execution has one owner, `TVSearch`; older TV GET interfaces delegate to it. Title, people/roles including creator, keywords, genre exclusions, first-air year, rating, language, origin country, episode runtime, viewing status/watchlist, resolution, source, discovery votes/ownership, sorting and feeds are supported. TV status/monitoring/missing/progress/audio-language filters remain available. Movie lists are deliberately absent from TV criteria.
3. TV details include trailers through the existing trailer window, aggregate cast/crew/creators, rating/votes, language/country/runtime, provider links, and TV watchlist actions. Online detail previews and season browsing are read-only; Add series is explicit. StreamIMDB TV URLs derive automatically from the configured StreamIMDB movie URL. Movie and TV playback use the same StreamPlayerModal, iframe settings, and provider player. Explicit TV overrides and unrelated custom movie providers are preserved.
4. Prowlarr TV searches use bounded concurrent requests to enabled TV-capable sources. One source failing cannot erase completed results. The dialog reports partial results and source states, supports retry, and aborts/ignores late responses when closed. Custom empty selection never broadcasts. Release evaluation and submission protections remain unchanged.

Additional regression repairs: equivalent movie search-mode switches no longer repeat requests; complete canonical local details avoid unnecessary TMDB requests. The shared trailer and stream windows now use one Escape/focus-restoration helper.

## Data and filtering semantics

- TV schema v2 adds only TV-owned watchlist state. Upgrade/reopen and v1 backup restore preserve series/episode identity, versions and progress. Watchlist never enables monitoring.
- Local predicates execute before pagination. Watched means all released episodes completed. Ownership requires an available file, not catalog membership. Deleted/unavailable files do not satisfy local quality or availability.
- Resolution comes from measured media facts. Audio languages come from measured tracks, with support for older records. Source is the existing filename source classification and remains a claim, not proof of provenance.
- Upgrade candidates use the shared profile cutoff comparison per episode, considering its best available version. This does not enable automatic upgrades.
- Online title/person/local-state combinations filter the current provider page and explicitly report incomplete totals and page-local ordering. Empty filtered pages still allow Next. Direct TV Discover criteria are sent to TV provider endpoints.
- Existing catalog rows may need **Refresh metadata** once to populate newly stored keyword/person/language/runtime filter fields. No live refresh was run automatically. Detail reads can obtain missing online trailer/display fields without rewriting local state.
- Movie-only collection/budget/list/file-management behavior and visual redesign remain outside this scope.

## Real provider evidence

Original Prowlarr logs showed Reacher S01 and S01E01 sent to 14 indexers in aggregate; the old TV transport imposed a single 20-second timeout. A separate 1337x read returned 46 results in 6.19 seconds.

The repaired transport was exercised read-only against the configured Prowlarr: **166 results returned in 20.00 seconds**; 13 sources completed, dmhy timed out, and Zamunda RIP failed. No acquisition route/store or download submission was involved. Redacted evidence: `prowlarr-read-only.json`.

Those real results did not contain TMDB/TVDB IDs. Existing acquisition checks consequently reject unverified identity. This repair does not claim real downloads were accepted or bypass that safeguard. Acquisition browser tests use explicit fixture identities and fake transfers.

Earlier live StreamIMDB verification demonstrated the episode URL and actual Reacher S01E01 player; the current browser checks verify CP's exact episode routing, shared window, iframe teardown, and absence of automatic watched changes with intercepted embeds. Current live subtitle selection and uninterrupted provider playback are not claimed as newly verified. Provider availability remains external to CP.

## Qualification

- Pre-change TV baseline: 1,299 Python tests passed; original Desktop focused baseline: 107 passed.
- New focused backend tests cover partial/failing/malformed indexers, explicit empty selection, combined TV predicates, roles, controlled identities, zero/unknown sort values, file availability, measured audio languages, per-episode upgrade cutoff, read-only preview, TV configuration derivation without writes, and v1 migration/restore.
- Movie browser coverage: all 85 distinct existing checks have passed across the qualification runs. These include More Like This on all owning surfaces, pagination, owned details, advanced search, settings, native-player routing, IPTV, selection, and background catalog updates.
- TV browser coverage: all nine checks passed, including shared filters/reset, preview without catalog insertion, trailer isolation/close, exact episode streaming, progress, fake release submission, watchlist isolation, partial-search retry/cancellation, and browser Back from preview.
- One initial browser selector named the wrong criterion button. A separate checkbox test needed to click the actual visible custom label instead of forcing the covered native input. Their assertions were preserved.
- An intermediate full Python run found two obsolete source-text assertions after Desktop restoration and one IPTV timing failure under concurrent test load. The two assertions now name the actual restored implementations; the unchanged timing test passed in isolation and in the final serial suite.

Final qualification:

- **1,326 Python tests passed** in the serial full-suite run (313.486 seconds).
- **101 Node tests passed**, with no failures or skips.
- **94 distinct browser checks passed across qualification runs**: 85 existing checks and nine TV checks. This is aggregate coverage, not a claim that one 94-test run completed. Earlier failures and their corrections are documented above; the final targeted 13-check run passed in full.
- Production frontend build succeeded. The production frontend route owner served `/library`, `/discover`, and `/tv/series/1` with the rebuilt index, and all **38 compiled assets matched their disk contents byte for byte** through Flask's test client. No normal application or network server was launched for this check. Hashes and results: `build-evidence.json`.
- `git diff --check` passed. All 43 original Desktop changed-file states still match the pre-implementation backup.

Final Python, Node, build, and browser logs are in `C:\Users\dante\.codex\backups\cp-tv-stabilization-20260918-183441` (`qualification-python-final.log`, `qualification-node.log`, `qualification-build.log`, `qualification-browser-v2.log`, and `qualification-tv-browser-v2.log`). Earlier qualification logs remain there for comparison.

Desktop screenshots: `library-filters.png`, `preview-details.png`; related-movie desktop screenshots and full logs are retained in the reconciliation backup. These are fixture images, not captures of Dante's live library.
