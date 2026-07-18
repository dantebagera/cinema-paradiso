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
    rating: parityMovie.tmdb_rating
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
        library_item: parityLibraryItem
      }]
    } });
  });
  await page.route('**/api/user/lists', async (route) => {
    await route.fulfill({ json: { lists: [{ id: 'render-parity', name: 'Render Parity', movies: [parityMovie] }] } });
  });
  await page.route('**/api/tmdb/discover**', async (route) => {
    await route.fulfill({ json: { results: [parityMovie], page: 1, total_pages: 1, total_results: 1 } });
  });
}

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

test('Library, Discover-owned, and Movie List cards render one shared movie identity', async ({ page }) => {
  await mockCardParityApis(page);

  await page.goto('/library', { waitUntil: 'domcontentloaded' });
  const libraryCard = page.locator('.library-movie-card').filter({ hasText: parityMovie.title });
  await expect(libraryCard.getByRole('heading', { name: parityMovie.title })).toBeVisible();
  await expect(libraryCard).toContainText(parityMovie.year);

  await page.goto('/discover', { waitUntil: 'domcontentloaded' });
  const discoverCard = page.locator('.discover-movie-card').filter({ hasText: parityMovie.title });
  await expect(discoverCard.getByRole('heading', { name: parityMovie.title })).toBeVisible();
  await expect(discoverCard).toContainText(parityMovie.year);
  await expect(discoverCard.getByText('Owned', { exact: true })).toBeVisible();

  await page.goto('/movie-lists', { waitUntil: 'domcontentloaded' });
  const listCard = page.locator('.library-movie-card').filter({ hasText: parityMovie.title });
  await expect(listCard.getByRole('heading', { name: parityMovie.title })).toBeVisible();
  await expect(listCard).toContainText(parityMovie.year);
});

test('expanded Library cards read persisted SQL plots without calling TMDB', async ({ page }) => {
  await mockCardParityApis(page);
  let tmdbDetailsRequests = 0;
  await page.route('**/api/library/details**', async (route) => {
    await route.fulfill({ json: {
      catalog_generation: 1,
      item: {
        ...parityLibraryItem,
        canonical_metadata: {
          ...parityLibraryItem.canonical_metadata,
          plot: 'Stored SQL detail.',
          summary: 'Stored SQL detail.'
        }
      }
    } });
  });
  await page.route('**/api/tmdb/details**', async (route) => {
    const requestUrl = new URL(route.request().url());
    if (requestUrl.searchParams.get('tmdb_id') === parityMovie.tmdb_id) tmdbDetailsRequests += 1;
    await route.fulfill({ status: 503, json: { error: 'TMDB unavailable' } });
  });

  await page.goto('/library', { waitUntil: 'domcontentloaded' });
  const libraryCard = page.locator('.library-movie-card').filter({ hasText: parityMovie.title });
  await expect(libraryCard.getByRole('heading', { name: parityMovie.title })).toBeVisible();
  await page.waitForTimeout(250);
  tmdbDetailsRequests = 0;
  await libraryCard.click();

  await expect(libraryCard).toContainText('Stored SQL detail.');
  expect(tmdbDetailsRequests).toBe(0);
});
