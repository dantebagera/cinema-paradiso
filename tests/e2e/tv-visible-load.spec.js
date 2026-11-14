import { test, expect } from '@playwright/test';

test.skip(process.env.CP_TV_E2E !== '1', 'Requires disposable TV fixture server');
const deferred = () => { let resolve; const promise=new Promise(r=>{resolve=r;}); return {promise,resolve}; };

for (const outcome of ['success','error']) {
test(`Library auxiliary reads wait for the first catalog ${outcome} and remain usable`,async({page})=>{
  const held=deferred(), auxiliary=[]; let searches=0;
  page.on('request',request=>{
    const url=new URL(request.url());
    if(['/api/tv/catalog/options','/api/tv/maintenance','/api/tv/lists'].includes(url.pathname))auxiliary.push(url);
  });
  await page.route('**/api/tv/catalog/search',async route=>{
    searches++;
    if(searches===1){await held.promise;if(outcome==='error')return route.fulfill({status:503,json:{error:'Fixture TV unavailable'}});}
    return route.continue().catch(()=>{});
  });
  await page.goto('/library');
  const requested=page.waitForRequest(request=>request.url().endsWith('/api/tv/catalog/search'));
  await page.getByRole('tablist',{name:'Library media'}).getByRole('button',{name:'TV Shows',exact:true}).click();
  await requested;
  try {
    await expect(page.getByText('Loading TV shows…',{exact:true})).toBeVisible();
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    expect(auxiliary).toHaveLength(0);
    held.resolve();
    if(outcome==='error'){
      await expect(page.getByText('Fixture TV unavailable',{exact:true})).toBeVisible();
      await page.getByRole('button',{name:'Retry',exact:true}).click();
    }
    await expect(page.getByRole('link',{name:'Open Harbor Signals',exact:true})).toBeVisible();
    await expect.poll(()=>auxiliary.length).toBe(3);
    expect(auxiliary.find(url=>url.pathname==='/api/tv/lists').search).toBe('');
    await page.getByRole('tablist',{name:'Library media'}).getByRole('button',{name:'Movies',exact:true}).click();
    await page.getByRole('tablist',{name:'Library media'}).getByRole('button',{name:'TV Shows',exact:true}).click();
    expect(auxiliary).toHaveLength(3);
    expect(searches).toBe(outcome==='error'?2:1);
  } finally {held.resolve();}
});
}

test('Library controls can load choices while the initial catalog remains stalled',async({page})=>{
  const held=deferred();const auxiliary=[];
  page.on('request',request=>{
    const path=new URL(request.url()).pathname;
    if(['/api/tv/catalog/options','/api/tv/maintenance','/api/tv/lists'].includes(path))auxiliary.push(path);
  });
  await page.route('**/api/tv/catalog/search',async route=>{await held.promise;return route.continue().catch(()=>{});});
  await page.goto('/library');
  const requested=page.waitForRequest(request=>request.url().endsWith('/api/tv/catalog/search'));
  await page.getByRole('tablist',{name:'Library media'}).getByRole('button',{name:'TV Shows',exact:true}).click();
  await requested;
  try{
    await page.getByRole('button',{name:'Search, filters & selection',exact:true}).click();
    await expect.poll(()=>auxiliary.length,{timeout:2000}).toBe(3);
    await expect(page.getByRole('combobox',{name:'TV Genres'}).getByRole('option',{name:'Drama',exact:true})).toHaveCount(1);
    await expect(page.getByText('Loading TV shows…',{exact:true})).toBeVisible();
  }finally{held.resolve();}
});

test('visible Discover cards finish while offscreen details are held and every card still enriches',async({page})=>{
  const held=deferred(), batches=[]; let active=0,peak=0;
  const rows=Array.from({length:39},(_,index)=>({tmdb_id:index+1,id:null,media_type:'tv',title:`Batch Show ${index+1}`,
    first_air_date:'2020-01-01',poster_url:'https://image.tmdb.org/t/p/w342/fixture.jpg',genres:[],status:'',season_count:null,
    available_count:0,completed_count:0,watchlisted:false}));
  await page.route('**/api/tmdb/discover/advanced',route=>route.fulfill({json:{results:[],page:1,total_pages:1,total_results:0}}));
  await page.route('**/api/tv/catalog/search',route=>route.fulfill({json:{items:rows,page:1,page_size:39,total:39,total_pages:1,complete:true}}));
  await page.route('**/api/tv/catalog/enrich',async route=>{
    const ids=route.request().postDataJSON().ids;batches.push(ids);active++;peak=Math.max(peak,active);
    try{
      if(ids.some(id=>id>12))await held.promise;
      await route.fulfill({json:{items:ids.map(tmdb_id=>({tmdb_id,status:'Ended',season_count:2,episode_count:16}))}});
    }catch{}finally{active--;}
  });
  await page.goto('/discover');
  await page.getByRole('tablist',{name:'Discover tools'}).getByRole('button',{name:'TV Shows',exact:true}).click();
  const cards=page.locator('.tv-discover-workspace .tv-series-card');
  try{
    await expect(cards).toHaveCount(39);
    await expect(cards.first()).toContainText('2 seas.',{timeout:2000});
    const visible=await cards.evaluateAll(elements=>elements.filter(element=>{
      const rect=element.getBoundingClientRect();return rect.width>0&&rect.bottom>0&&rect.top<innerHeight;
    }).map(element=>element.textContent));
    expect(visible.length).toBeGreaterThan(0);
    expect(visible.every(text=>text.includes('2 seas.'))).toBe(true);
    expect(active).toBeGreaterThan(0);
    held.resolve();
    await expect.poll(async()=>await cards.filter({hasText:'2 seas.'}).count()).toBe(39);
    expect(batches.flat().sort((a,b)=>a-b)).toEqual(rows.map(row=>row.tmdb_id));
    expect(peak).toBeLessThanOrEqual(2);
    expect(batches.every(batch=>batch.length<=20)).toBe(true);
  }finally{held.resolve();}
});

test('TV Library fetches nearby posters first and loads distant posters when scrolled into view',async({page})=>{
  const requested=new Set();
  const rows=Array.from({length:39},(_,i)=>({tmdb_id:i+1,id:null,title:`Poster Show ${i+1}`,media_type:'tv',
    poster_url:`https://image.tmdb.org/t/p/w342/poster-${i+1}.jpg`,first_air_date:'2020-01-01',season_count:1,status:'Ended',genres:[]}));
  await page.route('**/api/tv/catalog/search',route=>route.fulfill({json:{items:rows,page:1,page_size:39,total:39,total_pages:1,complete:true}}));
  await page.route('**/t/p/w342/poster-*.jpg',route=>{
    requested.add(Number(new URL(route.request().url()).pathname.match(/poster-(\d+)/)[1]));
    return route.fulfill({path:process.env.CP_TV_E2E_ARTWORK,contentType:'image/svg+xml'});
  });
  await page.goto('/library');
  await page.getByRole('tablist',{name:'Library media'}).getByRole('button',{name:'TV Shows',exact:true}).click();
  const cards=page.locator('.tv-library-workspace .tv-series-card');
  await expect(cards).toHaveCount(39);
  await expect.poll(()=>cards.first().locator('img').evaluate(img=>img.naturalWidth)).toBeGreaterThan(0);
  const distantIndex=await cards.evaluateAll(elements=>elements.findIndex(element=>{
    const rect=element.getBoundingClientRect();return rect.top>innerHeight+250&&rect.top<innerHeight+1800;
  }));
  expect(distantIndex).toBeGreaterThan(0);
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  expect(requested.has(distantIndex+1)).toBe(false);
  const target=cards.nth(distantIndex);
  await target.scrollIntoViewIfNeeded();
  await expect.poll(()=>requested.has(distantIndex+1)).toBe(true);
  await expect.poll(()=>target.locator('img').evaluate(img=>img.naturalWidth)).toBeGreaterThan(0);
  await expect(target.locator('img')).toHaveAttribute('src',rows[distantIndex].poster_url);
  await expect(target.locator('img')).toHaveCSS('object-fit','contain');
});
