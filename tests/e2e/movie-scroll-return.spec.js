import { expect, test } from '@playwright/test';

test.use({ viewport: { width: 1790, height: 940 }, reducedMotion: 'reduce' });
const movies = Array.from({ length: 18 }, (_, index) => ({
  tmdb_id: String(9100 + index), title: `Scroll movie ${index + 1}`, year: '2025',
  genres: ['Drama'], tmdb_rating: '7.8', poster_url: '', summary: 'Scroll return fixture.',
  cast: [], directors: [], recommendations: [], similar: [],
}));
const files = movies.map(movie => ({
  ...movie, path: `E:/Movies/${movie.tmdb_id}.mkv`, metadata_accepted: true,
  canonical_metadata: { ...movie, rating: '7.8', accepted: true },
}));
const controls = page => page.getByRole('button', { name: 'Search, filters & selection', exact: true });
const scrollTop = page => page.locator('main.workspace').evaluate(el => el.scrollTop);

async function fixtures(page, surface) {
  await page.route('**/api/tv/capabilities', route => route.fulfill({ json: { enabled: true } }));
  await page.route('**/api/user/lists**', route => route.fulfill({ json: {
    lists: [{ id: 'scroll-list', name: 'Scroll list', movies }], curation_generation: 1,
  } }));
  await page.route('**/api/library/check', route => route.fulfill({ json: {
    results: (route.request().postDataJSON().movies || []).map(movie => ({ ...movie, found: false })), catalog_generation: 1,
  } }));
  await page.route('**/api/tmdb/card-projections', route => route.fulfill({ json: { items: Object.fromEntries(movies.map(movie => [movie.tmdb_id, movie])), catalog_generation: 1 } }));
  await page.route('**/api/tmdb/details**', route => route.fulfill({ json: movies.find(movie => movie.tmdb_id === new URL(route.request().url()).searchParams.get('tmdb_id')) || movies[0] }));
  await page.route('**/api/library/details**', route => route.fulfill({ json: { item: files[0], catalog_generation: 1 } }));
  await page.route('**/api/tmdb/discover**', route => route.fulfill({ json: { results: movies, page: 1, total_pages: 1, total_results: movies.length } }));
  await page.route('**/api/library/search/advanced', route => route.fulfill({ json: {
    items: files, total: files.length, page: 1, total_pages: 1, page_start: 0, page_end: files.length,
    catalog_generation: 1, facets: { genres: [], countries: [], languages: [], sources: [] },
    stats: { total: files.length, matched: files.length, pending: 0, unmatched: 0, low: 0 },
  } }));
  await page.route('**/api/ai-control/preview', route => route.fulfill({ json: {
    state: 'valid_plan', plan_id: 'scroll-preview', action: 'list', summary: 'Scroll preview',
    total_matches: movies.length, items: movies.map(movie => ({ ...movie, selection_key: movie.tmdb_id })), blocked: [], warnings: [],
  } }));
  await page.route('**/api/ollama/recommend', route => route.fulfill({ json: { results: movies, model: 'Fixture' } }));
  await page.route('**/api/explore/indexers', route => route.fulfill({ json: { indexers: [{ id: 'fixture', name: 'Fixture' }] } }));
  await page.route('**/api/explore/browse**', route => route.fulfill({ json: { results: movies.map(movie => ({
    ...movie, parsed_title: movie.title, parsed_year: movie.year, metadata: movie,
    variants: [{ title: `${movie.title}.1080p`, resolution: '1080p', indexer: 'Fixture', seeders: 20, size_human: '2 GB' }],
  })) } }));
  await page.route('**/api/metadata?**', route => route.fulfill({ json: movies[0] }));
  await page.goto(['pick', 'browse'].includes(surface) ? '/discover' : `/${surface}`);
  if (surface === 'ai-control') {
    await page.getByPlaceholder('Tell CP what to find, list, download, or delete...').fill('List movies');
    await page.getByRole('button', { name: 'Preview command' }).click();
  }
  if (surface === 'pick') {
    await page.getByRole('button', { name: 'Pick My Movie', exact: true }).click();
    await controls(page).click();
    await page.getByPlaceholder('Something funny but a little sad, maybe an indie movie with a warm ending...').fill('A drama');
    await page.getByRole('button', { name: 'Ask AI', exact: true }).click();
  }
  if (surface === 'browse') {
    await page.getByRole('button', { name: 'Browse Indexers', exact: true }).click();
    await controls(page).click();
    await page.getByRole('button', { name: 'Load latest', exact: true }).click();
  }
  await expect(page.locator('.unified-movie-card:visible').nth(6)).toBeAttached();
}

for (const surface of ['discover', 'library', 'movie-lists', 'ai-control', 'pick', 'browse']) {
  test(`${surface} restores the pre-expansion scroll after repeated mouse and keyboard collapses`, async ({ page }) => {
    await fixtures(page, surface);
    if (await controls(page).count() && await controls(page).getAttribute('aria-expanded') === 'false') await controls(page).click();
    const workspace = page.locator('main.workspace');
    const card = page.locator('.unified-movie-card:visible').nth(6);
    for (const keyboard of [false, true]) {
      await workspace.evaluate(el => el.scrollTo({ top: 420, behavior: 'instant' }));
      const heading = card.locator('.unified-movie-main h3');
      await heading.scrollIntoViewIfNeeded();
      if (keyboard) await card.focus();
      const before = await scrollTop(page);
      expect(before).toBeGreaterThan(100);
      if (keyboard) await card.press('Enter');
      else await heading.click();
      await expect(card).toHaveClass(/unified-movie-card-expanded/);
      await expect.poll(async () => Math.abs(await scrollTop(page) - before)).toBeGreaterThan(30);
      // Read lower content and manually reopen controls during card viewing.
      if (await controls(page).count() && await controls(page).getAttribute('aria-expanded') === 'false') await controls(page).click();
      await workspace.evaluate(el => el.scrollBy({ top: 120, behavior: 'instant' }));
      if (keyboard) await card.press(' ');
      else await heading.click();
      await expect(card).not.toHaveClass(/unified-movie-card-expanded/);
      await expect.poll(() => scrollTop(page)).toBe(before);
    }
  });
}

test('expanding the last card leaves no blank footer and collapse restores scrolling', async ({ page }) => {
  await fixtures(page, 'discover');
  const workspace = page.locator('main.workspace');
  const card = page.locator('.unified-movie-card:visible').last();
  const heading = card.locator('.unified-movie-main h3');
  await heading.scrollIntoViewIfNeeded();
  const before = await scrollTop(page);
  await heading.click();
  await expect(card).toHaveClass(/unified-movie-card-expanded/);
  const blankFooter = await workspace.evaluate(element => {
    const panel = element.querySelector('.workspace-panel:not([hidden])');
    const contentEnd = panel.getBoundingClientRect().bottom - element.getBoundingClientRect().top + element.scrollTop;
    return element.scrollHeight - contentEnd - parseFloat(getComputedStyle(element).paddingBottom);
  });
  expect(blankFooter).toBeLessThanOrEqual(1);
  await workspace.evaluate(element => element.scrollTo({ top: element.scrollHeight, behavior: 'instant' }));
  await expect(card.getByRole('button', { name: 'View all', exact: true })).toBeInViewport();
  await heading.click();
  await expect(card).not.toHaveClass(/unified-movie-card-expanded/);
  await expect.poll(() => workspaceReturnDistance(page, before)).toBeLessThanOrEqual(1);
});

test('Switching movies lets the new expanded card own scrolling', async ({ page }) => {
  await fixtures(page, 'discover');
  const cards = page.locator('.unified-movie-card:visible');
  const first = cards.nth(6);
  const second = cards.nth(10);
  await first.locator('h3').click();
  await expect(first).toHaveClass(/unified-movie-card-expanded/);
  await second.locator('h3').scrollIntoViewIfNeeded();
  const before = await scrollTop(page);
  await second.locator('h3').click();
  await expect(second).toHaveClass(/unified-movie-card-expanded/);
  await expect(first).not.toHaveClass(/unified-movie-card-expanded/);
  await expect.poll(async () => {
    const card = await second.boundingBox();
    const chrome = await page.locator('.workspace-chrome:visible').boundingBox();
    return card.y >= chrome.y + chrome.height - 1 && card.y < 940;
  }).toBe(true);
  await second.locator('.unified-movie-main h3').click();
  // The first expanded card made the page taller; the browser can only return
  // as far as the collapsed page's scrollable end.
  await expect.poll(async () => workspaceReturnDistance(page, before)).toBe(0);
});

async function workspaceReturnDistance(page, before) {
  return page.locator('main.workspace').evaluate((el, top) =>
    Math.abs(el.scrollTop - Math.min(top, el.scrollHeight - el.clientHeight)), before);
}
