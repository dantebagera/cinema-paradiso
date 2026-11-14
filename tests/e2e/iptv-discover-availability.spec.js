import { test, expect } from '@playwright/test';

test('Discover displays movies before offline IPTV lookup and adds badges without moving cards', async ({ page }) => {
  const movie = { tmdb_id: '550', title: 'First Enriched Movie', year: '2024', genres: ['Drama'], poster_url: '' };
  await page.route('**/api/tmdb/discover**', route => route.fulfill({ json: {
    results: [movie], page: 1, total_pages: 1, total_results: 1,
  } }));
  await page.route('**/api/library/check', route => route.fulfill({ json: { results: [], catalog_generation: 1 } }));
  let release;
  const held = new Promise(resolve => { release = resolve; });
  await page.route('**/api/iptv/movies/availability', async route => {
    await held;
    await route.continue();
  });
  await page.goto('/discover');
  const card = page.locator('.unified-movie-card').filter({ hasText: movie.title }).first();
  await expect(card.getByRole('heading', { name: movie.title, exact: true })).toBeVisible();
  const before = await card.boundingBox();
  await expect(card.getByRole('button', { name: 'Stream from Provider One', exact: true })).toHaveCount(0);
  await page.waitForTimeout(5000);
  await expect(card.getByRole('heading', { name: movie.title, exact: true })).toBeVisible();
  release();
  await expect(card.getByRole('button', { name: 'Stream from Provider One', exact: true })).toBeVisible();
  if (process.env.CP_IPTV_EVIDENCE_DIR) await page.screenshot({ path: process.env.CP_IPTV_EVIDENCE_DIR + '/discover-badge.png' });
  const after = await card.boundingBox();
  expect(Math.abs(after.height - before.height)).toBeLessThanOrEqual(1);
  expect(Math.abs(after.y - before.y)).toBeLessThanOrEqual(1);
});

test('long provider names use bounded badges and expose all providers through overflow', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const movie = { tmdb_id: '550', title: 'Overflow Movie', year: '2024', poster_url: '' };
  await page.route('**/api/tmdb/discover**', route => route.fulfill({ json: { results: [movie], page: 1, total_pages: 1, total_results: 1 } }));
  await page.route('**/api/iptv/movies/availability', route => route.fulfill({ json: {
    providers: Array.from({ length: 10 }, (_, index) => ({
      provider_id: String(index), name: 'A long configured provider display name ' + index, state: 'ready',
      matches: { '550': { movie_key: 'tmdb:550', source_count: 1 } },
    })),
  } }));
  await page.goto('/discover');
  const row = page.getByLabel('Saved IPTV availability', { exact: true });
  await expect(row.getByRole('button')).toHaveCount(3);
  await expect(row.getByRole('button', { name: 'Show all 10 IPTV providers' })).toBeVisible();
  const dimensions = await row.evaluate(element => ({ width: element.clientWidth, content: element.scrollWidth, height: element.clientHeight }));
  expect(dimensions.height).toBe(30);
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.width);
  await row.getByRole('button', { name: 'Show all 10 IPTV providers' }).click();
  await expect(page.locator('.stream-dialog .iptv-source-list button').filter({ hasText: 'A long configured provider' })).toHaveCount(10);
});
