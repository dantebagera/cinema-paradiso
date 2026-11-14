import assert from 'node:assert/strict';
import test from 'node:test';
import { enrichTVCardBatches } from '../src/features/tv/tvCardEnrichment.js';

const deferred = () => { let resolve; const promise = new Promise(r => { resolve=r; }); return {promise,resolve}; };
test('visible identities complete before held offscreen work without increasing page concurrency',async()=>{
  const ids=Array.from({length:39},(_,i)=>i+1), held=deferred(), started=[],completed=[];
  let active=0,peak=0;
  const front=deferred();
  const done=enrichTVCardBatches(ids,[1,2,3,4],async batch=>{
    started.push(batch); active++; peak=Math.max(peak,active);
    if(batch.some(id=>id>4)) await held.promise;
    active--; return {items:batch};
  },result=>{completed.push(...result.items);if(completed.length===4)front.resolve();},new AbortController().signal);
  await front.promise;
  assert.deepEqual(completed,[1,2,3,4]); assert.equal(peak,2);
  held.resolve(); await done;
  assert.deepEqual([...completed].sort((a,b)=>a-b),ids);
  assert.equal(started.flat().length,39); assert.ok(started.every(b=>b.length<=20));
});
test('a short page keeps one request lane and failed details do not block remaining identities',async()=>{
  let active=0,peak=0; const started=[],completed=[];
  await enrichTVCardBatches([1,2,3,4,5],[1,2],async batch=>{
    started.push(batch);active++;peak=Math.max(peak,active);await Promise.resolve();active--;
    if(batch.includes(1))throw new Error('provider unavailable');return {items:batch};
  },result=>completed.push(...result.items),new AbortController().signal);
  assert.equal(peak,1);assert.deepEqual(started,[[1,2],[3,4,5]]);assert.deepEqual(completed,[3,4,5]);
});
test('abort stops queued work and ignores a late successful response',async()=>{
  const controller=new AbortController(), held=deferred(),started=[],completed=[];
  const done=enrichTVCardBatches([1,2,3,4],[1],async batch=>{started.push(batch);await held.promise;return {items:batch};},result=>completed.push(...result.items),controller.signal);
  controller.abort(); held.resolve(); await done;
  assert.deepEqual(started,[[1]]);assert.deepEqual(completed,[]);
});
