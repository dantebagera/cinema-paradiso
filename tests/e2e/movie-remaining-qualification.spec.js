import { expect, test } from '@playwright/test';

test('4000-film compiled search dispatches first/latest and reaches every exact result', async ({ page }, testInfo) => {
  test.setTimeout(120000);
  await page.goto('/library', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('region', { name: 'Library Movies', exact: true })).toBeVisible();
  const controls = page.getByRole('button', { name: 'Search, filters & selection', exact: true });
  if (await controls.getAttribute('aria-expanded') !== 'true') await controls.click();
  const input = page.getByRole('textbox', { name: 'Search your offline library', exact: true });
  let release;
  const barrier = new Promise(resolve => { release = resolve; });
  const dispatched = [];
  let active = 0, maximumActive = 0, latestFulfilled = false;
  await page.route('**/api/library/search/advanced', async route => {
    const text = route.request().postDataJSON().query.groups.find(group => group.type === 'title')?.values[0]?.text;
    if (!text) return route.continue();
    dispatched.push(text);
    maximumActive = Math.max(maximumActive, ++active);
    if (dispatched.length === 1) await barrier;
    const response = await route.fetch();
    active--;
    await route.fulfill({ response });
    if (text === 'searchfix') latestFulfilled = true;
  });
  try {
    await input.fill('s');
    await expect.poll(() => dispatched.length).toBe(1);
    for (const value of ['se', 'sea', 'sear', 'searc', 'search', 'searchf', 'searchfi', 'searchfix']) await input.fill(value);
    const started = Date.now();
    release();
    await expect.poll(() => latestFulfilled).toBe(true);
    await expect(page.getByRole('button', { name: 'Rescan library files', exact: true })).toBeEnabled();
    const pagination = page.getByRole('navigation', { name: 'Library pagination', exact: true }).first();
    await expect(pagination).toContainText(/of (4,000|4000)/);
    await expect(page.getByRole('heading', { name: 'Search Fixture 0000', exact: true })).toBeVisible();
    const latestRenderMs = Date.now() - started;
    expect(latestRenderMs).toBeLessThan(1000);
    expect(dispatched).toEqual(['s', 'searchfix']);
    expect(maximumActive).toBe(1);
    // Stop intercepting: subsequent page reads are independently verified below.
    await page.unroute('**/api/library/search/advanced');
    const seen = new Set();
    for (let index = 0; index < 100; index++) {
      await expect(page.getByRole('heading', { name: `Search Fixture ${String(index * 40).padStart(4, '0')}`, exact: true })).toBeVisible();
      const titles = await page.locator('.unified-movie-card h3').allTextContents();
      expect(titles).toHaveLength(40);
      for (const title of titles) seen.add(title);
      const next = pagination.getByRole('button', { name: 'Next', exact: true });
      if (index === 99) await expect(next).toBeDisabled();
      else await next.click();
    }
    expect([...seen].sort()).toEqual(Array.from({ length: 4000 }, (_, index) => `Search Fixture ${String(index).padStart(4, '0')}`));
    const evidence = { latestRenderMs, dispatched, maximumActive, catalogueSize: 4000, exactUniqueRendered: seen.size, pages: 100 };
    await testInfo.attach('4000-search-evidence', { body: JSON.stringify(evidence), contentType: 'application/json' });
    await page.screenshot({ path: testInfo.outputPath('4000-final-page.png') });
  } finally { release(); }
});

test('poster transport failure retries on due clock then publishes and refreshes Library and Following', async ({ page, request }, testInfo) => {
  const forceScans = [];
  page.on('request', req => { if (new URL(req.url()).searchParams.get('force_scan') === '1') forceScans.push(req.url()); });
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.release-item').filter({ hasText: 'Qualification Import' })).toBeVisible();
  await page.getByRole('button', { name: 'Library', exact: true }).click();
  const imported = page.getByRole('heading', { name: 'Qualification Import', exact: true });
  await expect(page.getByRole('region', { name: 'Library Movies', exact: true })).toBeVisible();
  await expect(imported).toHaveCount(0);
  const failed = await (await request.post('/api/test/qualification/drive')).json();
  expect(failed.ledger.state).toBe('waiting');
  expect(failed.ledger.attempts.assets).toBe(1);
  expect(failed.poster_calls).toBe(1);
  expect(failed.job.library_scan_pending).toBe(true);
  expect(failed.publication.publication_committed).toBe(false);
  expect(failed.events).toBe(0);
  await expect(imported).toHaveCount(0);
  // A repeated trigger before the deadline must not consume another attempt.
  const early = await (await request.post('/api/test/qualification/drive')).json();
  expect(early.poster_calls).toBe(1);
  expect(early.ledger.attempts.assets).toBe(1);
  await request.post('/api/test/qualification/advance');
  const completed = await (await request.post('/api/test/qualification/drive')).json();
  expect(completed.poster_calls).toBe(2);
  expect(completed.ledger.attempts.assets).toBe(2);
  expect(completed.ledger.state).toBe('complete');
  expect(completed.publication.publication_committed).toBe(true);
  expect(completed.job.library_scan_pending).toBe(false);
  expect(completed.events).toBeGreaterThan(0);
  await expect(imported).toBeVisible();
  await expect(imported.locator('xpath=ancestor::*[contains(@class,"unified-movie-card")][1]').locator('img').first()).toHaveAttribute('src', /\/api\/assets\/[a-f0-9]{64}/);
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(page.locator('.release-item').filter({ hasText: 'Qualification Import' })).toHaveCount(0);
  expect(forceScans).toEqual([]);
  await testInfo.attach('poster-retry-evidence', { body: JSON.stringify({ failed, early, completed, forceScans }), contentType: 'application/json' });
  await page.screenshot({ path: testInfo.outputPath('poster-completed-following.png') });
});
