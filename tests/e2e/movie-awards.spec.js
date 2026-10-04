import { expect, test } from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs';

test.use({viewport:{width:1920,height:1080},reducedMotion:'reduce'});
const portrait='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="106" height="132"><rect width="106" height="132" fill="#263038"/></svg>');
const movie=id=>({tmdb_id:String(id),title:id===1?'Award fixture':`Winning film ${id}`,year:'2024',tmdb_rating:id===1?'':'7.8',tmdb_vote_count:400,genres:['Drama'],summary:'A movie awards fixture.',poster_url:portrait});
const people={directors:[{id:90,name:'A long director name',profile_url:portrait}],cast:Array.from({length:9},(_,i)=>({id:100+i,name:`Actor ${i}`,character:'A long character name',profile_url:portrait}))};
async function fixtures(page) {
  await page.route('**/api/tmdb/discover**',route=>route.fulfill({json:{results:[movie(1),movie(4),movie(5)],page:1,total_pages:1,total_results:3}}));
  await page.route('**/api/library/check',route=>route.fulfill({json:{catalog_generation:1,results:route.request().postDataJSON().movies.map(row=>({...row,found:false}))}}));
  await page.route('**/api/tmdb/details**',route=>route.fulfill({json:{...movie(Number(new URL(route.request().url()).searchParams.get('tmdb_id'))),...people,runtime:110,certification:'PG-13'}}));
  await page.route('**/api/tmdb/related**',route=>route.fulfill({json:{results:Array.from({length:20},(_,i)=>movie(200+i)),page:1,total_pages:1,total_results:20,has_next:false}}));
  await page.route('**/api/user/lists',route=>route.fulfill({json:{lists:[],curation_generation:1}}));
}
const expanded=page=>page.locator('.unified-movie-card-expanded:visible');
const evidence=filename=>{const directory=path.resolve(process.env.CP_E2E_AWARDS_EVIDENCE_DIR || 'docs/verification/movie-awards/desktop');fs.mkdirSync(directory,{recursive:true});return path.join(directory,filename);};
async function open(page) {await fixtures(page);await page.goto('/discover');await page.getByRole('heading',{name:'Award fixture',exact:true}).click();await expect(expanded(page).locator('.person-card')).toHaveCount(10);}

for (const award of ['Oscars', 'Golden Globe']) {
  test(`${award} navigation restores detail-only plots through Arabic, repeated awards, and history`, async ({ page, request }, testInfo) => {
    await fixtures(page);
    const organization = award === 'Oscars' ? 'oscar' : 'golden_globe';
    const awardResponse = await request.get(`/api/movie-awards/person-films?person_id=100&role=actor&award=${organization}`);
    expect(awardResponse.ok()).toBeTruthy();
    const winning = (await awardResponse.json()).results.find(row => String(row.tmdb_id) === '2');
    expect(winning).toBeTruthy();
    expect(winning.summary || winning.plot || '').toBe('');

    await page.route('**/api/tmdb/details**', route => {
      const params = new URL(route.request().url()).searchParams;
      const id = Number(params.get('tmdb_id'));
      const arabic = params.get('language') === 'ar-SA';
      const { summary, ...base } = movie(id);
      return route.fulfill({ json: {
        ...base, ...people, runtime: 110,
        ...(arabic ? { title: `فيلم الجوائز ${id}` } : {}),
        plot: arabic ? `قصة الفيلم ${id}` : `Full English plot for winning film ${id}.`
      } });
    });

    await page.goto('/discover');
    await page.getByRole('heading', { name: 'Award fixture', exact: true }).click();
    await expect(expanded(page).locator('.person-card')).toHaveCount(10);
    await expect(expanded(page).locator('.movie-card-plot')).toHaveText('A movie awards fixture.');

    const actor = () => expanded(page).locator('.person-card').filter({ has: page.getByText('Actor 0', { exact: true }) });
    await actor().getByRole('button', { name: award, exact: true }).click();
    await page.getByRole('heading', { name: 'Winning film 2', exact: true }).click();
    const plot = () => expanded(page).locator('.movie-card-plot');
    await expect(plot()).toHaveText('Full English plot for winning film 2.');
    await expect(expanded(page).locator('.person-card')).toHaveCount(10);
    await expanded(page).getByRole('button', { name: 'العربية', exact: true }).click();
    await expect(plot()).toHaveText('قصة الفيلم 2');
    await expanded(page).getByRole('button', { name: 'English', exact: true }).click();
    await expect(plot()).toHaveText('Full English plot for winning film 2.');

    await actor().getByRole('button', { name: award === 'Oscars' ? 'Golden Globe' : 'Oscars', exact: true }).click();
    await page.getByRole('heading', { name: 'Winning film 1', exact: true }).click();
    await expect(plot()).toHaveText('Full English plot for winning film 1.');
    await page.getByLabel('Discovery path').getByRole('button', { name: 'Back', exact: true }).click();
    await expect(expanded(page).getByRole('heading', { name: 'Winning film 2', exact: true })).toBeVisible();
    await expect(plot()).toHaveText('Full English plot for winning film 2.');
    await page.goForward();
    await expect(page.getByRole('heading', { name: 'Winning film 1', exact: true })).toBeVisible();
    await page.getByRole('heading', { name: 'Winning film 1', exact: true }).click();
    await expect(plot()).toHaveText('Full English plot for winning film 1.');
    await expanded(page).screenshot({ path: testInfo.outputPath('restored-winning-plot.png') });
  });
}

test('real awards API: number-left icons, award-only footer, exact actor/director films and Back',async({page,request})=>{
  const api=await request.get('/api/movie-awards/person-films?person_id=100&role=actor&award=oscar');
  expect(api.ok()).toBeTruthy();const data=await api.json();expect(data.results.map(m=>m.id)).toEqual([1,2]);expect(data.award_wins).toBe(3);
  await fixtures(page);await page.goto('/discover');
  const card=page.locator('.discover-grid .unified-movie-card').filter({has:page.getByRole('heading',{name:'Award fixture',exact:true})});
  await expect(card.locator('.movie-awards')).toHaveCount(1);await expect(card.locator('.unified-rating')).toHaveCount(0);
  await expect(card.locator('.movie-award-oscar strong')).toHaveText('12');
  const pair=card.locator('.movie-award-oscar');const n=await pair.locator('strong').boundingBox(),icon=await pair.locator('img').boundingBox();expect(n.x+n.width).toBeLessThan(icon.x);
  await card.screenshot({path:evidence('collapsed-award-only.png')});
  await card.getByRole('heading').click();await expect(expanded(page).locator('.person-card')).toHaveCount(10);
  const actor=expanded(page).locator('.person-card').filter({has:page.getByText('Actor 0',{exact:true})});
  await expect(actor.getByRole('button',{name:'Oscars',exact:true})).toHaveAttribute('title','Oscars');
  await actor.getByRole('button',{name:'Oscars',exact:true}).press('Enter');
  await expect(page.locator('.discover-grid > .unified-movie-card')).toHaveCount(2);
  await expect(page.getByRole('heading',{name:'Winning film 1',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Winning film 2',exact:true})).toBeVisible();
  await expect(page.locator('.discover-toolbar')).toHaveCount(0);
  await page.getByRole('button',{name:'Back',exact:true}).click();
  await expect(expanded(page).getByRole('heading',{name:'Award fixture',exact:true})).toBeVisible();
  const director=expanded(page).locator('.director-person');
  await director.getByRole('button',{name:'Golden Globe',exact:true}).click();
  await expect(page.locator('.discover-grid > .unified-movie-card')).toHaveCount(1);
  await expect(page.getByRole('heading',{name:'Winning film 2',exact:true})).toBeVisible();
});

for(const size of [{width:1920,height:1080},{width:1600,height:1000},{width:1366,height:900},{width:1366,height:768}]) {
  test(`desktop geometry ${size.width}x${size.height}`,async({page})=>{
    await page.route('**/api/movie-awards/snapshot',async route=>{
      const response=await route.fetch();const data=await response.json();
      data.people['tmdb:90'].director={oscar:12,golden_globe:99};
      await route.fulfill({response,json:data});
    });
    await page.setViewportSize(size);await open(page);
    await expect(expanded(page).locator('.movie-awards')).toHaveCount(4);
    const geometry=await expanded(page).evaluate(card=>{
      const slot=card.querySelector('.movie-expanded-credits-slot').getBoundingClientRect();
      const awarded=[...card.querySelectorAll('.person-card-awards')].map(person=>{
        const avatar=person.querySelector('.person-avatar').getBoundingClientRect();
        const bounds=person.getBoundingClientRect();
        const bio=person.querySelector('.person-bio-button').getBoundingClientRect();
        const filmography=person.querySelector('.person-discover-button').getBoundingClientRect();
        const name=person.querySelector(':scope > strong').getBoundingClientRect();
        const pairs=[...person.querySelectorAll('.movie-award-pair')].map(pair=>{
          const b=pair.getBoundingClientRect(),number=pair.querySelector('strong').getBoundingClientRect(),icon=pair.querySelector('img').getBoundingClientRect();
          return {left:b.left,right:b.right,top:b.top,bottom:b.bottom,width:b.width,
            numberLeft:number.right<icon.left,contained:number.left>=b.left-.5&&icon.right<=b.right+.5,
            countUnclipped:pair.querySelector('strong').scrollWidth<=pair.querySelector('strong').clientWidth,
            fits:b.left>=bio.left-.5&&b.right<=bio.right+.5&&b.top>=filmography.bottom+2&&b.bottom<=name.top-2};
        });
        return {width:avatar.width,height:avatar.height,pairs};
      });
      const portraits=[...card.querySelectorAll('.person-avatar')].map(node=>node.getBoundingClientRect().width);
      return {slot:slot.height,awarded,portraitDelta:Math.max(...portraits)-Math.min(...portraits)};
    });
    expect(geometry.slot).toBe(238);expect(geometry.portraitDelta).toBeLessThanOrEqual(1);
    for(const person of geometry.awarded) {
      for(const pair of person.pairs){expect(pair.width).toBeLessThanOrEqual(28);expect(pair.fits).toBeTruthy();expect(pair.numberLeft).toBeTruthy();expect(pair.contained).toBeTruthy();expect(pair.countUnclipped).toBeTruthy();}
      if(person.pairs.length===2)expect(person.pairs[0].bottom).toBeLessThanOrEqual(person.pairs[1].top-2);
    }
    if(size.width===1920) for(const person of geometry.awarded){expect(Math.round(person.width)).toBe(106);expect(Math.round(person.height)).toBe(132);}
    await expanded(page).screenshot({path:evidence(`expanded-${size.width}x${size.height}.png`)});
  });
}

test('all 120 verified winning films are reachable through real pagination',async({request})=>{
  const ids=[];let generation;
  for(let page=1;page<=6;page++) {
    const response=await request.get(`/api/movie-awards/person-films?person_id=101&role=actor&award=oscar&page_size=20&page=${page}${generation?`&generation=${generation}`:''}`);
    expect(response.ok()).toBeTruthy();const data=await response.json();generation=data.awards_generation;ids.push(...data.results.map(r=>r.id));expect(data.total_results).toBe(120);expect(data.award_wins).toBe(1);
  }
  expect(new Set(ids).size).toBe(120);expect(ids.sort((a,b)=>a-b)).toEqual(Array.from({length:120},(_,i)=>i+30));
});

test('award keyboard Space keeps one history entry and browser Back/Forward restores the winning set',async({page})=>{
  await open(page);
  const button=expanded(page).locator('.director-person').getByRole('button',{name:'Oscars',exact:true});
  await page.keyboard.press('Tab');
  await button.focus();
  await expect(button).toBeFocused();
  expect(await button.evaluate(node=>getComputedStyle(node).outlineStyle)).not.toBe('none');
  await button.press('Space');
  await expect(page.getByRole('heading',{name:'Winning film 2',exact:true})).toBeVisible();
  await page.goBack();
  await expect(expanded(page).getByRole('heading',{name:'Award fixture',exact:true})).toBeVisible();
  await page.goForward();
  await expect(page.getByRole('heading',{name:'Winning film 2',exact:true})).toBeVisible();
  await expect(page.locator('.discover-grid > .unified-movie-card')).toHaveCount(1);
});

test('a late snapshot leaves the expanded card open and zero/unknown movie awards hidden',async({page})=>{
  let release;const waiting=new Promise(resolve=>release=resolve);
  await page.route('**/api/movie-awards/snapshot',async route=>{await waiting;await route.continue();});
  await open(page);
  await expect(expanded(page).locator('.movie-awards')).toHaveCount(0);
  const portraitSizes=()=>expanded(page).locator('.person-avatar').evaluateAll(nodes=>nodes.map(node=>{const b=node.getBoundingClientRect();return [b.width,b.height];}));
  const before=await portraitSizes();
  release();
  await expect(expanded(page).locator('.movie-award-oscar strong').first()).toHaveText('12');
  await expect(expanded(page).getByRole('heading',{name:'Award fixture',exact:true})).toBeVisible();
  expect(await portraitSizes()).toEqual(before);
  await expect(page.locator('.discover-grid > .unified-movie-card').filter({has:page.getByRole('heading',{name:'Winning film 4',exact:true})}).locator('.movie-awards')).toHaveCount(0);
});

test('a single Globe stays below the empty Oscar position and opens the real winning films',async({page})=>{
  await page.route('**/api/movie-awards/snapshot',async route=>{
    const response=await route.fetch();const data=await response.json();
    for(const person of Object.values(data.people))for(const role of ['actor','director'])person[role].oscar=0;
    await route.fulfill({response,json:data});
  });
  await open(page);
  const director=expanded(page).locator('.director-person');
  await expect(director.locator('.movie-award-oscar')).toHaveCount(0);
  const globe=director.getByRole('button',{name:'Golden Globe',exact:true});
  await expect(globe).toBeVisible();
  const bounds=await globe.boundingBox(),filmography=await director.locator('.person-discover-button').boundingBox();
  expect(bounds.y).toBeGreaterThan(filmography.y+filmography.height+20);
  await director.screenshot({path:evidence('person-single-globe.png')});
  await globe.click();
  await expect(page.getByRole('heading',{name:'Winning film 2',exact:true})).toBeVisible();
  await expect(page.locator('.discover-grid > .unified-movie-card')).toHaveCount(1);
});

test('first snapshot failure is quiet and regular details remain usable',async({page})=>{
  await page.route('**/api/movie-awards/snapshot',route=>route.fulfill({status:503,json:{error:'awards_unavailable'}}));
  await open(page);
  await expect(expanded(page).locator('.movie-awards')).toHaveCount(0);
  await expect(expanded(page).locator('.person-card')).toHaveCount(10);
  await expect(expanded(page).locator('.related-tile')).toHaveCount(16);
});

test('pending Globe coverage leaves only the positive Oscar pair visible',async({page})=>{
  await page.route('**/api/movie-awards/snapshot',async route=>{
    const response=await route.fetch();const data=await response.json();
    for(const value of Object.values(data.movies))value.golden_globe=null;
    for(const person of Object.values(data.people))for(const role of ['actor','director'])person[role].golden_globe=null;
    await route.fulfill({response,json:data});
  });
  await open(page);
  await expect(expanded(page).locator('.unified-movie-header-meta .movie-award-oscar')).toHaveCount(1);
  await expect(expanded(page).locator('.movie-award-golden_globe')).toHaveCount(0);
});

test('the same person has separate rendered acting and directing totals and winning-film membership',async({page,request})=>{
  const data=await (await request.get('/api/movie-awards/person-films?person_id=100&role=director&award=oscar')).json();
  expect(data.results.map(row=>row.id)).toEqual([3]);expect(data.award_wins).toBe(1);
  await fixtures(page);
  await page.route('**/api/tmdb/details**',route=>route.fulfill({json:{...movie(1),...people,directors:[{id:100,name:'Actor 0',profile_url:portrait}]}}));
  await page.goto('/discover');await page.getByRole('heading',{name:'Award fixture',exact:true}).click();
  const director=expanded(page).locator('.director-person');
  await expect(director.getByRole('button',{name:'Oscars',exact:true}).locator('strong')).toHaveText('1');
  const actor=expanded(page).locator('.person-card:not(.director-person)').filter({has:page.getByText('Actor 0',{exact:true})});
  await expect(actor.getByRole('button',{name:'Oscars',exact:true}).locator('strong')).toHaveText('3');
  await director.getByRole('button',{name:'Oscars',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Winning film 3',exact:true})).toBeVisible();
  await expect(page.locator('.discover-grid:visible > .unified-movie-card')).toHaveCount(1);
});

test('Back during a delayed award response discards its late winning films',async({page})=>{
  let release;const waiting=new Promise(resolve=>release=resolve);
  await page.route('**/api/movie-awards/person-films**',async route=>{await waiting;await route.continue();});
  await open(page);
  await expanded(page).locator('.director-person').getByRole('button',{name:'Oscars',exact:true}).click();
  await page.getByLabel('Discovery path').getByRole('button',{name:'Back',exact:true}).click();
  release();
  await expect(expanded(page).getByRole('heading',{name:'Award fixture',exact:true})).toBeVisible();
  await expect(page.locator('.discover-grid > .unified-movie-card')).toHaveCount(3);
});

test('an awards generation conflict retries page one once with the current real generation',async({page})=>{
  const requests=[];let initial=true;
  await page.route('**/api/movie-awards/person-films**',async route=>{
    requests.push(new URL(route.request().url()).searchParams);
    if(initial) {
      initial=false;const response=await route.fetch();const data=await response.json();
      return route.fulfill({response,json:{...data,awards_generation:99}});
    }
    return route.continue();
  });
  await open(page);
  await expanded(page).locator('.person-card').filter({has:page.getByText('Actor 1',{exact:true})}).getByRole('button',{name:'Oscars',exact:true}).click();
  const pagination=page.getByRole('navigation',{name:'TMDB relationship pagination',exact:true});
  await expect(pagination.getByRole('button',{name:'Next',exact:true})).toBeEnabled();
  await pagination.getByRole('button',{name:'Next',exact:true}).click();
  await expect(pagination.getByText(/^Page 1 of /)).toBeVisible();
  await expect.poll(()=>requests.length).toBe(3);
  expect(requests.map(params=>params.get('page'))).toEqual(['1','2','1']);
  expect(requests.map(params=>params.get('generation'))).toEqual([null,'99','1']);
});

test('Arabic display retains the canonical awards and number-left icon order',async({page})=>{
  await open(page);
  await page.route('**/api/tmdb/details**',route=>route.fulfill({json:{...movie(1),title:'فيلم الجوائز',summary:'قصة الفيلم',...people}}));
  await expanded(page).getByRole('button',{name:'العربية',exact:true}).click();
  await expect(expanded(page).getByRole('heading',{name:'فيلم الجوائز',exact:true})).toBeVisible();
  const pair=expanded(page).locator('.unified-movie-header-meta .movie-award-oscar');
  await expect(pair.locator('strong')).toHaveText('12');
  const number=await pair.locator('strong').boundingBox(),icon=await pair.locator('img').boundingBox();
  expect(number.x+number.width).toBeLessThan(icon.x);
  await expanded(page).screenshot({path:evidence('expanded-arabic.png')});
});

test('an owned candidate uses accepted movie counts instead of its conflicting raw ID',async({page})=>{
  await fixtures(page);
  const accepted={...movie(1),title:'Accepted winning identity',imdb_id:'tt0000001',accepted:true,summary:'Accepted description',...people};
  const owned={path:'E:/Movies/Accepted.mkv',title:accepted.title,metadata_accepted:true,resolution:'1080p',canonical_metadata:accepted};
  await page.route('**/api/tmdb/discover**',route=>route.fulfill({json:{results:[movie(4)],page:1,total_pages:1,total_results:1}}));
  await page.route('**/api/library/check',route=>route.fulfill({json:{catalog_generation:1,results:route.request().postDataJSON().movies.map(row=>({...row,found:true,path:owned.path,library_item:owned,canonical_card:owned}))}}));
  await page.route('**/api/library/details**',route=>route.fulfill({json:{item:owned,catalog_generation:1}}));
  await page.goto('/discover');
  const card=page.locator('.discover-grid:visible > .unified-movie-card');
  await expect(card.getByRole('heading',{name:accepted.title,exact:true})).toBeVisible();
  await expect(card.locator('.movie-award-oscar strong')).toHaveText('12');
  await card.getByRole('heading').click();
  await expect(expanded(page)).toContainText('Accepted description');
  await expect(expanded(page).locator('.unified-movie-header-meta .movie-award-oscar strong')).toHaveText('12');
});

test('regular Home cards opt in while IPTV stays free of movie awards and snapshot reads',async({page})=>{
  await fixtures(page);await page.goto('/');
  await expect(page.locator('.home-smart-movie-card .movie-award-oscar strong').first()).toHaveText('12');
  await expect(page.locator('.coming-soon-panel .movie-awards')).toHaveCount(0);
  await expect(page.locator('.continue-watching-panel .movie-awards')).toHaveCount(0);
  let reads=0;page.on('request',request=>{if(request.url().includes('/api/movie-awards/snapshot'))reads++;});
  await page.goto('/iptv');
  await expect(page.getByRole('heading',{name:'IPTV',exact:true})).toBeVisible();
  await expect(page.locator('.movie-awards:visible')).toHaveCount(0);
  expect(reads).toBe(0);
});

for(const mode of ['people','keywords']) {
  test(`${mode} IDs that collide with award-winning entities do not display awards`,async({page})=>{
    await fixtures(page);
    const name=mode==='people'?'Award person':'Award keyword';
    await page.route(`**/api/tmdb/${mode}/search**`,route=>route.fulfill({json:{results:[{tmdb_id:mode==='people'?'100':'1',name,known_for_department:'Acting',known_for:[]}],page:1,total_pages:1,total_results:1}}));
    await page.goto('/discover');
    await page.getByLabel('TMDB search type').selectOption(mode);
    await page.getByLabel(mode==='people'?'Search TMDB people':'Search TMDB keywords').fill(name);
    await page.getByRole('button',{name:'Search',exact:true}).click();
    await expect(page.getByRole('heading',{name,exact:true})).toBeVisible();
    await expect(page.locator('.movie-awards:visible')).toHaveCount(0);
  });
}

for (const surface of ['library','movie-lists','ai-control','pick','browse']) {
  test(`${surface} award click uses the accepted identity and Back restores its expanded origin`,async({page})=>{
    await fixtures(page);
    const owned={path:'E:/Movies/Award.fixture.mkv',title:'Award fixture',metadata_accepted:true,resolution:'1080p',canonical_metadata:{...movie(1),accepted:true}};
    await page.route(/\/api\/library(?:\?view=cards.*|\/search\/advanced)$/,route=>route.fulfill({json:{items:[owned],count:1,total:1,page:1,total_pages:1,catalog_generation:1,facets:{}}}));
    await page.route('**/api/library/details**',route=>route.fulfill({json:{item:owned,catalog_generation:1}}));
    await page.route('**/api/user/lists',route=>route.fulfill({json:{lists:[{id:'awards-list',name:'Awards fixture list',movies:[movie(1)]}],curation_generation:1}}));
    await page.route('**/api/library/check',route=>route.fulfill({json:{catalog_generation:1,results:route.request().postDataJSON().movies.map(row=>String(row.tmdb_id)==='1'?{...row,found:true,path:owned.path,library_item:owned,canonical_card:owned}:{...row,found:false})}}));
    await page.route('**/api/ai-control/preview',route=>route.fulfill({json:{state:'valid_plan',plan_id:'awards-preview',action:'list',summary:'Awards fixture',message:'One movie',total_matches:1,page_size:20,items:[{...movie(1),selection_key:'one'}],blocked:[],warnings:[]}}));
    await page.route('**/api/ollama/recommend',route=>route.fulfill({json:{results:[movie(1)],model:'Fixture'}}));
    await page.route('**/api/explore/indexers',route=>route.fulfill({json:{indexers:[{id:'fixture',name:'Fixture'}]}}));
    await page.route('**/api/explore/browse**',route=>route.fulfill({json:{results:[{...movie(1),parsed_title:'Award fixture',parsed_year:'2024',metadata:movie(1),variants:[{title:'Award.fixture.1080p',resolution:'1080p',indexer:'Fixture',seeders:20,size_human:'2 GB'}]}]}}));
    await page.route('**/api/metadata?**',route=>route.fulfill({json:movie(1)}));
    await page.goto(['pick','browse'].includes(surface)?'/discover':`/${surface}`);
    if(surface==='ai-control') {await page.getByPlaceholder('Tell CP what to find, list, download, or delete...').fill('List a movie');await page.getByRole('button',{name:'Preview command'}).click();}
    if(surface==='pick') {await page.getByRole('button',{name:'Pick My Movie',exact:true}).click();await page.getByPlaceholder('Something funny but a little sad, maybe an indie movie with a warm ending...').fill('A thriller');await page.getByRole('button',{name:'Ask AI',exact:true}).click();}
    if(surface==='browse') {await page.getByRole('button',{name:'Browse Indexers',exact:true}).click();await page.getByRole('button',{name:'Load latest',exact:true}).click();}
    await page.getByRole('heading',{name:'Award fixture',exact:true}).click();
    await expect(expanded(page).locator('.movie-award-oscar strong').first()).toHaveText('12');
    await expanded(page).locator('.director-person').getByRole('button',{name:'Golden Globe',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Winning film 2',exact:true})).toBeVisible();
    await expect(page.locator('.discover-grid:visible > .unified-movie-card')).toHaveCount(1);
    await page.getByLabel('Discovery path').getByRole('button',{name:'Back',exact:true}).click();
    await expect(expanded(page).getByRole('heading',{name:'Award fixture',exact:true})).toBeVisible();
  });
}
