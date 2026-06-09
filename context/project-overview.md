# Cinema Paradiso Project Overview

## Overview

Cinema Paradiso is a local-first movie archive command console for Windows users who manage large Plex/local movie libraries. It combines offline file management, Plex metadata checks, TMDB discovery, Prowlarr source search, live streaming actions, and local Ollama recommendations in one private web app.

## Goals

1. Make large local movie libraries easier to browse, clean, and trust.
2. Keep risky file operations explicit, controlled, and recoverable.
3. Separate offline library work from online discovery while keeping archive-aware actions available everywhere.
4. Preserve local-first privacy: user data, settings, and cache stay on the user's machine.

## Core User Flow

1. User configures one or more movie library folders in Settings.
2. User optionally configures Plex, Prowlarr, TMDB, and Ollama.
3. User opens Home to review library health, release watchlist alerts, and trending movies.
4. User uses Library Movie View to choose what to watch or File View to manage local files.
5. User uses Cleanup to review duplicates, smart-clean recommendations, low-quality files, and Plex-unmatched files.
6. User uses Discover to explore TMDB, browse indexers, stream, find sources, or ask Ollama for recommendations.

## Features

### Offline Library

- Movie View and File View.
- Local search, filters, sorting, and 40-item pagination.
- Play local files, rename files, delete to Recycle Bin, and find sources/upgrades.
- Plex metadata enrichment for title, year, genres, plot, rating, country, language, director, cast, poster, and TMDB id.

### Cleanup

- Duplicate groups.
- Smart Clean delete recommendations.
- Low-quality file review.
- Plex-unmatched fixes, including rename, fix path, Plex match search, and match apply.

### Online Discovery

- TMDB lists, genre filters, and search.
- Prowlarr latest/indexer browsing and manual torrent search.
- Live streaming through TMDB IMDb id lookup.
- Pick My Movie via local Ollama, enriched with TMDB.

### User Curation

- User-created lists.
- User-edited TMDB collections with reset-to-TMDB behavior.
- Backend-backed followed release watchlist with proper WEB/Blu-ray availability checks.

## Scope

### In Scope

- Local Windows movie library management.
- Plex metadata integration.
- TMDB discovery and metadata enrichment.
- Prowlarr source search.
- Ollama local AI recommendations.
- React/Vite UI served by Flask.

### Out of Scope

- Cloud accounts or hosted storage.
- Automatic downloading.
- Automatic destructive cleanup.
- The paused `winapp/` desktop packaging project.

## Success Criteria

1. A user can browse thousands of files without the UI becoming unmanageable.
2. A user can clean files only through explicit, confirmable actions.
3. A user can discover a movie and immediately know whether it is owned, streamable, or source-searchable.
4. A user can maintain lists, edited collections, and followed releases without losing them to cache cleanup.
