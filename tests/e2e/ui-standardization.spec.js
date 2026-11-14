import { test, expect } from '@playwright/test';

for (const viewport of [{ width: 1600, height: 1000 }, { width: 1280, height: 720 }]) {
  test(`shared UI reference preserves actions and desktop layout at ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('/styleguide');
    const reference = page.getByTestId('shared-ui-reference');
    await expect(reference).toBeVisible();
    const stream = reference.getByRole('button', { name: 'Stream', exact: true });
    expect(await stream.evaluate(el => getComputedStyle(el).color)).toBe('rgb(34, 197, 94)');
    await stream.hover();
    await expect.poll(() => stream.evaluate(el => getComputedStyle(el).color)).toBe('rgb(126, 242, 168)');
    await expect(reference.getByRole('button', { name: 'Working…' })).toBeDisabled();
    await expect(reference.getByRole('button', { name: 'Unavailable' })).toBeDisabled();
    const arabic = reference.getByRole('button', { name: 'إضافة الفيلم إلى القائمة' });
    expect(await arabic.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
    await reference.getByLabel('Search example', { exact: true }).fill('A long search query');
    await reference.getByRole('button', { name: 'Clear search', exact: true }).click();
    await expect(reference.getByLabel('Search example', { exact: true })).toBeFocused();
    await expect(reference.getByLabel('Search example', { exact: true })).toHaveValue('');
    await reference.getByRole('button', { name: 'Select all results' }).click();
    await expect(reference.getByText('3 selected', { exact: true })).toBeVisible();
    await reference.getByRole('button', { name: 'Clear', exact: true }).click();
    await expect(reference.getByText('Select movies', { exact: true })).toBeVisible();
    const paging = reference.getByRole('navigation', { name: 'Example pagination' });
    await expect(paging.getByRole('button', { name: 'Previous' })).toBeDisabled();
    await paging.getByRole('button', { name: 'Next' }).click();
    await paging.getByRole('button', { name: 'Next' }).click();
    await expect(paging.getByText('Showing 7-9 of 9')).toBeVisible();
    await expect(paging.getByRole('button', { name: 'Next' })).toBeDisabled();
    await reference.getByRole('button', { name: 'TV Shows', exact: true }).click();
    await expect(reference.getByRole('button', { name: 'TV Shows', exact: true })).toHaveAttribute('aria-pressed', 'true');
    expect(await reference.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
    await reference.screenshot({ path: info.outputPath('shared-families.png') });
    await reference.getByRole('button', { name: 'Open example dialog' }).click();
    const dialog = page.getByRole('dialog', { name: 'Example dialog', exact: true });
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(reference.getByText('Example saves: 0')).toBeVisible();
    await reference.getByRole('button', { name: 'Open example dialog' }).click();
    await dialog.getByLabel('Example title').press('Enter');
    await expect(dialog).toHaveCount(0);
    await expect(reference.getByText('Example saves: 1')).toBeVisible();
    expect(errors).toEqual([]);
  });
}

test('Maintenance shared section tabs fill the desktop bar equally', async ({ page }) => {
  await page.goto('/cleanup');
  const tabs = page.getByRole('tablist', { name: 'Cleanup workspace tabs' });
  await expect(tabs).toBeVisible();
  const widths = await tabs.getByRole('tab').evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().width));
  expect(widths.length).toBeGreaterThan(2);
  expect(Math.max(...widths) - Math.min(...widths)).toBeLessThan(1);
  expect(await tabs.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
});
