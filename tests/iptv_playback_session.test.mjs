import test from 'node:test';
import assert from 'node:assert/strict';
import { createIPTVPlaybackCoordinator } from '../src/features/iptv/iptvPlaybackSession.js';

test('choosing web in a different surface stops the active IPTV owner', async () => {
  const stopped = [];
  const coordinator = createIPTVPlaybackCoordinator({
    startPlayback: async () => ({ token: 'workspace-token' }),
    stopPlayback: async (provider, token) => stopped.push([provider, token]),
  });
  await coordinator.start('workspace', 'lionz', { kind: 'movie', item_id: '1' });
  await coordinator.stopActive('dialog');
  assert.deepEqual(stopped, [['lionz', 'workspace-token']]);
  assert.equal(coordinator.state().playback, null);
  assert.equal(coordinator.state().owner, 'dialog');
});

test('closing during a pending start disposes its late token', async () => {
  let finish;
  const stopped = [];
  const api = { startPlayback: () => new Promise(resolve => { finish = resolve; }),
    stopPlayback: async (provider, token) => stopped.push([provider, token]) };
  const coordinator = createIPTVPlaybackCoordinator(api);
  const owner = Symbol();
  const pending = coordinator.start(owner, 'a', { kind: 'movie', item_id: '1' });
  await Promise.resolve();
  await coordinator.stop(owner);
  finish({ token: 'late', manifest_url: '/late.m3u8' });
  assert.equal(await pending, null);
  assert.deepEqual(stopped, [['a', 'late']]);
  assert.equal(coordinator.state().playback, null);
});

test('switching owners stops the old exact provider session and preserves history identity', async () => {
  const stopped = [];
  const api = { startPlayback: async (provider, payload) => ({ token: provider, manifest_url: '/test.m3u8' }),
    stopPlayback: async (provider, token) => stopped.push([provider, token]) };
  const coordinator = createIPTVPlaybackCoordinator(api);
  await coordinator.start('workspace', 'a', { kind: 'movie', item_id: '1' });
  const next = await coordinator.start('dialog', 'b', { kind: 'movie', item_id: '2' }, { historyKind: 'movie', historyId: '2' });
  assert.deepEqual(stopped, [['a', 'a']]);
  assert.equal(next.provider_id, 'b');
  assert.equal(next.historyId, '2');
  await coordinator.stop('workspace');
  assert.equal(coordinator.state().playback.token, 'b');
});

test('a transient cleanup failure retries the same token before allowing the next source', async () => {
  let stops = 0;
  const starts = [];
  const coordinator = createIPTVPlaybackCoordinator({
    startPlayback: async provider => { starts.push(provider); return { token: provider }; },
    stopPlayback: async () => { if (++stops === 1) throw new Error('Temporary stop failure'); },
  });
  await coordinator.start('dialog', 'a', { kind: 'movie', item_id: '1' });
  await coordinator.start('dialog', 'b', { kind: 'movie', item_id: '2' });
  assert.deepEqual(starts, ['a', 'b']);
  assert.equal(stops, 2);
});
