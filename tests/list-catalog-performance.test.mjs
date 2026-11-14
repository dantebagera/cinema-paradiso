import assert from 'node:assert/strict';
import test from 'node:test';
import { emptyListFilters, filterListRows } from '../src/utils/listCatalogFilters.js';
import { movieGenres } from '../src/utils/catalogFilterOptions.js';

const titles = rows => rows.map(row => row.movie.title);

for (const size of [4000, 10000]) {
  test(`default filters preserve all ${size} members without reading metadata`, () => {
    const rows = Array.from({ length: size }, (_, id) => ({ id }));
    let reads = 0;
    const result = filterListRows(rows, emptyListFilters(), movieGenres, row => { reads++; return row; });
    assert.deepEqual(result, rows);
    assert.notEqual(result, rows, 'callers may change their result without changing membership');
    assert.equal(reads, 0);
  });

  test(`filtering and sorting ${size} members reads each canonical metadata object once`, () => {
    const rows = Array.from({ length: size }, (_, id) => ({
      id,
      movie: { title: `Movie ${id}`, genre_ids: [18], country: 'GB', rating: 1 },
      canonical: { genre_ids: [16], country: 'US', tmdb_rating: 8, tmdb_vote_count: 5000, release_date: '2021-07-08', popularity: id }
    }));
    const reads = new Map();
    const filters = { ...emptyListFilters(), genre: '16', country: 'US', minVotes: '1000', minRating: '7', yearFrom: '2020', yearTo: '2023', sort: 'popularity.desc' };
    const result = filterListRows(rows, filters, movieGenres, row => {
      reads.set(row.id, (reads.get(row.id) || 0) + 1);
      return { ...row.movie, ...row.canonical };
    });
    assert.equal(result.length, size, 'filtering evaluates full membership before callers page');
    assert.equal(result[0].id, size - 1);
    assert.equal(result.at(-1).id, 0);
    assert.deepEqual(result.slice(0, 3).map(row => row.id), [size - 1, size - 2, size - 3]);
    assert.equal(rows[0].id, 0, 'sort must not change the membership array');
    assert.equal(reads.size, size);
    assert.equal(Math.max(...reads.values()), 1);
  });
}

test('sort-only paths resolve canonical facts once and keep equal keys in list order', () => {
  const rows = [
    { movie: { title: 'Zulu' }, canonical: { title: 'Alpha', vote_count: 10, vote_average: 8, popularity: 2, release_date: '2021-01-01' } },
    { movie: { title: 'Alpha' }, canonical: { title: 'Alpha', vote_count: 10, vote_average: 8, popularity: 2, release_date: '2021-01-01' } },
    { movie: { title: 'Beta' }, canonical: { title: 'Zulu', vote_count: 20, vote_average: 9, popularity: 3, release_date: '2022-01-01' } }
  ];
  for (const sort of ['title.asc', 'vote_average.desc', 'vote_count.desc', 'popularity.desc', 'primary_release_date.desc']) {
    let reads = 0;
    const result = filterListRows(rows, { ...emptyListFilters(), sort }, movieGenres, row => { reads++; return { ...row.movie, ...row.canonical }; });
    assert.deepEqual(titles(result), sort === 'title.asc' ? ['Zulu', 'Alpha', 'Beta'] : ['Beta', 'Zulu', 'Alpha']);
    assert.equal(reads, rows.length, sort);
    assert.deepEqual(titles(rows), ['Zulu', 'Alpha', 'Beta']);
  }
});

test('genre-only filtering does not inspect unused ratings, votes or countries', () => {
  const rows = [{ title: 'Animation', genres: ['Animation'] }, { title: 'Drama', genres: ['Drama'] }];
  for (const row of rows) {
    for (const field of ['tmdb_rating', 'tmdb_vote_count', 'country']) {
      Object.defineProperty(row, field, { get() { throw new Error(`unused ${field}`); } });
    }
  }
  assert.deepEqual(filterListRows(rows, { ...emptyListFilters(), genre: '16' }, movieGenres, row => row).map(row => row.title), ['Animation']);
});

test('incomplete year drafts and unknown genre choices preserve membership without metadata reads', () => {
  const rows = [{ title: 'Unknown' }];
  let reads = 0;
  for (const draft of [{ yearFrom: '20' }, { yearFrom: '2025', yearTo: '2020' }, { genre: 'unknown' }]) {
    assert.deepEqual(filterListRows(rows, { ...emptyListFilters(), ...draft }, movieGenres, row => { reads++; return row; }), rows);
  }
  assert.equal(reads, 0);
});
