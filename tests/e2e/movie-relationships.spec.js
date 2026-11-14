import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

async function openControls(page) {
  const toggle = page.getByRole('button', { name: 'Search, filters & selection', exact: true });
  await expect(toggle).toBeVisible();
  if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
}

test.use({ viewport: { width: 1920, height: 1080 }, reducedMotion: 'reduce' });
const movie = (id, title = `Related Movie ${id}`) => ({
  tmdb_id: String(id), title, year: '2024', tmdb_rating: '7.8', tmdb_vote_count: 450,
  genres: ['Thriller', 'Mystery'], summary: 'A quiet gathering becomes a desperate test of loyalty when an unexpected guest arrives.',
  poster_url: 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="240" height="360"><defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="#634b32"/><stop offset="1" stop-color="#090c15"/></linearGradient></defs><rect width="240" height="360" fill="url(#g)"/><circle cx="120" cy="130" r="64" fill="#b3a98a" opacity=".2"/><text x="120" y="245" fill="#e2d1ac" font-family="serif" font-size="18" text-anchor="middle">' + title + '</text></svg>')
});
const seed = movie(1, 'The Hunt');
const selected = movie(2, 'Ready or Not');
const owned = { path: 'E:/Movies/Ready.or.Not.mkv', title: selected.title, metadata_accepted: true, resolution: '1080p', canonical_metadata: { ...selected, rating: '7.8', accepted: true } };
const portrait = (letter) => 'data:image/svg+xml,' + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="106" height="132"><rect width="106" height="132" fill="#20242a"/><text x="53" y="75" fill="#d4af37" font-size="28" text-anchor="middle">${letter}</text></svg>`);
const credits = { directors: [{ id: 90, name: 'Thomas Vinterberg', profile_url: portrait('T') }], cast: Array.from({ length: 9 }, (_, i) => ({ id: 100 + i, name: `Cast Member ${i + 1}`, character: `Character ${i + 1}`, profile_url: portrait(`C${i + 1}`) })), keywords: ['survival', 'family', 'mystery'], runtime: 115, certification: 'R' };

async function fixtures(page, { delay = 0, detailsDelay = 0, fail = false, lists = [{ id: 'related-list', name: 'Related Test List', movies: [selected] }] } = {}) {
  const requests = [];
  await page.route('**/api/streaming/config', (route) => route.fulfill({ json: { enabled: true, label: 'Stream', url_template: 'https://example.test/watch/{tmdb_id}' } }));
  await page.route('**/api/user/lists', (route) => route.fulfill({ json: { lists, curation_generation: 1 } }));
  await page.route('**/api/tmdb/discover**', (route) => route.fulfill({ json: { results: [seed, ...Array.from({ length: 12 }, (_, i) => movie(500 + i))], page: 1, total_pages: 1, total_results: 13 } }));
  await page.route('**/api/tmdb/details**', async (route) => {
    if (detailsDelay) await new Promise((resolve) => setTimeout(resolve, detailsDelay));
    await route.fulfill({ json: { ...movie(new URL(route.request().url()).searchParams.get('tmdb_id')), ...credits } });
  });
  await page.route('**/api/library/details**', (route) => route.fulfill({ json: { item: { ...owned, canonical_metadata: { ...owned.canonical_metadata, directors: [{ name: 'Thomas Vinterberg' }], cast: credits.cast.slice(0, 3).map(({ name }) => ({ name })) } }, catalog_generation: 1 } }));
  await page.route('**/api/library/check', (route) => route.fulfill({ json: { catalog_generation: 1, results: (route.request().postDataJSON().movies || []).map((item) => String(item.tmdb_id) === '2' ? { ...selected, found: true, path: owned.path, library_item: owned, canonical_card: owned } : { ...item, found: false }) } }));
  await page.route('**/api/tmdb/related**', async (route) => {
    const params = new URL(route.request().url()).searchParams;
    const recorded = { ...Object.fromEntries(params), completed: false };
    requests.push(recorded);
    if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
    if (fail === true || fail === params.get('source')) return route.fulfill({ status: 502, json: { error: 'Relationship provider unavailable' } });
    const source = params.get('source');
    const pageNumber = Number(params.get('page'));
    const start = pageNumber === 1 ? 2 : 22;
    const results = Array.from({ length: 20 }, (_, i) => movie(start + i + (source === 'similar' ? 10 : 0)));
    if (source === 'recommendations' && pageNumber === 1) results[0] = selected;
    await route.fulfill({ json: { results: results.filter((item) => item.tmdb_id !== params.get('tmdb_id')).map((item) => ({ ...item, relationship_source: source })), source, page: pageNumber, page_size: 20, source_limit: 100, total_pages: 2, total_results: 40, has_previous: pageNumber > 1, has_next: pageNumber < 2 } });
    recorded.completed = true;
  });
  return requests;
}
const expanded = (page) => page.locator('.unified-movie-card-expanded:visible');
async function expandSeed(page, scope = 'discover') {
  if (scope === 'library') {
    await page.route('**/api/tv/capabilities', route => route.fulfill({ json: { enabled: true } }));
    const item = { ...owned, canonical_metadata: { ...seed, ...credits, accepted: true, rating: '7.8' } };
    await page.route('**/api/library/search/advanced', route => route.fulfill({ json: {
      items: [item], total: 1, page: 1, total_pages: 1, page_start: 0, page_end: 1,
      catalog_generation: 1, facets: { genres: [], countries: [], languages: [], sources: [] },
      stats: { total: 1, matched: 1, pending: 0, unmatched: 0, low: 0 }
    } }));
    await page.route('**/api/library/details**', route => route.fulfill({ json: { item, catalog_generation: 1 } }));
  }
  await page.goto(`/${scope}`);
  await page.getByRole('heading', { name: seed.title, exact: true }).click();
  await expect(expanded(page)).toBeVisible();
}
async function fullCard(page, checkInitialPosition = true) {
  await expect.poll(async () => {
    const box = await expanded(page).boundingBox();
    const visibleChrome = page.locator('.workspace-chrome:visible');
    const chrome = await visibleChrome.count() ? await visibleChrome.boundingBox() : null;
    const remainingHeight = page.viewportSize().height - (chrome?.height || 0);
    // Dante approved scrolling the lower content when sticky controls leave
    // insufficient room. Cards that fit must still be fully visible.
    return box && (!checkInitialPosition || (box.y >= (chrome ? chrome.y + chrome.height - 1 : 0)
      && box.y < page.viewportSize().height
      && (box.height > remainingHeight || box.y + box.height <= page.viewportSize().height)))
      && box.x >= 0 && box.x + box.width <= page.viewportSize().width;
  }).toBe(true);
  const overflow = await expanded(page).evaluate((card) => {
    const border = card.getBoundingClientRect();
    return [...card.querySelectorAll('button, .person-card, .related-tile')].filter((element) => {
      const box = element.getBoundingClientRect();
      return box.width && box.height && (box.top < border.top || box.bottom > border.bottom + 1);
    }).map((element) => element.textContent);
  });
  expect(overflow).toEqual([]);
}

async function settledWorkspaceScroll(page) {
  return page.locator('.workspace').evaluate((workspace) => new Promise((resolve) => {
    let frames = 0;
    let stableFrames = 0;
    let previous = workspace.scrollTop;
    const check = () => {
      const current = workspace.scrollTop;
      frames += 1;
      stableFrames = Math.abs(current - previous) < 0.5 ? stableFrames + 1 : 0;
      previous = current;
      if (frames >= 4 && stableFrames >= 3) resolve(current);
      else requestAnimationFrame(check);
    };
    requestAnimationFrame(check);
  }));
}

for (const scope of ['discover', 'library']) {
  for (const width of [1600, 1366]) {
    test(`${scope} cast award icons remain visible beside counts at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await fixtures(page);
      await page.route('**/api/movie-awards/snapshot', route => route.fulfill({ json: {
        schema_version: 1, snapshot_owner: 'cast-award-layout', awards_generation: 1, ready: true, movies: {},
        people: {
          'tmdb:90': { director: { oscar: 12, golden_globe: 99 } },
          'tmdb:100': { actor: { oscar: 2, golden_globe: 3 } }
        }
      } }));
      await expandSeed(page, scope);
      const badges = expanded(page).locator('.person-card .movie-award-pair');
      await expect(badges).toHaveCount(4);
      await expect.poll(() => badges.locator('img').evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0))).toBe(true);
      const geometry = await badges.evaluateAll(nodes => nodes.map(node => {
        const icon = node.querySelector('img').getBoundingClientRect();
        const count = node.querySelector('strong').getBoundingClientRect();
        const badge = node.getBoundingClientRect();
        const portrait = node.closest('.person-card').querySelector('.person-avatar').getBoundingClientRect();
        return { iconWidth: icon.width, iconHeight: icon.height,
          separate: count.right <= icon.left,
          contained: count.left >= badge.left - 1 && icon.right <= badge.right + 1,
          besidePortrait: badge.left >= portrait.right };
      }));
      for (const badge of geometry) {
        expect(badge.iconWidth).toBeGreaterThan(0);
        expect(badge.iconHeight).toBeGreaterThan(0);
        expect(badge.separate).toBe(true);
        expect(badge.contained).toBe(true);
        expect(badge.besidePortrait).toBe(true);
      }
    });
  }
}

for (const scope of ['discover', 'library']) {
for (const viewport of [{ width: 1920, height: 1080 }, { width: 1366, height: 768 }, { width: 390, height: 844 }]) {
  test.describe(`${scope} movie artwork at ${viewport.width}px`, () => {
    test.use({ viewport });
    test('expanded movie artwork stays behind the poster and details without an outer hover effect', async ({ page }) => {
      await fixtures(page);
      await expandSeed(page, scope);
      const card = expanded(page);
      await expect.poll(() => card.evaluate(element => getComputedStyle(element).boxShadow)).toBe('none');
      const layout = await card.evaluate(element => {
        const main = element.querySelector('.unified-movie-main');
        const bounds = main.getBoundingClientRect();
        const footer = element.querySelector('.unified-movie-expanded-row').getBoundingClientRect();
        return { artwork: getComputedStyle(main).backgroundImage, outerArtwork: getComputedStyle(element).backgroundImage,
          childrenInside: [...main.querySelectorAll('.unified-movie-poster, .unified-movie-body')].every(child => {
            const box = child.getBoundingClientRect();
            return box.left >= bounds.left && box.right <= bounds.right + 1 && box.bottom <= bounds.bottom + 1;
          }), footerBelow: footer.top >= bounds.bottom, border: getComputedStyle(element).borderTopColor,
          shadow: getComputedStyle(element).boxShadow };
      });
      expect(layout.artwork).toContain('url(');
      // The outer surface may have a theme gradient; artwork belongs to main only.
      expect(layout.outerArtwork).not.toContain('url(');
      expect(layout.childrenInside).toBe(true);
      expect(layout.footerBelow).toBe(true);
      await card.locator('.unified-movie-header').hover();
      await expect.poll(() => card.evaluate(element => ({ border: getComputedStyle(element).borderTopColor, shadow: getComputedStyle(element).boxShadow })))
        .toEqual({ border: layout.border, shadow: layout.shadow });
    });
  });
}
}

test('movie details collapse from plain content while actions and dialogs remain usable', async ({ page }) => {
  await fixtures(page);
  await page.route('**/api/tmdb/discover**', route => route.fulfill({ json: { results: [{ ...seed, summary: seed.summary.repeat(3) }], page: 1, total_pages: 1, total_results: 1 } }));
  await page.route('**/api/tmdb/details**', route => route.fulfill({ json: { ...seed, ...credits, summary: seed.summary.repeat(3) } }));
  await expandSeed(page);
  for (const selector of ['.movie-card-plot', '.movie-expanded-runtime', '.lists-panel .mini-label', '.unified-movie-poster img']) {
    await expanded(page).locator(selector).click();
    await expect(expanded(page)).toHaveCount(0);
    await page.getByRole('heading', { name: seed.title, exact: true }).click();
    await expect(expanded(page)).toBeVisible();
  }
  await expanded(page).locator('.selection-checkbox').click();
  await expect(expanded(page).getByRole('checkbox', { name: `Select ${seed.title}` })).toBeChecked();
  await expect(expanded(page)).toBeVisible();
  await expanded(page).getByRole('button', { name: 'Read full plot', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: `Plot of ${seed.title}` });
  await expect(dialog).toHaveClass(/cp-dialog/);
  const keyword = expanded(page).locator('.movie-keyword-chip').first();
  await expect(keyword).toHaveClass(/cp-badge-compact/);
  expect(await keyword.evaluate(el => ({ weight: getComputedStyle(el).fontWeight, background: getComputedStyle(el).backgroundColor })))
    .toEqual({ weight: '700', background: 'rgb(26, 28, 32)' });
  await dialog.locator('p').click();
  await expect(dialog).toBeVisible();
  await expect(expanded(page)).toBeVisible();
  await dialog.getByRole('button', { name: 'Close', exact: true }).click();
  await expanded(page).focus();
  await page.keyboard.press('Enter');
  await expect(expanded(page)).toHaveCount(0);
});

for (const scope of ['discover', 'library']) {
test(`${scope} expanded movie rails reveal the remaining cast and related titles with matching arrows`, async ({ page }) => {
  await fixtures(page);
  await expandSeed(page, scope);
  const card = expanded(page);
  await expect(card.getByRole('button', { name: 'Open Ready or Not in Discover' })).toBeVisible();
  if (scope === 'library' && process.env.CP_LAYOUT_EVIDENCE_DIR) {
    fs.mkdirSync(process.env.CP_LAYOUT_EVIDENCE_DIR, { recursive: true });
    await page.screenshot({ path: path.join(process.env.CP_LAYOUT_EVIDENCE_DIR, 'library-expanded-parity.png') });
  }
  for (const label of ['cast', 'related titles']) {
    const track = card.getByRole('group', { name: `${label} cards`, exact: true });
    const left = card.getByRole('button', { name: `Scroll ${label} left`, exact: true });
    const right = card.getByRole('button', { name: `Scroll ${label} right`, exact: true });
    await expect(left).toBeDisabled();
    await expect(right).toBeEnabled();
    {
      const row = await track.boundingBox();
      const leftBox = await left.boundingBox();
      const rightBox = await right.boundingBox();
      expect(Math.abs(leftBox.y + leftBox.height / 2 - row.y - row.height / 2)).toBeLessThan(1);
      expect(Math.abs(rightBox.y + rightBox.height / 2 - row.y - row.height / 2)).toBeLessThan(1);
      const firstCard = await track.locator(':scope > *').first().boundingBox();
      expect(Math.abs(leftBox.x - row.x)).toBeLessThan(1);
      expect(Math.abs(rightBox.x + rightBox.width - row.x - row.width)).toBeLessThan(1);
      expect(rightBox.x).toBeLessThan(row.x + row.width);
      expect(Math.abs(leftBox.height - firstCard.height)).toBeLessThan(1);
      expect(Math.abs(rightBox.height - firstCard.height)).toBeLessThan(1);
      expect(await right.evaluate(element => getComputedStyle(element).borderTopWidth)).toBe('0px');
      expect(await right.evaluate(element => getComputedStyle(element.parentElement, '::after').backgroundImage)).toContain('linear-gradient');
      expect(await right.evaluate(element => getComputedStyle(element.parentElement, '::after').backgroundImage)).toContain('rgb(18, 19, 22) 44px');
      expect(await right.locator('svg').evaluate(element => element.parentElement.getBoundingClientRect().right - element.getBoundingClientRect().right)).toBeLessThanOrEqual(8.1);
      await card.getByRole('heading', { name: seed.title, exact: true }).hover();
      await expect.poll(() => right.evaluate(element => getComputedStyle(element).opacity)).toBe('0');
      await right.hover();
      await expect.poll(() => right.evaluate(element => getComputedStyle(element).opacity)).toBe('1');
      expect(await right.evaluate(element => getComputedStyle(element.parentElement, '::after').opacity)).toBe('1');
      await card.getByRole('heading', { name: seed.title, exact: true }).hover();
      await expect.poll(() => right.evaluate(element => getComputedStyle(element).opacity)).toBe('0');
      await page.keyboard.press('Tab');
      await right.focus();
      await expect.poll(() => right.evaluate(element => getComputedStyle(element).opacity)).toBe('1');
      if (label === 'related titles') {
        const viewAll = await card.getByRole('button', { name: 'View all', exact: true }).boundingBox();
        expect(viewAll.y + viewAll.height).toBeLessThan(row.y);
        const visible = await track.evaluate(element => [...element.children].filter(child => {
          const item = child.getBoundingClientRect();
          const rail = element.getBoundingClientRect();
          return item.left >= rail.left - 1 && item.right <= rail.right + 1;
        }).length);
        expect(visible).toBeGreaterThan(10);
      }
    }
    const last = track.locator(':scope > *').last();
    const lastVisible = () => last.evaluate(element => {
      const item = element.getBoundingClientRect();
      const rail = element.parentElement.getBoundingClientRect();
      return item.left >= rail.left - 1 && item.right <= rail.right + 1;
    });
    expect(await lastVisible()).toBe(false);
    await right.click();
    await expect.poll(lastVisible).toBe(true);
    await expect(right).toBeDisabled();
    await expect(left).toBeEnabled();
    await left.click();
    await expect(left).toBeDisabled();
    await expect(right).toBeEnabled();
    expect(await track.evaluate(element => getComputedStyle(element).scrollbarWidth)).toBe('none');
  }
  const person = card.locator('.person-card').first();
  const portraitBox = await person.locator('.person-avatar').boundingBox();
  const bioBox = await person.getByRole('button', { name: /Open biography/ }).boundingBox();
  expect(bioBox.x).toBeGreaterThanOrEqual(portraitBox.x + portraitBox.width + 4);
  await card.getByRole('button', { name: 'Similar', exact: true }).click();
  await expect(card.getByRole('button', { name: 'Scroll related titles left', exact: true })).toBeDisabled();
  await expect(card.getByRole('button', { name: 'Open Related Movie 12 in Discover' })).toBeVisible();
});
}

test('related posters reveal full title and year on hover and keyboard focus', async ({ page }) => {
  await fixtures(page);
  await expandSeed(page);
  const tile = expanded(page).getByRole('button', { name: 'Open Ready or Not in Discover' });
  await expect(tile).toBeVisible();
  await expect(tile.locator('strong, small')).toHaveCount(0);
  const poster = tile.locator('.related-poster');
  const posterBox = await poster.boundingBox();
  const tileBox = await tile.boundingBox();
  expect(tileBox.height - posterBox.height).toBeLessThanOrEqual(4.1);
  expect(posterBox.height).toBeLessThanOrEqual(136);
  expect(Math.abs(tileBox.height / tileBox.width - 1.5)).toBeLessThan(.03);
  expect(await poster.locator('img').evaluate(element => getComputedStyle(element).objectFit)).toBe('contain');
  await tile.hover();
  const tooltip = page.getByRole('tooltip');
  await expect(tooltip).toContainText('Ready or Not');
  await expect(tooltip).toContainText('2024');
  await expect(tile).toHaveAttribute('aria-describedby', await tooltip.getAttribute('id'));
  await tooltip.hover();
  await expect(tooltip).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(tooltip).toBeHidden();
  await expanded(page).getByRole('heading', { name: 'The Hunt' }).hover();
  await tile.focus();
  await expect(tooltip).toContainText('Ready or Not');
  await page.locator('main.workspace').evaluate(element => element.scrollBy({ top: 40, behavior: 'instant' }));
  await expect(tooltip).toBeVisible();
  await expanded(page).getByRole('button', { name: 'Recommended', exact: true }).focus();
  await expect(tooltip).toBeHidden();
  await tile.focus();
  await expect(tooltip).toBeVisible();
  await tile.press('Escape');
  await expect(tooltip).toBeHidden();
  // A tooltip must not obstruct the tile's existing navigation behavior.
  await tile.click();
  await expect(expanded(page).getByRole('heading', { name: 'Ready or Not' })).toBeVisible();
  await expect(page.getByLabel('Discovery path')).toContainText('Related to The Hunt');
});

test('stable async rail, scrollable tiles, restored cast and selected related expansion', async ({ page }) => {
  const requests = await fixtures(page, { delay: 600 });
  await expandSeed(page);
  await fullCard(page);
  const before = await expanded(page).boundingBox();
  await expect(expanded(page).getByRole('button', { name: 'Open Ready or Not in Discover' })).toBeVisible();
  const after = await expanded(page).boundingBox();
  expect(Math.abs(before.height - after.height)).toBeLessThan(1);
  await expect(expanded(page).locator('.related-tile')).toHaveCount(20);
  await expect(expanded(page).locator('.lists-panel')).toBeVisible();
  await expect(expanded(page).getByRole('button', { name: 'Add to list', exact: true })).toBeVisible();
  await expect(expanded(page).locator('.collection-panel')).toHaveCount(0);
  const relatedPoster = await expanded(page).locator('.related-poster img').first().boundingBox();
  expect(relatedPoster.width).toBeLessThan(100);
  const relatedCard = await expanded(page).locator('.related-tile').first().boundingBox();
  expect(Math.abs(relatedCard.height / relatedCard.width - 1.5)).toBeLessThan(.03);
  expect(relatedPoster.height).toBeLessThanOrEqual(136);
  expect(await expanded(page).locator('.related-poster img').first().evaluate(element => getComputedStyle(element).objectFit)).toBe('contain');
  const castAvatar = await expanded(page).locator('.person-avatar').first().boundingBox();
  expect(Math.round(castAvatar.width)).toBe(106);
  expect(Math.round(castAvatar.height)).toBe(132);
  await expect(expanded(page).getByText('Cast Member 9', { exact: true })).toBeVisible();
  await expect.poll(async () => {
    const castPanel = await expanded(page).getByLabel('Director and top cast').boundingBox();
    const relationshipTabs = await expanded(page).getByLabel('Relationship source').boundingBox();
    return relationshipTabs.y - (castPanel.y + castPanel.height);
  }).toBeGreaterThanOrEqual(10);
  await expect(expanded(page).getByText('Owned', { exact: true })).toBeVisible();
  await expanded(page).getByRole('button', { name: 'Similar', exact: true }).click();
  await expect(expanded(page).getByRole('button', { name: 'Open Related Movie 12 in Discover' })).toBeVisible();
  await expanded(page).getByRole('button', { name: 'Recommended', exact: true }).click();
  await expanded(page).getByRole('button', { name: 'Open Ready or Not in Discover' }).click();
  await expect(expanded(page).getByRole('heading', { name: 'Ready or Not' })).toBeVisible();
  await expect(page.getByLabel('Discovery path')).toContainText('Related to The Hunt');
  await openControls(page);
  await expect(page.getByLabel('Related movie sources')).toBeVisible();
  await expect(page.locator('.discover-grid > .unified-movie-card')).toHaveCount(20);
  await expect(expanded(page).getByRole('heading', { name: 'Ready or Not' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Related Movie 3', exact: true })).toBeVisible();
  await expect(expanded(page).getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  await expect(expanded(page).getByRole('button', { name: 'File details', exact: true })).toBeVisible();
  await fullCard(page);
  await expect(page.getByLabel('Discovery path')).toContainText('Related to The Hunt');
  await expect.poll(() => requests.some((request) => request.tmdb_id === '2')).toBe(true);
  await expect(expanded(page).locator('.related-skeleton')).toHaveCount(0);
  await expect(expanded(page).getByText('Cast Member 1', { exact: true })).toBeVisible();
  await expect(expanded(page).getByText('Cast Member 9', { exact: true })).toBeVisible();
  await expect(expanded(page).locator('button.person-discover-button[aria-label="Open filmography for Cast Member 9"]')).toBeVisible();
  await expect(expanded(page).locator('.person-avatar img')).toHaveCount(10);
  await page.screenshot({ path: test.info().outputPath('related-desktop-1920.png') });
});

test('Plex-only owned movie resolves rich cast by exact title and year', async ({ page }) => {
  await fixtures(page);
  const plexOnly = {
    ...owned,
    tmdb_id: '',
    canonical_metadata: {
      ...owned.canonical_metadata,
      tmdb_id: '',
      directors: [{ name: 'Thomas Vinterberg' }],
      cast: credits.cast.slice(0, 3).map(({ name }) => ({ name }))
    }
  };
  await page.route(/\/api\/library(?:\?view=cards.*|\/search\/advanced)$/, (route) => route.fulfill({ json: { items: [plexOnly], count: 1, total: 1, page: 1, total_pages: 1, catalog_generation: 1, facets: {} } }));
  await page.route('**/api/library/details**', (route) => route.fulfill({ json: { item: plexOnly, catalog_generation: 1 } }));
  await page.route('**/api/tmdb/search**', (route) => route.fulfill({ json: { results: [selected], page: 1, total_pages: 1, total_results: 1 } }));
  await page.goto('/library');
  await page.getByRole('heading', { name: selected.title, exact: true }).click();
  await expect(expanded(page).getByText('Cast Member 9', { exact: true })).toBeVisible();
  await expect(expanded(page).locator('.person-avatar img')).toHaveCount(10);
  await expect(expanded(page).locator('button.person-discover-button')).toHaveCount(10);
  await expect(expanded(page).getByRole('button', { name: 'View all', exact: true })).toBeEnabled();
});

test('director and cast rail retains all loaded credits on short desktops', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 720 });
  await fixtures(page);
  const fourDirectors = Array.from({ length: 4 }, (_, i) => ({
    id: 200 + i,
    name: `Director ${i + 1}`,
    profile_url: portrait(`D${i + 1}`)
  }));
  await page.route('**/api/tmdb/details**', (route) => route.fulfill({
    json: { ...movie(new URL(route.request().url()).searchParams.get('tmdb_id')), ...credits, directors: fourDirectors }
  }));
  await expandSeed(page);
  const people = expanded(page).getByLabel('Director and top cast').locator('.person-card');
  await expect(people).toHaveCount(13);
  await expect(expanded(page).getByText('Director 4', { exact: true })).toBeVisible();
  await expect(expanded(page).getByText('Cast Member 6', { exact: true })).toBeVisible();
  await expanded(page).getByRole('button', { name: 'Scroll cast right', exact: true }).click();
  await expect(expanded(page).getByText('Cast Member 9', { exact: true })).toBeVisible();
  await expect.poll(async () => {
    const castPanel = await expanded(page).getByLabel('Director and top cast').boundingBox();
    const relationshipTabs = await expanded(page).getByLabel('Relationship source').boundingBox();
    return relationshipTabs.y - (castPanel.y + castPanel.height);
  }).toBeGreaterThanOrEqual(10);
  // Clicking a lower rail arrow may scroll the locator into view; check the
  // preserved card geometry without mistaking that for expansion positioning.
  await fullCard(page, false);
});

test('View all keeps source, page, ownership and card position through inline expansion', async ({ page }) => {
  await fixtures(page);
  await expandSeed(page);
  await expanded(page).getByRole('button', { name: 'View all', exact: true }).click();
  const sources = page.getByLabel('Related movie sources');
  await openControls(page);
  await expect(sources.getByRole('button', { name: 'All', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('navigation', { name: 'TMDB relationship pagination', exact: true })).toContainText('40');
  await sources.getByRole('button', { name: 'Similar', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Related Movie 12', exact: true })).toBeVisible();
  await page.getByLabel('Library ownership', { exact: true }).selectOption('unowned');
  const pager = page.getByRole('navigation', { name: 'TMDB relationship pagination', exact: true });
  await pager.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(pager).toContainText('Page 2');
  const target = page.locator('.discover-grid h3').first();
  await expect(target).toBeVisible();
  await target.scrollIntoViewIfNeeded();
  const title = await target.textContent();
  await target.click();
  await expect(expanded(page)).toBeVisible();
  await fullCard(page);
  await expanded(page).getByRole('heading', { name: title, exact: true }).click();
  await expect(expanded(page)).toHaveCount(0);
  await expect(sources.getByRole('button', { name: 'Similar', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByLabel('Library ownership', { exact: true })).toHaveValue('unowned');
  await expect(pager).toContainText('Page 2');
  const collapsedTarget = page.getByRole('heading', { name: title, exact: true });
  await expect(collapsedTarget).toBeVisible();
  await expect.poll(async () => collapsedTarget.evaluate((element) => {
    const card = element.closest('.unified-movie-card')?.getBoundingClientRect();
    const workspace = element.closest('.workspace')?.getBoundingClientRect();
    return Boolean(card && workspace && card.top >= workspace.top && card.bottom <= workspace.bottom);
  })).toBe(true);
});

test('bounded View all shows an exact total and stops at the final page for each source', async ({ page }) => {
  await fixtures(page);
  const recommended = Array.from({ length: 100 }, (_, index) => ({ ...movie(1000 + index), relationship_source: 'recommendations' }));
  const similar = Array.from({ length: 100 }, (_, index) => ({ ...movie(2000 + index), relationship_source: 'similar' }));
  let releaseSummary;
  const summaryGate = new Promise((resolve) => { releaseSummary = resolve; });
  await page.route('**/api/tmdb/related**', async (route) => {
    const params = new URL(route.request().url()).searchParams;
    const source = params.get('source') || 'all';
    const results = source === 'all' ? [...recommended, ...similar] : source === 'similar' ? similar : recommended;
    const pageSize = Number(params.get('page_size') || 20);
    if (params.get('summary') === '1') {
      if (source === 'all') await summaryGate;
      return route.fulfill({ json: {
        source, page_size: pageSize, source_limit: 100, total_results: results.length,
        total_pages: Math.ceil(results.length / pageSize),
        source_counts: { recommendations: source === 'similar' ? 0 : 100, similar: source === 'recommendations' ? 0 : 100 }
      } });
    }
    const pageNumber = Number(params.get('page') || 1);
    const start = (pageNumber - 1) * pageSize;
    return route.fulfill({ json: {
      source, page: pageNumber, page_size: pageSize, source_limit: 100,
      results: results.slice(start, start + pageSize), total_results: null, total_pages: null,
      has_previous: pageNumber > 1, has_next: start + pageSize < results.length
    } });
  });
  try {
    await expandSeed(page);
    await expanded(page).getByRole('button', { name: 'View all', exact: true }).click();
    await openControls(page);
    const pager = page.getByRole('navigation', { name: 'TMDB relationship pagination', exact: true }).first();
    await expect(page.getByRole('heading', { name: 'Related Movie 1000', exact: true })).toBeVisible();
    await expect(page.getByText('Counting total…', { exact: false })).toBeVisible();
    releaseSummary();
    await expect(pager).toContainText('of 200');
    await expect(page.getByText('Browse limit: up to 100 per source.', { exact: false })).toBeVisible();
    const pageSize = await page.locator('.discover-grid > .unified-movie-card').count();
    const lastPage = Math.ceil(200 / pageSize);
    for (let current = 1; current < lastPage; current += 1) {
      await pager.getByRole('button', { name: 'Next', exact: true }).click();
      await expect(pager).toContainText(`Page ${current + 1} of ${lastPage}`);
    }
    await expect(page.locator('.discover-grid > .unified-movie-card')).toHaveCount(200 - (lastPage - 1) * pageSize);
    await expect(pager.getByRole('button', { name: 'Next', exact: true })).toBeDisabled();
    await openControls(page);
    await page.getByLabel('Related movie sources').getByRole('button', { name: 'Similar', exact: true }).click();
    await expect(pager).toContainText('of 100');
    await expect(page.getByRole('heading', { name: 'Related Movie 2000', exact: true })).toBeVisible();
  } finally {
    releaseSummary();
  }
});

test('a failed relationship count preserves loaded cards and can be retried', async ({ page }) => {
  await fixtures(page);
  let failSummary = true;
  await page.route('**/api/tmdb/related**', async (route) => {
    const params = new URL(route.request().url()).searchParams;
    if (params.get('summary') === '1') {
      if (failSummary) return route.fulfill({ status: 502, json: { error: 'Relationship provider unavailable' } });
      return route.fulfill({ json: { source: 'all', page_size: 20, source_limit: 100, total_results: 40, total_pages: 2 } });
    }
    const pageNumber = Number(params.get('page') || 1);
    const results = pageNumber === 1
      ? [selected, ...Array.from({ length: 19 }, (_, index) => movie(index + 3))]
      : Array.from({ length: 20 }, (_, index) => movie(index + 22));
    return route.fulfill({ json: {
      source: 'all', page: pageNumber, page_size: 20, source_limit: 100, results,
      total_results: null, total_pages: null, has_previous: pageNumber > 1, has_next: pageNumber === 1
    } });
  });
  await expandSeed(page);
  await expanded(page).getByRole('button', { name: 'View all', exact: true }).click();
  await openControls(page);
  await expect(page.getByRole('heading', { name: 'Ready or Not', exact: true })).toBeVisible();
  await expect(page.getByText('Exact count unavailable.', { exact: false })).toBeVisible();
  const pager = page.getByRole('navigation', { name: 'TMDB relationship pagination', exact: true }).first();
  await pager.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(pager).toContainText('Page 2');
  failSummary = false;
  await page.getByRole('button', { name: 'Retry count', exact: true }).click();
  await expect(pager).toContainText('of 40');
  await expect(page.getByText('Exact count unavailable.', { exact: false })).toHaveCount(0);
});

test('provider failure remains local and short desktop keeps all corners visible', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await fixtures(page, { fail: true });
  await expandSeed(page);
  await expect(expanded(page).getByRole('status')).toContainText('Relationship provider unavailable');
  await expect(expanded(page).getByRole('button', { name: 'Retry', exact: true })).toBeVisible();
  await expect(expanded(page).getByLabel('Director and top cast')).toBeVisible();
  await expect(expanded(page).locator('.movie-expanded-curation')).toBeVisible();
  await expect(expanded(page).getByRole('button', { name: 'Add to list', exact: true })).toBeVisible();
  await expect(expanded(page).locator('.related-tile')).toHaveCount(0);
  const compactGeometry = await expanded(page).evaluate((card) => {
    const facts = card.querySelector('.movie-expanded-facts').getBoundingClientRect();
    const curation = card.querySelector('.movie-expanded-curation').getBoundingClientRect();
    const portraitWidths = [...card.querySelectorAll('.person-card .person-avatar')]
      .map((portrait) => portrait.getBoundingClientRect().width);
    const portraitsFit = [...card.querySelectorAll('.person-card')].every((person) => {
      const personBox = person.getBoundingClientRect();
      const portraitBox = person.querySelector('.person-avatar').getBoundingClientRect();
      return portraitBox.left >= personBox.left && portraitBox.right <= personBox.right;
    });
    return {
      curationGap: curation.top - facts.bottom,
      portraitWidthDelta: Math.max(...portraitWidths) - Math.min(...portraitWidths),
      portraitsFit
    };
  });
  expect(compactGeometry.curationGap).toBeLessThanOrEqual(12);
  expect(compactGeometry.portraitWidthDelta).toBeLessThanOrEqual(1);
  expect(compactGeometry.portraitsFit).toBe(true);
  await fullCard(page);
  await page.screenshot({ path: 'test-results/related-desktop-720.png' });
});

test('late TMDB details recenter the finished card inside a short desktop viewport', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await fixtures(page, { detailsDelay: 500 });
  await expandSeed(page);
  await expect(expanded(page).getByRole('button', { name: 'Open biography for Thomas Vinterberg', exact: true })).toBeVisible();
  await fullCard(page);
});

test('Short desktop keeps expanded card layout and lets lower content scroll below pinned controls', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await fixtures(page);
  await expandSeed(page);
  await expect(expanded(page).getByRole('button', { name: 'Open biography for Thomas Vinterberg', exact: true })).toBeVisible();
  await fullCard(page);
  const initial = await expanded(page).boundingBox();
  await page.locator('main.workspace').evaluate(element => element.scrollTo({ top: element.scrollTop + 500, behavior: 'instant' }));
  await expect(expanded(page).getByRole('button', { name: 'View all', exact: true })).toBeInViewport();
  const after = await expanded(page).boundingBox();
  expect(after.height).toBeCloseTo(initial.height, 0);
  await expect(page.getByRole('button', { name: 'Search, filters & selection', exact: true })).toBeInViewport();
  await expect(page.locator('.workspace-chrome:visible')).toHaveCSS('background-color', 'rgb(0, 0, 0)');
});

test('collection shares one row with mandatory lists and list chips stay bounded', async ({ page }) => {
  const lists = Array.from({ length: 7 }, (_, index) => ({
    id: `list-${index + 1}`,
    name: `Movie List ${index + 1}`,
    movies: [seed]
  }));
  await fixtures(page, { lists });
  await page.route('**/api/tmdb/details**', (route) => route.fulfill({
    json: { ...movie(new URL(route.request().url()).searchParams.get('tmdb_id')), ...credits, collection: { id: '10', name: 'The Hunt Collection' } }
  }));
  await page.route('**/api/tmdb/collection**', (route) => route.fulfill({
    json: { id: '10', name: 'The Hunt Collection', parts: [seed] }
  }));
  await expandSeed(page);
  const collectionPanel = expanded(page).locator('.collection-panel');
  const listsPanel = expanded(page).locator('.lists-panel');
  await expect(collectionPanel).toBeVisible();
  await expect(listsPanel).toBeVisible();
  await expect(expanded(page).getByRole('button', { name: 'Add to list', exact: true })).toBeVisible();
  await expect(listsPanel.locator('.list-chip')).toHaveCount(5);
  await expect(listsPanel.getByText('+2 more', { exact: true })).toBeVisible();
  const alignment = await expanded(page).evaluate((card) => {
    const facts = card.querySelector('.movie-expanded-facts').getBoundingClientRect();
    const curation = card.querySelector('.movie-expanded-curation').getBoundingClientRect();
    const collection = card.querySelector('.collection-panel').getBoundingClientRect();
    const lists = card.querySelector('.lists-panel').getBoundingClientRect();
    return {
      panelTopDelta: Math.abs(collection.top - lists.top),
      panelBottomDelta: Math.abs(collection.bottom - lists.bottom),
      curationGap: curation.top - facts.bottom
    };
  });
  expect(alignment.panelTopDelta).toBeLessThanOrEqual(1);
  expect(alignment.panelBottomDelta).toBeLessThanOrEqual(1);
  expect(alignment.curationGap).toBeLessThanOrEqual(12);
  const posterGeometry = await expanded(page).evaluate((card) => {
    const poster = card.querySelector('.unified-movie-poster').getBoundingClientRect();
    const main = card.querySelector('.unified-movie-main').getBoundingClientRect();
    return { ratio: poster.height / poster.width, fits: poster.top >= main.top && poster.bottom <= main.bottom };
  });
  expect(posterGeometry.ratio).toBeCloseTo(1.5, 1);
  expect(posterGeometry.fits).toBe(true);
  await fullCard(page);
});

for (const surface of ['library', 'movie-lists', 'ai-control', 'pick', 'browse']) {
  test(`${surface} uses shared rail and returns to original expanded card and scroll`, async ({ page }) => {
    await fixtures(page);
    await page.route(/\/api\/library(?:\?view=cards.*|\/search\/advanced)$/, (route) => route.fulfill({ json: { items: [owned], count: 1, catalog_generation: 1 } }));
    await page.route('**/api/ai-control/preview', (route) => route.fulfill({ json: {
      state: 'valid_plan', plan_id: 'related-preview', action: 'list', summary: 'Related preview',
      message: 'One movie', total_matches: 1, page_size: 20, items: [{ ...selected, selection_key: 'one' }], blocked: [], warnings: []
    } }));
    await page.route('**/api/ollama/recommend', (route) => route.fulfill({ json: { results: [selected], model: 'Fixture' } }));
    await page.route('**/api/explore/indexers', (route) => route.fulfill({ json: { indexers: [{ id: 'fixture', name: 'Fixture' }] } }));
    await page.route('**/api/explore/browse**', (route) => route.fulfill({ json: { results: [{ ...selected, parsed_title: selected.title, parsed_year: selected.year, metadata: selected, variants: [{ title: 'Ready.or.Not.1080p', resolution: '1080p', indexer: 'Fixture', seeders: 20, size_human: '2 GB' }] }] } }));
    await page.route('**/api/metadata?**', (route) => route.fulfill({ json: selected }));
    await page.goto(['pick', 'browse'].includes(surface) ? '/discover' : `/${surface}`);
    if (surface === 'ai-control') {
      await page.getByPlaceholder('Tell CP what to find, list, download, or delete...').fill('List a movie');
      await page.getByRole('button', { name: 'Preview command' }).click();
    }
    if (surface === 'pick') {
      await page.getByRole('button', { name: 'Pick My Movie', exact: true }).click();
      await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
      await page.getByPlaceholder('Something funny but a little sad, maybe an indie movie with a warm ending...').fill('A thriller');
      await page.getByRole('button', { name: 'Ask AI', exact: true }).click();
    }
    if (surface === 'browse') {
      await page.getByRole('button', { name: 'Browse Indexers', exact: true }).click();
      await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
      await page.getByRole('button', { name: 'Load latest', exact: true }).click();
    }
    await page.getByRole('heading', { name: selected.title, exact: true }).click();
    await expect(expanded(page).getByRole('button', { name: 'View all', exact: true })).toBeVisible();
    await fullCard(page);
    const prior = await settledWorkspaceScroll(page);
    await expanded(page).getByRole('button', { name: 'View all', exact: true }).click();
    await openControls(page);
    await expect(page.getByLabel('Related movie sources')).toBeVisible();
    await page.getByLabel('Discovery path').getByRole('button', { name: 'Back', exact: true }).click();
    await expect(expanded(page).getByRole('heading', { name: selected.title, exact: true })).toBeVisible();
    // Returning to an expanded movie keeps controls temporarily collapsed.
    if (['pick', 'browse'].includes(surface)) await expect(page.getByRole('button', { name: 'Search, filters & selection', exact: true })).toHaveAttribute('aria-expanded', 'false');
    await expect.poll(() => page.locator('.workspace').evaluate((element) => element.scrollTop)).toBe(prior);
    await fullCard(page);
  });
}

test('browser Back and breadcrumbs reverse deeper related exploration', async ({ page }) => {
  await fixtures(page);
  await expandSeed(page);
  await fullCard(page);
  const prior = await settledWorkspaceScroll(page);
  await expanded(page).getByRole('button', { name: 'View all', exact: true }).click();
  await page.getByRole('heading', { name: 'Ready or Not', exact: true }).click();
  await fullCard(page);
  await expanded(page).getByRole('button', { name: 'View all', exact: true }).click();
  await expect(page.getByLabel('Discovery path')).toContainText('Related to Ready or Not');
  await page.goBack();
  await expect(expanded(page).getByRole('heading', { name: 'Ready or Not', exact: true })).toBeVisible();
  await expect(page.locator('.discover-grid > .unified-movie-card')).toHaveCount(20);
  await fullCard(page);
  await page.goBack();
  await expect(expanded(page).getByRole('heading', { name: 'The Hunt', exact: true })).toBeVisible();
  await expect.poll(() => page.locator('.workspace').evaluate((element) => element.scrollTop)).toBe(prior);
});

test('unowned tile keeps Discover source, streaming and watchlist actions; breadcrumb restores original expansion', async ({ page }) => {
  await fixtures(page);
  await expandSeed(page);
  await expanded(page).getByRole('button', { name: 'Open Related Movie 3 in Discover' }).click();
  await expect(page.locator('.discover-grid > .unified-movie-card')).toHaveCount(20);
  await expect(expanded(page).getByRole('heading', { name: 'Related Movie 3', exact: true })).toBeVisible();
  await expect(expanded(page).getByRole('button', { name: 'Find sources', exact: true })).toBeVisible();
  await expect(expanded(page).getByRole('button', { name: 'Stream', exact: true })).toBeVisible();
  await expect(expanded(page).getByLabel('Add Related Movie 3 to watchlist', { exact: true })).toBeAttached();
  await expect(expanded(page).getByRole('button', { name: 'Play', exact: true })).toHaveCount(0);
  await page.getByLabel('Discovery path').getByRole('button', { name: 'Discover', exact: true }).click();
  await expect(expanded(page).getByRole('heading', { name: 'The Hunt', exact: true })).toBeVisible();
  await fullCard(page);
});

test('Back during relationship loading ignores late results and preserves the expanded origin', async ({ page }) => {
  const requests = await fixtures(page, { delay: 600 });
  await expandSeed(page);
  await expanded(page).getByRole('button', { name: 'View all', exact: true }).click();
  await expect.poll(() => requests.length).toBeGreaterThanOrEqual(2);
  await page.getByLabel('Discovery path').getByRole('button', { name: 'Back', exact: true }).click();
  await expect.poll(() => requests.every((request) => request.completed)).toBe(true);
  await expect(expanded(page).getByRole('heading', { name: 'The Hunt', exact: true })).toBeVisible();
  await expect(page.getByLabel('Related movie sources')).toHaveCount(0);
  await expanded(page).getByRole('button', { name: 'View all', exact: true }).click();
  await openControls(page);
  await expect(page.getByLabel('Related movie sources')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Ready or Not', exact: true })).toBeVisible();
});

test('a failed Similar source does not block Recommended in Discover', async ({ page }) => {
  await fixtures(page, { fail: 'similar' });
  await expandSeed(page);
  await expanded(page).getByRole('button', { name: 'View all', exact: true }).click();
  await openControls(page);
  await page.getByLabel('Related movie sources').getByRole('button', { name: 'Similar', exact: true }).click();
  await expect(page.getByText('Relationship provider unavailable', { exact: true })).toBeVisible();
  await page.getByLabel('Related movie sources').getByRole('button', { name: 'Recommended', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ready or Not', exact: true })).toBeVisible();
});

for (const height of [1080, 900, 720]) {
  test(`dense metadata fits at desktop height ${height}`, async ({ page }) => {
    await page.setViewportSize({ width: 1920, height });
    await fixtures(page);
    const richMovie = { ...seed, title: 'The Hunt: A Very Long Movie Title With a Subtitle', summary: seed.summary.repeat(7) };
    await page.route('**/api/tmdb/discover**', (route) => route.fulfill({ json: { results: [richMovie], page: 1, total_pages: 1, total_results: 1 } }));
    await page.route('**/api/tmdb/details**', (route) => route.fulfill({ json: { ...richMovie, ...credits, tagline: 'The truth is rarely pure and never simple. '.repeat(3), writers: [{ name: 'A Very Long Writer Name' }, { name: 'Another Writer' }], collection: { id: '10', name: 'A Long Running Collection' } } }));
    await page.route('**/api/tmdb/collection**', (route) => route.fulfill({ json: { id: '10', name: 'A Long Running Collection', parts: [richMovie] } }));
    await page.goto('/discover');
    await page.getByRole('heading', { name: richMovie.title, exact: true }).click();
    await expect(expanded(page).getByText('Another Writer', { exact: false })).toBeVisible();
    await expect(expanded(page).locator('.movie-expanded-curation')).toBeVisible();
    await expect(expanded(page).getByRole('button', { name: 'Add to list', exact: true })).toBeVisible();
    await fullCard(page);
    const upperRowGeometry = await expanded(page).evaluate((card) => {
      const poster = card.querySelector('.unified-movie-poster').getBoundingClientRect();
      const body = card.querySelector('.unified-movie-body').getBoundingClientRect();
      const curation = card.querySelector('.movie-expanded-curation').getBoundingClientRect();
      return {
        topDelta: Math.abs(poster.top - body.top),
        bottomDelta: Math.abs(poster.bottom - curation.bottom),
        imageFit: getComputedStyle(card.querySelector('.unified-movie-poster img')).objectFit
      };
    });
    expect(upperRowGeometry.topDelta).toBeLessThanOrEqual(1);
    if (height > 950) expect(upperRowGeometry.bottomDelta).toBeLessThanOrEqual(1);
    expect(upperRowGeometry.imageFit).toBe('cover');
    const mainOverflow = await expanded(page).locator('.unified-movie-body').evaluate((body) => body.scrollHeight - body.clientHeight);
    expect(mainOverflow).toBeLessThanOrEqual(1);
    const plotLineFit = await expanded(page).locator('.movie-card-plot, .movie-summary-expanded').first().evaluate((plot) => {
      const lineHeight = Number.parseFloat(getComputedStyle(plot).lineHeight);
      return plot.getBoundingClientRect().height / lineHeight;
    });
    expect(Math.abs(plotLineFit - Math.round(plotLineFit))).toBeLessThan(.08);
    await expanded(page).getByRole('button', { name: 'Read full plot' }).click();
    await expect(page.getByRole('dialog', { name: `Plot of ${richMovie.title}` })).toContainText(richMovie.summary);
    await page.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).click();
  });
}
