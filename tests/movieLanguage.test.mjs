import test from 'node:test';
import assert from 'node:assert/strict';
import { isArabicMovie, movieDisplayTitle } from '../src/utils/movieLanguage.js';
import { fetchTransientMovieLanguage, mergeTransientMovieLanguage } from '../src/api/movieDetails.js';

test('Arabic defaults use original language, never a translated title alone', () => {
  const movie = Object.freeze({ title: 'The Blue Elephant', original_title: 'الفيل الأزرق', original_language: 'ar' });
  assert.equal(movieDisplayTitle(movie), 'الفيل الأزرق');
  assert.equal(movie.title, 'The Blue Elephant');
  assert.equal(isArabicMovie({ language: 'Arabic' }), true);
  assert.equal(isArabicMovie({ original_language: 'en', language: 'Arabic', original_title: 'عربي' }), false);
  assert.equal(movieDisplayTitle({ title: 'Foreign', original_language: 'en', original_title: 'عربي' }), 'Foreign');
  assert.equal(movieDisplayTitle({ title: 'Available', original_language: 'ar', original_title: '' }), 'Available');
});

test('localized text preserves identity, artwork, ratings and collection membership', () => {
  const movie = Object.freeze({ accepted: true, tmdb_id: '1', title: 'English', poster_url: '/custom.jpg', path: 'film.mkv', rating: '8', original_language: 'ar' });
  const details = { loading: true, error: 'Details unavailable', detail_source: 'library_sql', collection: { id: '10', name: 'Collection', owned_count: 2, parts: [{ tmdb_id: '1' }] } };
  const localized = { tmdb_id: '2', title: 'عنوان', plot: 'حبكة', poster_url: '/other.jpg', rating: '2', path: 'other.mkv', collection: { id: '99', name: 'مجموعة', parts: [] } };
  const { displayMovie, displayDetails } = mergeTransientMovieLanguage(movie, details, localized);
  assert.equal(displayMovie.title, 'عنوان');
  assert.equal(displayMovie.plot, 'حبكة');
  for (const field of ['tmdb_id', 'poster_url', 'path', 'rating']) assert.equal(displayMovie[field], movie[field]);
  assert.deepEqual(displayDetails.collection, details.collection);
  assert.equal(displayDetails.detail_source, 'library_sql');
  assert.equal(displayDetails.loading, true);
  assert.equal(displayDetails.error, 'Details unavailable');
});

test('empty translations do not erase descriptions or cast and keep Arabic original title', () => {
  const movie = { title: 'English', original_title: 'الأصل', original_language: 'ar', plot: 'Available', genres: ['Drama'] };
  const details = { cast: [{ id: 3, name: 'Actor', profile_url: '/portrait', character: 'Role' }] };
  const result = mergeTransientMovieLanguage(movie, details, { title: 'English', plot: '', genres: [], cast: [{ id: 3, name: 'ممثل' }] });
  assert.equal(result.displayMovie.title, 'الأصل');
  assert.equal(result.displayMovie.summary, 'Available');
  assert.deepEqual(result.displayMovie.genres, ['Drama']);
  assert.equal(result.displayDetails.cast[0].profile_url, '/portrait');
  assert.equal(result.displayDetails.cast[0].name, 'ممثل');
});

test('language requests deduplicate, cache successful responses, and retry failures', async () => {
  const previous = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => { calls++; return { ok: calls !== 1, status: 503, text: async () => JSON.stringify(calls === 1 ? { error: 'Unavailable' } : { title: 'عربي' }) }; };
  try {
    await assert.rejects(fetchTransientMovieLanguage('908172'), /Unavailable/);
    const results = await Promise.all([fetchTransientMovieLanguage('908172'), fetchTransientMovieLanguage('908172')]);
    assert.equal(results[0].title, 'عربي');
    await fetchTransientMovieLanguage('908172');
    assert.equal(calls, 2);
  } finally { globalThis.fetch = previous; }
});
