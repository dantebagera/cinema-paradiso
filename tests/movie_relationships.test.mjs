import test from 'node:test';
import assert from 'node:assert/strict';
import { mergeRelationshipMovies, fetchRelationshipPage, fetchTvRelationshipPage } from '../src/api/movieRelationships.js';
import { centeredWorkspaceScroll } from '../src/components/movie-card/expandedCardViewport.js';

test('All preserves provider order and deduplicates TMDB identity, not titles', () => {
  const recommended = [{ tmdb_id: '1', title: 'Same' }, { tmdb_id: '2', title: 'Same' }];
  assert.deepEqual(mergeRelationshipMovies(recommended, [{ tmdb_id: 1 }, { tmdb_id: '3' }]).map((m) => m.tmdb_id), ['1', '2', '3']);
});
test('workspace centering accounts for current scroll and viewport offset', () => {
  assert.equal(centeredWorkspaceScroll({ top: 700, height: 940 }, { top: 0, height: 1080, scrollTop: 300 }), 930);
  assert.equal(centeredWorkspaceScroll({ top: 10, height: 400 }, { top: 0, height: 1080, scrollTop: 0 }), 0);
});
test('page requests deduplicate and retry failures', async () => {
  const previous = global.fetch;
  const calls = [];
  global.fetch = async (url) => {
    calls.push(url);
    const params = new URL(url, 'http://localhost').searchParams;
    const source = params.get('source');
    const page = Number(params.get('page'));
    return { ok: true, text: async () => JSON.stringify({ total_pages: 2, results: [{ tmdb_id: String(source === 'similar' ? page + 1 : page) }] }) };
  };
  try {
    await Promise.all([fetchRelationshipPage('unit'), fetchRelationshipPage('unit')]);
    assert.equal(calls.length, 1);
    global.fetch = async () => { throw new Error('offline'); };
    await assert.rejects(fetchRelationshipPage('retry'), /offline/);
    global.fetch = async () => ({ ok: true, text: async () => '{"results":[]}' });
    assert.deepEqual((await fetchRelationshipPage('retry')).results, []);
  } finally { global.fetch = previous; }
});
test('TV and movie IDs use separate relationship endpoints and cache entries', async () => {
  const previous = global.fetch;
  const calls = [];
  global.fetch = async (url) => {
    calls.push(url);
    return { ok: true, text: async () => JSON.stringify({ results: [{ tmdb_id: url.startsWith('/api/tv/') ? 'tv' : 'movie' }] }) };
  };
  try {
    const [movie, tv, tvThreeColumns, tvTwoColumns] = await Promise.all([
      fetchRelationshipPage('shared-id'),
      fetchTvRelationshipPage('shared-id'),
      fetchTvRelationshipPage('shared-id', 'recommendations', 1, 39),
      fetchTvRelationshipPage('shared-id', 'recommendations', 1, 40),
    ]);
    assert.equal(movie.results[0].tmdb_id, 'movie');
    assert.equal(tv.results[0].tmdb_id, 'tv');
    assert.equal(tvThreeColumns.results[0].tmdb_id, 'tv');
    assert.equal(tvTwoColumns.results[0].tmdb_id, 'tv');
    assert.equal(calls.length, 4);
    assert.ok(calls.some(url => url.startsWith('/api/tv/related')));
    assert.ok(calls.some(url => url.startsWith('/api/tmdb/related')));
    assert.ok(calls.some(url => url.includes('page_size=39')));
    assert.ok(calls.some(url => url.includes('page_size=40')));
  } finally { global.fetch = previous; }
});
