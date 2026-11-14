// A bounded isolated desktop test, not automation of the user's CP window.
import { chromium, expect } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
import path from 'node:path';

const [url,scope]=process.argv.slice(2);
const target=new URL(url);
if(target.hostname!=='127.0.0.1'||target.port==='5000'||!['library','discover'].includes(scope))throw new Error('Isolated loopback diagnostic required');
if(process.env.CP_TEST_MODE!=='1'||!process.env.CP_TEST_ROOT)throw new Error('Explicit isolation required');
const root=process.env.CP_TEST_ROOT;
const browser=await chromium.launch({headless:true});
const events=[];let activeEnrichment=0,seenEnrichment=0;
try{
  const page=await browser.newPage({viewport:{width:1365,height:900}});
  await page.route('**/*',route=>{
    const destination=new URL(route.request().url());
    if(['http:','https:'].includes(destination.protocol)&&!['127.0.0.1','localhost','image.tmdb.org'].includes(destination.hostname))return route.abort();
    return route.continue();
  });
  page.on('console',message=>{if(message.text().startsWith('CP_TAB '))events.push(JSON.parse(message.text().slice(7)));});
  page.on('request',request=>{if(request.url().endsWith('/api/tv/catalog/enrich')){activeEnrichment++;seenEnrichment++;}});
  const finished=request=>{if(request.url().endsWith('/api/tv/catalog/enrich'))activeEnrichment--;};
  page.on('requestfinished',finished);page.on('requestfailed',finished);
  await page.goto(`${url}/${scope}`);
  const tabs=page.getByRole('tablist',{name:scope==='library'?'Library media':'Discover tools'});
  await tabs.getByRole('button',{name:'TV Shows',exact:true}).click();
  const name=scope==='library'?'Library TV Shows':'Discover TV Shows';
  await expect(page.getByRole('region',{name}).locator('.tv-series-card').first()).toBeVisible({timeout:20000});
  await expect.poll(()=>events.some(event=>event.phase==='visible_state'&&event.name===name&&event.count>0&&event.posters>0&&event.postersLoaded===event.posters&&event.missingCounts===0),{timeout:20000}).toBe(true);
  await expect.poll(()=>events.some(event=>event.phase==='visible_state'&&event.name===name&&event.count>0&&event.posters>0&&event.postersLoaded===event.posters&&event.missingCounts===0&&event.backdrops===event.visible&&event.backdropsLoaded===event.backdrops),{timeout:20000}).toBe(true);
  await page.screenshot({path:path.join(root,'first-complete-viewport.png')});
  if(scope==='discover')await expect.poll(()=>seenEnrichment>0&&activeEnrichment===0,{timeout:30000}).toBe(true);
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const click=events.find(event=>event.phase==='tab_click'&&event.media==='TV Shows').t;
  const cards=events.find(event=>event.phase==='visible_state'&&event.name===name&&event.count>0);
  const ready=events.find(event=>event.phase==='visible_state'&&event.name===name&&event.count>0&&event.posters>0&&event.postersLoaded===event.posters&&event.missingCounts===0);
  const headers=events.find(event=>event.phase==='headers'&&event.url==='/api/tv/catalog/search');
  const artwork=events.find(event=>event.phase==='visible_state'&&event.name===name&&event.count>0&&event.posters>0&&event.postersLoaded===event.posters&&event.missingCounts===0&&event.backdrops===event.visible&&event.backdropsLoaded===event.backdrops);
  const summary={scope,visibility:events.find(event=>event.phase==='probe_ready')?.visibility,
    cards:cards.count,visible:ready.visible,postersLoaded:ready.postersLoaded,
    cards_dom_ms:cards.t-click,complete_visible_dom_ms:ready.t-click,
    all_visible_artwork_dom_ms:artwork.t-click,
    server_ms:Number(headers.server),enrichment_requests:seenEnrichment,
    poster_resources:events.filter(event=>event.phase==='image_resource'&&event.url.includes('/w342/')&&event.start>=click).length};
  if(summary.visibility!=='visible')throw new Error('Hidden-page timing is invalid');
  await writeFile(path.join(root,'browser-events-headless.json'),JSON.stringify(events,null,2),{flag:'wx'});
  await writeFile(path.join(root,'summary.json'),JSON.stringify(summary,null,2),{flag:'wx'});
  console.log(JSON.stringify(summary));
}finally{await browser.close();}
