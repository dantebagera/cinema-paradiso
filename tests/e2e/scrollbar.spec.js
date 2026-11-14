import { expect, test } from '@playwright/test';

// Headless Chromium hides native scrollbar paint by default. Exercise the
// actual visible native control as well as its computed styles.
test.use({ launchOptions: { ignoreDefaultArgs: ['--hide-scrollbars'] } });

async function openFollowing(page) {
  const movies = Array.from({ length: 12 }, (_, index) => ({
    tmdb_id: String(9800 + index), title: `Scrollbar Movie ${index + 1}`,
    year: '2026', status: 'available', release_date: '2099-08-20',
    followed_at: 1000 - index, updated_at: 1000 - index, poster_url: ''
  }));
  await page.route('**/api/user/followed-releases**', route => route.fulfill({ json: {
    movies, newly_available: [], removed_owned: [], curation_generation: 1
  } }));
  await page.route('**/api/player/continue-watching**', route => route.fulfill({ json: { items: [{
    path_key: 'scrollbar-resume', title: 'Resume fixture', progress: 0.3,
    remaining_seconds: 3600, poster_url: ''
  }] } }));
  await page.route('**/api/tv/continue-watching**', route => route.fulfill({ json: { items: [] } }));
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  const list = page.locator('.release-panel .release-list');
  await expect(list.locator('.release-item')).toHaveCount(12);
  await page.mouse.move(0, 0);
  await page.locator('.brand-lockup').click();
  await expect.poll(() => list.evaluate(el => el.scrollHeight > el.clientHeight)).toBe(true);
  return list;
}

async function scrollbarPaint(scroller) {
  return scroller.evaluate(el => {
    const bar = getComputedStyle(el, '::-webkit-scrollbar');
    const thumb = getComputedStyle(el, '::-webkit-scrollbar-thumb');
    return {
      ink: parseFloat(bar.width) - parseFloat(thumb.borderLeftWidth) - parseFloat(thumb.borderRightWidth),
      width: bar.width, color: thumb.backgroundColor,
      track: getComputedStyle(el, '::-webkit-scrollbar-track').backgroundColor,
      buttons: getComputedStyle(el, '::-webkit-scrollbar-button').display,
      transition: thumb.transitionDuration
    };
  });
}

test('Following native scrollbar has a 2px reveal line on hover and keyboard focus', async ({ page }) => {
  const list = await openFollowing(page);
  const idle = await scrollbarPaint(list);
  expect(idle.ink).toBe(2);
  expect(idle.width).toBe('8px');
  expect(idle.track).toBe('rgba(0, 0, 0, 0)');
  expect(idle.buttons).toBe('none');
  await expect.poll(async () => (await scrollbarPaint(list)).color).toBe('rgba(0, 0, 0, 0)');
  const before = await list.boundingBox();
  await list.hover();
  await expect.poll(async () => (await scrollbarPaint(list)).color).not.toBe('rgba(0, 0, 0, 0)');
  expect(await list.boundingBox()).toEqual(before);
  await page.locator('.release-panel').screenshot({ path: test.info().outputPath('following-hover.png') });
  await page.mouse.move(0, 0);
  await expect.poll(async () => (await scrollbarPaint(list)).color).toBe('rgba(0, 0, 0, 0)');
  await list.locator('.release-item').first().focus();
  await expect.poll(async () => (await scrollbarPaint(list)).color).not.toBe('rgba(0, 0, 0, 0)');
});

test('scroll activity reveals only the scrolled element and expires after idle', async ({ page }) => {
  const list = await openFollowing(page);
  const sidebar = page.locator('.nav-stack');
  for (const offset of [100, 180]) {
    await list.evaluate((el, top) => { el.scrollTop = top; }, offset);
    await expect(list).toHaveAttribute('data-cp-scrolling', '');
    await expect(sidebar).not.toHaveAttribute('data-cp-scrolling');
    await expect.poll(async () => (await scrollbarPaint(list)).color).not.toBe('rgba(0, 0, 0, 0)');
    await expect(list).not.toHaveAttribute('data-cp-scrolling', { timeout: 2500 });
    await expect.poll(async () => (await scrollbarPaint(list)).color).toBe('rgba(0, 0, 0, 0)');
  }
  await page.locator('.release-panel').screenshot({ path: test.info().outputPath('following-idle.png') });
});

test('wheel, keyboard, native dragging and Following filters keep scrolling', async ({ page }) => {
  const list = await openFollowing(page);
  await list.hover();
  await page.mouse.wheel(0, 140);
  await expect.poll(() => list.evaluate(el => el.scrollTop)).toBeGreaterThan(0);
  await list.locator('.release-item').first().focus();
  await page.keyboard.press('PageDown');
  await expect.poll(() => list.evaluate(el => el.scrollTop)).toBeGreaterThan(140);
  await list.evaluate(el => { el.scrollTop = 0; });
  const bounds = await list.boundingBox();
  await page.mouse.move(bounds.x + bounds.width - 4, bounds.y + 12);
  await page.mouse.down();
  await page.mouse.move(bounds.x + bounds.width - 4, bounds.y + 90, { steps: 8 });
  await page.mouse.up();
  await expect.poll(() => list.evaluate(el => el.scrollTop)).toBeGreaterThan(0);
  await list.locator('.release-item').last().scrollIntoViewIfNeeded();
  await expect(list.locator('.release-item').last()).toBeInViewport();
  await expect(list).toHaveAttribute('data-cp-scrolling', '');
  await page.locator('.release-panel').getByRole('combobox', { name: 'Filter followed movies' }).selectOption('available');
  await expect(list.locator('.release-item')).toHaveCount(12);
  await expect.poll(() => list.evaluate(el => el.scrollTop)).toBe(0);
  await page.locator('.nav-stack').getByRole('button', { name: /Library/ }).first().click();
  await page.goBack();
  await expect(page.locator('.release-panel .release-item')).toHaveCount(12);
});

test('shared scrollbar styling preserves hidden horizontal rails and reduced motion', async ({ page }) => {
  const list = await openFollowing(page);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  expect((await scrollbarPaint(list)).transition).toBe('0s');
  // Exercise the actual shared rail CSS, without making the fixture a production component.
  await page.evaluate(() => {
    const fixture = document.createElement('div');
    fixture.id = 'scrollbar-horizontal-fixture';
    fixture.className = 'horizontal-card-rail';
    fixture.style.cssText = 'position:fixed;left:260px;bottom:24px;width:300px;height:70px;z-index:2000';
    const rail = document.createElement('div');
    rail.id = 'scrollbar-horizontal-track';
    rail.className = 'horizontal-card-rail-track';
    rail.style.cssText = 'display:block;width:300px;height:60px;overflow-x:auto';
    const content = document.createElement('div');
    content.style.cssText = 'width:900px;height:40px';
    rail.appendChild(content);
    fixture.appendChild(rail);
    document.body.appendChild(fixture);
  });
  const rail = page.locator('#scrollbar-horizontal-track');
  expect(await rail.evaluate(el => getComputedStyle(el).scrollbarWidth)).toBe('none');
  expect(await rail.evaluate(el => getComputedStyle(el, '::-webkit-scrollbar').display)).toBe('none');
  await rail.evaluate(el => { el.scrollLeft = 120; });
  await expect(rail).toHaveAttribute('data-cp-scrolling', '');
  expect(await rail.evaluate(el => el.scrollLeft)).toBe(120);
  // Removing the rail class represents an ordinary native horizontal overflow container.
  await rail.evaluate(el => { el.className = ''; });
  expect(await rail.evaluate(el => getComputedStyle(el, '::-webkit-scrollbar').height)).toBe('8px');
});
