import {test,expect} from '@playwright/test';

import {fixtures, movies} from './movieRatingsFixtures.js';

for(const width of [1366,1600,1920])test(`RT shares the bottom rating row and the expanded header between awards and TMDB at ${width}`,async({page})=>{
  await page.setViewportSize({width,height:width===1366?768:width===1600?1000:1080});
  await fixtures(page,{awards:true,score:100,crowded:true});
  await page.goto('/discover');
  const card=page.locator('.unified-movie-card').first();
  await expect(card.locator('.unified-rating-row > .movie-rt-pair[data-rt-visible="true"]')).toBeVisible();
  await expect(card.locator('.unified-rating')).toHaveText('7.8 - 1.2M');
  const bottom=await card.locator('.unified-rating-row').evaluate(e=>{
    const rects=[...e.children].map(x=>x.getBoundingClientRect());
    return {height:e.getBoundingClientRect().height,sameRow:rects.every(r=>r.top<rects[0].bottom&&r.bottom>rects[0].top),
      overlap:rects.some((a,i)=>rects.slice(i+1).some(b=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top))};
  });
  expect(bottom).toEqual({height:24,sameRow:true,overlap:false});
  await expect(card.locator('.unified-movie-poster .movie-rt-pair')).toHaveCount(0);
  await card.locator('h3').click();
  await expect(card.locator('.unified-movie-header-meta > .movie-awards + .movie-rt-pair + .unified-expanded-rating')).toBeVisible();
  await expect(card.locator('.unified-chip-row .movie-rt-pair')).toHaveCount(0);
  await expect(card.locator('.unified-expanded-rating small')).toHaveText('1.2M votes');
  const title=await card.locator('h3').evaluate(e=>({height:e.clientHeight,scroll:e.scrollHeight,clamp:getComputedStyle(e).webkitLineClamp}));
  expect(title.scroll).toBeLessThanOrEqual(title.height+1);
  expect(title.clamp).toBe('none');
  const header=await card.locator('.unified-movie-header').evaluate(e=>{
    const title=e.querySelector('h3').getBoundingClientRect();
    const group=e.querySelector('.unified-movie-header-meta').getBoundingClientRect();
    const children=[...e.querySelector('.unified-movie-header-meta').children].map(x=>x.getBoundingClientRect());
    return {titleClear:title.right<=group.left,titleWrap:title.height>parseFloat(getComputedStyle(e.querySelector('h3')).lineHeight)*1.5,
      sameRow:children.filter(r=>r.width>0).every(r=>r.top<group.top+4),
      overlap:children.some((a,i)=>children.slice(i+1).some(b=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top))};
  });
  if(width===1366)expect(header.titleWrap).toBe(true);
  expect(header).toMatchObject({titleClear:true,sameRow:true,overlap:false});
});

test('held poster prevents every RT request; scores arrive without changing card boxes',async({page})=>{
  let release;const heldPoster=new Promise(r=>release=r);
  const calls=await fixtures(page,{heldPoster});
  await page.goto('/discover');
  const card=page.locator('.unified-movie-card').first();await expect(card).toBeVisible();
  const before=await card.boundingBox();
  await page.waitForTimeout(800);expect(calls).toHaveLength(0);
  release();
  await expect(card.locator('[data-rt-icon="rotten"]')).toBeVisible();
  await expect(card.locator('[data-rt-icon="spilled"]')).toBeVisible();
  const after=await card.boundingBox();expect(after).toEqual(before);
  expect(calls.flatMap(c=>c.items).length).toBeLessThan(40);
  await page.screenshot({path:'test-results/rt-collapsed.png',fullPage:false});
});

test('a busy browser does not run ratings through a forced idle timeout',async({page})=>{
  const calls=await fixtures(page);
  await page.addInitScript(()=>{
    const native=window.requestIdleCallback.bind(window),pending=[];
    window.requestIdleCallback=callback=>{pending.push(callback);return pending.length;};
    window.releaseRatingsIdle=()=>{window.requestIdleCallback=native;for(const callback of pending)native(callback);};
  });
  await page.goto('/discover');
  const card=page.locator('.unified-movie-card').first();
  await expect(card).toBeVisible();
  await page.waitForTimeout(1600);expect(calls).toHaveLength(0);
  await card.locator('h3').click();await expect(card).toHaveClass(/unified-movie-card-expanded/);
  await page.evaluate(()=>window.releaseRatingsIdle());
  await expect(card.locator('[data-rt-visible="true"]')).toBeVisible();
});

test('30-second held ratings never block expansion and card actions',async({page})=>{
  test.setTimeout(45000);
  let release;const heldRatings=new Promise(r=>release=r);
  const calls=await fixtures(page,{heldRatings});
  await page.goto('/discover');
  const card=page.locator('.unified-movie-card').first();await expect(card).toBeVisible();
  await expect.poll(()=>calls.length).toBeGreaterThan(0);
  await card.locator('h3').click();
  await expect(card).toHaveClass(/unified-movie-card-expanded/);
  await expect(card.getByRole('button',{name:/Trailer/}).first()).toBeVisible();
  await page.waitForTimeout(30000);
  await expect(card.locator('h3')).toBeVisible();
  release();
});

test('percentages, four icons, missing and zero render from returned values',async({page})=>{
  await fixtures(page,{score:0});await page.goto('/discover');
  const card=page.locator('.unified-movie-card').first();
  await expect(card.getByLabel('Rotten Tomatoes® critics: 0%',{exact:true})).toBeVisible();
  await expect(card.locator('[data-rt-icon="spilled"]')).toBeVisible();
  await card.locator('h3').click();
  await expect(card.getByText('Critics',{exact:true})).toBeVisible();
  await card.getByLabel('Rotten Tomatoes® critics: 0%',{exact:true}).click();
  await expect(card).toHaveClass(/unified-movie-card-expanded/);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('tooltip')).toBeVisible();
  await page.keyboard.press('Escape');
  await page.screenshot({path:'test-results/rt-expanded.png'});
});

for(const {crowded,noStar} of [{crowded:false},{crowded:true},{crowded:true,noStar:true}])for(const width of [1366,1600,1920])test(`baseline card geometry is preserved at ${width}${crowded?' with crowded metadata':''}${noStar?' without star or awards':''}`,async({browser})=>{
  const boxes=[];
  for(const port of [5129,5128]){
    const page=await browser.newPage({viewport:{width,height:width===1366?768:width===1600?1000:1080}});
    await fixtures(page,{awards:!noStar,score:100,crowded,noStar});await page.goto(`http://127.0.0.1:${port}/discover`);
    await expect(page.locator('.unified-movie-card').first()).toBeVisible();
    await page.waitForTimeout(600);
    boxes.push(await page.locator('.unified-movie-card').evaluateAll(cards=>cards.slice(0,6).map(card=>{
      const r=card.getBoundingClientRect(),p=card.querySelector('.unified-movie-poster').getBoundingClientRect();
      return {x:r.x,y:r.y,width:r.width,height:r.height,poster:[p.width,p.height],overflow:card.scrollWidth>card.clientWidth};
    })));
    await page.locator('.unified-movie-card h3').first().click();
    await expect(page.locator('.unified-movie-card-expanded')).toBeVisible();
    await page.waitForTimeout(300);
    boxes.push(await page.locator('.unified-movie-card-expanded').evaluate(card=>{
      const r=card.getBoundingClientRect(),p=card.querySelector('.unified-movie-poster').getBoundingClientRect();
      return {width:r.width,height:r.height,poster:[p.width,p.height],awards:card.querySelectorAll('.movie-award-pair').length,overflow:card.scrollWidth>card.clientWidth};
    }));
    if(port===5128){
      const overlaps=await page.locator('.unified-movie-card-expanded .unified-chip-row').evaluate(row=>{
        const rects=[...row.children].map(e=>e.getBoundingClientRect());
        return rects.some((a,i)=>rects.slice(i+1).some(b=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top));
      });
      expect(overlaps).toBe(false);
      await page.screenshot({path:`test-results/rt-approved-${width}${crowded?'-crowded':''}${noStar?'-no-star':''}.png`});
    }
    await page.close();
  }
  if(crowded&&noStar){
    // Dante approved up to4px growth only when this new RT row had no
    // existing TMDB rating or awards row to share. Preserve every other box.
    for(let i=0;i<boxes[2].length;i++){
      const actual=boxes[2][i],original=boxes[0][i];
      expect(actual).toEqual({...original,height:actual.height,y:actual.y});
      expect(actual.height-original.height).toBeGreaterThanOrEqual(0);
      expect(actual.height-original.height).toBeLessThanOrEqual(4);
      expect(actual.y-original.y).toBeGreaterThanOrEqual(0);
      expect(actual.y-original.y).toBeLessThanOrEqual(4*Math.floor(i/(width===1920?3:2)));
    }
  }else expect(boxes[2]).toEqual(boxes[0]);
  // Dante explicitly requested expanded titles wrap beside the rating group.
  // In the shortest desktop viewport this adds one line, without changing the
  // poster, width, awards or overflow. Collapsed geometry remains exact above.
  if(width===1366&&!noStar){
    expect(boxes[3]).toEqual({...boxes[1],height:boxes[3].height});
    expect(boxes[3].height-boxes[1].height).toBeGreaterThanOrEqual(0);
    expect(boxes[3].height-boxes[1].height).toBeLessThanOrEqual(20);
  }else expect(boxes[3]).toEqual(boxes[1]);
});

test('scrolling pauses requests and publication, hidden workspaces stop demand',async({page})=>{
  const calls=await fixtures(page);
  await page.addInitScript(()=>{window.rtBusy=setInterval(()=>window.dispatchEvent(new Event('scroll')),40);});
  await page.goto('/discover');await expect(page.locator('.unified-movie-card').first()).toBeVisible();
  await page.waitForTimeout(500);expect(calls.length).toBe(0);
  await page.evaluate(()=>clearInterval(window.rtBusy));
  await expect.poll(()=>calls.length).toBeGreaterThan(0);
  const first=page.locator('.unified-movie-card').first();
  await expect(first.locator('[data-rt-visible="true"]')).toBeVisible();
  const count=calls.length;
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  await page.waitForTimeout(1300);expect(calls.length).toBe(count);
});

test('configuration invalidation immediately hides cached unowned content without errors',async({page})=>{
  await fixtures(page,{score:60});await page.goto('/discover');
  const pair=page.locator('.unified-movie-card').first().locator('.movie-rt-pair');
  await expect(pair.locator('[data-rt-icon="fresh"]')).toBeVisible();
  await expect(pair.locator('[data-rt-icon="upright"]')).toBeVisible();
  await page.route('**/api/movie-ratings/*',route=>route.fulfill({json:{owner:'offline',plex:{state:'not_configured',valid_until:0},items:{}}}));
  await page.evaluate(()=>window.dispatchEvent(new Event('cp-ratings-config-changed')));
  await expect(pair).toHaveAttribute('data-rt-visible','false');
  await expect(pair.locator('[tabindex]')).toHaveCount(0);
  await expect(page.getByText('Cinema Paradiso hit a display error.')).toHaveCount(0);
});

test('a newly mounted cached card waits for its subscription before showing scores',async({page})=>{
  let release;const heldPoster=new Promise(r=>release=r);
  await fixtures(page,{score:60});
  const movie={...movies[0],poster_url:'https://rt-fixture.test/held.svg'};
  await page.route('https://rt-fixture.test/held.svg',async route=>{await heldPoster;await route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="340" height="510"/>'});});
  await page.route('**/api/user/lists**',route=>route.fulfill({json:{lists:[{id:'watchlist',name:'Watchlist',system_type:'watchlist',movies:[movie]}],curation_generation:1}}));
  await page.goto('/discover');
  await expect(page.locator('.unified-movie-card').first().locator('[data-rt-visible="true"]')).toBeVisible();
  await page.route('**/api/tmdb/details**',route=>route.fulfill({json:movie}));
  await page.getByRole('button',{name:'Lists',exact:true}).click();
  const picker=page.getByRole('button',{name:/^Choose movies list:/});
  await picker.click();await page.locator('.lists-picker-options').getByRole('button',{name:/^Watchlist/}).click();
  const card=page.locator('.movie-lists-workspace .unified-movie-card').first();
  await expect(card).toBeVisible();
  await expect(card.locator('.unified-movie-poster img')).toHaveAttribute('src',movie.poster_url);
  expect(await card.locator('.unified-movie-poster img').evaluate(img=>img.complete)).toBe(false);
  await expect(card.locator('.movie-rt-pair')).toHaveAttribute('data-rt-visible','false');
  await page.route('**/api/movie-ratings/*',route=>route.fulfill({json:{owner:'offline',plex:{state:'not_configured',valid_until:0},items:{}}}));
  await page.evaluate(()=>window.dispatchEvent(new Event('cp-ratings-config-changed')));
  await expect(card.locator('.movie-rt-pair')).toHaveAttribute('data-rt-visible','false');
  release();
  await page.waitForTimeout(500);
  await expect(card.locator('.movie-rt-pair')).toHaveAttribute('data-rt-visible','false');
});

test('real service normalizes Plex values through API to icons, persists owned and hides unowned offline',async({page,request})=>{
  await request.post('http://127.0.0.1:5130/fixture/control',{data:{connected:true,owned:true}});
  await fixtures(page,{ratingsBackend:true});
  await page.goto('http://127.0.0.1:5130/discover');
  const owned=page.locator('.unified-movie-card').nth(0),unowned=page.locator('.unified-movie-card').nth(1);
  await expect(owned.getByLabel('Rotten Tomatoes® critics: 59%',{exact:true})).toBeVisible();
  await expect(owned.locator('[data-rt-icon="rotten"]')).toBeVisible();
  await expect(owned.getByLabel('Rotten Tomatoes® audience: 60%',{exact:true})).toBeVisible();
  await expect(owned.locator('[data-rt-icon="upright"]')).toBeVisible();
  await expect(unowned.locator('[data-rt-visible="true"]')).toBeVisible();
  const disconnected=await request.post('http://127.0.0.1:5130/fixture/control',{data:{connected:false}});
  const calls=(await disconnected.json()).calls;
  await page.evaluate(()=>window.dispatchEvent(new Event('cp-ratings-config-changed')));
  await expect(unowned.locator('.movie-rt-pair')).toHaveAttribute('data-rt-visible','false');
  await expect(owned.getByLabel('Rotten Tomatoes® critics: 59%',{exact:true})).toBeVisible();
  await page.reload();
  await expect(owned.getByLabel('Rotten Tomatoes® critics: 59%',{exact:true})).toBeVisible();
  expect((await (await request.get('http://127.0.0.1:5130/fixture/state')).json()).calls).toBe(calls);
});

test('a missing score stays a dash without a verdict icon',async({page})=>{
  await fixtures(page,{score:null,audienceScore:60});await page.goto('/discover');
  const card=page.locator('.unified-movie-card').first();
  const missing=card.getByLabel('No critics score available',{exact:true});
  await expect(missing).toHaveText('—');await expect(missing.locator('svg')).toHaveCount(0);
  await expect(card.getByLabel('Rotten Tomatoes® audience: 60%',{exact:true})).toBeVisible();
});

for(const surface of ['Library','Lists','Home','IPTV','AI','Indexers'])test(`${surface} passes accepted Movie IDs to the shared ratings display`,async({page})=>{
  const calls=await fixtures(page,{score:95});const movie=movies[0];
  if(surface==='Library'){
    const item={...movie,path:'C:/fixture/movie.mkv',metadata_accepted:true,canonical_metadata:{...movie,accepted:true}};
    await page.route('**/api/library/search/advanced',route=>route.fulfill({json:{items:[item],total:1,page:1,total_pages:1,page_start:0,page_end:1,catalog_generation:1,facets:{genres:[],countries:[],languages:[],sources:[]},stats:{total:1,matched:1,pending:0,unmatched:0,low:0}}}));
    await page.goto('/library');
  }else if(surface==='Lists'){
    await page.route('**/api/user/lists**',route=>route.fulfill({json:{lists:[{id:'watchlist',name:'Watchlist',system_type:'watchlist',movies:[movie]}],curation_generation:1}}));
    await page.goto('/movie-lists');
    const picker=page.getByRole('button',{name:/^Choose movies list:/});
    await picker.click();await page.locator('.lists-picker-options').getByRole('button',{name:/^Watchlist/}).click();
  }else if(surface==='Home'){
    await page.route('**/api/tmdb/discover?**',route=>route.fulfill({json:{results:[movie],page:1,total_pages:1,has_next:false}}));
    await page.goto('/');
    await expect(page.locator('.home-trending-track .upcoming-movie-card').first()).toBeVisible();
    await page.waitForTimeout(300);expect(calls.length).toBe(0);
    await page.locator('.home-trending-track .upcoming-movie-card').first().click();
  }else if(surface==='AI'){
    await page.route('**/api/ai/config',route=>route.fulfill({json:{provider:'ollama',generation:1,features:[{id:'movie_recommendations',ready:true}]}}));
    await page.route('**/api/ollama/recommend',route=>route.fulfill({json:{results:[movie],model:'fixture'}}));
    await page.goto('/discover');await page.getByRole('button',{name:'Pick My Movie',exact:true}).click();
    const prompt=page.getByPlaceholder('Something funny but a little sad, maybe an indie movie with a warm ending...');
    if(!await prompt.isVisible())await page.getByRole('button',{name:'Search, filters & selection',exact:true}).click();
    await prompt.fill('Synthetic ratings fixture');await page.getByRole('button',{name:'Ask AI',exact:true}).click();
  }else if(surface==='Indexers'){
    await page.route('**/api/explore/indexers',route=>route.fulfill({json:{indexers:[]}}));
    await page.route('**/api/explore/browse?**',route=>route.fulfill({json:{results:[{...movie,metadata:movie,parsed_title:movie.title,parsed_year:movie.year,variants:[{title:'Fixture release',seeders:10,resolution:'1080p',indexer:'Fixture',size_human:'2 GB'}]}]}}));
    await page.route('**/api/metadata?**',route=>route.fulfill({json:movie}));
    await page.goto('/discover');await page.getByRole('button',{name:'Browse Indexers',exact:true}).click();
    if(!await page.getByRole('button',{name:'Load latest',exact:true}).isVisible())await page.getByRole('button',{name:'Search, filters & selection',exact:true}).click();
    await page.getByRole('button',{name:'Load latest',exact:true}).click();
  }else{
    await page.route('**/api/iptv/providers',route=>route.fulfill({json:{providers:[{provider_id:'fixture',name:'Fixture',configured:true}],last_selected_provider_id:'fixture'}}));
    await page.route('**/api/iptv/providers/fixture/status',route=>route.fulfill({json:{configured:true,catalog_ready:true,generation:1,last_sync_at:new Date().toISOString(),counts:{movie:2,live:0,series:0}}}));
    await page.route('**/api/iptv/providers/fixture/movies?**',route=>route.fulfill({json:{items:[{...movie,movie_key:'tmdb:'+movie.tmdb_id,matched:true,image_url:movie.poster_url,metadata_status:'matched-manual'}, {movie_key:'unmatched:1',name:'Unmatched fixture',tmdb_id:'99999',matched:false}],total:2,page:1,total_pages:1}}));
    await page.goto('/iptv');await page.getByRole('button',{name:'Movies',exact:true}).click();await page.getByRole('button',{name:'CP View',exact:true}).click();
  }
  const card=page.locator('.unified-movie-card').filter({hasText:movie.title}).first();
  await expect(card.getByLabel('Rotten Tomatoes® critics: 95%',{exact:true})).toBeVisible();
  expect(calls.some(c=>c.items.some(i=>i.tmdb_id===movie.tmdb_id))).toBe(true);
  if(surface==='IPTV')expect(calls.flatMap(c=>c.items).some(i=>i.tmdb_id==='99999')).toBe(false);
});
