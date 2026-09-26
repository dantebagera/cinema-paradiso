# Reconciliation ledger

Approval: Dante said "go" on 2026-09-18.

Source backup: `C:\Users\dante\.codex\backups\cp-tv-stabilization-20260918-183441`. Current-user and SYSTEM access only.

| Desktop change | Action |
| --- | --- |
| `app.py` | merged against common ancestor; Desktop and TV behavior retained |
| `docs/verification/more-like-this/desktop-1920x1080.png` | copied from verified Desktop backup; dependencies reconciled |
| `docs/verification/more-like-this/desktop-1920x720.png` | copied from verified Desktop backup; dependencies reconciled |
| `docs/verification/more-like-this/validation.md` | copied from verified Desktop backup; dependencies reconciled |
| `native/player/CMakeLists.txt` | copied from verified Desktop backup; dependencies reconciled |
| `native/player/qml/Main.qml` | copied from verified Desktop backup; dependencies reconciled |
| `native/player/resources/icons/audio-language-tracks.svg` | copied from verified Desktop backup; dependencies reconciled |
| `native/player/resources/icons/audio-tracks.svg` | Desktop deletion applied after dependency check |
| `native/player/resources/icons/window-maximize.svg` | Desktop deletion applied after dependency check |
| `native/player/resources/icons/window-restore.svg` | Desktop deletion applied after dependency check |
| `native/player/runtime-metadata.json` | copied from verified Desktop backup; dependencies reconciled |
| `services/catalog_repository.py` | copied from verified Desktop backup; dependencies reconciled |
| `services/catalog_store.py` | copied from verified Desktop backup; dependencies reconciled |
| `services/library_ingestion.py` | copied from verified Desktop backup; dependencies reconciled |
| `services/library_startup_catchup.py` | copied from verified Desktop backup; dependencies reconciled |
| `services/movie_relationships.py` | copied from verified Desktop backup; dependencies reconciled |
| `src/App.jsx` | merged against common ancestor; Desktop and TV behavior retained |
| `src/api/movieDetails.js` | copied from verified Desktop backup; dependencies reconciled |
| `src/api/movieRelationships.js` | copied from verified Desktop backup; dependencies reconciled |
| `src/components/MovieRelationshipNavigation.jsx` | copied from verified Desktop backup; dependencies reconciled |
| `src/components/RelatedMovieRail.jsx` | copied from verified Desktop backup; dependencies reconciled |
| `src/components/SharedMovieCards.jsx` | copied from verified Desktop backup; dependencies reconciled |
| `src/components/WorkspacePathBar.jsx` | copied from verified Desktop backup; dependencies reconciled |
| `src/components/movie-card/MovieCard.jsx` | merged against common ancestor; Desktop and TV behavior retained |
| `src/components/movie-card/expandedCardViewport.js` | copied from verified Desktop backup; dependencies reconciled |
| `src/components/movie-card/movieCard.css` | copied from verified Desktop backup; dependencies reconciled |
| `src/features/discover/DiscoverWorkspace.jsx` | copied from verified Desktop backup; dependencies reconciled |
| `src/features/library/LibraryWorkspace.jsx` | copied from verified Desktop backup; dependencies reconciled |
| `src/main.jsx` | copied from verified Desktop backup; dependencies reconciled |
| `src/styles.css` | copied from verified Desktop backup; dependencies reconciled |
| `src/styles/movieRelationships.css` | copied from verified Desktop backup; dependencies reconciled |
| `tests/e2e/app-smoke.spec.js` | merged against common ancestor; Desktop and TV behavior retained |
| `tests/e2e/caret-visibility.spec.js` | copied from verified Desktop backup; dependencies reconciled |
| `tests/e2e/movie-relationships.spec.js` | copied from verified Desktop backup; dependencies reconciled |
| `tests/movieDetails.test.mjs` | copied from verified Desktop backup; dependencies reconciled |
| `tests/movie_relationships.test.mjs` | copied from verified Desktop backup; dependencies reconciled |
| `tests/test_catalog_store.py` | copied from verified Desktop backup; dependencies reconciled |
| `tests/test_final_card_publication.py` | copied from verified Desktop backup; dependencies reconciled |
| `tests/test_library_ingestion_queue.py` | copied from verified Desktop backup; dependencies reconciled |
| `tests/test_library_startup_catchup.py` | copied from verified Desktop backup; dependencies reconciled |
| `tests/test_movie_relationships.py` | copied from verified Desktop backup; dependencies reconciled |
| `tests/test_native_player.py` | copied from verified Desktop backup; dependencies reconciled |
| `tests/test_tmdb_details_transform.py` | copied from verified Desktop backup; dependencies reconciled |

No configuration, live database, debug log, or media file is part of this reconciliation.

Baseline: Desktop focused regression 107 passed. Initial global-Python full-suite attempts were stopped after discovery delays; project-venv full baseline passed: 1,299 tests in 236.585 seconds. All 43 Desktop changes reconciled; four overlaps merged against HEAD, preserving TV additions. MovieCard uses Desktop child-event guard and layout centering plus TV navigation props. Source hashes rechecked before applying.


Runtime dependency: copied only the 1,361 manifest-listed files and the manifest/selector from Desktop's `0.1.34-qt6.10.3-mpv20260610-lgpl-cp2.8.5` player. Every source digest matched the manifest. Source metadata and runtime now agree; runtime-generated vendor directories were not copied.

Reconciliation corrections found by regression checks:

- Library request identity now ignores equivalent simple/advanced editor switches while keeping explicit refresh and catalog events functional.
- Complete canonical SQL movie details do not call TMDB again; incomplete/Plex-only details still use the restored richer-credit lookup. Related-movie requests remain independent.
- Two Python source assertions now reference the restored scroll helper and expanded-related-card argument. Their behavioral browser tests remain in place.
- The catalog-event browser check clicks the visible selection label instead of forcing a click through the decorative span on a moving native input. All selection/state assertions are unchanged.

Original Desktop source hashes were rechecked after implementation: no changes.
