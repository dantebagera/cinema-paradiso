import assert from 'node:assert/strict';
import test from 'node:test';

import {
  cx,
  formatCount,
  getUniqueOptions,
  movieKey,
  sectionFromPath,
  sortFollowedReleases,
  buildStreamTemplateUrl,
  streamTemplateTokens,
  toYouTubeEmbedUrl,
  topBarSearchEnabled,
  torrentSizeBytes,
  torrentPrimaryAction,
  youtubeTrailerSearchUrl
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

test('torrentPrimaryAction never treats a Prowlarr download URL as a browser link', () => {
  assert.deepEqual(
    torrentPrimaryAction({ magnet_url: 'magnet:?xt=urn:btih:test', download_url: 'http://prowlarr/file' }),
    { kind: 'magnet', url: 'magnet:?xt=urn:btih:test' }
  );
  assert.deepEqual(
    torrentPrimaryAction({ download_url: 'http://prowlarr/file' }),
    { kind: 'torrent', url: 'http://prowlarr/file' }
  );
  assert.deepEqual(
    torrentPrimaryAction({ info_url: 'https://indexer/source' }),
    { kind: 'source', url: 'https://indexer/source' }
  );
  assert.deepEqual(
    torrentPrimaryAction({ magnet_url: 'http://localhost:9696/prowlarr/1/download?id=5' }),
    { kind: 'torrent', url: 'http://localhost:9696/prowlarr/1/download?id=5' }
  );
});

test('sectionFromPath resolves known sections and falls back home', () => {
  const sections = [{ id: 'home' }, { id: 'library' }, { id: 'cleanup' }];

  assert.equal(sectionFromPath('/library', sections), 'library');
  assert.equal(sectionFromPath('/cleanup/unmatched', sections), 'cleanup');
  assert.equal(sectionFromPath('/', sections), 'home');
  assert.equal(sectionFromPath('/settings', sections), 'home');
  assert.equal(sectionFromPath('', sections), 'home');
});

test('sectionFromPath resolves help and search is disabled on help', () => {
  const sections = [{ id: 'home' }, { id: 'help' }];

  assert.equal(sectionFromPath('/help', sections), 'help');
  assert.equal(topBarSearchEnabled('help', 'explore'), false);
});

test('topBarSearchEnabled limits search to functional page contexts', () => {
  assert.equal(topBarSearchEnabled('home', 'explore'), true);
  assert.equal(topBarSearchEnabled('library', 'explore'), true);
  assert.equal(topBarSearchEnabled('discover', 'explore'), true);
  assert.equal(topBarSearchEnabled('discover', 'browse'), true);
  assert.equal(topBarSearchEnabled('discover', 'pick'), false);
  assert.equal(topBarSearchEnabled('settings', 'explore'), false);
  assert.equal(topBarSearchEnabled('cleanup', 'explore'), false);
  assert.equal(topBarSearchEnabled('downloads', 'explore'), false);
});

test('streamTemplateTokens reports required movie identifiers', () => {
  assert.deepEqual(streamTemplateTokens('https://example.test/embed/{tmdb_id}'), ['tmdb_id']);
  assert.deepEqual(streamTemplateTokens('https://example.test/{imdb_id}/{tmdb_id}'), ['imdb_id', 'tmdb_id']);
});

test('buildStreamTemplateUrl replaces configured movie identifiers', () => {
  assert.equal(
    buildStreamTemplateUrl('https://streamimdb.ru/embed/movie/{tmdb_id}', { tmdb_id: 1413976 }),
    'https://streamimdb.ru/embed/movie/1413976'
  );
  assert.equal(
    buildStreamTemplateUrl('https://example.test/title/{imdb_id}', { imdb_id: 'tt0111161' }),
    'https://example.test/title/tt0111161'
  );
});

test('buildStreamTemplateUrl rejects missing ids and non-http templates', () => {
  assert.throws(
    () => buildStreamTemplateUrl('https://streamimdb.ru/embed/movie/{tmdb_id}', {}),
    /Missing TMDB ID/
  );
  assert.throws(
    () => buildStreamTemplateUrl('javascript:alert({tmdb_id})', { tmdb_id: '1413976' }),
    /http/
  );
});

test('toYouTubeEmbedUrl converts common YouTube trailer links to embeddable player URLs', () => {
  assert.equal(
    toYouTubeEmbedUrl('https://www.youtube.com/watch?v=official-key&feature=share'),
    'https://www.youtube.com/embed/official-key?autoplay=1&rel=0'
  );
  assert.equal(
    toYouTubeEmbedUrl('https://youtu.be/short-key?t=12'),
    'https://www.youtube.com/embed/short-key?autoplay=1&rel=0'
  );
  assert.equal(
    toYouTubeEmbedUrl('https://www.youtube.com/embed/already-embed'),
    'https://www.youtube.com/embed/already-embed?autoplay=1&rel=0'
  );
});

test('toYouTubeEmbedUrl rejects non-player and invalid trailer URLs', () => {
  assert.equal(toYouTubeEmbedUrl('https://www.youtube.com/results?search_query=heat+trailer'), '');
  assert.equal(toYouTubeEmbedUrl('https://example.com/watch?v=official-key'), '');
  assert.equal(toYouTubeEmbedUrl(''), '');
  assert.equal(toYouTubeEmbedUrl(null), '');
});

test('youtubeTrailerSearchUrl builds an external YouTube fallback search', () => {
  assert.equal(
    youtubeTrailerSearchUrl('Heat', 1995),
    'https://www.youtube.com/results?search_query=Heat+1995+trailer'
  );
  assert.equal(
    youtubeTrailerSearchUrl('The Matrix', ''),
    'https://www.youtube.com/results?search_query=The+Matrix+trailer'
  );
});
