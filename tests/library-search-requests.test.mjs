import test from 'node:test';
import assert from 'node:assert/strict';
import { createLibrarySearchRequests } from '../src/features/library/librarySearchRequests.js';

const barrier = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
test('nine intents dispatch first and latest only; superseded callers settle', async () => {
  const gate = barrier(); const sent = []; let active = 0; let maximum = 0;
  const owner = createLibrarySearchRequests(async d => {
    sent.push(d); maximum = Math.max(maximum, ++active);
    if (sent.length === 1) await gate.promise;
    active--; return d.query;
  });
  const reads = Array.from({length: 9}, (_, revision) => owner.request({query: `term${revision}`, revision}));
  gate.resolve();
  const result = await Promise.all(reads);
  assert.equal(maximum, 1); assert.equal(sent.length, 2);
  assert.equal(sent[1].query, 'term8');
  assert.ok(result.slice(1, 8).every(r => r.status === 'superseded'));
  assert.equal(result[8].data, 'term8'); owner.dispose();
});
test('freshness requires another read; errors release the queue', async () => {
  const gate = barrier(); let calls = 0;
  const owner = createLibrarySearchRequests(async () => { calls++; if (calls === 1) { await gate.promise; throw new Error('offline'); } return 'fresh'; });
  const first = owner.request({query: 'x', freshness: 1});
  const error = assert.rejects(first, /offline/);
  const next = owner.request({query: 'x', freshness: 2}); gate.resolve();
  await error; assert.equal((await next).data, 'fresh'); assert.equal(calls, 2); owner.dispose();
});
test('dispose settles pending and prevents late completion', async () => {
  const gate = barrier(); const owner = createLibrarySearchRequests(() => gate.promise);
  const first = owner.request({revision: 1}); const next = owner.request({revision: 2});
  owner.dispose(); gate.resolve('late');
  assert.equal((await first).status, 'superseded'); assert.equal((await next).status, 'superseded');
});
