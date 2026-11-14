import { expect, test } from '@playwright/test';

async function openControls(page) {
  const toggle = page.getByRole('button', { name: 'Search, filters & selection', exact: true });
  await expect(toggle).toBeVisible();
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click();
}
import fs from 'node:fs';
import path from 'node:path';

test.skip(process.env.CP_DISCOVER_PAGING_E2E !== '1', 'Requires isolated overlapping-provider server');

async function openDiscover(page) {
  // Match the fullscreen width recorded in the motivating investigation.
  await page.setViewportSize({ width: 3345, height: 1084 });
  await page.goto('/discover', { waitUntil: 'domcontentloaded' });
  await openControls(page);
  return page.locator('.discover-panel .discover-grid');
}

async function assertCards(grid, count, columns, first, last) {
  await expect(grid.locator(':scope > article')).toHaveCount(count);
  await expect.poll(() => grid.evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length)).toBe(columns);
  if (first) await expect(grid.locator(':scope > article').first().getByRole('heading', { level: 3 })).toHaveText(first);
  if (last) await expect(grid.locator(':scope > article').last().getByRole('heading', { level: 3 })).toHaveText(last);
}

async function evidence(page, name) {
  const directory = process.env.CP_DISCOVER_EVIDENCE_DIR;
  if (directory) {
    fs.mkdirSync(directory, { recursive: true });
    await page.screenshot({ path: path.join(directory, `${name}.png`) });
  }
}

for (const collapsed of [false, true]) {
  test(`real Discover API fills consecutive ${collapsed ? 'collapsed' : 'expanded'} desktop pages and preserves the final remainder`, async ({ page }) => {
    const grid = await openDiscover(page);
    const size = collapsed ? 40 : 39;
    const columns = collapsed ? 4 : 3;
    await assertCards(grid, 39, 3, 'Overlap Movie 1', 'Overlap Movie 39');
    if (collapsed) await page.getByRole('button', { name: 'Collapse sidebar' }).click();
    await assertCards(grid, size, columns, 'Overlap Movie 1', `Overlap Movie ${size}`);
    await evidence(page, `${collapsed ? 'collapsed' : 'expanded'}-page1`);
    const controls = page.getByRole('navigation', { name: 'TMDB movie pagination', exact: true }).first();
    const response = page.waitForResponse(r => r.url().endsWith('/api/tmdb/discover/advanced')
      && r.request().postDataJSON()?.page === 2 && r.request().postDataJSON()?.page_size === size);
    await controls.getByRole('button', { name: 'Next', exact: true }).click();
    const payload = await (await response).json();
    expect(payload.results).toHaveLength(size);
    await assertCards(grid, size, columns, `Overlap Movie ${size + 1}`, `Overlap Movie ${size * 2}`);
    await evidence(page, `${collapsed ? 'collapsed' : 'expanded'}-page2`);
    await controls.getByRole('button', { name: 'Next', exact: true }).click();
    await assertCards(grid, 81 - size * 2, columns, `Overlap Movie ${size * 2 + 1}`, 'Overlap Movie 81');
    await expect(controls.getByRole('button', { name: 'Next', exact: true })).toBeDisabled();
    await expect(controls).toContainText('Page 3 of 3');
    await evidence(page, `${collapsed ? 'collapsed' : 'expanded'}-final`);
    await controls.getByRole('button', { name: 'Previous', exact: true }).click();
    await assertCards(grid, size, columns, `Overlap Movie ${size + 1}`, `Overlap Movie ${size * 2}`);
    await controls.getByRole('button', { name: 'Previous', exact: true }).click();
    await assertCards(grid, size, columns, 'Overlap Movie 1', `Overlap Movie ${size}`);
  });
}

test('sidebar expansion and collapse repeatedly repaginate the real unique result stream', async ({ page }) => {
  const grid = await openDiscover(page);
  await assertCards(grid, 39, 3, 'Overlap Movie 1', 'Overlap Movie 39');
  for (let iteration = 0; iteration < 2; iteration += 1) {
    await page.getByRole('button', { name: 'Collapse sidebar' }).click();
    await assertCards(grid, 40, 4, 'Overlap Movie 1', 'Overlap Movie 40');
    await page.getByRole('navigation', { name: 'TMDB movie pagination', exact: true }).first()
      .getByRole('button', { name: 'Next', exact: true }).click();
    await assertCards(grid, 40, 4, 'Overlap Movie 41', 'Overlap Movie 80');
    await page.getByRole('button', { name: 'Expand sidebar' }).click();
    await assertCards(grid, 39, 3, 'Overlap Movie 1', 'Overlap Movie 39');
  }
});

test('finite title search shows all three movies with either sidebar layout', async ({ page }) => {
  const grid = await openDiscover(page);
  await assertCards(grid, 39, 3, 'Overlap Movie 1', 'Overlap Movie 39');
  await page.getByRole('textbox', { name: 'Search TMDB movies', exact: true }).fill('Lord of the Rings');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await assertCards(grid, 3, 3, 'The Fellowship of the Ring', 'The Return of the King');
  await expect(grid.getByRole('heading', { name: 'The Two Towers', exact: true })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'TMDB movie pagination', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Collapse sidebar' }).click();
  await assertCards(grid, 3, 4, 'The Fellowship of the Ring', 'The Return of the King');
  await evidence(page, 'finite-three-movies');
});

test('narrower desktop retains complete measured rows when collapse cannot fit another column', async ({ page }) => {
  const grid = await openDiscover(page);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await assertCards(grid, 39, 3, 'Overlap Movie 1', 'Overlap Movie 39');
  await page.getByRole('button', { name: 'Collapse sidebar' }).click();
  await assertCards(grid, 39, 3, 'Overlap Movie 1', 'Overlap Movie 39');
  await page.getByRole('navigation', { name: 'TMDB movie pagination', exact: true }).first()
    .getByRole('button', { name: 'Next', exact: true }).click();
  await assertCards(grid, 39, 3, 'Overlap Movie 40', 'Overlap Movie 78');
});

test('browser Back and Forward restore the full second page and allow continued paging', async ({ page }) => {
  const grid = await openDiscover(page);
  await assertCards(grid, 39, 3, 'Overlap Movie 1', 'Overlap Movie 39');
  await page.getByRole('navigation', { name: 'TMDB movie pagination', exact: true }).first()
    .getByRole('button', { name: 'Next', exact: true }).click();
  await assertCards(grid, 39, 3, 'Overlap Movie 40', 'Overlap Movie 78');
  await page.getByRole('button', { name: 'Library', exact: true }).click();
  await openControls(page);
  await expect(page).toHaveURL(/\/library$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/discover$/);
  await assertCards(grid, 39, 3, 'Overlap Movie 40', 'Overlap Movie 78');
  await page.goForward();
  await expect(page).toHaveURL(/\/library$/);
  await page.goBack();
  await assertCards(grid, 39, 3, 'Overlap Movie 40', 'Overlap Movie 78');
  await page.getByRole('navigation', { name: 'TMDB movie pagination', exact: true }).first()
    .getByRole('button', { name: 'Next', exact: true }).click();
  await assertCards(grid, 3, 3, 'Overlap Movie 79', 'Overlap Movie 81');
});

test('Advanced title sorting publishes complete stable pages without repeating earlier movies', async ({ page }) => {
  const grid = await openDiscover(page);
  await assertCards(grid, 39, 3, 'Overlap Movie 1', 'Overlap Movie 39');
  await page.getByRole('textbox', { name: 'Search TMDB movies', exact: true }).fill('Sorted');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await assertCards(grid, 39, 3, 'Sorted Z001', 'Sorted Z039');
  await page.getByLabel('TMDB search type').selectOption('advanced');
  await page.getByRole('button', { name: 'Add advanced search criterion', exact: true }).click();
  await page.getByRole('combobox', { name: 'Sort', exact: true }).selectOption('title.asc');
  await assertCards(grid, 39, 3, 'Sorted A041', 'Sorted A079');
  const controls = page.getByRole('navigation', { name: 'TMDB movie pagination', exact: true }).first();
  await controls.getByRole('button', { name: 'Next', exact: true }).click();
  await assertCards(grid, 39, 3, 'Sorted A080', 'Sorted Z038');
  await controls.getByRole('button', { name: 'Next', exact: true }).click();
  await assertCards(grid, 2, 3, 'Sorted Z039', 'Sorted Z040');
  await expect(controls.getByRole('button', { name: 'Next', exact: true })).toBeDisabled();
  await controls.getByRole('button', { name: 'Previous', exact: true }).click();
  await assertCards(grid, 39, 3, 'Sorted A080', 'Sorted Z038');
});
