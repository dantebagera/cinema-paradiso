import { test, expect } from '@playwright/test';

async function openMovie(page) {
  const movie = { tmdb_id: '550', imdb_id: 'tt0137523', title: 'First Enriched Movie', year: '2024', genres: ['Drama'], poster_url: '' };
  await page.route('**/api/tmdb/discover**', route => route.fulfill({ json: { results: [movie], page: 1, total_pages: 1, total_results: 1 } }));
  await page.route('**/api/tmdb/details**', route => route.fulfill({ json: movie }));
  await page.route('**/api/tmdb/related**', route => route.fulfill({ json: { results: [] } }));
  await page.route('**/api/library/check', route => route.fulfill({ json: { results: [], catalog_generation: 1 } }));
  await page.goto('/discover');
  await page.getByRole('heading', { name: movie.title, exact: true }).click();
  return page.locator('.unified-movie-card-expanded').getByRole('button', { name: 'Stream', exact: true }).evaluate(button => new Promise(resolve => {
    const started = performance.now();
    const observer = new MutationObserver(() => {
      if (document.querySelector('.stream-dialog')) { observer.disconnect(); resolve(performance.now() - started); }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    button.click();
  }));
}

test('movie opens choices immediately and loads only the selected web provider', async ({ page }) => {
  await page.route('https://streamimdb.ru/embed/movie/550', route => route.fulfill({ contentType: 'text/html', body: '<p>Chosen provider</p>' }));
  await openMovie(page);
  const dialog = page.getByRole('dialog', { name: 'Stream First Enriched Movie 2024' });
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('iframe')).toHaveCount(0);
  await expect(dialog.getByRole('button', { name: /StreamIMDB/ })).toBeVisible();
  if (process.env.CP_IPTV_EVIDENCE_DIR) await page.screenshot({ path: process.env.CP_IPTV_EVIDENCE_DIR + '/stream-chooser.png' });
  await dialog.getByRole('button', { name: /StreamIMDB/ }).click();
  await expect(dialog.locator('iframe')).toHaveAttribute('src', 'https://streamimdb.ru/embed/movie/550');
  await dialog.getByRole('button', { name: 'Change source', exact: true }).click();
  await expect(dialog.locator('iframe')).toHaveCount(0);
  await expect(dialog.getByRole('button', { name: /VSEmbed/ })).toBeVisible();
});

test('web selection stays usable while each IPTV catalog is still checking', async ({ page }) => {
  let release;
  const held = new Promise(resolve => { release = resolve; });
  await page.route('**/api/iptv/movies/availability', async route => { await held; await route.continue(); });
  await page.route('https://streamimdb.ru/embed/movie/550', route => route.fulfill({ contentType: 'text/html', body: '<p>Web source</p>' }));
  try {
    const openedMs = await openMovie(page);
    console.log(`Movie chooser opened while catalog held: ${openedMs.toFixed(1)}ms`);
    expect(openedMs).toBeLessThan(100);
    const dialog = page.locator('.stream-dialog');
    await expect(dialog.getByRole('button', { name: /Provider One.*Checking saved catalog/ })).toBeDisabled();
    await dialog.getByRole('button', { name: /StreamIMDB/ }).click();
    await expect(dialog.locator('iframe')).toHaveCount(1);
  } finally { release(); }
});

test('IPTV choice uses real saved versions and starts the explicitly selected source', async ({ page }) => {
  let start;
  let stopped = false;
  await page.route('**/playback', route => {
    start = route.request().postDataJSON();
    return route.fulfill({ json: { token: 'fixture-token', manifest_url: '/fixture.m3u8' } });
  });
  await page.route('**/fixture.m3u8', route => route.fulfill({ status: 404, body: '' }));
  await page.route('**/playback/fixture-token', route => { stopped = true; return route.fulfill({ json: { stopped: true } }); });
  await openMovie(page);
  const dialog = page.locator('.stream-dialog');
  await dialog.getByRole('button', { name: /Provider One.*In catalog/ }).click();
  await expect(dialog.getByRole('button', { name: /First Movies/ })).toHaveCount(2);
  await dialog.getByRole('button', { name: /First Movies/ }).nth(1).click();
  await expect.poll(() => start?.item_id).toBe('8');
  await expect(dialog.locator('video')).toHaveCount(1);
  await dialog.getByRole('button', { name: 'Close stream', exact: true }).click();
  await expect.poll(() => stopped).toBe(true);
});

test('disabled web streaming still offers IPTV and keyboard focus stays in the chooser', async ({ page, request }) => {
  const original = await (await request.get('/api/streaming/config')).json();
  try {
    await request.post('/api/streaming/config', { data: { enabled: false } });
    await openMovie(page);
    const dialog = page.locator('.stream-dialog');
    await expect(dialog.getByRole('button', { name: /Provider One.*In catalog/ })).toBeVisible();
    await expect(dialog.getByRole('button', { name: /StreamIMDB/ })).toHaveCount(0);
    await dialog.getByRole('button', { name: 'Close stream', exact: true }).focus();
    await page.keyboard.press('Shift+Tab');
    await expect(dialog.getByRole('button', { name: /Provider One.*In catalog/ })).toBeFocused();
  } finally {
    await request.post('/api/streaming/config', { data: { enabled: original.enabled } });
  }
});
