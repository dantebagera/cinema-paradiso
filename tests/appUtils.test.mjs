import assert from 'node:assert/strict';
import test from 'node:test';

import {
  cx,
  formatCount,
  getUniqueOptions,
  movieKey,
  sectionFromPath,
  sortFollowedReleases,
  torrentSizeBytes
} from '../src/utils/appUtils.js';

test('cx joins only truthy class names in order', () => {
  assert.equal(cx('btn', false, '', null, undefined, 'active'), 'btn active');
});

test('formatCount preserves current numeric display fallback', () => {
  assert.equal(formatCount(1234567), '1,234,567');
  assert.equal(formatCount('42'), '42');
  assert.equal(formatCount(null), '0');
  assert.equal(formatCount(undefined), '0');
  assert.equal(formatCount(Number.NaN), '0');
});

test('movieKey preserves lowercase title and year identity', () => {
  assert.equal(movieKey({ title: 'Heat', year: 1995 }), 'heat|1995');
  assert.equal(movieKey({ title: '', year: '' }), '|');
  assert.equal(movieKey({}), '|');
});

test('sortFollowedReleases preserves status and recency ordering without mutating input', () => {
  const items = [
    { title: 'Owned', status: 'owned', updated_at: 300 },
    { title: 'Watching old', status: 'watching', followed_at: 100 },
    { title: 'Available', status: 'available', updated_at: 50 },
    { title: 'Watching new', status: 'watching', updated_at: 200 }
  ];

  assert.deepEqual(sortFollowedReleases(items).map((item) => item.title), [
    'Available',
    'Watching new',
    'Watching old',
    'Owned'
  ]);
  assert.deepEqual(items.map((item) => item.title), [
    'Owned',
    'Watching old',
    'Available',
    'Watching new'
  ]);
});

test('getUniqueOptions flattens arrays, removes empty values, and sorts labels', () => {
  const items = [
    { genres: ['Drama', '', 'Crime'] },
    { genres: ['Drama'] },
    { genres: null },
    { source: 'BluRay' }
  ];

  assert.deepEqual(getUniqueOptions(items, (item) => item.genres), ['Crime', 'Drama']);
  assert.deepEqual(getUniqueOptions(items, (item) => item.source), ['BluRay']);
});

test('torrentSizeBytes preserves size_bytes before size fallback', () => {
  assert.equal(torrentSizeBytes({ size_bytes: 1024, size: 1 }), 1024);
  assert.equal(torrentSizeBytes({ size: 2048 }), 2048);
  assert.equal(torrentSizeBytes({}), 0);
  assert.equal(torrentSizeBytes(null), 0);
});

test('sectionFromPath resolves known sections and falls back home', () => {
  const sections = [{ id: 'home' }, { id: 'library' }, { id: 'cleanup' }];

  assert.equal(sectionFromPath('/library', sections), 'library');
  assert.equal(sectionFromPath('/cleanup/unmatched', sections), 'cleanup');
  assert.equal(sectionFromPath('/', sections), 'home');
  assert.equal(sectionFromPath('/settings', sections), 'home');
  assert.equal(sectionFromPath('', sections), 'home');
});
