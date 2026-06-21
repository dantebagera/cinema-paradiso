import assert from 'node:assert/strict';
import test from 'node:test';

import {
  filterIdentityReviewItems,
  filterCleanupItems,
  filterUnmatchedItems,
  metadataStatusChipClass,
  metadataStatusLabel,
  renameModalItem
} from '../src/utils/cleanupUtils.js';

test('filterCleanupItems preserves search and exact cleanup filter behavior', () => {
  const items = [
    {
      title: 'Heat',
      filename: 'Heat.1995.mkv',
      path: 'E:/Movies/Heat.1995.mkv',
      plex_title: 'Heat',
      plex_year: 1995,
      rip_source: 'BluRay',
      resolution: '1080p',
      plex_matched: true
    },
    {
      title: 'Alien',
      filename: 'Alien.1979.mkv',
      path: 'E:/Movies/Alien.1979.mkv',
      rip_source: 'WEB-DL',
      resolution: '720p',
      plex_matched: false
    }
  ];

  const all = { query: '', resolution: 'all', source: 'all', plex: 'all' };
  assert.deepEqual(filterCleanupItems(items, all), items);
  assert.deepEqual(filterCleanupItems(items, { ...all, query: '1995' }), [items[0]]);
  assert.deepEqual(filterCleanupItems(items, { ...all, resolution: '720p' }), [items[1]]);
  assert.deepEqual(filterCleanupItems(items, { ...all, source: 'BluRay' }), [items[0]]);
  assert.deepEqual(filterCleanupItems(items, { ...all, plex: 'matched' }), [items[0]]);
  assert.deepEqual(filterCleanupItems(items, { ...all, plex: 'unmatched' }), [items[1]]);
});

test('filterUnmatchedItems preserves metadata search and status buckets', () => {
  const items = [
    {
      filename: 'Heat.file.mkv',
      path: 'E:/Movies/Heat.file.mkv',
      suggested_title: 'Heat',
      suggested_year: 1995,
      plex_title: 'Heat',
      tmdb_title: 'Heat',
      metadata_hint: 'accepted',
      plex_hint: 'matched',
      folder: 'Heat (1995)',
      plex_matched: true,
      tmdb_id: 949,
      metadata_status: 'pending'
    },
    {
      filename: 'Unknown.file.mkv',
      path: 'E:/Movies/Unknown.file.mkv',
      folder: 'Unknown',
      plex_matched: false,
      tmdb_id: '',
      metadata_status: 'conflict'
    },
    {
      filename: 'Review.file.mkv',
      path: 'E:/Movies/Review.file.mkv',
      plex_matched: false,
      tmdb_id: 10,
      metadata_status: 'needs_review'
    }
  ];

  const all = { query: '', resolution: 'all', source: 'all', plex: 'all' };
  assert.deepEqual(filterUnmatchedItems(items, { ...all, query: '1995' }), [items[0]]);
  assert.deepEqual(filterUnmatchedItems(items, { ...all, plex: 'plex-unmatched' }), [items[1], items[2]]);
  assert.deepEqual(filterUnmatchedItems(items, { ...all, plex: 'tmdb-unmatched' }), [items[1]]);
  assert.deepEqual(filterUnmatchedItems(items, { ...all, plex: 'pending' }), [items[0]]);
  assert.deepEqual(filterUnmatchedItems(items, { ...all, plex: 'conflict' }), [items[1]]);
  assert.deepEqual(filterUnmatchedItems(items, { ...all, plex: 'needs_review' }), [items[2]]);
});

test('filterIdentityReviewItems searches identities and filters classifications', () => {
  const items = [
    {
      filename: 'Ick.2024.mkv',
      classification: 'recommended',
      current: { title: 'The Ick', year: '2024' },
      candidate: { title: 'Ick', year: '2025' }
    },
    {
      filename: 'Love.2011.mp4',
      classification: 'review',
      current: { title: 'Love', year: '2011' },
      candidate: { title: 'Money or Love', year: '2011' }
    },
    {
      filename: 'Weak.Match.2011.mp4',
      classification: 'weak',
      current: { title: 'Weak', year: '2011' },
      candidate: { title: 'Weak Match', year: '2011' }
    }
  ];

  assert.deepEqual(
    filterIdentityReviewItems(items, { query: 'money', identity: 'all' }).map((item) => item.filename),
    ['Love.2011.mp4']
  );
  assert.deepEqual(
    filterIdentityReviewItems(items, { query: '', identity: 'recommended' }).map((item) => item.filename),
    ['Ick.2024.mkv']
  );
  assert.deepEqual(
    filterIdentityReviewItems(items, { query: '', identity: 'weak' }).map((item) => item.filename),
    ['Weak.Match.2011.mp4']
  );
});

test('renameModalItem preserves suggested title and year precedence', () => {
  const item = {
    title: 'Fallback Title (1980)',
    suggested_title: 'Suggested Title',
    suggested_year: 1981,
    path: 'E:/Movies/Fallback Title.mkv'
  };

  assert.deepEqual(renameModalItem(item), {
    ...item,
    title: 'Suggested Title (1981)'
  });
  assert.equal(renameModalItem({ title: 'Heat (1995)' }).title, 'Heat (1995)');
});

test('metadata status display helpers preserve current labels and chip classes', () => {
  assert.equal(metadataStatusLabel({ metadata_status: 'pending' }), 'Pending metadata');
  assert.equal(metadataStatusLabel({ metadata_status: 'conflict' }), 'Conflict');
  assert.equal(metadataStatusLabel({ metadata_status: 'needs_review' }), 'Needs review');
  assert.equal(metadataStatusLabel({ in_plex: true, plex_matched: false, tmdb_id: 1 }), 'Plex unmatched');
  assert.equal(metadataStatusLabel({ in_plex: false, tmdb_id: '' }), 'TMDB unmatched');
  assert.equal(metadataStatusLabel({ tmdb_id: 1 }), 'Unmatched metadata');

  assert.equal(metadataStatusChipClass({ metadata_status: 'pending' }), 'chip-warning');
  assert.equal(metadataStatusChipClass({ metadata_status: 'conflict' }), 'chip-warning');
  assert.equal(metadataStatusChipClass({ metadata_status: 'needs_review' }), 'status-missing');
});
