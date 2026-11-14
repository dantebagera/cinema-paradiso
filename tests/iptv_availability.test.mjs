import test from 'node:test';
import assert from 'node:assert/strict';
import { createMovieAvailabilityClient } from '../src/api/iptvAvailability.js';

const result = ids => ({ providers: [{ provider_id: 'a', name: 'Lionz', state: 'ready',
  matches: Object.fromEntries(ids.filter(id => id === 550).map(id => [id, { movie_key: 'tmdb:550', source_count: 2 }])) }] });

test('catalog mutations invalidate the shared cache without a mounted availability hook', async () => {
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;
  globalThis.window = new EventTarget();
  let calls = 0;
  globalThis.fetch = async () => ({ ok: true, text: async () => JSON.stringify({ providers: [{ name: String(++calls) }] }) });
  try {
    const { getMovieAvailability } = await import('../src/api/iptvAvailability.js?invalidation-test');
    await getMovieAvailability([550]);
    window.dispatchEvent(new Event('cp-iptv-catalog-changed'));
    const refreshed = await getMovieAvailability([550]);
    assert.equal(refreshed.providers[0].name, '2');
  } finally {
    globalThis.window = originalWindow;
    globalThis.fetch = originalFetch;
  }
});

test('batches and deduplicates IDs then reuses a page result in the chooser', async () => {
  const calls = [];
  const client = createMovieAvailabilityClient(async ids => { calls.push(ids); return result(ids); });
  await client.get([550, 550, 999]);
  const single = await client.get([550]);
  assert.deepEqual(calls, [[550, 999]]);
  assert.equal(single.providers[0].matches['550'].source_count, 2);
});

test('one subscriber abort does not cancel shared work', async () => {
  let finish;
  let calls = 0;
  const client = createMovieAvailabilityClient(ids => {
    calls++;
    return new Promise(resolve => { finish = () => resolve(result(ids)); });
  });
  const abort = new AbortController();
  const first = client.get([550], { signal: abort.signal });
  const second = client.get([550]);
  abort.abort();
  await assert.rejects(first, { name: 'AbortError' });
  finish();
  assert.equal((await second).providers[0].state, 'ready');
  assert.equal(calls, 1);
});

test('expiry and invalidation refresh local results without reusing a pending old generation', async () => {
  let now = 0;
  let calls = 0;
  const client = createMovieAvailabilityClient(async ids => { calls++; return result(ids); }, () => now);
  await client.get([550]);
  now = 15001;
  await client.get([550]);
  client.invalidate();
  await client.get([550]);
  assert.equal(calls, 3);
});

test('provider unknown stays distinct from a successful empty match', async () => {
  const client = createMovieAvailabilityClient(async () => ({ providers: [
    { provider_id: 'a', state: 'ready', matches: {} },
    { provider_id: 'b', state: 'unknown', matches: {} },
  ] }));
  const data = await client.get([550]);
  assert.deepEqual(data.providers.map(p => p.state), ['ready', 'unknown']);
});

test('a response from before invalidation cannot replace the refreshed cache', async () => {
  let finish;
  let calls = 0;
  const client = createMovieAvailabilityClient(() => {
    calls++;
    if (calls === 1) return new Promise(resolve => { finish = resolve; });
    return Promise.resolve({ providers: [{ provider_id: 'new', state: 'ready', matches: {} }] });
  });
  const old = client.get([550]);
  client.invalidate();
  await client.get([550]);
  finish(result([550]));
  await old;
  assert.equal((await client.get([550])).providers[0].provider_id, 'new');
});
