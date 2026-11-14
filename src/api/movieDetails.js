import { fetchJson } from './client.js';
import { observeCatalogGeneration } from './library.js';
import { movieDisplayTitle } from '../utils/movieLanguage.js';

function ownedPath(movie, owned) {
  return String(owned?.path || owned?.library_item?.path || owned?.canonical_card?.path || '').trim();
}

export function movieDetailsCacheKey(movie, owned = null) {
  const path = ownedPath(movie, owned);
  if (path) return `owned:${path.toLowerCase()}`;
  const tmdbId = String(movie?.tmdb_id || '').trim();
  return tmdbId ? `tmdb:${tmdbId}` : '';
}

export function markMovieDetailsCacheStale(cache = {}) {
  return Object.fromEntries(
    Object.entries(cache).map(([key, details]) => [
      key,
      details && typeof details === 'object' ? { ...details, stale: true } : details
    ])
  );
}

export function mergeCanonicalMovieDetails(summary = {}, details = {}) {
  const merged = { ...(summary || {}), ...(details || {}) };
  const textFields = [
    'title', 'year', 'tmdb_id', 'imdb_id', 'plex_guid', 'poster_url', 'backdrop_url',
    'plot', 'summary', 'rating', 'language', 'country', 'country_flag', 'release_date', 'original_title', 'original_language'
  ];
  textFields.forEach((field) => {
    if ((merged[field] === '' || merged[field] == null) && summary?.[field] != null) {
      merged[field] = summary[field];
    }
  });
  if (!merged.genres?.length && summary?.genres?.length) merged.genres = summary.genres;
  if (!merged.cast?.length && summary?.cast?.length) merged.cast = summary.cast;
  if (!merged.directors?.length && summary?.directors?.length) merged.directors = summary.directors;
  if (!merged.collection?.id && summary?.collection?.id) merged.collection = summary.collection;
  return merged;
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

function creditQuality(people = []) {
  return people.reduce((score, person) => (
    score + 100
    + (person?.id ? 20 : 0)
    + (person?.profile_url ? 20 : 0)
    + (person?.character ? 5 : 0)
  ), 0);
}

function richerCredits(localCredits = [], providerCredits = []) {
  return creditQuality(providerCredits) > creditQuality(localCredits)
    ? providerCredits
    : localCredits;
}

export function mergeLibraryProviderDetails(localDetails = {}, providerDetails = {}) {
  const merged = mergeCanonicalMovieDetails(providerDetails, localDetails);
  merged.cast = richerCredits(localDetails.cast, providerDetails.cast);
  merged.directors = richerCredits(localDetails.directors, providerDetails.directors);
  merged.writers = richerCredits(localDetails.writers, providerDetails.writers);
  merged.director = merged.directors[0] || localDetails.director || providerDetails.director || null;
  if (!merged.keywords?.length && providerDetails.keywords?.length) merged.keywords = providerDetails.keywords;
  if (!merged.collection?.id && providerDetails.collection?.id) merged.collection = providerDetails.collection;
  ['certification', 'runtime', 'tagline', 'trailer_url'].forEach((field) => {
    if ((merged[field] === '' || merged[field] == null) && providerDetails[field] != null) {
      merged[field] = providerDetails[field];
    }
  });
  merged.detail_source = 'library_sql+tmdb_live';
  return merged;
}

function ownedTmdbId(movie, owned) {
  return String(
    movie?.tmdb_id
    || owned?.tmdb_id
    || owned?.canonical_metadata?.tmdb_id
    || owned?.library_item?.canonical_metadata?.tmdb_id
    || owned?.canonical_card?.canonical_metadata?.tmdb_id
    || ''
  ).trim();
}

function comparableTitle(value) {
  return String(value || '').normalize('NFKC').trim().toLocaleLowerCase();
}

async function resolveProviderDetails(movie, localDetails, tmdbId = '') {
  if (tmdbId) return fetchJson(`/api/tmdb/details?tmdb_id=${encodeURIComponent(tmdbId)}`);
  const title = String(localDetails?.title || movie?.title || '').trim();
  const year = String(localDetails?.year || movie?.year || '').trim();
  if (!title) return null;
  const query = [title, year].filter(Boolean).join(' ');
  const search = await fetchJson(`/api/tmdb/search?q=${encodeURIComponent(query)}&page=1&include_adult=false`);
  const match = (search.results || []).find((candidate) => (
    comparableTitle(candidate?.title) === comparableTitle(title)
    && (!year || String(candidate?.year || '') === year)
  ));
  const resolvedId = String(match?.tmdb_id || '').trim();
  if (!resolvedId) return null;
  return fetchJson(`/api/tmdb/details?tmdb_id=${encodeURIComponent(resolvedId)}`);
}

export async function fetchCanonicalMovieDetails(movie, owned = null) {
  const path = ownedPath(movie, owned);
  if (path) {
    const hintedTmdbId = ownedTmdbId(movie, owned);
    const response = await fetchJson(`/api/library/details?path=${encodeURIComponent(path)}`);
    const localDetails = normalizeLibraryMovieDetails(response);
    if (localDetails.projection_contract === 'canonical_movie_details' && Array.isArray(localDetails.deferred_fields) && !localDetails.deferred_fields.length) return localDetails;
    const tmdbId = hintedTmdbId || String(localDetails.tmdb_id || '').trim();
    try {
      const providerDetails = await resolveProviderDetails(movie, localDetails, tmdbId);
      return providerDetails
        ? mergeLibraryProviderDetails(localDetails, providerDetails)
        : localDetails;
    } catch {
      return localDetails;
    }
  }
  const tmdbId = String(movie?.tmdb_id || '').trim();
  if (!tmdbId) return null;
  return {
    ...await fetchJson(`/api/tmdb/details?tmdb_id=${encodeURIComponent(tmdbId)}`),
    detail_source: 'tmdb_live'
  };
}

const languageCache = new Map();
const pendingLanguages = new Map();
const LANGUAGE_CACHE_TTL = 30 * 60 * 1000;

export function cachedMovieLanguage(tmdbId, language = 'ar-SA') {
  const key = `${tmdbId}:${language}`;
  const entry = languageCache.get(key);
  if (entry && Date.now() - entry.time < LANGUAGE_CACHE_TTL) return entry.data;
  languageCache.delete(key);
  return null;
}

export async function fetchTransientMovieLanguage(tmdbId, language = 'ar-SA') {
  const id = String(tmdbId || '').trim();
  if (!id) throw new Error('A TMDB ID is required for language display.');
  const cached = cachedMovieLanguage(id, language);
  if (cached) return cached;
  const key = `${id}:${language}`;
  if (pendingLanguages.has(key)) return pendingLanguages.get(key);
  const pending = fetchJson(
    `/api/tmdb/details?tmdb_id=${encodeURIComponent(id)}&language=${encodeURIComponent(language)}`
  ).then(data => {
    languageCache.set(key, { time: Date.now(), data });
    while (languageCache.size > 128) languageCache.delete(languageCache.keys().next().value);
    return data;
  }).finally(() => pendingLanguages.delete(key));
  pendingLanguages.set(key, pending);
  return pending;
}

function firstPlotText(...values) {
  return values.find(value => typeof value === 'string' && value.trim()) || '';
}

export function mergeTransientMovieLanguage(movie, details, localized) {
  const moviePlot = firstPlotText(movie?.summary, movie?.plot);
  const englishPlot = moviePlot || firstPlotText(details?.summary, details?.plot);
  const displayMovie = englishPlot && !firstPlotText(movie?.summary || movie?.plot)
    ? { ...(movie || {}), summary: englishPlot, plot: englishPlot }
    : movie;
  if (!localized) return { displayMovie, displayDetails: details };
  const overlay = (base) => {
    const result = { ...(base || {}) };
    for (const field of ['title', 'tagline', 'language', 'country']) {
      if (typeof localized[field] === 'string' && localized[field].trim()) result[field] = localized[field];
    }
    result.title = movieDisplayTitle(movie, details, localized);
    result.plot = result.summary = firstPlotText(localized.summary, localized.plot) || englishPlot;
    const protectedArtwork = movie?.accepted || details?.accepted || movie?.poster_override || details?.poster_override
      || movie?.poster_override_locked || details?.poster_override_locked || movie?.poster_url?.startsWith('/api/assets/');
    if (!protectedArtwork) {
      for (const field of ['poster_url', 'backdrop_url']) {
        if (localized[field]) result[field] = localized[field];
      }
    }
    for (const field of ['genres', 'keywords']) {
      if (localized[field]?.length) result[field] = localized[field];
    }
    for (const field of ['cast', 'directors', 'writers']) {
      const people = base?.[field]?.length ? base[field] : details?.[field];
      if (people?.length) result[field] = people.map(person => {
        const translated = localized[field]?.find(other => person.id && String(other.id) === String(person.id));
        return translated ? { ...person, name: translated.name || person.name, character: translated.character || person.character } : person;
      });
      else if (localized[field]?.length) result[field] = localized[field];
    }
    if (base?.collection?.id && String(base.collection.id) === String(localized.collection?.id) && localized.collection?.name) {
      result.collection = { ...base.collection, name: localized.collection.name };
    }
    if (result.directors?.length) result.director = result.directors[0];
    return result;
  };
  return {
    displayMovie: overlay(displayMovie),
    displayDetails: overlay(details)
  };
}

export function movieCollectionUrl(details) {
  const collectionId = details?.collection?.id;
  if (!collectionId) return '';
  const route = details.detail_source === 'library_sql' ? '/api/library/collection/' : '/api/tmdb/collection?collection_id=';
  return `${route}${encodeURIComponent(collectionId)}`;
}

export function movieCollectionSource(details) {
  return details?.detail_source === 'library_sql' ? 'library' : 'tmdb';
}

export function movieCollectionCacheKey(details) {
  const collectionId = String(details?.collection?.id || '').trim();
  if (!collectionId) return '';
  return `${movieCollectionSource(details)}:${collectionId}`;
}

export function movieCollectionView(cache = {}, details = null) {
  const collection = details?.collection || {};
  const cacheKey = movieCollectionCacheKey(details);
  const cached = cacheKey ? cache[cacheKey] : null;
  const hasCompleteInlineData = Array.isArray(collection.parts) || Number.isFinite(collection.owned_count);
  return {
    cacheKey,
    status: cached?.status || (hasCompleteInlineData ? 'loaded' : collection.id ? 'idle' : 'empty'),
    data: cached?.data || collection,
    error: cached?.error || ''
  };
}
