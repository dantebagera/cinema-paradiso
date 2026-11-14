import { test, expect } from '@playwright/test';

test.skip(process.env.CP_TV_E2E !== '1', 'Requires disposable TV fixture server');
test.use({ viewport: { width: 1920, height: 1080 }, reducedMotion: 'reduce' });

test('expanded TV cast and related rails share arrow scrolling and keep portrait actions clear', async ({ page }) => {
  await page.route(/\/api\/tv\/series\/\d+$/, async route => {
    const response = await route.fetch();
    const series = await response.json();
    await route.fulfill({ json: { ...series, cast: Array.from({ length: 16 }, (_, index) => ({
      tmdb_id: 88000 + index, name: `TV Credit ${index + 1}`, kind: index ? 'actor' : 'creator',
      role: index ? `Role ${index}` : 'Creator', portrait_url: '/static/logo.svg',
    })) } });
  });
  await page.route('**/api/tv/related**', route => route.fulfill({ json: {
    results: Array.from({ length: 20 }, (_, index) => ({ tmdb_id: 99000 + index, title: `TV Recommendation ${index + 1}`, year: '2024', poster_url: '/static/logo.svg' })),
    source: 'recommendations', page: 1, has_next: false,
  } }));
  await page.goto('/library');
  await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
  await page.getByRole('link', { name: 'Open Harbor Signals' }).click();
  for (const label of ['cast', 'related titles']) {
    const track = page.getByRole('group', { name: `${label} cards`, exact: true });
    const left = page.getByRole('button', { name: `Scroll ${label} left`, exact: true });
    const right = page.getByRole('button', { name: `Scroll ${label} right`, exact: true });
    await expect(left).toBeDisabled();
    await expect(right).toBeEnabled();
    const arrowBox = await right.boundingBox();
    const cardBox = await track.locator(':scope > *').first().boundingBox();
    const trackBox = await track.boundingBox();
    const leftBox = await left.boundingBox();
    expect(Math.abs(leftBox.x - trackBox.x)).toBeLessThan(1);
    expect(Math.abs(arrowBox.x + arrowBox.width - trackBox.x - trackBox.width)).toBeLessThan(1);
    expect(Math.abs(arrowBox.height - cardBox.height)).toBeLessThan(1);
    expect(Math.abs(arrowBox.y - cardBox.y)).toBeLessThan(1);
    expect(await right.evaluate(element => getComputedStyle(element).borderTopWidth)).toBe('0px');
    await page.getByRole('heading', { name: 'Harbor Signals', exact: true }).hover();
    await expect.poll(() => right.evaluate(element => getComputedStyle(element).opacity)).toBe('0');
    await right.hover();
    await expect.poll(() => right.evaluate(element => getComputedStyle(element).opacity)).toBe('1');
    await right.click();
    await expect.poll(() => track.evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
    await expect(left).toBeEnabled();
    await expect(right).toBeDisabled();
    await expect.poll(() => track.evaluate(element => element.scrollWidth - element.clientWidth - element.scrollLeft)).toBeLessThan(2);
    expect(await track.evaluate(element => getComputedStyle(element).scrollbarWidth)).toBe('none');
    await left.click();
    await expect(right).toBeEnabled();
  }
  await page.getByRole('button', { name: 'Full Credit', exact: true }).click();
  const creator = page.getByRole('region', { name: 'Directors and creators', exact: true }).locator('.director-person');
  const portraitBox = await creator.locator('.person-avatar').boundingBox();
  const bioBox = await creator.getByRole('button', { name: 'Open biography for TV Credit 1' }).boundingBox();
  expect(bioBox.x).toBeGreaterThanOrEqual(portraitBox.x + portraitBox.width + 4);
});

test('TV Full Credit starts collapsed, retains crew groups and portraits, and leaves actors scrollable', async ({ page }) => {
  const profileRequests = [];
  await page.route('**/api/tmdb/person?**', route => {
    const id = new URL(route.request().url()).searchParams.get('person_id');
    profileRequests.push(id);
    return route.fulfill({ json: { id, name: `Creative ${id}`, profile_url: id === '77103' ? '' : '/static/logo.svg' } });
  });
  await page.route(/\/api\/tv\/series\/\d+$/, async route => {
    const series = await (await route.fetch()).json();
    await route.fulfill({ json: { ...series, cast: [
      { tmdb_id: 77101, name: 'First Director', kind: 'director', role: 'Director' },
      { tmdb_id: 77102, name: 'Second Director', kind: 'director', role: 'Director' },
      { tmdb_id: 77101, name: 'First Director', kind: 'creator', role: 'Creator' },
      { tmdb_id: 77103, name: 'Creator Without Photo', kind: 'creator', role: 'Creator' },
      { tmdb_id: 77104, name: 'Writer', kind: 'writer', role: 'Screenplay', portrait_url: '/static/logo.svg' },
      ...Array.from({ length: 16 }, (_, index) => ({ tmdb_id: 77200 + index, name: `Actor ${index + 1}`, kind: 'actor', role: `Role ${index + 1}`, portrait_url: '/static/logo.svg' })),
    ] } });
  });
  await page.goto('/library');
  await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
  await page.getByRole('link', { name: 'Open Harbor Signals' }).click();
  const fullCredit = page.getByRole('button', { name: 'Full Credit', exact: true });
  await expect(fullCredit).toBeVisible();
  await expect(page.getByText('Director · Creator', { exact: true })).not.toBeVisible();
  await expect(page.getByRole('group', { name: 'cast cards', exact: true }).getByText('Actor 1', { exact: true })).toBeVisible();
  await fullCredit.press('Enter');
  const creative = page.getByRole('region', { name: 'Directors and creators', exact: true });
  const actors = page.getByRole('group', { name: 'cast cards', exact: true });
  await expect(creative.locator('.person-card')).toHaveCount(3);
  await expect(creative.getByText('Director · Creator', { exact: true })).toBeVisible();
  await expect(actors.locator('.person-card')).toHaveCount(16);
  await expect(actors.locator('.director-person')).toHaveCount(0);
  await expect(actors.getByText('Actor 1', { exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Writers and crew' }).getByText('Writer', { exact: true })).toBeVisible();
  await expect.poll(() => creative.locator('.person-avatar img').count()).toBe(2);
  expect(profileRequests.sort()).toEqual(['77101', '77102', '77103']);
  const creativeBox = await creative.boundingBox();
  const actorsBox = await actors.boundingBox();
  expect(creativeBox.y + creativeBox.height).toBeLessThan(actorsBox.y);
  expect((await creative.locator('.person-card').first().boundingBox()).height).toBeLessThan(100);
  await fullCredit.press('Space');
  await expect(creative).not.toBeVisible();
  await expect(page.getByText('Writer', { exact: true })).not.toBeVisible();
  await page.getByRole('button', { name: 'Scroll cast right', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Scroll cast left', exact: true })).toBeEnabled();
  await expect(actors.getByText('Actor 16', { exact: true })).toBeVisible();
  await fullCredit.click();
  await expect(creative.getByText('Director · Creator', { exact: true })).toBeVisible();
  await expect(creative.locator('.person-avatar img')).toHaveCount(2);
  expect(profileRequests.sort()).toEqual(['77101', '77102', '77103']);
  await creative.getByRole('button', { name: 'Open biography for First Director', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Biography for Creative 77101' })).toBeVisible();
});

test('standard TV card keeps dates and episode counts together and opens from the card', async ({ page }) => {
  await page.goto('/library');
  await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
  const card = page.getByRole('link', { name: 'Open Harbor Signals' });
  const facts = card.locator('.unified-movie-title-block > span');
  await expect(facts).toContainText('2020');
  await expect(facts).toContainText('2 seas. · 4 eps.');
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

test('related TV posters stay compact with inline arrows and full titles in tooltips', async ({ page }) => {
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
    return { display: getComputedStyle(element).display, width: element.getBoundingClientRect().width, height: element.getBoundingClientRect().height,
      posterHeight: poster?.getBoundingClientRect().height, imageLoaded: Boolean(image?.naturalWidth),
      title: element.querySelector('strong')?.textContent };
  });
  expect(geometry.display).toBe('grid');
  expect(geometry.width).toBeGreaterThan(70);
  expect(geometry.width).toBeLessThan(100);
  expect(geometry.height).toBe(136);
  expect(Math.abs(geometry.height / geometry.width - 1.5)).toBeLessThan(.03);
  expect(geometry.imageLoaded).toBe(true);
  expect(geometry.title).toBeUndefined();
  const rightBox = await rail.getByRole('button', { name: 'Scroll related titles right', exact: true }).boundingBox();
  expect(Math.abs(rightBox.y + rightBox.height / 2 - (await tile.boundingBox()).y - (await tile.boundingBox()).height / 2)).toBeLessThan(1);
  await page.setViewportSize({ width: 1366, height: 768 });
  expect((await tile.boundingBox()).height).toBe(120);
  await tile.hover();
  await expect(page.getByRole('tooltip')).toContainText('Related Series 1');
  await expect(page.getByRole('tooltip')).toContainText('2024');
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
  await page.getByRole('tablist', { name: 'Discover tools' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await page.getByRole('textbox', { name: 'Search TV shows' }).fill('Dark Matter');
  await page.getByRole('button', { name: 'Search TV', exact: true }).click();
  await page.getByRole('link', { name: 'Open Dark Matter' }).click();

  const header = page.locator('.tv-series-header');
  await expect(header.locator('.tv-series-badges .unified-chip')).toContainText(['Sci-Fi & Fantasy', 'Drama', 'English', 'US']);
  const cast = page.getByRole('region', { name: 'Series cast' });
  await expect(cast.getByRole('group', { name: 'cast cards', exact: true }).locator('.person-card').first()).toContainText('Joel Edgerton');
  await expect(cast.getByRole('button', { name: 'Scroll cast right', exact: true })).toBeEnabled();
  expect(await cast.getByRole('group', { name: 'cast cards', exact: true }).evaluate(row => row.scrollWidth > row.clientWidth)).toBe(true);
  await expect(cast.getByRole('button', { name: 'Open biography for Joel Edgerton', exact: true })).toBeVisible();
  await expect(cast.getByRole('button', { name: 'Open filmography for Joel Edgerton', exact: true })).toBeVisible();
  await cast.getByRole('button', { name: 'Open biography for Joel Edgerton', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Biography for Joel Edgerton' })).toContainText('A test biography.');
  await expect(page.getByRole('dialog', { name: 'Biography for Joel Edgerton' })).toHaveClass(/cp-dialog/);
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
  await page.getByRole('region', { name: 'Series cast' }).getByRole('button', { name: 'Full Credit', exact: true }).click();
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
  await page.getByRole('tablist', { name: 'Discover tools' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
  await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await page.getByRole('textbox', { name: 'Search TV shows' }).fill('Dark Matter');
  await page.getByRole('button', { name: 'Search TV', exact: true }).click();
  await page.getByRole('link', { name: 'Open Dark Matter' }).click();
  const rail = page.getByRole('region', { name: 'More like this' });
  await expect(rail.getByRole('button', { name: 'Retry' }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Download season' })).toBeEnabled();
  await expect(page.getByRole('heading', { name: 'Dark Matter', exact: true })).toBeVisible();
});
