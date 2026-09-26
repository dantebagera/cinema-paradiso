import { test, expect } from '@playwright/test';

test.skip(process.env.CP_TV_E2E !== '1', 'Requires the isolated native-TV fixture server');

test.beforeEach(async ({ request }) => {
  for (const id of [2, 3]) await request.post(`/api/tv/episodes/${id}/progress`, { data: { restart: true } });
});

test('TV library uses CP cards, preserves movie state and opens a dedicated series route', async ({ page }) => {
  await page.goto('/library');
  const switcher = page.getByRole('tablist', { name: 'Library media' });
  await switcher.getByRole('button', { name: 'TV Shows', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Open Harbor Signals' })).toContainText('2 seasons · 6 episodes');
  await expect(page.getByRole('link', { name: 'Open Harbor Signals' })).toContainText('Mixed quality');
  await page.getByRole('textbox', { name: 'Search TV shows', exact: true }).fill('Harbor');
  await page.getByRole('button', { name: 'Search TV', exact: true }).click();
  await switcher.getByRole('button', { name: 'Movies', exact: true }).click();
  await expect(page.getByText('Movie View', { exact: true }).first()).toBeVisible();
  await switcher.getByRole('button', { name: 'TV Shows', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Search TV shows', exact: true })).toHaveValue('Harbor');
  await page.screenshot({ path: 'docs/verification/tv-parity/library.png', fullPage: true });
  await page.getByRole('link', { name: 'Open Harbor Signals' }).click();
  await expect(page).toHaveURL(/\/tv\/series\/1$/);
  await expect(page.getByRole('heading', { name: 'Harbor Signals', exact: true })).toBeVisible();
  await expect(page.getByRole('article', { name: 'S01E02 The Signal' })).toContainText('Missing locally');
  await page.screenshot({ path: 'docs/verification/tv-parity/series.png', fullPage: true });
  await page.getByLabel('TV season').selectOption('0');
  await expect(page.getByRole('article', { name: 'S00E01 Before the Harbor' })).toBeVisible();
});

test('episode streaming targets exact released episode without marking watched', async ({ page, request }) => {
  await page.route('https://example.invalid/**', (route) => route.fulfill({ body: '<p>Fixture stream</p>', contentType: 'text/html' }));
  await page.goto('/tv/series/1');
  const row = page.getByRole('article', { name: 'S01E02 The Signal' });
  await row.getByRole('button', { name: 'Stream', exact: true }).click();
  await expect(page.locator('iframe[src="https://example.invalid/tv/900001/1/2"]')).toBeVisible();
  const season = await (await request.get('/api/tv/series/1/seasons/1')).json();
  expect(season.items.find((episode) => episode.episode_number === 2).completed).toBeFalsy();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: /^Stream / })).not.toBeVisible();
  await expect(row.getByRole('button', { name: 'Stream', exact: true })).toBeFocused();
});

test('episode completion derives Play next without skipping missing episodes', async ({ page }) => {
  await page.goto('/tv/series/1');
  const row = page.getByRole('article', { name: 'S01E01 Arrival' });
  await row.getByRole('button', { name: 'Versions (1)', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'S01E01 versions' })).toContainText('1080p');
  await page.getByRole('button', { name: 'Close', exact: true }).click();
  await row.getByRole('button', { name: 'Mark watched', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Play next', exact: true })).toBeDisabled();
  await expect(page.getByRole('article', { name: 'S01E02 The Signal' })).toContainText('Unwatched');
});


test('TV Home progress stays typed and opening a missing next episode navigates to its series', async ({ page, request }) => {
  await request.post('/api/tv/episodes/2/progress', { data: { completed: true } });
  await page.goto('/');
  const rail = page.getByRole('region', { name: 'Continue Watching movies and TV shows' });
  await expect(rail).toContainText('Play next · S01E02 · The Signal · Missing locally');
  await rail.getByRole('button', { name: 'Play Harbor Signals', exact: true }).click();
  await expect(page).toHaveURL(/tv\/series\/1$/);
  await expect(page.getByRole('heading', { name: 'Harbor Signals', exact: true })).toBeVisible();
});

test('TV release review explains rejected capture and submits only the accepted fixture', async ({ page }) => {
  await page.goto('/tv/series/1');
  await page.getByRole('article', { name: 'S01E02 The Signal' }).getByRole('button', { name: 'Download episode' }).click();
  const dialog = page.getByRole('dialog', { name: 'TV release review' });
  await expect(dialog.getByRole('button', { name: 'Download selected releases' })).toBeEnabled();
  await dialog.getByLabel(/Show blocked releases/).check();
  await expect(dialog).toContainText('HDCAM');
  await page.screenshot({ path: 'docs/verification/tv-parity/release-review.png', fullPage: true });
  await dialog.getByRole('button', { name: 'Download selected releases' }).click();
  await expect(dialog.getByRole('button', { name: 'Queued', exact:true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Close TV release review' }).click();
  await page.goto('/downloads');
  await page.getByRole('button', { name: 'TV Shows', exact: true }).click();
  await expect(page.getByRole('region', { name: 'TV Downloads' })).toContainText('validating');
  await expect(page.getByTitle('qBittorrent Downloads')).toHaveCount(0);
  await page.screenshot({ path: 'docs/verification/tv-parity/downloads.png', fullPage: true });
});
