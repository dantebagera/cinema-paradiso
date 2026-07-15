import assert from 'node:assert/strict';
import test from 'node:test';

import {
  filterIdentityReviewItems,
  metadataStatusChipClass,
  metadataStatusLabel,
  renameModalItem
} from '../src/utils/cleanupUtils.js';

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
  assert.equal(metadataStatusLabel({ metadata_status: 'unverified' }), 'Verification gap');
  assert.equal(metadataStatusLabel({ metadata_status: 'review' }), 'Needs review');
  assert.equal(metadataStatusLabel({ metadata_status: 'needs_review' }), 'Needs review');
  assert.equal(metadataStatusLabel({ in_plex: true, plex_matched: false, tmdb_id: 1 }), 'Plex unmatched');
  assert.equal(metadataStatusLabel({ in_plex: false, tmdb_id: '' }), 'TMDB unmatched');
  assert.equal(metadataStatusLabel({ tmdb_id: 1 }), 'Unmatched metadata');

  assert.equal(metadataStatusChipClass({ metadata_status: 'pending' }), 'chip-warning');
  assert.equal(metadataStatusChipClass({ metadata_status: 'conflict' }), 'chip-warning');
  assert.equal(metadataStatusChipClass({ metadata_status: 'unverified' }), 'chip-warning');
  assert.equal(metadataStatusChipClass({ metadata_status: 'review' }), 'chip-warning');
  assert.equal(metadataStatusChipClass({ metadata_status: 'needs_review' }), 'status-missing');
});
