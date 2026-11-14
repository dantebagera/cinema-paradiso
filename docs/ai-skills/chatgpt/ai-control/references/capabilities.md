# CP capability catalogue for the ChatGPT drafts

**Status:** Source inventory for review, 2026-10-24. This document does not register tools or grant execution permissions. CP has no ChatGPT integration yet.

The enabled runtime manifest must identify which operations are actually connected, their schemas, domains, prerequisites, and review requirements. Load only the relevant catalogue sections when needed. Do not inject this entire document into every recommendation request.

## Current AI Control exposure

`services/ai_control_capabilities.json` permits four actions: `find`, `create_list`, `download`, and `delete`. Its filters are title, year, size, genre, actor, director, resolution, and ownership. These are the existing Ollama-era capabilities, not proof of a ChatGPT tool connection.

`services/ai_control.py` owns interpretation, plan storage, selection validation, preview, and execution orchestration. `app.py` supplies catalogue, TMDB, list, deletion, and acquisition dependencies. The existing provider prompts remain unchanged by these draft documents.

## Discovery, recommendations, and information

**CP can:** Search movie titles; browse popular, trending, top-rated, now-playing, upcoming, and other existing feeds; use supported advanced-search combinations; retrieve details, credits, alternative titles, person filmographies, related films, collections, awards data, posters, translations where available, and trailers. Recommend movies through the existing Ollama path.

**Existing owners:** `app.py` TMDB/search/recommendation routes; `services/advanced_search.py`; `services/tmdb_advanced_search.py`; `services/movie_relationships.py`; `services/movie_awards_routes.py`; `services/youtube_playlist.py`.

**Important boundaries:** Available search criteria differ by surface. The shared advanced-search model includes writer, keyword, rating, language, country, runtime, and viewing/list criteria beyond AI Control v1. Actor and director roles are not interchangeable. Movie details and awards have their own provider evidence. Trailer playback and source search are distinct actions.

**Needs new ChatGPT support:** Provider connection, curator request/continuation state, and validated tools. Studio/company search, company/group membership, and studio filmography filtering are not implemented in the existing AI Control schema or shared advanced-search compiler. A factual franchise request needs a verified collection or another explicit, evidenced definition, not guessed membership.

## Lists, watched state, and release following

**CP can:** Inspect/create/rename/delete movie lists; add/remove movies; add movies in bulk; inspect list membership; manage watchlist and watched state; follow/unfollow movies; inspect/check followed releases; save/reset personal movie-collection overrides.

**Existing owners:** `services/curation_routes.py`; `services/curation_store.py`; `app.py` collection and followed-release routes; `services/movie_acquisition.py` release checking.

**Important boundaries:** Watched applies only to owned Library movies. Removing a list entry, deleting a list, unfollowing a release, and deleting a media file are different actions. Saved list membership is independent of local ownership. List creation must report confirmed persistence and actual saved membership. A release check can lead to acquisition work and is not automatically a read-only status query.

**AI exposure:** AI Control v1 can create a reviewed movie list. Editing lists, curation, following, and collection amendments need dedicated connections for ChatGPT.

## Library, files, and copying

**CP can:** Browse/search/filter local movies; inspect file and ownership facts; resolve selections across pages; inspect ingestion/reconciliation status; reconcile library changes; request Plex scans; inspect library statistics; preview/apply supported file renames and path corrections; copy selected movies to an export destination and inspect/cancel copy jobs.

**Existing owners:** `services/catalog_repository.py`; `services/canonical_catalog.py`; `services/library_ingestion.py`; `services/library_mutations.py`; `app.py` library, rename, path, Plex, and export-job routes.

**Important boundaries:** A scan or reconciliation may write catalogue data. Copy/export consumes storage and must retain the source. Destination, file selection, overwrite/conflict behavior, and cancellation effects come from the existing owner. Arbitrary filesystem commands are not a replacement for these operations.

**AI exposure:** AI Control v1 can find library movies and perform its reviewed file deletion. Other operations need dedicated connections.

## Metadata, identity, artwork, and maintenance

**CP can:** Inspect metadata health and authority; search/preview/apply TMDB or Plex matches; review smart matching and identity audits; pause/resume/cancel supported audit jobs; refresh metadata; inspect/save/remove supported overrides; select/upload/reset posters; inspect artwork jobs; inspect duplicate, storage, upgrade, and identity-maintenance results; preview/apply renames; perform supported deletion actions.

**Existing owners:** `app.py` metadata, smart-match, smart-rename, poster, artwork, and maintenance routes; `services/smart_match.py`; `services/identity_audit.py`; `services/identity_verification.py`; `services/maintenance_audit.py`; `services/media_assets.py`; `services/library_mutations.py`.

**Important boundaries:** Finding a probable duplicate is not permission to delete it. Metadata suggestions do not directly apply identity. Preserve preview/apply tokens, manual choices, root/file checks, active-use restrictions, and the owner's Recycle Bin policy. Migration, artwork cleanup, and backfill are explicit maintenance operations with different costs; they are not hidden side effects of answering a question.

**AI exposure:** AI Control v1 has reviewed movie deletion. Existing standalone AI matching is a separate feature. Other management actions need explicit tool connections.

## Movie acquisition and downloads

**CP can:** Search configured indexers; inspect source results and quality variants; prepare/review selected sources; submit validated movie downloads and upgrades; inspect jobs; finalize supported imports; follow release availability. The Downloads surface exposes the embedded qBittorrent WebUI and its controls.

**Existing owners:** `services/source_search.py`; `services/movie_acquisition.py`; `services/acquisition_decision.py`; `services/acquisition_profiles.py`; `services/qbittorrent.py`; `services/download_monitor.py`; `services/verified_import.py`; `app.py` source-review, submission, job, and finalize routes.

**Important boundaries:** Preserve configured indexer trust, torrent validation, identity, ownership/upgrade rules, quality selection, destination checks, and download/import state. Do not claim all qBittorrent WebUI actions are already CP AI tools. Pause/resume, priorities, queue changes, and removal with/without data require explicit supported bindings. qBittorrent owns active-download queue limits; a result count is not an active-transfer limit.

**AI exposure:** AI Control v1 can preview and confirm movie downloads through its existing source-review flow. Its default/direct policy is 1080p; a GPT request for another quality must not silently become 1080p. Quality support must come from the connected tool and reviewed source choices.

## TV discovery, library, lists, and playback

**CP can:** Discover/search series; inspect series, seasons, episodes, related shows, and supported translations; add/refresh series; inspect files, coverage, and inventory; run supported discovery/scans; review/approve assignments; manage maintenance exclusions, lists, watchlist/watched state, posters, and Continue Watching; launch episode playback and manage supported progress state.

**Existing owners:** `services/tv_routes.py`; `services/tv_metadata.py`; `services/tv_catalog_repository.py`; `services/tv_read_model.py`; `services/tv_library_discovery.py`; `services/tv_ingestion.py`; `services/tv_playback.py`.

**Important boundaries:** Native TV must be enabled and configured. Series, season, episode, local file, and online preview identities differ. Series watched state must follow TV's existing semantics. Approval of a discovered folder and scanning it are separate operations.

**AI exposure:** Not exposed by the four movie-oriented AI Control v1 actions. Use dedicated TV connections rather than sending TV identities through movie operations.

## TV acquisition, monitoring, tasks, and bulk actions

**CP can:** Search episodes, missing episodes, upgrades, and season releases; prepare releases; submit single/batch acquisitions; inspect acquisition state; retry/cancel/block/rollback supported acquisitions; choose an import home; configure monitoring; preview/save/start/finish-season/cancel tasks; preview and perform supported bulk downloads/deletions; inspect bulk history.

**Existing owners:** `services/tv_routes.py`; `services/tv_acquisition.py`; `services/tv_monitoring.py`; `services/tv_bulk_actions.py`; shared acquisition/profile/store owners.

**Important boundaries:** Preserve episode identity, season-pack handling, profile rules, metadata-completeness gates, decision tokens, explicit extras/partial-batch choices, import checks, task cancellation modes, active-use protections, and existing bulk limits. A saved monitoring task can cause future downloads; its future scope must be visible before confirmation.

**AI exposure:** Requires dedicated ChatGPT connections and scenario coverage; existing TV functionality alone does not make it callable from AI Control.

## Player and subtitles

**CP can:** Launch/resume/restart supported local playback; inspect runtime/status; inspect/clear Continue Watching; use catalogue-owned playlists; select tracks and preferences through existing player controls; search/download/save subtitles through the existing player session; manage configured player preferences.

**Existing owners:** `services/player_routes.py`; `services/player_catalog.py`; `services/player_manager.py`; `services/player_protocol.py`; `services/player_queue.py`; `services/playback_history.py`; `services/subtitle_service.py`; `native/player/` UI.

**Important boundaries:** Launch uses a validated library identity, not an arbitrary path from the model. Player UI and session capabilities are not automatically external AI controls. In particular, this inventory does not establish a ready-made AI play/pause/seek/volume bridge. Track/subtitle selection and file saving must use the active validated session and supported messages.

**AI exposure:** Dedicated bindings are required. Do not promise remote player controls merely because a button exists in the player.

## IPTV providers, content, lists, and playback

**CP can:** Add/edit/remove/select/test/sync providers; inspect status, categories, channels, movies, series, programme guides, and source details; browse supported filters; manage provider-local favorites, lists, list membership/order, and history; inspect recent items; start/stop supported playback sessions.

**Existing owners:** `services/iptv_routes.py`; `services/iptv_provider_manager.py`; `services/iptv_service.py`; `services/iptv_store.py`; `services/iptv_xtream.py`.

**Important boundaries:** Provider identity is required throughout. IPTV availability is not local ownership. IPTV lists are not local Movie or TV lists. Provider removal, sync, playback, and history changes are different operations. Provider credentials and stream URLs must not be exposed to the model as a shortcut.

**AI exposure:** Requires provider-scoped ChatGPT tools; none is implied by movie AI Control v1.

## IPTV metadata and review

**CP can:** Inspect metadata/review queues; preview/apply classification; start/inspect/cancel/apply supported matching jobs; search/apply/remove manual matches; prioritize items; start/pause/resume/cancel enrichment; retry failures/re-evaluate stale records; preview/apply/cancel supported rebuilds; preview/apply fusion; retry projection work; retrieve supported localized metadata.

**Existing owners:** `services/iptv_routes.py`; `services/iptv_movie_service.py`; `services/iptv_movie_classifier.py`; `services/iptv_movie_store.py`; `services/iptv_metadata_settings.py`; `services/iptv_enrichment_worker.py`; `services/iptv_tmdb.py`.

**Important boundaries:** Keep provider-scoped validation and consent. AI can propose classifications or rank real candidates; it must not invent or directly force identities. The existing IPTV Ollama configuration is separate and restricts the endpoint to localhost. A future cloud provider requires an explicit data-sharing design; it is not enabled by changing this skill.

## Settings, diagnostics, notifications, and lifecycle

**CP can:** Configure supported libraries/data locations and integrations (Plex, Prowlarr, TMDB, YouTube, qBittorrent, streaming templates, IPTV, Ollama); configure player and acquisition preferences/profiles; inspect service/startup status and diagnostics; test integrations; run supported runtime maintenance; inspect/read notifications; request existing CP/device shutdown or restart actions and manage their after-download coordination.

**Existing owners:** `app.py` configuration, startup, integration, qBittorrent-update, and power routes; `services/acquisition_routes.py`; `services/player_config.py`; `services/power_actions.py`; `services/tv_routes.py` notification routes; `src/features/help/HelpWorkspace.jsx` for product help.

**Important boundaries:** Public/redacted configuration must be distinguished from secrets. Some tests generate a model response or contact an external service. Updates, data relocation, migrations, provider removal, and shutdown/restart have distinct effects and must retain their dedicated review/authorization flow. Helping someone find a setting does not authorize changing it. A notification read-state change is a small write, not a media-management action.

**AI exposure:** Requires explicit connections and per-operation permissions. The skill is not an administrator shell and does not grant blanket access to every API route.
