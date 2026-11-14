import { test, expect } from '@playwright/test';

test('IPTV provider controls sit below My Lists and retain provider and sync actions', async ({ page }, info) => {
  const registry = await (await page.request.get('/api/iptv/providers')).json();
  const second = registry.providers.find(provider => provider.name === 'Provider Two');
  expect(second).toBeTruthy();
  const syncRequests = [];
  await page.route('**/api/iptv/providers/*/sync', async route => {
    syncRequests.push({ url: route.request().url(), method: route.request().method() });
    await route.fulfill({ json: { success: true } });
  });
  await page.goto('/iptv');
  const workspace = page.locator('section.iptv-workspace');
  const tabs = page.getByRole('navigation', { name: 'IPTV sections' });
  const provider = page.getByLabel('Active IPTV provider');
  const sync = page.getByRole('button', { name: 'Sync IPTV catalog' });
  await expect(provider).toBeVisible();
  await expect(sync).toBeVisible();
  await expect(workspace.locator(':scope > header')).toHaveCount(0);
  await expect(workspace.getByRole('heading', { name: 'IPTV', exact: true })).toHaveCount(0);
  await expect(workspace.getByText('Provider television', { exact: true })).toHaveCount(0);
  const tabBox = await tabs.boundingBox();
  const listBox = await tabs.getByRole('button', { name: 'My Lists', exact: true }).boundingBox();
  const providerBox = await provider.boundingBox();
  const syncBox = await sync.boundingBox();
  expect(providerBox.y).toBeGreaterThanOrEqual(tabBox.y + tabBox.height);
  expect(Math.abs(syncBox.x + syncBox.width - listBox.x - listBox.width)).toBeLessThan(4);
  expect(providerBox.x + providerBox.width).toBeLessThan(syncBox.x);
  expect(Math.abs(providerBox.y + providerBox.height / 2 - syncBox.y - syncBox.height / 2)).toBeLessThan(2);
  await page.screenshot({ path: info.outputPath('iptv-provider-controls.png') });
  await provider.selectOption(second.provider_id);
  await expect(provider).toHaveValue(second.provider_id);
  await sync.click();
  await expect.poll(() => syncRequests.length).toBe(1);
  expect(syncRequests[0]).toMatchObject({ method: 'POST' });
  expect(syncRequests[0].url).toContain(`/providers/${second.provider_id}/sync`);
});
