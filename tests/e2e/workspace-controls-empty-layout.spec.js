import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const movie = { tmdb_id: '601', title: 'Layout Test Movie', year: '2026', poster_url: '', genres: ['Drama'], tmdb_rating: '7.5', tmdb_vote_count: 120 };
const show = { id: 701, title: 'Layout Test Show', genres: ['Drama'], first_air_date: '2026-01-01', status: 'Returning Series', available_count: 0, watchlisted: true };
const file = { path: 'E:/Movies/Layout.Test.Movie.2026.mkv', filename: 'Layout.Test.Movie.2026.mkv', title: 'Layout Test Movie (2026)', resolution: '1080p', size: 100, size_human: '100 B', metadata_accepted: true, canonical_metadata: { accepted: true, title: movie.title, year: movie.year, tmdb_id: movie.tmdb_id, genres: ['Drama'], rating: '7.5' } };
const systemLists = [
  { id: 'watchlist', name: 'Watchlist', system_type: 'watchlist', movies: [] },
  { id: 'watched', name: 'Watched', system_type: 'watched', movies: [] }
];
const panel = (page) => page.locator('.workspace-panel:not([hidden]) .workspace-empty-state:visible');
async function chooseList(page, name) {
  await page.getByRole('button', { name: /^Choose (movies|shows) list:/ }).click();
  await page.locator('.lists-picker-options').getByRole('button', { name: new RegExp(`^${name}`) }).click();
}
async function openListControls(page) {
  const toggle = page.getByRole('button', { name: 'Search, filters & selection', exact: true });
  if (await toggle.getAttribute('aria-expanded') !== 'true') await toggle.click();
}


async function common(page, { tv = true, lists = systemLists } = {}) {
  await page.route('**/api/tv/capabilities', (route) => route.fulfill({ json: { enabled: tv } }));
  await page.route('**/api/user/lists**', (route) => route.fulfill({ json: { lists, curation_generation: 1 } }));
  await page.route('**/api/user/followed-releases**', (route) => route.fulfill({ json: { movies: [], newly_available: [], removed_owned: [], curation_generation: 1 } }));
  await page.route('**/api/library/check', (route) => route.fulfill({ json: { results: (route.request().postDataJSON()?.movies || []).map((item) => ({ ...item, found: false })), catalog_generation: 1 } }));
  await page.route('**/api/tmdb/card-projections', (route) => route.fulfill({ json: { items: {}, catalog_generation: 1 } }));
}

async function library(page, { total = 0, matched = 0, items = [], files = items, failure = false } = {}) {
  await common(page);
  await page.route('**/api/library/search/advanced', (route) => {
    if (failure) return route.fulfill({ status: 503, json: { error: 'Fixture library unavailable' } });
    const restricted = route.request().postDataJSON()?.query?.groups?.length > 0;
    const rows = restricted ? [] : items;
    return route.fulfill({ json: { items: rows, total: rows.length, page: 1, total_pages: 1, page_start: 0, page_end: rows.length, catalog_generation: 1, facets: { genres: [], countries: [], languages: [], sources: [] }, stats: { total, matched, pending: 0, unmatched: total - matched, low: 0 } } });
  });
  await page.route('**/api/library?view=files', (route) => route.fulfill({ json: { items: files, count: files.length, catalog_generation: 1 } }));
}

async function discover(page, captured = []) {
  await common(page);
  await page.route('**/api/tmdb/discover**', (route) => {
    const request = route.request().postDataJSON() || Object.fromEntries(new URL(route.request().url()).searchParams);
    captured.push(request);
    const pageSize = Math.min(40, Number(request.page_size || 40));
    return route.fulfill({ json: { results: Array.from({ length: pageSize }, (_, index) => ({ ...movie, tmdb_id: String(601 + index), title: index ? `Layout Movie ${index + 1}` : movie.title })), page: 1, total_pages: 2, total_results: 80 } });
  });
  await page.goto('/discover');
  await expect(page.getByRole('heading', { name: movie.title, exact: true })).toBeVisible();
}

async function evidence(page, name) {
  if (!process.env.CP_LAYOUT_EVIDENCE_DIR) return;
  fs.mkdirSync(process.env.CP_LAYOUT_EVIDENCE_DIR, { recursive: true });
  await page.screenshot({ path: path.join(process.env.CP_LAYOUT_EVIDENCE_DIR, `${name}.png`) });
}

// Catches a separate action row, clipping, or actions that toggle the disclosure.
async function assertCombinedLibraryHeader(page, groupName, refreshName) {
  const controls = page.locator('.workspace-controls:visible');
  const heading = controlsToggle(page);
  const group = page.getByRole('group', { name: groupName, exact: true });
  const refresh = page.getByRole('button', { name: refreshName, exact: true });
  const header = await controls.locator('.workspace-controls-strip').boundingBox();
  const panel = await controls.boundingBox();
  const headingBox = await heading.locator('.workspace-controls-heading').boundingBox();
  const count = await controls.locator('.workspace-controls-summary').boundingBox();
  expect(header.height).toBeLessThanOrEqual(60);
  for (const control of [group, refresh]) {
    await expect(control).toBeVisible();
    const box = await control.boundingBox();
    expect(Math.abs(box.y + box.height / 2 - headingBox.y - headingBox.height / 2)).toBeLessThanOrEqual(1);
    expect(box.x).toBeGreaterThanOrEqual(panel.x);
    expect(box.x + box.width).toBeLessThanOrEqual(panel.x + panel.width);
    expect(box.y).toBeGreaterThanOrEqual(header.y);
    expect(box.y + box.height).toBeLessThanOrEqual(header.y + header.height);
  }
  expect(count.x + count.width).toBeLessThanOrEqual((await group.boundingBox()).x);
  expect(await controls.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  expect(await heading.evaluate(button => button.scrollWidth <= button.clientWidth + 1)).toBe(true);
  expect(await heading.evaluate(button => button.querySelector('button') === null)).toBe(true);
  const maintenance = page.getByRole('button', { name: 'Review TV identity in Maintenance', exact: true });
  if (groupName === 'TV library mode') {
    await expect(maintenance).toBeVisible();
    const box = await maintenance.boundingBox();
    expect(Math.abs(box.y + box.height / 2 - headingBox.y - headingBox.height / 2)).toBeLessThanOrEqual(1);
    expect(box.x + box.width).toBeLessThanOrEqual(panel.x + panel.width);
  }
}

for (const width of [1280, 1600, 2048]) {
  for (const media of ['movie', 'tv']) {
    test(`combined Library header ${media} desktop ${width} keeps views and refresh independent in Media and File View`, async ({ page }) => {
      await page.setViewportSize({ width, height: 1000 });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await library(page, { total: 1, matched: 1, items: [file] });
      let scans = 0;
      await page.route('**/api/library?view=cards&force_scan=1**', route => {
        scans += 1;
        return route.fulfill({ json: { catalog_generation: 1 } });
      });
      await page.route('**/api/tv/catalog/options?**', route => route.fulfill({ json: {} }));
      await page.route('**/api/tv/maintenance?**', route => route.fulfill({ json: { counts: {} } }));
      let searches = 0;
      await page.route('**/api/tv/catalog/search', route => {
        searches += 1;
        return route.fulfill({ json: { items: [show], total: 1, page: 1, total_pages: 1 } });
      });
      await page.route('**/api/tv/files?**', route => route.fulfill({ json: { items: [{ file_id: 1, filename: 'Layout.Episode.mkv', path: 'E:/TV/Layout.Episode.mkv', size: 100, episodes: [], facts: {}, available: false }], total: 1, page: 1, page_size: 50, total_pages: 1 } }));
      await page.goto('/library');
      if (media === 'tv') await page.getByRole('button', { name: 'TV Shows', exact: true }).click();
      const groupName = media === 'tv' ? 'TV library mode' : 'Library mode';
      const refreshName = media === 'tv' ? 'Refresh TV catalog' : 'Rescan library files';
      const group = page.getByRole('group', { name: groupName, exact: true });
      await expect(page.getByRole('heading', { name: media === 'tv' ? show.title : movie.title, exact: true })).toBeVisible();
      for (const view of ['Media View', 'File View', 'Media View']) {
        await group.getByRole('button', { name: view, exact: true }).click();
        await expect(group.getByRole('button', { name: view, exact: true })).toHaveAttribute('aria-pressed', 'true');
        await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'false');
        await assertCombinedLibraryHeader(page, groupName, refreshName);
        const beforeDisclosure = media === 'tv' ? searches : scans;
        await controlsToggle(page).focus();
        await controlsToggle(page).press('Enter');
        await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'true');
        await assertCombinedLibraryHeader(page, groupName, refreshName);
        expect(media === 'tv' ? searches : scans).toBe(beforeDisclosure);
        await page.getByRole('button', { name: refreshName, exact: true }).focus();
        await page.getByRole('button', { name: refreshName, exact: true }).press('Enter');
        await expect.poll(() => media === 'tv' ? searches : scans).toBe(beforeDisclosure + 1);
        await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'true');
        await expect(page.getByRole('button', { name: refreshName, exact: true })).toBeEnabled();
        await controlsToggle(page).click();
        await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'false');
        await evidence(page, `combined-header-${media}-${view.replaceAll(' ', '-')}-${width}`);
      }
      expect(errors).toEqual([]);
    });
  }
}

test('combined Library header retains a disabled scan during loading and exposes scan failure without expanding filters', async ({ page }) => {
  await library(page, { total: 1, matched: 1, items: [file] });
  let releaseScan;
  const scanGate = new Promise(resolve => { releaseScan = resolve; });
  await page.route('**/api/library?view=cards&force_scan=1**', async route => {
    await scanGate;
    await route.fulfill({ status: 503, json: { error: 'Fixture scan failed' } });
  });
  await page.goto('/library');
  const scan = page.getByRole('button', { name: 'Rescan library files', exact: true });
  await expect(page.getByRole('heading', { name: movie.title, exact: true })).toBeVisible();
  await scan.click();
  try {
    await expect(scan).toBeDisabled();
    await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'false');
    await assertCombinedLibraryHeader(page, 'Library mode', 'Rescan library files');
  } finally {
    releaseScan();
  }
  await expect(scan).toBeEnabled();
  await expect(page.locator('.library-status-error')).toContainText('Fixture scan failed');
  await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'false');
});

test('combined Library header keeps a long TV File search summary from crowding view actions', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await library(page);
  await page.route('**/api/tv/catalog/options?**', route => route.fulfill({ json: {} }));
  await page.route('**/api/tv/maintenance?**', route => route.fulfill({ json: { counts: {} } }));
  await page.route('**/api/tv/catalog/search', route => route.fulfill({ json: { items: [], total: 0, page: 1, total_pages: 1 } }));
  await page.route('**/api/tv/files?**', route => route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 50, total_pages: 1 } }));
  await page.goto('/library');
  await page.getByRole('button', { name: 'TV Shows', exact: true }).click();
  await page.getByRole('group', { name: 'TV library mode' }).getByRole('button', { name: 'File View', exact: true }).click();
  await controlsToggle(page).click();
  const search = page.getByLabel('Search TV files', { exact: true });
  for (const query of [
    'A very long TV series folder name with several seasons and a complete episode title to search in the file inventory',
    'Star.Trek.Strange.New.Worlds.S02E03.1080p.WEB.H264-GROUP'
  ]) {
    await search.fill(query);
    const request = page.waitForResponse(response => response.url().includes('/api/tv/files?') && new URL(response.url()).searchParams.get('query') === query);
    await search.press('Enter');
    await request;
    await expect(page.locator('.workspace-controls-summary:visible')).toContainText(query);
    await expect(page.locator('.workspace-controls-summary:visible > span[title]')).toHaveAttribute('title', `Search: ${query}`);
    await controlsToggle(page).click();
    await assertCombinedLibraryHeader(page, 'TV library mode', 'Refresh TV catalog');
    await evidence(page, 'combined-header-tv-long-file-query-1280');
    await controlsToggle(page).click();
    await expect(search).toHaveValue(query);
  }
});

test('Lists reuses styled fields and supports media-tab keyboard navigation without losing queries', async ({ page }) => {
  await common(page);
  await page.route('**/api/tv/lists?**', (route) => route.fulfill({ json: { lists: [{ id: 'watchlist', name: 'Watchlist', count: 0, system: true }], items: [], total: 0, page: 1, page_size: 40, total_pages: 1 } }));
  await page.goto('/movie-lists');
  const movies = page.getByRole('tab', { name: 'Movies', exact: true });
  const tv = page.getByRole('tab', { name: 'TV Shows', exact: true });
  await expect(movies).toHaveAttribute('aria-selected', 'true');
  await openListControls(page);
  const input = page.getByLabel('Search movie list');
  await input.fill('A long list search to preserve across media switches');
  await expect(input.locator('..')).toHaveClass(/library-search/);
  await expect(input.locator('..')).toHaveCSS('outline-style', 'solid');
  await movies.focus();
  await movies.press('ArrowRight');
  await expect(tv).toBeFocused();
  await expect(tv).toHaveAttribute('aria-selected', 'true');
  await openListControls(page);
  await expect(page.getByLabel('Search TV list').locator('..')).toHaveClass(/library-search/);
  await tv.press('Home');
  await expect(input).toHaveValue('A long list search to preserve across media switches');
  await expect(movies).toBeFocused();
  await movies.press('End');
  await expect(tv).toBeFocused();
  await tv.press('ArrowLeft');
  await expect(movies).toBeFocused();
  await evidence(page, 'lists-controls');
});

test('TV-disabled Lists falls back to Movies despite a saved TV preference', async ({ page }) => {
  await common(page, { tv: false });
  await page.addInitScript(() => sessionStorage.setItem('cp-lists-media', 'tv'));
  await page.goto('/movie-lists');
  await openListControls(page);
  await expect(page.getByLabel('Search movie list')).toBeVisible();
  await expect(page.getByRole('tab', { name: 'TV Shows' })).toHaveCount(0);
});

for (const [name, title] of [['Watchlist', 'Your Watchlist is empty.'], ['Watched', 'No watched movies yet.'], ['Following', "You're not following any movies yet."]]) {
  test(`Movie ${name} explains empty membership even with a search`, async ({ page }) => {
    await common(page);
    await page.goto('/movie-lists');
    await chooseList(page, name);
    await openListControls(page);
    await page.getByLabel('Search movie list').fill('nothing');
    await expect(panel(page)).toContainText(title);
    await expect(panel(page).getByRole('button', { name: 'Clear filters' })).toHaveCount(0);
    if (name !== 'Watchlist') await expect(panel(page).getByRole('button', { name: 'Add movie' })).toHaveCount(0);
  });
}

test('Movie list filter recovery retains the list and restores missing cards even when Library is empty', async ({ page }) => {
  await common(page, { lists: [{ id: 'custom', name: 'My custom list', movies: [movie] }] });
  await page.goto('/movie-lists');
  await expect(page.getByRole('heading', { name: movie.title, exact: true })).toBeVisible();
  await openListControls(page);
  await page.getByLabel('Search movie list').fill('not in this list');
  await expect(panel(page)).toContainText('No movies match this list view.');
  await panel(page).getByRole('button', { name: 'Clear filters' }).click();
  await expect(page.getByLabel('Search movie list')).toHaveValue('');
  await expect(page.getByRole('button', { name: 'Choose movies list: My custom list' })).toBeVisible();
  await expect(page.getByRole('heading', { name: movie.title, exact: true })).toBeVisible();
  await page.getByLabel('Movie list status').selectOption('owned');
  await expect(panel(page)).toContainText('No movies match this list view.');
  await panel(page).getByRole('button', { name: 'Clear filters' }).click();
  await expect(page.getByRole('heading', { name: movie.title, exact: true })).toBeVisible();
});

test('Empty custom Movie list opens its existing add dialog without saving membership', async ({ page }) => {
  await common(page, { lists: [{ id: 'custom', name: 'My custom list', movies: [] }] });
  const mutations = [];
  page.on('request', (request) => { if (request.method() !== 'GET' && /\/api\/user\/lists/.test(request.url())) mutations.push(request.url()); });
  await page.goto('/movie-lists');
  await expect(panel(page)).toContainText('This list is empty.');
  await panel(page).getByRole('button', { name: 'Add movie' }).click();
  await expect(page.getByRole('dialog', { name: 'Add movie to My custom list' })).toBeVisible();
  expect(mutations).toEqual([]);
});

test('Library distinguishes a genuinely empty source and routes Settings through App navigation', async ({ page }) => {
  await library(page);
  await page.goto('/library');
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await expect(panel(page)).toContainText('No movies in your library yet.');
  await evidence(page, 'library-empty');
  await panel(page).getByRole('button', { name: 'Open Settings' }).click();
  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
});

test('Unaccepted files get Movie View guidance and the existing File View recovery', async ({ page }) => {
  await library(page, { total: 1, files: [{ ...file, metadata_accepted: false, canonical_metadata: null }] });
  await page.goto('/library');
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await expect(panel(page)).toContainText("Your files aren't ready for Movie View.");
  await panel(page).getByRole('button', { name: 'Open File View' }).click();
  await expect(page.getByRole('region', { name: 'Library Movie Files', exact: true })).toBeVisible();
  await expect(page.locator('.library-file-row')).toContainText(file.filename);
});

test('Library filter recovery uses the existing full reset and restores cards', async ({ page }) => {
  await library(page, { total: 1, matched: 1, items: [file] });
  await page.goto('/library');
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await expect(page.getByRole('heading', { name: movie.title, exact: true })).toBeVisible();
  await page.getByLabel('Search your offline library').fill('nothing matches');
  await expect(panel(page)).toContainText('No movies match this view.');
  await panel(page).getByRole('button', { name: 'Clear filters' }).click();
  await expect(page.getByRole('heading', { name: movie.title, exact: true })).toBeVisible();
});

test('Accepted but unavailable movies are not labelled as an empty archive or unaccepted metadata', async ({ page }) => {
  await library(page, { total: 1, matched: 1, files: [file] });
  await page.goto('/library');
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await expect(panel(page)).toContainText('No movies available in this view.');
  await expect(panel(page)).not.toContainText('No movies in your library yet.');
});

test('File View distinguishes an empty inventory from a filtered inventory', async ({ page }) => {
  await library(page, { total: 1, matched: 1, files: [file] });
  await page.goto('/library');
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await expect(panel(page)).toContainText('No movies available in this view.');
  await page.getByRole('button', { name: 'File View', exact: true }).click();
  await expect(page.locator('.library-file-row')).toBeVisible();
  await openListControls(page);
  await page.getByLabel('Search your offline library').fill('nothing matches');
  await expect(panel(page)).toContainText('No files match this view.');
  await panel(page).getByRole('button', { name: 'Clear filters' }).click();
  await expect(page.locator('.library-file-row')).toBeVisible();
  await page.unroute('**/api/library?view=files');
  await page.route('**/api/library?view=files', (route) => route.fulfill({ json: { items: [], count: 0, catalog_generation: 1 } }));
  await page.reload();
  await expect(panel(page)).toContainText('No movies available in this view.');
  await page.getByRole('button', { name: 'File View', exact: true }).click();
  await expect(panel(page)).toContainText('No movie files in your library yet.');
});

test('A failed Library read shows its error without declaring the source empty', async ({ page }) => {
  await library(page, { failure: true });
  await page.goto('/library');
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await expect(page.locator('.library-status-error')).toContainText('Fixture library unavailable');
  await expect(panel(page)).toHaveCount(0);
});

test('TV Lists separates empty membership, filtered results, pending requests and failed reads', async ({ page }) => {
  await common(page);
  let release;
  let fail = false;
  const gate = new Promise((resolve) => { release = resolve; });
  await page.route('**/api/tv/lists?**', async (route) => {
    const { searchParams } = new URL(route.request().url());
    if (searchParams.get('query') === 'slow') await gate;
    if (fail) return route.fulfill({ status: 503, json: { error: 'Fixture TV unavailable' } });
    const listId = searchParams.get('list_id');
    const items = listId === 'custom' && !searchParams.get('query') ? [show] : [];
    return route.fulfill({ json: { lists: [{ id: 'watchlist', name: 'Watchlist', count: 0, system: true }, { id: 'custom', name: 'TV custom list', count: 1, system: false }, { id: 'watched', name: 'Watched', count: 0, system: true }], items, total: items.length, page: 1, page_size: 40, total_pages: 1, selected: listId } });
  });
  await page.goto('/movie-lists');
  await page.getByRole('tab', { name: 'TV Shows' }).click();
  await expect(panel(page)).toContainText('Your TV Watchlist is empty.');
  await openListControls(page);
  await page.getByLabel('Search TV list').fill('slow');
  await expect(page.getByRole('status').filter({ hasText: 'Updating TV lists' })).toBeVisible();
  await expect(panel(page)).toHaveCount(0);
  release();
  await expect(panel(page)).toContainText('Your TV Watchlist is empty.');
  await chooseList(page, 'TV custom list');
  await expect(panel(page)).toContainText('No shows match this list view.');
  await panel(page).getByRole('button', { name: 'Clear filters' }).click();
  await expect(page.getByLabel('Search TV list')).toHaveValue('');
  await expect(page.getByRole('button', { name: 'Choose shows list: TV custom list' })).toBeVisible();
  await expect(page.getByRole('heading', { name: show.title, exact: true })).toBeVisible();
  fail = true;
  await page.getByLabel('Search TV list').fill('fail');
  await expect(page.getByRole('alert')).toContainText('Fixture TV unavailable');
  await expect(panel(page)).toHaveCount(0);
  await expect(page.getByRole('heading', { name: show.title, exact: true })).toBeVisible();
});

test('TV Lists explains empty Watched and custom membership without offering filter recovery', async ({ page }) => {
  await common(page);
  await page.route('**/api/tv/lists?**', (route) => route.fulfill({ json: { lists: [
    { id: 'watchlist', name: 'Watchlist', count: 0, system: true },
    { id: 'watched', name: 'Watched', count: 0, system: true },
    { id: 'custom', name: 'Empty TV list', count: 0, system: false }
  ], items: [], total: 0, page: 1, page_size: 40, total_pages: 1 } }));
  await page.goto('/movie-lists');
  await page.getByRole('tab', { name: 'TV Shows' }).click();
  await expect(panel(page)).toContainText('Your TV Watchlist is empty.');
  await chooseList(page, 'Watched');
  await expect(panel(page)).toContainText('No completely watched shows yet.');
  await chooseList(page, 'Empty TV list');
  await openListControls(page);
  await page.getByLabel('Search TV list').fill('nothing');
  await expect(panel(page)).toContainText('This TV list is empty.');
  await expect(panel(page).getByRole('button', { name: 'Clear filters' })).toHaveCount(0);
});

test('TV Lists recovers an out-of-range page without clearing list membership or changing page size', async ({ page }) => {
  await common(page);
  const requests = [];
  await page.route('**/api/tv/lists?**', (route) => {
    const params = Object.fromEntries(new URL(route.request().url()).searchParams);
    requests.push(params);
    const pageNumber = Number(params.page);
    return route.fulfill({ json: { lists: [{ id: 'watchlist', name: 'Watchlist', count: 41, system: true }], items: pageNumber === 1 ? [show] : [], total: pageNumber === 1 ? 41 : 1, page: pageNumber, page_size: 40, total_pages: pageNumber === 1 ? 2 : 1 } });
  });
  await page.goto('/movie-lists');
  await page.getByRole('tab', { name: 'TV Shows' }).click();
  await expect(page.getByRole('heading', { name: show.title, exact: true })).toBeVisible();
  await page.getByRole('navigation', { name: 'TV Lists pages' }).getByRole('button', { name: 'Next' }).click();
  await expect(panel(page)).toContainText('No results on this page.');
  await panel(page).getByRole('button', { name: 'Go to page 1' }).click();
  await expect(page.getByRole('heading', { name: show.title, exact: true })).toBeVisible();
  expect(requests.map(({ page: resultPage, page_size, list_id }) => [resultPage, page_size, list_id])).toEqual([
    ['1', '40', 'watchlist'], ['2', '40', 'watchlist'], ['1', '40', 'watchlist']
  ]);
});

test('Discover disclosure retains criteria, shows summaries, and does not fetch merely by opening or closing', async ({ page }) => {
  const requests = [];
  await discover(page, requests);
  const toggle = page.getByRole('button', { name: 'Search, filters & selection', exact: true });
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByLabel('Production country')).toBeHidden();
  const before = requests.length;
  await toggle.click();
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await expect(toggle).toBeFocused();
  expect(requests.length).toBe(before);
  await toggle.click();
  await page.getByLabel('Production country').selectOption('EG');
  await page.getByLabel('Minimum rating', { exact: true }).selectOption('7');
  await expect(page.locator('.workspace-controls-summary:visible')).toContainText('Country: Egypt · Rating: 7+');
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Search, filters & selection', exact: true })).toHaveAttribute('aria-expanded', 'false');
  await expect(page.locator('.workspace-controls-summary:visible')).toBeVisible();
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await expect(page.getByLabel('Production country')).toHaveValue('EG');
  await expect(page.getByLabel('Minimum rating', { exact: true })).toHaveValue('7');
  await evidence(page, 'discover-filters-open');
});

test('Invalid and incomplete Discover years remain visible and block Refresh when filters close', async ({ page }) => {
  const requests = [];
  await discover(page, requests);
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await page.getByLabel('Year from', { exact: true }).fill('1800');
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Year must be between 1888 and 2100');
  await expect(page.getByRole('button', { name: 'Refresh Discover results', includeHidden: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await expect(page.getByLabel('Year from', { exact: true })).toHaveAttribute('aria-invalid', 'true');
  await page.getByLabel('Year from', { exact: true }).fill('20');
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await expect(page.getByText('Complete the year range to refresh results.')).toBeVisible();
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await page.getByRole('button', { name: 'Reset Discover filters' }).click();
  await expect(page.getByText('Complete the year range to refresh results.')).toHaveCount(0);
});

test('Discover bulk actions appear after selection and disappear on Clear', async ({ page }) => {
  await discover(page);
  const bar = page.locator('.discover-bulk-selection');
  await expect(bar.getByRole('button', { name: 'Add to list' })).toHaveCount(0);
  await expect(bar).toBeHidden();
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await expect(bar.getByRole('button', { name: 'Select all results' })).toBeVisible();
  await page.getByLabel(`Select ${movie.title}`, { exact: true }).check({ force: true });
  await expect(bar).toContainText('1 selected');
  await expect(bar.getByRole('button', { name: 'Add to list' })).toBeEnabled();
  await expect(bar.getByRole('button', { name: 'Find sources' })).toBeEnabled();
  await bar.getByRole('button', { name: 'Clear', exact: true }).click();
  await expect(bar.getByRole('button', { name: 'Find sources' })).toHaveCount(0);
  await expect(page.getByLabel(`Select ${movie.title}`, { exact: true })).not.toBeChecked();
});

for (const [width, height, maximumY] of [[1280, 900, 480], [1600, 1000, 420], [1920, 1080, 420]]) {
  test(`Discover desktop ${width} brings cards higher without changing card width or page completeness`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await discover(page);
    const grid = page.locator('.discover-panel .discover-grid');
    const before = await grid.evaluate((element) => ({ width: element.getBoundingClientRect().width, columns: getComputedStyle(element).gridTemplateColumns, y: element.getBoundingClientRect().top }));
    expect(before.y).toBeLessThanOrEqual(maximumY);
    await expect(page.locator('.discover-header')).toHaveCount(0);
    expect(await page.locator('.workspace-controls-strip').evaluate(el => el.getBoundingClientRect().height)).toBeLessThanOrEqual(60);
    await evidence(page, `discover-${width}`);
    await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
    const after = await grid.evaluate((element) => ({ width: element.getBoundingClientRect().width, columns: getComputedStyle(element).gridTemplateColumns }));
    expect(after).toEqual({ width: before.width, columns: before.columns });
    await expect(grid.locator(':scope > article')).toHaveCount(width === 1920 ? 39 : 40);
    expect(await page.locator('.discover-workspace').evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
    expect(errors).toEqual([]);
    await expect(page.locator('vite-error-overlay')).toHaveCount(0);
  });
}

const controlsToggle = page => page.getByRole('button', { name: 'Search, filters & selection', exact: true });
const externalShow = { tmdb_id: 9001, title: 'External Selection Show', genres: ['Drama'], first_air_date: '2026-01-01', status: 'Ended', season_count: 1 };
const localShow = { ...externalShow, id: 701, tmdb_id: 9002, title: 'Catalog Selection Show' };

for (const surface of ['discover-movie', 'library-movie', 'discover-tv', 'library-tv', 'library-file', 'library-tv-file']) {
  test(`${surface} keeps clear search in its field and reset filters after all selectors`, async ({ page }) => {
    await page.setViewportSize({ width: 1600, height: 900 });
    const tv = surface.includes('tv');
    const files = surface.endsWith('file');
    const scope = surface.startsWith('discover') ? 'discover' : 'library';
    await page.route('**/api/tv/catalog/options?**', route => route.fulfill({ json: {} }));
    await page.route('**/api/tv/catalog/search', route => route.fulfill({ json: { items: [show], total: 1, page: 1, total_pages: 1 } }));
    await page.route('**/api/tv/files?**', route => route.fulfill({ json: { items: [], total: 0, page: 1, total_pages: 1 } }));
    if (scope === 'discover') await discover(page);
    else {
      await library(page, { total: 1, matched: 1, items: [file] });
      await page.goto('/library');
    }
    if (tv) await page.getByRole('tablist', { name: scope === 'discover' ? 'Discover tools' : 'Library media' })
      .getByRole('button', { name: scope === 'discover' ? 'TV Shows' : 'TV Shows', exact: true }).click();
    if (files) await page.getByRole('button', { name: 'File View', exact: true }).click();
    await controlsToggle(page).click();
    const field = page.locator('.workspace-search-form:visible .library-search');
    const search = field.locator('input');
    let rating;
    if (!files) {
      rating = page.locator('.workspace-filter-grid:visible select').filter({ has: page.locator('option[value="7"]') }).last();
      await rating.selectOption('7');
    }
    await search.fill('Batman');
    if (scope === 'discover' || tv) await page.locator('.workspace-search-form:visible button[type="submit"]').click();
    const clear = field.getByRole('button', { name: /Clear .*search/ });
    await expect(clear).toBeVisible();
    expect(await clear.evaluate(button => button.parentElement.lastElementChild === button)).toBe(true);
    const inputBox = await search.boundingBox();
    const clearBox = await clear.boundingBox();
    expect(clearBox.x).toBeGreaterThanOrEqual(inputBox.x + inputBox.width);
    if (!files) {
      const filters = page.locator('.workspace-filter-grid:visible');
      const reset = filters.getByRole('button', { name: /Reset.*filters/ });
      await expect(reset).toBeEnabled();
      expect(await reset.evaluate(button => [...button.parentElement.querySelectorAll('select, input')]
        .every(control => Boolean(control.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING)))).toBe(true);
      if (scope === 'discover') expect(await filters.locator('button').last().getAttribute('aria-label')).toMatch(/Refresh/);
    }
    await clear.click();
    await expect(search).toHaveValue('');
    await expect(search).toBeFocused();
    await expect(clear).toHaveCount(0);
    if (rating) await expect(rating).toHaveValue('7');
    if (surface === 'discover-movie') await evidence(page, 'search-clear-and-filter-reset');
  });
}

async function searchSurface(page, scope, media) {
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.route('**/api/tv/catalog/options?**', route => route.fulfill({ json: {} }));
  await page.route('**/api/tv/catalog/search', route => route.fulfill({ json: { items: [show], total: 1, page: 1, total_pages: 1 } }));
  await page.route('**/api/tv/catalog/identities?**', route => route.fulfill({ json: { items: [{ id: '81', label: 'Search Fixture' }] } }));
  await page.route('**/api/library/search/identities?**', route => route.fulfill({ json: { items: [{ id: '81', label: 'Search Fixture' }] } }));
  await page.route('**/api/tmdb/people/search?**', route => route.fulfill({ json: { results: [{ id: 81, name: 'Search Fixture', known_for: [] }], total_results: 1, total_pages: 1 } }));
  await page.route('**/api/tmdb/keywords/search?**', route => route.fulfill({ json: { results: [{ id: 81, name: 'Search Fixture' }], total_results: 1, total_pages: 1 } }));
  await page.route('**/api/library?view=people', route => route.fulfill({ json: { items: [], catalog_generation: 1 } }));
  await page.route('**/api/library?view=keywords&**', route => route.fulfill({ json: { items: [], total_results: 0, total_pages: 1, catalog_generation: 1 } }));
  if (scope === 'discover') await discover(page);
  else {
    await library(page, { total: 1, matched: 1, items: [file] });
    await page.goto('/library');
  }
  if (media === 'tv') await page.getByRole('tablist', { name: scope === 'discover' ? 'Discover tools' : 'Library media' })
    .getByRole('button', { name: scope === 'discover' ? 'TV Shows' : 'TV Shows', exact: true }).click();
  await controlsToggle(page).click();
  return page.getByLabel(media === 'tv' ? 'TV search type' : scope === 'discover' ? 'TMDB search type' : 'Library search type');
}

for (const scope of ['discover', 'library']) {
  for (const media of ['movie', 'tv']) {
    ;
  }
}

;

for (const scope of ['discover', 'library']) {
  for (const media of ['movie', 'tv']) {
    for (const kind of ['People', 'Keywords']) {
      test(`${scope} ${media} clear identity search retains ${kind} mode and returns focus`, async ({ page }) => {
        const searchType = await searchSurface(page, scope, media);
        await searchType.selectOption({ label: kind });
        const field = page.locator('.workspace-search-form:visible .library-search');
        const input = field.locator('input');
        await input.fill('Search Fixture');
        const clear = field.getByRole('button', { name: /Clear .*search|Clear search/ });
        await expect(clear).toBeVisible();
        if (media === 'movie' && scope === 'discover') {
          await page.locator('.workspace-search-form:visible button[type="submit"]').click();
          await expect(page.getByRole('heading', { name: 'Search Fixture', exact: true })).toBeVisible();
        } else if (media === 'tv') {
          await expect(page.getByRole('option', { name: 'Search Fixture', exact: true })).toBeVisible();
        }
        const selectedMode = await searchType.inputValue();
        await clear.click();
        await expect(input).toHaveValue('');
        await expect(input).toBeFocused();
        await expect(clear).toHaveCount(0);
        await expect(searchType).toHaveValue(selectedMode);
        await expect(page.getByRole('heading', { name: 'Search Fixture', exact: true })).toHaveCount(0);
        await expect(page.locator('.advanced-picker-results')).toHaveCount(0);
        await input.fill('Another search');
        await expect(clear).toBeVisible();
      });
    }

    test(`${scope} ${media} clear advanced search removes criteria and stays Advanced`, async ({ page }) => {
      const searches = [];
      page.on('request', request => {
        if (request.method() === 'POST' && /\/api\/(tmdb\/discover\/advanced|library\/search\/advanced|tv\/catalog\/search)$/.test(new URL(request.url()).pathname)) {
          searches.push(request.postDataJSON());
        }
      });
      const searchType = await searchSurface(page, scope, media);
      await searchType.selectOption('advanced');
      const builder = page.locator('.advanced-search-builder:visible');
      const trigger = page.getByRole('button', { name: 'Add advanced search criterion' });
      const picker = page.getByRole('dialog', { name: 'Add search criterion' });
      async function addTitle(text) {
        await trigger.click();
        await picker.getByLabel('Criterion to add').selectOption('title');
        await picker.getByLabel('Title value').fill(text);
        await picker.getByRole('button', { name: 'Add criterion', exact: true }).click();
        await picker.getByRole('button', { name: 'Close criterion picker' }).click();
      }
      await addTitle('Search Fixture');
      await expect(builder.getByLabel('Edit title')).toHaveValue('Search Fixture');
      await trigger.click();
      await picker.getByLabel('Criterion to add').selectOption('rating');
      await picker.getByRole('button', { name: 'Add criterion', exact: true }).click();
      await picker.getByRole('button', { name: 'Close criterion picker' }).click();
      await expect(builder.locator('.advanced-criterion-cluster')).toHaveCount(2);
      await page.locator('.workspace-search-form:visible button[type="submit"]').click();
      await expect.poll(() => searches.at(-1)?.query?.groups.some(group => group.type === 'title')).toBe(true);
      await builder.getByRole('button', { name: 'Clear search', exact: true }).click();
      await expect(searchType).toHaveValue('advanced');
      await expect(builder.locator('.advanced-criterion-cluster')).toHaveCount(0);
      await expect.poll(() => searches.at(-1)?.query?.groups).toEqual([]);
      await expect(page.getByRole('button', { name: 'Reset advanced search' })).toHaveCount(0);
      // Clearing from the picker also resets an unfinished draft without leaving Advanced.
      await addTitle('Second criterion');
      await trigger.click();
      await picker.getByLabel('Criterion to add').selectOption('person');
      await picker.getByLabel('Find person').fill('Unfinished draft');
      await picker.locator('.advanced-popover-actions').getByRole('button', { name: 'Clear search', exact: true }).click();
      await expect(searchType).toHaveValue('advanced');
      await expect(picker.getByLabel('Criterion to add')).toHaveValue('');
      await expect(builder.locator('.advanced-criterion-cluster')).toHaveCount(0);
      await picker.getByRole('button', { name: 'Close criterion picker' }).click();
      await searchType.selectOption(media === 'tv' ? 'title' : 'movies');
      await searchType.selectOption('advanced');
      await expect(builder.locator('.advanced-criterion-cluster')).toHaveCount(0);
      await addTitle('Fresh criterion');
      await expect(builder.getByLabel('Edit title')).toHaveValue('Fresh criterion');
    });
  }
}

for (const scope of ['discover', 'library']) {
  for (const initiallyExpanded of [true, false]) {
    test(`${scope} movie expansion restores ${initiallyExpanded ? 'expanded' : 'collapsed'} controls and retains drafts and selection`, async ({ page }) => {
      const searches = [];
      await page.route('**/api/tmdb/details**', route => route.fulfill({ json: { ...movie, summary: 'Fixture movie details.', cast: [], directors: [] } }));
      await page.route('**/api/library/details**', route => route.fulfill({ json: { item: file, catalog_generation: 1 } }));
      page.on('request', request => {
        if (request.url().includes('/api/tmdb/discover') || request.url().includes('/api/library/search/advanced')) searches.push(request.url());
      });
      if (scope === 'discover') await discover(page);
      else {
        await library(page, { total: 1, matched: 1, items: [file] });
        await page.route('**/api/library/search/advanced', route => route.fulfill({ json: {
          items: [file], total: 1, page: 1, total_pages: 1, page_start: 0, page_end: 1,
          catalog_generation: 1, facets: { genres: [], countries: [], languages: [], sources: [] },
          stats: { total: 1, matched: 1, pending: 0, unmatched: 0, low: 0 }
        } }));
        await page.goto('/library');
      }
      const card = page.locator(scope === 'discover' ? '.discover-grid > .unified-movie-card' : '.library-movie-results > .unified-movie-card').first();
      await expect(card).toBeVisible();
      const selection = card.getByRole('checkbox');
      await controlsToggle(page).click();
      const search = page.getByLabel(scope === 'discover' ? 'Search TMDB movies' : 'Search your offline library', { exact: true });
      const librarySearch = scope === 'library' ? page.waitForResponse(response => response.url().includes('/api/library/search/advanced')
        && response.request().postDataJSON()?.query?.groups?.some(group => group.type === 'title')) : null;
      await search.fill('Layout');
      if (librarySearch) await librarySearch;
      await selection.check({ force: true });
      await expect(selection).toBeChecked();
      if (!initiallyExpanded) await controlsToggle(page).click();
      const before = searches.length;
      await card.getByRole('heading').click();
      await expect(card).toHaveClass(/unified-movie-card-expanded/);
      await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'false');
      await expect(search).toBeHidden();
      await expect(selection).toBeChecked();

      // Reopening controls during viewing is temporary, including manual closes.
      const collapsedTop = (await card.boundingBox()).y;
      await controlsToggle(page).click();
      await expect(search).toHaveValue('Layout');
      const body = page.locator('.workspace-controls-body:visible');
      expect(await body.evaluate(element => element.scrollHeight <= element.clientHeight + 1)).toBe(true);
      const chrome = page.locator('.workspace-chrome:visible');
      await expect.poll(async () => {
        const cardBox = await card.boundingBox();
        const chromeBox = await chrome.boundingBox();
        return cardBox.y >= chromeBox.y + chromeBox.height - 1 && cardBox.y > collapsedTop;
      }).toBe(true);
      if (initiallyExpanded) await controlsToggle(page).click();
      await card.locator('.unified-movie-main').getByRole('heading').click();
      await expect(card).not.toHaveClass(/unified-movie-card-expanded/);
      await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', String(initiallyExpanded));
      if (!initiallyExpanded) await controlsToggle(page).click();
      await expect(search).toHaveValue('Layout');
      await expect(selection).toBeChecked();
      expect(searches).toHaveLength(before);

      // Repeated expansion of the same movie must start collapsed again.
      await card.getByRole('heading').click();
      await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'false');
      await card.locator('.unified-movie-main').getByRole('heading').click();
      await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'true');
    });
  }
}

async function assertSticky(page, resultSelector) {
  await page.locator('main.workspace').evaluate(element => element.scrollTo({ top: 0, behavior: 'instant' }));
  await expect.poll(() => page.locator('main.workspace').evaluate(element => element.scrollTop)).toBe(0);
  const chrome = page.locator('.workspace-chrome:visible');
  await expect(chrome).toHaveCount(1);
  const firstResult = page.locator(resultSelector).first();
  const before = await firstResult.boundingBox();
  await page.locator('main.workspace').evaluate(element => element.scrollTo({ top: 650, behavior: 'instant' }));
  await expect.poll(() => page.locator('main.workspace').evaluate(element => element.scrollTop)).toBeGreaterThan(300);
  await expect.poll(async () => (await chrome.boundingBox()).y).toBeCloseTo(0, 0);
  const after = await firstResult.boundingBox();
  expect(before.y - after.y).toBeGreaterThan(300);
  await expect(controlsToggle(page)).toBeInViewport();
  expect(await chrome.evaluate(element => {
    const tabs = element.querySelector('[role="tablist"]');
    const rect = tabs.getBoundingClientRect();
    return element.contains(document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2));
  })).toBe(true);
  await expect(chrome).toHaveCSS('background-color', 'rgb(0, 0, 0)');
}

test('Library remembers separate Media and File controls states when returning to an expanded movie', async ({ page }) => {
  await library(page, { total: 1, matched: 1, items: [file] });
  await page.route('**/api/tmdb/details**', route => route.fulfill({ json: { ...movie, cast: [], directors: [] } }));
  await page.route('**/api/library/details**', route => route.fulfill({ json: { item: file, catalog_generation: 1 } }));
  await page.goto('/library');
  const card = page.locator('.library-movie-results > .unified-movie-card').first();
  await expect(card).toBeVisible();
  await controlsToggle(page).click();
  await card.getByRole('heading').click();
  await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'false');
  await page.getByRole('button', { name: 'File View', exact: true }).click();
  await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'false');
  await controlsToggle(page).click();
  await expect(page.getByLabel('Search your offline library', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Media View', exact: true }).click();
  await expect(card).toHaveClass(/unified-movie-card-expanded/);
  await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'false');
  await card.locator('.unified-movie-main').getByRole('heading').click();
  await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'true');
  await controlsToggle(page).click();
  await page.getByRole('button', { name: 'File View', exact: true }).click();
  await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'true');
  await page.getByRole('button', { name: 'Media View', exact: true }).click();
  await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'false');
});

test('Discover Movie chrome stays pinned with controls collapsed and expanded without requerying', async ({ page }) => {
  const calls = [];
  await discover(page, calls);
  const startCalls = calls.length;
  await assertSticky(page, '.discover-grid > .unified-movie-card');
  await page.locator('.workspace-controls-summary:visible').click();
  await expect(page.getByLabel('Search TMDB movies', { exact: true })).toBeVisible();
  await page.getByLabel('Search TMDB movies', { exact: true }).fill('Retained draft');
  await assertSticky(page, '.discover-grid > .unified-movie-card');
  await page.locator('.workspace-controls-summary:visible').click();
  await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'false');
  await controlsToggle(page).press('Enter');
  await expect(page.getByLabel('Search TMDB movies', { exact: true })).toHaveValue('Retained draft');
  expect(calls.length).toBe(startCalls);
  await evidence(page, 'sticky-discover-expanded');
});

test('Discover TV uses the same pinned tabs and expanded controls', async ({ page }) => {
  await discover(page);
  await page.route('**/api/tv/catalog/options?**', route => route.fulfill({ json: {} }));
  await page.route('**/api/tv/catalog/search', route => route.fulfill({ json: { items: Array.from({ length: 40 }, (_, i) => ({ ...externalShow, tmdb_id: 9001 + i, title: `Sticky Show ${i}` })), total: 40, page: 1, total_pages: 1 } }));
  const movieTabHeight = (await page.getByRole('button', { name: 'Movies', exact: true }).boundingBox()).height;
  await page.getByRole('button', { name: 'TV Shows', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sticky Show 0', exact: true })).toBeVisible();
  expect((await page.getByRole('button', { name: 'TV Shows', exact: true }).boundingBox()).height).toBe(movieTabHeight);
  await assertSticky(page, '.tv-series-grid > .unified-movie-card');
  await controlsToggle(page).click();
  await assertSticky(page, '.tv-series-grid > .unified-movie-card');
});

test('Movie Library removes titles and retains sticky view actions in media and files', async ({ page }) => {
  const rows = Array.from({ length: 50 }, (_, i) => ({ ...file, path: `E:/Movies/Sticky.${i}.mkv`, filename: `Sticky.${i}.mkv`, title: `Sticky Movie ${i}`, canonical_metadata: { ...file.canonical_metadata, title: `Sticky Movie ${i}`, tmdb_id: String(1000 + i) } }));
  await library(page, { total: 50, matched: 50, items: rows, files: rows });
  await page.goto('/library');
  await expect(page.getByRole('region', { name: 'Library Movies', exact: true })).toBeVisible();
  await expect(page.locator('.library-workspace:visible > .library-header')).toHaveCount(0);
  const mode = page.getByRole('group', { name: 'Library mode', exact: true });
  await expect(mode.getByRole('button', { name: 'Media View' })).toHaveAttribute('aria-pressed', 'true');
  await assertSticky(page, '.library-movie-results > .unified-movie-card');
  await expect(page.getByRole('button', { name: 'Rescan library files' })).toBeInViewport();
  await mode.getByRole('button', { name: 'File View' }).click();
  await expect(page.getByRole('region', { name: 'Library Movie Files', exact: true })).toBeVisible();
  await expect(mode.getByRole('button', { name: 'File View' })).toHaveAttribute('aria-pressed', 'true');
  await assertSticky(page, '.library-file-results > .library-file-row');
  await controlsToggle(page).click();
  await assertSticky(page, '.library-file-results > .library-file-row');
  await evidence(page, 'sticky-library-files');
});

test('TV Library retains sticky view, refresh and Maintenance import actions in media and files', async ({ page }) => {
  await common(page);
  await page.route('**/api/tv/catalog/options?**', route => route.fulfill({ json: {} }));
  await page.route('**/api/tv/maintenance?**', route => route.fulfill({ json: { counts: {} } }));
  await page.route('**/api/tv/catalog/search', route => route.fulfill({ json: { items: Array.from({ length: 40 }, (_, i) => ({ ...localShow, id: i + 1, tmdb_id: i + 9001, title: `Sticky Library Show ${i}` })), total: 40, page: 1, total_pages: 1 } }));
  await page.route('**/api/tv/files?**', route => route.fulfill({ json: { items: Array.from({ length: 50 }, (_, i) => ({ file_id: i + 1, filename: `Sticky.Episode.${i}.mkv`, path: `E:/TV/Sticky.Episode.${i}.mkv`, size: 100, episodes: [], facts: {}, available: false })), total: 50, page: 1, page_size: 50, total_pages: 1 } }));
  await page.goto('/library');
  await page.getByRole('button', { name: 'TV Shows', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sticky Library Show 0', exact: true })).toBeVisible();
  await expect(page.locator('.tv-library-workspace > .library-header')).toHaveCount(0);
  await assertSticky(page, '.tv-series-grid > .unified-movie-card');
  await expect(page.getByRole('button', { name: 'Refresh TV catalog' })).toBeInViewport();
  await expect(page.getByRole('button', { name: 'Review TV identity in Maintenance', exact: true })).toBeInViewport();
  const mode = page.getByRole('group', { name: 'TV library mode' });
  await mode.getByRole('button', { name: 'File View' }).click();
  await expect(page.getByText('Sticky.Episode.0.mkv', { exact: true })).toBeVisible();
  await assertSticky(page, '.tv-file-view .library-file-row');
  await expect(mode.getByRole('button', { name: 'File View' })).toHaveAttribute('aria-pressed', 'true');
  await controlsToggle(page).click();
  await expect(page.getByLabel('Search TV files')).toBeVisible();
  await assertSticky(page, '.tv-file-view .library-file-row');
  await evidence(page, 'sticky-tv-library-files');
});

test('Advanced picker stays outside pinned controls and preserves its draft through collapse', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await discover(page);
  await page.locator('.workspace-controls-summary:visible').click();
  await page.getByLabel('TMDB search type').selectOption('advanced');
  await page.getByRole('button', { name: 'Add advanced search criterion' }).click();
  await page.getByLabel('Criterion to add').selectOption('year');
  const body = page.locator('.workspace-controls-body:visible');
  expect(await body.evaluate(element => element.clientHeight <= window.innerHeight / 2)).toBe(true);
  await page.getByRole('button', { name: 'Add criterion', exact: true }).click();
  await page.getByLabel('Criterion to add').selectOption('rating');
  await page.getByRole('button', { name: 'Add criterion', exact: true }).click();
  await expect(controlsToggle(page)).toBeInViewport();
  await page.getByLabel('Criterion to add').selectOption('title');
  await page.getByLabel('Title value').fill('Unsubmitted advanced draft');
  await page.locator('.workspace-controls-summary:visible').click();
  await expect(body).toHaveCount(0);
  await controlsToggle(page).press('Space');
  await expect(page.getByRole('dialog', { name: 'Add search criterion' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Add advanced search criterion' }).click();
  await expect(page.getByLabel('Title value')).toHaveValue('Unsubmitted advanced draft');
  await expect(page.getByRole('button', { name: 'Add criterion', exact: true })).toBeInViewport();
});

for (const scope of ['discover', 'library']) {
  for (const media of ['movie', 'tv']) {
    test(`${scope} ${media} advanced picker floats above controls without adding scroll and dismisses accessibly`, async ({ page }) => {
      const pageErrors = [];
      page.on('pageerror', error => pageErrors.push(error.message));
      await page.setViewportSize({ width: 1366, height: 768 });
      if (scope === 'discover') await discover(page);
      else {
        await library(page, { total: 1, matched: 1, items: [movie] });
        await page.goto('/library');
      }
      if (media === 'tv') {
        await page.route('**/api/tv/catalog/options?**', route => route.fulfill({ json: {} }));
        await page.route('**/api/tv/catalog/search', route => route.fulfill({ json: { items: [show], total: 1, page: 1, total_pages: 1 } }));
        await page.getByRole('tablist', { name: scope === 'discover' ? 'Discover tools' : 'Library media' })
          .getByRole('button', { name: scope === 'discover' ? 'TV Shows' : 'TV Shows', exact: true }).click();
      }
      await controlsToggle(page).click();
      const searchType = page.getByLabel(media === 'tv' ? 'TV search type' : scope === 'discover' ? 'TMDB search type' : 'Library search type');
      await searchType.click();
      await searchType.getByRole('option', { name: 'Advanced', exact: true }).click();
      const body = page.locator('.workspace-controls-body:visible');
      const before = await body.evaluate(element => ({ height: element.clientHeight, scroll: element.scrollHeight }));
      const trigger = page.getByRole('button', { name: 'Add advanced search criterion' });
      const picker = page.getByRole('dialog', { name: 'Add search criterion' });
      await trigger.press('Enter');
      await expect(picker).toBeVisible();
      await expect(page.getByLabel('Criterion to add')).toBeFocused();
      expect(await body.evaluate(element => ({ height: element.clientHeight, scroll: element.scrollHeight }))).toEqual(before);
      expect(await picker.evaluate(element => element.parentElement === document.body)).toBe(true);
      const bounds = await picker.boundingBox();
      expect(bounds.x).toBeGreaterThanOrEqual(12);
      expect(bounds.x + bounds.width).toBeLessThanOrEqual(1366 - 12);
      expect(bounds.y + bounds.height).toBeLessThanOrEqual(768 - 12);
      expect(await picker.evaluate(element => {
        const rect = element.getBoundingClientRect();
        return element.contains(document.elementFromPoint(rect.right - 20, rect.bottom - 10));
      })).toBe(true);
      await page.getByLabel('Criterion to add').selectOption('title');
      await page.getByLabel('Title value').fill('Retained criterion draft');
      await page.getByLabel('Title value').press('Escape');
      await expect(picker).toHaveCount(0);
      await expect(trigger).toBeFocused();
      await trigger.click();
      await expect(page.getByLabel('Title value')).toHaveValue('Retained criterion draft');
      await controlsToggle(page).focus();
      await controlsToggle(page).press('Space');
      await expect(picker).toHaveCount(0);
      await controlsToggle(page).press('Space');
      await trigger.click();
      await expect(page.getByLabel('Title value')).toHaveValue('Retained criterion draft');
      await page.locator('.workspace-controls-summary:visible').click();
      await expect(picker).toHaveCount(0);
      expect(pageErrors).toEqual([]);
    });
  }
}

async function tvSelectionFixture(page, mutations) {
  await common(page);
  await page.route('**/api/tv/catalog/options?**', route => route.fulfill({ json: {} }));
  await page.route('**/api/tv/catalog/search', route => {
    const currentPage = route.request().postDataJSON().page;
    return route.fulfill({ json: { items: currentPage === 1 ? [externalShow, localShow] : [{ ...externalShow, title: 'External Selection Show' }], total: 3, total_pages: 2, page: currentPage, page_size: 2 } });
  });
  await page.route('**/api/tv/lists?**', route => route.fulfill({ json: { lists: [{ id: 81, name: 'Fixture custom list', system: false }], items: [], total: 0 } }));
  await page.route('**/api/tv/series', route => { mutations.push(['catalog', route.request().postDataJSON()]); return route.fulfill({ json: { id: 801 } }); });
  await page.route('**/api/tv/series/*/watchlist', route => { mutations.push(['watchlist', route.request().postDataJSON()]); return route.fulfill({ json: { watchlisted: true } }); });
  await page.route('**/api/tv/bulk/download/preview', route => { mutations.push(['preview', route.request().postDataJSON()]); return route.fulfill({ json: { items: [{ series_id: 701, metadata_complete: true, counts: { released_missing: 2, owned: 0, review: 0, queued: 0 } }] } }); });
  await page.goto('/discover');
  await page.getByRole('tablist', { name: 'Discover tools' }).getByRole('button', { name: 'TV Shows' }).click();
  await expect(page.getByRole('heading', { name: externalShow.title, exact: true })).toBeVisible();
}

test('Every Discover tool uses one default-collapsed panel and removes the title bar', async ({ page }) => {
  await discover(page);
  await page.route('**/api/tv/catalog/options?**', route => route.fulfill({ json: {} }));
  await page.route('**/api/tv/catalog/search', route => route.fulfill({ json: { items: [externalShow], total: 1, page: 1, total_pages: 1 } }));
  for (const tab of ['Movies', 'TV Shows', 'Browse Indexers', 'Pick My Movie']) {
    await page.getByRole('tablist', { name: 'Discover tools' }).getByRole('button', { name: tab }).click();
    await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'false');
    await expect(page.locator('.workspace-controls:visible')).toHaveCount(1);
    await expect(page.locator('.discover-header')).toHaveCount(0);
    await expect(page.locator('.workspace-controls-body:visible')).toHaveCount(0);
    await controlsToggle(page).click();
    await expect(page.locator('.workspace-search-form:visible')).toHaveCount(1);
    await expect(page.getByRole('button', { name: /More filters|Open filters|Hide filters/ })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Close controls', exact: true })).toHaveCount(0);
    if (tab === 'Movies' || tab === 'TV Shows') {
      const refreshLabel = tab === 'Movies' ? 'Refresh Discover results' : 'Refresh TV results';
      expect(await page.getByRole('button', { name: refreshLabel, exact: true }).evaluate(button => button === button.parentElement.lastElementChild)).toBe(true);
    }
    await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
    await expect(controlsToggle(page)).toBeFocused();
  }
  const tabs = page.getByRole('tablist', { name: 'Discover tools' });
  await tabs.getByRole('button', { name: 'Movies' }).click();
  await controlsToggle(page).click();
  await tabs.getByRole('button', { name: 'Pick My Movie' }).click();
  await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'false');
  await tabs.getByRole('button', { name: 'Movies' }).click();
  await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'true');
});

test('TV bulk review dismisses when its retained workspace is hidden and selection survives', async ({ page }) => {
  const mutations = [];
  await tvSelectionFixture(page, mutations);
  await page.locator('.sidebar').getByRole('button', { name: 'Home', exact: true }).click();
  await page.locator('.sidebar').getByRole('button', { name: 'Discover', exact: true }).click();
  await page.getByLabel(`Select ${localShow.title}`, { exact: true }).check({ force: true });
  await controlsToggle(page).click();
  const region = page.locator('.tv-bulk-actions:visible');
  await expect(region.getByRole('button', { name: 'Select all loaded TV shows', exact: true })).toBeVisible();
  await region.getByRole('button', { name: 'Download released episodes', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Review TV bulk download', exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('dialog', { name: 'Review TV bulk download', exact: true })).toHaveCount(0);
  await page.goForward();
  await expect(page.getByLabel(`Select ${localShow.title}`, { exact: true })).toBeChecked();
  expect(mutations.filter(([kind]) => kind === 'confirm')).toEqual([]);
});

test('TV cards retain the backend explanation when no episode target is available', async ({ page }) => {
  const mutations = [];
  await tvSelectionFixture(page, mutations);
  await page.route('**/api/tv/catalog/search', route => route.fulfill({ json: {
    items: [{ ...localShow, primary_action: { playable: false, target: null, reason: 'Next episode is unknown until metadata is complete' } }],
    total: 1, page: 1, total_pages: 1
  } }));
  await page.reload();
  await page.getByRole('tablist', { name: 'Discover tools' }).getByRole('button', { name: 'TV Shows' }).click();
  await expect(page.locator('.tv-series-card')).toHaveCount(1);
  await expect(page.locator('.tv-series-card')).toContainText('Next episode is unknown until metadata is complete');
});

test('Mixed TV download confirmation uses the reviewed local subset and retains external selection', async ({ page }) => {
  const mutations = [];
  await tvSelectionFixture(page, mutations);
  await page.route('**/api/tv/bulk/download', route => { mutations.push(['confirm', route.request().postDataJSON()]); return route.fulfill({ json: { tasks: [{}] } }); });
  await page.getByLabel(`Select ${externalShow.title}`, { exact: true }).check({ force: true });
  await page.getByLabel(`Select ${localShow.title}`, { exact: true }).check({ force: true });
  await controlsToggle(page).click();
  await page.getByRole('button', { name: 'Download released episodes', exact: true }).click();
  await page.getByRole('button', { name: 'Start one-shot downloads', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Review TV bulk download' })).toHaveCount(0);
  await expect(page.getByLabel(`Select ${externalShow.title}`, { exact: true })).toBeChecked();
  await expect(page.getByLabel(`Select ${localShow.title}`, { exact: true })).not.toBeChecked();
  expect(mutations).toEqual([['preview', { series_ids: [701] }], ['confirm', { series_ids: [701] }]]);
});

test('External TV selection stays read-only, deduplicates across pages and preserves draft through collapse', async ({ page }) => {
  const mutations = [];
  await tvSelectionFixture(page, mutations);
  await page.getByLabel(`Select ${externalShow.title}`, { exact: true }).check({ force: true });
  await expect(page.locator('.workspace-controls-summary:visible')).toContainText('Selected: 1');
  expect(mutations).toEqual([]);
  await controlsToggle(page).click();
  await page.getByLabel('Search TV shows', { exact: true }).fill('Unsubmitted draft');
  await expect(page.getByRole('button', { name: 'Download released episodes', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await page.getByRole('navigation', { name: 'TV page controls above results' }).getByRole('button', { name: 'Next' }).click();
  await expect(page.getByLabel(`Select ${externalShow.title}`, { exact: true })).toBeChecked();
  await controlsToggle(page).click();
  await expect(page.getByLabel('Search TV shows', { exact: true })).toHaveValue('Unsubmitted draft');
  await page.getByRole('button', { name: 'Select all loaded TV shows', exact: true }).click();
  await expect(page.locator('.workspace-controls-summary:visible')).toContainText('Selected: 1');
  expect(mutations).toEqual([]);
  await evidence(page, 'tv-selection-expanded');
});

test('TV membership resolves external metadata only on action and reuses resolved IDs after failure', async ({ page }) => {
  const mutations = [];
  await tvSelectionFixture(page, mutations);
  let attempts = 0;
  await page.route('**/api/tv/lists/81/series', route => { mutations.push(['list', route.request().postDataJSON()]); attempts += 1; return route.fulfill({ status: attempts === 1 ? 503 : 200, json: attempts === 1 ? { error: 'Fixture membership failure' } : {} }); });
  await page.getByLabel(`Select ${externalShow.title}`, { exact: true }).check({ force: true });
  await controlsToggle(page).click();
  await page.getByLabel('Add selected TV shows to list').selectOption('81');
  await page.getByRole('button', { name: 'Add to a list', exact: true }).click();
  await expect(page.locator('.tv-membership-error:visible')).toContainText('Fixture membership failure');
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await expect(page.locator('.tv-membership-error:visible')).toContainText('Fixture membership failure');
  await controlsToggle(page).click();
  await expect(page.locator('.workspace-controls-summary:visible')).toContainText('Selected: 1');
  await page.getByRole('button', { name: 'Add to a list', exact: true }).click();
  await expect(page.getByLabel(`Select ${externalShow.title}`, { exact: true })).not.toBeChecked();
  expect(mutations).toEqual([['catalog', { tmdb_id: 9001 }], ['list', { series_ids: [801] }], ['list', { series_ids: [801] }]]);
});

test('TV Watchlist supports external rows; mixed download preview uses only cataloged IDs and remains visible when collapsed', async ({ page }) => {
  const mutations = [];
  await tvSelectionFixture(page, mutations);
  await page.getByLabel(`Select ${externalShow.title}`, { exact: true }).check({ force: true });
  await page.getByLabel(`Select ${localShow.title}`, { exact: true }).check({ force: true });
  await controlsToggle(page).click();
  await page.getByRole('button', { name: 'Download released episodes', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Review TV bulk download' })).toBeVisible();
  expect(mutations).toEqual([['preview', { series_ids: [701] }]]);
  await controlsToggle(page).press('Enter');
  await expect(controlsToggle(page)).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('dialog', { name: 'Review TV bulk download' })).toBeVisible();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await controlsToggle(page).click();
  await page.getByRole('button', { name: 'Add to Watchlist', exact: true }).click();
  await expect(page.getByLabel(`Select ${externalShow.title}`, { exact: true })).not.toBeChecked();
  expect(mutations).toEqual([['preview', { series_ids: [701] }], ['catalog', { tmdb_id: 9001 }], ['watchlist', { watchlisted: true }], ['watchlist', { watchlisted: true }]]);
});

for (const tab of ['Movies', 'Browse Indexers', 'Pick My Movie']) {
  test(`${tab} sends its selected identity through the shared Find sources review`, async ({ page }) => {
    await discover(page);
    const previews = [], submissions = [];
    await page.route('**/api/explore/indexers', route => route.fulfill({ json: { indexers: [] } }));
    await page.route('**/api/explore/browse?**', route => route.fulfill({ json: { results: [{ ...movie, parsed_title: movie.title, parsed_year: movie.year, metadata: movie, variants: [{ resolution: '1080p', seeders: 10, indexer: 'Fixture' }] }] } }));
    await page.route('**/api/metadata?**', route => route.fulfill({ json: movie }));
    await page.route('**/api/ollama/recommend', route => route.fulfill({ json: { results: [movie], model: 'fixture' } }));
    await page.route('**/api/sources/review/preview', route => { previews.push(route.request().postDataJSON()); return route.fulfill({ json: { rows: [], blocked: [], defaults: {} } }); });
    await page.route('**/api/sources/review/submit', route => { submissions.push(route.request().postDataJSON()); return route.fulfill({ json: {} }); });
    await page.getByRole('tablist', { name: 'Discover tools' }).getByRole('button', { name: tab }).click();
    await controlsToggle(page).click();
    if (tab === 'Browse Indexers') await page.getByRole('button', { name: 'Load latest', exact: true }).click();
    if (tab === 'Pick My Movie') {
      await page.getByLabel('Describe what you want to watch').fill('Fixture mood');
      await page.getByRole('button', { name: 'Ask AI', exact: true }).click();
    }
    await expect(page.getByRole('heading', { name: movie.title, exact: true })).toBeVisible();
    await page.getByLabel(`Select ${movie.title}`, { exact: true }).check({ force: true });
    await page.locator('.discover-bulk-selection:visible').getByRole('button', { name: 'Find sources', exact: true }).click();
    await expect(page.getByRole('dialog', { name: 'Find sources', exact: true })).toBeVisible();
    expect(previews).toHaveLength(1);
    expect(previews[0].movies).toHaveLength(1);
    expect(previews[0].movies[0]).toMatchObject({ tmdb_id: movie.tmdb_id, title: movie.title, year: movie.year });
    expect(submissions).toEqual([]);
  });
}
