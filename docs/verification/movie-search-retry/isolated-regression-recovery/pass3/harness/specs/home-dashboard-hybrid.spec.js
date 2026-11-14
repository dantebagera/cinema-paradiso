import { expect, test } from './pass3-browser-fixture.cjs';

test.use({ launchOptions: { ignoreDefaultArgs: ['--hide-scrollbars'] } });

const poster = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="156" height="234"><rect width="156" height="234" fill="#28221a"/><text x="20" y="120" fill="#d4af37">Cinema Paradiso</text></svg>');
const follows = count => Array.from({ length: count }, (_, i) => ({ tmdb_id: String(9900 + i), title: `Follow ${i + 1}`, year: '2026', poster_url: poster, status: i < 4 ? 'available' : 'watching', release_date: i > 7 ? '2099-01-01' : '2020-01-01', followed_at: 1000 - i }));
const stats = { total_files: 1284, unique_titles: 1016, low_quality_count: 12, duplicate_groups: 3, extra_copies: 5, unmatched_count: 8, identity_review_count: 2, identity_review_recommended: 1 };
const videos = Array.from({ length: 9 }, (_, i) => ({ video_id: `hybrid-${i}`, title: `Feature ${i} Official Trailer (2026)`, source_id: i % 2 ? 'beta' : 'alpha', source_name: i % 2 ? 'Beta' : 'Alpha', thumbnail_url: poster, url: `https://www.youtube.com/watch?v=hybrid-${i}`, published_at: '2026-10-18T10:00:00Z' }));

async function openHome(page, options = {}) {
  const state = { follows: follows(options.count ?? 12), stats, statsMode: 'ok', videos: [...videos, { ...videos[0], video_id: 'alternate', title: 'Feature 0 Teaser Trailer (2026)', source_id: 'beta', source_name: 'Beta' }], ...options };
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/stats', async route => { await state.statsGate; return state.statsMode === 'error' ? route.fulfill({ status: 503, json: { error: 'Stats fixture unavailable' } }) : route.fulfill({ json: state.stats }); });
  await page.route('**/api/user/followed-releases**', route => route.fulfill({ json: { movies: state.follows, newly_available: [], removed_owned: [], curation_generation: 1 } }));
  await page.route('**/api/player/continue-watching**', route => route.fulfill({ json: { items: Array.from({ length: state.history ?? 16 }, (_, i) => ({ path_key: `hybrid-${i}`, title: `Resume ${i + 1}`, poster_url: poster, progress: .4, remaining_seconds: 300 })) } }));
  await page.route('**/api/tv/continue-watching**', route => route.fulfill({ json: { items: state.tvItems || [] } }));
  await page.route('**/api/home/trailers**', async route => { await state.videoGate; return state.videoMode === 'error' ? route.fulfill({ status: 503, json: { error: 'Trailer fixture unavailable' } }) : route.fulfill({ json: { items: state.videos, sources: [{ id: 'alpha', name: 'Alpha' }, { id: 'beta', name: 'Beta' }], has_more: true, next_cursor: 'more', stale: state.stale ?? false } }); });
  await page.route('**/api/tmdb/discover**', route => {
    const upcoming = new URL(route.request().url()).searchParams.get('list') === 'upcoming';
    return route.fulfill({ json: { results: Array.from({ length: 12 }, (_, i) => ({ tmdb_id: String((upcoming ? 8500 : 8000) + i), title: `${upcoming ? 'Upcoming' : 'Trending'} poster ${i + 1}`, poster_url: poster, year: '2099', release_date: '2099-12-01' })), page: 1, total_pages: 1, total_results: 12 } });
  });
  await page.route('**/api/tmdb/details**', route => route.fulfill({ json: { title: 'Canonical fixture', rating: 8, tmdb_vote_count: 1234, cast: [], directors: [], genres: [] } }));
  await page.route('**/api/library/check', route => route.fulfill({ json: { results: [], catalog_generation: 1 } }));
  await page.goto('/');
  await expect(page.locator('.release-panel .release-item')).toHaveCount(state.follows.length);
  if (state.waitForVideos !== false) await expect(page.locator('.home-video-card')).toHaveCount(9);
  return { state, errors };
}

const closeTo = (actual, expected, tolerance = 1) => expect(Math.abs(actual - expected)).toBeLessThanOrEqual(tolerance);

for (const width of [1280, 1366, 1440, 1600, 1920]) {
  test(`hybrid desktop geometry and reachable follows at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: ({ 1280: 720, 1366: 900, 1440: 900, 1600: 1000, 1920: 1080 })[width] });
    const { errors } = await openHome(page);
    const measure = () => page.evaluate(() => {
      const rect = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height, right: r.right, bottom: r.bottom }; };
      const list = document.querySelector('.release-list');
      const bounds = list.getBoundingClientRect();
      return { root: rect('.home-grid'), hero: rect('.hero-panel'), health: rect('.health-panel'), follow: rect('.release-panel'), list: rect('.release-list'), row: rect('.release-item'), trailers: rect('.home-trailers-panel'), resume: rect('.continue-watching-panel'), trending: rect('.movie-rail'), upcoming: rect('.coming-soon-panel'), poster: rect('.continue-movie-poster'), progress: rect('.continue-movie-progress'), visible: [...list.children].filter(el => { const r = el.getBoundingClientRect(); return r.top >= bounds.top - 1 && r.bottom <= bounds.bottom + 1; }).length, overflow: document.documentElement.scrollWidth > innerWidth, heroClipped: document.querySelector('.hero-copy').getBoundingClientRect().bottom > document.querySelector('.hero-panel').getBoundingClientRect().bottom, columns: getComputedStyle(document.querySelector('.health-cards')).gridTemplateColumns.split(' ').length };
    });
    const m = await measure();
    closeTo(m.hero.height, 156); closeTo(m.follow.height, 287.2); closeTo(m.list.height, 190); closeTo(m.row.height, 58);
    closeTo(m.poster.width, 156); closeTo(m.poster.height, 234); closeTo(m.progress.height, 4);
    expect(m.visible).toBe(3); expect(m.overflow).toBe(false); expect(m.heroClipped).toBe(false); expect(m.columns).toBe(5);
    if (width < 1440) expect(m.follow.y).toBeGreaterThanOrEqual(m.health.bottom + 17);
    else closeTo(m.follow.y, m.health.y);
    for (const section of [m.trailers, m.resume, m.trending, m.upcoming]) { closeTo(section.x, m.root.x); closeTo(section.width, m.root.width); }
    expect(m.trailers.y).toBeGreaterThan(m.follow.bottom); expect(m.resume.y).toBeGreaterThan(m.trailers.bottom); expect(m.trending.y).toBeGreaterThan(m.resume.bottom); closeTo(m.upcoming.y - m.trending.bottom, 12);
    await expect(page.locator('.home-grid > *').evaluateAll(elements => elements.map(el => el.className))).resolves.toEqual(['hero-panel', 'home-status-grid', 'home-trailers-panel', 'continue-watching-panel', 'home-poster-stack']);
    const list = page.locator('.release-list');
    await list.locator('.release-item').last().focus();
    await expect(list.locator('.release-item').last()).toBeInViewport();
    await page.locator('.release-status-filter').selectOption('awaiting');
    await expect(page.locator('.release-item')).toHaveCount(4);
    await expect.poll(() => list.evaluate(el => el.scrollTop)).toBe(0);
    closeTo((await list.boundingBox()).height, 190);
    await page.locator('.release-status-filter').selectOption('all');
    await list.screenshot({ path: test.info().outputPath(`following-${width}.png`) });
    await page.locator('.workspace').evaluate(el => el.scrollTo(0, 0));
    await page.screenshot({ path: test.info().outputPath(`dashboard-${width}.png`), fullPage: true });
    if (width >= 1600) {
      await page.getByRole('button', { name: 'Collapse sidebar', exact: true }).click();
      const collapsed = await measure(); closeTo(collapsed.list.height, 190); expect(collapsed.overflow).toBe(false);
      await page.screenshot({ path: test.info().outputPath(`dashboard-collapsed-${width}.png`), fullPage: true });
    }
    expect(errors).toEqual([]);
  });
}

for (const count of [0, 1, 3]) test(`Following keeps its three-row viewport for ${count} follows and no history`, async ({ page }) => {
  await openHome(page, { count, history: 0 });
  await expect(page.locator('.continue-watching-panel')).toHaveCount(0);
  closeTo((await page.locator('.release-list').boundingBox()).height, 190);
  await expect(page.locator('.release-panel').getByRole('button', { name: 'View all', exact: true })).toHaveCount(0);
  await expect(page.locator('.coming-soon-panel').getByRole('button', { name: 'View all', exact: true })).toBeVisible();
});

for (const width of [1280, 1600, 1920]) test(`Following details span Home without resizing status panels at ${width}`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1080 });
  const movies = follows(12); movies[0].title = 'A very long followed title '.repeat(20);
  const { errors } = await openHome(page, { follows: movies });
  const health = page.locator('.health-panel');
  const release = page.locator('.release-panel');
  const before = { health: await health.boundingBox(), release: await release.boundingBox() };
  await page.locator('.release-filter-count').evaluate(el => el.textContent = '9999');
  expect(await page.locator('.release-panel .section-heading').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  expect(await page.locator('.release-item strong').first().evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true);
  await page.locator('.release-item').first().click();
  const details = page.locator('.home-inline-details');
  await expect(details).toBeVisible();
  const root = await page.locator('.home-grid').boundingBox();
  const card = await details.boundingBox();
  closeTo(card.x, root.x); closeTo(card.width, root.width);
  for (const [name, panel] of [['health', health], ['release', release]]) {
    const current = await panel.boundingBox();
    closeTo(current.width, before[name].width); closeTo(current.height, before[name].height);
    expect(card.y).toBeGreaterThanOrEqual(current.y + current.height);
  }
  closeTo((await page.locator('.release-list').boundingBox()).height, 190);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  await page.locator('.home-status-grid').screenshot({ path: test.info().outputPath(`following-expanded-${width}.png`) });
  expect(errors).toEqual([]);
});

test('Following keeps shared details actions, repeat-click close and scroll/focus recovery', async ({ page }) => {
  await openHome(page);
  await page.route('**/api/tmdb/details**', route => route.fulfill({ json: {
    summary: 'Following shared details fixture.', cast: [{ id: 1, name: 'Fixture actor' }], directors: [], genres: []
  } }));
  const row = page.locator('.release-item').first();
  const workspace = page.locator('.workspace');
  const details = page.locator('.home-inline-details');
  for (const closeWithRow of [true, false]) {
    await row.focus();
    const before = await workspace.evaluate(el => el.scrollTop);
    await row.click();
    await expect(details).toContainText('Following shared details fixture.');
    await expect(details).toContainText('Fixture actor');
    await expect(details.getByRole('button', { name: 'Find torrent', exact: true })).toBeVisible();
    await expect(details.getByRole('button', { name: 'Following', exact: true })).toBeVisible();
    if (closeWithRow) await row.click();
    else await details.getByRole('button', { name: 'Close movie details', exact: true }).click();
    await expect(details).toHaveCount(0);
    await expect(row).toBeFocused();
    await expect.poll(() => workspace.evaluate(el => el.scrollTop)).toBe(before);
  }
});

test('Following details stay full width while loading and after a details error', async ({ page }) => {
  await openHome(page);
  let releaseDetails;
  const gate = new Promise(resolve => { releaseDetails = resolve; });
  await page.route('**/api/tmdb/details**', async route => {
    await gate;
    await route.fulfill({ status: 503, json: { error: 'Following details fixture unavailable' } });
  });
  await page.locator('.release-item').first().click();
  const details = page.locator('.home-inline-details');
  const assertFullWidth = async () => {
    const root = await page.locator('.home-grid').boundingBox();
    const card = await details.boundingBox();
    closeTo(card.x, root.x); closeTo(card.width, root.width);
  };
  await expect(details).toContainText('Loading cast…');
  await assertFullWidth();
  releaseDetails();
  await expect(details.getByRole('status')).toContainText('Details could not be refreshed:');
  await expect(details.getByRole('heading', { name: 'Follow 1', exact: true })).toBeVisible();
  await expect(details.getByRole('button', { name: 'Find torrent', exact: true })).toBeVisible();
  await assertFullWidth();
  await details.getByRole('button', { name: 'Close movie details', exact: true }).click();
  await expect(details).toHaveCount(0);
});

for (const width of [1600, 1920]) test(`old trailer geometry and current source grouping at ${width}`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1080 });
  await openHome(page);
  const track = page.locator('.home-trailer-grid');
  const dimensions = await track.evaluate(el => ({ width: el.clientWidth, card: el.firstElementChild.getBoundingClientRect().width, gap: parseFloat(getComputedStyle(el).gap) }));
  const columns = width === 1600 ? 4 : 5;
  closeTo(dimensions.card * columns + dimensions.gap * (columns - 1), dimensions.width);
  const thumbnail = await track.locator('.home-video-thumbnail').first().boundingBox(); closeTo(thumbnail.width / thumbnail.height, 16 / 9, .01);
  await expect(page.locator('.home-trailers-panel select')).toHaveCount(0);
  const sources = page.getByRole('group', { name: 'Trailer channel', exact: true });
  await expect(sources.getByRole('button')).toHaveText(['All', 'Alpha', 'Beta']);
  const versions = page.getByRole('button', { name: 'Choose from 2 videos for Feature 0' });
  await versions.click();
  await expect(page.getByRole('dialog', { name: 'Feature 0', exact: true })).toContainText('Feature 0 Teaser Trailer (2026)');
  await page.keyboard.press('Escape'); await expect(versions).toBeFocused();
  await sources.getByRole('button', { name: 'Beta', exact: true }).click();
  await expect(track.locator('.home-video-card')).toHaveCount(5);
  await expect(sources.getByRole('button', { name: 'Beta', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await sources.getByRole('button', { name: 'All', exact: true }).click();
  await expect(track.locator('.home-video-card')).toHaveCount(9);
  const more = page.locator('.home-load-trailers');
  const arrow = page.getByRole('button', { name: 'Scroll New trailers right' });
  closeTo((await more.boundingBox()).y, (await arrow.boundingBox()).y, 2);
  await arrow.click(); await expect.poll(() => track.evaluate(el => el.scrollLeft)).toBeGreaterThan(100);
});

test('Continue Watching paints the old native scrollbar at idle, scrolls natively and keeps other rails hidden', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openHome(page);
  const track = page.locator('.continue-watching-viewport');
  await track.scrollIntoViewIfNeeded();
  const paint = () => track.evaluate(el => ({ color: getComputedStyle(el).scrollbarColor, width: getComputedStyle(el).scrollbarWidth }));
  expect(await paint()).toEqual({ color: 'rgba(212, 175, 55, 0.4) rgba(0, 0, 0, 0)', width: 'thin' });
  await track.screenshot({ path: test.info().outputPath('native-idle.png') });
  await page.getByRole('button', { name: 'Scroll Continue Watching right', exact: true }).click();
  await expect.poll(() => track.evaluate(el => el.scrollLeft)).toBeGreaterThan(100);
  expect(await paint()).toEqual({ color: 'rgba(212, 175, 55, 0.4) rgba(0, 0, 0, 0)', width: 'thin' });
  // Use the real native thin scrollbar thumb, rather than setting scrollLeft.
  await track.evaluate(el => el.scrollTo(0, 0));
  // Clicking the header arrow can bring that button into view while leaving
  // the scrollbar below the viewport; reveal the actual drag target again.
  await track.evaluate(el => el.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' }));
  const box = await track.boundingBox();
  const native = await track.evaluate(el => ({ client: el.clientWidth, scroll: el.scrollWidth, height: el.offsetHeight - el.clientHeight }));
  expect(native.height).toBeGreaterThan(0);
  const thumbCenter = box.x + native.client * native.client / native.scroll / 2;
  const thumbY = box.y + box.height - native.height / 2;
  expect(thumbY).toBeGreaterThanOrEqual(0);
  expect(thumbY).toBeLessThan(page.viewportSize().height);
  await page.mouse.move(thumbCenter, thumbY);
  await page.mouse.down(); await page.mouse.move(thumbCenter + 150, thumbY, { steps: 10 }); await page.mouse.up();
  await expect.poll(() => track.evaluate(el => el.scrollLeft)).toBeGreaterThan(50);
  await track.locator('.continue-movie-card').last().getByRole('button').first().focus();
  await expect(track.locator('.continue-movie-card').last()).toBeInViewport();
  await track.screenshot({ path: test.info().outputPath('native-scrolled.png') });
  for (const selector of ['.home-trending-track', '.coming-soon-grid', '.home-trailer-grid']) await expect(page.locator(selector)).toHaveCSS('scrollbar-width', 'none');
  closeTo((await track.locator('.continue-movie-menu summary').first().boundingBox()).width, 30);
});

test('health cards retain current counts, stale recovery and truthful missing/empty states', async ({ page }) => {
  const { state } = await openHome(page, { statsMode: 'error' });
  const health = page.getByRole('region', { name: 'Library health', exact: true });
  await expect(health).toContainText('Library status is unavailable'); await expect(health.locator('.health-card')).toHaveCount(0);
  state.statsMode = 'ok'; await health.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(health.locator('.health-card strong')).toHaveText(['1,284', '12', '3', '8', '2']);
  await expect(health.locator('.health-card span')).toHaveText(['Files', 'Low quality', 'Duplicates', 'Unmatched', 'Identity review']);
  await expect(health.locator('.health-card small')).toHaveText(['1,016 unique titles', 'below 1080p', '5 extra copies', 'files without accepted metadata', '1 recommended corrections']);
  state.statsMode = 'error'; await page.getByRole('button', { name: 'Library', exact: true }).click(); await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(health).toContainText('Showing last-known library status.'); await expect(health.locator('.health-card')).toHaveCount(5);
  state.statsMode = 'ok'; state.stats = { total_files: 0, unique_titles: 0 }; await health.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(health).toContainText('Your local library is empty'); await expect(health.locator('.health-card')).toHaveCount(0);
});

test('health loading preserves cached counts and high-count detail text stays readable', async ({ page }) => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const { state } = await openHome(page, { statsGate: gate });
  const health = page.locator('.health-panel');
  await expect(health).toContainText('Loading library status');
  await expect(health.locator('.health-card')).toHaveCount(0);
  release(); await expect(health.locator('.health-card')).toHaveCount(5);
  state.statsGate = new Promise(resolve => { release = resolve; });
  await page.getByRole('button', { name: 'Library', exact: true }).click(); await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(health).toContainText('Refreshing'); await expect(health.locator('.health-card strong').first()).toHaveText('1,284');
  state.stats = { ...stats, total_files: 999999999, identity_review_recommended: 123456789 }; release();
  await expect(health.locator('.health-card strong').first()).toHaveText('999,999,999');
  expect(await health.locator('.health-card').evaluateAll(cards => cards.every(el => el.scrollWidth <= el.clientWidth && [...el.children].every(child => child.getBoundingClientRect().bottom <= el.getBoundingClientRect().bottom)))).toBe(true);
  closeTo((await page.locator('.release-list').boundingBox()).height, 190);
  await health.screenshot({ path: test.info().outputPath('health-large-counts.png') });
});

test('health issue cards keep their cleanup destinations', async ({ page }) => {
  await openHome(page);
  for (const [label, tab] of [['Low quality', 'upgrade'], ['Duplicates', 'Storage'], ['Unmatched', 'Identity'], ['Identity review', 'Identity']]) {
    await page.locator('.health-card-action').filter({ hasText: label }).click();
    await expect.poll(() => new URL(page.url()).pathname).toBe(tab === 'upgrade' ? '/library' : '/cleanup');
    if (tab === 'upgrade') {
      const toggle = page.getByRole('button', { name: 'Search, filters & selection', exact: true });
      if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click();
      await expect(page.getByLabel('Library resolution filter')).toHaveValue('upgrade');
    } else await expect(page.getByRole('tab', { name: tab, exact: true })).toHaveAttribute('aria-selected', 'true');
    await page.getByRole('button', { name: 'Home', exact: true }).click();
  }
});

test('trailer loading, retry, stale data and More videos retain their lifecycle', async ({ page }) => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const { state } = await openHome(page, { videoGate: gate, waitForVideos: false });
  const panel = page.locator('.home-trailers-panel');
  await expect(panel.locator('.skeleton-card')).toHaveCount(4);
  state.videoMode = 'error'; release();
  await expect(panel).toContainText('Trailers are temporarily unavailable.');
  state.videoMode = 'ok'; state.stale = true;
  await panel.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(panel.locator('.home-video-card')).toHaveCount(9);
  await expect(panel).toContainText('Showing the last successfully refreshed trailers.');
  state.videoGate = new Promise(resolve => { release = resolve; });
  await panel.getByRole('button', { name: 'More videos', exact: true }).click();
  await expect(panel.getByRole('button', { name: 'Loading videos', exact: false })).toBeDisabled();
  state.videos.push({ ...videos[1], video_id: 'hybrid-new', title: 'Another Feature Official Trailer (2026)' }); release();
  await expect(panel.locator('.home-video-card')).toHaveCount(10);
  await expect(panel.getByRole('button', { name: 'More videos', exact: true })).toBeEnabled();
});

test('trailer version chooser closes on channel change and navigation; a late feed cannot reopen it', async ({ page }) => {
  const { state } = await openHome(page);
  const chooser = () => page.getByRole('button', { name: 'Choose from 2 videos for Feature 0', exact: true });
  await chooser().click();
  await page.getByRole('group', { name: 'Trailer channel', exact: true }).getByRole('button', { name: 'Beta', exact: true }).dispatchEvent('click');
  await expect(page.locator('.home-trailer-versions')).toHaveCount(0);
  await page.getByRole('group', { name: 'Trailer channel', exact: true }).getByRole('button', { name: 'All', exact: true }).click();
  let release;
  state.videoGate = new Promise(resolve => { release = resolve; });
  await page.getByRole('button', { name: 'More videos', exact: true }).click();
  await chooser().click();
  await page.getByRole('button', { name: 'Library', exact: true }).dispatchEvent('click');
  await expect(page.locator('.home-trailer-versions')).toHaveCount(0);
  release(); await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(page.locator('.home-trailer-versions')).toHaveCount(0);
});

test('Trending and Coming soon retain per-section inline details, repeated selection and history navigation', async ({ page }) => {
  await openHome(page);
  await page.locator('.release-item').first().click();
  await expect(page.locator('.home-status-grid .home-inline-details')).toBeVisible();
  const trending = page.locator('.home-trending-track .upcoming-movie-card').first();
  for (let i = 0; i < 2; i++) {
    await trending.click(); await expect(page.locator('.movie-rail .home-inline-details')).toBeVisible();
    await expect(page.locator('.home-inline-details')).toHaveCount(1);
    await trending.click(); await expect(page.locator('.home-inline-details')).toHaveCount(0); await expect(trending).toBeFocused();
  }
  await trending.click();
  await page.locator('.coming-soon-grid .upcoming-movie-card').nth(1).click();
  await expect(page.locator('.coming-soon-panel .home-inline-details')).toBeVisible();
  await expect(page.locator('.movie-rail .home-inline-details')).toHaveCount(0);
  await expect(page.locator('.home-inline-details')).toHaveCount(1);
  await page.getByRole('button', { name: 'Close movie details', exact: true }).click();
  await page.locator('.continue-watching-panel').screenshot({ path: test.info().outputPath('continue-full-width.png') });
  await page.locator('.home-poster-stack').screenshot({ path: test.info().outputPath('current-poster-stack.png') });
  await page.getByRole('button', { name: 'Library', exact: true }).click();
  await page.goBack(); await expect(page.locator('.home-grid')).toBeVisible(); await expect(page.locator('.home-inline-details')).toHaveCount(0);
  await page.goForward(); await expect.poll(() => new URL(page.url()).pathname).toBe('/library');
});

test('Continue Watching preserves TV resume restart remove and missing-episode presentation', async ({ page }) => {
  await page.route('**/api/tv/capabilities', route => route.fulfill({ json: { enabled: true } }));
  const plays = [], removals = [];
  await page.route('**/api/tv/episodes/*/play', route => { plays.push({ url: route.request().url(), body: route.request().postDataJSON() }); return route.fulfill({ json: { ok: true } }); });
  await page.route('**/api/tv/series/*/hide-progress', route => { removals.push(route.request().url()); return route.fulfill({ json: { ok: true } }); });
  const tvItems = [true, false].map((playable, i) => ({ id: String(21 + i), media_type: 'tv', path_key: `tv-${i}`, title: `Series ${i + 1}`, poster_url: poster, progress: .3, primary_action: { label: 'Resume', playable, target: { episode_id: '101', code: 'S01E02', title: 'Second episode' } } }));
  await openHome(page, { history: 0, tvItems });
  const rail = page.getByRole('region', { name: 'Continue Watching movies and TV shows', exact: true });
  await expect(rail.locator('.continue-movie-card')).toHaveCount(2);
  const card = rail.locator('.continue-movie-card').first();
  await card.getByRole('button', { name: 'Play Series 1', exact: true }).click();
  await expect.poll(() => plays.length).toBe(1); expect(plays[0].body).toEqual({ restart: false }); expect(plays[0].url).toContain('/api/tv/episodes/101/play');
  await card.locator('summary').click(); await card.getByRole('button', { name: 'Restart', exact: true }).click();
  await expect.poll(() => plays.length).toBe(2); expect(plays[1].body).toEqual({ restart: true });
  const missing = rail.locator('.continue-movie-card').nth(1);
  await expect(missing).toContainText('Resume · S01E02 · Second episode · Missing locally');
  await missing.getByRole('button', { name: 'Play Series 2', exact: true }).click();
  await expect.poll(() => new URL(page.url()).pathname).toBe('/tv/series/22'); expect(plays).toHaveLength(2);
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await card.locator('summary').click(); await expect(card.getByRole('button', { name: 'View card', exact: true })).toHaveCount(0);
  await card.getByRole('button', { name: 'Remove', exact: true }).click();
  await expect.poll(() => removals.length).toBe(1); expect(removals[0]).toContain('/api/tv/series/21/hide-progress');
});

test('Continue Watching menus remain completely visible and clickable inside the narrow cards', async ({ page }) => {
  await openHome(page);
  const track = page.locator('.continue-watching-viewport');
  for (const index of [0, 15]) {
    const card = track.locator('.continue-movie-card').nth(index);
    await card.locator('summary').click();
    await expect(card).toHaveCSS('background-image', 'none');
    await expect(card).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
    const menu = card.locator('.continue-movie-menu > div');
    const bounds = await menu.boundingBox(), rail = await track.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(rail.x);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(rail.x + rail.width);
    expect(await menu.evaluate(el => { const r = el.getBoundingClientRect(); return el.contains(document.elementFromPoint(r.left + 3, r.top + 10)); })).toBe(true);
    await menu.screenshot({ path: test.info().outputPath(`complete-menu-${index}.png`) });
    await card.locator('summary').click();
  }
});
