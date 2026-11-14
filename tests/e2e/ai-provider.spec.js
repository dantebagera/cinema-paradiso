import { test, expect } from '@playwright/test';

test.describe.configure({ mode: 'serial' });
let account;
async function configure(request, values = {}) {
  if (!account) account = (await (await request.post('/api/ai/auth/start', { data: {} })).json()).attempt_id;
  const config = await (await request.get('/api/ai/config')).json();
  expect((await request.put('/api/ai/config', { data: { expected_generation: config.generation,
    provider: 'chatgpt', active_account_id: account, chatgpt_model: 'fixture-model-a', recommendation_count: '15',
    allow_movie_identity_hints: true, allow_iptv_titles: true, ...values } })).ok()).toBeTruthy();
  await request.post('/api/test/ai-fixture', { data: {} });
}
async function completed(request, id) {
  let result;
  await expect.poll(async () => {
    result = await (await request.get(`/api/ai/jobs/${id}`)).json();
    return ['queued', 'running'].includes(result.state);
  }).toBe(false);
  return result;
}
async function pick(page) {
  await page.goto('/discover');
  await page.getByRole('button', { name: 'Pick My Movie', exact: true }).click();
  if (!await prompt(page).isVisible()) await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
}
const prompt = page => page.getByPlaceholder('Something funny but a little sad, maybe an indie movie with a warm ending...');
test.beforeEach(async ({ page }) => {
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    return url.hostname === '127.0.0.1' || url.protocol === 'data:' ? route.continue() : route.abort();
  });
});

test('Settings uses explicit sign-in/model choice and separate initially-off evidence permissions', async ({ page, request }) => {
  await page.goto('/settings');
  const card = page.locator('#settings-chatgpt');
  await card.getByLabel('AI provider', { exact: true }).selectOption('chatgpt');
  await expect(card.getByRole('checkbox')).toHaveCount(2);
  for (const box of await card.getByRole('checkbox').all()) await expect(box).not.toBeChecked();
  await card.getByRole('button', { name: 'Continue with ChatGPT', exact: true }).click();
  await expect(card.getByText('Signed in. Select the account, load its models, then choose a model.')).toBeVisible();
  account = (await (await request.get('/api/ai/config')).json()).accounts[0].account_id;
  await card.getByLabel('ChatGPT account', { exact: true }).selectOption(account);
  await card.getByRole('button', { name: 'Load available models' }).click();
  await card.getByLabel('ChatGPT model', { exact: true }).selectOption('fixture-model-a');
  await card.getByLabel('ChatGPT default recommendation count').fill('9007199254740993');
  await card.getByRole('button', { name: 'Save ChatGPT settings', exact: true }).click();
  await expect(card.getByText('ChatGPT settings saved.')).toBeVisible();
  expect((await (await request.get('/api/ai/config')).json()).chatgpt.recommendation_count).toBe('9007199254740993');
  await card.getByRole('button', { name: 'Test ChatGPT connection' }).click();
  await expect(card.getByText('ChatGPT connection test completed.', { exact: true })).toBeVisible();
  await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/settings-desktop.png`, fullPage: true });
});

for (const width of [1600, 1280]) test(`compact Pick prompt scrolls and resizes with count beside Ask AI at ${width}px`, async ({ page, request }) => {
  await configure(request);
  await page.setViewportSize({ width, height: 1000 });
  await pick(page);
  const form = page.locator('.pick-prompt-panel');
  const textarea = prompt(page);
  const count = page.getByLabel('Recommendation count for this request');
  const submit = form.getByRole('button', { name: 'Ask AI', exact: true });
  await expect(form.locator('.ai-provider-status')).toHaveCount(0);
  await expect(form).not.toContainText('Leave blank to use');
  const original = await textarea.boundingBox();
  expect(original.height).toBeLessThan(100);
  const inputBox = await count.boundingBox();
  const buttonBox = await submit.boundingBox();
  expect(Math.abs(inputBox.y + inputBox.height / 2 - buttonBox.y - buttonBox.height / 2)).toBeLessThan(3);
  expect(inputBox.x + inputBox.width).toBeLessThan(buttonBox.x);
  expect(buttonBox.width).toBeLessThan(250);
  await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/pick-compact-${width}.png`, fullPage: true });
  await textarea.fill(Array.from({ length: 16 }, (_, i) => `Long prompt line ${i}`).join('\n'));
  expect((await textarea.boundingBox()).height).toBe(original.height);
  expect(await textarea.evaluate(element => element.scrollHeight > element.clientHeight)).toBe(true);
  await page.mouse.move(original.x + original.width - 4, original.y + original.height - 4);
  await page.mouse.down();
  await page.mouse.move(original.x + original.width - 4, original.y + original.height + 76, { steps: 8 });
  await page.mouse.up();
  expect((await textarea.boundingBox()).height).toBeGreaterThan(original.height + 40);
  await textarea.fill('Synthetic compact twisted endings');
  await count.fill('3');
  const started = page.waitForResponse(response => response.url().endsWith('/api/ai/recommendations') && response.status() === 202);
  await submit.click();
  const job = await (await started).json();
  expect(job.requested_count).toBe('3');
  await expect(page.getByRole('region', { name: 'ChatGPT recommendations' })).toHaveText('3 movies ready.');
  expect((await completed(request, job.id)).accepted_count).toBe(3);
  await expect(page.locator('.pick-panel-react .discover-movie-card')).toHaveCount(3);
});

for (const width of [1600, 1280]) test(`recommendations restore all 120 verified items with desktop paging at ${width}px`, async ({ page, request }) => {
  await configure(request);
  await page.setViewportSize({ width, height: width === 1600 ? 1000 : 800 });
  await pick(page);
  await prompt(page).fill('Synthetic atmosphere');
  await page.getByLabel('Recommendation count for this request').fill('120');
  const started = page.waitForResponse(response => response.url().endsWith('/api/ai/recommendations') && response.status() === 202);
  await page.getByRole('button', { name: 'Ask AI', exact: true }).click();
  const job = await (await started).json();
  expect((await completed(request, job.id)).accepted_count).toBe(120);
  await expect(page.getByRole('region', { name: 'ChatGPT recommendations' })).toContainText('120 movies ready.');
  await expect(page.locator('.pick-panel-react .discover-movie-card')).toHaveCount(20);
  const pagination = page.getByRole('navigation', { name: 'ChatGPT recommendation pagination' });
  await expect(pagination.getByText('Page 1 of 6')).toBeVisible();
  for (let i = 0; i < 5; i++) {
    await pagination.getByRole('button', { name: 'Next', exact: true }).click();
    await expect(pagination.getByText(`Page ${i + 2} of 6`)).toBeVisible();
  }
  await expect(page.getByText('Fixture Movie 120', { exact: true }).first()).toBeVisible();
  await page.reload();
  if (!await page.getByRole('button', { name: 'Ask AI', exact: true }).isVisible()) await page.getByRole('button', { name: 'Pick My Movie', exact: true }).click();
  await expect(page.getByRole('region', { name: 'ChatGPT recommendations' })).toContainText('120 movies ready.');
  await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/recommendations-${width}.png`, fullPage: true });
  if (width === 1600) {
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    await expect(page.locator('#settings-chatgpt')).toBeVisible();
    await page.goBack();
    if (!await page.getByRole('region', { name: 'ChatGPT recommendations' }).isVisible()) await page.getByRole('button', { name: 'Pick My Movie', exact: true }).click();
    await expect(page.getByRole('region', { name: 'ChatGPT recommendations' })).toContainText('120 movies ready.');
    await page.goForward();
    await expect(page.locator('#settings-chatgpt')).toBeVisible();
  }
});

test('AI Control saves only two explicitly selected movies from the complete 120-card review, once', async ({ page, request }) => {
  await configure(request);
  await page.goto('/ai-control');
  await page.getByPlaceholder('Tell CP what to find, list, download, or delete...').fill('Create fixture studio list');
  await page.getByRole('button', { name: 'Preview command' }).click();
  await expect(page.getByRole('button', { name: 'Confirm action', exact: true })).toBeVisible();
  await expect(page.locator('.ai-control-card-toolbar')).toContainText('120 selected');
  await page.locator('.ai-control-card-toolbar').getByRole('button', { name: 'Clear', exact: true }).click();
  const first = page.getByRole('checkbox', { name: 'Select Fixture Movie 1', exact: true });
  await page.locator('label.selection-checkbox').filter({ has: first }).click();
  await expect(first).toBeChecked();
  const nav = page.locator('.ai-control-pagination').first();
  while (await nav.getByRole('button', { name: 'Next page', exact: true }).isEnabled()) {
    await nav.getByRole('button', { name: 'Next page', exact: true }).click();
  }
  const last = page.getByRole('checkbox', { name: 'Select Fixture Movie 120', exact: true });
  await page.locator('label.selection-checkbox').filter({ has: last }).click();
  await expect(last).toBeChecked();
  await expect(page.locator('.ai-control-card-toolbar')).toContainText('2 selected');
  await page.getByRole('button', { name: 'Confirm action', exact: true }).click();
  await expect(page.locator('.ai-control-execution-receipt')).toContainText('completed');
  const lists = await (await request.get('/api/user/lists')).json();
  const saved = lists.lists.find(row => row.name === 'Desktop fixture studio');
  expect(saved.movies.map(row => Number(row.tmdb_id)).sort((a, b) => a - b)).toEqual([1, 120]);
  const calls = (await (await request.post('/api/test/ai-fixture', { data: {} })).json()).calls;
  await page.reload();
  await expect(page.locator('.ai-control-execution-receipt')).toContainText('completed');
  expect((await (await request.post('/api/test/ai-fixture', { data: {} })).json()).calls).toBe(calls);
  await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/control-receipt.png`, fullPage: true });
});

test('provider failure stays visible and switching to Ollama is manual', async ({ page, request }) => {
  await configure(request);
  await request.post('/api/test/ai-fixture', { data: { failure: 'rate_limit_exceeded' } });
  await pick(page);
  await prompt(page).fill('Synthetic failure');
  await page.getByRole('button', { name: 'Ask AI', exact: true }).click();
  await expect(page.getByRole('region', { name: 'ChatGPT recommendations' })).toContainText('ChatGPT is busy or its usage limit was reached.');
  expect((await (await request.get('/api/ai/config')).json()).provider).toBe('chatgpt');
  await page.goto('/settings');
  const reload = page.getByRole('button', { name: 'Reload AI settings', exact: true });
  await expect.poll(async () => await page.locator('#settings-chatgpt').getByLabel('AI provider', { exact: true }).isEnabled()
    || await reload.isVisible()).toBe(true);
  if (await reload.isVisible()) await reload.click();
  await page.locator('#settings-chatgpt').getByLabel('AI provider', { exact: true }).selectOption('ollama');
  await expect(page.locator('#settings-ollama')).toBeVisible();
  expect((await (await request.get('/api/ai/config')).json()).provider).toBe('ollama');
});

test('IPTV shows an oversized selection before starting ChatGPT', async ({ page, request }) => {
  await configure(request);
  await request.post('/api/test/ai-fixture', { data: { iptv_unmatched: true } });
  await page.route('**/movies/metadata/review?*', async route => {
    const response = await route.fetch();
    const review = await response.json();
    if (review.view === 'unmatched') review.total = 6413;
    await route.fulfill({ response, json: review });
  });
  await page.goto('/iptv');
  await page.getByRole('button', { name: 'Metadata', exact: true }).click();
  await page.getByRole('combobox', { name: 'Status', exact: true }).selectOption('unmatched');
  await expect(page.locator('.iptv-review-card-grid')).toContainText('Fixture Movie');
  await page.getByRole('button', { name: 'Select all filtered', exact: true }).click();
  await page.locator('.iptv-review-workspace').getByText('Actions', { exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('5,000 sources per job');
  await expect(page.getByRole('button', { name: 'Match selected with ChatGPT', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Classify selected with ChatGPT', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Add current page', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Match selected with ChatGPT', exact: true })).toBeEnabled();
});

test('IPTV proposals render through the native review panels and require a separate Apply', async ({ page, request }) => {
  await configure(request);
  const fixture = await (await request.post('/api/test/ai-fixture', { data: { iptv_unmatched: true } })).json();
  await page.goto('/iptv');
  await page.getByRole('button', { name: 'Metadata', exact: true }).click();
  await page.locator('.iptv-review-workspace').getByText('Actions', { exact: true }).click();
  for (const [feature, suffix, index] of [['F4', 'classification-jobs', 0], ['F5', 'match-jobs', 1]]) {
    const classification = feature === 'F4';
    await page.getByRole('combobox', { name: 'Status', exact: true }).selectOption(classification ? 'classification-review' : 'unmatched');
    await page.getByPlaceholder('Search this review queue...').fill(classification ? 'Opaque object' : 'Fixture Movie');
    await expect(page.locator('.iptv-review-card-grid')).toContainText(classification ? 'Opaque object' : 'Fixture Movie');
    await page.getByRole('button', { name: 'Select all filtered', exact: true }).click();
    const requested = page.waitForResponse(response => response.url().endsWith(`/movies/ai/${suffix}`) && response.request().method() === 'POST');
    await page.getByRole('button', { name: classification ? 'Classify selected with ChatGPT' : 'Match selected with ChatGPT', exact: true }).click();
    const response = await requested;
    expect(response.status()).toBe(202);
    const job = await completed(request, (await response.json()).id);
    expect(job.state).toBe('completed');
    expect(job.output.review_required).toBe(true);
    expect(job.request.selection_snapshot.source_keys).toEqual([fixture.source_keys[index].replace('source:', '')]);
    if (!classification) {
      expect(job.run_calls).toBe(2);
      expect(job.output.review.proposals[0].evidence.search_hints).toEqual(['Fixture Movie Alternate']);
    }
    await expect(page.getByRole('region', { name: classification ? 'ChatGPT IPTV classification' : 'ChatGPT IPTV matching' })).toContainText('Ready for review');
    const panel = page.locator('.iptv-proposal-panel').last();
    await expect(panel).toBeVisible();
    if (!classification) await expect(panel).toContainText('ChatGPT search hints: Fixture Movie Alternate');
    await expect(panel.getByRole('button', { name: /^Apply/ })).toBeEnabled();
    await panel.getByRole('button', { name: /^Apply/ }).click();
    await expect(page.locator('.ai-control-execution-receipt').last()).toContainText('completed');
  }
  await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/iptv-receipts.png`, fullPage: true });
});

test('IPTV Play keeps its category after TMDB lookup, Apply and reload', async ({ page }) => {
  await page.goto('/iptv');
  const plays = page.getByRole('group', { name: 'IPTV Movies category' }).getByRole('button', { name: /^Plays/ });
  async function openPlays() {
    await page.getByRole('button', { name: 'Movies', exact: true }).first().click();
    await page.getByRole('group', { name: 'IPTV Movies view' }).getByRole('button', { name: 'CP View' }).click();
    await plays.click();
  }
  await openPlays();
  const card = page.locator('.iptv-movie-card').filter({ hasText: 'مسرحية الاختبار' });
  await card.first().click();
  await card.getByRole('button', { name: 'Match metadata' }).click();
  const dialog = page.getByRole('dialog', { name: 'Match IPTV movie metadata' });
  await dialog.getByLabel('Title', { exact: true }).fill('tmdb:781869');
  await dialog.getByRole('button', { name: 'Search TMDB' }).click();
  await expect(dialog).toContainText('مسرحية الاختبار الموثقة');
  await dialog.getByRole('button', { name: /Use this match|Review and use/ }).click();
  await expect(dialog).toHaveCount(0);
  await page.reload();
  await openPlays();
  await expect(card).toContainText('مسرحية الاختبار الموثقة');
  await card.first().click();
  await expect(card).toContainText('TMDB plot for مسرحية الاختبار الموثقة');
  await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/iptv-play-metadata.png`, fullPage: true });
  page.once('dialog', confirmation => confirmation.accept());
  await card.getByRole('button', { name: 'Remove match', exact: true }).click();
  await expect(card).toContainText('مسرحية الاختبار');
  await expect(card).not.toContainText('مسرحية الاختبار الموثقة');
});

test('Movie Smart Match uses ChatGPT through its native review and applies only after confirmation', async ({ page, request }) => {
  await configure(request);
  await page.goto('/cleanup');
  await page.getByRole('tab', { name: 'Identity', exact: true }).click();
  const row = page.locator('.unmatched-row').filter({ hasText: 'Fixture.Movie.1.2001.mkv' });
  await row.locator('.cleanup-check').click();
  await page.getByRole('radio', { name: 'Match by AI', exact: true }).check();
  const started = page.waitForResponse(response => response.url().endsWith('/api/metadata/smart-match') && response.status() === 202);
  await page.getByRole('button', { name: 'Smart Match Selected (1)', exact: true }).click();
  const native = await (await started).json();
  const dialog = page.getByRole('dialog', { name: 'Smart Match review', exact: true });
  await expect(dialog).toContainText('ChatGPT · fixture-model-a');
  await expect(dialog.getByRole('button', { name: 'Review selected matches (1)', exact: true })).toBeEnabled();
  let fixture = await (await request.post('/api/test/ai-fixture', { data: {} })).json();
  expect(fixture.movie_record.identity_status).toBe('unmatched');
  await dialog.getByRole('button', { name: 'Review selected matches (1)', exact: true }).click();
  await dialog.getByRole('button', { name: 'Confirm apply matches', exact: true }).click();
  await expect.poll(async () => {
    fixture = await (await request.post('/api/test/ai-fixture', { data: {} })).json();
    return String(fixture.movie_record.tmdb_id);
  }).toBe('1');
  expect((await completed(request, native.ai_job_id)).run_calls).toBe(1);
  await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/smart-match-desktop.png`, fullPage: true });
});

test('AI Control reuses the native TV card and persists TV list membership through its TV owner', async ({ page, request }) => {
  await configure(request);
  await page.goto('/ai-control');
  await page.getByPlaceholder('Tell CP what to find, list, download, or delete...').fill('Create TV list');
  await page.getByRole('button', { name: 'Preview command' }).click();
  await expect(page.getByText('Harbor Signals', { exact: true }).first()).toBeVisible();
  await expect(page.locator('.ai-control-card-results .tv-series-card')).toHaveCount(1);
  await page.getByRole('button', { name: 'Confirm action', exact: true }).click();
  await expect(page.locator('.ai-control-execution-receipt')).toContainText('completed');
  const lists = await (await request.get('/api/tv/lists')).json();
  expect(JSON.stringify(lists)).toContain('Synthetic TV list');
  expect((await (await request.get('/api/user/lists')).json()).lists.some(row => row.name === 'Synthetic TV list')).toBe(false);
  await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/tv-action-desktop.png`, fullPage: true });
});

test('a failed Settings read can be retried explicitly without inference', async ({ page, request }) => {
  await configure(request);
  const before = (await (await request.post('/api/test/ai-fixture', { data: {} })).json()).calls;
  let blocked = false;
  await page.route('**/api/ai/config', route => {
    if (!blocked) { blocked = true; return route.abort('failed'); }
    return route.continue();
  });
  await page.goto('/settings');
  await page.getByRole('button', { name: 'Reload AI settings', exact: true }).click();
  await expect(page.locator('#settings-chatgpt').getByLabel('AI provider', { exact: true })).toBeEnabled();
  expect((await (await request.post('/api/test/ai-fixture', { data: {} })).json()).calls).toBe(before);
});

test('classification then matching waits for confirmation and an explicit next preparation', async ({ page, request }) => {
  await configure(request);
  await page.goto('/ai-control');
  await page.getByPlaceholder('Tell CP what to find, list, download, or delete...').fill('Classification then matching');
  await page.getByRole('button', { name: 'Preview command' }).click();
  await expect(page.getByRole('button', { name: 'Prepare next step', exact: true })).toBeVisible();
  await page.locator('.iptv-proposal-panel').getByRole('button', { name: /^Apply .* classifications$/ }).click();
  await expect(page.locator('.ai-control-execution-receipt')).toHaveCount(1);
  const before = (await (await request.post('/api/test/ai-fixture', { data: {} })).json()).calls;
  await page.reload();
  await expect(page.getByRole('button', { name: 'Prepare next step', exact: true })).toBeVisible();
  expect((await (await request.post('/api/test/ai-fixture', { data: {} })).json()).calls).toBe(before);
  await page.getByRole('button', { name: 'Prepare next step', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Next IPTV preparation' })).toContainText('Finished');
  await page.getByRole('button', { name: 'Load prepared review', exact: true }).click();
  await expect(page.locator('.iptv-proposal-panel').getByRole('button', { name: /^Apply/ })).toBeEnabled();
  await page.locator('.iptv-proposal-panel').getByRole('button', { name: /^Apply/ }).click();
  await expect(page.locator('.ai-control-execution-receipt')).toHaveCount(2);
  await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/ordered-iptv-desktop.png`, fullPage: true });
});

test('budget pause restores without inference, Continue keeps the exact target, and Cancel stops future work', async ({ page, request }) => {
  await configure(request);
  await pick(page);
  await prompt(page).fill('Synthetic large batch');
  await page.getByLabel('Recommendation count for this request').fill('500');
  const started = page.waitForResponse(response => response.url().endsWith('/api/ai/recommendations') && response.status() === 202);
  await page.getByRole('button', { name: 'Ask AI', exact: true }).click();
  const id = (await (await started).json()).id;
  const paused = await completed(request, id);
  expect(paused.state).toBe('paused_budget');
  expect(paused.accepted_count).toBe(480);
  expect(paused.run_calls).toBe(24);
  const before = (await (await request.post('/api/test/ai-fixture', { data: {} })).json()).calls;
  await page.reload();
  await page.getByRole('button', { name: 'Pick My Movie', exact: true }).click();
  await expect(page.getByRole('region', { name: 'ChatGPT recommendations' })).toContainText('Paused. 480 of 500 movies ready.');
  expect((await (await request.post('/api/test/ai-fixture', { data: {} })).json()).calls).toBe(before);
  if (!await prompt(page).isVisible()) await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await page.getByLabel('Recommendation count for this request').fill('500');
  await page.getByLabel('Recommendation count for this request').fill('');
  await expect(page.getByRole('button', { name: 'Ask AI', exact: true })).toBeEnabled();
  await page.getByLabel('Recommendation count for this request').fill('500');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await expect(page.getByRole('region', { name: 'ChatGPT recommendations' })).toHaveText('500 movies ready.');
  expect((await completed(request, id)).state).toBe('completed');
  await page.getByRole('button', { name: 'New conversation', exact: true }).click();
  await request.post('/api/test/ai-fixture', { data: { delay: .5 } });
  if (!await prompt(page).isVisible()) await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  await prompt(page).fill('Synthetic cancellable batch');
  await page.getByLabel('Recommendation count for this request').fill('500');
  await page.getByRole('button', { name: 'Ask AI', exact: true }).click();
  // Cancelling must work even if the user has since typed an invalid count.
  await page.getByLabel('Recommendation count for this request').fill('1.5');
  await page.getByRole('button', { name: 'Stop', exact: true }).click();
  await expect(page.getByRole('region', { name: 'ChatGPT recommendations' })).toContainText('Stopped.');
});

test('Pick My Movie shows real response stages in one line and keeps actions in the prompt form', async ({ page, request }) => {
  await configure(request);
  await page.setViewportSize({ width: 1600, height: 1000 });
  await request.post('/api/test/ai-phases', { data: { hold: ['connecting', 'retrieving', 'matching'] } });
  try {
    await pick(page);
    await prompt(page).fill('Synthetic twisted endings');
    await page.getByLabel('Recommendation count for this request').fill('1');
    const started = page.waitForResponse(response => response.url().endsWith('/api/ai/recommendations') && response.status() === 202);
    await page.getByRole('button', { name: 'Ask AI', exact: true }).click();
    const id = (await (await started).json()).id;
    const status = page.getByRole('region', { name: 'ChatGPT recommendations' });
    for (const [phase, text] of [['connecting', 'Connecting to ChatGPT…'], ['retrieving', 'Getting movie suggestions…'], ['matching', 'Checking movie matches…']]) {
      await expect(status).toHaveText(text);
      const backend = await (await request.get(`/api/ai/jobs/${id}`)).json();
      expect(backend.progress_phase).toBe(phase);
      expect(backend.accepted_count).toBe(0);
      await expect(page.getByRole('button', { name: 'Stop', exact: true })).toBeEnabled();
      await expect(status.locator('button, a, h3, .screen-kicker')).toHaveCount(0);
      await expect(status).not.toHaveClass(/ai-control-result/);
      await expect(status.locator('p')).toHaveCSS('border-top-width', '0px');
      await expect(status.locator('p')).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
      expect((await status.boundingBox()).height).toBeLessThan(40);
      if (phase === 'retrieving') await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/pick-status-retrieving.png`, fullPage: true });
      await request.post('/api/test/ai-phases', { data: { release: phase } });
    }
    await expect(status).toHaveText('1 movie ready.');
    expect((await completed(request, id)).accepted_count).toBe(1);
    await expect(page.locator('.pick-panel-react .discover-movie-card')).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'Ask AI', exact: true })).toBeEnabled();
    await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/pick-status-completed.png`, fullPage: true });
  } finally {
    await request.post('/api/test/ai-phases', { data: { release: 'all' } });
  }
});

test('a restored requirements failure explains saved results and starts a fresh request', async ({ page, request }) => {
  await configure(request);
  const seeded = await request.post('/api/ai/recommendations', { data: { prompt: 'Synthetic saved endings', count: '18', request_key: 'status-saved-results' } });
  const saved = await completed(request, (await seeded.json()).id);
  expect(saved.accepted_count).toBe(18);
  // Recreate the screenshot state for rendering; real backend failure semantics
  // are covered by recommendation/store tests. Cards come from the real fixture.
  const failed = { ...saved, state: 'failed', requested_count: '50',
    request: { ...saved.request, count: '50' }, message: 'scope_changed_during_operation' };
  await page.route(`**/api/ai/jobs/${saved.id}*`, route => route.fulfill({ json: failed }));
  await page.goto('/discover');
  await page.evaluate(({ id, account }) => localStorage.setItem(`cp-ai-job:F1:${account}:`, JSON.stringify({ id })), { id: saved.id, account });
  await page.reload();
  await page.getByRole('button', { name: 'Pick My Movie', exact: true }).click();
  const status = page.getByRole('region', { name: 'ChatGPT recommendations' });
  await expect(status).toHaveText('The request requirements changed. 18 of 50 movies ready. Start a new request.');
  await expect(status.locator('button, a, h3')).toHaveCount(0);
  await expect(status).not.toContainText(/scope_changed|24|fixture-model/);
  await expect(page.locator('.pick-panel-react .discover-movie-card')).toHaveCount(18);
  await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/pick-status-saved-failure.png`, fullPage: true });
  if (!await prompt(page).isVisible()) await page.getByRole('button', { name: 'Search, filters & selection', exact: true }).click();
  const started = page.waitForResponse(response => response.url().endsWith('/api/ai/recommendations') && response.status() === 202);
  await page.getByRole('button', { name: 'Ask AI', exact: true }).click();
  const next = await (await started).json();
  expect(next.session_id).not.toBe(saved.session_id);
  expect(next.request.prompt).toBe('Synthetic saved endings');
  expect(next.requested_count).toBe('50');
  await expect(status).toHaveText('50 movies ready.');
  expect((await completed(request, next.id)).accepted_count).toBe(50);
});

test('disconnect and account switch preserve isolation and leave the next account without a saved model', async ({ page, request }) => {
  await configure(request);
  const old = await request.post('/api/ai/recommendations', { data: { prompt: 'Synthetic private session', count: '1', request_key: 'account-isolation' } });
  const job = await completed(request, (await old.json()).id);
  await page.goto('/settings');
  const card = page.locator('#settings-chatgpt');
  await card.getByRole('button', { name: 'Disconnect selected account', exact: true }).click();
  await expect(card.getByText('Account disconnected; its session was revoked.')).toBeVisible();
  await card.getByRole('button', { name: 'Continue with ChatGPT', exact: true }).click();
  const nextAccount = 'fixture-account-2';
  await expect(card.getByLabel('ChatGPT account', { exact: true }).locator('option')).toHaveCount(3);
  await card.getByLabel('ChatGPT account', { exact: true }).selectOption(nextAccount);
  await expect(card.getByLabel('ChatGPT model', { exact: true })).toHaveValue('');
  expect((await request.get(`/api/ai/jobs/${job.id}`)).status()).toBe(409);
  await page.goto('/discover');
  await page.getByRole('button', { name: 'Pick My Movie', exact: true }).click();
  await expect(page.getByRole('region', { name: 'ChatGPT recommendations' })).toHaveCount(0);
});
