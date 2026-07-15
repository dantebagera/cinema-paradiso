import { expect, test } from '@playwright/test';

const workspaces = [
  ['/', 'heading', 'Home'],
  ['/library', 'heading', 'Movie View'],
  ['/movie-lists', 'heading', 'Movie Lists'],
  ['/cleanup', 'heading', 'Library Maintenance'],
  ['/discover', 'heading', 'Discover'],
  ['/ai-control', 'heading', 'AI Control'],
  ['/downloads', 'region', 'Downloads powered by qBittorrent'],
  ['/help', 'heading', 'Help'],
  ['/settings', 'heading', 'Settings']
];

for (const [path, role, name] of workspaces) {
  test(`${path} renders without a workspace crash`, async ({ page }) => {
    const pageErrors = [];
    page.on('pageerror', (error) => pageErrors.push(error.message));

    const response = await page.goto(path, { waitUntil: 'domcontentloaded' });

    expect(response?.ok()).toBeTruthy();
    await expect(page.getByRole(role, { name })).toBeVisible();
    await expect(page.locator('.app-crash-screen')).toHaveCount(0);
    expect(pageErrors).toEqual([]);
  });
}

test('Library switches between canonical movie and raw file views', async ({ page }) => {
  await page.goto('/library', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Movie View' })).toBeVisible();

  await page.getByRole('button', { name: 'File View' }).click();
  await expect(page.getByRole('heading', { name: 'File View' })).toBeVisible();

  await page.getByRole('button', { name: 'Movie View' }).click();
  await expect(page.getByRole('heading', { name: 'Movie View' })).toBeVisible();
});

test('Maintenance tabs remain interactive after the audit loads', async ({ page }) => {
  await page.goto('/cleanup', { waitUntil: 'domcontentloaded' });
  const storage = page.getByRole('tab', { name: 'Storage' });
  const identity = page.getByRole('tab', { name: 'Identity' });

  await expect(storage).toHaveAttribute('aria-selected', 'true');
  await identity.click();
  await expect(identity).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('.app-crash-screen')).toHaveCount(0);
});

test('Maintenance upgrade summary opens the authoritative Library filter', async ({ page }) => {
  await page.goto('/cleanup', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: /Upgrade candidates/ }).click();

  await expect(page).toHaveURL(/\/library$/);
  await expect(page.getByRole('heading', { name: 'Movie View' })).toBeVisible();
  await page.getByRole('button', { name: 'Open Filters' }).click();
  await expect(page.getByLabel('Library quality filter')).toHaveValue('upgrade');
  await expect(page.getByText('Upgrade candidate', { exact: true }).first()).toBeVisible();
});
