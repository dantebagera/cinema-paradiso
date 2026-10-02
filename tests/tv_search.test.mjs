import test from 'node:test';
import assert from 'node:assert/strict';
import { createEmptyQuery, normalizeAdvancedQuery, withCriterion, querySignature } from '../src/features/search/advancedSearchModel.js';
import { buildTvStreamTemplateUrl } from '../src/utils/appUtils.js';

test('TV creator criteria survive edits while movie validation stays unchanged', () => {
  const value = { id: '123', label: 'A creator', role: 'creator' };
  const query = withCriterion({ ...createEmptyQuery('library'), media_type: 'tv' }, 'person', value);
  assert.equal(normalizeAdvancedQuery(query).groups[0].values[0].role, 'creator');
  assert.throws(() => withCriterion(createEmptyQuery('library'), 'person', value));
  const movie = createEmptyQuery('library');
  assert.notEqual(querySignature(movie), querySignature({ ...movie, media_type: 'tv' }));
});

test('TMDB series status is available only to TV Discover queries', () => {
  const status = { id: '3', label: 'Ended' };
  const tvDiscover = { ...createEmptyQuery('discover'), media_type: 'tv' };
  const filtered = withCriterion(tvDiscover, 'tv_status', status);
  assert.deepEqual(normalizeAdvancedQuery(filtered).groups[0].values[0], status);
  assert.throws(() => withCriterion(createEmptyQuery('discover'), 'tv_status', status));
  assert.throws(() => withCriterion({ ...createEmptyQuery('library'), media_type: 'tv' }, 'tv_status', status));
  assert.throws(() => withCriterion(tvDiscover, 'tv_status', { id: '6', label: 'Other' }));
});

test('TV stream targets the series and episode, refuses unaired or incomplete targets', () => {
  const template = 'https://streamimdb.ru/embed/tv/{tmdb_id}/{season_number}/{episode_number}';
  const episode = { tmdb_id: 108978, episode_id: 9999, season_number: 1, episode_number: 2, released: true };
  assert.equal(buildTvStreamTemplateUrl(template, episode), 'https://streamimdb.ru/embed/tv/108978/1/2');
  assert.equal(buildTvStreamTemplateUrl(template, { ...episode, released: false }), '');
  assert.equal(buildTvStreamTemplateUrl(template, { ...episode, episode_number: null }), '');
});
