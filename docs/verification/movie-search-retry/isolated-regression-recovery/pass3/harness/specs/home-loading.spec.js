import { expect, test } from './pass3-browser-fixture.cjs';

test.use({ viewport: { width: 1600, height: 1080 }, reducedMotion: 'reduce' });
const poster = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="176" height="264"><rect width="176" height="264" fill="#493d28"/></svg>');
const movie = id => ({ tmdb_id: String(id), title: `Movie ${id}`, year: '2099', release_date: '2099-12-01', poster_url: poster });
const rows = (start, count) => Array.from({ length: count }, (_, i) => movie(start + i));
const video = (id, title = `Feature ${id} Official Trailer (2026)`, source = 'alpha') => ({ video_id: String(id), title, source_id: source, source_name: source, thumbnail_url: poster, url: `https://www.youtube.com/watch?v=${id}`, published_at: '2026-10-18T10:00:00Z' });
const deferred = () => { let release; const promise = new Promise(resolve => { release = resolve; }); return { promise, release }; };
const trending = page => page.locator('.home-trending-track .upcoming-movie-card');
const upcoming = page => page.locator('.coming-soon-grid .upcoming-movie-card');
const trailers = page => page.locator('.home-trailer-grid .home-video-card');

async function fixture(page, options = {}) {
  const state = { trending: rows(1, 20), upcoming: [rows(101, 20)], items: [video('abcdefghijk')],
    counts: { trending: 0, upcoming: [], trailers: [], ownership: [] }, generation: 1, ...options };
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', route => new URL(route.request().url()).origin === new URL(test.info().project.use.baseURL).origin
    ? route.fallback() : route.abort());
  await page.route('**/api/**', async route => {
    const request = route.request(); const url = new URL(request.url()); const path = url.pathname;
    let json = {};
    if (path === '/api/tmdb/discover') {
      if (url.searchParams.get('list') === 'trending_week') {
        state.counts.trending++;
        await state.trendingGate?.promise;
        if (state.trendingError) return route.fulfill({ status: 503, json: { error: 'Trending failed' } });
        json = { results: state.trending };
      } else {
        const number = Number(url.searchParams.get('page'));
        state.counts.upcoming.push({ page: number, size: Number(url.searchParams.get('page_size')) });
        await state.upcomingGate?.promise; await state.pageGates?.[number]?.promise;
        if (state.failPage === number) return route.fulfill({ status: 503, json: { error: 'Upcoming failed' } });
        json = { results: state.upcoming[number - 1] || [], page: number, has_next: number < state.upcoming.length,
          provider_exhausted: number >= state.upcoming.length, ...state.pageMetadata };
      }
    } else if (path === '/api/library/check') {
      const scope = request.postDataJSON().movies;
      state.counts.ownership.push(scope);
      const generation = state.generation;
      const results = scope.map(query => state.owned?.(query) || { ...query, found: false });
      await (scope.some(query => Number(query.tmdb_id) < 100) ? state.trendingOwnershipGate?.promise : state.upcomingOwnershipGate?.promise);
      if (state.ownershipError) return route.fulfill({ status: 503, json: { error: 'Ownership failed' } });
      json = { results, catalog_generation: generation };
    } else if (path === '/api/home/trailers') {
      const cursor = url.searchParams.get('cursor') || '';
      state.counts.trailers.push(cursor);
      await (cursor ? state.appendGate?.promise : state.trailerGate?.promise);
      if (state.trailerError) return route.fulfill({ status: 503, json: { error: 'Trailer failed' } });
      json = { items: cursor ? state.moreItems || [] : state.items, sources: [{ id: 'alpha', name: 'Alpha' }, { id: 'beta', name: 'Beta' }],
        next_cursor: cursor ? '' : 'next', has_more: !cursor, stale: Boolean(state.stale), fallback: Boolean(state.stale) };
    } else if (path === '/api/user/lists') json = { lists: [] };
    else if (path === '/api/notifications') json = state.notificationsBroken ? {} : { items: [], unread: 0, total: 0, total_pages: 1 };
    else if (path.startsWith('/api/user/followed-releases')) json = { movies: [], curation_generation: 1 };
    else if (path === '/api/stats') json = { total_files: 1, unique_titles: 1 };
    else if (path === '/api/library/reconcile') json = { status: 'idle' };
    else if (path === '/api/tv/capabilities') json = { enabled: false };
    else if (path === '/api/power/status') { state.powerRequests = (state.powerRequests || 0) + 1; json = { active_downloads: state.powerRequests - 1, plan: {} }; }
    else if (path.includes('continue-watching')) json = { items: [] };
    else if (path.includes('filter-options')) json = { genres: [], languages: [], countries: [] };
    else if (path.includes('/discover/advanced')) json = { results: [], total_results: 0, total_pages: 1, page: 1 };
    else if (path.includes('/details')) json = { summary: 'Fresh details', cast: [], genres: [] };
    else if (path.includes('/awards/')) json = { counts: {} };
    else if (path === '/api/catalog/events') return route.fulfill({ contentType: 'text/event-stream', body: ': fixture\n\n' });
    return route.fulfill({ json });
  });
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.home-grid')).toBeVisible();
  return { state, errors };
}

async function awayAndBack(page) {
  await page.getByRole('button', { name: 'Discover', exact: true }).click();
  await expect(page).toHaveURL(/\/discover$/);
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
}
async function ready(page, count = 20) {
  await expect(trending(page)).toHaveCount(20);
  await expect(upcoming(page)).toHaveCount(count);
  await expect(page.locator('.home-poster-stack .skeleton-card')).toHaveCount(0);
}

test('Trending and trailers become usable while Upcoming response and its ownership are held', async ({ page }) => {
  const gate = deferred(); const ownership = deferred();
  const { state, errors } = await fixture(page, { upcomingGate: gate, upcomingOwnershipGate: ownership });
  await expect(trending(page)).toHaveCount(20);
  await expect(trailers(page)).toHaveCount(1);
  await expect(page.locator('.home-trending-track .skeleton-card')).toHaveCount(0);
  gate.release();
  await expect.poll(() => state.counts.ownership.length).toBe(2);
  await expect(page.locator('.coming-soon-grid .skeleton-card')).toHaveCount(7);
  await expect(trending(page).first()).toHaveAttribute('aria-label', /Movie 1/);
  ownership.release(); await ready(page); expect(errors).toEqual([]);
});

test('Upcoming finishing first waits for effective Trending and fills replacements without blocking Trending', async ({ page }) => {
  const gate = deferred(); const second = deferred();
  const { state } = await fixture(page, { trendingGate: gate, upcoming: [rows(1, 20), rows(101, 20)], pageGates: { 2: second } });
  await expect(trailers(page)).toHaveCount(1);
  await expect(page.locator('.coming-soon-grid .skeleton-card')).toHaveCount(7);
  gate.release();
  await expect(page.locator('.home-trending-track .skeleton-card')).toHaveCount(0);
  await expect.poll(() => state.counts.upcoming.length).toBe(2);
  second.release(); await ready(page);
  expect(state.counts.upcoming).toEqual([{ page: 1, size: 20 }, { page: 2, size: 20 }]);
  expect(state.counts.ownership.at(-1).map(item => item.tmdb_id)).toEqual(rows(101, 20).map(item => item.tmdb_id));
});

test('return and browser history retain cards and reuse all pending feed operations', async ({ page }) => {
  const { state, errors } = await fixture(page); await ready(page); await expect(trailers(page)).toHaveCount(1);
  state.trendingGate = deferred(); state.upcomingGate = deferred(); state.trailerGate = deferred();
  await awayAndBack(page);
  await expect.poll(() => state.counts.trending).toBe(2);
  await expect.poll(() => state.counts.trailers.length).toBe(2);
  await ready(page); await expect(trailers(page)).toHaveCount(1);
  await awayAndBack(page); await page.goBack(); await page.goForward();
  expect(state.counts.trending).toBe(2); expect(state.counts.upcoming).toHaveLength(2); expect(state.counts.trailers).toHaveLength(2);
  await expect(page.locator('.home-grid .skeleton-card')).toHaveCount(0);
  await page.screenshot({ path: test.info().outputPath('retained-refresh-desktop.png') });
  await expect(page.getByRole('button', { name: 'More videos', exact: true })).toBeDisabled();
  state.trendingGate.release(); state.upcomingGate.release(); state.trailerGate.release();
  await expect(page.getByRole('button', { name: 'More videos', exact: true })).toBeEnabled();
  expect(errors).toEqual([]);
});

test('initial active operations survive navigation and do not launch duplicate pages or checks', async ({ page }) => {
  const gate = deferred();
  const { state } = await fixture(page, { trendingGate: gate, upcomingGate: gate, trailerGate: gate });
  await expect.poll(() => state.counts.upcoming.length).toBe(1);
  await awayAndBack(page); await page.goBack(); await page.goForward();
  expect(state.counts.trending).toBe(1); expect(state.counts.upcoming).toHaveLength(1); expect(state.counts.trailers).toEqual(['']);
  gate.release(); await ready(page); await expect(trailers(page)).toHaveCount(1);
  expect(state.counts.ownership).toHaveLength(2);
});

for (const count of [0, 13, 20]) test(`Upcoming preserves resolved ${count} result state; no unnecessary top-up`, async ({ page }) => {
  const { state } = await fixture(page, { upcoming: [rows(101, count)], items: [] });
  await ready(page, count); await expect(page.getByText('No videos in this channel.')).toBeVisible();
  expect(state.counts.upcoming).toEqual([{ page: 1, size: 20 }]);
  state.upcomingGate = deferred(); state.trailerGate = deferred(); await awayAndBack(page);
  await expect.poll(() => state.counts.upcoming.length).toBe(2);
  await expect(page.locator('.coming-soon-grid .skeleton-card,.home-trailer-grid .skeleton-card')).toHaveCount(0);
  if (!count) await expect(page.getByText('No upcoming movies are available.')).toBeVisible();
  await expect(page.getByText('No videos in this channel.')).toBeVisible();
  state.upcomingGate.release(); state.trailerGate.release();
});

test('duplicates across three pages fill twenty, navigation joins the pending top-up', async ({ page }) => {
  const gate = deferred();
  const { state } = await fixture(page, { upcoming: [[movie(1), ...rows(101, 19)], [movie(101), movie(1)], [movie(120)]], pageGates: { 3: gate } });
  await expect.poll(() => state.counts.upcoming.length).toBe(3);
  await awayAndBack(page); expect(state.counts.upcoming).toHaveLength(3);
  gate.release(); await ready(page);
  await expect(page.locator('.coming-soon-grid .upcoming-movie-copy strong')).toHaveText(rows(101, 20).map(item => item.title));
  expect(state.counts.ownership.filter(scope => scope[0]?.tmdb_id === '101').every(scope => scope.length <= 20)).toBe(true);
});

test('top-up failure is an error, shared Retry fills twenty and does not block Trending', async ({ page }) => {
  const { state } = await fixture(page, { upcoming: [[movie(1), ...rows(101, 19)], [movie(120)]], failPage: 2 });
  await expect(page.getByText('Upcoming movies are temporarily unavailable.')).toBeVisible();
  await expect(page.locator('.home-trending-track .skeleton-card')).toHaveCount(0);
  state.failPage = 0;
  await page.locator('.coming-soon-panel').getByRole('button', { name: 'Retry', exact: true }).click();
  await ready(page);
  expect(state.counts.upcoming.map(item => item.page)).toEqual([1, 2, 1, 2]);
});

test('incomplete retryable pages are not reported as provider depletion', async ({ page }) => {
  await fixture(page, { upcoming: [rows(101, 13)], pageMetadata: { has_next: false, budget_exhausted: true, retryable: true } });
  await expect(page.getByText('Upcoming movies are temporarily unavailable.')).toBeVisible();
  await expect(page.locator('.coming-soon-panel').getByRole('button', { name: 'Retry' })).toBeVisible();
});

test('refresh errors retain cards while pending then expose settled errors and saved suggestions', async ({ page }) => {
  const { state } = await fixture(page); await ready(page);
  state.upcomingGate = deferred(); state.trailerGate = deferred();
  await awayAndBack(page); await ready(page); await expect(trailers(page)).toHaveCount(1);
  state.failPage = 1; state.trailerError = true;
  state.upcomingGate.release(); state.trailerGate.release();
  await expect(page.getByText('Upcoming movies are temporarily unavailable.')).toBeVisible();
  await expect(page.getByText('Trailers are temporarily unavailable.')).toBeVisible();
  await expect(page.locator('.home-trending-track .skeleton-card')).toHaveCount(0);
});

for (const empty of [false, true]) test(`Trending ${empty ? 'empty success' : 'failure'} uses saved suggestions without hiding Upcoming`, async ({ page }) => {
  await fixture(page, { trending: [], trendingError: !empty });
  await expect(page.getByRole('heading', { name: 'Movie suggestions' })).toBeVisible();
  await expect(page.locator('.coming-soon-grid .skeleton-card')).toHaveCount(0);
  await expect(upcoming(page)).toHaveCount(20);
});

test('More videos joins active append on return, deduplicates videos and advances cursor once', async ({ page }) => {
  const { state } = await fixture(page, { moreItems: [video('abcdefghijk'), video('zyxwvutsrqp')] });
  await expect(trailers(page)).toHaveCount(1); state.appendGate = deferred();
  await page.getByRole('button', { name: 'More videos', exact: true }).click();
  await expect.poll(() => state.counts.trailers.length).toBe(2);
  await awayAndBack(page);
  expect(state.counts.trailers).toEqual(['', 'next']);
  await expect(page.getByRole('button', { name: /Loading videos/ })).toBeDisabled();
  state.appendGate.release(); await expect(trailers(page)).toHaveCount(2);
  await expect(page.getByRole('button', { name: 'More videos', exact: true })).toHaveCount(0);
});

test('90 trailer groups, alternate versions, channel selection, scroll and observer membership survive a power-only update', async ({ page }) => {
  await page.addInitScript(() => {
    const Native = window.ResizeObserver;
    window.__railObservations = [];
    window.ResizeObserver = class extends Native {
      observe(node, options) { window.__railObservations.push({ node, action: 'observe' }); super.observe(node, options); }
      unobserve(node) { window.__railObservations.push({ node, action: 'unobserve' }); super.unobserve(node); }
      disconnect() { window.__railObservations.push({ action: 'disconnect' }); super.disconnect(); }
    };
    window.__homeRenders = 0;
    window.__REACT_DEVTOOLS_GLOBAL_HOOK__ = { supportsFiber: true, renderers: new Map(), inject(renderer) { this.renderers.set(1, renderer); return 1; },
      onCommitFiberRoot(_id, root) { function visit(fiber) { if (!fiber) return; if (fiber.memoizedProps?.onRetryHomeMovies && (fiber.flags & 1)) window.__homeRenders++; visit(fiber.child); visit(fiber.sibling); } visit(root.current); }, onCommitFiberUnmount() {} };
  });
  const { state, errors } = await fixture(page, { items: [...Array.from({ length: 90 }, (_, i) => video(`feature-${i}`, undefined, i % 2 ? 'beta' : 'alpha')), video('alternative', 'Feature feature-0 Teaser Trailer (2026)', 'beta')] });
  await ready(page); await expect(trailers(page)).toHaveCount(90);
  expect(await page.evaluate(() => window.__homeRenders)).toBeGreaterThan(0);
  const chooser = page.getByRole('button', { name: /Choose from 2 videos/ });
  await chooser.click(); await expect(page.locator('.home-trailer-versions button')).toHaveCount(3);
  await page.getByRole('button', { name: 'Close trailer versions' }).click();
  const rail = page.locator('.home-trailer-grid');
  await rail.evaluate(node => { window.__railScrollDone = new Promise(resolve => node.addEventListener('scrollend', resolve, { once: true })); });
  await page.getByRole('button', { name: 'Scroll New trailers right', exact: true }).click();
  await page.evaluate(() => window.__railScrollDone);
  expect(await rail.evaluate(node => node.scrollLeft)).toBeGreaterThan(0);
  await rail.evaluate(node => { window.__rail = node; window.__railObservations = []; window.__homeRenders = 0; window.__scroll = node.scrollLeft; });
  const powerCount = state.powerRequests;
  await page.getByRole('button', { name: 'Power options', exact: true }).click();
  await expect.poll(() => state.powerRequests, { timeout: 6500 }).toBeGreaterThan(powerCount);
  await expect(page.getByLabel('After current downloads finish')).toBeEnabled();
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  expect(await page.evaluate(() => window.__homeRenders)).toBe(0);
  expect(await page.evaluate(() => window.__railObservations.filter(entry => entry.node === window.__rail || entry.node?.parentElement === window.__rail || entry.action === 'disconnect').length)).toBe(0);
  expect(await rail.evaluate(node => node.scrollLeft)).toBe(await page.evaluate(() => window.__scroll));
  await expect(trailers(page)).toHaveCount(90);
  await page.getByRole('button', { name: 'Power options', exact: true }).click();
  await page.locator('.home-trailers-panel').screenshot({ path: test.info().outputPath('ninety-trailers-desktop.png') });
  await page.getByRole('button', { name: 'Beta', exact: true }).click();
  await expect(trailers(page)).toHaveCount(46);
  await expect.poll(() => rail.evaluate(node => node.scrollLeft)).toBe(0);
  await page.getByRole('button', { name: 'All', exact: true }).click();
  await expect(trailers(page)).toHaveCount(90);
  expect(await page.evaluate(() => window.__railObservations.some(entry => entry.action === 'unobserve'))).toBe(true);
  expect(await page.evaluate(() => window.__railObservations.some(entry => entry.action === 'observe'))).toBe(true);
  expect(await page.evaluate(() => window.__railObservations.some(entry => entry.action === 'disconnect'))).toBe(false);
  expect(errors).toEqual([]);
});

test('exhausted provider with cached logical pages still fills replacements', async ({ page }) => {
  const { state } = await fixture(page, { upcoming: [[movie(1), ...rows(101, 19)], [movie(120)]], pageMetadata: { provider_exhausted: true } });
  await ready(page);
  expect(state.counts.upcoming.map(item => item.page)).toEqual([1, 2]);
});

test('Upcoming ownership failure cannot erase accepted Trending ownership', async ({ page }) => {
  const gate = deferred();
  const { state } = await fixture(page, { upcomingGate: gate, owned: query => query.tmdb_id === '1' ? { ...query, found: true, path: 'fixture.mkv', library_item: { canonical_metadata: { accepted: true, title: 'Accepted title' } } } : null });
  await expect(page.locator('.home-trending-track .upcoming-movie-copy strong').first()).toHaveText('Accepted title');
  state.ownershipError = true; gate.release(); await ready(page);
  await expect(page.locator('.home-trending-track .upcoming-movie-copy strong').first()).toHaveText('Accepted title');
});

test('canonical ownership is ready before display; deletion during a pending check cannot resurrect the file', async ({ page }) => {
  const gate = deferred();
  const owned = query => query.tmdb_id === '1' ? { ...query, found: true, path: 'fixture-deleted.mkv', library_item: {
    path: 'fixture-deleted.mkv', canonical_metadata: { accepted: true, title: 'Accepted title', year: '2026' } } } : null;
  const { state } = await fixture(page, { trendingOwnershipGate: gate, owned });
  await expect.poll(() => state.counts.ownership.length).toBe(1);
  state.owned = () => null; state.generation = 2;
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('cp-library-changed', { detail: { deleted_paths: ['fixture-deleted.mkv'], catalog_generation: 2 } })));
  gate.release(); await ready(page);
  await page.locator('.home-trending-track').getByRole('button', { name: 'Inspect Movie 1, 2099', exact: true }).click();
  await expect(page.locator('.home-detail-card')).toContainText('Unreleased');
  await expect(page.locator('.home-detail-card').getByRole('button', { name: 'Play from HDD' })).toHaveCount(0);
});

test('successful canonical metadata and changed feed/detail callbacks remain current after memoization', async ({ page }) => {
  const { state } = await fixture(page, { owned: query => query.tmdb_id === '1' ? { ...query, found: true, path: 'fixture.mkv', library_item: { path: 'fixture.mkv', canonical_metadata: { accepted: true, title: 'Accepted title' } } } : null });
  await ready(page);
  await expect(page.locator('.home-trending-track .upcoming-movie-copy strong').first()).toHaveText('Accepted title');
  state.trending = rows(21, 20); state.upcoming = [[movie(1), ...rows(101, 19)]];
  await awayAndBack(page); await ready(page);
  await expect(page.locator('.home-trending-track .upcoming-movie-copy strong').first()).toHaveText('Movie 21');
  await page.locator('.home-trending-track').getByRole('button', { name: 'Inspect Movie 21, 2099', exact: true }).click();
  await expect(page.locator('.home-detail-card')).toContainText('Fresh details');
});

test('retained trailer source and scroll survive a base refresh; alternate version opens its exact video', async ({ page }) => {
  const { state } = await fixture(page, { items: [video('abcdefghijk', 'Feature One Official Trailer (2026)', 'alpha'),
    video('zyxwvutsrqp', 'Feature One Teaser Trailer (2026)', 'beta'),
    ...Array.from({ length: 12 }, (_, i) => video(`extra-${i}`, `Extra Feature ${i} Official Trailer (2026)`, 'beta'))] });
  await expect(trailers(page)).toHaveCount(13);
  await page.getByRole('button', { name: 'Choose from 2 videos for Feature One', exact: true }).click();
  await page.getByRole('dialog', { name: 'Feature One', exact: true }).getByRole('button', { name: 'Feature One Teaser Trailer (2026) beta' }).click();
  await expect(page.locator('.trailer-dialog iframe')).toHaveAttribute('src', /embed\/zyxwvutsrqp/);
  await page.keyboard.press('Escape');
  const beta = page.getByRole('group', { name: 'Trailer channel' }).getByRole('button', { name: 'Beta', exact: true });
  await beta.click();
  const rail = page.locator('.home-trailer-grid');
  await rail.evaluate(node => { window.__trailerScrollDone = new Promise(resolve => node.addEventListener('scrollend', resolve, { once: true })); });
  await page.getByRole('button', { name: 'Scroll New trailers right', exact: true }).click();
  await page.evaluate(() => window.__trailerScrollDone);
  const position = await rail.evaluate(node => node.scrollLeft);
  state.trailerGate = deferred(); await awayAndBack(page);
  await expect.poll(() => state.counts.trailers.length).toBe(2);
  await expect(beta).toHaveAttribute('aria-pressed', 'true');
  await expect(trailers(page)).toHaveCount(13);
  expect(await rail.evaluate(node => node.scrollLeft)).toBe(position);
  await expect(page.locator('.home-trailer-grid .skeleton-card')).toHaveCount(0);
  state.trailerGate.release();
  await expect(page.getByRole('button', { name: 'More videos', exact: true })).toBeEnabled();
});

test('Trending changes during an existing fill reproject retained raw candidates without restarting its pages', async ({ page }) => {
  const gate = deferred();
  const { state } = await fixture(page, { upcoming: [[movie(1), ...rows(101, 19)], [movie(120)]], pageGates: { 2: gate } });
  await expect.poll(() => state.counts.upcoming.length).toBe(2);
  state.trending = rows(21, 20); await awayAndBack(page);
  await expect(page.locator('.home-trending-track .upcoming-movie-copy strong').first()).toHaveText('Movie 21');
  gate.release(); await ready(page);
  await expect(page.locator('.coming-soon-grid .upcoming-movie-copy strong')).toHaveText(['Movie 1', ...rows(101, 19).map(item => item.title)]);
  expect(state.counts.upcoming.map(item => item.page)).toEqual([1, 2]);
});

test('all twenty Upcoming cards are reachable with existing rail arrows', async ({ page }) => {
  await fixture(page); await ready(page);
  const rail = page.locator('.coming-soon-grid');
  const right = page.getByRole('button', { name: 'Scroll Upcoming movies right', exact: true });
  for (let step = 0; step < 4 && await right.isEnabled(); step++) {
    await rail.evaluate(node => { window.__upcomingScrollDone = new Promise(resolve => node.addEventListener('scrollend', resolve, { once: true })); });
    await right.click(); await page.evaluate(() => window.__upcomingScrollDone);
  }
  await expect(right).toBeDisabled();
  const bounds = await rail.boundingBox(); const last = await upcoming(page).last().boundingBox();
  expect(last.x).toBeGreaterThanOrEqual(bounds.x - 1);
  expect(last.x + last.width).toBeLessThanOrEqual(bounds.x + bounds.width + 1);
});

test('actual App unmount ignores held feed completions and cleans mounted rail monitoring', async ({ page }) => {
  await page.addInitScript(() => {
    const Native = window.ResizeObserver;
    window.__mountedRailObservers = new Set(); window.__closedRailObservers = new Set();
    window.ResizeObserver = class extends Native {
      observe(node, options) { if (node.classList.contains('horizontal-card-rail-track')) window.__mountedRailObservers.add(this); super.observe(node, options); }
      disconnect() { if (window.__mountedRailObservers.has(this)) window.__closedRailObservers.add(this); super.disconnect(); }
    };
    const add = HTMLElement.prototype.addEventListener; const remove = HTMLElement.prototype.removeEventListener;
    window.__railScrollListeners = new Set();
    HTMLElement.prototype.addEventListener = function(type, listener, options) { if (type === 'scroll' && this.classList.contains('horizontal-card-rail-track')) window.__railScrollListeners.add(this); return add.call(this, type, listener, options); };
    HTMLElement.prototype.removeEventListener = function(type, listener, options) { if (type === 'scroll' && this.classList.contains('horizontal-card-rail-track')) window.__railScrollListeners.delete(this); return remove.call(this, type, listener, options); };
  });
  const gate = deferred();
  const { state } = await fixture(page, { trendingGate: gate, upcomingGate: gate, trailerGate: gate });
  await expect.poll(() => page.evaluate(() => window.__mountedRailObservers.size)).toBe(3);
  // A malformed test-only sibling response drives the real error boundary and
  // unmounts ArchiveApp, rather than merely hiding Home through navigation.
  state.notificationsBroken = true;
  await page.getByRole('button', { name: 'Notifications, 0 unread', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Cinema Paradiso hit a display error.');
  const responses = Promise.all([
    page.waitForResponse(response => response.url().includes('list=trending_week')),
    page.waitForResponse(response => response.url().includes('list=upcoming')),
    page.waitForResponse(response => response.url().endsWith('/api/home/trailers'))
  ]);
  gate.release(); await responses;
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  expect(state.counts.ownership).toEqual([]);
  await expect(page.locator('.home-grid')).toHaveCount(0);
  expect(await page.evaluate(() => window.__closedRailObservers.size)).toBe(3);
  expect(await page.evaluate(() => window.__railScrollListeners.size)).toBe(0);
});
