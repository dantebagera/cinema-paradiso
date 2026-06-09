import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildOwnershipMap,
  discoverMoviePayload,
  discoverMovieKey,
  filterEnrichedIndexerResults,
  listsForDiscoverMovie,
  sortTorrentVariants
} from '../src/discoverUtils.js';

test('buildOwnershipMap keeps only found movies with local paths', () => {
  const map = buildOwnershipMap([
    { title: 'The Thing', year: '1982', found: true, path: 'E:/Movies/The Thing.mkv', resolution: '1080p' },
    { title: 'Alien', year: '1979', found: false, path: '', resolution: '' },
    { title: 'Heat', year: '1995', found: true, path: '', resolution: '720p' }
  ]);

  assert.deepEqual(Object.keys(map), ['the thing|1982']);
  assert.equal(map[discoverMovieKey({ title: 'The Thing', year: '1982' })].resolution, '1080p');
});

test('filterEnrichedIndexerResults hides browse rows without TMDB metadata', () => {
  const rows = filterEnrichedIndexerResults([
    {
      parsed_title: 'Earth, Wind & Fire',
      parsed_year: '2026',
      metadata: {
        tmdb_id: 123,
        title: 'Earth, Wind & Fire',
        year: '2026',
        poster_url: 'https://image.tmdb.org/poster.jpg',
        genres: ['Documentary']
      },
      variants: [{ resolution: '1080p', seeders: 100, size_human: '2.2 GB', indexer: 'YTS' }]
    },
    {
      parsed_title: 'Strange.Indexer.Release.Name',
      parsed_year: '',
      metadata: {},
      variants: [{ resolution: '1080p', seeders: 4, size_human: '1.1 GB', indexer: 'Unknown' }]
    }
  ]);

  assert.equal(rows.length, 1);
  assert.equal(rows[0].title, 'Earth, Wind & Fire');
  assert.equal(rows[0].tmdb_id, 123);
  assert.equal(rows[0].variants[0].indexer, 'YTS');
});

test('sortTorrentVariants prioritizes quality then seeders', () => {
  const variants = sortTorrentVariants([
    { resolution: '1080p', seeders: 450, size_human: '2 GB' },
    { resolution: '4K', seeders: 10, size_human: '12 GB' },
    { resolution: '720p', seeders: 900, size_human: '1 GB' },
    { resolution: '1080p', seeders: 1200, size_human: '4 GB' }
  ]);

  assert.deepEqual(
    variants.map((variant) => `${variant.resolution}:${variant.seeders}`),
    ['4K:10', '1080p:1200', '1080p:450', '720p:900']
  );
});

test('discoverMoviePayload supports online movies and owned paths', () => {
  const payload = discoverMoviePayload(
    { tmdb_id: 155, title: 'The Dark Knight', year: '2008', poster_url: 'poster.jpg' },
    { path: 'E:/Movies/The Dark Knight.mkv' }
  );

  assert.deepEqual(payload, {
    tmdb_id: '155',
    title: 'The Dark Knight',
    year: '2008',
    poster_url: 'poster.jpg',
    path: 'E:/Movies/The Dark Knight.mkv'
  });
});

test('listsForDiscoverMovie matches online movies by tmdb id without a file path', () => {
  const lists = [
    {
      id: 'favorites',
      name: 'Favorites',
      movies: [{ tmdb_id: '155', title: 'The Dark Knight', year: '2008', poster_url: 'poster.jpg' }]
    },
    {
      id: 'watch-later',
      name: 'Watch Later',
      movies: [{ title: 'Heat', year: '1995' }]
    }
  ];

  const matches = listsForDiscoverMovie({ tmdb_id: 155, title: 'The Dark Knight', year: '2008' }, lists);

  assert.deepEqual(matches.map((list) => list.name), ['Favorites']);
});
