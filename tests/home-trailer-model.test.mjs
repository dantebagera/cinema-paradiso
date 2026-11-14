import { test } from 'node:test';
import assert from 'node:assert/strict';
import { groupHomeTrailers, trailerPresentation } from '../src/features/home/homeTrailerModel.js';

test('groups alternate trailer versions without losing their original playback identity', () => {
  const first = { video_id: 'one', source_id: 'a', title: 'The Exorcist: Martyrs Trailer #1 (2027)' };
  const second = { video_id: 'two', source_id: 'b', title: 'THE EXORCIST: MARTYRS Official Trailer (2027)' };
  const remake = { video_id: 'three', source_id: 'a', title: 'The Exorcist: Martyrs Trailer (2030)' };
  const groups = groupHomeTrailers([first, second, first, remake]);
  assert.equal(groups.length, 2);
  assert.deepEqual(groups[0].videos, [first, second]);
  assert.equal(groups[0].title, 'The Exorcist: Martyrs');
  assert.deepEqual(groupHomeTrailers([first, second], 'b')[0].videos, [second]);
});

test('labels videos from their supplied title without claiming unofficial teasers are official', () => {
  for (const [title, type] of [['Film Teaser', 'Teaser'], ['Film Official Teaser Trailer', 'Official teaser'], ['Film Fan Edit Trailer', 'Fan edit'], ['Film Featurette', 'Featurette'], ['Film Trailer #1', 'Trailer']]) {
    assert.equal(trailerPresentation({title}).type, type);
  }
  assert.deepEqual(groupHomeTrailers(null), []);
});
