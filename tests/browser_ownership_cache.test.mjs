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
