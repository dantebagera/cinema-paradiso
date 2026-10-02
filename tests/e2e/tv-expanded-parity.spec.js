import { test, expect } from '@playwright/test';

test.skip(process.env.CP_TV_E2E !== '1', 'Requires disposable TV fixture server');
test.use({ viewport: { width: 1920, height: 1080 }, reducedMotion: 'reduce' });

test('standard TV card keeps dates and episode counts together and opens from the card', async ({ page }) => {
  await page.goto('/library');
  await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
  const card = page.getByRole('link', { name: 'Open Harbor Signals' });
  const facts = card.locator('.unified-movie-title-block > span');
  await expect(facts).toContainText('2020');
  await expect(facts).toContainText('2 seasons · 4 episodes');
  for (const width of [1920, 1366]) {
    await page.setViewportSize({ width, height: 1080 });
    const layout = await facts.evaluate(element => ({ height: element.getBoundingClientRect().height,
      contentWidth: element.scrollWidth, availableWidth: element.clientWidth }));
    expect(layout.height).toBeLessThan(24);
    expect(layout.contentWidth).toBeLessThanOrEqual(layout.availableWidth + 1);
  }
  await expect(card.getByRole('button', { name: 'Stream' })).toHaveCount(0);
  await expect(card.getByRole('button', { name: 'View series' })).toHaveCount(0);
  await card.click();
  await expect(page.getByRole('heading', { name: 'Harbor Signals', exact: true })).toBeVisible();
});

test('related TV posters render as full tiles with readable titles', async ({ page }) => {
  await page.route('**/api/tv/related**', route => route.fulfill({ json: {
    results: Array.from({ length: 16 }, (_, index) => ({
      tmdb_id: 910000 + index, title: `Related Series ${index + 1}`, year: '2024', tmdb_rating: 8.1,
      poster_url: '/static/logo.svg', media_type: 'tv', available_count: 0,
    })), source: 'recommendations', page: 1, page_size: 20, has_next: false,
  } }));
  await page.goto('/library');
  await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
  await page.getByRole('link', { name: 'Open Harbor Signals' }).click();
  const rail = page.getByRole('region', { name: 'More like this' });
  const tile = rail.getByRole('button', { name: 'Open Related Series 1 TV series' });
  await expect(tile).toBeVisible();
  await expect.poll(() => tile.locator('img').evaluate(image => image.naturalWidth)).toBeGreaterThan(0);
  const geometry = await tile.evaluate((element) => {
    const poster = element.querySelector('.related-poster');
    const image = poster?.querySelector('img');
    return { display: getComputedStyle(element).display, width: element.getBoundingClientRect().width,
      posterHeight: poster?.getBoundingClientRect().height, imageLoaded: Boolean(image?.naturalWidth),
      title: element.querySelector('strong')?.textContent };
  });
  expect(geometry.display).toBe('grid');
  expect(geometry.width).toBeGreaterThan(85);
  expect(geometry.posterHeight).toBeGreaterThan(120);
  expect(geometry.imageLoaded).toBe(true);
  expect(geometry.title).toBe('Related Series 1');
});

test('TV score, IMDb, and temporary Arabic display match Movie controls', async ({ page, request }) => {
  await page.goto('/library');
  await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
  await page.getByRole('link', { name: 'Open Harbor Signals' }).click();
  const header = page.locator('.tv-series-header');
  await expect(header.locator('.tv-series-heading .unified-expanded-rating')).toContainText('8.2');
  await expect(header.locator('.tv-series-heading .unified-expanded-rating')).toContainText('1.2K votes');
  await expect(header.locator('.movie-imdb-link')).toHaveAttribute('href', 'https://www.imdb.com/title/tt1234567/');
  await header.locator('.movie-language-toggle').click();
  await expect(header.getByRole('heading', { name: 'إشارات الميناء' })).toBeVisible();
  await expect(header).toContainText('بلدة ساحلية تتبع إشارة غامضة.');
  await expect(header.locator('.tv-series-badges .unified-chip').first()).toHaveText('دراما');
  await expect(header.locator('.movie-language-toggle')).toHaveAttribute('aria-pressed', 'true');
  await expect(header.locator('.unified-expanded-rating')).toContainText('8.2');
  await header.locator('.movie-language-toggle').click();
  await expect(header.getByRole('heading', { name: 'Harbor Signals' })).toBeVisible();
  const saved = await (await request.get('/api/tv/series/1')).json();
  expect(saved.title).toBe('Harbor Signals');
  const invalid = await request.get('/api/tv/translation/900001?language=fr-FR');
  expect(invalid.status()).toBe(400);
});

test('TV badges, movie-style credits, TV filmography, and related navigation work without changing the library', async ({ page, request }) => {
  const movieRequests = [];
  const personQueries = [];
  page.on('request', request => { if (request.url().includes('/api/tmdb/related') || request.url().includes('/api/library/check')) movieRequests.push(request.url()); });
  await page.route('**/api/tmdb/person**', route => route.fulfill({ json: { id: 33192, name: 'Joel Edgerton', biography: 'A test biography.', known_for_department: 'Acting' } }));
  await page.route('**/api/tv/related**', route => {
    const params = new URL(route.request().url()).searchParams;
    const result = { tmdb_id: 900002, id: null, title: 'Open Water', first_air_date: '2020-01-01', year: '2020', rating: 8.2, tmdb_rating: 8.2,
      genres: ['Drama'], original_language_name: 'English', origin_country: ['GB'], available_count: 0, media_type: 'tv' };
    return route.fulfill({ json: { results: [result], source: params.get('source'), page: Number(params.get('page')), page_size: 20,
      has_next: false, total_pages: 1, total_results: 1 } });
  });
  await page.route('**/api/tv/catalog/search', async route => {
    const body = route.request().postDataJSON();
    const person = body.query?.groups?.find(group => group.type === 'person');
    if (!person) return route.continue();
    personQueries.push(body);
    return route.fulfill({ json: { items: [{ tmdb_id: 900002, id: null, title: 'Open Water', first_air_date: '2020-01-01', genres: ['Drama'], available_count: 0 }],
      page: body.page, page_size: 20, total_pages: 1, total: 1, complete: true } });
  });

  await page.goto('/discover');
  await page.getByRole('tablist', { name: 'Discover tools' }).getByRole('button', { name: 'Explore Shows', exact: true }).click();
  await page.getByRole('textbox', { name: 'Search TV shows' }).fill('Dark Matter');
  await page.getByRole('button', { name: 'Search TV', exact: true }).click();
  await page.getByRole('link', { name: 'Open Dark Matter' }).click();

  const header = page.locator('.tv-series-header');
  await expect(header.locator('.tv-series-badges .unified-chip')).toContainText(['Sci-Fi & Fantasy', 'Drama', 'English', 'US']);
  const cast = page.getByRole('region', { name: 'Series cast' });
  await expect(cast.locator('.person-card').first()).toContainText('Joel Edgerton');
  await expect(cast.getByRole('button', { name: 'More cast' })).toBeVisible();
  expect(await cast.locator('.tv-cast').evaluate(row => row.scrollWidth > row.clientWidth)).toBe(true);
  await expect(cast.getByRole('button', { name: 'Open biography for Joel Edgerton', exact: true })).toBeVisible();
  await expect(cast.getByRole('button', { name: 'Open filmography for Joel Edgerton', exact: true })).toBeVisible();
  await cast.getByRole('button', { name: 'Open biography for Joel Edgerton', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Biography for Joel Edgerton' })).toContainText('A test biography.');
  await page.getByRole('button', { name: 'Close biography' }).click();
  await cast.getByRole('button', { name: 'Open filmography for Joel Edgerton', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Joel Edgerton · TV shows' })).toBeVisible();
  expect(personQueries).toHaveLength(1);
  expect(personQueries[0].query.groups.find(group => group.type === 'person').values[0]).toMatchObject({ id: '33192', role: 'actor' });
  await page.getByRole('button', { name: 'Back to series' }).click();
  await expect(page.getByRole('heading', { name: 'Dark Matter', exact: true })).toBeVisible();

  const rail = page.getByRole('region', { name: 'More like this' });
  await expect(rail.getByRole('button', { name: 'Open Open Water TV series' })).toBeVisible();
  await rail.getByRole('button', { name: 'Similar' }).click();
  await expect(rail.getByRole('button', { name: 'Similar' })).toHaveAttribute('aria-pressed', 'true');
  await rail.getByRole('button', { name: 'View all' }).click();
  await expect(page.getByRole('heading', { name: 'More like Dark Matter' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open Open Water' })).toBeVisible();
  await page.getByRole('button', { name: 'Back to series' }).click();
  await rail.getByRole('button', { name: 'Open Open Water TV series' }).click();
  await expect(page.getByRole('heading', { name: 'Open Water', exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Dark Matter', exact: true })).toBeVisible();
  expect(movieRequests).toEqual([]);
  const catalog = await (await request.get('/api/tv/series')).json();
  expect(catalog.items.some(item => item.tmdb_id === 196322)).toBe(false);
});

test('saved series keeps its selected season through creator TV filmography and Back', async ({ page }) => {
  await page.route('**/api/tv/related**', route => route.fulfill({ json: { results: [], source: 'recommendations', page: 1, page_size: 20, total_pages: 1, total_results: 0, has_next: false } }));
  await page.goto('/library');
  await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
  await page.getByRole('link', { name: 'Open Harbor Signals' }).click();
  const header = page.locator('.tv-series-header');
  await expect(header.locator('.tv-series-badges .unified-chip')).toContainText(['Drama', 'Mystery', 'English', 'GB']);
  await page.getByRole('combobox', { name: 'TV season' }).selectOption('2');
  await page.getByRole('region', { name: 'Series cast' }).getByRole('button', { name: 'Open filmography for Mira Stone', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Mira Stone · TV shows' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open Harbor Signals' })).toBeVisible();
  await page.getByRole('button', { name: 'Back to series' }).click();
  await expect(page.getByRole('combobox', { name: 'TV season' })).toHaveValue('2');
  await expect(page.getByRole('heading', { name: 'Harbor Signals', exact: true })).toBeVisible();
});

test('a TV recommendation failure keeps the series usable and offers retry', async ({ page }) => {
  await page.route('**/api/tv/related**', route => route.fulfill({ status: 503, json: { error: 'The provider could not complete this request.' } }));
  await page.goto('/discover');
  await page.getByRole('tablist', { name: 'Discover tools' }).getByRole('button', { name: 'Explore Shows', exact: true }).click();
  await page.getByRole('textbox', { name: 'Search TV shows' }).fill('Dark Matter');
  await page.getByRole('button', { name: 'Search TV', exact: true }).click();
  await page.getByRole('link', { name: 'Open Dark Matter' }).click();
  const rail = page.getByRole('region', { name: 'More like this' });
  await expect(rail.getByRole('button', { name: 'Retry' }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Download season' })).toBeEnabled();
  await expect(page.getByRole('heading', { name: 'Dark Matter', exact: true })).toBeVisible();
});
