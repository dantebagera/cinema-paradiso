import { expect, test } from '@playwright/test';

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
