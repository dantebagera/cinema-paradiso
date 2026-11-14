# Arabic movie card defaults

**Status:** Approved for implementation, 2026-11-14. Dante requested Arabic movie cards in Arabic on all CP pages, then said “go”. Full available display metadata defaults to Arabic with English accessible through the existing toggle. No restart, catalog migration, commit or push is authorized here.

## Problem and decision
The shared Movie language hook resets to English on close. Discover/search and compact SQL Library projections drop original titles/languages. Home uses separate cards without the language hook. IPTV already provides Arabic defaults.
Scope: Movie Library, Discover/indexer, Lists/Following, Home, related and collection results, Maintenance cards. TV language behavior and canonical movie identity stay unchanged. Missing translations retain available source text. No GPT translation or new setting. No open product decisions.

## Contracts affected and contract-change decision
| Contract and source | Agreed behavior | Callers | Proposed behavior | Changes contract? | Decision |
| --- | --- | --- | --- | --- | --- |
| Dante's Arabic defaults request | Arabic movies display Arabic by default | All Movie cards | Original Arabic title immediately; localized details on expansion | Explicitly requested | “go”, 2026-11-14 |
| Catalog identity and actions | Accepted IDs, paths, artwork, source selection remain authoritative | Movie actions | Display-only text overlay | No | Preserve |
| Existing language toggle and IPTV defaults | English accessible; IPTV already defaults Arabic | Expanded cards | Reuse existing control; preserve IPTV | No | Preserve |
| TV separation | Existing TV language behavior | TV callers | Unchanged | No | Preserve |

## Current design and ownership
Worktree youtube-movie-stream, detached 117526b, substantial pre-existing dirty work (including installed YouTube feature). Relevant files match desktop baseline. Live desktop PID 24204, served index-BIL_deZ4.js, data owned by desktop configuration. New source is isolated until installed; no live claims from tests.
- app.py normalizes provider summaries; canonical_catalog.py projects saved Library snapshots; playback_history.py supplies Continue Watching.
- movieDetails.js owns transient language requests and overlays; MovieLanguageToggle.jsx owns selection; SharedMovieCards covers standard surfaces and DiscoverWorkspace its indexer variant.
- HomeWorkspace and RelatedMovieRail reuse the same pure display selection for their small tiles, and Home inspector reuses the shared language hook/control. No duplicate language rules.

## Exact behavior contract
### Frontend
Original language ar (or legacy explicit Arabic language metadata) defaults Arabic. A known non-Arabic original language takes precedence over fallback labels. Use existing Arabic original title/saved display text immediately. Fetch missing localized details only on expanded cards with a TMDB ID, deduplicate requests and bound the session cache. A failed request leaves available text and permits retry. English toggle is immediate, remains selected across collapse/reopen of the same mounted card, and resets for a new movie. Old replies cannot affect another movie. Text overlays cannot replace IDs, paths, canonical source, poster overrides, ratings or collection membership. Existing layouts and controls remain; Home inspector gains the existing language control in its actions row. Arabic text uses existing browser text layout, with direction auto where required.
### Backend
Keep English canonical metadata and existing routes. Carry original_title/original_language through existing movie summary, saved-card and playback projections. Read existing provider snapshot JSON; no schema migration or live catalog writes. Preserve optional original fields in curated entries. Older entries without Arabic metadata retain known text until normal enrichment provides it. No automatic translation of foreign movies.

## Implementation sequence
1. Add regression tests for original fields, display overlays and language defaults; watch failures.
2. Correct existing projections, central display helper/request cache/hook, and alternate Movie surfaces. Preserve action payloads.
3. Run focused and broader relevant tests; build and verify rendered desktop cards and English switching. Fresh-context review of incremental changes, then report installation boundary.

## Acceptance matrix
| Scenario | Action | Expected | Owner | Evidence |
| --- | --- | --- | --- | --- |
| Arabic provider movie | Browse Discover | Arabic original title, no translation request while collapsed | Summary/helper | API + desktop |
| Arabic Library snapshot | Read compact and detail projections | Original fields retained; identity unchanged | SQL catalog | Python |
| Arabic card | Expand, toggle English, collapse/reopen | Arabic details initially; English choice honored | Hook | Desktop |
| Missing/failed Arabic | Expand | Existing text retained, error visible and retry possible | API/hook | Node + desktop |
| Concurrent cards / late reply | Expand same ID / change ID | Deduped request; no stale overwrite | API/hook | Node + desktop |
| Foreign movie / TV | Browse/expand | Existing defaults unchanged | Hook/helper | Node + existing regressions |
| Home/Lists/related/maintenance | Browse Arabic fixture | Shared Arabic title rule | Callers | Desktop + source audit |
| Translation includes conflicting identity/artwork | Merge | Only display text changes | Merge owner | Node |
| IPTV | Existing Arabic locale flow | Existing provider-owned Arabic behavior remains | IPTV | Existing tests |

## Verification and rollout
Baseline: prior broad suite had two source-literal failures in test_iptv_movie_ui and test_trailer_modal_ui, documented in YouTube report; no weakening those assertions. New task baseline snapshot recorded in verification/arabic-movie-cards-2026-11-14/baseline.json.
Focused: node --test tests/movieDetails.test.mjs tests/movieLanguage.test.mjs; Python test_arabic_movie_cards and canonical/playback regressions in disposable CP_TEST_ROOT.
Broader: relevant details, discovery, curated lists, IPTV language and desktop regressions. Build via npm run build; Playwright desktop 1600x1000 against disposable server. No mobile work. Record counts and failures in verification report.
Live: installation/restart boundary reported separately; preserve baseline backups and feature-only delta for later installation. Compare exact requested Arabic defaults, English toggle, identity and TV/IPTV invariants before claiming completion.

## Execution ledger
Investigation complete; authoritative owners identified. Baseline preserved. Implementation approved.

Implementation: original fields retained by existing projections; shared display/helper and Movie hook cover standard cards, Home, related rails and list picker. Plex-selected Library rows obtain original-language identity metadata from their matching saved TMDB snapshot; Plex artwork remains selected. No catalog migration.
Verification: new backend projection tests reproduced missing fields before fixes; overlay and cache tests reproduced identity replacement and duplicate requests before fixes. Node full suite 170/170 passed. Initial six desktop scenarios and real CP route/render integration passed, with Lists and Continue Watching coverage added afterward.
Final review: independent reviewer found English blocked during automatic Arabic loading. Gated desktop regression failed before correction; the Movie control now permits immediate English while the TV loading state remains unchanged. No minor or declined-to-judge findings.

Final verification: 144 Python passes; 170 Node passes; 77 desktop passes with one confirmed baseline label assertion failure; one real CP API/render integration pass. All eight new Arabic desktop cases pass, including the review correction (RED → GREEN). Production build passes. Final review clean after the single fix pass; no deferred minors, additional product rulings or contract changes. Implementation is worktree-only, not installed or live.
