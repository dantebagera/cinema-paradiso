import test from 'node:test';
import assert from 'node:assert/strict';

import { buildUpcomingHomeMovies, uniqueHomeMovies } from '../src/utils/homeMovies.js';

test('backend upcoming results exclude duplicate and Trending titles then sort by release date', () => {
  const trending = [{ tmdb_id: 2, title: 'Already Trending', year: '2026' }];
  const results = [
    { tmdb_id: 1, title: 'Later', release_date: '2026-09-10', popularity: 20 },
    { tmdb_id: 2, title: 'Already Trending', release_date: '2026-08-02' },
    { tmdb_id: 4, title: 'Soon', release_date: '2026-08-02', popularity: 10 },
    { tmdb_id: 4, title: 'Soon duplicate', release_date: '2026-08-02', popularity: 100 },
    { tmdb_id: 5, title: 'Soon popular', release_date: '2026-08-02', popularity: 30 }
  ];

  assert.deepEqual(
    buildUpcomingHomeMovies(results, trending).map((movie) => movie.title),
    ['Soon popular', 'Soon', 'Later']
  );
});

test('unique Home movies prefer the first authoritative projection', () => {
  const first = { tmdb_id: 10, title: 'First' };
  const second = { tmdb_id: 10, title: 'Duplicate' };
  const titleOnly = { title: 'No ID', year: '2026' };

  assert.deepEqual(uniqueHomeMovies([first], [second, titleOnly, { ...titleOnly }]), [first, titleOnly]);
});

test('Upcoming selects twenty survivors in provider order before sorting, retaining raw replacements', () => {
  const raw = Array.from({ length: 25 }, (_, i) => ({ tmdb_id: i + 1,
    title: `Movie ${i + 1}`, release_date: `2099-02-${String(28 - i).padStart(2, '0')}` }));
  raw.splice(5, 0, { ...raw[4], title: 'Duplicate' });
  const preview = buildUpcomingHomeMovies(raw, [raw[0], raw[1]]);
  assert.equal(preview.length, 20);
  assert.deepEqual(preview.map(movie => movie.tmdb_id), [22,21,20,19,18,17,16,15,14,13,12,11,10,9,8,7,6,5,4,3]);
  assert.equal(raw.length, 26);
  // A movie leaving Trending is eligible again; the retained raw pool was not capped.
  assert.deepEqual(buildUpcomingHomeMovies(raw, []).map(movie => movie.tmdb_id),
    [20,19,18,17,16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1]);
});
