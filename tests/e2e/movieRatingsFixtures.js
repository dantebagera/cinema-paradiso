export const svg='<svg xmlns="http://www.w3.org/2000/svg" width="340" height="510"><rect width="340" height="510" fill="#293845"/></svg>';
export const movies=Array.from({length:40},(_,i)=>({tmdb_id:String(44012+i),title:i===0?'Jeanne Dielman, 23 quai du Commerce, 1080 Bruxelles':`Ratings fixture ${i+1}`,year:'1975',genres:['Drama'],tmdb_rating:'7.8',tmdb_vote_count:1234567,poster_url:`https://rt-fixture.test/${i}.svg`,backdrop_url:'',summary:'A fixture with existing movie details, actions and ratings.'}));
export async function fixtures(page,{heldPoster,heldRatings,score=58,audienceScore=score,owned=false,awards=false,ratingsBackend=false,crowded=false,noStar=false}={}) {
  const calls=[];
  const fixtureMovies=movies.map(m=>({...m,...(crowded?{genres:['Science Fiction','Action & Adventure'],language:'English',country:'United States of America',certification:'PG-13'}:{}),...(noStar?{tmdb_rating:'',tmdb_vote_count:0}:{})}));
  await page.route('**/api/**',route=>ratingsBackend&&route.request().url().includes('/api/movie-ratings/')?route.continue():route.fulfill({json:{items:[],results:[],unread_count:0}}));
  await page.route('https://rt-fixture.test/**',async route=>{if(heldPoster&&route.request().url().endsWith('/0.svg'))await heldPoster;await route.fulfill({contentType:'image/svg+xml',body:svg});});
  await page.route('**/api/tv/capabilities',route=>route.fulfill({json:{enabled:false}}));
  await page.route('**/api/user/lists**',route=>route.fulfill({json:{lists:[],curation_generation:1}}));
  await page.route('**/api/user/followed-releases**',route=>route.fulfill({json:{movies:[],curation_generation:1}}));
  await page.route('**/api/library/check',route=>route.fulfill({json:{results:[],catalog_generation:1}}));
  await page.route('**/api/tmdb/card-projections',route=>route.fulfill({json:{items:{},catalog_generation:1}}));
  await page.route('**/api/tmdb/discover/advanced',route=>route.fulfill({json:{results:fixtureMovies,page:1,total_pages:1,total_results:fixtureMovies.length}}));
  await page.route('**/api/tmdb/details**',route=>route.fulfill({json:fixtureMovies.find(m=>m.tmdb_id===new URL(route.request().url()).searchParams.get('tmdb_id'))||fixtureMovies[0]}));
  await page.route('**/api/movie-awards/batch',route=>route.fulfill({json:{items:{}}}));
  if(awards)await page.route('**/api/movie-awards/snapshot',route=>route.fulfill({json:{schema_version:1,awards_generation:1,snapshot_owner:'fixture',ready:true,movies:Object.fromEntries(movies.map(m=>[`tmdb:${m.tmdb_id}`,{entity_id:m.tmdb_id,oscar:11,golden_globe:7}])),people:{}}}));
  await page.route('**/api/movie-ratings/*',async route=>{
    if(ratingsBackend)return route.fallback();
    const items=route.request().postDataJSON().items;calls.push({path:route.request().url(),items});
    if(heldRatings)await heldRatings;
    await route.fulfill({json:{owner:'fixture',plex:{state:'available',valid_until:Date.now()/1000+300},items:Object.fromEntries(items.map(i=>[`movie:tmdb:${i.tmdb_id}`,{state:'ready',owned,display_allowed:true,critics:score,audience:audienceScore,retrieved_at:1700000000}]))}});
  });
  return calls;
}

