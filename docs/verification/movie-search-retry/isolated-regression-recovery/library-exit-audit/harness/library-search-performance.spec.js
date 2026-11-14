import { expect, test } from './pass3-browser-fixture.cjs';

test.beforeEach(async ({ request }) => {
  expect(process.env.CP_DOWNLOAD_COMPLETION_E2E).toBe('1');
  expect((await request.post('/api/test/search/seed')).ok()).toBe(true);
});

async function openLibrary(page) {
  await page.goto('/library', { waitUntil: 'domcontentloaded' });
  const controls = page.getByRole('button', { name: 'Search, filters & selection', exact: true });
  await expect(page.getByRole('region', { name: 'Library Movies', exact: true })).toBeVisible();
  if (await controls.getAttribute('aria-expanded') !== 'true') await controls.click();
  return page.getByRole('textbox', { name: 'Search your offline library', exact: true });
}

test('rapid live typing serializes reads and renders exact identities and reachable count', async ({ page }) => {
  const input = await openLibrary(page);
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const sent = [];
  let active = 0; let maximum = 0;
  await page.route('**/api/library/search/advanced', async route => {
    const body = route.request().postDataJSON();
    const title = body.query.groups.find(group => group.type === 'title')?.values[0]?.text;
    if (!title) return route.continue();
    sent.push(title); maximum = Math.max(maximum, ++active);
    if (sent.length === 1) await gate;
    const response = await route.fetch();
    active--;
    await route.fulfill({ response });
  });
  try {
    await input.fill('s');
    await expect.poll(() => sent.length).toBe(1);
    for (const text of ['se', 'sea', 'sear', 'searc', 'search', 'searchf', 'searchfi', 'searchfix']) await input.fill(text);
    const began = Date.now();
    release();
    await expect(page.getByRole('heading', { name: 'Search Fixture 000', exact: true })).toBeVisible();
    const pagination = page.getByRole('navigation', { name: 'Library pagination', exact: true }).first();
    await expect(pagination).toContainText('of 85');
    const latestRenderMs = Date.now() - began;
    expect(latestRenderMs).toBeLessThan(1000);
    expect(sent).toEqual(['s', 'searchfix']);
    expect(maximum).toBe(1);
    await test.info().attach('search-request-timing', { body: JSON.stringify({ latestRenderMs, dispatched: sent, maximumActive: maximum }), contentType: 'application/json' });
    const seen = new Set();
    while (true) {
      for (const title of await page.locator('.unified-movie-card h3').allTextContents()) seen.add(title);
      const next = pagination.getByRole('button', { name: 'Next', exact: true });
      if (await next.isDisabled()) break;
      const old = await pagination.locator('strong').textContent();
      await next.click();
      await expect(pagination.locator('strong')).not.toHaveText(old);
    }
    expect([...seen].sort()).toEqual(Array.from({length: 85}, (_, i) => `Search Fixture ${String(i).padStart(3, '0')}`));
    await page.screenshot({ path: test.info().outputPath('search-final-page.png') });
  } finally { release(); }
});

test('stale success and failure cannot replace latest search; empty and repeat navigation recover', async ({ page }) => {
  const input = await openLibrary(page);
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  let blocked = false;
  await page.route('**/api/library/search/advanced', async route => {
    const text = route.request().postDataJSON().query.groups.find(group => group.type === 'title')?.values[0]?.text;
    if (text === 'obsolete') {
      blocked = true; await gate;
      return route.fulfill({ status: 503, json: { error: 'obsolete synthetic error' } });
    }
    return route.continue();
  });
  await input.fill('obsolete');
  await expect.poll(() => blocked).toBe(true);
  await input.fill('Search Fixture 084');
  release();
  await expect(page.getByRole('heading', { name: 'Search Fixture 084', exact: true })).toBeVisible();
  await expect(page.getByText('obsolete synthetic error', { exact: false })).toHaveCount(0);
  await input.fill('no matching synthetic movie');
  await expect(page.locator('.unified-movie-card:visible')).toHaveCount(0);
  await input.fill('Search Fixture 084');
  await expect(page.getByRole('heading', { name: 'Search Fixture 084', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Search Fixture 084', exact: true })).toBeVisible();
  await page.goForward();
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Search Fixture 084', exact: true })).toBeVisible();
});

test('foreground typing wins while an old background poster preload is outstanding', async ({ page }) => {
  const input = await openLibrary(page);
  let releasePoster;
  const posterGate = new Promise(resolve => { releasePoster = resolve; });
  let posterRequested = false;
  await page.route('**/api/assets/search-preload-gate', async route => {
    posterRequested = true;
    await posterGate;
    await route.fulfill({ status: 503, body: 'obsolete poster error' });
  });
  let background = true;
  await page.route('**/api/library/search/advanced', async route => {
    if (!background) return route.continue();
    background = false;
    const response = await route.fetch();
    const data = await response.json();
    data.items[0].poster_url = '/api/assets/search-preload-gate';
    await route.fulfill({ json: data });
  });
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('cp-catalog-ready', { detail: {} })));
  await expect.poll(() => posterRequested).toBe(true);
  try {
    await input.fill('Search Fixture 084');
    await expect(page.getByRole('heading', { name: 'Search Fixture 084', exact: true })).toBeVisible();
    await expect(page.locator('.unified-movie-card:visible')).toHaveCount(1);
    releasePoster();
    await expect(page.getByText('Background library update deferred:', { exact: false })).toHaveCount(0);
    await expect(page.locator('.unified-movie-card:visible')).toHaveCount(1);
  } finally { releasePoster(); }
});

test('Movie to File to Movie during a read schedules a valid replacement and settles loading', async ({ page }) => {
  const input = await openLibrary(page);
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const searches = [];
  await page.route('**/api/library/search/advanced', async route => {
    const text = route.request().postDataJSON().query.groups.find(group => group.type === 'title')?.values[0]?.text;
    if (text === 'Search Fixture 084') {
      searches.push(text);
      if (searches.length === 1) await gate;
    }
    return route.continue();
  });
  await input.fill('Search Fixture 084');
  await expect.poll(() => searches.length).toBe(1);
  await page.getByRole('button', { name: 'File View', exact: true }).click();
  await page.getByRole('button', { name: 'Media View', exact: true }).click();
  release();
  await expect(page.getByRole('heading', { name: 'Search Fixture 084', exact: true })).toBeVisible({ timeout: 2500 });
  await expect(page.getByRole('button', { name: 'Rescan library files', exact: true })).toBeEnabled();
  expect(searches).toHaveLength(2);
});

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
