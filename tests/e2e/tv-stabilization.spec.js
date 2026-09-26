import { test, expect } from '@playwright/test';

test.skip(process.env.CP_TV_E2E !== '1', 'Requires disposable TV server');

test('shared TV criteria filter the real catalog and reset restores results', async ({ page }) => {
  await page.goto('/library');
  await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
  const tv = page.getByRole('region', { name: 'Library TV Shows', exact: true });
  await expect(tv.getByRole('link', { name: 'Open Harbor Signals' })).toBeVisible();
  await tv.getByLabel('TV search type').selectOption('advanced');
  await tv.getByRole('button', { name: 'Add advanced search criterion', exact: true }).click();
  await tv.getByLabel('Criterion to add').selectOption('year');
  await tv.getByRole('button', { name: 'Add criterion', exact: true }).last().click();
  await tv.getByLabel('year from', {exact:true}).fill('2025');
  await tv.getByRole('button', { name: 'Search TV', exact: true }).click();
  await expect(tv.getByText('No series match your search.', { exact: true })).toBeVisible();
  await tv.getByRole('button', { name: 'Close criterion picker' }).click();
  await tv.getByRole('button', { name: 'Open filters' }).click();
  await tv.getByRole('button', { name: 'Reset filters' }).click();
  await expect(tv.getByRole('link', { name: 'Open Harbor Signals' })).toBeVisible();
  await page.screenshot({ path: 'docs/verification/tv-parity/library-filters.png', fullPage: true });
});

test('TV status and in-progress viewing state filter from the main Library bar', async ({ page }) => {
  const searches = [];
  page.on('request', request => {
    if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/tv/catalog/search') searches.push(request.postDataJSON());
  });
  await page.goto('/library');
  await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
  const tv = page.getByRole('region', { name: 'Library TV Shows', exact: true });
  await tv.getByRole('button', { name: 'Open filters' }).click();
  await tv.getByLabel('TV Status').selectOption('Continuing');
  await expect(tv.getByRole('link', { name: 'Open Harbor Signals' })).toHaveCount(0);
  await expect.poll(() => searches.some(body => body.scope === 'library' && body.extras?.status === 'Continuing')).toBe(true);
  await tv.getByLabel('TV Status').selectOption('Ended');
  await expect(tv.getByRole('link', { name: 'Open Harbor Signals' })).toBeVisible();
  await tv.getByLabel('TV Viewing states').selectOption('in_progress');
  await expect.poll(() => searches.some(body => body.scope === 'library' && body.extras?.status === 'Ended' && body.query.groups.some(group => group.type === 'viewing_status' && group.values[0]?.id === 'in_progress'))).toBe(true);
  await tv.getByRole('button', { name: 'Reset filters' }).click();
  await expect(tv.getByLabel('TV Status')).toHaveValue('');
  await expect(tv.getByLabel('TV Viewing states')).toHaveValue('');
  await expect(tv.getByRole('link', { name: 'Open Harbor Signals' })).toBeVisible();
});

test('discover preview is read-only and trailers use the shared player without movie requests', async ({ page, request }) => {
  const catalogBefore = await (await request.get('/api/tv/series')).json();
  let additions = 0, movieCalls = 0;
  page.on('request', (r) => {
    if (r.method() === 'POST' && new URL(r.url()).pathname === '/api/tv/series') additions++;
    if (/youtube\/.*movie|tmdb\/details/.test(r.url())) movieCalls++;
  });
  await page.route('https://www.youtube.com/**', (route) => route.fulfill({ contentType: 'text/html', body: '<p>Trailer fixture</p>' }));
  await page.goto('/discover');
  await page.getByRole('tablist', { name: 'Discover tools' }).getByRole('button', { name: 'Explore Shows', exact: true }).click();
  await page.getByRole('link', { name: 'Open Open Water' }).click();
  await expect(page.getByRole('heading', { name: 'Open Water', exact: true })).toBeVisible();
  const previewActions = page.locator('.tv-series-header .card-actions');
  await expect(previewActions.getByRole('button', { name: 'Add to library', exact: true })).toHaveClass(/btn-primary/);
  expect(await previewActions.locator('button').evaluateAll(buttons => buttons.every(button => button.classList.contains('btn') && button.querySelector('svg')))).toBe(true);
  expect(additions).toBe(0);
  const before = movieCalls;
  await page.getByRole('button', { name: 'Trailer', exact: true }).click();
  await expect(page.locator('iframe[src*="abc12345678"]')).toBeVisible();
  expect(movieCalls).toBe(before);
  await page.keyboard.press('Escape');
  await expect(page.locator('iframe[src*="abc12345678"]')).toHaveCount(0);
  const rows = await (await request.get('/api/tv/series')).json();
  expect(rows.total).toBe(catalogBefore.total);
  await page.screenshot({ path: 'docs/verification/tv-parity/preview-details.png', fullPage: true });
  await page.goBack();
  await expect(page.getByRole('link', { name: 'Open Open Water' })).toBeVisible();
});

test('TV watchlist is separate from monitoring and survives metadata refresh', async ({ page, request }) => {
  await request.post('/api/tv/series/1/watchlist', { data: { watchlisted: false } });
  const before = await (await request.get('/api/tv/series/1/monitor')).json();
  await page.goto('/tv/series/1');
  const actions = page.locator('.tv-series-header .card-actions');
  await expect(actions.locator('.btn.btn-primary.btn-green')).toHaveCount(1);
  await expect(actions.getByRole('button', { name: 'Stream', exact: true })).toHaveClass(/btn-green-outline/);
  await expect(actions.getByRole('button', { name: 'Trailer', exact: true })).toHaveClass(/btn-secondary/);
  await expect(actions.locator('button')).toHaveCount(5);
  expect(await actions.locator('button').evaluateAll(buttons => buttons.every(button => button.classList.contains('btn') && button.querySelector('svg')))).toBe(true);
  await expect(actions.getByRole('button', { name: 'Add to watchlist', exact: true })).toHaveCSS('font-weight', '800');
  await page.getByRole('button', { name: 'Add to watchlist', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Remove from watchlist', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Refresh metadata', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Remove from watchlist', exact: true })).toBeVisible();
  expect(await (await request.get('/api/tv/series/1/monitor')).json()).toEqual(before);
});

test('partial release search offers retry and close ignores a late response', async ({ page }) => {
  let attempts = 0;
  await page.route('**/api/tv/search', async (route) => {
    attempts++;
    if (attempts > 1) await new Promise((resolve) => setTimeout(resolve, 200));
    await route.fulfill({ json: { decisions: [], search: { partial: true, notice: 'Some indexers did not finish.' } } });
  });
  await page.goto('/tv/series/1');
  await page.getByRole('button', { name: 'Download season', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'TV release review' });
  await expect(dialog).toContainText('Some sources did not finish.');
  await dialog.getByRole('button', { name: 'Retry search' }).click();
  await dialog.getByRole('button', { name: 'Close TV release review', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(attempts).toBeGreaterThanOrEqual(2);
});
