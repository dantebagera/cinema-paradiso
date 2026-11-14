import { test, expect } from '@playwright/test';

async function configure(request) {
  const auth = await (await request.post('/api/ai/auth/start', { data: {} })).json();
  const config = await (await request.get('/api/ai/config')).json();
  const update = await request.put('/api/ai/config', { data: {
    expected_generation: config.generation, provider: 'chatgpt', active_account_id: auth.attempt_id,
    chatgpt_model: 'fixture-model-a', allow_iptv_titles: true,
  } });
  expect(update.ok()).toBeTruthy();
}

async function seed(request, saved = false) {
  const response = await request.post('/api/test/iptv-bulk-fixture', { data: { count: 6413, saved } });
  expect(response.ok()).toBeTruthy();
  const fixture = await response.json();
  return { ...fixture, endpoint: `/api/iptv/providers/${fixture.provider_id}/movies/ai/bulk-jobs` };
}

async function metadata(page) {
  await page.goto('/iptv');
  await page.getByRole('button', { name: 'Metadata', exact: true }).click();
}

async function maintenance(page) {
  await page.goto('/cleanup');
  await page.getByRole('tab', { name: 'IPTV', exact: true }).click();
}

const bulkPanel = page => page.getByRole('region', { name: 'ChatGPT matching' });
const progressBar = bulk => bulk.getByRole('progressbar', { name: 'ChatGPT matching progress' });
const snapshot = async (request, id, view = 'pending_matches') => (
  await (await request.get(`/api/ai/jobs/${id}?review_view=${view}`)).json()
);

async function cancelFixtureJob(request, id) {
  const job = await snapshot(request, id);
  const response = await request.post(`/api/ai/jobs/${id}/cancel`, { data: {
    revision: job.revision, run_number: job.cursor.run_number,
  } });
  expect(response.ok()).toBeTruthy();
}

async function completedFixture(request) {
  const response = await request.post('/api/test/iptv-bulk-fixture', {
    data: { count: 6413, saved: true, completed: true },
  });
  expect(response.ok()).toBeTruthy();
  const fixture = await response.json();
  return { ...fixture, endpoint: `/api/iptv/providers/${fixture.provider_id}/movies/ai/bulk-jobs` };
}

async function selectUnmatched(page) {
  await page.getByRole('button', { name: 'Unmatched', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Select all filtered' })).toBeEnabled();
  await page.getByRole('button', { name: 'Select all filtered' }).click();
  await page.getByRole('button', { name: 'Match with ChatGPT' }).click();
}

test('IPTV opens on enrichment and explicitly controls only the selected provider', async ({ page, request }) => {
  await configure(request);
  const seeded = await request.post('/api/test/iptv-bulk-fixture', { data: { count: 3 } });
  expect(seeded.ok()).toBeTruthy();
  const { provider_id: providerId } = await seeded.json();
  const path = '/api/iptv/providers/' + providerId + '/movies';
  const status = await (await request.get(path + '/metadata/status')).json();
  const commands = [];
  let worker = { ...status, state: 'idle', consent: false, automatic_remaining: 2, classification_review: 1,
    matches: { unprocessed: 3 } };
  await page.route('**' + path + '/metadata/status*', route => route.fulfill({ json: worker }));
  await page.route('**/movies/enrichment/*', async route => {
    const url = new URL(route.request().url());
    expect(url.pathname.startsWith(path + '/enrichment/')).toBeTruthy();
    const action = url.pathname.split('/').at(-1);
    commands.push([action, route.request().postDataJSON()]);
    worker = { ...worker, state: action === 'start' ? 'running' : 'paused', consent: true };
    await route.fulfill({ json: { status: worker } });
  });
  await metadata(page);
  await expect(page.getByRole('button', { name: 'ChatGPT matching', exact: true })).toHaveCount(0);
  const panel = page.getByRole('region', { name: 'Enrich Metadata', exact: true });
  await expect(panel.getByText('2 pending CP work', { exact: true })).toBeVisible();
  await expect(panel.getByText('Category unknown 1')).toBeVisible();
  const start = panel.getByRole('button', { name: 'Start enrichment', exact: true });
  await expect(start).toBeEnabled();
  expect(commands).toEqual([]);
  await page.screenshot({ path: process.env.CP_TEST_ROOT + '/iptv-enrich-ready.png' });
  await start.click();
  await panel.getByRole('button', { name: 'Pause', exact: true }).click();
  await expect(panel.getByRole('button', { name: 'Resume', exact: true })).toBeEnabled();
  expect(commands).toEqual([['start', { consent: true, diagnostic: false }], ['pause', {}]]);
});

test('a delayed projection retry preserves the selected provider status', async ({ page, request }) => {
  await configure(request);
  const other = await (await request.post('/api/test/iptv-bulk-fixture', { data: { count: 3 } })).json();
  const first = await (await request.post('/api/test/iptv-bulk-fixture', { data: { count: 3 } })).json();
  const firstPath = `/api/iptv/providers/${first.provider_id}/movies`;
  const otherPath = `/api/iptv/providers/${other.provider_id}/movies`;
  const firstStatus = await (await request.get(firstPath + '/metadata/status')).json();
  const otherStatus = await (await request.get(otherPath + '/metadata/status')).json();
  await page.route('**' + firstPath + '/metadata/status*', route => route.fulfill({ json: {
    ...firstStatus, projection: { ...firstStatus.projection, state: 'failed' },
  } }));
  await page.route('**' + otherPath + '/metadata/status*', route => route.fulfill({ json: {
    ...otherStatus, state: 'idle', automatic_remaining: 2,
  } }));
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**' + firstPath + '/projection/retry', async route => {
    await gate;
    await route.fulfill({ json: { ...firstStatus.projection, state: 'running' } });
  });
  try {
    await metadata(page);
    const panel = page.getByRole('region', { name: 'Enrich Metadata', exact: true });
    const start = panel.getByRole('button', { name: 'Start enrichment', exact: true });
    const retryRequest = page.waitForRequest('**' + firstPath + '/projection/retry');
    await panel.getByRole('button', { name: 'Retry projection' }).click();
    await retryRequest;
    await page.getByLabel('Active IPTV provider').selectOption(other.provider_id);
    await expect(start).toBeEnabled();
    const retryResponse = page.waitForResponse('**' + firstPath + '/projection/retry');
    release();
    await retryResponse;
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await expect(start).toBeEnabled();
    await expect(panel.getByText('2 pending CP work', { exact: true })).toBeVisible();
  } finally {
    release();
  }
});

test('a resync exposes new first-pass work and Continue can recover from an early worker exit', async ({ page, request }) => {
  await configure(request);
  const fixture = await (await request.post('/api/test/iptv-bulk-fixture', { data: { count: 3 } })).json();
  const provider = `/api/iptv/providers/${fixture.provider_id}`;
  let status = await (await request.get(provider + '/status')).json();
  let worker = await (await request.get(provider + '/movies/metadata/status')).json();
  worker = { ...worker, state: 'complete', consent: true, evaluated: 1, automatic_remaining: 0,
    classification_review: 1, matches: { 'matched-manual': 1, unmatched: 1 } };
  await page.route('**' + provider + '/status', route => route.fulfill({ json: status }));
  await page.route('**' + provider + '/movies/metadata/status*', route => route.fulfill({ json: worker }));
  await page.route('**' + provider + '/sync', route => {
    status = { ...status, sync: { ...status.sync, state: 'running' } };
    return route.fulfill({ json: { status } });
  });
  let attempts = 0;
  await page.route('**' + provider + '/movies/enrichment/resume', route => {
    attempts += 1;
    expect(route.request().postDataJSON()).toEqual({});
    worker = attempts === 1 ? { ...worker, state: 'crashed', worker_error: 'Worker exited before finishing' }
      : { ...worker, state: 'complete', worker_error: '', automatic_remaining: 0 };
    const { projection, ...control } = worker;
    return route.fulfill({ json: control });
  });

  await metadata(page);
  const panel = page.getByRole('region', { name: 'Enrich Metadata', exact: true });
  const progress = panel.getByRole('progressbar', { name: 'IPTV first-pass progress' });
  await expect(progress).toHaveAttribute('aria-valuenow', '3');
  await expect(panel.getByText('First pass complete', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Sync IPTV catalog' }).click();
  await expect(panel.getByText('Syncing provider catalog…')).toBeVisible();
  const generation = Number(status.generation) + 1;
  status = { ...status, generation, sync: { ...status.sync, state: 'complete' } };
  worker = { ...worker, sources: 4, automatic_remaining: 1, source_generation: generation,
    summary_revision: worker.summary_revision + 1,
    projection: { ...worker.projection, source_generation: generation, published: 4, total: 4, processed: 4 } };
  const resume = panel.getByRole('button', { name: 'Continue enrichment' });
  await expect(resume).toBeEnabled();
  await expect(panel.getByText('Ready to continue', { exact: true })).toBeVisible();
  await expect(panel.getByText('1 pending CP work', { exact: true })).toBeVisible();
  await expect(progress).toHaveAttribute('aria-valuenow', '3');
  await resume.click();
  await expect(panel.getByText('Worker exited before finishing')).toBeVisible();
  await expect(resume).toBeEnabled();
  await resume.click();
  await expect(progress).toHaveAttribute('aria-valuenow', '4');
  await expect(panel.getByText('First pass complete', { exact: true })).toBeVisible();
  expect(attempts).toBe(2);
  await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/iptv-first-pass-after-resync.png` });
});

test('one Unmatched list can submit all settled reasons in one ChatGPT session', async ({ page, request }) => {
  await configure(request);
  const seeded = await request.post('/api/test/iptv-bulk-fixture', { data: { count: 3, mixed_unmatched: true } });
  expect(seeded.ok()).toBeTruthy();
  const fixture = await seeded.json();
  const endpoint = `/api/iptv/providers/${fixture.provider_id}/movies/ai/bulk-jobs`;
  await maintenance(page);
  const list = page.getByRole('region', { name: 'Unmatched listings' });
  await expect(list.getByText('Unmatched · 3 listings', { exact: true })).toBeVisible();
  for (const reason of ['No verified match', 'Uncertain match', 'Category unknown']) {
    await expect(list.getByText(reason, { exact: true })).toBeVisible();
  }
  await expect(list.getByRole('combobox', { name: 'Status', exact: true })).toHaveCount(0);
  await list.getByRole('button', { name: 'Select all filtered' }).click();
  await expect(list.getByText('3 filtered sources selected')).toBeVisible();
  await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/iptv-unified-unmatched.png` });
  await list.getByRole('button', { name: 'Match with ChatGPT' }).click();
  const panel = bulkPanel(page);
  await expect(panel.getByText(/3 selected sources/)).toBeVisible();
  await request.post('/api/test/ai-phases', { data: { hold: ['retrieving'] } });
  let job;
  try {
    const posted = page.waitForResponse(response => response.url().endsWith(endpoint) && response.request().method() === 'POST');
    await panel.getByRole('button', { name: 'Start matching' }).click();
    const response = await posted;
    expect(response.status()).toBe(202);
    expect(response.request().postDataJSON()).toMatchObject({
      selection_mode: 'all-filtered', expected_source_count: 3,
      filters: { review_scope: 'leftovers', review_view: 'unmatched' },
    });
    job = await response.json();
    expect(job.bulk.total).toBe(3);
    await expect(panel.getByText(/Scanned queue: Unmatched/)).toBeVisible();
  } finally {
    if (job) await cancelFixtureJob(request, job.id);
    await request.post('/api/test/ai-phases', { data: { release: 'all' } });
  }
});

test('catalog recovery resumes the saved matching job after preparation', async ({ page, request }) => {
  await configure(request);
  const response = await request.post('/api/test/iptv-bulk-fixture', { data: { count: 3, stale_bulk: true } });
  expect(response.ok()).toBeTruthy();
  const fixture = await response.json();
  let preparing = true;
  await page.route(`**/api/iptv/providers/${fixture.provider_id}/movies/metadata/status*`, async route => {
    const response = await route.fetch();
    const data = await response.json();
    if (!preparing) return route.fulfill({ response, json: data });
    await route.fulfill({ response, json: { ...data, projection: { ...data.projection, state: 'running' } } });
  });
  await maintenance(page);
  const bulk = bulkPanel(page);
  await expect(progressBar(bulk)).toHaveAttribute('aria-valuenow', '1');
  await expect(progressBar(bulk)).toHaveAttribute('aria-valuemax', '3');
  const resume = bulk.getByRole('button', { name: 'Resume 2 unfinished sources' });
  await expect(resume).toBeDisabled();
  await expect(bulk.getByText('Preparing provider movies. See progress in IPTV Metadata.')).toBeVisible();
  await expect(bulk.getByRole('progressbar', { name: 'Provider movie preparation' })).toHaveCount(0);
  preparing = false;
  await expect(resume).toBeEnabled();
  const continued = page.waitForResponse(response => response.url().endsWith(`/api/ai/jobs/${fixture.job_id}/continue`));
  await resume.click();
  expect((await continued).status()).toBe(202);
  await expect(progressBar(bulk)).toHaveAttribute('aria-valuenow', '3');
  await expect(bulk.getByText('Matching session complete.')).toBeVisible();
  const saved = await snapshot(request, fixture.job_id, 'needs_attention');
  expect(saved.results[0].provider_title).toBe('Fixture Movie (2024)');
  expect(saved.cursor.run_number).toBe(1);
  expect(saved.bulk.total).toBe(3);
});

test('saved search-limit recheck after sync keeps request usage and applies the verified result', async ({ page, request }) => {
  await configure(request);
  const setup = await request.post('/api/test/iptv-bulk-fixture', { data: { count: 3, search_recheck: true } });
  expect(setup.ok()).toBeTruthy();
  const fixture = await setup.json();
  await maintenance(page);
  await page.getByRole('button', { name: 'ChatGPT matching', exact: true }).click();
  const bulk = bulkPanel(page);
  const recheck = bulk.getByRole('button', { name: 'Recheck 1 search-limit listing with TMDB' });
  await expect(recheck).toBeEnabled();
  const oldJob = await snapshot(request, fixture.job_id);
  const response = page.waitForResponse(r => r.url().endsWith(`/api/ai/jobs/${fixture.job_id}/continue`));
  await recheck.click();
  expect((await response).status()).toBe(202);
  await expect(bulk.getByRole('progressbar', { name: 'TMDB recheck progress' })).toHaveAttribute('aria-valuenow', '1');
  await expect(bulk.getByText('Matching session complete.')).toBeVisible();
  await expect(bulk.getByText(/1 ChatGPT requests used/)).toBeVisible();
  await expect(recheck).toHaveCount(0);
  const applied = await snapshot(request, fixture.job_id, 'applied');
  expect(applied.bulk.catalog_generation).toBeGreaterThan(oldJob.bulk.catalog_generation);
  expect(applied.results.map(row => row.candidate_tmdb_id)).toEqual([550]);
});

test('preparation gates launch and refreshes selected sources on the matching tab', async ({ page, request }) => {
  test.setTimeout(100_000);
  await configure(request);
  const fixture = await completedFixture(request);
  const savedScope = async route => {
    const response = await route.fetch();
    const data = await response.json();
    const job = data.job || data;
    if (job.bulk) job.bulk.selection_scope = { mode: 'all-filtered', filters: { review_view: 'needs-review' } };
    await route.fulfill({ response, json: data });
  };
  await page.route(`**${fixture.endpoint}/latest?*`, savedScope);
  await page.route(`**/api/ai/jobs/${fixture.job_id}?*`, savedScope);
  let preparing = true;
  let holdSelection = false;
  let refreshing = false;
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const writes = [];
  page.on('request', item => {
    if (item.method() === 'POST' && item.url().endsWith(fixture.endpoint)) writes.push(item.postDataJSON());
  });
  await page.route(`**/api/iptv/providers/${fixture.provider_id}/movies/metadata/status*`, async route => {
    const response = await route.fetch();
    const data = await response.json();
    await route.fulfill({ response, json: { ...data, projection: { ...data.projection,
      state: preparing ? 'running' : 'complete', processed: preparing ? 3200 : 6413, total: 6413 } } });
  });
  await page.route(`**/api/iptv/providers/${fixture.provider_id}/movies/metadata/review?*`, async route => {
    if (holdSelection) { refreshing = true; await gate; }
    await route.continue().catch(() => {});
  });
  let launched;
  try {
    await maintenance(page);
    await selectUnmatched(page);
    const bulk = bulkPanel(page);
    const start = bulk.getByRole('button', { name: /^Start (bulk job|matching)$/ });
    await expect(start).toBeDisabled();
    const launch = bulk.getByRole('region', { name: 'New matching session' });
    const previous = bulk.getByRole('region', { name: 'Previous matching session' });
    await expect(launch.getByText(/Queue: Unmatched/)).toBeVisible();
    await expect(previous.getByText(/Scanned queue: Needs review/)).toBeVisible();
    await expect(launch.getByText('Preparing provider movies. See progress in IPTV Metadata.')).toBeVisible();
    await expect(bulk.getByRole('progressbar', { name: 'Provider movie preparation' })).toHaveCount(0);
    await expect(previous.getByText('Matching session complete.')).toBeVisible();
    const buttonBox = await start.boundingBox();
    const fieldBox = await launch.getByLabel('Titles per ChatGPT request').boundingBox();
    const launchBox = await launch.boundingBox();
    const previousBox = await previous.boundingBox();
    expect(buttonBox.x).toBeGreaterThan(fieldBox.x + fieldBox.width);
    expect(buttonBox.x + buttonBox.width).toBeGreaterThan(launchBox.x + launchBox.width - 40);
    expect(previousBox.y).toBeGreaterThanOrEqual(launchBox.y + launchBox.height);
    await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/bulk-preparing.png` });
    expect(writes).toHaveLength(0);
    const metadataPage = await page.context().newPage();
    try {
      await metadataPage.route(`**/api/iptv/providers/${fixture.provider_id}/movies/metadata/status*`, async route => {
        const response = await route.fetch();
        const data = await response.json();
        await route.fulfill({ response, json: { ...data, projection: { ...data.projection,
          state: 'running', processed: 3200, total: 6413 } } });
      });
      await metadata(metadataPage);
      await expect(metadataPage.getByRole('progressbar', { name: 'Provider movie preparation' })).toHaveAttribute('aria-valuenow', '3200');
      await expect(metadataPage.getByRole('progressbar', { name: 'IPTV first-pass progress' })).toBeVisible();
      await metadataPage.screenshot({ path: `${process.env.CP_TEST_ROOT}/iptv-metadata-preparing.png` });
    } finally {
      await metadataPage.close();
    }

    holdSelection = true;
    preparing = false;
    await expect.poll(() => refreshing).toBe(true);
    await expect(start).toBeDisabled();
    await expect(launch.getByText('Refreshing selected sources…')).toBeVisible();
    holdSelection = false;
    release();
    await expect(start).toBeEnabled();
    expect(writes).toHaveLength(0);
    await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/bulk-ready.png` });
    await request.post('/api/test/ai-phases', { data: { hold: ['retrieving'] } });
    const responsePromise = page.waitForResponse(response => response.url().endsWith(fixture.endpoint) && response.request().method() === 'POST');
    await start.click();
    const response = await responsePromise;
    expect(response.status()).toBe(202);
    launched = await response.json();
    expect(writes).toHaveLength(1);
    expect(writes[0]).toMatchObject({ expected_source_count: 6393, titles_per_request: 100 });
    await expect(bulk.getByRole('region', { name: 'Current matching session' })).toBeVisible();
    await expect(bulk.getByRole('region', { name: 'Current matching session' }).getByText(/Scanned queue: Unmatched/)).toBeVisible();
    await expect(bulk.getByRole('region', { name: 'Previous matching session' })).toHaveCount(0);
  } finally {
    release();
    if (launched) await cancelFixtureJob(request, launched.id);
    await request.post('/api/test/ai-phases', { data: { release: 'all' } });
  }
});

test('returning to IPTV Maintenance waits for fresh provider readiness', async ({ page, request }) => {
  await configure(request);
  const fixture = await completedFixture(request);
  await maintenance(page);
  await selectUnmatched(page);
  const bulk = bulkPanel(page);
  const start = bulk.getByRole('button', { name: 'Start matching' });
  await expect(start).toBeEnabled();
  const navigation = page.getByLabel('Primary navigation');
  for (const destination of ['Home', 'IPTV']) {
    await navigation.getByRole('button', { name: destination, exact: true }).click();
    let release;
    let requested = false;
    const gate = new Promise(resolve => { release = resolve; });
    const pattern = `**/api/iptv/providers/${fixture.provider_id}/movies/metadata/status*`;
    await page.route(pattern, async route => {
      requested = true;
      await gate;
      await route.continue().catch(() => {});
    });
    try {
      await navigation.getByRole('button', { name: 'Maintenance', exact: true }).click();
      await expect(bulk.getByText('Checking provider readiness…')).toBeVisible();
      await expect(start).toBeDisabled();
      await expect.poll(() => requested).toBe(true);
      release();
      await expect(start).toBeEnabled();
    } finally {
      release();
      await page.unroute(pattern);
    }
  }
});

test('preparation race recovers readiness and selection errors without automatically launching', async ({ page, request }) => {
  test.setTimeout(100_000);
  await configure(request);
  const fixture = await completedFixture(request);
  let preparing = false;
  let readinessFails = true;
  let rejectStart = true;
  let selectionFails = false;
  let attempts = 0;
  await page.route(`**/api/iptv/providers/${fixture.provider_id}/movies/metadata/status*`, async route => {
    if (readinessFails) return route.fulfill({ status: 503, json: { error: 'Provider status temporarily unavailable' } });
    const response = await route.fetch();
    const data = await response.json();
    await route.fulfill({ response, json: { ...data, projection: { ...data.projection,
      state: preparing ? 'running' : 'complete', processed: preparing ? 3000 : 6413, total: 6413 } } });
  });
  await page.route(`**/api/iptv/providers/${fixture.provider_id}/movies/metadata/review?*`, route =>
    selectionFails ? route.fulfill({ status: 503, json: { error: 'Selection refresh temporarily failed' } }) : route.continue());
  await page.route(`**${fixture.endpoint}`, async route => {
    if (route.request().method() !== 'POST') return route.continue();
    attempts += 1;
    if (!rejectStart) return route.continue();
    preparing = true;
    await route.fulfill({ status: 422, json: { error: {
      code: 'iptv_projection_in_progress', message: 'Wait until provider movies finish preparing.',
    } } });
  });
  await maintenance(page);
  await selectUnmatched(page);
  const bulk = bulkPanel(page);
  const start = bulk.getByRole('button', { name: /^Start (bulk job|matching)$/ });
  await expect(bulk.getByRole('button', { name: 'Retry readiness' })).toBeVisible();
  await expect(start).toBeDisabled();
  expect(attempts).toBe(0);
  readinessFails = false;
  await bulk.getByRole('button', { name: 'Retry readiness' }).click();
  await expect(start).toBeEnabled();
  await start.click();
  await expect(bulk.getByText('Preparing provider movies. See progress in IPTV Metadata.')).toBeVisible();
  await expect(bulk.getByRole('progressbar', { name: 'Provider movie preparation' })).toHaveCount(0);
  await expect(start).toBeDisabled();
  selectionFails = true;
  preparing = false;
  await expect(bulk.getByRole('button', { name: 'Retry selection' })).toBeVisible();
  await expect(start).toBeDisabled();
  selectionFails = false;
  await bulk.getByRole('button', { name: 'Retry selection' }).click();
  await expect(start).toBeEnabled();
  await expect(bulk.getByText('Wait until provider movies finish preparing.', { exact: true })).toHaveCount(0);
  expect(attempts).toBe(1);
  rejectStart = false;
  let launched;
  try {
    await request.post('/api/test/ai-phases', { data: { hold: ['retrieving'] } });
    const accepted = page.waitForResponse(response => response.url().endsWith(fixture.endpoint) && response.request().method() === 'POST');
    await start.click();
    const response = await accepted;
    expect(response.status()).toBe(202);
    launched = await response.json();
    expect(attempts).toBe(2);
  } finally {
    if (launched) await cancelFixtureJob(request, launched.id);
    await request.post('/api/test/ai-phases', { data: { release: 'all' } });
  }
});

test('desktop launch calculates the allowance and recovers dropped and hung status reads without replay', async ({ page, request }) => {
  test.setTimeout(100_000);
  await configure(request);
  const fixture = await seed(request);
  let latestReads = 0;
  await page.route('**/movies/ai/bulk-jobs/latest?*', route =>
    route.request().url().includes(fixture.provider_id) && ++latestReads === 1 ? route.abort('failed') : route.continue());
  let mode = 'normal';
  let hung = false;
  let releaseRead;
  const gate = new Promise(resolve => { releaseRead = resolve; });
  let activeId;
  const writes = [];
  page.on('request', item => {
    if (item.method() === 'POST' && /\/bulk-jobs$|\/api\/ai\/jobs\/.+\/(pause|continue|cancel)$/.test(item.url())) {
      writes.push(item.url());
    }
  });
  await page.route('**/api/ai/jobs/*?*', async route => {
    if (!activeId || !route.request().url().includes(activeId)) return route.continue();
    if (mode === 'drop') { mode = 'hang'; return route.abort('failed'); }
    if (mode === 'hang') {
      mode = 'normal';
      hung = true;
      await gate;
    }
    await route.continue().catch(() => {});
  });

  try {
    await request.post('/api/test/ai-phases', { data: { hold: ['retrieving'] } });
    await maintenance(page);
    await page.getByRole('button', { name: 'Unmatched', exact: true }).click();
    await expect(page.locator('.iptv-review-card-grid')).toContainText('Bulk specimen');
    await page.getByRole('button', { name: 'Select all filtered' }).click();
    await expect(page.getByText('6,413 filtered sources selected')).toBeVisible();
    await page.getByText('Actions', { exact: true }).click();
    await expect(page.getByText(/Standard actions accept up to 5,000/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Match selected with ChatGPT', exact: true })).toBeDisabled();
    await page.getByRole('button', { name: 'Match with ChatGPT' }).click();

    const bulk = bulkPanel(page);
    const size = bulk.getByLabel('Titles per ChatGPT request');
    await expect(size).toHaveValue('100');
    await expect(bulk.getByText('6,413 selected sources · 65 estimated first-pass requests')).toBeVisible();
    await size.fill('50');
    await expect(bulk.getByText('6,413 selected sources · 129 estimated first-pass requests')).toBeVisible();
    await size.fill('100');
    await expect.poll(() => latestReads).toBeGreaterThan(1);
    await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/iptv-bulk-start.png` });
    const launched = page.waitForResponse(response => response.url().endsWith(fixture.endpoint) &&
      response.request().method() === 'POST');
    await bulk.getByRole('button', { name: 'Start matching' }).click();
    const response = await launched;
    expect(response.status()).toBe(202);
    const job = await response.json();
    activeId = job.id;
    expect(job.request).toEqual({ bulk_call_budget: 969, titles_per_request: 100 });
    expect(job.bulk.total).toBe(6413);
    await expect(bulk.getByText('Waiting for the ChatGPT batch')).toBeVisible();
    const lastProcessed = await progressBar(bulk).getAttribute('aria-valuenow');
    mode = 'drop';
    await expect(bulk.getByText(/Reconnecting to job status.*Last successful status/)).toBeVisible();
    await expect(bulk.getByRole('button', { name: 'Pause matching' })).toBeDisabled();
    await expect(bulk.getByText('Waiting for the ChatGPT batch')).toHaveCount(0);
    await expect(progressBar(bulk)).toHaveAttribute('aria-valuenow', lastProcessed);
    const live = await snapshot(request, job.id);
    expect((await request.post(`/api/ai/jobs/${job.id}/pause`, { data: {
      run_number: live.cursor.run_number,
    } })).ok()).toBeTruthy();
    await request.post('/api/test/ai-phases', { data: { release: 'all' } });
    await expect.poll(() => hung).toBe(true);
    await expect(bulk.getByText('Paused by request.')).toBeVisible({ timeout: 20_000 });
    await expect(bulk.getByRole('button', { name: 'Resume matching' })).toBeEnabled();
    expect(writes).toEqual([expect.stringContaining(fixture.endpoint)]);

    await request.post('/api/test/ai-phases', { data: { hold: ['retrieving'] } });
    await bulk.getByRole('button', { name: 'Resume matching' }).click();
    await expect(progressBar(bulk)).toHaveAttribute('aria-valuenow', '100');
    await expect(bulk.getByRole('button', { name: 'Pause matching' })).toBeEnabled();
    await bulk.getByRole('button', { name: 'Pause matching' }).click();
    await request.post('/api/test/ai-phases', { data: { release: 'all' } });
    await expect(bulk.getByRole('button', { name: 'Resume matching' })).toBeEnabled();
    expect(writes.map(url => url.split('/').at(-1))).toEqual(['bulk-jobs', 'continue', 'pause']);

    await bulk.getByRole('button', { name: 'Review proposals (optional)' }).click();
    await expect(bulk.getByText('0 verified pending · 1 applied')).toBeVisible();
    await expect(bulk.getByRole('button', { name: /Apply .*verified matches/ })).toHaveCount(0);
    const paused = await snapshot(request, job.id);
    expect(paused.review_counts.classifications).toBe(paused.bulk.processed - 1);
    await bulk.getByRole('button', { name: 'Classifications (' + paused.review_counts.classifications + ')',
      exact: true }).click();
    const appliedClassification = page.waitForResponse(response => response.url().endsWith(`/${job.id}/apply`) &&
      response.request().method() === 'POST');
    await bulk.getByRole('button', { name: 'Apply 20 selected classifications' }).click();
    expect((await appliedClassification).ok()).toBeTruthy();
    await expect(bulk.getByText('20 applied · 0 locked · 0 skipped · 0 failed', { exact: true })).toBeVisible();

    await bulk.getByRole('button', { name: 'Cancel matching' }).click();
    await expect(bulk.getByText('Matching session cancelled. Saved results are available for review.')).toBeVisible();
    await page.getByRole('button', { name: 'Unmatched', exact: true }).click();
    await page.getByRole('button', { name: 'Add current page' }).click();
    await page.getByRole('button', { name: 'Match with ChatGPT' }).click();
    let acceptedId;
    await page.route(`**${fixture.endpoint}`, async route => {
      const response = await route.fetch();
      expect(response.status()).toBe(202);
      acceptedId = (await response.json()).id;
      await route.abort('failed');
    });
    await request.post('/api/test/ai-phases', { data: { hold: ['retrieving'] } });
    await bulk.getByRole('button', { name: 'Start matching' }).click();
    await expect.poll(() => acceptedId).toBeTruthy();
    expect(acceptedId).not.toBe(job.id);
    await expect(progressBar(bulk)).toHaveAttribute('aria-valuemax', '50');
    await expect(bulk.getByRole('button', { name: 'Pause matching' })).toBeEnabled();
    expect(writes.filter(url => url.endsWith('/bulk-jobs'))).toHaveLength(2);

    let releaseOldProvider;
    let capturedOldStatus = false;
    const oldProvider = new Promise(resolve => { releaseOldProvider = resolve; });
    await page.route(`**/api/ai/jobs/${acceptedId}?*`, async route => {
      const response = await route.fetch();
      capturedOldStatus = true;
      await oldProvider;
      await route.fulfill({ response }).catch(() => {});
    });
    try {
      await expect.poll(() => capturedOldStatus).toBe(true);
      await page.getByRole('combobox', { name: 'Active IPTV provider' }).selectOption(fixture.other_provider_id);
      await expect(page.getByRole('heading', { name: 'Synthetic provider' })).toBeVisible();
      releaseOldProvider();
      await page.getByRole('button', { name: 'ChatGPT matching', exact: true }).click();
      await expect(bulk.getByText('Select listings in Unmatched to start ChatGPT matching.')).toBeVisible();
      await expect(progressBar(bulk)).toHaveCount(0);
    } finally {
      releaseOldProvider();
      const active = await snapshot(request, acceptedId);
      await request.post(`/api/ai/jobs/${acceptedId}/pause`, { data: { run_number: active.cursor.run_number } });
    }
  } finally {
    releaseRead();
    await request.post('/api/test/ai-phases', { data: { release: 'all' } });
  }
});

test('one confirmation applies the entire saved job with proposal review closed', async ({ page, request }) => {
  test.setTimeout(150_000);
  await configure(request);
  const fixture = await seed(request, true);
  const url = `${fixture.endpoint}/${fixture.job_id}/apply`;
  const writes = [];
  page.on('request', item => {
    if (item.method() === 'POST' && item.url().endsWith(url)) writes.push(item.postDataJSON());
  });
  await maintenance(page);
  const bulk = bulkPanel(page);
  await expect(progressBar(bulk)).toHaveAttribute('aria-valuenow', '3741');
  await expect(progressBar(bulk)).toHaveAttribute('aria-valuemax', '6413');
  await expect(bulk.getByText('39 ChatGPT requests used · 61 of the approved 100 remaining · 100 titles per request')).toBeVisible();
  await expect(bulk.getByText('2,281 awaiting Apply · 20 applied')).toBeVisible();
  await expect(bulk.getByRole('button', { name: 'Review proposals (optional)' })).toHaveAttribute('aria-expanded', 'false');
  await expect(bulk.locator('.iptv-proposal-panel')).toHaveCount(0);
  await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/iptv-bulk-paused.png` });

  await bulk.getByRole('button', { name: 'Apply all 2,281 verified matches' }).click();
  const confirm = page.getByRole('dialog', { name: 'Apply verified IPTV matches' });
  await expect(confirm).toContainText('Apply all 2,281 verified Film matches to Bulk fixture saved.');
  const accepted = page.waitForResponse(response => response.url().endsWith(url) && response.request().method() === 'POST');
  await confirm.getByRole('button', { name: 'Apply all verified matches' }).click();
  const response = await accepted;
  expect(response.status()).toBe(202);
  const claim = await response.json();
  expect(writes).toHaveLength(1);
  expect(writes[0]).toMatchObject({ kind: 'match', scope: 'verified_pending', expected_count: 2281 });
  expect(writes[0]).not.toHaveProperty('proposal_ids');
  const replay = await request.post(url, { data: writes[0] });
  expect(replay.status()).toBe(202);
  expect((await replay.json()).apply_id).toBe(claim.apply_id);
  const foreign = await request.post(url.replace(fixture.provider_id, fixture.other_provider_id), { data: writes[0] });
  expect(foreign.status()).toBe(409);

  await expect(bulk.getByText('0 awaiting Apply · 2,301 applied')).toBeVisible({ timeout: 110_000 });
  await expect(bulk.getByText(/Apply complete · 2,281 applied · 0 locked · 0 skipped · 0 failed/)).toBeVisible();
  const saved = await snapshot(request, fixture.job_id);
  expect(saved.results).toEqual([]);
  expect(saved.review_counts).toMatchObject({ applied: 2301, pending_matches: 0, needs_attention: 1440 });
  const committed = await (await request.get(
    `/api/iptv/providers/${fixture.provider_id}/movies/source:${fixture.last_verified_source}`)).json();
  expect(committed.tmdb_id).toBe(550);

  await bulk.getByRole('button', { name: 'Review proposals (optional)' }).click();
  await expect(bulk.getByText('No verified matches awaiting Apply.')).toBeVisible();
  await bulk.getByRole('button', { name: 'Applied (2,301)', exact: true }).click();
  await expect(bulk.locator('.iptv-proposal-panel')).toContainText('Saved source 0');
  await bulk.getByRole('button', { name: 'Next matching proposal page' }).click();
  await expect(bulk.getByText('Page 2 of 116')).toBeVisible();
  await expect(bulk.locator('.iptv-proposal-panel')).toContainText('Saved source 20');
  await bulk.getByRole('button', { name: 'Needs attention (1,440)', exact: true }).click();
  await expect(bulk.locator('.iptv-proposal-panel')).toContainText('Saved source 2301');
  await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/iptv-bulk-applied.png` });
});

test('new jobs finish after the title pass and apply verified films automatically', async ({ page, request }) => {
  await configure(request);
  const created = await request.post('/api/test/iptv-bulk-fixture', { data: { count: 3 } });
  expect(created.ok()).toBeTruthy();
  const fixture = await created.json();
  const writes = [];
  page.on('request', item => {
    if (item.method() === 'POST' && item.url().includes('/providers/' + fixture.provider_id + '/') &&
        item.url().includes('/bulk-jobs')) writes.push(item.url().split('/').at(-1));
  });
  try {
    await request.post('/api/test/ai-phases', { data: { hold: ['retrieving'] } });
    await maintenance(page);
    await selectUnmatched(page);
    const bulk = bulkPanel(page);
    await expect(bulk.getByText(/Verified film matches apply automatically/)).toBeVisible();
    await bulk.getByRole('button', { name: 'Start matching' }).click();
    await expect(bulk.getByText('Waiting for the ChatGPT batch')).toBeVisible();
    await expect(bulk.getByText('0 verified pending · 1 applied')).toBeVisible();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await request.post('/api/test/ai-phases', { data: { release: 'all' } });
    await expect(bulk.getByText('Matching session complete.')).toBeVisible();
    await expect(bulk.getByText('0 verified pending · 2 applied')).toBeVisible();
    await expect(bulk.getByText(/^1 ChatGPT requests used/)).toBeVisible();
    await expect(bulk.getByText(/Recovery requests/)).toHaveCount(0);
    const saved = await (await request.get('/api/iptv/providers/' + fixture.provider_id +
      '/movies/ai/bulk-jobs/latest?review_view=pending_matches')).json();
    expect(saved.job.bulk.recovery_enabled).toBe(false);
    expect(saved.job.bulk.recovery.admitted).toBe(0);
    await expect(progressBar(bulk)).toHaveAttribute('aria-valuenow', '3');
    await bulk.getByRole('button', { name: 'Review proposals (optional)' }).click();
    await bulk.getByRole('button', { name: 'Needs attention (1)' }).click();
    await expect(bulk.getByText('ChatGPT could not classify this source confidently.').first()).toBeVisible();
    await page.screenshot({ path: process.env.CP_TEST_ROOT + '/iptv-first-pass-completed.png' });
    await page.getByRole('button', { name: 'Unmatched', exact: true }).click();
    await expect(page.locator('.iptv-review-card-grid')).toContainText('Missing Story');
    await expect(page.locator('.iptv-review-card-grid')).not.toContainText('Crystal River');
    expect(writes).toEqual(['bulk-jobs']);
  } finally {
    await request.post('/api/test/ai-phases', { data: { release: 'all' } });
  }
});

test('first-pass usage pause keeps saved writes and can be cancelled', async ({ page, request }) => {
  await configure(request);
  expect((await request.post('/api/test/iptv-bulk-fixture', { data: { count: 3 } })).ok()).toBeTruthy();
  try {
    await request.post('/api/test/ai-fixture', { data: { failure: 'usage_limit_reached' } });
    await maintenance(page);
    await selectUnmatched(page);
    const bulk = bulkPanel(page);
    await bulk.getByRole('button', { name: 'Start matching' }).click();
    await expect(bulk.getByText('ChatGPT plan usage exhausted. Resume when usage is available.')).toBeVisible();
    await expect(bulk.getByText('0 verified pending · 1 applied')).toBeVisible();
    await expect(bulk.getByRole('button', { name: 'Resume matching' })).toBeEnabled();
    await bulk.getByRole('button', { name: 'Cancel matching' }).click();
    await expect(bulk.getByText('Matching session cancelled. Saved results are available for review.')).toBeVisible();
    await expect(bulk.getByText('0 verified pending · 1 applied')).toBeVisible();
  } finally {
    await request.post('/api/test/ai-fixture', { data: { failure: null } });
  }
});

test('an automatic write failure is visible and retries the write without new inference', async ({ page, request }) => {
  await configure(request);
  expect((await request.post('/api/test/iptv-bulk-fixture', { data: { count: 3, fail_write: true } })).ok()).toBeTruthy();
  await maintenance(page);
  await selectUnmatched(page);
  const bulk = bulkPanel(page);
  await bulk.getByRole('button', { name: 'Start matching' }).click();
  await expect(bulk.getByText('Matching session complete.')).toBeVisible();
  await expect(bulk.getByText('Automatic Apply · 1 applied · 0 locked · 0 skipped · 1 failed')).toBeVisible();
  await bulk.getByRole('button', { name: 'Review proposals (optional)' }).click();
  await bulk.getByRole('button', { name: 'Needs attention (2)' }).click();
  await expect(bulk.getByText('Fixture catalogue write failed')).toBeVisible();
  await bulk.getByRole('button', { name: 'Retry 1 failed write' }).click();
  await page.getByRole('dialog', { name: 'Retry failed writes' }).getByRole('button', { name: 'Retry failed writes' }).click();
  await expect(bulk.getByText('0 verified pending · 2 applied')).toBeVisible();
  await expect(bulk.getByText('Automatic Apply · 2 applied · 0 locked · 0 skipped · 0 failed')).toBeVisible();
  await expect(bulk.getByText(/^1 ChatGPT requests used/)).toBeVisible();
});

test('catalog requests stay independent and advanced controls have one destination each', async ({ page, request }) => {
  await configure(request);
  let releaseSlow;
  let releaseQueue;
  const slow = new Promise(resolve => { releaseSlow = resolve; });
  const oldQueue = new Promise(resolve => { releaseQueue = resolve; });
  let delayedReview = false;
  const searches = [];
  const fixture = await (await request.post('/api/test/ai-fixture', { data: { iptv_unmatched: true } })).json();
  expect((await request.post('/api/iptv/providers/selection', { data: { provider_id: fixture.provider_id } })).ok()).toBeTruthy();
  for (const pattern of ['**/api/iptv/metadata/settings', '**/movies/facets?*']) {
    await page.route(pattern, async route => { await slow; await route.continue().catch(() => {}); });
  }
  await page.route('**/movies/metadata/review?*', async route => {
    const params = new URL(route.request().url()).searchParams;
    if (params.get('q')) searches.push(params.get('q'));
    if (params.get('category') === 'film') {
      delayedReview = true;
      await oldQueue;
    }
    await route.continue().catch(() => {});
  });
  try {
    await maintenance(page);
    await page.getByRole('button', { name: 'Unmatched', exact: true }).click();
    const category = page.getByRole('combobox', { name: 'Filter by category' });
    await category.selectOption('film');
    await expect.poll(() => delayedReview).toBe(true);
    await expect(page.getByText('Loading unmatched listings')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Select all filtered' })).toBeDisabled();
    await category.selectOption('');
    const grid = page.locator('.iptv-review-card-grid');
    await expect(grid).toContainText('Fixture Movie');
    releaseQueue();
    const search = page.getByPlaceholder('Search unmatched listings...');
    await search.fill('Fix');
    await search.fill('Fixture Movie');
    await expect.poll(() => searches).toEqual(['Fixture Movie']);
    await expect(grid).toContainText('Fixture Movie');
    await expect(page.getByRole('button', { name: 'Improve this provider\'s Movies' })).toHaveCount(0);
    await expect(page.getByText('IPTV TMDB credential', { exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'ChatGPT matching', exact: true }).click();
    await expect(bulkPanel(page)).toBeVisible();
    releaseSlow();
    await page.getByRole('button', { name: 'Unmatched', exact: true }).click();
    await expect(grid).toContainText('Fixture Movie');
    await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/iptv-catalog-review.png` });
    await page.goto('/settings');
    const settings = page.locator('#settings-iptv');
    await expect(settings.getByRole('heading', { name: 'Movie metadata' })).toBeVisible();
    await expect(settings.getByRole('button', { name: 'Test saved credential' })).toBeVisible();
    await expect(settings.getByText('Enable IPTV Ollama', { exact: true })).toBeHidden();
    await settings.getByText('Advanced AI', { exact: true }).click();
    await expect(settings.getByText('Enable IPTV Ollama', { exact: true })).toBeVisible();
    await settings.screenshot({ path: `${process.env.CP_TEST_ROOT}/iptv-metadata-settings.png` });

    await page.goto('/cleanup');
    await page.getByRole('tab', { name: 'IPTV', exact: true }).click();
    await expect(page.getByText('Local projection', { exact: true })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Start enrichment', exact: true })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Retry failures', exact: true })).toBeVisible();
    await page.getByText('Recheck automatic matches', { exact: true }).click();
    await expect(page.getByRole('button', { name: 'Preview rechecking automatic matches' })).toBeVisible();
    await page.getByText('Group versions of the same movie', { exact: true }).click();
    await expect(page.getByRole('button', { name: 'Preview grouping versions of the same movie' })).toBeVisible();
    await page.screenshot({ path: `${process.env.CP_TEST_ROOT}/iptv-maintenance.png` });
  } finally {
    releaseSlow();
    releaseQueue();
  }
});
