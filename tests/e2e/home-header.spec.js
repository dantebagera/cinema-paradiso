import { expect, test } from '@playwright/test';

const description = 'A richer movie library. More to discover. AI to guide you. Ready to stream.';

async function openHeader(page) {
  await page.goto('/');
  const header = page.getByRole('region', { name: 'Home', exact: true });
  await expect(header.getByRole('heading', { name: 'Your movie archive, under command.', exact: true })).toBeVisible();
  return header;
}

async function expectReadableHeader(header) {
  await expect(header.getByText(description, { exact: true })).toBeVisible();
  const layout = await header.evaluate(element => {
    const box = element.getBoundingClientRect();
    const rect = node => {
      const r = node.getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height };
    };
    const title = element.querySelector('h1');
    const kicker = element.querySelector('.screen-kicker');
    const copy = element.querySelector('.hero-copy');
    const body = copy.querySelector('p:not(.screen-kicker)');
    const text = [...element.querySelectorAll('h1, h2, p')];
    return {
      height: box.height, title: rect(title), kicker: rect(kicker),
      copy: rect(copy), body: rect(body),
      bodyLineHeight: parseFloat(getComputedStyle(body).lineHeight),
      textFits: text.every(node => {
        const r = node.getBoundingClientRect();
        return r.top >= box.top && r.bottom <= box.bottom && r.left >= box.left && r.right <= box.right
          && node.scrollWidth <= node.clientWidth + 1;
      }),
      projectorClearance: box.right - copy.getBoundingClientRect().right,
      overflow: document.documentElement.scrollWidth > innerWidth
    };
  });
  expect(layout.height).toBeCloseTo(156, 0);
  expect(Math.abs((layout.title.top + layout.title.bottom) / 2 - (layout.kicker.top + layout.kicker.bottom) / 2)).toBeLessThan(2);
  expect(layout.kicker.left).toBeGreaterThan(layout.title.right);
  expect(layout.body.height).toBeLessThanOrEqual(layout.bodyLineHeight + 1);
  expect(layout.projectorClearance).toBeGreaterThanOrEqual(200);
  expect(layout.textFits).toBe(true);
  expect(layout.overflow).toBe(false);
}

for (const width of [1280, 1600, 1920]) {
  test(`slim Home header preserves readable text and projector space at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    const header = await openHeader(page);
    await expectReadableHeader(header);
    const art = header.locator('img');
    await expect(art).toHaveAttribute('aria-hidden', 'true');
    await expect(art).toHaveAttribute('alt', '');
    await expect(art).toHaveAttribute('src', /home-film-projector.*\.png$/);
    await expect.poll(() => art.evaluate(image => image.complete && image.naturalWidth > 0)).toBe(true);
    // The selected artwork's complete projector occupies y=34%-66%.
    // Leave clearance around that band instead of cropping the reels/base.
    const artClearance = await art.evaluate(image => {
      const scale = Math.max(image.clientWidth / image.naturalWidth, image.clientHeight / image.naturalHeight);
      const renderedHeight = image.naturalHeight * scale;
      const croppedTop = (renderedHeight - image.clientHeight) / 2;
      return {
        top: renderedHeight * .34 - croppedTop,
        bottom: image.clientHeight - (renderedHeight * .66 - croppedTop)
      };
    });
    expect(artClearance.top).toBeGreaterThanOrEqual(4);
    expect(artClearance.bottom).toBeGreaterThanOrEqual(4);
    await header.screenshot({ path: test.info().outputPath(`home-header-${width}.png`) });
    await page.screenshot({ path: test.info().outputPath(`home-desktop-${width}.png`) });
  });
}

test('Home banner survives Library navigation and browser Back/Forward', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await openHeader(page);
  await page.getByRole('button', { name: 'Library', exact: true }).click();
  await expect(page).toHaveURL(/\/library$/);
  await page.goBack();
  await expectReadableHeader(page.getByRole('region', { name: 'Home', exact: true }));
  await page.goForward();
  await expect(page).toHaveURL(/\/library$/);
  await page.getByRole('button', { name: 'Home', exact: true }).click();
  await expectReadableHeader(page.getByRole('region', { name: 'Home', exact: true }));
  expect(errors).toEqual([]);
});

test('decorative artwork failure leaves the banner content readable', async ({ page }) => {
  await page.route('**/assets/home-film-projector*.png', route => route.abort());
  const header = await openHeader(page);
  await expectReadableHeader(header);
});

test('Style Guide retains its original artwork', async ({ page }) => {
  await page.goto('/styleguide');
  const art = page.locator('.sg-hero-art');
  await expect(art).toHaveAttribute('src', /\/header-[^/]+\.png$/);
  await expect.poll(() => art.evaluate(image => image.complete && image.naturalWidth > 0)).toBe(true);
});
