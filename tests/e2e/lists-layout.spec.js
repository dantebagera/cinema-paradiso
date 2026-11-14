import { expect, test } from '@playwright/test';

const movies = Array.from({ length: 12 }, (_, index) => ({ tmdb_id: String(8500 + index), title: `Saved movie ${index + 1}`, year: '2025', poster_url: '' }));
const initialLists = [
  { id: 'watched', name: 'Watched', system_type: 'watched', movies: [] },
  { id: 'watchlist', name: 'Watchlist', system_type: 'watchlist', movies: movies.slice(0, 3) },
  { id: 'custom', name: 'Animated favourites', movies },
];
const controls = page => page.getByRole('button', { name: 'Search, filters & selection', exact: true });

test('Popularity uses cached scores for owned and unowned titles while retaining canonical owned display', async ({ page }) => {
  await fixture(page);
  const ownedMovie = movies[0];
  const cached = Object.fromEntries(movies.map((movie, index) => [`tmdb:${movie.tmdb_id}`, { ...movie, popularity: index === 0 ? 500 : 100 - index }]));
  await page.route('**/api/library/check', route => route.fulfill({ json: { results: [{ found: true, tmdb_id: ownedMovie.tmdb_id, library_item: {
    path: 'C:/fixture/owned.mkv', metadata_accepted: true, title: 'Canonical owned title', canonical_metadata: { ...ownedMovie, title: 'Canonical owned title', accepted: true }
  } }], catalog_generation: 1 } }));
  await page.route('**/api/tmdb/card-projections', route => route.fulfill({ json: { items: cached, catalog_generation: 1 } }));
  const ownedProviderCalls = [];
  await page.route('**/api/tmdb/details**', route => {
    const id = new URL(route.request().url()).searchParams.get('tmdb_id');
    if (id === ownedMovie.tmdb_id) ownedProviderCalls.push(id);
    return route.fulfill({ json: cached[`tmdb:${id}`] });
  });
  await page.goto('/movie-lists');
  await choose(page, 'Animated favourites');
  await controls(page).click();
  await page.getByLabel('Sort results', { exact: true }).selectOption('popularity.desc');
  await expect(page.locator('.movie-lists-card-grid article').first()).toContainText('Canonical owned title');
  await expect(page.locator('.movie-lists-card-grid article')).toHaveCount(12);
  expect(ownedProviderCalls).toEqual([]);
});

test('Partial cached projections hydrate the fields needed for active list filters', async ({ page }) => {
  await fixture(page);
  const requests = [];
  await page.route('**/api/tmdb/card-projections', route => route.fulfill({ json: {
    items: Object.fromEntries(movies.map(movie => [`tmdb:${movie.tmdb_id}`, { tmdb_id: movie.tmdb_id, title: movie.title, plot: 'Cached card summary only' }])), catalog_generation: 1
  } }));
  await page.route('**/api/tmdb/details**', route => {
    const id = new URL(route.request().url()).searchParams.get('tmdb_id');
    requests.push(id);
    return route.fulfill({ json: { ...movies.find(movie => movie.tmdb_id === id), genres: ['Animation'], country_flag: 'US', tmdb_rating: 9, tmdb_vote_count: 5000 } });
  });
  await page.goto('/movie-lists');
  await choose(page, 'Animated favourites');
  await expect(page.locator('.movie-lists-card-grid article')).toHaveCount(12);
  await controls(page).click();
  await page.getByLabel('Genre', { exact: true }).selectOption('16');
  await expect(page.locator('.movie-lists-card-grid article')).toHaveCount(12);
  await expect.poll(() => new Set(requests).size).toBe(12);
  await page.getByLabel('Minimum votes', { exact: true }).selectOption('1000');
  await page.getByLabel('Production country', { exact: true }).selectOption('US');
  await expect(page.locator('.movie-lists-card-grid article')).toHaveCount(12);
  await expect(page.getByText('No movies match this list view.', { exact: true })).toHaveCount(0);
});

test('Add movie search renders results and submits the chosen identity without a display crash', async ({ page }) => {
  await fixture(page);
  const errors = [];
  const additions = [];
  page.on('pageerror', error => errors.push(error.message));
  const candidate = { tmdb_id: '9901', title: 'New fixture movie', year: '2026', poster_url: '' };
  await page.route('**/api/tmdb/search**', route => route.fulfill({ json: { results: [candidate] } }));
  await page.route('**/api/user/lists/custom/movies', route => {
    additions.push(route.request().postDataJSON());
    return route.fulfill({ json: { ok: true, curation_generation: 2 } });
  });
  await page.goto('/movie-lists');
  await choose(page, 'Animated favourites');
  await page.getByRole('button', { name: 'Add movie', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Add movie to Animated favourites' });
  await dialog.getByPlaceholder('Search TMDB movies...').fill(candidate.title);
  await dialog.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(dialog.getByText(candidate.title, { exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Add to list', exact: true }).click();
  await expect(dialog).toBeHidden();
  expect(errors).toEqual([]);
  expect(additions).toHaveLength(1);
  expect(additions[0].movie.tmdb_id).toBe(candidate.tmdb_id);
});

test('New list dialog dismisses on browser navigation without submitting or stealing focus', async ({ page }) => {
  const mutations = await fixture(page);
  await page.goto('/');
  await page.locator('.sidebar').getByRole('button', { name: 'Lists', exact: true }).click();
  await page.getByRole('button', { name: 'New list', exact: true }).click();
  await page.getByLabel('New movie list name').fill('Unsubmitted list');
  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('dialog', { name: 'New list', exact: true })).toHaveCount(0);
  await page.goForward();
  await expect(page.getByRole('button', { name: 'New list', exact: true })).toBeVisible();
  expect(mutations).toEqual([]);
});

test('Failed filter metadata is visibly incomplete and retry restores matches without list mutations', async ({ page }) => {
  const mutations = await fixture(page);
  let unavailable = true;
  await page.route('**/api/tmdb/details**', route => unavailable
    ? route.fulfill({ status: 503, json: { error: 'Fixture metadata unavailable' } })
    : route.fulfill({ json: { ...movies.find(movie => movie.tmdb_id === new URL(route.request().url()).searchParams.get('tmdb_id')), genres: ['Animation'], tmdb_rating: 9, tmdb_vote_count: 5000 } }));
  await page.goto('/movie-lists');
  await choose(page, 'Animated favourites');
  await controls(page).click();
  await page.getByLabel('Minimum rating', { exact: true }).selectOption('8.5');
  await expect(page.getByRole('alert').filter({ hasText: 'Some titles could not be checked' })).toContainText('12');
  await expect(page.getByText('No movies match this list view.', { exact: true })).toHaveCount(0);
  unavailable = false;
  await page.getByRole('button', { name: 'Retry filter metadata', exact: true }).click();
  await expect(page.locator('.movie-lists-card-grid article')).toHaveCount(12);
  await expect(page.getByRole('alert').filter({ hasText: 'Some titles could not be checked' })).toHaveCount(0);
  expect(mutations).toEqual([]);
});
async function choose(page, name) {
  await page.getByRole('button', { name: /^Choose (movies|shows) list:/ }).click();
  await page.locator('.lists-picker-options').getByRole('button', { name: new RegExp(`^${name}`) }).click();
}
async function fixture(page) {
  const lists = structuredClone(initialLists);
  const mutations = [];
  await page.route('**/api/tv/capabilities', route => route.fulfill({ json: { enabled: true } }));
  await page.route('**/api/user/followed-releases**', route => route.fulfill({ json: { movies: [], newly_available: [], removed_owned: [], curation_generation: 1 } }));
  await page.route('**/api/user/lists**', route => {
    const request = route.request();
    if (request.method() === 'GET') return route.fulfill({ json: { lists, curation_generation: 1 } });
    const body = request.postDataJSON();
    mutations.push({ method: request.method(), url: request.url(), body });
    if (request.method() === 'POST') {
      if (body.name === 'Fail list') return route.fulfill({ status: 503, json: { error: 'Cannot save fixture list' } });
      const created = { id: 'created', name: body.name, movies: [] };
      lists.push(created);
      return route.fulfill({ json: created });
    }
    if (request.method() === 'PATCH') {
      const list = lists.find(row => row.id === request.url().split('/').pop());
      list.name = body.name;
      return route.fulfill({ json: list });
    }
    return route.fulfill({ json: {} });
  });
  await page.route('**/api/library/check', route => route.fulfill({ json: { results: (route.request().postDataJSON().movies || []).map(movie => ({ ...movie, found: false })), catalog_generation: 1 } }));
  await page.route('**/api/tmdb/card-projections', route => route.fulfill({ json: { items: {}, catalog_generation: 1 } }));
  await page.route('**/api/tmdb/details**', route => {
    const id = new URL(route.request().url()).searchParams.get('tmdb_id');
    const movie = movies.find(row => row.tmdb_id === id);
    return route.fulfill({ json: { ...movie, genres: ['Animation', 'Action'], language: 'English', country_flag: 'US', tmdb_rating: '7.8', tmdb_vote_count: 1500, backdrop_url: 'https://image.example.test/landscape.jpg', cast: [], directors: [], collection: {}, recommendations: [], similar: [] } });
  });
  return mutations;
}

test('Lists fills the workspace and shares sticky, remembered controls with catalog views', async ({ page }) => {
  await page.setViewportSize({ width: 1790, height: 940 });
  const mutations = await fixture(page);
  await page.goto('/movie-lists');
  await choose(page, 'Animated favourites');
  await expect(page.locator('.movie-lists-card-grid article')).toHaveCount(12);
  await expect(controls(page)).toHaveAttribute('aria-expanded', 'false');
  const toolbar = await page.locator('.lists-toolbar:visible').boundingBox();
  const grid = await page.locator('.movie-lists-card-grid').boundingBox();
  expect(Math.abs(grid.x - toolbar.x)).toBeLessThan(2);
  expect(Math.abs(grid.width - toolbar.width)).toBeLessThan(2);
  await controls(page).click();
  await page.getByLabel('Movie list status').selectOption('missing');
  await page.getByLabel('Select Saved movie 1', { exact: true }).check({ force: true });
  await page.getByRole('heading', { name: 'Saved movie 1', exact: true }).click();
  await expect(controls(page)).toHaveAttribute('aria-expanded', 'false');
  await controls(page).click();
  await expect(page.getByLabel('Movie list status')).toBeVisible();
  const chrome = await page.locator('.workspace-chrome:visible').boundingBox();
  const expanded = await page.locator('.unified-movie-card-expanded').boundingBox();
  expect(expanded.y).toBeGreaterThanOrEqual(chrome.y + chrome.height);
  await page.getByRole('heading', { name: 'Saved movie 1', exact: true }).click();
  await expect(controls(page)).toHaveAttribute('aria-expanded', 'true');
  await expect(page.getByLabel('Movie list status')).toHaveValue('missing');
  await expect(page.getByRole('region', { name: 'Selected movie actions' })).toBeVisible();
  await controls(page).click();
  await page.locator('main.workspace').evaluate(el => { el.scrollTop = 600; });
  const pinned = await page.locator('.workspace-chrome:visible').boundingBox();
  expect(pinned.y).toBeGreaterThanOrEqual(0);
  expect(pinned.y).toBeLessThan(20);
  expect(mutations).toEqual([]);
});

test('List picker searches, dismisses and protects smart lists; dialogs retain failures and save custom names', async ({ page }) => {
  const mutations = await fixture(page);
  await page.goto('/movie-lists');
  await expect(page.getByRole('button', { name: 'List actions', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: /^Choose movies list:/ }).click();
  await page.getByLabel('Find a list').fill('animated');
  await expect(page.locator('.lists-picker-option')).toHaveCount(1);
  await page.getByLabel('Find a list').press('Escape');
  await expect(page.getByLabel('Find a list')).toBeHidden();
  await expect(page.getByRole('button', { name: /^Choose movies list:/ })).toBeFocused();
  await choose(page, 'Animated favourites');
  await page.getByRole('button', { name: 'List actions', exact: true }).click();
  await page.getByRole('button', { name: 'Rename list', exact: true }).click();
  const rename = page.getByRole('dialog', { name: 'Rename list', exact: true });
  await rename.getByLabel('Selected list name').fill('Animation collection');
  await rename.getByRole('button', { name: 'Rename list' }).click();
  await expect(rename).toBeHidden();
  await expect(page.getByRole('button', { name: 'Choose movies list: Animation collection' })).toBeVisible();
  expect(mutations[0].method).toBe('PATCH');
  expect(mutations[0].url).toMatch(/\/api\/user\/lists\/custom$/);
  await page.getByRole('button', { name: 'New list', exact: true }).click();
  const create = page.getByRole('dialog', { name: 'New list', exact: true });
  await create.getByLabel('New movie list name').fill('Fail list');
  await create.getByRole('button', { name: 'Create list' }).click();
  await expect(create.getByRole('alert')).toContainText('Cannot save fixture list');
  await create.getByLabel('New movie list name').fill('Weekend');
  await create.getByRole('button', { name: 'Create list' }).click();
  await expect(create).toBeHidden();
  await expect(page.getByRole('button', { name: 'Choose movies list: Weekend' })).toBeVisible();
  await expect(page.getByText('This list is empty.', { exact: true })).toBeVisible();
});

test('Search and filter clearing are independent, and selection actions remain reachable while collapsed', async ({ page }) => {
  await fixture(page);
  await page.goto('/movie-lists');
  await choose(page, 'Animated favourites');
  await controls(page).click();
  await page.getByLabel('Search movie list').fill('Saved movie 1');
  await page.getByLabel('Movie list status').selectOption('missing');
  await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
  await expect(page.getByLabel('Search movie list')).toHaveValue('Saved movie 1');
  await page.getByLabel('Movie list status').selectOption('missing');
  await page.getByRole('button', { name: 'Clear search', exact: true }).click();
  await expect(page.getByLabel('Movie list status')).toHaveValue('missing');
  await page.getByLabel('Select Saved movie 1', { exact: true }).check({ force: true });
  await controls(page).click();
  const actions = page.getByRole('region', { name: 'Selected movie actions' });
  await expect(actions.getByRole('button', { name: 'Copy selected to...' })).toBeVisible();
  await actions.getByRole('button', { name: 'Clear', exact: true }).click();
  await expect(actions).toBeHidden();
});

test('TV shares the list picker and controls, preserves selection across pages and opens TV Shows', async ({ page }) => {
  const mutations = await fixture(page);
  const rows = [{ id: 701, title: 'TV list show 1', available_count: 0 }, { id: 702, title: 'TV list show 2', available_count: 0 }];
  const requests = [];
  await page.route('**/api/tv/lists?**', route => {
    const params = Object.fromEntries(new URL(route.request().url()).searchParams);
    requests.push(params);
    return route.fulfill({ json: { lists: [{ id: 'watchlist', name: 'Watchlist', count: 41, system: true }, { id: 'custom', name: 'TV favourites', count: 0, system: false }], items: [rows[Number(params.page) - 1]], total: 41, total_pages: 2, page_size: 40 } });
  });
  await page.route('**/api/tv/discover**', route => route.fulfill({ json: { items: [], results: [], total: 0, total_pages: 1, page: 1, page_size: 40 } }));
  await page.goto('/movie-lists');
  await page.getByRole('tab', { name: 'TV Shows' }).click();
  await expect(controls(page)).toHaveAttribute('aria-expanded', 'false');
  await controls(page).click();
  await page.getByLabel('Search TV list').fill('show');
  await page.getByLabel('TV list status').selectOption('missing');
  await page.getByRole('button', { name: 'Clear search', exact: true }).click();
  await expect(page.getByLabel('TV list status')).toHaveValue('missing');
  await page.getByLabel('Select all loaded TV shows').check({ force: true });
  await page.getByRole('navigation', { name: 'TV Lists pages' }).getByRole('button', { name: 'Next' }).click();
  await expect(page.getByRole('heading', { name: 'TV list show 2', exact: true })).toBeVisible();
  await page.getByLabel('Select all loaded TV shows').check({ force: true });
  await controls(page).click();
  await expect(page.getByRole('region', { name: 'Selected TV list actions' })).toContainText('2 selected TV shows');
  await page.getByRole('tab', { name: 'Movies', exact: true }).click();
  await page.getByRole('tab', { name: 'TV Shows', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Selected TV list actions' })).toContainText('2 selected TV shows');
  await page.getByRole('button', { name: 'Find shows', exact: true }).click();
  await expect(page).toHaveURL(/\/discover$/);
  await expect(page.getByRole('region', { name: 'Discover TV Shows', exact: true })).toBeVisible();
  expect(requests.some(row => row.status === 'missing')).toBe(true);
  expect(mutations).toEqual([]);
});

test('Uncached saved movies hydrate the regular Discover card and reuse details when expanded', async ({ page }) => {
  await fixture(page);
  const detailRequests = [];
  page.on('request', request => { if (request.url().includes('/api/tmdb/details?')) detailRequests.push(new URL(request.url()).searchParams.get('tmdb_id')); });
  await page.goto('/movie-lists');
  await choose(page, 'Animated favourites');
  const card = page.locator('.discover-movie-card').filter({ has: page.getByRole('heading', { name: 'Saved movie 1', exact: true }) });
  await expect(card).toContainText('Animation');
  await expect(card).toContainText('English');
  await expect(card).toContainText('US');
  await expect(card).toContainText('7.8');
  await expect(card).toContainText('1.5K votes');
  await expect(card).toHaveAttribute('style', /landscape\.jpg/);
  await card.getByRole('heading', { name: 'Saved movie 1', exact: true }).click();
  await expect(card).toHaveClass(/unified-movie-card-expanded/);
  expect(detailRequests.filter(id => id === movies[0].tmdb_id)).toHaveLength(1);
});

test('Movie list refinements find uncached matches beyond the first page, sort them and preserve valid year drafts', async ({ page }) => {
  await fixture(page);
  const rows = Array.from({ length: 60 }, (_, index) => ({ tmdb_id: String(9500 + index), title: `Refinement movie ${index + 1}`, year: '2024' }));
  await page.route('**/api/user/lists**', route => route.fulfill({ json: { lists: [{ id: 'full-list', name: 'Whole list', movies: rows }], curation_generation: 1 } }));
  await page.route('**/api/tmdb/details**', route => {
    const id = new URL(route.request().url()).searchParams.get('tmdb_id');
    const row = rows.find(movie => movie.tmdb_id === id);
    const matches = Number(id) >= 9558;
    return route.fulfill({ json: { ...row, genres: [matches ? 'Mystery' : 'Animation'], country_flag: matches ? 'GB' : 'US', tmdb_rating: matches ? 9 : 7, tmdb_vote_count: matches ? Number(id) === 9559 ? 9000 : 6000 : 1000 } });
  });
  await page.goto('/movie-lists');
  await expect(page.getByRole('heading', { name: 'Refinement movie 1', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Refinement movie 60', exact: true })).toHaveCount(0);
  await controls(page).click();
  await page.getByLabel('Genre', { exact: true }).selectOption('9648');
  await page.getByLabel('Production country', { exact: true }).selectOption('GB');
  await page.getByLabel('Minimum votes', { exact: true }).selectOption('5000');
  await page.getByLabel('Minimum rating', { exact: true }).selectOption('8.5');
  await page.getByLabel('Year from', { exact: true }).fill('2024');
  await page.getByLabel('Year to', { exact: true }).fill('2025');
  await page.getByLabel('Sort results', { exact: true }).selectOption('vote_count.desc');
  await expect(page.locator('.movie-lists-card-grid article')).toHaveCount(2);
  await expect(page.locator('.movie-lists-card-grid article').first()).toContainText('Refinement movie 60');
  await expect(page.getByText('Loading list metadata to find all matches…', { exact: true })).toBeHidden();
  await page.getByLabel('Year from', { exact: true }).fill('3');
  await expect(page.locator('.movie-lists-card-grid article')).toHaveCount(2);
  await page.getByLabel('Year from', { exact: true }).fill('2026');
  await expect(page.getByRole('alert')).toContainText('Year range cannot be reversed');
  await expect(page.locator('.movie-lists-card-grid article')).toHaveCount(2);
  await controls(page).click();
  await controls(page).click();
  await expect(page.getByLabel('Genre', { exact: true })).toHaveValue('9648');
  await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
  await expect(page.getByLabel('Genre', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('Sort results', { exact: true })).toHaveValue('auto');
  await expect(page.getByRole('heading', { name: 'Refinement movie 1', exact: true })).toBeVisible();
});

test('TV list controls submit TV criteria together and clear refinements independently of search', async ({ page }) => {
  await fixture(page);
  const requests = [];
  await page.route('**/api/tv/lists?**', route => {
    const params = new URL(route.request().url()).searchParams;
    requests.push({ query: params.get('query'), criteria: JSON.parse(params.get('criteria')) });
    return route.fulfill({ json: { lists: [{ id: 'watchlist', name: 'Watchlist', count: 1, system: true }], items: [{ id: 702, tmdb_id: 9520, title: 'TV refinement show' }], total: 1, total_pages: 1, page: 1, page_size: 40 } });
  });
  await page.goto('/movie-lists');
  await page.getByRole('tab', { name: 'TV Shows' }).click();
  await controls(page).click();
  await page.getByLabel('Search TV list').fill('refinement');
  await page.getByLabel('TV Genre', { exact: true }).selectOption('10765');
  await page.getByLabel('TV Origin country', { exact: true }).selectOption('GB');
  await page.getByLabel('TV Minimum votes', { exact: true }).selectOption('1000');
  await page.getByLabel('TV Minimum rating', { exact: true }).selectOption('8');
  await page.getByLabel('TV Year from', { exact: true }).fill('2020');
  await page.getByLabel('TV Year to', { exact: true }).fill('2025');
  await page.getByLabel('TV Sort results', { exact: true }).selectOption('vote_average.desc');
  await expect.poll(() => requests.at(-1)?.criteria.groups.length).toBe(5);
  await expect.poll(() => requests.at(-1)?.criteria.sort.key).toBe('vote_average.desc');
  expect(requests.at(-1).criteria.groups[0].values[0].id).toBe('10765');
  await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
  await expect.poll(() => requests.at(-1)?.criteria.groups.length).toBe(0);
  await expect(page.getByLabel('Search TV list')).toHaveValue('refinement');
  await expect(page.getByLabel('TV Genre', { exact: true })).toHaveValue('');
});
