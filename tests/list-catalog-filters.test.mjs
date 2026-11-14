import assert from 'node:assert/strict';
import test from 'node:test';
import { emptyListFilters, filterListRows, needsListMetadata, tvListCriteria } from '../src/utils/listCatalogFilters.js';
import { movieGenres, tvGenres } from '../src/utils/catalogFilterOptions.js';

const movies = [
  { title: 'Zulu', year: '2021', genres: ['Animation'], country_flag: '🇺🇸', tmdb_rating: 8.5, tmdb_vote_count: 5000, popularity: 2 },
  { title: 'Alpha', year: '2024', genre_ids: [16], production_countries: [{ iso_3166_1: 'US', name: 'United States' }], vote_average: 7.4, vote_count: 1500, popularity: 10 },
  { title: 'Beta', year: '2019', genres: ['Drama'], country: 'United Kingdom', rating: 9, votes: 9000, popularity: 4 }
];
const apply = filters => filterListRows(movies, { ...emptyListFilters(), ...filters }, movieGenres, movie => movie);

test('an upper year bound excludes unknown years and requests enrichment for missing saved metadata', () => {
  const rows = [{ title: 'Unknown year' }, { title: 'Known year', year: '2021' }];
  const filters = { ...emptyListFilters(), yearTo: '2024' };
  assert.deepEqual(filterListRows(rows, filters, movieGenres, row => row).map(row => row.title), ['Known year']);
  assert.equal(needsListMetadata(filters), true);
});

test('list metadata filters intersect genre, country, years, votes and ratings using provider or canonical facts', () => {
  assert.deepEqual(apply({ genre: '16', country: 'US', yearFrom: '2020', yearTo: '2023', minVotes: '1000', minRating: '8' }).map(movie => movie.title), ['Zulu']);
  assert.deepEqual(apply({ country: 'GB' }).map(movie => movie.title), ['Beta']);
  assert.deepEqual(apply({ genre: '16', minVotes: '1000' }).map(movie => movie.title), ['Zulu', 'Alpha']);
});
test('sorts preserve original list order by default and never mutate membership', () => {
  assert.deepEqual(apply({}).map(movie => movie.title), ['Zulu', 'Alpha', 'Beta']);
  assert.deepEqual(apply({ sort: 'title.asc' }).map(movie => movie.title), ['Alpha', 'Beta', 'Zulu']);
  assert.deepEqual(apply({ sort: 'vote_average.desc' }).map(movie => movie.title), ['Beta', 'Zulu', 'Alpha']);
  assert.deepEqual(apply({ sort: 'vote_count.desc' }).map(movie => movie.title), ['Beta', 'Zulu', 'Alpha']);
  assert.deepEqual(apply({ sort: 'primary_release_date.desc' }).map(movie => movie.title), ['Alpha', 'Zulu', 'Beta']);
  assert.deepEqual(apply({ sort: 'popularity.desc' }).map(movie => movie.title), ['Alpha', 'Beta', 'Zulu']);
  assert.equal(movies[0].title, 'Zulu');
});
test('TV list criteria retain TV genre identity and use first-air years, with all common filters', () => {
  const query = tvListCriteria({ ...emptyListFilters(), genre: '10765', country: 'GB', minRating: '8', minVotes: '500', yearFrom: '2020', yearTo: '2025', sort: 'vote_count.desc' }, tvGenres);
  assert.deepEqual(query.groups.map(group => group.type), ['genre', 'country', 'rating', 'minimum_votes', 'year']);
  assert.equal(query.groups[0].values[0].label, 'Sci-Fi & Fantasy');
  assert.deepEqual(query.groups.at(-1).values[0], { operator: 'between', from: 2020, to: 2025 });
  assert.equal(query.sort.key, 'vote_count.desc');
});
