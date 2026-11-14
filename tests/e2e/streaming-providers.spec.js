import { expect, test } from '@playwright/test';

test.skip(process.env.CP_TV_E2E !== '1', 'Requires the isolated native-TV server');
test.setTimeout(90_000);

let original;
test.beforeEach(async ({ request }) => {
  original = await (await request.get('/api/streaming/config')).json();
  expect((await request.post('/api/streaming/config', { data: { provider: 'streamimdb', enabled: true, label: 'Stream' } })).ok()).toBe(true);
});
test.afterEach(async ({ request }) => {
  if (original) expect((await request.post('/api/streaming/config', { data: original })).ok()).toBe(true);
});

async function saveStreaming(page) {
  const response = page.waitForResponse((response) => response.url().endsWith('/api/streaming/config') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Save Streaming', exact: true }).click();
  const saved = await response;
  expect(saved.ok()).toBe(true);
  return saved.json();
}

test('settings selection persists and routes both movies and episodes through the selected provider', async ({ page, request }) => {
  const movie = { tmdb_id: '864168', title: 'Joy Ride', year: '2023', genres: ['Comedy'], summary: 'Four friends travel together.', poster_url: '' };
  await page.route('**/api/tmdb/discover**', (route) => route.fulfill({ json: { results: [movie], page: 1, total_pages: 1, total_results: 1 } }));
  await page.route('**/api/tmdb/details**', (route) => route.fulfill({ json: movie }));
  await page.route('**/api/tmdb/related**', (route) => route.fulfill({ json: { results: [], page: 1, total_pages: 0 } }));
  await page.route('**/api/library/check', (route) => route.fulfill({ json: {
    results: (route.request().postDataJSON()?.movies || []).map((item) => ({ ...item, found: false })), catalog_generation: 1
  } }));
  for (const host of ['vsembed.ru', 'streamimdb.ru']) {
    await page.route(`https://${host}/**`, (route) => route.fulfill({ contentType: 'text/html', body: '<button>Provider play control</button>' }));
  }
  await page.goto('/settings');
  await expect(page.getByLabel('Streaming provider', { exact: true })).toHaveValue('streamimdb');
  expect((await page.getByLabel('Streaming provider', { exact: true }).boundingBox()).height).toBeGreaterThanOrEqual(42);
  for (const [provider, movieUrl, tvUrl] of [
    ['vsembed', 'https://vsembed.ru/embed/movie/864168/', 'https://vsembed.ru/embed/tv/900001/1-2'],
    ['streamimdb', 'https://streamimdb.ru/embed/movie/864168', 'https://streamimdb.ru/embed/tv/900001/1/2'],
  ]) {
    await page.getByLabel('Streaming provider', { exact: true }).selectOption(provider);
    const previous = await (await request.get('/api/streaming/config')).json();
    expect(previous.provider).not.toBe(provider);
    // Leaving an unsaved Settings draft must not switch the actual player.
    await page.getByRole('button', { name: 'Discover', exact: true }).click();
    await page.getByRole('heading', { name: 'Joy Ride', exact: true }).click();
    await page.locator('.unified-movie-card-expanded:visible').getByRole('button', { name: 'Stream', exact: true }).click();
    await page.locator('.stream-dialog').getByRole('button', { name: previous.provider === 'streamimdb' ? /StreamIMDB/ : /VSEmbed/ }).click();
    await expect(page.locator('.stream-dialog iframe')).toHaveAttribute('src', previous.provider === 'streamimdb'
      ? 'https://streamimdb.ru/embed/movie/864168' : 'https://vsembed.ru/embed/movie/864168/');
    await page.getByRole('button', { name: 'Close stream' }).click();
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    // Settings retains its unsaved draft while the active player stays unchanged.
    await expect(page.getByLabel('Streaming provider', { exact: true })).toHaveValue(provider);
    await page.getByLabel('Streaming provider', { exact: true }).selectOption(provider);
    const saved = await saveStreaming(page);
    expect(saved.provider).toBe(provider);
    await expect(page.getByLabel('Streaming provider', { exact: true })).toHaveValue(provider);
    await expect(page.getByLabel('URL template', { exact: true })).toHaveAttribute('readonly', '');
    if (process.env.CP_STREAM_EVIDENCE_DIR) await page.locator('#settings-streaming').screenshot({ path: `${process.env.CP_STREAM_EVIDENCE_DIR}/${provider}-settings.png` });

    // No document reload: this exercises the Settings -> App callback.
    await page.getByRole('button', { name: 'Discover', exact: true }).click();
    if (!await page.locator('.unified-movie-card-expanded:visible').getByRole('button', { name: 'Stream', exact: true }).isVisible()) {
      await page.getByRole('heading', { name: 'Joy Ride', exact: true }).click();
    }
    await page.locator('.unified-movie-card-expanded:visible').getByRole('button', { name: 'Stream', exact: true }).click();
    await page.locator('.stream-dialog').getByRole('button', { name: provider === 'streamimdb' ? /StreamIMDB/ : /VSEmbed/ }).click();
    await expect(page.locator('.stream-dialog iframe')).toHaveAttribute('src', movieUrl);
    await expect(page.frameLocator('.stream-dialog iframe').getByRole('button', { name: 'Provider play control' })).toBeVisible();
    await page.getByRole('button', { name: 'Close stream' }).click();

    const before = await (await request.get('/api/tv/series/1/seasons/1')).json();
    await page.getByRole('button', { name: 'Library', exact: true }).click();
    await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
    await page.getByRole('link', { name: 'Open Harbor Signals' }).click();
    await page.getByRole('article', { name: 'S01E02 The Signal' }).getByRole('button', { name: 'Stream', exact: true }).click();
    await expect(page.locator('.stream-dialog iframe')).toHaveAttribute('src', tvUrl);
    await expect(page.frameLocator('.stream-dialog iframe').getByRole('button', { name: 'Provider play control' })).toBeVisible();
    const after = await (await request.get('/api/tv/series/1/seasons/1')).json();
    expect(after.items.find((ep) => ep.episode_number === 2).completed).toBe(before.items.find((ep) => ep.episode_number === 2).completed);
    await page.getByRole('button', { name: 'Close stream' }).click();
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    await page.reload();
    await expect(page.getByLabel('Streaming provider', { exact: true })).toHaveValue(provider);
  }
});

test('custom templates remain editable and invalid saves preserve the active provider', async ({ page, request }) => {
  await request.post('/api/streaming/config', { data: {
    url_template: 'https://custom.invalid/movie/{imdb_id}',
    tv_url_template: 'https://custom.invalid/tv/{tmdb_id}/{season_number}/{episode_number}',
  } });
  await page.goto('/settings');
  await expect(page.getByLabel('Streaming provider', { exact: true })).toHaveValue('custom');
  await expect(page.getByLabel('URL template', { exact: true })).toBeEditable();
  await page.getByLabel('TV episode URL template', { exact: true }).fill('https://custom.invalid/{tmdb_id}');
  const response = page.waitForResponse((r) => r.url().endsWith('/api/streaming/config') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Save Streaming', exact: true }).click();
  expect((await response).status()).toBe(400);
  await expect(page.locator('#settings-streaming')).toContainText('requires tmdb_id, season_number and episode_number');
  const unchanged = await (await request.get('/api/streaming/config')).json();
  expect(unchanged.tv_url_template).toBe('https://custom.invalid/tv/{tmdb_id}/{season_number}/{episode_number}');
  await page.getByLabel('TV episode URL template', { exact: true }).fill('https://custom.invalid/show/{tmdb_id}/{season_number}/{episode_number}');
  const saved = await saveStreaming(page);
  expect(saved.provider).toBe('custom');
  expect(saved.url_template).toBe('https://custom.invalid/movie/{imdb_id}');
  await page.reload();
  await expect(page.getByLabel('Streaming provider', { exact: true })).toHaveValue('custom');
  await expect(page.getByLabel('TV episode URL template', { exact: true })).toHaveValue(saved.tv_url_template);
});

test('disabled streaming retains the provider and hides movie and episode actions', async ({ page, request }) => {
  await page.goto('/settings');
  await page.getByLabel('Streaming provider', { exact: true }).selectOption('vsembed');
  await page.getByRole('checkbox', { name: /Enable Stream buttons/ }).uncheck();
  const saved = await saveStreaming(page);
  expect(saved.enabled).toBe(false);
  expect(saved.provider).toBe('vsembed');
  await page.goto('/tv/series/1');
  await expect(page.getByRole('article', { name: 'S01E02 The Signal' }).getByRole('button', { name: 'Stream', exact: true })).toHaveCount(0);
  await page.goto('/settings');
  await expect(page.getByLabel('Streaming provider', { exact: true })).toHaveValue('vsembed');
  expect((await (await request.get('/api/streaming/config')).json()).enabled).toBe(false);
});
