import { fetchJson } from './client.js';

const USER_LISTS_CACHE_TTL = 1000;
let userListsCache = { data: null, time: 0, promise: null };
let userListsCacheVersion = 0;

export function clearUserListsCache() {
  userListsCacheVersion += 1;
  userListsCache = { data: null, time: 0, promise: null };
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
  userListsCache.promise = fetchJson('/api/user/lists')
    .then((data) => {
      if (cacheVersion !== userListsCacheVersion) {
        return userListsCache.promise || userListsCache.data || data;
      }
      userListsCache = { data, time: Date.now(), promise: null };
      return data;
    })
    .catch((error) => {
      if (cacheVersion === userListsCacheVersion) userListsCache.promise = null;
      throw error;
    });
  return userListsCache.promise;
}

async function addMoviePayloadsIndividually(listId, movies) {
  for (const movie of movies || []) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie })
    });
  }
}

export async function addMoviePayloadsToList(listId, movies) {
  try {
    return await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies/bulk`, {
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
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('cp-curation-changed'));
  }
}
