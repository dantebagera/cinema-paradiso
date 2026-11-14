import { test, expect } from '@playwright/test';

test.skip(process.env.CP_TV_E2E !== '1', 'Requires disposable TV fixture server');

test('review renders the backend season destination and normal lifecycle in existing desktop dialog', async ({ page, request }) => {
  const response = await request.post('/api/tv/search', { data: { series_id: 1, season: 2, episode: 1 } });
  const review = await response.json();
  expect(review.import_destination.state).toBe('ready');
  expect(review.import_destination.path).toMatch(/Harbor Signals[\\/]Season 02$/);
  expect(review.import_policy).toEqual({ version: 1, mode: 'move', seeding_mode: 'none' });
  await page.goto('/tv/series/1');
  await page.getByLabel('TV season').selectOption('2');
  await page.getByRole('article', { name: /S02E01/ }).getByRole('button', { name: 'Download episode' }).click();
  const dialog = page.getByRole('dialog', { name: 'TV release review' });
  await expect(dialog.getByText(`Destination: ${review.import_destination.path}`, { exact: true })).toBeVisible();
  await expect(dialog).toContainText('Verified episodes move into the season folder. Completed downloads are removed from qBittorrent.');
  await expect(dialog.getByRole('button', { name: 'Download selected releases' })).toBeEnabled();
  expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.screenshot({ path: 'docs/verification/tv-normal-import/review.png' });
});

test('unsafe canonical show name retains source browsing while destination review blocks download', async ({ page }) => {
  await page.goto('/discover');
  await page.getByRole('tablist', { name: 'Discover tools' }).getByRole('button', { name: 'TV Shows' }).click();
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await page.getByRole('textbox', { name: 'Search TV shows', exact: true }).fill('Daredevil: Born Again');
  await page.getByRole('button', { name: 'Search TV', exact: true }).click();
  await page.getByRole('link', { name: 'Open Daredevil: Born Again', exact: true }).click();
  await page.getByRole('button', { name: 'Download season', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'TV release review' });
  await expect(dialog).toContainText('canonical show name is unsafe on Windows');
  await expect(dialog.getByRole('button', { name: /Download selected releases|Download available/ })).toBeDisabled();
  await expect(dialog.locator('.tv-release-row').first()).toBeVisible();
  await page.screenshot({ path: 'docs/verification/tv-normal-import/no-home.png' });
});

test('Downloads distinguishes cleanup failure and hides rollback after cleanup begins', async ({ page }) => {
  await page.route('**/api/tv/acquisitions', route => route.fulfill({ json: { items: [{
    id: 'normal', target: 'episode:tmdb:tv:999:1:1', state: 'import_pending', history: [],
    job: { title: 'Verified fixture episode', state: 'cleanup_failed', tv_lifecycle_version: 1,
      destination: 'C:\\TV\\Collection\\Season 01', rollback_available: false,
      tv_import: { imported_files: 1, failed_files: 0 }, last_error: 'qBittorrent unavailable',
      preserving_import_plan: [{ target: 'C:\\TV\\Collection\\Season 01\\episode.mkv' }] },
  }] } }));
  await page.goto('/downloads');
  await page.getByRole('button', { name: 'TV Shows', exact: true }).click();
  const downloads = page.getByRole('region', { name: 'TV Downloads' });
  await expect(downloads).toContainText('Cleanup failed');
  await expect(downloads.getByRole('button', { name: 'Retry cleanup', exact: true })).toBeVisible();
  await expect(downloads.getByRole('button', { name: 'Roll back imported files' })).toHaveCount(0);
});

test('real isolated completion returns the season binding and renders completed status without rollback', async ({ page, request }) => {
  try {
    const response = await request.post('/__tv_fixture/complete-normal');
    expect(response.ok()).toBeTruthy();
    const result = await response.json();
    expect(result.job.state).toBe('imported');
    expect(result.job.import_mode).toBe('move');
    expect(result.source_exists).toBe(false);
    expect(result.binding_paths).toEqual(result.job.imported_paths);
    expect(result.job.imported_paths[0]).toMatch(/Harbor Signals[\\/]Season 02[\\/]Harbor.Signals.S02E01/);
    await page.goto('/downloads');
    await page.getByRole('button', { name: 'TV Shows', exact: true }).click();
    const row = page.getByRole('region', { name: 'TV Downloads' }).locator('article').filter({ hasText: 'Harbor.Signals.S02E01.1080p.WEB-DL.mkv' });
    await expect(row).toContainText('Transfer: imported');
    await expect(row).toContainText(`Destination: ${result.job.destination}`);
    await expect(row).toHaveCSS('background-color', 'rgb(18, 19, 23)');
    await expect(row).toHaveCSS('border-top-style', 'solid');
    await expect(row.getByRole('button', { name: 'Roll back imported files' })).toHaveCount(0);
    const rollback = await request.post(`/api/tv/acquisitions/${result.intent_id}/action`, { data: { action: 'rollback' } });
    expect(rollback.status()).toBe(400);
    await page.screenshot({ path: 'docs/verification/tv-normal-import/completed.png' });
  } finally {
    await request.post('/__tv_fixture/reset-normal');
  }
});

test('ambiguous home selection persists through the owner and refreshes a long desktop destination', async ({ page, request }) => {
  const fixture = await (await request.post('/__tv_fixture/ambiguous-home')).json();
  try {
    await page.goto('/tv/series/1');
    await page.getByLabel('TV season').selectOption('2');
    await page.getByRole('article', { name: /S02E01/ }).getByRole('button', { name: 'Download episode' }).click();
    const dialog = page.getByRole('dialog', { name: 'TV release review' });
    await expect(dialog.getByRole('button', { name: /Download selected releases|Download available/ })).toBeDisabled();
    await dialog.getByLabel('Approved TV show folder').selectOption(fixture.home);
    await expect(dialog.getByText(`Destination: ${fixture.destination}`, { exact: true })).toBeVisible();
    const preview = await (await request.post('/api/tv/search', { data: { series_id: 1, season: 2, episode: 1 } })).json();
    expect(preview.import_destination.show_home).toBe(fixture.home);
    expect(preview.import_destination.path).toBe(fixture.destination);
    expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
    await page.screenshot({ path: 'docs/verification/tv-normal-import/home-choice-long-path.png' });
  } finally {
    await request.post('/__tv_fixture/reset-home');
  }
});

test('review keeps loading, failed search and partial coverage in existing dialog', async ({ page, request }) => {
  let releaseSearch;
  const gate = new Promise(resolve => { releaseSearch = resolve; });
  await page.route('**/api/tv/search', async route => { await gate; await route.fulfill({ status: 503, json: { error: 'Fixture search unavailable' } }); });
  await page.goto('/tv/series/1');
  await page.getByLabel('TV season').selectOption('2');
  await page.getByRole('button', { name: 'Download season', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'TV release review' });
  await expect(dialog.getByRole('status')).toContainText('Searching TV sources');
  releaseSearch();
  await expect(dialog.getByRole('alert')).toContainText('Fixture search unavailable');
  await page.unroute('**/api/tv/search');
  const review = await (await request.post('/api/tv/search', { data: { series_id: 1, season: 2, episode_numbers: [1, 2] } })).json();
  await page.route('**/api/tv/search', route => route.fulfill({ json: review }));
  await dialog.getByRole('button', { name: 'Retry search' }).click();
  await expect(dialog).toContainText('Not covered:');
  await expect(dialog.getByRole('button', { name: 'Download available' })).toBeVisible();
});
