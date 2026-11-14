import { expect, test } from '@playwright/test';

const movies = [1, 2].map(index => ({ tmdb_id: String(9800 + index), title: `Completion fixture ${index}`,
  year: '2026', release_date: '2020-01-01', status: 'available', followed_at: index }));

async function eventSourceFixture(page) {
  await page.route('**/api/tmdb/discover**', route => route.fulfill({ json: { results: [], total_pages: 0 } }));
  await page.route('**/api/home/trailers', route => route.fulfill({ json: { items: [] } }));
  await page.addInitScript(() => {
    window.EventSource = class {
      constructor() { this.handlers = {}; window.completionEvents = this; }
      addEventListener(type, handler) { this.handlers[type] = handler; }
      close() {}
      emit(type, generation) { this.handlers[type]?.({ data: JSON.stringify({ type, generation }) }); }
    };
  });
}

test('reconnect ownership runs during full scan and older full response cannot restore removed movies', async ({ page }) => {
  await eventSourceFixture(page);
  let releaseScan;
  const scanGate = new Promise(resolve => { releaseScan = resolve; });
  let scans = 0;
  let ownership = 0;
  await page.route('**/api/user/followed-releases**', async route => {
    const full = route.request().url().endsWith('/check');
    const owned = route.request().url().endsWith('/reconcile-owned');
    if (full) { scans++; await scanGate; }
    if (owned) ownership++;
    await route.fulfill({ json: { movies: owned ? [] : movies, newly_available: [], removed_owned: [],
      curation_generation: owned ? 2 : 1 } });
  });
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  const panel = page.locator('.release-panel');
  await expect(panel.locator('.release-item')).toHaveCount(2);
  await expect.poll(() => scans).toBe(1);
  await page.evaluate(() => window.completionEvents.emit('catalog-sync', 2));
  try {
    await expect.poll(() => ownership).toBe(1);
    await expect(panel.locator('.release-item')).toHaveCount(0);
    await expect(panel.getByRole('button', { name: 'Scanning followed releases' })).toBeDisabled();
  } finally { releaseScan(); }
  await expect(panel.getByRole('button', { name: 'Scan followed releases' })).toBeEnabled();
  await expect(panel.locator('.release-item')).toHaveCount(0);
  await expect(panel.locator('.release-filter-count')).toHaveText('0');
});

test('another completion during ownership read is reconciled after that read finishes', async ({ page }) => {
  await eventSourceFixture(page);
  let ownership = 0;
  let releaseOwnership;
  const gate = new Promise(resolve => { releaseOwnership = resolve; });
  await page.route('**/api/user/followed-releases**', async route => {
    const owned = route.request().url().endsWith('/reconcile-owned');
    if (owned) { ownership++; if (ownership === 1) await gate; }
    await route.fulfill({ json: { movies: !owned ? movies : ownership === 1 ? [movies[1]] : [],
      newly_available: [], removed_owned: [], curation_generation: !owned ? 1 : ownership + 1 } });
  });
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  const panel = page.locator('.release-panel');
  await expect(panel.getByRole('button', { name: 'Scan followed releases' })).toBeEnabled();
  await page.evaluate(() => window.completionEvents.emit('catalog-ready', 2));
  await expect.poll(() => ownership).toBe(1);
  await page.evaluate(() => window.completionEvents.emit('catalog-ready', 3));
  releaseOwnership();
  await expect.poll(() => ownership).toBe(2);
  await expect(panel.locator('.release-item')).toHaveCount(0);
});

for (const outcome of ['retained', 'removed', 'refollowed']) {
  test(`delayed availability alert is ${outcome === 'retained' ? 'preserved once' : 'suppressed'} for ${outcome} follow instance`, async ({ page }) => {
    await eventSourceFixture(page);
    await page.addInitScript(() => {
      window.releaseSounds = 0;
      window.AudioContext = class {
        constructor() { window.releaseSounds++; this.currentTime = 0; }
        createOscillator() { return { frequency: { setValueAtTime() {} }, connect() {}, start() {}, stop() {} }; }
        createGain() { return { gain: { setValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() {} }; }
        close() { return Promise.resolve(); }
      };
    });
    const initial = [{ ...movies[0], status: 'watching' }, movies[1]];
    const newlyAvailable = { ...movies[0], status: 'available' };
    const current = outcome === 'removed' ? [] : [{ ...newlyAvailable,
      followed_at: outcome === 'refollowed' ? 999 : newlyAvailable.followed_at }];
    let releaseScan;
    const gate = new Promise(resolve => { releaseScan = resolve; });
    await page.route('**/api/user/followed-releases**', async route => {
      const full = route.request().url().endsWith('/check');
      const ownership = route.request().url().endsWith('/reconcile-owned');
      if (full) await gate;
      await route.fulfill({ json: {
        movies: ownership ? current : full ? [newlyAvailable, movies[1]] : initial,
        newly_available: full ? [newlyAvailable, newlyAvailable] : [], removed_owned: [],
        curation_generation: ownership ? 3 : full ? 2 : 1
      } });
    });
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    const panel = page.locator('.release-panel');
    await expect(panel.getByRole('button', { name: 'Scanning followed releases' })).toBeDisabled();
    await page.evaluate(() => window.completionEvents.emit('catalog-ready', 3));
    await expect(panel.locator('.release-item')).toHaveCount(current.length);
    releaseScan();
    await expect(panel.getByRole('button', { name: 'Scan followed releases' })).toBeEnabled();
    await expect(panel.locator('.release-item')).toHaveCount(current.length);
    if (outcome === 'retained') await expect(page.locator('.toast')).toHaveText('1 followed release now available');
    else await expect(page.locator('.toast').filter({ hasText: 'now available' })).toHaveCount(0);
    expect(await page.evaluate(() => window.releaseSounds)).toBe(outcome === 'retained' ? 1 : 0);
  });
}

test('real import publication refreshes Library and removes Following without Force scan, including reconnect', async ({ page, request }) => {
  test.skip(process.env.CP_DOWNLOAD_COMPLETION_E2E !== '1', 'Requires disposable real completion fixture');
  expect((await request.post('/api/test/completion/arm')).ok()).toBe(true);
  const forceScans = [];
  page.on('request', r => {
    if (new URL(r.url()).searchParams.get('force_scan') === '1') forceScans.push(r.url());
  });
  const scan = page.waitForRequest(r => r.url().endsWith('/api/user/followed-releases/check'));
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await scan;
  await expect(page.locator('.release-item').filter({ hasText: 'Automatic Refresh' })).toBeVisible();
  await page.getByRole('button', { name: 'Library', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Library Movies', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Library Movies', exact: true }).getByRole('heading', { name: 'Automatic Refresh', exact: true })).toHaveCount(0);
  const result = await (await request.post('/api/test/completion/import')).json();
  expect(result.pending).toBe(false);
  expect(result.events).toBeGreaterThan(0);
  await expect(page.getByRole('region', { name: 'Library Movies', exact: true }).getByRole('heading', { name: 'Automatic Refresh', exact: true })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath('automatic-library.png') });
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(page.locator('.release-item').filter({ hasText: 'Automatic Refresh' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Scanning followed releases' })).toBeDisabled();
  const beforeReconnect = await (await request.get('/api/test/completion/status')).json();
  await request.post('/api/test/completion/reconnect');
  await expect.poll(async () => (await (await request.get('/api/test/completion/status')).json()).ownership_requests).toBeGreaterThan(beforeReconnect.ownership_requests);
  await expect.poll(async () => (await (await request.get('/api/test/completion/status')).json()).followed_count).toBe(0);
  await expect(page.locator('.release-item').filter({ hasText: 'Automatic Refresh' })).toHaveCount(0);
  await request.post('/api/test/completion/release-scan');
  await expect(page.getByRole('button', { name: 'Scan followed releases' })).toBeEnabled();
  await expect(page.locator('.release-item').filter({ hasText: 'Automatic Refresh' })).toHaveCount(0);
  expect(forceScans).toEqual([]);
  await page.screenshot({ path: test.info().outputPath('automatic-completion.png') });
});
