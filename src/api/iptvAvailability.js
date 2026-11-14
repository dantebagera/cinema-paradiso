import { fetchJson } from './client.js';

function waitForSubscriber(promise, signal) {
  if (!signal) return promise;
  if (signal.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  return new Promise((resolve, reject) => {
    const abort = () => reject(new DOMException('Aborted', 'AbortError'));
    signal.addEventListener('abort', abort, { once: true });
    promise.then(resolve, reject).finally(() => signal.removeEventListener('abort', abort));
  });
}

export function createMovieAvailabilityClient(request, now = Date.now) {
  const cache = new Map();
  const pending = new Map();
  let generation = 0;

  function invalidate() {
    generation++;
    cache.clear();
    pending.clear();
  }

  function batch(ids, force) {
    const key = ids.join(',');
    if (!force) {
      for (const entry of cache.values()) {
        if (now() - entry.time < 15000 && ids.every(id => entry.ids.includes(id))) {
          return Promise.resolve(entry.data);
        }
      }
    }
    if (pending.has(key)) return pending.get(key);
    const startedGeneration = generation;
    const promise = Promise.resolve(request(ids)).then(data => {
      if (generation === startedGeneration) {
        cache.set(key, { ids, data, time: now() });
        let size = [...cache.values()].reduce((sum, entry) => sum + entry.ids.length, 0);
        while (size > 500) {
          const oldest = cache.keys().next().value;
          size -= cache.get(oldest).ids.length;
          cache.delete(oldest);
        }
      }
      return data;
    }).finally(() => {
      if (pending.get(key) === promise) pending.delete(key);
    });
    pending.set(key, promise);
    return promise;
  }

  async function get(values, { signal, force = false } = {}) {
    const ids = [...new Set(values.map(Number).filter(id => Number.isInteger(id) && id > 0 && id <= 2147483647))];
    if (!ids.length) return { providers: [] };
    const batches = [];
    for (let offset = 0; offset < ids.length; offset += 100) {
      batches.push(batch(ids.slice(offset, offset + 100), force));
    }
    const responses = await waitForSubscriber(Promise.all(batches), signal);
    const providers = new Map();
    for (const response of responses) {
      for (const provider of response.providers || []) {
        const previous = providers.get(provider.provider_id);
        providers.set(provider.provider_id, {
          ...provider,
          state: previous?.state === 'unknown' ? 'unknown' : provider.state,
          matches: { ...previous?.matches, ...provider.matches },
        });
      }
    }
    return { ...responses[0], providers: [...providers.values()] };
  }
  return { get, invalidate };
}

const client = createMovieAvailabilityClient(tmdbIds => fetchJson('/api/iptv/movies/availability', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tmdb_ids: tmdbIds }),
}));

export const getMovieAvailability = client.get;
export function invalidateMovieAvailability() {
  client.invalidate();
}

// The cache outlives screens; a mutation must invalidate it even with no subscribers.
if (typeof window !== 'undefined') {
  window.addEventListener('cp-iptv-catalog-changed', invalidateMovieAvailability);
}

export function getMovieStreamingSources(providerId, tmdbId, options = {}) {
  return fetchJson('/api/iptv/movies/sources', {
    ...options, method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider_id: providerId, tmdb_id: Number(tmdbId) }),
  });
}
