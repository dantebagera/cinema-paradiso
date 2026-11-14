import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ratingsIdentity, createMovieRatingsClient } from '../src/api/movieRatings.js';

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
test('identity rejects TV, empty and malformed data and preserves exact accepted IDs', () => {
  assert.equal(ratingsIdentity({ type: 'tv', tmdb_id: 1 }), null);
  assert.equal(ratingsIdentity({ tmdb_id: 'no' }), null);
  assert.equal(ratingsIdentity({ title: 'Movie' }), null);
  assert.equal(ratingsIdentity({ tmdb_id: '001', imdb_id: 'tt12345' }).key, 'movie:tmdb:1');
});
test('no work for hidden cards or while poster/input gates are closed; shared visible copies coalesce', async () => {
  let ready = false, visible = false;
  const calls = [];
  const client = createMovieRatingsClient({ eligible: () => ready, fetchBatch: async (route, items) => {
    calls.push({route, items});
    return { owner: 'one', plex: {state: 'available', valid_until: Date.now()/1000+300}, items: Object.fromEntries(items.map(i => [i.key, {state:'ready',owned:false,display_allowed:true,critics:95,audience:77}])) };
  }});
  const id = ratingsIdentity({tmdb_id:44012});
  const a = client.subscribe(id, () => visible, () => {});
  const b = client.subscribe(id, () => visible, () => {});
  await delay(100); assert.equal(calls.length,0);
  visible = true; client.wake(); await delay(100); assert.equal(calls.length,0);
  ready = true; client.wake(); await delay(150);
  assert.equal(calls.length,1); assert.equal(calls[0].items.length,1);
  assert.equal(client.get(id.key).critics,95);
  client.invalidate(); assert.equal(client.get(id.key),null);
  a(); b(); client.destroy();
});
test('late responses after invalidation cannot publish', async () => {
  let release;
  const client=createMovieRatingsClient({eligible:()=>true, fetchBatch:()=>new Promise(r=>{release=r;})});
  const id=ratingsIdentity({tmdb_id:1});
  const stop=client.subscribe(id,()=>true,()=>{});
  await delay(100); client.invalidate();
  release({owner:'old',plex:{state:'available',valid_until:9999999999},items:{[id.key]:{display_allowed:true,critics:90}}});
  await delay(20); assert.equal(client.get(id.key),null);
  stop();client.destroy();
});
test('late same-key response cannot overwrite a corrected accepted identity',async()=>{
  let release;
  const client=createMovieRatingsClient({eligible:()=>true,fetchBatch:()=>new Promise(r=>release=r)});
  const old=ratingsIdentity({tmdb_id:1,imdb_id:'tt11111'}),corrected=ratingsIdentity({tmdb_id:1,imdb_id:'tt22222'});
  const stop=client.subscribe(old,()=>true,()=>{});
  await delay(100);stop();
  const stopNew=client.subscribe(corrected,()=>true,()=>{});
  release({owner:'same',plex:{state:'available',valid_until:Date.now()/1000+300},items:{[old.key]:{state:'ready',display_allowed:true,owned:false,critics:99}}});
  await delay(30);assert.equal(client.get(corrected.key),null);
  stopNew();client.destroy();
});
test('pending visible polls renew backend demand using resolve, with one request in flight',async()=>{
  const calls=[];let resolves=0;
  const id=ratingsIdentity({tmdb_id:1});
  const client=createMovieRatingsClient({eligible:()=>true,fetchBatch:async route=>{
    calls.push(route);if(route==='resolve')resolves++;
    return {owner:'one',plex:{state:'available',valid_until:Date.now()/1000+300},items:{[id.key]:{state:route==='read'?'missing':resolves===1?'pending':'ready',display_allowed:resolves>1,owned:false,critics:70}}};
  }});
  const stop=client.subscribe(id,()=>true,()=>{});
  await delay(1450);assert.deepEqual(calls,['read','resolve','resolve']);assert.equal(client.get(id.key).critics,70);
  stop();client.destroy();
});
test('visible unavailable demand wakes once after backoff and recovers quietly',async()=>{
  const id=ratingsIdentity({tmdb_id:1});let calls=0;
  const client=createMovieRatingsClient({eligible:()=>true,fetchBatch:async()=>{
    calls++;
    return calls===1?{owner:'one',plex:{state:'unavailable',valid_until:0},items:{[id.key]:{state:'unavailable',owned:false,display_allowed:false,retry_at:Date.now()/1000+.15}}}:
      {owner:'one',plex:{state:'available',valid_until:Date.now()/1000+300},items:{[id.key]:{state:'ready',owned:false,display_allowed:true,critics:80}}};
  }});
  const stop=client.subscribe(id,()=>true,()=>{});
  await delay(350);assert.equal(calls,2);assert.equal(client.get(id.key).critics,80);
  stop();client.destroy();
});
test('a long retry timer cannot block another newly visible identity',async()=>{
  const calls=[];
  const client=createMovieRatingsClient({eligible:()=>true,fetchBatch:async(route,items)=>{
    calls.push(items.map(i=>i.key));
    return {owner:'same',plex:{state:'unavailable',valid_until:0},items:Object.fromEntries(items.map(i=>[i.key,{state:'unavailable',owned:false,display_allowed:false,retry_at:Date.now()/1000+1800}]))};
  }});
  const a=client.subscribe(ratingsIdentity({tmdb_id:1}),()=>true,()=>{});
  await delay(180);
  const b=client.subscribe(ratingsIdentity({tmdb_id:2}),()=>true,()=>{});
  await delay(120);assert.equal(calls.length,2);assert.deepEqual(calls[1],['movie:tmdb:2']);
  a();b();client.destroy();
});
test('compatible complete and partial identities both receive a verified result',async()=>{
  const basic=ratingsIdentity({tmdb_id:1}),full=ratingsIdentity({tmdb_id:1,imdb_id:'tt11111'});
  const client=createMovieRatingsClient({eligible:()=>true,fetchBatch:async()=>({owner:'same',plex:{state:'available',valid_until:Date.now()/1000+300},items:{[full.key]:{state:'ready',owned:false,display_allowed:true,critics:70}}})});
  const a=client.subscribe(full,()=>true,()=>{}),b=client.subscribe(basic,()=>true,()=>{});
  await delay(120);assert.equal(client.get(basic.key,basic).critics,70);assert.equal(client.get(full.key,full).critics,70);
  a();b();client.destroy();
});
test('expired negative cache resolves again rather than staying missing forever',async()=>{
  const routes=[],id=ratingsIdentity({tmdb_id:1});
  const client=createMovieRatingsClient({eligible:()=>true,fetchBatch:async route=>{
    routes.push(route);return {owner:'same',plex:{state:'available',valid_until:Date.now()/1000+300},items:{[id.key]:route==='read'?{state:'not_found',display_allowed:false,retry_at:Date.now()/1000-1}:{state:'ready',display_allowed:true,owned:false,critics:70}}};
  }});
  const stop=client.subscribe(id,()=>true,()=>{});
  await delay(200);assert.deepEqual(routes,['read','resolve']);assert.equal(client.get(id.key).critics,70);
  stop();client.destroy();
});
test('an optional cache failure retains saved owned session scores with current ownership',async()=>{
  const id=ratingsIdentity({tmdb_id:1});let failed=false;
  const client=createMovieRatingsClient({eligible:()=>true,fetchBatch:async()=>({owner:'same',cache_state:failed?'unavailable':'available',plex:{state:'not_configured',valid_until:0},items:{[id.key]:failed?{state:'unavailable',owned:true,display_allowed:false}:{state:'ready',owned:true,display_allowed:true,critics:95,stale:true}}})});
  const stop=client.subscribe(id,()=>true,()=>{});await delay(120);assert.equal(client.get(id.key).critics,95);
  failed=true;client.revisit();await delay(120);assert.equal(client.get(id.key).critics,95);
  stop();client.destroy();
});
test('a late accepted ownership answer rechecks an initially unavailable offline card',async()=>{
  const id=ratingsIdentity({tmdb_id:1});let owned=false,calls=0;
  const client=createMovieRatingsClient({eligible:()=>true,fetchBatch:async()=>{calls++;return {owner:'same',plex:{state:'not_configured',valid_until:0},items:{[id.key]:{state:owned?'ready':'unavailable',owned,display_allowed:owned,critics:owned?95:null}}};}});
  const stop=client.subscribe(id,()=>true,()=>{});await delay(120);assert.equal(client.get(id.key),null);
  owned=true;client.refresh([id]);await delay(120);assert.equal(client.get(id.key).critics,95);assert.equal(calls,2);
  stop();client.destroy();
});
