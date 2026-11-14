import { test, expect } from '@playwright/test';

test('IPTV portrait browsing preserves provider filters and Back restoration', async ({ page }) => {
  await page.goto('/iptv');
  await page.getByRole('button', { name: 'Movies', exact: true }).click();
  await page.getByRole('button', { name: 'CP View', exact: true }).click();
  const card = page.locator('.iptv-movie-card').filter({ hasText: 'First Enriched Movie' });
  await card.getByRole('heading', { name: 'First Enriched Movie', exact: true }).click();
  await expect(card.getByRole('button', { name: 'Open biography for Fixture Actor', exact: true })).toBeVisible();
  await card.getByRole('button', { name: 'Open biography for Fixture Actor', exact: true }).scrollIntoViewIfNeeded();
  const portrait = await card.locator('.person-avatar').first().boundingBox();
  expect(portrait.width).toBe(106);
  expect(portrait.height).toBe(132);
  if (process.env.CP_IPTV_EVIDENCE_DIR) await page.screenshot({ path: process.env.CP_IPTV_EVIDENCE_DIR + '/iptv-cast.png' });
  await page.route('**/people/103', route => route.fulfill({ json: {
    id: '103', name: 'Fixture Actor', biography: 'The actor biography.', profile_url: '',
  } }));
  await card.getByRole('button', { name: 'Open biography for Fixture Actor', exact: true }).click();
  await expect(page.getByText('The actor biography.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /Close.*biography/i }).click();
  await card.locator('.person-credit-browse').filter({ hasText: 'Fixture Actor' }).click();
  await expect(page.getByRole('button', { name: 'Back to previous IPTV view' })).toBeVisible();
  await expect(page.locator('.iptv-movie-card')).toHaveCount(1);
  await page.getByPlaceholder('Search movie...', { exact: true }).fill('No matching film');
  await expect(page.locator('.iptv-movie-card')).toHaveCount(0);
  const resetResponse = page.waitForResponse(response => response.url().includes('/movies?')
    && !new URL(response.url()).searchParams.get('q'));
  await page.getByRole('button', { name: 'Reset filters', exact: true }).click();
  expect(new URL((await resetResponse).url()).searchParams.get('person_id')).toBe('103');
  await expect(page.locator('.iptv-movie-card')).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Back to previous IPTV view' })).toBeVisible();
  await page.getByRole('button', { name: 'Back to previous IPTV view' }).click();
  await expect(card.getByRole('button', { name: 'Open filmography for Fixture Actor', exact: true })).toBeVisible();
  await card.locator('.person-credit-browse').filter({ hasText: 'Fixture Actor' }).click();
  await page.getByRole('button', { name: 'Provider View', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Back to previous IPTV view' })).toHaveCount(0);
});

test('missing person identity explains disabled filmography without fetching a biography', async ({ page }) => {
  await page.route('**/movies/tmdb%3A550', async route => {
    const response = await route.fetch();
    const movie = await response.json();
    movie.cast = [{ name: 'Unknown Credit', character: 'Witness' }];
    await route.fulfill({ json: movie });
  });
  await page.goto('/iptv');
  await page.getByRole('button', { name: 'Movies', exact: true }).click();
  await page.getByRole('button', { name: 'CP View', exact: true }).click();
  await page.getByRole('heading', { name: 'First Enriched Movie', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Filmography unavailable: no TMDB person ID for this credit.', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Open biography for Unknown Credit', exact: true }).click();
  await expect(page.getByText('No TMDB person ID is available for this credit.', { exact: true })).toBeVisible();
});

test.describe('large desktop with 150% display density', () => {
  test.use({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1.5 });
  test('cast actions keep the shared rail geometry', async ({ page }) => {
    await page.goto('/iptv');
    await page.getByRole('button', { name: 'Movies', exact: true }).click();
    await page.getByRole('button', { name: 'CP View', exact: true }).click();
    const card = page.locator('.iptv-movie-card').filter({ hasText: 'First Enriched Movie' });
    await card.getByRole('heading', { name: 'First Enriched Movie', exact: true }).click();
    const bio = card.getByRole('button', { name: 'Open biography for Fixture Actor', exact: true });
    await bio.scrollIntoViewIfNeeded();
    await expect(bio).toBeVisible();
    await expect(card.getByRole('button', { name: 'Open filmography for Fixture Actor', exact: true })).toBeVisible();
    const portrait = await card.locator('.person-avatar').first().boundingBox();
    expect(portrait.width).toBe(106);
    expect(portrait.height).toBe(132);
    if (process.env.CP_IPTV_EVIDENCE_DIR) await page.screenshot({ path: process.env.CP_IPTV_EVIDENCE_DIR + '/iptv-cast-1920-150.png' });
  });
});

for (const [person, personId, role] of [['Fixture Actor', '103', 'actor'], ['Fixture Director', '101', 'director']]) {
  test(`${role} Filmography opens full Movie Discover while the portrait remains provider-local`, async ({ page }) => {
    await page.addInitScript(() => sessionStorage.setItem('cp-discover-media', 'tv'));
    let creditsRequest;
    const outside = { tmdb_id: 99999991, title: 'A Film Outside IPTV', year: '1998', genres: ['Drama'] };
    await page.route('**/api/tmdb/person_movies**', route => {
      creditsRequest = new URL(route.request().url());
      return route.fulfill({ json: { results: [outside], page: 1, total_pages: 1, total_results: 1 } });
    });
    await page.goto('/iptv');
    await page.getByRole('button', { name: 'Movies', exact: true }).click();
    await page.getByRole('button', { name: 'CP View', exact: true }).click();
    const card = page.locator('.iptv-movie-card').filter({ hasText: 'First Enriched Movie' });
    await card.getByRole('heading', { name: 'First Enriched Movie', exact: true }).click();
    await card.getByRole('button', { name: `Open filmography for ${person}`, exact: true }).click();
    await expect(page).toHaveURL(/\/discover$/);
    await expect(page.getByRole('heading', { name: outside.title, exact: true })).toBeVisible();
    await expect(page.getByText(`IPTV > ${role === 'actor' ? 'Actor' : 'Director'}: ${person}`, { exact: true })).toBeVisible();
    expect(creditsRequest.searchParams.get('person_id')).toBe(personId);
    expect(creditsRequest.searchParams.get('role')).toBe(role);
    await expect(page.getByRole('button', { name: 'Movies', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await page.getByRole('button', { name: 'IPTV', exact: true }).click();
    await expect(card.getByRole('button', { name: `Open filmography for ${person}`, exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Back to previous IPTV view' })).toHaveCount(0);
  });
}
