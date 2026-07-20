import assert from 'node:assert/strict';
import test from 'node:test';

import {
  clearOwnershipCheckCache,
  fetchOwnershipChecks,
  observeCatalogGeneration
} from '../src/api/library.js';

test('catalog generation changes invalidate cached ownership checks', async () => {
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return new Response(JSON.stringify({
      catalog_generation: calls === 1 ? 10 : 11,
      results: [{
        title: 'Parity Movie',
        year: '2024',
        tmdb_id: '42',
        found: calls > 1,
        path: calls > 1 ? 'E:/Movies/Parity.Movie.2024.mkv' : '',
        resolution: calls > 1 ? '1080p' : '',
        size_human: ''
      }]
    }), { status: 200 });
  };

  try {
    clearOwnershipCheckCache();
    observeCatalogGeneration(10);
    const movie = { tmdb_id: '42', title: 'Parity Movie', year: '2024' };

    const first = await fetchOwnershipChecks([movie]);
    const cached = await fetchOwnershipChecks([movie]);
    observeCatalogGeneration(11);
    const refreshed = await fetchOwnershipChecks([movie]);

    assert.equal(calls, 2);
    assert.equal(first[0].found, false);
    assert.equal(cached[0].found, false);
    assert.equal(refreshed[0].found, true);
  } finally {
    globalThis.fetch = originalFetch;
    clearOwnershipCheckCache();
  }
});

test('catalog generation changes broadcast detail-cache invalidation', () => {
  const originalWindow = globalThis.window;
  const originalCustomEvent = globalThis.CustomEvent;
  const events = [];
  globalThis.window = { dispatchEvent: (event) => events.push(event) };
  globalThis.CustomEvent = class CustomEvent {
    constructor(type, options = {}) {
      this.type = type;
      this.detail = options.detail;
    }
  };

  try {
    observeCatalogGeneration(100);
    observeCatalogGeneration(101);
    assert.equal(events.at(-1).type, 'cp-catalog-generation-changed');
    assert.deepEqual(events.at(-1).detail, { previousGeneration: 100, generation: 101 });
    const eventCount = events.length;
    assert.equal(observeCatalogGeneration(100), false);
    assert.equal(events.length, eventCount);
  } finally {
    if (originalWindow === undefined) delete globalThis.window;
    else globalThis.window = originalWindow;
    if (originalCustomEvent === undefined) delete globalThis.CustomEvent;
    else globalThis.CustomEvent = originalCustomEvent;
  }
});
