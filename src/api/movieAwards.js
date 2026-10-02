const AWARDS = ['oscar', 'golden_globe'];
export function buildPersonAwardsContext(person,role,award,prefix='') {
  const id=person?.id || person?.tmdb_id;
  if (!/^\d+$/.test(String(id)) || Number(id)<1 || !['actor','director'].includes(role) || !AWARDS.includes(award)) return null;
  const params=new URLSearchParams({person_id:String(id),role,award});
  return {type:'person-awards',owner:'person-awards',availability:'all',personId:Number(id),role,award,
    label:`${prefix ? prefix+' > ' : ''}${person.name || 'Person'}: ${award==='oscar' ? 'Oscars' : 'Golden Globe'}`,
    baseUrl:`/api/movie-awards/person-films?${params}`,emptyText:'No winning films for this role and award.'};
}
export const positiveAwards = counts => AWARDS.filter(award => Number.isInteger(counts?.[award]) && counts[award] > 0).map(award => [award, counts[award]]);
const pair = value => value ? Object.fromEntries(AWARDS.map(award => [award, Number.isInteger(value[award]) && value[award] >= 0 ? value[award] : null])) : null;

export function movieAwardCounts(snapshot, movie, enabled = true) {
  if (!enabled || !snapshot?.ready) return null;
  const tmdb = String(movie?.tmdb_id || movie?.id || '').trim();
  const imdb = String(movie?.imdb_id || '').trim();
  const tmdbValue = /^\d+$/.test(tmdb) && Number(tmdb) > 0 ? snapshot.movies?.[`tmdb:${Number(tmdb)}`] : null;
  const imdbValue = /^tt\d+$/.test(imdb) ? snapshot.movies?.[`imdb:${imdb}`] : null;
  if (tmdb && imdb && (!tmdbValue || !imdbValue || tmdbValue.entity_id !== imdbValue.entity_id)) return null;
  return pair(tmdbValue || imdbValue);
}

export function personAwardCounts(snapshot, personId, role, enabled = true) {
  if (!enabled || !snapshot?.ready || !['actor','director'].includes(role) || !/^\d+$/.test(String(personId)) || Number(personId) < 1) return null;
  return pair(snapshot.people?.[`tmdb:${Number(personId)}`]?.[role]);
}

export function createAwardsCache({fetcher = (...args) => fetch(...args), now = () => Date.now(), visible = () => true} = {}) {
  let snapshot = null, etag = '', pending = null, lastAttempt = null, consumers = 0;
  const listeners = new Set();
  const cache = {
    getSnapshot: () => snapshot,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    acquire(enabled) {
      if (!enabled) return () => {};
      consumers++;
      if (lastAttempt === null && visible()) cache.revalidate();
      return () => { consumers = Math.max(0,consumers - 1); };
    },
    focus() {
      if (consumers && visible() && (lastAttempt === null || now() - lastAttempt >= 60000)) return cache.revalidate();
      return Promise.resolve();
    },
    revalidate() {
      if (pending) return pending;
      lastAttempt = now();
      pending = (async () => {
        try {
          const response = await fetcher('/api/movie-awards/snapshot', {headers:etag ? {'If-None-Match':etag} : {}});
          if (response.status === 304) return;
          if (!response.ok) throw new Error('Awards unavailable');
          const next = await response.json();
          if (next.schema_version !== 1 || !Number.isInteger(next.awards_generation) || next.awards_generation < 0) throw new Error('Unsupported awards snapshot');
          const sameOwner = snapshot && next.snapshot_owner === snapshot.snapshot_owner;
          if (sameOwner && next.awards_generation <= snapshot.awards_generation) return;
          snapshot = next; etag = response.headers.get('ETag') || '';
          for (const listener of listeners) listener();
        } catch { /* A local read failure leaves the last complete snapshot usable. */ }
      })().finally(() => { pending = null; });
      return pending;
    }
  };
  return cache;
}
