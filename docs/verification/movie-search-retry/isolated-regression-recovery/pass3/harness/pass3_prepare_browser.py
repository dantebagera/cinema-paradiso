import shutil
from pathlib import Path
R=Path(__file__).parent;SPEC=R/'pass3-specs'
shutil.copy2(R/'pass3-browser-fixture.cjs',SPEC/'pass3-browser-fixture.cjs')
for p in SPEC.glob('*.spec.js'):
    text=p.read_text(encoding='utf-8');assert "from '@playwright/test'" in text
    p.write_text(text.replace("from '@playwright/test'","from './pass3-browser-fixture.cjs'"),encoding='utf-8')
with (SPEC/'following-refresh.spec.js').open('a',encoding='utf-8') as f:f.write('''
test('pass3 manual scan calls full scan while catalogue refresh calls ownership only', async ({page})=>{
  await eventSourceFixture(page);
  let scans=0,ownership=0;
  await page.route('**/api/user/followed-releases**',async route=>{
    if(route.request().url().endsWith('/check'))scans++;
    if(route.request().url().endsWith('/reconcile-owned'))ownership++;
    await route.fulfill({json:{movies,newly_available:[],removed_owned:[],curation_generation:1}});
  });
  await page.goto('/',{waitUntil:'domcontentloaded'});
  await expect.poll(()=>scans).toBe(1);
  const scan=page.locator('.release-panel').getByRole('button',{name:'Scan followed releases',exact:true});
  await expect(scan).toBeEnabled();await scan.click();
  await expect.poll(()=>scans).toBe(2);expect(ownership).toBe(0);
  await expect(scan).toBeEnabled();
  await page.evaluate(()=>window.completionEvents.emit('catalog-sync',2));
  await expect.poll(()=>ownership).toBe(1);expect(scans).toBe(2);
  await page.locator('.release-panel').screenshot({path:test.info().outputPath('manual-scan-ownership.png')});
});
''')
with (SPEC/'library-search-performance.spec.js').open('a',encoding='utf-8') as f:f.write('''
test('pass3 quiet refresh preserves page two, query, cards, loading and notifications', async ({page})=>{
  const reads=[];
  page.on('request',request=>{
    if(request.url().endsWith('/api/library/search/advanced'))reads.push(request.postDataJSON());
  });
  const input=await openLibrary(page);
  await input.fill('searchfix');
  const pager=page.getByRole('navigation',{name:'Library pagination',exact:true}).first();
  await expect(pager).toContainText('of 85');
  const initialTitles=await page.locator('.unified-movie-card h3').allTextContents();
  await pager.getByRole('button',{name:'Next',exact:true}).click();
  await expect(pager).toContainText('Page 2');
  await expect.poll(()=>page.locator('.unified-movie-card h3').allTextContents()).not.toEqual(initialTitles);
  const refresh=page.getByRole('button',{name:'Rescan library files',exact:true});
  await expect(refresh).toBeEnabled();await expect(page.locator('.toast')).toHaveCount(0);
  const before=await page.locator('.unified-movie-card h3').allTextContents();
  const beforePage=await pager.locator('strong').textContent();
  const expected=reads.at(-1);expect(expected.page).toBe(2);expect(before.length).toBeGreaterThan(0);
  await page.evaluate(()=>{
    window.pass3QuietViolations=[];
    window.pass3QuietObserver=new MutationObserver(()=>{
      if(document.querySelector('.library-status .spin'))window.pass3QuietViolations.push('foreground spinner');
      if(document.querySelector('.toast'))window.pass3QuietViolations.push('toast');
    });
    window.pass3QuietObserver.observe(document.body,{subtree:true,childList:true,attributes:true,characterData:true});
  });
  let release;let requested=0;
  let gate=new Promise(resolve=>{release=resolve;});
  await page.route('**/api/library/search/advanced',async route=>{
    const body=route.request().postDataJSON();
    expect(body).toEqual(expected);requested++;
    const marker=`Pass3 quiet refresh ${requested}`;
    await gate;
    const response=await route.fetch();const data=await response.json();
    data.facets={...data.facets,genres:[...(data.facets?.genres||[]),marker]};
    await route.fulfill({json:data});
  });
  try {
    for(const [index,event] of ['cp-library-changed','cp-catalog-ready'].entries()){
      if(index)gate=new Promise(resolve=>{release=resolve;});
      await page.evaluate(event=>window.dispatchEvent(new CustomEvent(event,{detail:{}})),event);
      await expect.poll(()=>requested).toBe(index+1);
      await expect(refresh).toBeEnabled();
      await expect(page.locator('.library-status .spin')).toHaveCount(0);
      await expect(page.locator('.toast')).toHaveCount(0);
      await expect(pager.locator('strong')).toHaveText(beforePage);
      expect(await page.locator('.unified-movie-card h3').allTextContents()).toEqual(before);
      await expect(input).toHaveValue('searchfix');
      release();
      // This option is delivered only by the refreshed response: proves it committed.
      await expect(page.locator('option').filter({hasText:`Pass3 quiet refresh ${index+1}`})).toHaveCount(1);
      await expect(pager.locator('strong')).toHaveText(beforePage);
      expect(await page.locator('.unified-movie-card h3').allTextContents()).toEqual(before);
    }
    expect(await page.evaluate(()=>window.pass3QuietViolations)).toEqual([]);
    await page.screenshot({path:test.info().outputPath('quiet-refresh-page-two.png')});
    await test.info().attach('quiet-refresh-current-page',{body:JSON.stringify({page:expected.page,pageSize:expected.page_size,titles:before,events:2}),contentType:'application/json'});
  } finally {release();await page.evaluate(()=>window.pass3QuietObserver.disconnect());}
});
''')
print('Prepared disposable compiled behavior scenarios; original specs unchanged')
