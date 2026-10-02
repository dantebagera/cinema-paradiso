import test from 'node:test';
import assert from 'node:assert/strict';
import { createAwardsCache, movieAwardCounts, personAwardCounts, positiveAwards, buildPersonAwardsContext } from '../src/api/movieAwards.js';

const snapshot = generation => ({schema_version:1,ready:true,awards_generation:generation,
  movies:{'tmdb:10':{entity_id:'movie:one',oscar:12,golden_globe:2},'imdb:tt10':{entity_id:'movie:one',oscar:12,golden_globe:2},'imdb:tt11':{entity_id:'movie:two',oscar:12,golden_globe:2}},
  people:{'tmdb:20':{actor:{oscar:1,golden_globe:2},director:{oscar:3,golden_globe:0}}}});
const response = (data,status=200) => ({ok:status<400,status,headers:{get:()=>`etag-${data?.awards_generation}`},json:async()=>data});

test('winning-film context carries exact person role and award without filmography or narrowed filters',()=>{
  const context=buildPersonAwardsContext({id:20,name:'Same name'},'director','golden_globe');
  assert.equal(context.type,'person-awards');assert.equal(context.owner,'person-awards');
  const params=new URL(context.baseUrl,'http://localhost').searchParams;
  assert.equal(params.get('person_id'),'20');assert.equal(params.get('role'),'director');assert.equal(params.get('award'),'golden_globe');
  assert.equal(context.availability,'all');assert.equal(context.query,undefined);
  assert.equal(buildPersonAwardsContext({id:20},'creator','oscar'),null);
});

test('canonical ID disagreement stays unavailable even when counts happen to match',()=>{
  assert.deepEqual(movieAwardCounts(snapshot(1),{tmdb_id:'10',imdb_id:'tt10'}),{oscar:12,golden_globe:2});
  assert.equal(movieAwardCounts(snapshot(1),{tmdb_id:10,imdb_id:'tt11'}),null);
  assert.equal(movieAwardCounts(snapshot(1),{tmdb_id:99,imdb_id:'tt10'}),null);
  assert.equal(movieAwardCounts(snapshot(1),{title:'Same name'}),null);
});
test('explicit role and opt-in isolate actor/director and excluded creator cards',()=>{
  assert.deepEqual(personAwardCounts(snapshot(1),20,'actor'),{oscar:1,golden_globe:2});
  assert.deepEqual(personAwardCounts(snapshot(1),20,'director'),{oscar:3,golden_globe:0});
  assert.equal(personAwardCounts(snapshot(1),20,'creator'),null);
  assert.equal(movieAwardCounts(snapshot(1),{tmdb_id:10},false),null);
  assert.deepEqual(positiveAwards({oscar:0,golden_globe:null}),[]);
  assert.deepEqual(positiveAwards({oscar:12,golden_globe:0}),[['oscar',12]]);
});
test('one concurrent snapshot request and ETag 304 preserve object identity',async()=>{
  let release,requests=0,headers;
  const cache=createAwardsCache({fetcher:async(url,options)=>{requests++;headers=options.headers;return requests===1?new Promise(r=>release=r):response(null,304);},visible:()=>true,now:()=>100000});
  const one=cache.revalidate(),two=cache.revalidate();assert.equal(requests,1);
  release(response(snapshot(2)));await Promise.all([one,two]);const original=cache.getSnapshot();
  await cache.revalidate();assert.equal(cache.getSnapshot(),original);assert.equal(headers['If-None-Match'],'etag-2');
});
test('older generation and failed reads retain last good counts',async()=>{
  let next=response(snapshot(3));const cache=createAwardsCache({fetcher:async()=>next});
  await cache.revalidate();const good=cache.getSnapshot();next=response(snapshot(2));await cache.revalidate();assert.equal(cache.getSnapshot(),good);
  next=response({},503);await cache.revalidate();assert.equal(cache.getSnapshot(),good);
});

test('a different userdata owner replaces cached counts even with a lower generation',async()=>{
  let next=response({...snapshot(8),snapshot_owner:'first-user'});
  const cache=createAwardsCache({fetcher:async()=>next});
  await cache.revalidate();
  next=response({...snapshot(1),snapshot_owner:'second-user'});
  await cache.revalidate();
  assert.equal(cache.getSnapshot().snapshot_owner,'second-user');
  assert.equal(cache.getSnapshot().awards_generation,1);
});
test('disabled and hidden consumers make no request; focus minimum is sixty seconds',async()=>{
  let requests=0,clock=100000,shown=false;
  const cache=createAwardsCache({fetcher:async()=>{requests++;return response(snapshot(1));},visible:()=>shown,now:()=>clock});
  cache.acquire(false);cache.focus();assert.equal(requests,0);
  const cleanup=cache.acquire(true);cache.focus();assert.equal(requests,0);
  shown=true;await cache.focus();assert.equal(requests,1);
  clock+=59000;await cache.focus();assert.equal(requests,1);
  clock+=1000;await cache.focus();assert.equal(requests,2);
  cleanup();clock+=60000;await cache.focus();assert.equal(requests,2);
});
