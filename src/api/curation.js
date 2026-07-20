import { fetchJson } from './client.js';

export const CURATION_GENERATION_CHANGED_EVENT = 'cp-curation-generation-changed';
const USER_LISTS_CACHE_TTL = 1000;
let userListsCache = { data: null, time: 0, promise: null };
let userListsCacheVersion = 0;
let currentCurationGeneration = null;

export function clearUserListsCache() {
  userListsCacheVersion += 1;
  userListsCache = { data: null, time: 0, promise: null };
}

export function observeCurationGeneration(generation) {
  const nextGeneration = Number(generation);
  if (!Number.isFinite(nextGeneration)) return false;
  const previousGeneration = currentCurationGeneration;
  if (previousGeneration !== null && nextGeneration < previousGeneration) return false;
  currentCurationGeneration = nextGeneration;
  if (previousGeneration === null || previousGeneration === nextGeneration) return false;
  clearUserListsCache();
  if (typeof window !== 'undefined') {
    const detail = { previousGeneration, generation: nextGeneration };
    window.dispatchEvent(new CustomEvent(CURATION_GENERATION_CHANGED_EVENT, { detail }));
    window.dispatchEvent(new CustomEvent('cp-curation-changed', { detail }));
  }
  return true;
}

export async function fetchCurationJson(url, options) {
  const data = await fetchJson(url, options);
  observeCurationGeneration(data?.curation_generation);
  return data;
}

export async function fetchUserListsCached(options = {}) {
  const force = Boolean(options?.force);
  const now = Date.now();
  if (!force && userListsCache.data && now - userListsCache.time < USER_LISTS_CACHE_TTL) {
    return userListsCache.data;
  }
  if (!force && userListsCache.promise) return userListsCache.promise;
  if (force) clearUserListsCache();

  const cacheVersion = userListsCacheVersion;
  const requestPromise = fetchCurationJson('/api/user/lists')
    .then((data) => {
      if (cacheVersion === userListsCacheVersion) {
        userListsCache = { data, time: Date.now(), promise: null };
      }
      return data;
    })
    .catch((error) => {
      if (cacheVersion === userListsCacheVersion && userListsCache.promise === requestPromise) {
        userListsCache.promise = null;
      }
      throw error;
    });
  userListsCache.promise = requestPromise;
  return requestPromise;
}

async function addMoviePayloadsIndividually(listId, movies) {
  for (const movie of movies || []) {
    await fetchCurationJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie })
    });
  }
}

export async function addMoviePayloadsToList(listId, movies) {
  try {
    return await fetchCurationJson(`/api/user/lists/${encodeURIComponent(listId)}/movies/bulk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movies })
    });
  } catch (bulkError) {
    if (bulkError.status !== 404) throw bulkError;
    await addMoviePayloadsIndividually(listId, movies);
    return { fallback: 'individual' };
  }
}

export function announceCurationChanged() {
  clearUserListsCache();
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('cp-curation-changed'));
  }
}
