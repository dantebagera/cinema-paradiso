# Movie awards implementation — 2026-10-02

**Status: implementation, complete historical seed and final verification are finished. All six approved source tasks are implemented and verified in isolation. The final full Python suite passes all 1,563 tests. No layout or source decision remains pending. Dante canceled shutdown; no shutdown is scheduled.**

All 98 Oscar ceremonies and 83 Golden Globe ceremonies pass full independent category/winner/recipient and typed identity checks. There are zero unresolved identities, conflicting mappings or source failures. The reproducible seed contains both complete organizations. The running Desktop application has not been deployed or restarted as part of this source implementation.

## Placement clarification and sizing correction

Dante explicitly clarified: “i selected an area for implementations , the sizes of the award photos should shrink to fit the place”. The prior fixed 52px reservation and award dimensions were implementation assumptions. Treating them as a reason to shrink actor portraits or replace the credit grid was incorrect.

The shared awards styles now remove the extra portrait padding and size the number/image pairs within the existing right-side control area below Biography and Filmography. Award rows compact as the existing portrait height decreases at narrower desktop widths. The original portrait sizing, ten-column grid, credits slot and related rail are preserved. The browser checks now require uniform portraits and containment of two-digit count/image pairs within that selected area, clear of the existing actions and person labels. The 1920px 106×132 portrait checks and existing relationship checks remain intact.

The previous request to choose smaller actor portraits or a scrolling replacement is withdrawn. No such redesign is required or approved. The correction passes at 1920×1080, 1600×1000, 1366×900 and 1366×768. The additional Tom Cruise example is preserved in [person-placement-clarified.png](reference/person-placement-clarified.png). Actor portraits keep their original geometry when awards load later; two-digit counts remain visible in full, and a single Globe retains its lower position. The early two-digit setup error and subsequently detected name-style ellipsis were corrected; the clipping regression was observed failing before the count-style fix.

## What changed

- One movie-only awards subsystem owns parsing, explicit category classification, verified identities, historical builds, SQLite publication and annual refresh. Film totals count distinct ceremony/category awards rather than recipients; actor/director wins and film membership remain separate.
- The local SQLite store publishes contributions, person links, newly verified identities, generation and refresh state in one transaction. Repeated imports and old seeds do not add or downgrade counts. Concurrent fresh startup and lease ownership have regression coverage.
- Three local read-only endpoints provide snapshot, refresh status and paginated winning films. They neither initialize the catalog nor call providers. Snapshot ETags and generation comparisons are scoped to the active data-folder owner.
- A cancellable startup-owned worker bootstraps the seed in the background. It uses Cairo's actual Windows timezone/DST rules, January/March eligibility, seven-day pending retries, bounded source/identity reads and persistent leases. Missing evidence keeps the previous complete generation. Test mode never automatically starts external refresh.
- One passive award renderer and one shared snapshot cache serve explicit regular-movie callers. Zero/unknown pairs stay hidden. Number-left icons, exact tooltips, award-only footers, accepted canonical identities and temporary Arabic display are covered.
- Actor/director award clicks open the exact winning-film set in Discover, clearing prior narrowing criteria. Existing request cancellation, pagination and history owners handle stale responses, page-generation conflicts and restoration to Library/Lists/AI/Explore/Pick/Browse origins. Existing biography and Filmography actions retain their separate meaning.

The prior Filmography regression test assumed that Back collapsed the movie, then clicked its heading again. The approved history contract restores its expansion. The test now asserts that restored expansion before using the credit body; its full-credit and preserved-filter assertions remain unchanged and pass.

## Historical publication gate

The seed contains 181 ceremony contributions and 2,377 verified movie/person mappings. SHA-256: `d634b020c4f8410cc1b916eab6c38ab5b389cea749885347f2da51240da918b3`. Two identical offline builds produced identical bytes. The checked-in bundled-seed test rebuilds without credentials/network, verifies byte equality/hash, installs both complete organizations into OS-temp and proves a second installation is idempotent.

The real snapshot confirms Gladiator has two Globe film awards, Les Girls has two rather than multiplying its shared actress award, and Sallah has three distinct historical instances: New Star, Foreign Language and Samuel Goldwyn. Tom Cruise has three acting Globes, with exact winning-film membership TMDb 2604, 9390 and 334. Marjorie Morningstar's future-film illustration creates no award contribution.

Reproduction inputs, exact revisions, byte hashes, scoped identity corrections and attribution are in [reproduction/README.md](reproduction/README.md). The complete audit is [historical-coverage-audit.json](historical-coverage-audit.json); [historical-gaps.json](historical-gaps.json) contains no remaining gaps. [historical-crosscheck-details.json](historical-crosscheck-details.json) records all 181 successful checks, including ties, multi-film awards and supplemental independent program evidence.

Pinned Wikipedia category tables replace incomplete annual film associations and incorrect historical winner flags. The authoritative parser reconstructs row spans, preserves ties and distinct Comedy/Musical columns, requires positive winner evidence and verifies exact reviewed conventions against their page/revision. It rejects missing markers, misplaced film columns, year/ordinal disagreement, unknown categories and unsupported shapes. Explicit primary source groups assign one owner per category/ceremony; overlapping owners fail the build.

The original CC0 historical CSV retains retired categories. Seven film-specific specials/outdoor awards omitted from it and the distinct ceremony-22 Samuel Goldwyn award are restored through pinned licensed factual curation. The 118 original sparse official records independently replace only named inaccurate/incomplete historical category blocks. Each row retains its original page, response hash and hash-bound transcription proof. Raw official website HTML/prose remains outside the bundle. Wikipedia source bytes retain CC BY-SA attribution; CC0 applies to the original official fact compilation, never the source website. The modern Mengting/IMDb scrape is not a bundled input.

Category independence is checked against both adapter/revision and actual cited record origin. A transcribed copy cannot verify its original category under a different parser name or compilation hash. A source may contribute evidence on opposite sides for different categories only when each category has a different actual independent record. Every full winning-film/eligible-recipient comparison still passes.

Reviewed exceptions preserve the approved film-association contract. Debbie Reynolds's 1951 New Star entry is a nominee; generic Gene Nelson remains the winner. Carolyn Jones's 1958 honor has no named film in the original CSV or official record; the category-page Marjorie Morningstar illustration is excluded by replacing that whole ceremony/category with the original feed. Pia Zadora retains the generic 1982 New Star category. The official Miracle Worker URL mixes movie and TV entries; only the explicit 1963 movie-category winner is used, anchored to the 1962 film. Scenes from a Marriage is the 1974 theatrical film, not its TV identity. Exact contextual aliases, pinned subject links, typed external-ID lookups and eligible credits are retained; no fuzzy title matcher or count override was added.

Future annual checks preserve the full independent program/winner/identity gate. An incomplete feed or new unsupported category/layout remains pending, retains the last complete generation and retries weekly. No future source availability is promised.

## Current verification

All runs used this Desktop checkout, Python/Node already installed, fresh OS-temp data roots and isolated Vite output. The production `dist` was not rebuilt.

| Check | Result | Evidence |
| --- | --- | --- |
| Focused source/identity/store/API/refresh/bundle/startup/card/relationships/package Python | 174 passed | [layout-example-focused-python.log](test-runs/layout-example-focused-python.log) |
| Final parser/identity/offline-seed regressions | 119 passed after the complete historical audit and source-independence guard | [complete-history-focused-python.log](test-runs/complete-history-focused-python.log) |
| Full Node suite | 110 passed | [layout-example-full-node.log](test-runs/layout-example-full-node.log) |
| Complete-history full Python suite before the last source-independence guard | 1,562 passed in 208.381 seconds; two resource warnings | [complete-history-intermediate-full-python.log](test-runs/complete-history-intermediate-full-python.log) |
| Final full Python suite including source-independence guard | 1,563 passed in 206.699 seconds; two resource warnings | [complete-history-full-python.log](test-runs/complete-history-full-python.log) |
| Full normal browser suite | 113 passed; 37 native-TV skips | [layout-example-full-e2e.log](test-runs/layout-example-full-e2e.log) |
| Additional final placement/loading/single-Globe browser checks | Six passed; includes the four desktop sizes and new single-Globe case | [layout-example-additional-e2e.log](test-runs/layout-example-additional-e2e.log) |
| Separate native-TV regression subset | 32 passed | [tv-e2e-final.log](test-runs/tv-e2e-final.log) |
| Additional accepted-identity browser proof | One passed | [awards-canonical-current.log](test-runs/awards-canonical-current.log) |
| Additional same-person role/unknown-coverage browser proof | Two passed | [awards-role-pending-current.log](test-runs/awards-role-pending-current.log) |
| Standard/Arabic artwork capture | Two passed | [awards-artwork-current.log](test-runs/awards-artwork-current.log) |
| Offline bundle and package fixture checks | Nine passed | [bundle-packaging-current.log](test-runs/bundle-packaging-current.log) |
| Repeated concurrent fresh-store initialization | Twelve passed after fixing the schema/journal-mode race | Focused store test and recorded OS-temp audit |
| Isolated production compilation | Passed, 1,690 modules | Browser-run build output above |
| Scoped tracked diff whitespace check | Passed | No changed-scope whitespace errors |

The final full Python suite passes all 1,563 tests, including the source-independence guard and expanded real-bundle assertions. The previously recorded IPTV projection timing failure remains documented in [full-python-confirmed.log](test-runs/full-python-confirmed.log); its one-second assertion and production owner were not changed. The final run emits two ResourceWarnings for unclosed test file handles, without failing tests.

The three earlier browser geometry failures are fixed. The original 1920px 106×132 portrait and uniform-width assertions still pass. Following Dante's clarification, awards are tested inside the selected existing right-side control area rather than against an assumed separate 52px strip. Screenshot review exposed two-digit count clipping inherited from person-name styling; the added visibility assertion failed at 1920 and 1600 before the count style was corrected, then passed at all four sizes. The latest full browser suite passes, and the subsequently added single-Globe/late-portrait checks also pass in a separate focused run. This is not a claim that the full suite included the later-added case.

## Contract-by-contract result

“Pass” below refers to the stated isolated proof. Both historical organizations are now complete; live deployment remains a separate gate.

| Contract | Result and proof |
| --- | --- |
| A01 Counts/placement/rating preservation | Pass through the real API, existing card tests and selected-area placement checks; existing portraits remain unchanged. |
| A02 Zero/one/unknown pairs | Pass: Node suppression, rendered zero films, pending-Globe single Oscar pair and first-read failure. |
| A03 Gladiator distinct film awards | Pass: source fixture returns two categories rather than three recipients. |
| A04 Les Girls shared acting win | Pass: source fixture deduplicates the film and retains each eligible person's win. |
| A05 Multi-film personal wins/special subtypes | Pass: source, independent identity, store/API and real distinct-film pagination. |
| A06 Separate acting/directing for one person | Pass: same person renders three acting wins versus one directing win; director membership is film 3 only. |
| A07 Excluded domains/search cards | Pass: positive ID opt-out Node checks, rendered People/Keywords/IPTV exclusions, zero IPTV snapshot reads and separate TV regression suite. |
| A08 Accepted owned identity | Pass: raw movie 4 has zero awards; accepted movie 1 renders 12 Oscars and preserves its accepted description. Existing canonical card matrix also passes. |
| A09 Conflicting/missing/same-name identities | Pass: strict namespace/source-context identity tests and conflicting-ID cache checks. |
| A10 Idempotent import | Pass: same payload/seed preserves generation and totals. |
| A11 Atomic replacement/concurrency/crash | Pass: transaction rollback, lease expiry, concurrent claims and repeated concurrent fresh bootstrap. |
| A12 Incomplete winner evidence | Pass: no publication, last counts retained and next check seven days later. |
| A13 Ties/shared recipients | Pass: explicit annual ties, multiple winners, film/person aggregation and independent agreement. |
| A14 Unknown category/layout | Pass for fail-closed diagnostics; unknown or incomplete inputs remain unpublished; the bundled history now has no gaps. No unknown format is silently accepted. |
| A15 Month/cadence/independent organizations | Pass: fake-clock weekly/month-crossing, completed-year stop and independent publication tests. |
| A16 Missed years/offline/429/credentials | Pass for chronological catch-up, bounded failure, 429 cadence, cancellation and disabled test-mode external startup. Live provider availability is not a success claim. |
| A17 Awards without rating | Pass: real snapshot, visible awards and no invented collapsed star/rating. |
| A18 Long content/narrow geometry | Pass: all four desktop sizes preserve uniform portraits; two-digit pairs stay within the selected right-side area, below existing controls and clear of names/roles; counts are not clipped. |
| A19 Fixed credits/rail/portraits | Pass: fixed slots, ten credits, 16 tiles, 106×132 reference portraits and uniform compact widths; original relationship assertions remain intact. |
| A20 Arabic/delayed snapshot | Pass: same canonical totals and number-left order; expansion stays open during snapshot completion and localization. |
| A21 Keyboard/tooltips/no bubbling | Pass: exact button tooltip strings, Enter/Space, visible keyboard focus and one browser-history action. |
| A22 Exact personal winning-film membership | Pass: actor 100 → films 1/2; director 90 → film 2; person 100 as director → film 3; API and rendered cards agree. |
| A23 Deduplication/all pages | Pass: three personal wins yield two distinct films; all 120 fixture films are reachable through real pagination. |
| A24 Origin/history restoration | Pass: Library/Lists/AI/Explore/Pick/Browse origins, browser Back/Forward, restored expansion, original Filmography criteria and existing scroll regressions. |
| A25 Late responses | Pass: returning during a delayed awards response preserves the origin; existing stale relationship/search cases pass. |
| A26 Local awards unavailable | Pass: quiet first failure, last-good cache retention, regular details/rail remain usable and no render-time external awards sources. |
| A27 Changed page generation | Pass: real 409 followed by exactly one current-generation page-one retry. |
| A28 Uncached winning metadata | Pass: exact verified IDs/minimal facts retained; real awards GET tests forbid catalog initialization and provider fetches. |
| A29 Shared callers | Pass functionally for regular Home, Library, Lists, AI, Explore, Pick and Browse; selected-area appearance and existing controls regressions pass. |
| A30 Bundle/startup/package/preservation | Pass in isolation: reproducible seed bootstrap and fixture ZIP inclusion; automatic test-network startup disabled; TV suite passes and its preexisting screenshot bytes were restored. No production package or deployment was performed. |

## Artwork and preservation

Runtime assets are `static/movie-awards/oscar.png` (1020×1542 RGBA) and `golden_globe.png` (1067×1474 RGBA). Both have alpha spanning 0–255 with transparent corners and were inspected against the preserved icon references and actual CP dark cards. They were prepared using the built-in image-generation editor with the supplied gold outlines as references. Asset brief: retain the supplied silhouette, remove dark backgrounds, preserve transparent internal gaps, and render small gold icons without badge containers. Rejected filled/glowing edits were not installed; an additional crop request was rejected by the image tool. The supplied reference files remain unchanged.

Current snapshots are [collapsed-award-only.png](desktop/collapsed-award-only.png), [expanded-arabic.png](desktop/expanded-arabic.png), and expanded fixtures at 1600×1000, 1366×900 and 1366×768. The corrected layout is verified against the clarified placement and preserved portrait sizing. [person-single-globe.png](desktop/person-single-globe.png) shows the single-Globe position. Synthetic fixture portraits deliberately use neutral artwork; the actor photo itself is not edited.

The initial dirty checkout had 74 tracked modifications and 25 untracked entries. Recorded preexisting dirty-file hashes differ only in approved implementation/test/plan owners. All unrelated recorded files, including native-TV sources and verification PNGs, match their captured bytes. No worktree, delegation, commit, push, release, production package, live catalog/config mutation or application restart was performed by this implementation.

At the final live probe, port 5000 was owned by PID 24624 (Python 3.12 `app.py`, started 06:10:45). The served HTML and Desktop `dist/index.html` still have the initial SHA-256 `f6db43f83bc0875a98a70e5ad88bd48a007cdf56bb904d22eb5940e640a8d860`; the live awards API returns 404. The implementation is source-only and tested in isolation. No live-readiness claim is made.

## Completion boundary

The six approved implementation tasks, full historical seed, offline reproduction, selected-area layout and complete-path isolated acceptance are complete. No product contract differs from Dante's approved placement, counting, role, domain or navigation rules. The source-independence safeguard adds rejection coverage without accepting weaker evidence.

Live deployment, restart, commit, push, packaging and release are separate authorization boundaries. None was performed. The source result is ready for a separately authorized live installation. Shutdown remains canceled.
