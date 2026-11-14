import { expect, test } from '@playwright/test';

test('real CP discovery and details responses render Arabic without changing canonical titles', async ({ page, request }) => {
  test.skip(process.env.CP_ARABIC_INTEGRATION !== '1', 'Requires disposable Arabic upstream fixture server');
  const response = await request.get('/api/tmdb/discover');
  const movie = (await response.json()).results[0];
  expect(movie.title).toBe('The Blue Elephant');
  expect(movie.original_title).toBe('الفيل الأزرق');
  expect(movie.original_language).toBe('ar');
  await page.goto('/discover');
  await page.getByRole('heading', { name: 'الفيل الأزرق', exact: true }).click();
  const card = page.locator('.unified-movie-card-expanded:visible');
  await expect(card).toContainText('حبكة الفيلم باللغة العربية');
  await card.getByRole('button', { name: 'English', exact: true }).click();
  await expect(card).toContainText('The Blue Elephant');
  await expect(card).toContainText('English plot.');
  const canonical = await request.get('/api/tmdb/details?tmdb_id=700701');
  expect((await canonical.json()).title).toBe('The Blue Elephant');
});
