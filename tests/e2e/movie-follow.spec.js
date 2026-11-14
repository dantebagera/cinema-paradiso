import { expect, test } from '@playwright/test';

test.skip(process.env.CP_MOVIE_FOLLOW_E2E !== '1', 'Requires disposable real Movie Follow server');

function scanResponse(page) {
  return page.waitForResponse(response => response.url().endsWith('/api/user/followed-releases/check')
    && response.request().method() === 'POST');
}

async function available(page, title) {
  const row = page.locator('.release-item').filter({ hasText: title });
  await expect(row).toBeVisible();
  await expect(row.locator('em')).toHaveText('Available');
}

test.beforeEach(async ({ request }) => {
  await request.post('/api/test/movie-follow/reset');
});

test('startup and consecutive Scan clicks freshly search pending movies through real routes', async ({ page, request }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  const startup = scanResponse(page);
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  const initial = await (await startup).json();
  expect(initial.movies.find(movie => movie.title === 'Practical Magic 2').status).toBe('available');
  expect(initial.movies.find(movie => movie.title === 'The Uprising').status).toBe('watching');
  expect(initial.scan_stats.skipped.not_due).toBe(0);
  await available(page, 'Practical Magic 2');

  await request.post('/api/test/movie-follow/advance');
  const firstScan = scanResponse(page);
  await page.getByRole('button', { name: 'Scan followed releases', exact: true }).click();
  const first = await (await firstScan).json();
  expect(first.movies.find(movie => movie.title === 'The Uprising').best_release.title).toContain('The Rage');
  expect(first.movies.find(movie => movie.title === 'Northspur').status).toBe('watching');
  await available(page, 'The Uprising');

  await request.post('/api/test/movie-follow/advance');
  const secondScan = scanResponse(page);
  await page.getByRole('button', { name: 'Scan followed releases', exact: true }).click();
  const second = await (await secondScan).json();
  expect(second.movies.find(movie => movie.title === 'Northspur').best_release.title).toContain('(2022)');
  expect(second.movies.every(movie => movie.status === 'available')).toBe(true);
  await available(page, 'Northspur');
  await page.screenshot({ path: process.env.CP_MOVIE_FOLLOW_SCREENSHOT || test.info().outputPath('movie-follow.png') });
});

test('a later app startup checks saved pending movies despite future retry dates', async ({ page, request }) => {
  const firstStartup = scanResponse(page);
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await firstStartup;
  await available(page, 'Practical Magic 2');
  await request.post('/api/test/movie-follow/advance');
  const nextStartup = scanResponse(page);
  await page.reload({ waitUntil: 'domcontentloaded' });
  const result = await (await nextStartup).json();
  expect(result.movies.find(movie => movie.title === 'The Uprising').status).toBe('available');
  expect(result.newly_available.map(movie => movie.title)).toContain('The Uprising');
  await available(page, 'The Uprising');
});
