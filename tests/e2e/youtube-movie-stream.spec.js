import { test, expect } from '@playwright/test';

const movie = { tmdb_id: '550', title: 'The Example', year: '2001', genres: ['Drama'], poster_url: '' };
const row = (id, title = 'The Example — full movie') => ({ video_id: id, title, channel_title: 'Any uploader',
  duration_seconds: 6000, embeddable: true, url: `https://www.youtube.com/watch?v=${id}` });
const results = (candidates = [], hasMore = true) => ({ search_id: 'session-one', movie: { title: 'The Example' },
  runtime_seconds: 6000, duration_range: [5700, 6300], candidates, has_more: hasMore, queries: ['The Example full movie'] });

async function open(page) {
  await page.route('**/api/tmdb/discover**', route => route.fulfill({ json: { results: [movie], page: 1, total_pages: 1, total_results: 1 } }));
  await page.route('**/api/tmdb/details**', route => route.fulfill({ json: movie }));
  await page.route('**/api/tmdb/related**', route => route.fulfill({ json: { results: [] } }));
  await page.route('**/api/library/check', route => route.fulfill({ json: { results: [], catalog_generation: 1 } }));
  await page.route('**/api/ai/config', route => route.fulfill({ json: { provider: 'chatgpt', generation: 1,
    chatgpt: { active_account_id: 'account', model: 'fixture' }, features: [{ id: 'F6', ready: true }] } }));
  await page.goto('/discover');
  await page.getByRole('heading', { name: movie.title, exact: true }).click();
  await page.locator('.unified-movie-card-expanded').getByRole('button', { name: 'Stream', exact: true }).click();
  const dialog = page.locator('.stream-dialog');
  await dialog.getByRole('button', { name: /YouTube/ }).click();
  return dialog;
}

test('YouTube searches only when selected, paginates without GPT, plays and keeps results', async ({ page }) => {
  let searches = 0;
  let aiCalls = 0;
  await page.route('**/api/youtube/movie-search', route => {
    searches++;
    expect(route.request().postDataJSON()).toEqual(searches === 1 ? { tmdb_id: '550' } : { search_id: 'session-one' });
    return route.fulfill({ json: results(searches === 1 ? [row('aaaaaa1')] : [row('aaaaaa1'), row('aaaaaa2', 'The Example alternative')]) });
  });
  await page.route('**/api/ai/youtube/movie-search', route => { aiCalls++; return route.abort(); });
  await page.route('https://www.youtube.com/embed/**', route => route.fulfill({ contentType: 'text/html', body: '<p>YouTube fixture</p>' }));
  const dialog = await open(page);
  await expect(dialog.getByRole('button', { name: 'Play The Example — full movie' })).toBeVisible();
  await expect(dialog.getByText(/95:00.*105:00/)).toBeVisible();
  await dialog.getByRole('button', { name: 'Search more', exact: true }).click();
  await expect(dialog.getByRole('button', { name: /Play The Example/ })).toHaveCount(2);
  expect(aiCalls).toBe(0);
  await dialog.getByRole('button', { name: 'Play The Example — full movie' }).click();
  await expect(dialog.locator('iframe')).toHaveAttribute('src', /youtube.com\/embed\/aaaaaa1/);
  await expect(dialog.getByRole('link', { name: 'Open on YouTube', exact: true })).toHaveAttribute('href', /watch\?v=aaaaaa1/);
  await dialog.getByRole('button', { name: 'Back to results' }).click();
  await expect(dialog.getByRole('button', { name: /Play The Example/ })).toHaveCount(2);
  if (process.env.CP_YOUTUBE_EVIDENCE_DIR) await page.screenshot({ path: `${process.env.CP_YOUTUBE_EVIDENCE_DIR}/results.png` });
  await dialog.getByRole('button', { name: 'Change source', exact: true }).click();
  await expect(dialog.getByRole('button', { name: /StreamIMDB/ })).toBeVisible();
});

test('empty, error and exhausted searches keep both discovery controls visible', async ({ page }) => {
  let count = 0;
  await page.route('**/api/youtube/movie-search', route => {
    count++;
    if (count === 1) return route.fulfill({ status: 422, json: { error: { message: 'YouTube is unavailable. Retry.' } } });
    return route.fulfill({ json: results([], false) });
  });
  const dialog = await open(page);
  await expect(dialog.getByRole('alert')).toContainText('YouTube is unavailable');
  await expect(dialog.getByRole('button', { name: 'Use GPT', exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Search more', exact: true }).click();
  await expect(dialog.getByText(/No videos matched/)).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Search more', exact: true })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Use GPT', exact: true })).toBeEnabled();
});

test('GPT is explicit and completed results are rendered through the existing job flow', async ({ page }) => {
  let calls = 0;
  const job = { id: 'job-one', revision: 1, state: 'queued', selection: { account_id: 'account', domain_id: 'session-one' },
    request: { search_id: 'session-one' }, cursor: {}, output: null };
  await page.route('**/api/youtube/movie-search', route => route.fulfill({ json: results() }));
  await page.route('**/api/ai/youtube/movie-search', route => {
    calls++;
    expect(route.request().postDataJSON().search_id).toBe('session-one');
    return route.fulfill({ status: 202, json: job });
  });
  await page.route('**/api/ai/jobs/job-one**', route => route.fulfill({ json: { ...job, revision: 2, state: 'completed',
    output: { ...results([row('aaaaaa3', 'The Example found with another query')]), explanation: 'Tried an alternate title.' } } }));
  const dialog = await open(page);
  await expect(dialog.getByText(/No videos matched/)).toBeVisible();
  expect(calls).toBe(0);
  await dialog.getByRole('button', { name: 'Use GPT', exact: true }).click();
  await expect(dialog.getByRole('button', { name: /Play The Example found/ })).toBeVisible();
  expect(calls).toBe(1);
});

test('switching source while search is pending discards late results', async ({ page }) => {
  let release;
  const wait = new Promise(resolve => { release = resolve; });
  await page.route('**/api/youtube/movie-search', async route => { await wait; await route.fulfill({ json: results([row('aaaaaa1')]) }).catch(() => {}); });
  const dialog = await open(page);
  await expect(dialog.getByText('Searching YouTube…')).toBeVisible();
  await dialog.getByRole('button', { name: 'Change source', exact: true }).click();
  release();
  await expect(dialog.getByRole('button', { name: /StreamIMDB/ })).toBeVisible();
  await expect(dialog.getByRole('button', { name: /Play The Example/ })).toHaveCount(0);
});

test('failed GPT keeps partial results visible with the error', async ({ page }) => {
  const job = { id: 'job-partial', revision: 1, state: 'queued', selection: { account_id: 'account', domain_id: 'session-one' },
    request: { search_id: 'session-one' }, cursor: {}, output: null };
  await page.route('**/api/youtube/movie-search', route => route.fulfill({ json: results() }));
  await page.route('**/api/youtube/movie-search/status', route => route.fulfill({ json: results([row('aaaaaa7', 'The Example partial match')]) }));
  await page.route('**/api/ai/youtube/movie-search', route => route.fulfill({ json: job }));
  await page.route('**/api/ai/jobs/job-partial**', route => route.fulfill({ json: { ...job, state: 'failed',
    message: 'YouTube query failed', output: results([row('aaaaaa7', 'The Example partial match')]) } }));
  const dialog = await open(page);
  await expect(dialog.getByRole('button', { name: 'Use GPT', exact: true })).toBeEnabled();
  await dialog.getByRole('button', { name: 'Use GPT', exact: true }).click();
  await expect(dialog.getByRole('alert')).toContainText('YouTube query failed');
  await expect(dialog.getByRole('button', { name: 'Play The Example partial match' })).toBeVisible();
});

test('cancel GPT retrieves earlier matches without starting another search', async ({ page }) => {
  let cancelled = false;
  let searches = 0;
  let statusReads = 0;
  const job = { id: 'job-cancel', revision: 1, state: 'running', selection: { account_id: 'account', domain_id: 'session-one' },
    request: { search_id: 'session-one' }, cursor: {}, output: null };
  await page.route('**/api/youtube/movie-search', route => { searches++; return route.fulfill({ json: results() }); });
  await page.route('**/api/youtube/movie-search/status', route => {
    statusReads++; return route.fulfill({ json: results([row('aaaaaa8', 'The Example before cancellation')]) });
  });
  await page.route('**/api/ai/youtube/movie-search', route => route.fulfill({ json: job }));
  await page.route('**/api/ai/jobs/job-cancel**', route => {
    if (route.request().url().endsWith('/cancel')) cancelled = true;
    return route.fulfill({ json: { ...job, revision: cancelled ? 2 : 1, state: cancelled ? 'cancelled' : 'running' } });
  });
  const dialog = await open(page);
  await expect(dialog.getByRole('button', { name: 'Use GPT', exact: true })).toBeEnabled();
  await dialog.getByRole('button', { name: 'Use GPT', exact: true }).click();
  await dialog.getByRole('button', { name: 'Cancel GPT', exact: true }).click();
  await expect(dialog.getByRole('button', { name: 'Play The Example before cancellation' })).toBeVisible();
  await expect(dialog.getByText('GPT cancelled. Results already found are kept.')).toBeVisible();
  expect(searches).toBe(1);
  expect(statusReads).toBe(1);
});
