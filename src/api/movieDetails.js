import { fetchJson } from './client.js';
import { observeCatalogGeneration } from './library.js';

function ownedPath(movie, owned) {
  return String(owned?.path || owned?.library_item?.path || owned?.canonical_card?.path || '').trim();
}

export function movieDetailsCacheKey(movie, owned = null) {
  const path = ownedPath(movie, owned);
  if (path) return `owned:${path.toLowerCase()}`;
  const tmdbId = String(movie?.tmdb_id || '').trim();
  return tmdbId ? `tmdb:${tmdbId}` : '';
}

export function normalizeLibraryMovieDetails(response) {
  const item = response?.item || {};
  const canonical = item.canonical_metadata || {};
  const cast = canonical.cast?.length ? canonical.cast : item.plex_cast || [];
  const directors = canonical.directors?.length ? canonical.directors : item.plex_directors || [];
  return {
    ...canonical,
    summary: canonical.summary || canonical.plot || item.plex_summary || '',
    plot: canonical.plot || canonical.summary || item.plex_summary || '',
    cast,
    directors,
    director: directors[0] || null,
    genres: canonical.genres?.length ? canonical.genres : item.plex_genres || [],
    collection: canonical.collection || {},
    trailer_url: canonical.trailer_url || '',
    catalog_generation: response?.catalog_generation,
    catalog_generation_changed: observeCatalogGeneration(response?.catalog_generation),
    detail_source: 'library_sql'
  };
}

export async function fetchCanonicalMovieDetails(movie, owned = null) {
  const path = ownedPath(movie, owned);
  if (path) {
    const response = await fetchJson(`/api/library/details?path=${encodeURIComponent(path)}`);
    return normalizeLibraryMovieDetails(response);
  }
  const tmdbId = String(movie?.tmdb_id || '').trim();
  if (!tmdbId) return null;
  return {
    ...await fetchJson(`/api/tmdb/details?tmdb_id=${encodeURIComponent(tmdbId)}`),
    detail_source: 'tmdb_live'
  };
}

export function movieCollectionUrl(details) {
  const collectionId = details?.collection?.id;
  if (!collectionId) return '';
  const route = details.detail_source === 'library_sql' ? '/api/library/collection/' : '/api/tmdb/collection?collection_id=';
  return `${route}${encodeURIComponent(collectionId)}`;
}
