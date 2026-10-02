import { expect, test } from '@playwright/test';

test.use({ viewport: { width: 1920, height: 1080 }, actionTimeout: 10000 });

const items = [
  { path_key: 'e:\\movies\\first.mkv', movie_key: 'tmdb:348', tmdb_id: '348', imdb_id: 'tt0078748', title: 'Alien', year: '1979' },
  { path_key: 'e:\\movies\\second.mkv', movie_key: 'tmdb:679', tmdb_id: '679', imdb_id: 'tt0090605', title: 'Aliens', year: '1986' },
  { path_key: 'e:\\movies\\unknown.mkv', movie_key: '', tmdb_id: '', imdb_id: '', title: 'Unmatched film', year: '' }
].map((item) => ({ ...item, poster_url: '', position_ms: 300000, duration_ms: 600000, progress: 0.5, remaining_seconds: 300, last_played_at: 1000 }));

async function prepare(page, { tvSelected = false } = {}) {
  await page.route('**/api/player/continue-watching**', (route) => route.fulfill({ json: { items } }));
  await page.route('**/api/tv/continue-watching**', (route) => route.fulfill({ json: { items: [] } }));
  await page.route('**/api/tmdb/details**', (route) => {
    const id = new URL(route.request().url()).searchParams.get('tmdb_id');
    const movie = items.find((item) => item.tmdb_id === id);
    return route.fulfill({ json: { ...movie, plot: `Full details for ${movie?.title}`, cast: [], directors: [], writers: [], genres: ['Science Fiction'], keywords: [] } });
  });
  await page.route('**/api/library/check', (route) => route.fulfill({ json: { results: [] } }));
  if (tvSelected) {
    await page.route('**/api/tv/capabilities', (route) => route.fulfill({ json: { enabled: true } }));
    await page.addInitScript(() => sessionStorage.setItem('cp-discover-media', 'tv'));
  }
  await page.goto('/');
  const rail = page.getByRole('region', { name: 'Continue Watching movies', exact: true });
  await expect(rail.locator('.continue-movie-card')).toHaveCount(3);
  return rail;
}

test('Continue Watching keeps only the selected menu open with mouse and keyboard', async ({ page }) => {
  const rail = await prepare(page);
  const menus = rail.locator('.continue-movie-menu');
  await menus.nth(0).locator('summary').click();
  await expect(menus.nth(0)).toHaveAttribute('open', '');
  await page.getByRole('heading', { name: 'Continue Watching', exact: true }).click();
  await expect(menus.nth(0)).toHaveAttribute('open', '');
  await menus.nth(1).locator('summary').click();
  await expect(menus.nth(1)).toHaveAttribute('open', '');
  await expect(rail.locator('.continue-movie-menu[open]')).toHaveCount(1);
  await expect(menus.nth(0)).not.toHaveAttribute('open');
  if (process.env.CP_CONTINUE_EVIDENCE_PATH) {
    await page.locator('.continue-watching-panel').screenshot({ path: process.env.CP_CONTINUE_EVIDENCE_PATH });
  }
  await menus.nth(1).locator('summary').click();
  await expect(rail.locator('.continue-movie-menu[open]')).toHaveCount(0);
  await menus.nth(0).locator('summary').focus();
  await page.keyboard.press('Enter');
  await menus.nth(1).locator('summary').focus();
  await page.keyboard.press('Space');
  await expect(menus.nth(1)).toHaveAttribute('open', '');
  await expect(rail.locator('.continue-movie-menu[open]')).toHaveCount(1);
});

test('Continue Watching View card opens only that expanded movie and supports a second selection', async ({ page }) => {
  let rail = await prepare(page);
  for (const index of [0, 1]) {
    const tile = rail.locator('.continue-movie-card').nth(index);
    await tile.locator('summary').click();
    await tile.getByRole('button', { name: 'View card', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Discover', exact: true })).toBeVisible();
    const cards = page.locator('.workspace-panel:not([hidden]) .discover-movie-card');
    await expect(cards).toHaveCount(1);
    await expect(page.locator('.workspace-panel:not([hidden]) .discover-card-expanded')).toContainText(items[index].title);
    await expect(page.locator('.workspace-path-bar')).toContainText(`Continue Watching: ${items[index].title}`);
    await page.getByRole('button', { name: 'Home', exact: true }).click();
    rail = page.getByRole('region', { name: 'Continue Watching movies', exact: true });
    await expect(rail.locator('.continue-movie-menu[open]')).toHaveCount(0);
  }
});

test('Continue Watching View card selects Movies when Discover last showed TV', async ({ page }) => {
  const rail = await prepare(page, { tvSelected: true });
  const tile = rail.locator('.continue-movie-card').first();
  await tile.locator('summary').click();
  await tile.getByRole('button', { name: 'View card', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Explore Movies', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('.discover-card-expanded')).toBeVisible();
  await expect(page.locator('.discover-card-expanded')).toContainText('Alien');
  await expect.poll(() => page.evaluate(() => sessionStorage.getItem('cp-discover-media'))).toBe('movie');
  await page.getByRole('button', { name: 'Explore Shows', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Explore Shows', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  const nextTile = rail.locator('.continue-movie-card').nth(1);
  await nextTile.locator('summary').click();
  await nextTile.getByRole('button', { name: 'View card', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Explore Movies', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('.discover-card-expanded')).toBeVisible();
  await expect(page.locator('.discover-card-expanded')).toContainText('Aliens');
});

test('Continue Watching explains missing identity without searching for a different movie', async ({ page }) => {
  const searches = [];
  await page.route('**/api/tmdb/search**', (route) => {
    searches.push(route.request().url());
    return route.fulfill({ json: { results: [] } });
  });
  const rail = await prepare(page);
  const tile = rail.locator('.continue-movie-card').nth(2);
  await tile.locator('summary').click();
  await tile.getByRole('button', { name: 'View card', exact: true }).click();
  await expect(page.getByText(/Unmatched film.*no saved TMDB identity/)).toBeVisible();
  await expect(rail).toBeVisible();
  await expect(rail.locator('.continue-movie-menu[open]')).toHaveCount(0);
  expect(searches).toEqual([]);
});
