import { expect, test } from '@playwright/test';

const makeMovies = () => Array.from({ length: 12 }, (_, index) => ({
  tmdb_id: String(9900 + index), imdb_id: `tt990${index}`, title: `Following fixture ${index + 1}`,
  year: '2026', poster_url: '', followed_at: 1000 - index,
  status: index < 4 ? 'available' : index === 11 ? 'owned' : 'watching',
  release_date: index === 3 || (index >= 8 && index < 11) ? '2099-08-20' : index === 7 ? '' : '2020-01-01'
}));

async function openFollowing(page, initial = makeMovies()) {
  const state = { movies: initial };
  await page.route('**/api/user/followed-releases**', route => route.fulfill({ json: {
    movies: state.movies, newly_available: [], removed_owned: [], curation_generation: 1
  } }));
  await page.route('**/api/player/continue-watching**', route => route.fulfill({ json: { items: [{
    path_key: 'following-resume', title: 'Resume fixture', progress: .3, remaining_seconds: 3600, poster_url: ''
  }] } }));
  await page.route('**/api/tv/continue-watching**', route => route.fulfill({ json: { items: [] } }));
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  const panel = page.locator('.release-panel');
  await expect(panel.getByRole('combobox', { name: 'Filter followed movies' })).toBeVisible();
  return { panel, state };
}

for (const [width, playback] of [[1600, true], [1920, true], [1600, false]]) {
  test(`Following compact heading shares its action row at ${width}px with playback ${playback}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1080 });
    if (!playback) await page.route('**/api/player/continue-watching**', route => route.fulfill({ json: { items: [] } }));
    const { panel } = await openFollowing(page, playback ? makeMovies() : []);
    if (!playback) {
      // Override the helper's playback fixture and reload through the real Home path.
      await page.route('**/api/player/continue-watching**', route => route.fulfill({ json: { items: [] } }));
      await page.reload();
      await expect(page.locator('.continue-watching-panel')).toHaveCount(0);
    }
    const heading = panel.getByRole('heading', { name: /^Followed movies/ });
    for (const value of ['all', 'available', 'monitoring', 'awaiting']) {
      await panel.getByRole('combobox', { name: 'Filter followed movies' }).selectOption(value);
      const titleBox = await heading.boundingBox();
      const cardBox = await panel.boundingBox();
      for (const control of [
        panel.getByRole('button', { name: 'Download all available followed movies' }),
        panel.locator('.release-available-indicator'),
        panel.getByRole('button', { name: 'Scan followed releases', exact: true }),
        panel.locator('.release-filter-count'),
        panel.getByRole('combobox', { name: 'Filter followed movies' })
      ]) {
        const box = await control.boundingBox();
        expect(Math.abs(box.y + box.height / 2 - titleBox.y - titleBox.height / 2)).toBeLessThanOrEqual(1);
        expect(box.x).toBeGreaterThanOrEqual(titleBox.x + titleBox.width);
        expect(box.x + box.width).toBeLessThanOrEqual(cardBox.x + cardBox.width);
      }
      await expect(heading).toHaveText('Followed movies');
      await expect(panel.locator('.screen-kicker')).toHaveText('Release watchlist');
      // Detect a selected label wrapping or clipping inside the compact dropdown.
      const selectedLabel = await panel.getByRole('combobox', { name: 'Filter followed movies' }).evaluate(select => {
        const controlStyle = getComputedStyle(select);
        const selectedStyle = getComputedStyle(select.selectedOptions[0]);
        const context = document.createElement('canvas').getContext('2d');
        context.font = `${selectedStyle.fontWeight} ${selectedStyle.fontSize} ${selectedStyle.fontFamily}`;
        const optionWidth = context.measureText(select.selectedOptions[0].textContent.trim()).width;
        context.font = `${controlStyle.fontWeight} ${controlStyle.fontSize} ${controlStyle.fontFamily}`;
        const labelWidth = Math.max(optionWidth, context.measureText(select.selectedOptions[0].textContent.trim()).width);
        return { labelWidth, availableWidth: select.clientWidth - parseFloat(controlStyle.paddingLeft) - parseFloat(controlStyle.paddingRight), font: context.font };
      });
      expect(selectedLabel.labelWidth, `${value}: ${selectedLabel.font}`).toBeLessThanOrEqual(selectedLabel.availableWidth);
      expect(await panel.locator('.section-heading').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
      const listBox = await panel.locator('.release-list').boundingBox();
      expect(listBox.y - cardBox.y).toBeLessThanOrEqual(77);
      expect(Math.abs(listBox.height - 190)).toBeLessThanOrEqual(1);
    }
    await panel.screenshot({ path: test.info().outputPath(`following-compact-${width}-${playback}.png`) });
  });
}

test('Following filters use existing statuses and update count while availability badge stays global', async ({ page }) => {
  const { panel } = await openFollowing(page);
  const filter = panel.getByRole('combobox', { name: 'Filter followed movies' });
  await expect(filter.locator('option')).toHaveText(['All', 'Available', 'Monitoring', 'Awaiting release']);
  await expect(panel.getByRole('button', { name: 'View all', exact: true })).toHaveCount(0);
  await expect(page.getByRole('dialog', { name: 'Followed releases', exact: true })).toHaveCount(0);
  const toolbar = await panel.locator('.release-heading-actions').evaluate(element => ({
    fits: element.scrollWidth <= element.clientWidth,
    lefts: [...element.children].map(child => child.getBoundingClientRect().left)
  }));
  expect(toolbar.fits).toBe(true);
  expect(toolbar.lefts).toHaveLength(5);
  expect(toolbar.lefts).toEqual([...toolbar.lefts].sort((a, b) => a - b));
  for (const [value, count, label] of [['all', 12, null], ['available', 4, 'Available'], ['monitoring', 4, 'Monitoring'], ['awaiting', 3, 'Awaiting release']]) {
    await filter.selectOption(value);
    await expect(panel.locator('.release-item')).toHaveCount(count);
    await expect(panel.locator('.release-filter-count')).toHaveText(String(count));
    await expect(panel.getByRole('img', { name: '4 available followed movies' })).toBeVisible();
    if (label) await expect(panel.locator('.release-item em')).toHaveText(Array(count).fill(label));
  }
  await filter.selectOption('available');
  await expect(panel.getByText('Following fixture 4', { exact: true })).toBeVisible();
  await expect(panel.locator('.release-item em').first()).toHaveCSS('color', 'rgb(34, 197, 94)');
  await filter.selectOption('monitoring');
  await expect(panel.getByText('Following fixture 8', { exact: true })).toBeVisible();
  await expect(panel.locator('.release-item em').first()).toHaveCSS('color', 'rgb(212, 175, 55)');
  await panel.screenshot({ path: test.info().outputPath('following-monitoring.png') });
  await filter.selectOption('awaiting');
  await expect(panel.getByText('Following fixture 4', { exact: true })).toHaveCount(0);
  await expect(panel.locator('.release-item em').first()).toHaveCSS('color', 'rgb(163, 166, 173)');
  await panel.screenshot({ path: test.info().outputPath('following-awaiting.png') });
  await filter.selectOption('all');
  await expect(panel.locator('.release-item').filter({ has: page.getByText('Following fixture 12', { exact: true }) })).toContainText('Owned');
  await panel.screenshot({ path: test.info().outputPath('following-header.png') });
});

test('download previews all available movies regardless of filter and preserves explicit shared submission', async ({ page }) => {
  const previews = [];
  const submissions = [];
  await page.route('**/api/sources/review/preview', route => {
    const payload = route.request().postDataJSON(); previews.push(payload);
    return route.fulfill({ json: { rows: payload.movies.map((movie, index) => ({
      ...movie, quality: '1080p', selected: index < 2, status: index < 2 ? 'ready' : 'blocked',
      reason: index < 2 ? '' : 'No trusted 1080p source found',
      variant: index < 2 ? { title: `${movie.title} 1080p WEBRip`, indexer: 'Trusted fixture', size_human: '1 GB' } : null,
      variants_by_quality: { '1080p': index < 2 ? { title: `${movie.title} 1080p WEBRip`, indexer: 'Trusted fixture' } : null, '4K': null }
    })), defaults: { quality: '1080p', policy: 'shared' } } });
  });
  await page.route('**/api/sources/review/submit', route => {
    submissions.push(route.request().postDataJSON());
    return route.fulfill({ json: { submitted_count: 2 } });
  });
  const { panel } = await openFollowing(page);
  for (const filter of ['all', 'available', 'monitoring', 'awaiting']) {
    await panel.getByRole('combobox').selectOption(filter);
    await panel.getByRole('button', { name: 'Download all available followed movies' }).click();
    const dialog = page.getByRole('dialog', { name: 'Download available followed movies', exact: true });
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('.source-review-row')).toHaveCount(4);
    expect(previews.at(-1).movies.map(movie => movie.tmdb_id)).toEqual(['9900', '9901', '9902', '9903']);
    expect(previews.at(-1).policy).toBeUndefined();
    expect(previews.at(-1).quality).toBeUndefined();
    expect(submissions).toHaveLength(0);
    await expect(dialog).toContainText('2 selected for download');
    await expect(dialog).toContainText('2 movies had no trusted source.');
    if (filter === 'awaiting') {
      await dialog.getByRole('button', { name: 'Submit selected to qBittorrent' }).click();
      await expect.poll(() => submissions.length).toBe(1);
      expect(submissions[0].rows.filter(row => row.status === 'ready' && row.selected).map(row => row.tmdb_id)).toEqual(['9900', '9901']);
      await expect(dialog).toBeHidden();
    } else await dialog.getByRole('button', { name: 'Close source review' }).click();
  }
});

test('scan refreshes selected filter and the global available count from the same followed state', async ({ page }) => {
  const { panel, state } = await openFollowing(page);
  await panel.getByRole('combobox').selectOption('monitoring');
  await expect(panel.locator('.release-filter-count')).toHaveText('4');
  state.movies[4] = { ...state.movies[4], status: 'available' };
  await panel.getByRole('button', { name: 'Scan followed releases', exact: true }).click();
  await expect(panel.locator('.release-item')).toHaveCount(3);
  await expect(panel.locator('.release-filter-count')).toHaveText('3');
  await expect(panel.getByRole('img', { name: '5 available followed movies' })).toBeVisible();
});

test('empty filter and empty followed list retain zero counts and safe download state', async ({ page }) => {
  const { panel } = await openFollowing(page, [{ ...makeMovies()[4] }]);
  await expect(panel.getByRole('button', { name: 'Download all available followed movies' })).toBeDisabled();
  await expect(panel.getByRole('img', { name: '0 available followed movies' })).toBeVisible();
  await panel.getByRole('combobox').selectOption('available');
  await expect(panel.locator('.release-filter-count')).toHaveText('0');
  await expect(panel).toContainText('No followed releases in this filter.');
  await page.route('**/api/user/followed-releases**', route => route.fulfill({ json: { movies: [], newly_available: [], removed_owned: [], curation_generation: 2 } }));
  await page.reload();
  await expect(panel).toContainText('No followed releases yet.');
  await expect(panel.locator('.release-filter-count')).toHaveText('0');
});

test('cancelled pending source review cannot reopen on navigation or after late response', async ({ page }) => {
  let release;
  const previewResponses = [];
  page.on('response', response => { if (response.url().endsWith('/api/sources/review/preview')) previewResponses.push(response); });
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/api/sources/review/preview', async route => {
    await gate;
    await route.fulfill({ json: { rows: [], defaults: { quality: '1080p' } } });
  });
  const { panel } = await openFollowing(page);
  await page.getByRole('button', { name: 'Library', exact: true }).click();
  await expect(page).toHaveURL(/\/library$/);
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expect(panel).toBeVisible();
  await panel.getByRole('button', { name: 'Download all available followed movies' }).click();
  const dialog = page.getByRole('dialog', { name: 'Download available followed movies', exact: true });
  await expect(dialog).toContainText('Finding trusted sources');
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(panel.getByRole('button', { name: 'Download all available followed movies' })).toBeFocused();
  await panel.getByRole('button', { name: 'Download all available followed movies' }).click();
  await expect(dialog).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/\/library$/);
  await expect(dialog).toBeHidden();
  release();
  await expect.poll(() => previewResponses.length).toBe(2);
  await Promise.all(previewResponses.map(response => response.finished()));
  await page.goForward();
  await expect(panel).toBeVisible();
  await expect(dialog).toBeHidden();
});

test('failed source preview remains reviewable and can be retried without queueing', async ({ page }) => {
  await page.route('**/api/sources/review/preview', route => route.fulfill({ status: 503, json: { error: 'Trusted source fixture unavailable' } }));
  const { panel } = await openFollowing(page);
  await panel.getByRole('button', { name: 'Download all available followed movies' }).click();
  const dialog = page.getByRole('dialog', { name: 'Download available followed movies', exact: true });
  await expect(dialog).toContainText('Trusted source fixture unavailable');
  await expect(dialog.getByRole('button', { name: 'Submit selected to qBittorrent' })).toBeDisabled();
  await dialog.getByRole('button', { name: 'Close source review' }).click();
  await page.route('**/api/sources/review/preview', route => route.fulfill({ json: { rows: [], defaults: {} } }));
  await panel.getByRole('button', { name: 'Download all available followed movies' }).click();
  await expect(dialog).not.toContainText('Trusted source fixture unavailable');
});
