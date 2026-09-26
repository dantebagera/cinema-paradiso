import { fetchJson } from './client.js';

const pages = new Map();
const TTL = 15 * 60 * 1000;

export function mergeRelationshipMovies(recommended, similar = []) {
  const seen = new Set();
  return [...recommended, ...similar].filter((movie) => {
    const id = String(movie.tmdb_id || '');
    if (!id || seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

function fetchTypedRelationshipPage(mediaType, id, source, page, pageSize = null) {
  const key = `${mediaType}:${id}:${source}:${page}:${pageSize || ''}`;
  const cached = pages.get(key);
  if (cached && cached.expires > Date.now()) return cached.promise;
  const endpoint = mediaType === 'tv' ? '/api/tv/related' : '/api/tmdb/related';
  const sizeQuery = pageSize == null ? '' : `&page_size=${encodeURIComponent(pageSize)}`;
  const promise = fetchJson(`${endpoint}?tmdb_id=${encodeURIComponent(id)}&source=${source}&page=${page}${sizeQuery}`)
    .catch((error) => { pages.delete(key); throw error; });
  pages.set(key, { promise, expires: Date.now() + TTL });
  if (pages.size > 256) pages.delete(pages.keys().next().value);
  return promise;
}

export function fetchRelationshipPage(movieId, source = 'recommendations', page = 1) {
  return fetchTypedRelationshipPage('movie', movieId, source, page);
}

export function fetchTvRelationshipPage(seriesId, source = 'recommendations', page = 1, pageSize = null) {
  return fetchTypedRelationshipPage('tv', seriesId, source, page, pageSize);
}
