import { expect, test } from '@playwright/test';

const streamUrl = 'https://stream.example.test/movie/864168';
const streamPage = '<!doctype html><html><body><button>Play video</button></body></html>';

async function openMovie(page) {
  const movie = { tmdb_id: '864168', title: 'Joy Ride', year: '2023', genres: ['Comedy'], summary: 'Four friends travel together.', poster_url: '' };
  await page.route('**/api/streaming/config', (route) => route.fulfill({ json: {
    enabled: true, label: 'Stream', url_template: 'https://stream.example.test/movie/{tmdb_id}'
  } }));
  await page.route('**/api/tmdb/discover**', (route) => route.fulfill({ json: {
    results: [movie], page: 1, total_pages: 1, total_results: 1
  } }));
  await page.route('**/api/tmdb/details**', (route) => route.fulfill({ json: movie }));
  await page.route('**/api/tmdb/related**', (route) => route.fulfill({ json: { results: [], page: 1, total_pages: 0 } }));
  await page.route('**/api/library/check', (route) => route.fulfill({ json: {
    results: (route.request().postDataJSON()?.movies || []).map((item) => ({ ...item, found: false })), catalog_generation: 1
  } }));
  await page.goto('/discover');
  await page.getByRole('heading', { name: 'Joy Ride', exact: true }).click();
  const action = page.locator('.unified-movie-card-expanded:visible').getByRole('button', { name: 'Stream', exact: true });
  await expect(action).toBeVisible();
  return action;
}

test('movie page load removes CP status immediately and leaves provider controls accessible', async ({ page }) => {
  await page.route(streamUrl, (route) => route.fulfill({ contentType: 'text/html', body: streamPage }));
  const action = await openMovie(page);
  await page.clock.install();
  await action.click();
  const dialog = page.locator('.stream-dialog');
  await expect(dialog.locator('iframe')).toHaveAttribute('src', streamUrl);
  await expect(page.frameLocator('.stream-dialog iframe').getByRole('button', { name: 'Play video' })).toBeVisible();
  await expect(dialog.getByRole('status')).toHaveCount(0, { timeout: 2000 });
  if (process.env.CP_STREAM_EVIDENCE_DIR) await page.screenshot({ path: `${process.env.CP_STREAM_EVIDENCE_DIR}/movie-loaded.png` });
  await page.frameLocator('.stream-dialog iframe').getByRole('button', { name: 'Play video' }).click();
  await page.clock.runFor(31_000);
  await expect(dialog.getByRole('status')).toHaveCount(0);
  // Keyboard events inside a cross-origin provider do not reach CP's document.
  await dialog.getByRole('button', { name: 'Close stream' }).click();
  await expect(dialog).toHaveCount(0);
  await expect(action).toBeFocused();
});

test('delayed page keeps a truthful loading status, then removes it on load and resets on reopen', async ({ page }) => {
  const action = await openMovie(page);
  await page.clock.install();
  let pending;
  await page.route(streamUrl, (route) => { pending = route; });
  await action.click();
  await expect.poll(() => Boolean(pending)).toBe(true);
  const status = page.locator('.stream-dialog').getByRole('status');
  await expect(status).toContainText('Loading stream page');
  if (process.env.CP_STREAM_EVIDENCE_DIR) await page.screenshot({ path: `${process.env.CP_STREAM_EVIDENCE_DIR}/movie-loading.png` });
  await page.clock.runFor(12_000);
  await expect(status).toContainText('The streaming page is taking longer than usual');
  if (process.env.CP_STREAM_EVIDENCE_DIR) await page.screenshot({ path: `${process.env.CP_STREAM_EVIDENCE_DIR}/movie-slow.png` });
  await pending.fulfill({ contentType: 'text/html', body: streamPage });
  await expect(status).toHaveCount(0, { timeout: 2000 });
  await page.keyboard.press('Escape');
  pending = null;
  await action.click();
  await expect.poll(() => Boolean(pending)).toBe(true);
  await expect(status).toContainText('Loading stream page');
  await expect(status).not.toContainText('taking longer');
  await page.clock.runFor(30_000);
  await expect(status).toHaveCount(0);
  await pending.fulfill({ contentType: 'text/html', body: streamPage });
  await expect(page.frameLocator('.stream-dialog iframe').getByRole('button', { name: 'Play video' })).toBeVisible();
});

test('a provider 404 page stays visible without a misleading CP preparation status', async ({ page }) => {
  await page.route(streamUrl, (route) => route.fulfill({ status: 404, contentType: 'text/html', body: '<p>Media unavailable</p>' }));
  const action = await openMovie(page);
  await action.click();
  await expect(page.frameLocator('.stream-dialog iframe').getByText('Media unavailable')).toBeVisible();
  await expect(page.locator('.stream-dialog').getByRole('status')).toHaveCount(0, { timeout: 2000 });
  if (process.env.CP_STREAM_EVIDENCE_DIR) await page.screenshot({ path: `${process.env.CP_STREAM_EVIDENCE_DIR}/movie-unavailable.png` });
});

test('TV page load clears CP status without changing episode identity or watched state', async ({ page, request }) => {
  test.skip(process.env.CP_TV_E2E !== '1', 'Requires the isolated native-TV fixture server');
  const url = 'https://example.invalid/tv/900001/1/2';
  await page.route(url, (route) => route.fulfill({ contentType: 'text/html', body: streamPage }));
  const before = await (await request.get('/api/tv/series/1/seasons/1')).json();
  await page.goto('/tv/series/1');
  const action = page.getByRole('article', { name: 'S01E02 The Signal' }).getByRole('button', { name: 'Stream', exact: true });
  await action.click();
  const dialog = page.locator('.stream-dialog');
  await expect(dialog.locator('iframe')).toHaveAttribute('src', url);
  await expect(page.frameLocator('.stream-dialog iframe').getByRole('button', { name: 'Play video' })).toBeVisible();
  await expect(dialog.getByRole('status')).toHaveCount(0, { timeout: 2000 });
  if (process.env.CP_STREAM_EVIDENCE_DIR) await page.screenshot({ path: `${process.env.CP_STREAM_EVIDENCE_DIR}/tv-loaded.png` });
  const after = await (await request.get('/api/tv/series/1/seasons/1')).json();
  expect(after.items.find((episode) => episode.episode_number === 2).completed).toBe(before.items.find((episode) => episode.episode_number === 2).completed);
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(action).toBeFocused();
});
