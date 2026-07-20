import { expect, test } from '@playwright/test';

const parityMovie = {
  tmdb_id: '42',
  imdb_id: 'tt0000042',
  title: 'Render Parity Movie',
  year: '2024',
  poster_url: '',
  tmdb_rating: '8.4',
  tmdb_vote_count: 120,
  genres: ['Drama'],
  plot: 'Stored SQL detail.'
};

const parityLibraryItem = {
  path: 'E:/Movies/Render.Parity.Movie.2024.mkv',
  filename: 'Render.Parity.Movie.2024.mkv',
  title: 'Render Parity Movie (2024)',
  resolution: '1080p',
  size: 100,
  size_human: '100 B',
  metadata_status: 'accepted',
  metadata_accepted: true,
  canonical_metadata: {
    accepted: true,
    title: parityMovie.title,
    year: parityMovie.year,
    tmdb_id: parityMovie.tmdb_id,
    imdb_id: parityMovie.imdb_id,
    poster_url: parityMovie.poster_url,
    genres: parityMovie.genres,
    plot: parityMovie.plot,
    summary: parityMovie.plot,
    rating: parityMovie.tmdb_rating,
    tmdb_vote_count: parityMovie.tmdb_vote_count,
    detail_provider: 'tmdb_snapshot'
  }
};

const parityDeferredDetails = {
  ...parityLibraryItem,
  canonical_metadata: {
    ...parityLibraryItem.canonical_metadata,
    cast: [{ id: '1001', name: 'SQL Cast Member', character: 'Archivist' }],
    directors: [{ id: '1002', name: 'SQL Director' }],
    collection: { id: '7001', name: 'SQL Collection' },
    trailer_url: 'https://www.youtube.com/watch?v=sql-parity'
  }
};

async function mockCardParityApis(page) {
  await page.route('**/api/library?view=cards', async (route) => {
    await route.fulfill({ json: { items: [parityLibraryItem], count: 1, catalog_generation: 1 } });
  });
  await page.route('**/api/library/check', async (route) => {
    await route.fulfill({ json: {
      results: [{
        found: true,
        path: parityLibraryItem.path,
        resolution: parityLibraryItem.resolution,
        size_human: parityLibraryItem.size_human,
        tmdb_id: parityMovie.tmdb_id,
        imdb_id: parityMovie.imdb_id,
        title: parityMovie.title,
        year: parityMovie.year,
        canonical_card: parityLibraryItem,
        library_item: parityLibraryItem
      }]
      , catalog_generation: 1
    } });
  });
  await page.route('**/api/user/lists', async (route) => {
    await route.fulfill({ json: { lists: [{ id: 'render-parity', name: 'Render Parity', movies: [parityMovie] }], curation_generation: 1 } });
  });
  await page.route('**/api/tmdb/discover**', async (route) => {
    await route.fulfill({ json: { results: [parityMovie], page: 1, total_pages: 1, total_results: 1 } });
  });
}

const workspaces = [
  ['/', 'heading', 'Home'],
  ['/library', 'heading', 'Movie View'],
  ['/movie-lists', 'heading', 'Movie Lists'],
  ['/cleanup', 'heading', /^Library Maintenance/],
  ['/discover', 'heading', 'Discover'],
  ['/ai-control', 'heading', /^AI Control/],
  ['/iptv', 'heading', 'IPTV'],
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
    await expect(page.getByRole(role, { name, exact: typeof name === 'string' })).toBeVisible();
    await expect(page.locator('.app-crash-screen')).toHaveCount(0);
    expect(pageErrors).toEqual([]);
  });
}

test('Downloads shows qBittorrent without migration-only review records', async ({ page }) => {
  await page.goto('/downloads', { waitUntil: 'domcontentloaded' });

  await expect(page.getByTitle('qBittorrent Downloads')).toBeVisible();
  await expect(page.getByText('Legacy import audit')).toHaveCount(0);
  await expect(page.getByText('deferred completed imports')).toHaveCount(0);
});

test('Library switches between canonical movie and raw file views', async ({ page }) => {
  await page.goto('/library', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Movie View' })).toBeVisible();

  await page.getByRole('button', { name: 'File View' }).click();
  await expect(page.getByRole('heading', { name: 'File View' })).toBeVisible();

  await page.getByRole('button', { name: 'Movie View' }).click();
  await expect(page.getByRole('heading', { name: 'Movie View' })).toBeVisible();
});

test('Library people search renders portraits stored in canonical metadata', async ({ page }) => {
  const profileUrl = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';
  const peopleItem = {
    path: 'E:/Movies/Apollo.13.1995.mkv',
    canonical_metadata: {
      accepted: true,
      title: 'Apollo 13',
      year: '1995',
      cast: [{ id: '31', name: 'Tom Hanks', profile_url: profileUrl }],
      directors: []
    },
    plex_cast: [],
    plex_directors: []
  };
  await page.route('**/api/library?view=cards', async (route) => {
    await route.fulfill({ json: {
      items: [{
        path: peopleItem.path,
        canonical_metadata: { accepted: true, title: 'Apollo 13', year: '1995' }
      }],
      count: 1,
      catalog_generation: 1
    } });
  });
  await page.route('**/api/library?view=people', async (route) => {
    await route.fulfill({ json: { items: [peopleItem], count: 1, catalog_generation: 1 } });
  });

  await page.goto('/library', { waitUntil: 'domcontentloaded' });
  await page.getByLabel('Library search type').selectOption('people');
  await page.getByPlaceholder('Search people in your library...').fill('Tom Hanks');

  const card = page.locator('.person-search-card').filter({ hasText: 'Tom Hanks' });
  const portrait = card.getByRole('img', { name: 'Tom Hanks profile' });
  await expect(portrait).toBeVisible();
  await expect.poll(() => portrait.evaluate((image) => image.naturalWidth)).toBeGreaterThan(0);
});

test('Library credit clicks load the people projection before filtering owned work', async ({ page }) => {
  const cards = [
    {
      path: 'E:/Movies/Awakenings.1990.mkv',
      title: 'Awakenings (1990)',
      resolution: '1080p',
      canonical_metadata: { accepted: true, title: 'Awakenings', year: '1990', plot: 'First plot.' }
    },
    {
      path: 'E:/Movies/Heat.1995.mkv',
      title: 'Heat (1995)',
      resolution: '1080p',
      canonical_metadata: { accepted: true, title: 'Heat', year: '1995', plot: 'Second plot.' }
    }
  ];
  const person = { id: '380', name: 'Robert De Niro', character: 'Lead' };
  await page.route('**/api/library?view=cards', (route) => route.fulfill({ json: { items: cards, count: 2, catalog_generation: 1 } }));
  await page.route('**/api/library?view=people', (route) => route.fulfill({ json: {
    items: cards.map((item) => ({
      path: item.path,
      canonical_metadata: { cast: [person], directors: [] },
      plex_cast: [],
      plex_directors: []
    })),
    count: 2,
    catalog_generation: 1
  } }));
  await page.route('**/api/library/details**', (route) => route.fulfill({ json: {
    item: { ...cards[0], canonical_metadata: { ...cards[0].canonical_metadata, cast: [person], directors: [] } },
    catalog_generation: 1
  } }));

  await page.goto('/library', { waitUntil: 'domcontentloaded' });
  const awakenings = page.locator('.library-movie-card').filter({ hasText: 'Awakenings' });
  await awakenings.click();
  await awakenings.getByText('Robert De Niro', { exact: true }).click();

  await expect(page.locator('.library-movie-card')).toHaveCount(2);
  await expect(page.getByText('Actor: Robert De Niro', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Maintenance', exact: true }).click();
  await page.getByRole('button', { name: /Upgrade candidates/ }).click();

  await expect(page).toHaveURL(/\/library$/);
  await expect(page.getByText('Actor: Robert De Niro', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Open Filters' }).click();
  await expect(page.getByLabel('Library quality filter')).toHaveValue('upgrade');
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

  await page.getByLabel('Library quality filter').selectOption('all');
  await page.getByRole('button', { name: 'Discover', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Discover', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Library', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Movie View', exact: true })).toBeVisible();
  await expect(page.getByLabel('Library quality filter')).toHaveValue('all');
});

test('every stateful workspace preserves its page state after sidebar navigation', async ({ page }) => {
  await mockCardParityApis(page);
  await page.route('**/api/iptv/status', (route) => route.fulfill({ json: {
    configured: true,
    generation: 1,
    counts: { live: 0, movie: 0, series: 0 },
    sync: { state: 'idle' }
  } }));
  await page.route('**/api/iptv/recent**', (route) => route.fulfill({ json: { items: [] } }));
  await page.route('**/api/iptv/categories**', (route) => route.fulfill({ json: { items: [] } }));
  await page.route('**/api/iptv/items**', (route) => route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 30 } }));

  const openSection = (name) => page.getByRole('button', { name: name === 'AI Control' ? /AI Control/ : name, exact: name !== 'AI Control' }).click();

  await page.goto('/library', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Open Filters' }).click();
  await page.getByLabel('Library quality filter').selectOption('upgrade');

  await openSection('Discover');
  await page.getByLabel('Library ownership').selectOption('owned');

  await openSection('Movie Lists');
  await page.getByPlaceholder('Search the selected list...').fill('parity list state');

  await openSection('Maintenance');
  await page.getByRole('tab', { name: 'Identity' }).click();
  await page.getByPlaceholder('Search files, paths, or catalog titles...').fill('identity state');
  await page.locator('.workspace-panel:visible').evaluate((panel) => panel.style.minHeight = '1800px');
  const maintenanceScrollTop = await page.locator('main.workspace').evaluate((workspace) => {
    workspace.scrollTop = Math.min(300, Math.max(0, workspace.scrollHeight - workspace.clientHeight));
    return workspace.scrollTop;
  });
  expect(maintenanceScrollTop).toBeGreaterThan(0);

  await openSection('AI Control');
  await page.getByPlaceholder('Tell CP what to find, list, download, or delete...').fill('show my horror films');

  await openSection('IPTV');
  await page.getByRole('button', { name: 'Movies', exact: true }).click();
  await page.getByPlaceholder('Search movie...').fill('matrix');

  await openSection('Settings');
  await page.getByLabel('Button label').fill('Temporary state');

  await openSection('Downloads');
  const downloadsFrame = page.getByTitle('qBittorrent Downloads');
  await downloadsFrame.evaluate((frame) => frame.dataset.stateToken = 'preserved');

  await openSection('Library');
  await expect(page.getByLabel('Library quality filter')).toHaveValue('upgrade');
  await openSection('Discover');
  await expect(page.getByLabel('Library ownership')).toHaveValue('owned');
  await openSection('Movie Lists');
  await expect(page.getByPlaceholder('Search the selected list...')).toHaveValue('parity list state');
  await openSection('Maintenance');
  await expect(page.getByRole('tab', { name: 'Identity' })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByPlaceholder('Search files, paths, or catalog titles...')).toHaveValue('identity state');
  await expect.poll(() => page.locator('main.workspace').evaluate((workspace) => workspace.scrollTop)).toBe(maintenanceScrollTop);
  await openSection('AI Control');
  await expect(page.getByPlaceholder('Tell CP what to find, list, download, or delete...')).toHaveValue('show my horror films');
  await openSection('IPTV');
  await expect(page.getByRole('button', { name: 'Movies', exact: true })).toHaveClass(/is-active/);
  await expect(page.getByPlaceholder('Search movie...')).toHaveValue('matrix');
  await openSection('Settings');
  await expect(page.getByLabel('Button label')).toHaveValue('Temporary state');
  await openSection('Downloads');
  await expect(downloadsFrame).toHaveAttribute('data-state-token', 'preserved');
});

test('Library, Discover-owned, and Movie List cards render one canonical movie contract', async ({ page }) => {
  await mockCardParityApis(page);
  let tmdbDetailsRequests = 0;
  let libraryDetailsRequests = 0;
  await page.route('**/api/library/details**', async (route) => {
    libraryDetailsRequests += 1;
    await route.fulfill({ json: { item: parityDeferredDetails, catalog_generation: 1 } });
  });
  await page.route('**/api/tmdb/details**', async (route) => {
    const requestUrl = new URL(route.request().url());
    if (requestUrl.searchParams.get('tmdb_id') === parityMovie.tmdb_id) tmdbDetailsRequests += 1;
    await route.fulfill({ status: 503, json: { error: 'TMDB unavailable' } });
  });

  await page.goto('/library', { waitUntil: 'domcontentloaded' });
  const libraryCard = page.locator('.library-movie-card').filter({ hasText: parityMovie.title });
  await expect(libraryCard.getByRole('heading', { name: parityMovie.title })).toBeVisible();
  await expect(libraryCard).toContainText(parityMovie.year);
  const libraryRequestsBeforeExpand = tmdbDetailsRequests;
  await libraryCard.click();
  await expect(libraryCard).toContainText(parityMovie.plot);
  await expect(libraryCard).toContainText('SQL Director');
  await expect(libraryCard).toContainText('SQL Cast Member');
  await expect(libraryCard).toContainText('SQL Collection');
  await expect(libraryCard.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  await expect(libraryCard.getByRole('button', { name: 'Follow', exact: true })).toHaveCount(0);
  expect(tmdbDetailsRequests).toBe(libraryRequestsBeforeExpand);

  await page.goto('/discover', { waitUntil: 'domcontentloaded' });
  const discoverCard = page.locator('.discover-movie-card').filter({ hasText: parityMovie.title });
  await expect(discoverCard.getByRole('heading', { name: parityMovie.title })).toBeVisible();
  await expect(discoverCard).toContainText(parityMovie.year);
  await expect(discoverCard.getByText('Owned', { exact: true })).toBeVisible();
  const discoverRequestsBeforeExpand = tmdbDetailsRequests;
  await discoverCard.click();
  await expect(discoverCard).toContainText(parityMovie.plot);
  await expect(discoverCard).toContainText('SQL Director');
  await expect(discoverCard).toContainText('SQL Cast Member');
  await expect(discoverCard).toContainText('SQL Collection');
  await expect(discoverCard.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  await expect(discoverCard.getByRole('button', { name: 'Follow', exact: true })).toHaveCount(0);
  expect(tmdbDetailsRequests).toBe(discoverRequestsBeforeExpand);

  await page.goto('/movie-lists', { waitUntil: 'domcontentloaded' });
  const listCard = page.locator('.library-movie-card').filter({ hasText: parityMovie.title });
  await expect(listCard.getByRole('heading', { name: parityMovie.title })).toBeVisible();
  await expect(listCard).toContainText(parityMovie.year);
  const listRequestsBeforeExpand = tmdbDetailsRequests;
  await listCard.click();
  await expect(listCard).toContainText(parityMovie.plot);
  await expect(listCard).toContainText('SQL Director');
  await expect(listCard).toContainText('SQL Cast Member');
  await expect(listCard).toContainText('SQL Collection');
  await expect(listCard.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  await expect(listCard.getByRole('button', { name: 'Follow', exact: true })).toHaveCount(0);
  expect(tmdbDetailsRequests).toBe(listRequestsBeforeExpand);

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.inspector')).toContainText(parityMovie.plot);
  await expect(page.locator('.inspector')).toContainText('SQL Cast Member');

  await page.route('**/api/ai-control/preview', async (route) => {
    await route.fulfill({ json: {
      state: 'valid_plan',
      plan_id: 'sql-parity-plan',
      action: 'find',
      summary: 'SQL parity plan',
      message: 'One owned result',
      total_matches: 1,
      items: [parityMovie]
    } });
  });
  await page.goto('/ai-control', { waitUntil: 'domcontentloaded' });
  await page.getByPlaceholder('Tell CP what to find, list, download, or delete...').fill('Find my parity movie');
  await page.getByRole('button', { name: 'Preview command' }).click();
  await page.getByRole('button', { name: 'Display as cards' }).click();
  const aiCard = page.locator('.discover-movie-card').filter({ hasText: parityMovie.title });
  await aiCard.click();
  await expect(aiCard).toContainText('SQL Director');
  await expect(aiCard).toContainText('SQL Cast Member');
  await expect(aiCard).toContainText('SQL Collection');

  expect(libraryDetailsRequests).toBeGreaterThanOrEqual(5);
  expect(tmdbDetailsRequests).toBe(0);
});

test('curation generation refresh keeps an expanded Discover card open', async ({ page }) => {
  await mockCardParityApis(page);
  await page.route('**/api/library/details**', (route) => route.fulfill({ json: {
    item: parityDeferredDetails,
    catalog_generation: 1
  } }));

  await page.goto('/discover', { waitUntil: 'domcontentloaded' });
  const card = page.locator('.discover-movie-card').filter({ hasText: parityMovie.title });
  await card.click();
  await expect(card).toContainText('SQL Director');

  await page.evaluate(() => {
    window.dispatchEvent(new CustomEvent('cp-curation-generation-changed', {
      detail: { previousGeneration: 1, generation: 2 }
    }));
  });

  await expect(card).toContainText('SQL Director');
  await expect(card).toHaveClass(/unified-movie-card-expanded/);
});
