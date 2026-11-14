import { chromium } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const output = path.dirname(fileURLToPath(import.meta.url));
const label = process.argv[2] || 'before';
const browser = await chromium.launch({headless:true});
const results=[];
const fixtureResponses=new Map();
try {
  for (const port of process.env.CP_PERF_PORTS ? process.env.CP_PERF_PORTS.split(',').map(Number) : [5000,15000,15000,5000]) {
    const context=await browser.newContext({viewport:{width:1920,height:1080}});
    const page=await context.newPage();
    const requests=[], errors=[];
    await page.route('**/api/**', async route => {
      const req=route.request();
      const url=new URL(req.url());
      if (process.env.CP_PERF_IDENTICAL_DATA === '1' && ['/api/library/search/advanced','/api/library/details','/api/user/lists','/api/library/check'].includes(url.pathname)) {
        const key=url.pathname+url.search+(req.postData()||'');
        if(!fixtureResponses.has(key)) {
          const response=await route.fetch({url:`http://127.0.0.1:5000${url.pathname}${url.search}`});
          fixtureResponses.set(key,{status:response.status(),headers:{'content-type':response.headers()['content-type']||'application/json'},body:await response.body()});
        }
        return route.fulfill(fixtureResponses.get(key));
      }
      if (!['GET','HEAD'].includes(req.method()) && !['/api/library/check','/api/library/search/advanced'].includes(url.pathname)) {
        return route.fulfill({status:403,json:{error:'Performance probe blocks mutations'}});
      }
      return route.continue();
    });
    page.on('pageerror',e=>errors.push(e.message));
    page.on('response', async r=>{if(r.url().includes('/api/')) requests.push({url:new URL(r.url()).pathname,status:r.status(),timing:r.request().timing()});});
    await page.addInitScript(()=>{
      window.__perf={longTasks:[],events:[]};
      new PerformanceObserver(list=>window.__perf.longTasks.push(...list.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask',buffered:true});
      new PerformanceObserver(list=>window.__perf.events.push(...list.getEntries().map(e=>({name:e.name,duration:e.duration,delay:e.processingStart-e.startTime})))).observe({type:'event',buffered:true,durationThreshold:16});
    });
    const start=Date.now();
    await page.goto(`http://127.0.0.1:${port}/library`,{waitUntil:'domcontentloaded'});
    await page.locator('.unified-movie-card').first().waitFor({timeout:60000});
    const ready=Date.now()-start;
    await page.waitForTimeout(1500);
    const buttons=await page.locator('.unified-movie-card').first().getByRole('button').evaluateAll(es=>es.map(e=>({text:e.textContent,aria:e.getAttribute('aria-label')})));
    const before=await page.evaluate(()=>({nodes:document.getElementsByTagName('*').length,metrics:window.__perf,resources:performance.getEntriesByType('resource').map(e=>({name:e.name,duration:e.duration,transfer:e.transferSize,type:e.initiatorType})),cards:document.querySelectorAll('.unified-movie-card').length,body:document.body.innerText.slice(0,1600)}));
    const actions=[];
    const cdp=await context.newCDPSession(page);await cdp.send('Performance.enable');
    const metrics=async()=>Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(m=>[m.name,m.value]));
    async function measure(name, action) {
      const old=await metrics();const t=Date.now();await action();
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      const next=await metrics();
      const delta=Object.fromEntries(['TaskDuration','ScriptDuration','LayoutDuration','RecalcStyleDuration','LayoutCount','RecalcStyleCount'].map(k=>[k,next[k]-old[k]]));
      actions.push({name,ms:Date.now()-t,...delta});
    }
    const scroll=()=>page.evaluate(()=>new Promise(resolve=>{
      const workspace=document.querySelector('.workspace');let n=0;
      function step(){workspace.scrollTop=(n%60)*50;n++;if(n<120)requestAnimationFrame(step);else resolve();}requestAnimationFrame(step);
    }));
    await measure('scroll',scroll);
    await measure('scroll-warm',scroll);
    await page.evaluate(()=>document.querySelector('.workspace').scrollTop=0);
    for(let n=0;n<3;n++) {
      await measure('expand',async()=>{await page.locator('.unified-movie-card').first().locator('h3').click();await page.locator('.unified-movie-card-expanded').waitFor();await page.waitForTimeout(800);});
      await measure('collapse',async()=>{const title=page.locator('.unified-movie-card-expanded h3').first();await title.click();await page.locator('.unified-movie-card-expanded').waitFor({state:'hidden'});});
    }
    for(let n=0;n<3;n++) {
      for(const section of ['Settings','Library']) {
        const nav=page.locator('nav').getByRole('button',{name:section,exact:true});
        if(!await nav.count()) continue;
        const t=Date.now();await nav.click();
        await page.waitForFunction(()=>document.querySelector('.workspace-panel:not([hidden])')?.getBoundingClientRect().height>100);
        await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
        actions.push({name:section,ms:Date.now()-t});
      }
    }
    await page.screenshot({path:path.join(output,`${label}-${port}-${results.length}.png`)});
    const after=await page.evaluate(()=>({metrics:window.__perf,nodes:document.getElementsByTagName('*').length}));
    const item={port,ready,before,after,buttons,actions,requests,errors};results.push(item);
    console.log(JSON.stringify({port,ready,nodes:before.nodes,cards:before.cards,longTasks:before.metrics.longTasks,actions,errors}));
    await context.close();
  }
} finally {await browser.close();fs.writeFileSync(path.join(output,`${label}.json`),JSON.stringify(results,null,2));}
