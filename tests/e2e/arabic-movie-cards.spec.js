import { expect, test } from '@playwright/test';

const movie = { tmdb_id: '700701', title: 'The Blue Elephant', original_title: 'الفيل الأزرق', original_language: 'ar', language: 'Arabic', year: '2014', plot: 'English plot.', genres: ['Drama'], poster_url: '', release_date: '2014-01-01' };
const translated = { ...movie, title: 'الفيل الأزرق', plot: 'حبكة الفيلم باللغة العربية', genres: ['دراما'], cast: [{ id: 1, name: 'كريم عبد العزيز' }] };
const foreign = { ...movie, tmdb_id: '700702', title: 'English Movie', original_title: 'English Movie', original_language: 'en', language: 'English' };
const item = { path: 'E:/Movies/Elephant.mkv', title: movie.title, metadata_accepted: true, metadata_status: 'accepted', resolution: '1080p', canonical_metadata: { ...movie, accepted: true } };

async function fixtures(page, { failArabic = false, gate } = {}) {
  const state = { requests: 0, failArabic };
  await page.route('**/api/tmdb/discover**', route => route.fulfill({ json: { results: [movie, foreign], page: 1, total_pages: 1, total_results: 2 } }));
  await page.route('**/api/tmdb/related**', route => route.fulfill({ json: { results: [movie], page: 1, total_pages: 1 } }));
  await page.route('**/api/library/check', route => route.fulfill({ json: { results: [], catalog_generation: 1 } }));
  await page.route('**/api/tmdb/details**', async route => {
    const params = new URL(route.request().url()).searchParams;
    const arabic = params.get('language') === 'ar-SA';
    if (arabic) { state.requests++; if (gate) await gate; }
    if (arabic && state.failArabic) return route.fulfill({ status: 503, json: { error: 'Arabic unavailable' } });
    return route.fulfill({ json: arabic ? translated : params.get('tmdb_id') === foreign.tmdb_id ? foreign : movie });
  });
  await page.route('**/api/library/search/advanced', route => route.fulfill({ json: { items: [item], total: 1, page: 1, total_pages: 1, page_start: 0, page_end: 1, catalog_generation: 1, facets: { genres: [], countries: [], languages: [], sources: [] }, stats: { total: 1, matched: 1, pending: 0, unmatched: 0, low: 0 } } }));
  await page.route('**/api/library/details**', route => route.fulfill({ json: { item, catalog_generation: 1 } }));
  await page.route('**/api/user/followed-releases**', route => route.fulfill({ json: { movies: [{ ...movie, status: 'watching' }], newly_available: [], removed_owned: [], curation_generation: 1 } }));
  await page.route('**/api/player/continue-watching**', route => route.fulfill({ json: { items: [{ ...movie, path_key: 'arabic-resume', progress: .4, remaining_seconds: 1200 }] } }));
  await page.route('**/api/tv/continue-watching**', route => route.fulfill({ json: { items: [] } }));
  return state;
}

for (const surface of ['discover', 'library']) test(`${surface}: Arabic default, English choice, cached reopening`, async ({ page }) => {
  const state = await fixtures(page);
  await page.goto(`/${surface}`);
  const heading = page.getByRole('heading', { name: movie.original_title, exact: true });
  await expect(heading).toBeVisible();
  expect(state.requests).toBe(0);
  await heading.click();
  const card = page.locator('.unified-movie-card-expanded:visible');
  await expect(card).toContainText(translated.plot);
  await card.getByRole('button', { name: 'English', exact: true }).click();
  await expect(card.getByRole('heading', { name: movie.title, exact: true })).toBeVisible();
  await expect(card).toContainText(movie.plot);
  await card.getByRole('heading', { name: movie.title, exact: true }).click();
  await page.getByRole('heading', { name: movie.title, exact: true }).click();
  await expect(card.getByRole('button', { name: 'العربية', exact: true })).toBeVisible();
  await card.getByRole('button', { name: 'العربية', exact: true }).click();
  await expect(card).toContainText(translated.plot);
  expect(state.requests).toBe(1);
  await expect(card).toHaveJSProperty('scrollWidth', await card.evaluate(el => el.clientWidth));
  await card.screenshot({ path: test.info().outputPath(`${surface}-arabic.png`) });
});

test('translation failure retains Arabic title and source plot, then retries', async ({ page }) => {
  const state = await fixtures(page, { failArabic: true });
  await page.goto('/discover');
  await page.getByRole('heading', { name: movie.original_title, exact: true }).click();
  const card = page.locator('.unified-movie-card-expanded:visible');
  await expect(card).toContainText('Arabic unavailable');
  await expect(card).toContainText(movie.plot);
  await expect(card).toContainText(movie.original_title);
  state.failArabic = false;
  await card.getByRole('button', { name: 'Retry Arabic', exact: true }).click();
  await expect(card).toContainText(translated.plot);
  expect(state.requests).toBe(2);
});

test('foreign movies retain English and related Arabic titles use the same rule', async ({ page }) => {
  const state = await fixtures(page);
  await page.goto('/discover');
  await page.getByRole('heading', { name: foreign.title, exact: true }).click();
  const card = page.locator('.unified-movie-card-expanded:visible');
  await expect(card.getByRole('button', { name: 'العربية', exact: true })).toBeVisible();
  await expect(card.getByRole('button', { name: `Open ${movie.original_title} in Discover`, exact: true })).toBeVisible();
  expect(state.requests).toBe(0);
});

test('Home movie rails and inspector default to Arabic', async ({ page }) => {
  const state = await fixtures(page);
  await page.goto('/');
  await expect(page.locator('.release-list')).toContainText(movie.original_title);
  await expect(page.locator('.continue-watching-panel')).toContainText(movie.original_title);
  const rail = page.locator('.upcoming-movie-card').filter({ hasText: movie.original_title }).first();
  await expect(rail).toBeVisible();
  expect(state.requests).toBe(0);
  await rail.click();
  const card = page.locator('.home-detail-card');
  await expect(card).toContainText(translated.plot);
  await card.getByRole('button', { name: 'English', exact: true }).click();
  await expect(card).toContainText(movie.title);
});

test('a late Arabic response cannot translate a different movie', async ({ page }) => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const state = await fixtures(page, { gate });
  await page.goto('/discover');
  await page.getByRole('heading', { name: movie.original_title, exact: true }).click();
  await expect.poll(() => state.requests).toBe(1);
  await page.getByRole('heading', { name: foreign.title, exact: true }).click();
  release();
  const card = page.locator('.unified-movie-card-expanded:visible');
  await expect(card.getByRole('heading', { name: foreign.title, exact: true })).toBeVisible();
  await expect(card.getByRole('button', { name: 'العربية', exact: true })).toBeVisible();
  await expect(card).not.toContainText(translated.plot);
});

test('Lists keeps Arabic metadata in cached cards and expands in Arabic', async ({ page }) => {
  await fixtures(page);
  await page.route('**/api/user/lists**', route => route.fulfill({ json: { lists: [{ id: 'watchlist', name: 'Watchlist', system_type: 'watchlist', movies: [movie] }], curation_generation: 1 } }));
  await page.route('**/api/tmdb/card-projections', route => route.fulfill({ json: { items: { [`tmdb:${movie.tmdb_id}`]: movie }, catalog_generation: 1 } }));
  await page.goto('/movie-lists');
  await page.getByRole('heading', { name: movie.original_title, exact: true }).click();
  const card = page.locator('.unified-movie-card-expanded:visible');
  await expect(card).toContainText(translated.plot);
  await expect(card.getByRole('button', { name: 'English', exact: true })).toBeVisible();
});

test('English switches immediately while Arabic loads and survives its late response', async ({ page }) => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const state = await fixtures(page, { gate });
  try {
    await page.goto('/discover');
    await page.getByRole('heading', { name: movie.original_title, exact: true }).click();
    await expect.poll(() => state.requests).toBe(1);
    const card = page.locator('.unified-movie-card-expanded:visible');
    const english = card.getByRole('button', { name: 'English', exact: true });
    await expect(english).toBeEnabled({ timeout: 1500 });
    await english.click();
    await expect(card).toContainText(movie.title);
    const completed = page.waitForResponse(response => response.url().includes('language=ar-SA'));
    release();
    await completed;
    await expect(card.getByRole('button', { name: 'العربية', exact: true })).toBeVisible();
    await expect(card).not.toContainText(translated.plot);
  } finally { release(); }
});
