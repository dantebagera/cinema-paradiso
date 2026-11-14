import { test, expect } from '@playwright/test';

test.skip(process.env.CP_TV_E2E !== '1', 'Requires disposable TV fixture server');
test.use({ reducedMotion: 'reduce' });

async function openTV(page, surface) {
  await page.goto(surface === 'lists' ? '/movie-lists' : `/${surface}`);
  if (surface === 'discover') {
    const controls = page.getByRole('button', { name: 'Search, filters & selection', exact: true });
    if (await controls.getAttribute('aria-expanded') === 'false') await controls.click();
  }
  const tabs = page.getByRole('tablist', { name: surface === 'library' ? 'Library media' : surface === 'lists' ? 'Lists media' : 'Discover tools' });
  await tabs.getByRole(surface === 'lists' ? 'tab' : 'button', { name: 'TV Shows', exact: true }).click();
}

async function cardGeometry(card) {
  return card.evaluate(element => {
    const poster = element.querySelector('.unified-movie-poster').getBoundingClientRect();
    const bounds = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      emptyBelowPoster: bounds.bottom - poster.bottom - parseFloat(style.paddingBottom) - parseFloat(style.borderBottomWidth),
      horizontalOverflow: element.scrollWidth - element.clientWidth,
    };
  });
}

for (const width of [1366, 1920]) {
  for (const surface of ['library', 'discover', 'lists']) {
    test(`${surface} TV cards keep green offline metadata compact at ${width}px`, async ({ page, request }, testInfo) => {
      await page.setViewportSize({ width, height: 1080 });
      // Use the real backend coverage (two available of four released episodes).
      const series = await (await request.get('/api/tv/series/1')).json();
      expect(series.available_count).toBe(2);
      expect(series.offline_percent).toBe(50);
      await page.route('**/api/tv/lists?**', async route => {
        const payload = await (await route.fetch()).json();
        await route.fulfill({ json: { ...payload, items: [series], total: 1, total_pages: 1 } });
      });
      await openTV(page, surface);
      const card = page.getByRole('link', { name: 'Open Harbor Signals', exact: true });
      await expect(card).toBeVisible();
      const metadata = card.locator('.unified-movie-title-block > span');
      await expect(metadata).toContainText('2 seas. · 4 eps.');
      const offline = metadata.getByText('50% offline', { exact: true });
      await expect(offline).toHaveCSS('color', 'rgb(120, 242, 167)');
      await expect(card).not.toContainText(/\d+ \/ \d+ watched|eps\. offline|Downloads add this show/);
      await expect(card.locator('.unified-status-chip', { hasText: 'Ended' })).toHaveCSS('color', 'rgb(34, 197, 94)');
      expect((await cardGeometry(card)).emptyBelowPoster).toBeLessThanOrEqual(4);
      expect((await cardGeometry(card)).horizontalOverflow).toBeLessThanOrEqual(1);
      await page.screenshot({ path: testInfo.outputPath(`${surface}-${width}.png`) });
    });
  }
}

test('preview cards and detail omit the download explanation and zero offline label', async ({ page, request }) => {
  const preview = await (await request.get('/api/tv/preview/900002')).json();
  expect(preview.primary_action.reason).toBe('');
  await openTV(page, 'discover');
  const card = page.getByRole('link', { name: 'Open Open Water', exact: true });
  await expect(card).toBeVisible();
  await expect(card).not.toContainText(/offline|watched|Downloads add this show/);
  await card.click();
  const header = page.locator('.tv-series-header');
  await expect(header).not.toContainText('Downloads add this show');
  await expect(header.getByRole('button', { name: 'Add to library', exact: true })).toBeVisible();
  await expect(header.locator('.tv-series-progress')).toHaveCount(0);
});

for (const [status, color] of [['Returning Series', 'rgb(239, 68, 68)'], ['Ended', 'rgb(34, 197, 94)'], ['Planned', null]]) {
  test(`${status} tone is shared by standard and expanded TV views`, async ({ page }) => {
    await page.route('**/api/tv/catalog/search', async route => {
      const payload = await (await route.fetch()).json();
      await route.fulfill({ json: { ...payload, items: payload.items.map(series => ({ ...series, status, status_label: status })) } });
    });
    await page.route(/\/api\/tv\/series\/1$/, async route => {
      const series = await (await route.fetch()).json();
      await route.fulfill({ json: { ...series, status, status_label: status } });
    });
    await openTV(page, 'library');
    const card = page.getByRole('link', { name: 'Open Harbor Signals', exact: true });
    const badge = card.locator('.unified-status-chip', { hasText: status });
    if (color) await expect(badge).toHaveCSS('color', color);
    else await expect(badge).toHaveClass(/unified-status-neutral/);
    await card.click();
    const expandedBadge = page.locator('.tv-series-header .unified-status-chip', { hasText: status });
    if (color) await expect(expandedBadge).toHaveCSS('color', color);
    else await expect(expandedBadge).toHaveClass(/unified-status-neutral/);
  });
}

test('incomplete coverage keeps downloaded ownership visible without inventing a percentage', async ({ page }) => {
  await page.route('**/api/tv/catalog/search', async route => {
    const payload = await (await route.fetch()).json();
    await route.fulfill({ json: { ...payload, items: payload.items.map(series => ({ ...series,
      coverage_complete: false, listed_episode_count: 6, offline_percent: null,
      pending_review_count: 1, primary_action: { playable: false, reason: 'The next episode file is unavailable.' },
    })) } });
  });
  await page.route(/\/api\/tv\/series\/1$/, async route => {
    const series = await (await route.fetch()).json();
    await route.fulfill({ json: { ...series, coverage_complete: false, offline_percent: null, watched_percent: null } });
  });
  await openTV(page, 'library');
  const card = page.getByRole('link', { name: 'Open Harbor Signals', exact: true });
  await expect(card.locator('.unified-movie-title-block > span')).toContainText('6 eps. (est.)');
  await expect(card.getByText('Offline % unknown', { exact: true })).toHaveCSS('color', 'rgb(120, 242, 167)');
  await expect(card).toContainText('1 file need identity review');
  await expect(card).toContainText('The next episode file is unavailable.');
  await expect(card).not.toContainText('watched (');
  await card.click();
  await expect(page.locator('.tv-series-header .tv-series-progress')).toHaveText('2 / — eps. offline (—) · 0 / — watched (—)');
});

test('zero available episodes suppress a stale nonzero offline percentage', async ({ page }) => {
  await page.route('**/api/tv/catalog/search', async route => {
    const payload = await (await route.fetch()).json();
    await route.fulfill({ json: { ...payload, items: payload.items.map(series => ({ ...series, available_count: 0, offline_percent: 50 })) } });
  });
  await openTV(page, 'library');
  const metadata = page.getByRole('link', { name: 'Open Harbor Signals', exact: true }).locator('.unified-movie-title-block > span');
  await expect(metadata).not.toContainText('offline');
});

for (const width of [1366, 1920]) {
  test(`dense TV metadata does not stretch the standard card below its poster at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1080 });
    await page.route('**/api/tv/catalog/search', async route => {
      const payload = await (await route.fetch()).json();
      await route.fulfill({ json: { ...payload, items: payload.items.map(series => ({ ...series,
        title: 'Cyberpunk: Edgerunners — A Very Long Series Title',
        genres: ['Animation', 'Action & Adventure', 'Sci-Fi & Fantasy', 'Crime', 'Drama'],
        origin_country: ['JP', 'PL', 'US'], status: 'Returning Series', status_label: 'Returning Series',
      })) } });
    });
    await openTV(page, 'library');
    const card = page.getByRole('link', { name: 'Open Cyberpunk: Edgerunners — A Very Long Series Title', exact: true });
    await expect(card).toBeVisible();
    const geometry = await cardGeometry(card);
    expect(geometry.emptyBelowPoster).toBeLessThanOrEqual(4);
    expect(geometry.horizontalOverflow).toBeLessThanOrEqual(1);
    await page.screenshot({ path: testInfo.outputPath(`dense-${width}.png`) });
  });
}

for (const width of [1366, 1920]) {
  test(`expanded TV long text flows beneath the poster without a blank column at ${width}px`, async ({ page, request }, testInfo) => {
    await page.setViewportSize({ width, height: 1080 });
    await page.route('**/density-poster.svg', route => route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="300"><rect width="200" height="300" fill="#27384d"/><circle cx="100" cy="100" r="45" fill="#d4af37"/></svg>' }));
    await page.route(/\/api\/tv\/series\/1$/, async route => {
      const series = await (await route.fetch()).json();
      await route.fulfill({ json: { ...series, poster_url: '/density-poster.svg',
        overview: 'A coastal town follows a mysterious radio signal. '.repeat(80) } });
    });
    await openTV(page, 'library');
    const real = await (await request.get('/api/tv/series/1')).json();
    expect(real.offline_percent).toBe(50);
    await page.getByRole('link', { name: 'Open Harbor Signals', exact: true }).click();
    const header = page.locator('.tv-series-header');
    await expect(header.locator('.tv-series-progress')).toHaveText('2 / 4 eps. offline (50%) · 0 / 4 watched (0%)');
    const poster = header.locator(':scope > img');
    await expect(poster).toHaveCSS('object-fit', 'contain');
    await expect.poll(() => poster.evaluate(img => img.complete && img.naturalWidth > 0)).toBeTruthy();
    const geometry = await header.evaluate(element => {
      const poster = element.querySelector(':scope > img').getBoundingClientRect();
      const summary = element.querySelector('.tv-series-header-summary').getBoundingClientRect();
      const details = element.querySelector('.tv-series-header-details').getBoundingClientRect();
      return { gap: details.top - poster.bottom, startsBelowSummary: details.top >= summary.bottom,
        fullWidth: details.width > poster.width + summary.width, aspect: poster.height / poster.width };
    });
    expect(geometry.gap).toBeGreaterThanOrEqual(0);
    expect(geometry.gap).toBeLessThanOrEqual(28);
    expect(geometry.startsBelowSummary).toBe(true);
    expect(geometry.fullWidth).toBe(true);
    expect(geometry.aspect).toBeCloseTo(1.5, 2);
    await page.screenshot({ path: testInfo.outputPath(`expanded-${width}.png`), fullPage: true });
    await header.getByRole('button', { name: 'Back to TV Shows', exact: true }).click();
    await expect(page.getByRole('link', { name: 'Open Harbor Signals', exact: true })).toBeVisible();
  });
}
