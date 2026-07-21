import assert from 'node:assert/strict';
import test from 'node:test';

import { mergeCanonicalMovieDetails } from '../src/api/movieDetails.js';

test('owned detail merges preserve valid card summaries when deferred fields are empty', () => {
  const summary = {
    projection_contract: 'canonical_movie_card',
    title: 'Correct Movie',
    year: '2020',
    plot: 'Stored plot',
    summary: 'Stored plot',
    poster_url: 'local-or-provider-poster.jpg',
    genres: ['Drama'],
    rating: '8.4'
  };
  const details = {
    projection_contract: 'canonical_movie_details',
    title: '',
    plot: '',
    summary: '',
    poster_url: '',
    genres: [],
    cast: [{ id: '1', name: 'Lead Actor' }]
  };

  const merged = mergeCanonicalMovieDetails(summary, details);

  assert.equal(merged.title, 'Correct Movie');
  assert.equal(merged.plot, 'Stored plot');
  assert.equal(merged.summary, 'Stored plot');
  assert.equal(merged.poster_url, 'local-or-provider-poster.jpg');
  assert.deepEqual(merged.genres, ['Drama']);
  assert.equal(merged.cast[0].name, 'Lead Actor');
  assert.equal(merged.projection_contract, 'canonical_movie_details');
});
