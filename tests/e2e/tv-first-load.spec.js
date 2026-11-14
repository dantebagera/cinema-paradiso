import { test, expect } from '@playwright/test';

test.skip(process.env.CP_TV_E2E !== '1', 'Requires disposable TV fixture server');

for (const context of ['library', 'discover']) {
test(`first TV selection in ${context} starts its request without a cold code fallback and retains cached returns`, async ({ page }) => {
  await page.addInitScript(() => {
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
      const url = String(args[0]?.url || args[0]);
      if (url.endsWith('/api/tv/catalog/search') && window.__firstTVClickAt != null) {
        window.__firstTVFetchAt ??= Date.now();
      }
      return originalFetch.apply(this, args);
    };
    document.addEventListener('click', event => {
      const button = event.target.closest('button');
      if (button?.closest('[role="tablist"]') && button.textContent.trim() === 'TV Shows') {
        window.__firstTVClickAt ??= Date.now();
      }
    }, true);
  });
  await page.route('**/assets/TVWorkspace-*.js', async route => {
    await new Promise(resolve => setTimeout(resolve, 600));
    await route.continue();
  });
  let catalogRequests = 0;
  if (context === 'discover') {
    // The disposable server has no Movie provider key. Supply only its empty
    // Movie result; TV requests still exercise the real fixture backend.
    await page.route('**/api/tmdb/discover/advanced', route => route.fulfill({json:{results:[],page:1,total_pages:1,total_results:0}}));
  }
  page.on('request', request => {
    if (request.url().endsWith('/api/tv/catalog/search')) catalogRequests += 1;
  });
  const movieEndpoint = context === 'library' ? '/api/library/search/advanced' : '/api/tmdb/discover/advanced';
  const movieReady = page.waitForResponse(response => response.url().endsWith(movieEndpoint) && response.ok());
  await page.goto(`/${context}`);
  await movieReady;
  const tabs = page.getByRole('tablist', { name: context === 'library' ? 'Library media' : 'Discover tools' });
  await expect(tabs.getByRole('button', { name: 'Movies', exact: true })).toHaveAttribute('aria-pressed', 'true');
  expect(catalogRequests).toBe(0);
  const requested = page.waitForRequest(request => request.url().endsWith('/api/tv/catalog/search'));
  await tabs.getByRole('button', { name: 'TV Shows', exact: true }).click();
  await requested;
  // Both timestamps originate in Chromium. Exclude Playwright's pre-click
  // stability wait, which is unrelated to the tab's initialization work.
  const {clickAt,fetchAt} = await page.evaluate(() => ({clickAt:window.__firstTVClickAt,fetchAt:window.__firstTVFetchAt}));
  expect(clickAt).toEqual(expect.any(Number));
  expect(fetchAt).toEqual(expect.any(Number));
  const elapsed = fetchAt - clickAt;
  expect(elapsed).toBeGreaterThanOrEqual(0);
  console.info(`FIRST_TV_REQUEST ${context} ${elapsed}ms`);
  expect(elapsed).toBeLessThan(400);
  await expect(page.getByRole('link', { name: 'Open Harbor Signals' })).toBeVisible();
  await tabs.getByRole('button', { name: 'Movies', exact: true }).click();
  await tabs.getByRole('button', { name: 'TV Shows', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Open Harbor Signals' })).toBeVisible();
  expect(catalogRequests).toBe(1);
});
}
