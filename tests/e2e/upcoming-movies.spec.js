import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test.skip(process.env.CP_DISCOVER_PAGING_E2E !== '1', 'Requires isolated real Discover API server');

async function openControls(page) {
  const toggle = page.getByRole('button', { name: 'Search, filters & selection', exact: true });
  await expect(toggle).toBeVisible();
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click();
}

function upcomingResponse(page, predicate = () => true) {
  return page.waitForResponse(response => response.url().endsWith('/api/tmdb/discover/advanced')
    && response.request().method() === 'POST'
    && response.request().postDataJSON()?.query?.feed === 'upcoming'
    && predicate(response.request().postDataJSON()));
}

async function assertUpcomingGrid(page, response, count) {
  const payload = await response.json();
  expect(response.status()).toBe(200);
  expect(payload.results).toHaveLength(count);
  for (const movie of payload.results) {
    expect(movie.release_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(movie.title).toMatch(/^Upcoming Movie \d{3}$/);
  }
  const grid = page.locator('.discover-panel .discover-grid');
  await expect(grid.locator(':scope > article')).toHaveCount(count);
  await expect(grid.getByRole('heading', { level: 3 })).toHaveText(payload.results.map(movie => movie.title));
  return payload;
}

async function evidence(page, name) {
  if (!process.env.CP_UPCOMING_EVIDENCE_DIR) return;
  fs.mkdirSync(process.env.CP_UPCOMING_EVIDENCE_DIR, { recursive: true });
  await page.screenshot({ path: path.join(process.env.CP_UPCOMING_EVIDENCE_DIR, `${name}.png`) });
}

test('Home View all uses the backend Upcoming selection and preserves full pages and navigation', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const homeResponse = page.waitForResponse(response => response.url().includes('/api/tmdb/discover?list=upcoming'));
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  const homePayload = await (await homeResponse).json();
  expect(homePayload.results).toHaveLength(20);
  const upcoming = page.locator('.coming-soon-panel');
  // Home is a twenty-card preview; Discover retains all 81 eligible movies.
  await expect(upcoming.locator('.upcoming-movie-card')).toHaveCount(20);
  await expect(upcoming.locator('.upcoming-movie-copy strong')).toHaveText(
    homePayload.results.map(movie => movie.title));
  await upcoming.scrollIntoViewIfNeeded();
  await evidence(page, 'home-upcoming');

  const firstResponse = upcomingResponse(page, body => body.page === 1);
  await upcoming.getByRole('button', { name: 'View all', exact: true }).click();
  await expect(page).toHaveURL(/\/discover$/);
  await openControls(page);
  await expect(page.getByRole('combobox', { name: 'Discover feed', exact: true })).toHaveValue('upcoming');
  const first = await assertUpcomingGrid(page, await firstResponse, 39);
  expect(first.results.map(movie => movie.tmdb_id)).toEqual(Array.from({ length: 39 }, (_, i) => String(60001 + i)));
  await evidence(page, 'discover-upcoming-first');
  const controls = page.getByRole('navigation', { name: 'TMDB movie pagination', exact: true }).first();
  const secondResponse = upcomingResponse(page, body => body.page === 2);
  await controls.getByRole('button', { name: 'Next', exact: true }).click();
  const second = await assertUpcomingGrid(page, await secondResponse, 39);
  expect(second.results.map(movie => movie.tmdb_id)).toEqual(Array.from({ length: 39 }, (_, i) => String(60040 + i)));

  await page.getByRole('button', { name: 'Library', exact: true }).click();
  await expect(page).toHaveURL(/\/library$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/discover$/);
  await expect(page.locator('.discover-panel .discover-grid').getByRole('heading', { level: 3 }))
    .toHaveText(second.results.map(movie => movie.title));
  await page.goForward();
  await expect(page).toHaveURL(/\/library$/);
  await page.goBack();
  await expect(page.getByRole('combobox', { name: 'Discover feed', exact: true })).toHaveValue('upcoming');
  const finalResponse = upcomingResponse(page, body => body.page === 3);
  await controls.getByRole('button', { name: 'Next', exact: true }).click();
  const final = await assertUpcomingGrid(page, await finalResponse, 3);
  expect(final.total_results).toBe(81);
  expect(final.total_pages).toBe(3);
  await expect(controls.getByRole('button', { name: 'Next', exact: true })).toBeDisabled();
  await evidence(page, 'discover-upcoming-final');

  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await page.locator('.coming-soon-panel').getByRole('button', { name: 'View all', exact: true }).click();
  // Reopening the already-selected feed preserves CP's current page.
  await expect(page.locator('.discover-panel .discover-grid').getByRole('heading', { level: 3 }))
    .toHaveText(final.results.map(movie => movie.title));
  const revisitedResponse = upcomingResponse(page, body => body.page === 2);
  await controls.getByRole('button', { name: 'Previous', exact: true }).click();
  await assertUpcomingGrid(page, await revisitedResponse, 39);
});

test('direct Upcoming selection and extra ownership and Advanced criteria keep the backend rule', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto('/discover', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.discover-panel .discover-grid > article')).toHaveCount(39);
  await openControls(page);
  const directResponse = upcomingResponse(page);
  await page.getByRole('combobox', { name: 'Discover feed', exact: true }).selectOption('upcoming');
  await assertUpcomingGrid(page, await directResponse, 39);

  const ownershipResponse = upcomingResponse(page, body => body.query.groups.some(group => group.type === 'availability'));
  await page.getByRole('combobox', { name: 'Library ownership', exact: true }).selectOption('unowned');
  await assertUpcomingGrid(page, await ownershipResponse, 39);
  await expect(page.getByRole('combobox', { name: 'Discover feed', exact: true })).toHaveValue('upcoming');

  await page.getByLabel('TMDB search type').selectOption('advanced');
  await page.getByRole('button', { name: 'Add advanced search criterion', exact: true }).click();
  await page.getByRole('combobox', { name: 'Feed', exact: true }).selectOption('upcoming');
  await page.getByRole('combobox', { name: 'Criterion to add', exact: true }).selectOption('genre');
  await page.getByRole('combobox', { name: 'Genre value', exact: true }).selectOption('18');
  const genreResponse = upcomingResponse(page, body => body.query.groups.some(group => group.type === 'genre'));
  await page.getByRole('button', { name: 'Add criterion', exact: true }).click();
  await assertUpcomingGrid(page, await genreResponse, 39);
  const sortedResponse = upcomingResponse(page, body => body.query.sort.key === 'popularity.desc');
  await page.getByRole('combobox', { name: 'Sort', exact: true }).selectOption('popularity.desc');
  await assertUpcomingGrid(page, await sortedResponse, 39);
  await evidence(page, 'discover-upcoming-advanced');
});
