import { test, expect } from '@playwright/test';

async function openControls(page) {
  const toggle = page.getByRole('button', { name: 'Search, filters & selection', exact: true });
  await expect(toggle).toBeVisible();
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click();
}

async function measureLibraryActions(page, label) {
  return page.getByRole('group', { name: label, exact: true }).evaluate(group => {
    // Read the shared header synchronously so layout cannot move between samples.
    const rescan = group.parentElement.querySelector('.library-rescan-button');
    if (!rescan) throw new Error('Library refresh control is missing');
    const rectangle = element => {
      const { x, y, width, height } = element.getBoundingClientRect();
      return { x, y, width, height };
    };
    return { view: rectangle(group), rescan: rectangle(rescan) };
  });
}

async function measureDiscoverControls(page, tv = false) {
  if (tv) {
    // The zero-height sizing probe still contributes a grid gap while loading.
    await expect(page.locator('.tv-discover-workspace .tv-series-card').first()).toBeVisible();
    await expect(page.locator('.tv-discover-workspace .library-grid-metrics-probe')).toHaveCount(0);
  }
  await page.evaluate(async () => { await document.fonts.ready; });
  return page.locator(tv ? '.tv-discover-workspace' : '.discover-workspace:not(.tv-discover-workspace)').evaluate(section => {
    // Compare both modes at the same scroll origin, in one layout sample.
    const workspace = section.closest('.workspace');
    if (workspace) workspace.scrollTop = 0;
    const rectangle = selector => {
      const element = section.querySelector(selector);
      if (!element) throw new Error(`Missing Discover geometry target: ${selector}`);
      const { x, y, width, height } = element.getBoundingClientRect();
      return { x, y, width, height };
    };
    return {
      header: rectangle('.workspace-controls-strip'),
      navigation: rectangle('.workspace-chrome > .media-section-tabs'),
      search: rectangle('.workspace-search-form'),
      field: rectangle('.workspace-search-form .discover-main-search'),
      type: rectangle('.workspace-search-form select'),
      submit: rectangle('.workspace-search-form > button[type="submit"]'),
      filters: rectangle('.workspace-filter-grid'),
    };
  });
}


test.skip(process.env.CP_TV_E2E !== '1', 'Requires disposable TV fixture server');

test('TV Library performance preserves real card values and exact saved version', async ({ page, request }) => {
  const begin = await request.post('/__tv_fixture/library-performance/begin');
  expect(begin.ok()).toBeTruthy();
  const fixture = await begin.json();
  try {
    const response = await request.post('/api/tv/catalog/search', { data: { scope: 'library',
      query: { version: 1, scope: 'library', mode: 'simple', groups: [], sort: { key: 'title', direction: 'asc' } },
      page: 1, page_size: 100 } });
    expect(response.ok()).toBeTruthy();
    const payload = await response.json();
    await page.goto('/library');
    await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
    const region = page.getByRole('region', { name: 'Library TV Shows', exact: true });
    await expect(region.locator('.tv-series-card')).toHaveCount(payload.items.length);
    const card = region.getByRole('link', { name: 'Open Harbor Signals' });
    const series = payload.items.find(item => item.title === 'Harbor Signals');
    expect(series.available_count).toBe(2);
    expect(series.primary_action.playable).toBe(true);
    await expect(card).toContainText(`${series.season_count} seas. · ${series.episode_count} eps.`);
    await card.click();
    const season = await (await request.get('/api/tv/series/1/seasons/1')).json();
    const episode = season.items.find(item => item.id === fixture.episode_id);
    expect(episode).toHaveProperty('metadata');
    expect(episode).toHaveProperty('overview');
    expect(episode).toHaveProperty('guest_stars');
    expect(episode.versions.map(item => item.file_id)).toEqual([1, fixture.file_id]);
    const row = page.getByRole('article', { name: 'S01E01 Arrival' });
    await row.getByRole('button', { name: 'Versions (2)', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'S01E01 versions' });
    await dialog.getByRole('button', { name: 'Play this version', exact: true }).nth(1).click();
    await expect.poll(async () => (await (await request.get('/__tv_fixture/library-performance/state')).json()).keys).toEqual([fixture.expected_key]);
    const saved = await (await request.get('/api/tv/series/1/seasons/1')).json();
    expect(saved.items.find(item => item.id === fixture.episode_id).selected_file_id).toBe(fixture.file_id);
    await row.getByRole('button', { name: 'Play', exact: true }).click();
    await expect.poll(async () => (await (await request.get('/__tv_fixture/library-performance/state')).json()).keys).toEqual([fixture.expected_key, fixture.expected_key]);
  } finally {
    expect((await request.post('/__tv_fixture/library-performance/end')).ok()).toBeTruthy();
  }
});

test('TV Library routes identity review to Maintenance and preserves its cards', async ({ page }) => {
  await page.route('**/api/tv/maintenance**', route => route.fulfill({ json: {
    items: [{ kind: 'show_folder', state: 'review', path: 'G:\\TV\\Example', files: 1,
      title_hint: 'Example', reason: 'Identity needs review', sample_filenames: ['Example.S01E01.mkv'], candidates: [] }],
    counts: { unidentified_folders: 1, unresolved_episode_files: 0, conflicts: 0, scan_errors: 0, exclusions: 0 },
    total: 1, page: 1, total_pages: 1,
  } }));
  await page.goto('/library');
  await openControls(page);
  await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows' }).click();
  await openControls(page);
  const card = page.locator('.tv-series-card').first();
  await expect(card).toBeVisible();
  await page.getByRole('button', { name: /Review TV identity in Maintenance/ }).click();
  await expect(page.getByRole('tab', { name: 'TV Identity' })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByText('G:\\TV\\Example')).toBeVisible();
  await page.getByRole('button', { name: 'Library', exact: true }).click();
  await openControls(page);
  await expect(card).toBeVisible();
});

test('Discover and Library use the in-page media rows and TV File View shows native TV files', async ({ page, request }) => {
  await page.goto('/discover');
  await openControls(page);
  const discoverTabs = page.getByRole('tablist', { name: 'Discover tools' });
  await expect(discoverTabs.getByRole('button')).toHaveCount(4);
  await expect(discoverTabs.getByRole('button', { name: 'Movies' })).toBeVisible();
  await expect(discoverTabs.getByRole('button', { name: 'TV Shows' })).toBeVisible();
  await expect(discoverTabs.getByRole('button', { name: 'Browse Indexers' })).toBeVisible();
  await expect(discoverTabs.getByRole('button', { name: 'Pick My Movie' })).toBeVisible();
  await expect(page.locator('.tv-media-switch')).toHaveCount(0);
  await page.screenshot({ path: 'docs/verification/tv-normal-import/parity/discover-media-row.png' });
  await discoverTabs.getByRole('button', { name: 'TV Shows' }).click();
  await openControls(page);
  await expect(page.getByRole('region', { name: 'Discover TV Shows' })).toBeVisible();
  await discoverTabs.getByRole('button', { name: 'Browse Indexers' }).click();
  await expect(page.getByRole('button', { name: 'Browse Indexers' })).toHaveAttribute('aria-pressed', 'true');

  await page.goto('/library');
  await openControls(page);
  const libraryTabs = page.getByRole('tablist', { name: 'Library media' });
  await expect(libraryTabs.getByRole('button')).toHaveCount(2);
  const { view: movieSwitch, rescan: movieRescan } = await measureLibraryActions(page, 'Library mode');
  // Approved combined Library header: embedded actions are 36px (2026-10-14 plan).
  expect(movieSwitch.height).toBe(36);
  expect(movieSwitch.y).toBe(movieRescan.y);
  expect(movieSwitch.height).toBe(movieRescan.height);
  await libraryTabs.getByRole('button', { name: 'TV Shows' }).click();
  await openControls(page);
  const { view: tvSwitch, rescan: tvRescan } = await measureLibraryActions(page, 'TV library mode');
  expect(tvSwitch.width).toBe(movieSwitch.width);
  expect(tvSwitch.height).toBe(movieSwitch.height);
  expect(tvSwitch.y).toBe(tvRescan.y);
  expect(tvSwitch.height).toBe(tvRescan.height);
  await page.getByRole('group', { name: 'TV library mode' }).getByRole('button', { name: 'File View' }).click();
  await openControls(page);
  await expect(page.locator('.tv-file-view .library-file-row')).toHaveCount(2);
  await page.locator('.tv-file-view .library-file-row').first().getByRole('button', { name: /Expand file details/ }).click();
  await expect(page.locator('.tv-file-view .library-file-row').first().getByText('Episode bindings')).toBeVisible();
  await expect(page.locator('.tv-file-view .library-file-row').first().getByRole('button', { name: 'Play episode' })).toBeVisible();
  await page.screenshot({ path: 'docs/verification/tv-normal-import/parity/tv-file-view.png' });
  const response = await request.get('/api/tv/files');
  expect(response.ok()).toBeTruthy();
  expect((await response.json()).items).toHaveLength(2);
  await page.getByRole('textbox', { name: 'Search TV files' }).fill('S01E01');
  await page.locator('.tv-file-view').getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.locator('.tv-file-view .library-file-row')).toHaveCount(1);
  await expect(page.locator('.tv-file-view .library-file-row')).toContainText('Harbor.Signals.S01E01');
  await page.locator('.tv-file-view .library-file-row').getByRole('button', { name: 'Media View' }).click();
  await expect(page.getByRole('heading', { name: 'Harbor Signals' })).toBeVisible();
});

for (const width of [1366, 1920, 2048]) {
  test(`TV Discover shares the movie page gutters and keeps every year field readable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/discover');
  await openControls(page);
    const { header: movieHeader, navigation: movieNavigation, search: movieSearch,
      field: movieField, type: movieType, submit: movieSubmit, filters: movieFilters } = await measureDiscoverControls(page);
    await expect(page.locator('.discover-header')).toHaveCount(0);
    await page.getByRole('tablist', { name: 'Discover tools' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
  await openControls(page);
    const { header: tvHeader, navigation: tvNavigation, search: tvSearch,
      field: tvField, type: tvType, submit: tvSubmit, filters: tvFilters } = await measureDiscoverControls(page, true);
    await expect(page.locator('.discover-header')).toHaveCount(0);
    expect(tvHeader.height).toBeLessThanOrEqual(60);
    expect(Math.abs(tvHeader.height - movieHeader.height)).toBeLessThan(2);
    expect(Math.abs(tvHeader.x - movieHeader.x)).toBeLessThan(2);
    expect(Math.abs(tvHeader.width - movieHeader.width)).toBeLessThan(2);
    for (const key of ['x', 'width', 'height']) expect(Math.abs(tvNavigation[key] - movieNavigation[key])).toBeLessThan(2);
    for (const key of ['x', 'width', 'height']) expect(Math.abs(tvSearch[key] - movieSearch[key])).toBeLessThan(2);
    for (const key of ['x', 'y', 'width']) expect(Math.abs(tvFilters[key] - movieFilters[key]),
      `Filter ${key}: Movie ${JSON.stringify(movieFilters)}, TV ${JSON.stringify(tvFilters)}`).toBeLessThan(2);
    for (const [tv, movie] of [[tvField, movieField], [tvType, movieType], [tvSubmit, movieSubmit]]) {
      expect(Math.abs((tv.x - tvSearch.x) - (movie.x - movieSearch.x))).toBeLessThan(2);
      expect(Math.abs(tv.width - movie.width)).toBeLessThan(2);
      expect(Math.abs(tv.height - movie.height)).toBeLessThan(2);
    }
    await expect(page.getByRole('button', { name: 'Add TV search criterion' })).toHaveCount(0);
    await expect(page.locator('.tv-discover-workspace .workspace-search-form > button[type="submit"]')).toHaveText('Search');
    const from = await page.getByLabel('TV year from').boundingBox();
    const to = await page.getByLabel('TV year to').boundingBox();
    const feed = await page.getByLabel('TV Discover feed').boundingBox();
    await expect(page.getByRole('button', { name: /Hide TV filters|Open TV filters/ })).toHaveCount(0);
    expect(from.width).toBeGreaterThanOrEqual(110);
    expect(to.width).toBeGreaterThanOrEqual(110);
    expect(from.x + from.width).toBeLessThanOrEqual(to.x - 4);
    expect(Math.abs(to.y - from.y)).toBeLessThan(2);
    const toolbar = page.locator('.tv-discover-workspace .workspace-filter-grid');
    const rows = await toolbar.evaluate((element) => {
      const tops = [];
      for (const child of element.children) {
        const top = child.getBoundingClientRect().top;
        if (!tops.some((previous) => Math.abs(previous - top) < 8)) tops.push(top);
      }
      return tops.length;
    });
    expect(rows).toBeLessThanOrEqual(2);
    expect(await toolbar.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    const toolbarBox = await toolbar.boundingBox();
    const sortBox = await page.getByLabel('Sort TV shows').boundingBox();
    expect(sortBox.x + sortBox.width).toBeLessThanOrEqual(toolbarBox.x + toolbarBox.width);
    await expect(page.getByRole('link', { name: 'Open Harbor Signals' })).toBeVisible();
    expect((await page.getByRole('link', { name: 'Open Harbor Signals' }).boundingBox()).width).toBeGreaterThanOrEqual(460);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test('TV Discover status uses Catalog and all four quick bars omit Language', async ({ page }) => {
  await page.goto('/discover');
  await openControls(page);
  await expect(page.getByLabel('Original language')).toHaveCount(0);
  await page.getByRole('tablist', { name: 'Discover tools' }).getByRole('button', { name: 'TV Shows' }).click();
  await openControls(page);
  const status = page.getByLabel('TV Series status');
  await expect(page.getByLabel('TV Original language')).toHaveCount(0);
  await expect(status.locator('option')).toHaveCount(7);
  await status.selectOption('3');
  await expect(page.getByLabel('TV Discover feed')).toHaveValue('catalog');
  await expect(page.getByRole('link', { name: 'Open Harbor Signals' })).toBeVisible();
  await status.selectOption('5');
  await expect(page.getByRole('link', { name: 'Open Harbor Signals' })).toHaveCount(0);
  await page.getByLabel('TV Discover feed').selectOption('trending_week');
  await expect(status).toHaveValue('');
  await page.getByLabel('TV search type').selectOption('advanced');
  await page.getByRole('button', { name: 'Add advanced search criterion' }).click();
  await expect(page.getByLabel('Criterion to add').locator('option[value="language"]')).toHaveCount(1);
  await expect(page.getByLabel('Criterion to add').locator('option[value="tv_status"]')).toHaveCount(1);
  await page.goto('/library');
  await openControls(page);
  await openControls(page);
  await expect(page.locator('.library-filter-toolbar-movie').getByText('All languages')).toHaveCount(0);
  await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows' }).click();
  await openControls(page);
  await openControls(page);
  await expect(page.getByLabel('TV Original language')).toHaveCount(0);
});

for (const width of [1366, 2048]) {
  test(`TV Library filters keep the movie grid and readable year fields at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/library');
  await openControls(page);
    const movieHeader = await page.locator('.library-workspace:not(.tv-library-workspace) > .workspace-chrome').boundingBox();
    const movieNavigation = await page.locator('.library-workspace:not(.tv-library-workspace) > .workspace-chrome > .media-section-tabs').boundingBox();
    const movieSearch = await page.locator('.library-workspace:not(.tv-library-workspace) .workspace-search-form').boundingBox();
    const movieField = await page.locator('.library-workspace:not(.tv-library-workspace) .workspace-search-form .library-main-search').boundingBox();
    const movieType = await page.getByLabel('Library search type').boundingBox();
    const movieSubmit = await page.locator('.library-workspace:not(.tv-library-workspace) .workspace-search-form > button[type="submit"]').boundingBox();
    const movieTab = await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'Movies', exact: true }).boundingBox();
    await openControls(page);
    const movieFilters = await page.locator('.library-workspace:not(.tv-library-workspace) .library-filter-toolbar').boundingBox();
    await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
  await openControls(page);
    const tvHeader = await page.locator('.tv-library-workspace > .workspace-chrome').boundingBox();
    const tvNavigation = await page.locator('.tv-library-workspace > .workspace-chrome > .media-section-tabs').boundingBox();
    const tvSearch = await page.locator('.tv-library-workspace .workspace-search-form').boundingBox();
    const tvField = await page.locator('.tv-library-workspace .workspace-search-form .library-main-search').boundingBox();
    const tvType = await page.getByLabel('TV search type').boundingBox();
    const tvSubmit = await page.locator('.tv-library-workspace .workspace-search-form > button[type="submit"]').boundingBox();
    const tvTab = await page.getByRole('tablist', { name: 'Library media' }).getByRole('button', { name: 'TV Shows', exact: true }).boundingBox();
    expect(Math.abs(tvHeader.x - movieHeader.x)).toBeLessThan(2);
    expect(Math.abs(tvHeader.width - movieHeader.width)).toBeLessThan(2);
    for (const key of ['x', 'width', 'height']) expect(Math.abs(tvNavigation[key] - movieNavigation[key])).toBeLessThan(2);
    for (const key of ['x', 'width', 'height']) expect(Math.abs(tvSearch[key] - movieSearch[key])).toBeLessThan(2);
    for (const [tv, movie] of [[tvField, movieField], [tvType, movieType], [tvSubmit, movieSubmit]]) {
      expect(Math.abs((tv.x - tvSearch.x) - (movie.x - movieSearch.x))).toBeLessThan(2);
      expect(Math.abs(tv.width - movie.width)).toBeLessThan(2);
      expect(Math.abs(tv.height - movie.height)).toBeLessThan(2);
    }
    await expect(page.getByRole('button', { name: 'Add TV search criterion' })).toHaveCount(0);
    await expect(page.locator('.tv-library-workspace .workspace-search-form > button[type="submit"]')).toHaveText('Search');
    expect(Math.abs(tvTab.height - movieTab.height)).toBeLessThan(2);
    await openControls(page);
    const toolbar = page.locator('.tv-library-workspace .workspace-filter-grid');
    const tvFilters = await toolbar.boundingBox();
    for (const key of ['x', 'y', 'width']) expect(Math.abs(tvFilters[key] - movieFilters[key])).toBeLessThan(2);
    await expect(toolbar.getByLabel('TV Resolutions')).toBeVisible();
    await expect(toolbar.getByLabel('TV Sources')).toBeVisible();
    await expect(toolbar.getByLabel('TV Viewing states')).toBeVisible();
    await expect(toolbar.getByLabel('TV Status')).toBeVisible();
    await expect(toolbar.getByLabel('TV Viewing states').locator('option[value="in_progress"]')).toHaveText('In progress');
    await expect(page.getByText('TV status and local episodes', { exact: true })).toHaveCount(0);
    for (const label of ['TV Progress', 'TV Monitoring', 'TV Availability', 'TV Local audio language']) await expect(page.getByLabel(label, { exact: true })).toHaveCount(0);
    const first = await toolbar.getByLabel('TV Resolutions').boundingBox();
    const viewing = await toolbar.getByLabel('TV Viewing states').boundingBox();
    const status = await toolbar.getByLabel('TV Status').boundingBox();
    const yearFrom = await toolbar.getByLabel('TV year from').boundingBox();
    const yearTo = await toolbar.getByLabel('TV year to').boundingBox();
    const sort = await toolbar.getByLabel('Sort TV shows').boundingBox();
    const reset = await toolbar.getByRole('button', { name: 'Reset filters' }).boundingBox();
    expect(viewing.width).toBeGreaterThanOrEqual(145);
    expect(status.width).toBeGreaterThanOrEqual(145);
    await expect(toolbar.getByLabel('TV Original language')).toHaveCount(0);
    expect(Math.abs(yearTo.y - yearFrom.y)).toBeLessThan(2);
    expect(yearFrom.width).toBeGreaterThanOrEqual(125);
    expect(yearTo.width).toBeGreaterThanOrEqual(125);
    expect(sort.width).toBeGreaterThanOrEqual(145);
    const rows = await toolbar.evaluate((element) => {
      const tops = [];
      for (const child of element.children) {
        const top = child.getBoundingClientRect().top;
        if (!tops.some((previous) => Math.abs(previous - top) < 8)) tops.push(top);
      }
      return tops.length;
    });
    expect(rows).toBeLessThanOrEqual(2);
    expect(await toolbar.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    expect(reset.width).toBeLessThanOrEqual(40);
    await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Search, filters & selection', exact: true })).toHaveAttribute('aria-expanded', 'false');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test('Advanced search explains how to add filters in both media tabs of Library and Discover', async ({ page }) => {
  for (const area of ['library', 'discover']) {
    for (const media of ['Movies', 'TV Shows']) {
      await page.goto(`/${area}`);
  await openControls(page);
      if (media === 'TV Shows') await page.getByRole('tablist', { name: area === 'discover' ? 'Discover tools' : 'Library media' }).getByRole('button', { name: area === 'discover' ? 'TV Shows' : media, exact: true }).click();
      await openControls(page);
      const form = area === 'library'
        ? page.locator(media === 'Movies' ? '.library-workspace:not(.tv-library-workspace) form.workspace-search-form' : '.tv-library-workspace form.workspace-search-form')
        : page.locator(media === 'Movies' ? '.discover-workspace form.workspace-search-form' : '.tv-discover-workspace form.workspace-search-form');
      await form.getByLabel(media === 'Movies' ? area === 'library' ? 'Library search type' : 'TMDB search type' : 'TV search type').selectOption('advanced');
      await expect(form.getByText('Click + to choose a filter', { exact: true })).toBeVisible();
      await expect(form.getByText('This field is not a normal text search')).toHaveCount(0);
      await form.getByRole('button', { name: 'Add advanced search criterion' }).click();
      await expect(page.getByLabel('Criterion to add')).toBeVisible();
    }
  }
});

async function discover(page, title) {
  await page.goto('/discover');
  await openControls(page);
  await page.getByRole('tablist', { name:'Discover tools' }).getByRole('button',{name:'TV Shows',exact:true}).click();
  await openControls(page);
  await page.getByRole('textbox',{name:'Search TV shows',exact:true}).fill(title);
  await page.getByRole('button',{name:'Search TV',exact:true}).click();
  await expect(page.getByRole('link',{name:`Open ${title}`,exact:true})).toBeVisible();
}

for (const viewport of [{width:1920,height:1080},{width:1920,height:720},{width:1366,height:768}]) {
  test(`TV desktop parity and uncropped Dark Matter poster at ${viewport.width}x${viewport.height}`, async({page,request})=>{
    await page.setViewportSize(viewport);
    await discover(page,'Dark Matter');
    const field=page.getByRole('textbox',{name:'Search TV shows',exact:true});
    const dimensions=await field.boundingBox();
    expect(dimensions.width).toBeGreaterThan(viewport.width*0.4);
    await expect(page.getByRole('button',{name:'Add TV search criterion',exact:true})).toHaveCount(0);
    for(const label of ['TV Genres','TV Series status','TV Countries','TV minimum rating','TV minimum votes','Sort TV shows']) await expect(page.getByLabel(label,{exact:true})).toBeVisible();
    const card=page.getByRole('link',{name:'Open Dark Matter',exact:true});
    await expect(card).toContainText('Sci-Fi & Fantasy');await expect(card).toContainText('English');await expect(card).toContainText('US');
    await expect.poll(()=>card.locator('img').first().evaluate(img=>img.complete&&img.naturalWidth>0)).toBeTruthy();
    await page.screenshot({path:`docs/verification/tv-normal-import/parity/discover-${viewport.width}x${viewport.height}.png`,fullPage:true});
    const before=await (await request.get('/api/tv/series')).json();
    await card.click();
    await expect(page.getByRole('region',{name:'Series cast'})).toContainText('Joel Edgerton');
    const poster=page.locator('.tv-series-header > img');
    await expect(poster).toHaveCSS('object-fit','contain');
    const box=await poster.boundingBox();expect(box.width).toBeGreaterThanOrEqual(180);
    expect(box.height/box.width).toBeGreaterThan(1.4);expect(box.height/box.width).toBeLessThan(1.6);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
    await page.getByRole('button',{name:'Download season',exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'TV release review'});
    await expect(dialog).toContainText('Torrent link will be resolved before queuing.');
    await dialog.getByRole('button',{name:'Close TV release review'}).click();
    expect((await (await request.get('/api/tv/series')).json()).total).toBe(before.total);
    await page.getByRole('heading',{name:'Dark Matter',exact:true}).scrollIntoViewIfNeeded();
    await page.screenshot({path:`docs/verification/tv-normal-import/parity/dark-matter-${viewport.width}x${viewport.height}.png`,fullPage:true});
  });
}

test('Born Again exposes season downloads and main cast without adding the series',async({page})=>{
  await discover(page,'Daredevil: Born Again');
  await page.getByRole('link',{name:'Open Daredevil: Born Again',exact:true}).click();
  await expect(page.getByRole('region',{name:'Series cast'})).toContainText('Charlie Cox');
  await expect(page.getByRole('button',{name:'Download season',exact:true})).toBeEnabled();
  await expect(page.getByRole('button',{name:'Download episode',exact:true}).first()).toBeEnabled();
});

test('selected Simpsons episodes resolve missing hashes and queue once without enabling monitoring',async({page,request})=>{
  expect((await request.post('/__tv_fixture/approved-home/456')).ok()).toBeTruthy();
  await discover(page,'The Simpsons');
  await page.getByRole('link',{name:'Open The Simpsons',exact:true}).click();
  await page.getByLabel('Select S01E01',{exact:true}).check();await page.getByLabel('Select S01E02',{exact:true}).check();
  await page.getByRole('button',{name:'Download selected',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'TV release review'});
  await expect(dialog).toContainText('2 of 2 episodes');
  await dialog.getByRole('button',{name:'Download selected releases',exact:true}).click();
  await expect(dialog.getByRole('button',{name:'Queued',exact:true})).toBeDisabled();
  const jobs=await (await request.get('/api/tv/acquisitions')).json();
  const selected=jobs.items.filter(r=>r.target.includes(':456:'));
  expect(selected).toHaveLength(2);expect(new Set(selected.map(r=>r.info_hash)).size).toBe(2);
  const seriesId=selected[0].job?.tv_request?.series_id;
  expect(seriesId).toBeTruthy();
  const monitoring=await (await request.get(`/api/tv/series/${seriesId}/monitor`)).json();
  expect(monitoring.rules).toHaveLength(0);
  await page.screenshot({path:'docs/verification/tv-normal-import/parity/simpsons-selected-downloads.png',fullPage:true});
});

test('top and bottom TV pagination share state',async({page})=>{
  const pages=[];
  await page.route('**/api/tv/catalog/search',async route=>{
    const body=route.request().postDataJSON();pages.push(body.page);
    await route.fulfill({json:{items:[{tmdb_id:900001,title:'Harbor Signals',genres:[],available_count:0}],page:body.page,page_size:20,total:40,total_pages:2,has_next:body.page<2}});
  });
  await page.goto('/discover');
  await openControls(page);
  await page.getByRole('tablist',{name:'Discover tools'}).getByRole('button',{name:'TV Shows',exact:true}).click();
  const top=page.getByRole('navigation',{name:'TV page controls above results'}),bottom=page.getByRole('navigation',{name:'TV pagination',exact:true});
  await top.getByRole('button',{name:'Next',exact:true}).click();
  await expect(bottom).toContainText('Page 2 of 2');
  await bottom.getByRole('button',{name:'Previous',exact:true}).click();
  await expect(top).toContainText('Page 1 of 2');expect(pages).toContain(2);
});

for (const [width, expectedColumns, expectedPageSize] of [[1366, 2, 40], [1920, 3, 39]]) {
  test(`TV Discover and Library fill complete card rows at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const requests = [];
    const series = Array.from({ length: 80 }, (_, index) => ({
      tmdb_id: 910000 + index,
      title: `Series ${String(index + 1).padStart(2, '0')}`,
      first_air_date: '2020-01-01',
      season_count: 1,
      episode_count: 1,
      status: 'Ended',
      genres: [],
      available_count: 0,
    }));
    await page.route('**/api/tv/catalog/search', async route => {
      const body = route.request().postDataJSON();
      requests.push({ scope: body.scope, page: body.page, pageSize: body.page_size });
      const start = (body.page - 1) * body.page_size;
      await route.fulfill({ json: {
        items: series.slice(start, start + body.page_size),
        page: body.page, page_size: body.page_size, total: series.length,
        total_pages: Math.ceil(series.length / body.page_size), complete: true,
      } });
    });

    for (const scope of ['discover', 'library']) {
      await page.goto(`/${scope}`);
      const tabs = page.getByRole('tablist', { name: scope === 'discover' ? 'Discover tools' : 'Library media' });
      await tabs.getByRole('button', { name: scope === 'discover' ? 'TV Shows' : 'TV Shows', exact: true }).click();
      const grid = page.locator(`.tv-${scope}-workspace .tv-series-grid:not(.library-grid-metrics-probe)`);
      await expect(grid.locator('.tv-series-card')).toHaveCount(expectedPageSize);
      const columns = await grid.evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').filter(Boolean).length);
      expect(columns).toBe(expectedColumns);
      expect(expectedPageSize % columns).toBe(0);
      expect(requests.some(request => request.scope === scope && request.page === 1 && request.pageSize === expectedPageSize)).toBe(true);
    }

    const top = page.getByRole('navigation', { name: 'TV page controls above results' });
    await top.getByRole('button', { name: 'Next', exact: true }).click();
    const nextPage = page.locator('.tv-library-workspace .tv-series-grid:not(.library-grid-metrics-probe)');
    await expect(nextPage.locator('.tv-series-card')).toHaveCount(expectedPageSize);
    await expect(nextPage.locator('.tv-series-card').first()).toContainText(`Series ${String(expectedPageSize + 1).padStart(2, '0')}`);
    expect(requests.some(request => request.scope === 'library' && request.page === 2 && request.pageSize === expectedPageSize)).toBe(true);
  });
}

test('TV Discover enriches every card on a 39-card page', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 900 });
  const batches = [];
  const series = Array.from({ length: 39 }, (_, index) => ({
    tmdb_id: 920000 + index,
    title: `Series ${index + 1}`,
    first_air_date: '2020-01-01',
    genres: [],
    available_count: 0,
  }));
  await page.route('**/api/tv/catalog/search', route => route.fulfill({ json: {
    items: series, page: 1, page_size: 39, total: series.length,
    total_pages: 1, complete: true,
  } }));
  await page.route('**/api/tv/catalog/enrich', route => {
    const ids = route.request().postDataJSON().ids;
    batches.push(ids);
    return route.fulfill({ json: { items: ids.map(tmdb_id => ({
      tmdb_id, season_count: 2, episode_count: 12, status: 'Ended',
    })) } });
  });

  await page.goto('/discover');
  await openControls(page);
  await page.getByRole('tablist', { name: 'Discover tools' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
  await openControls(page);
  const cards = page.locator('.tv-discover-workspace .tv-series-card');
  await expect(cards).toHaveCount(39);
  await expect(cards.last()).toContainText('2 seas.');
  await expect(cards.filter({ hasText: '2 seas.' })).toHaveCount(39);
  expect(batches.every(batch => batch.length > 0 && batch.length <= 20)).toBe(true);
  expect(batches.flat()).toHaveLength(39);
  expect(new Set(batches.flat()).size).toBe(39);
});


test('TV title draft survives opening advanced criteria and keyboard search',async({page})=>{
  await page.goto('/discover');
  await openControls(page);
  await page.getByRole('tablist',{name:'Discover tools'}).getByRole('button',{name:'TV Shows',exact:true}).click();
  await openControls(page);
  await page.getByRole('textbox',{name:'Search TV shows',exact:true}).fill('Dark Matter');
  await page.getByLabel('TV search type').selectOption('advanced');
  await expect(page.getByRole('textbox',{name:'Edit title',exact:true})).toHaveValue('Dark Matter');
  await page.getByRole('textbox',{name:'Edit title',exact:true}).press('Enter');
  await expect(page.getByRole('link',{name:'Open Dark Matter',exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:'Open Harbor Signals',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Reset Discover filters',exact:true}).click();
  await expect(page.getByRole('textbox',{name:'Search TV shows',exact:true})).toHaveValue('');
  await expect(page.getByRole('link',{name:'Open Harbor Signals',exact:true})).toBeVisible();
});
