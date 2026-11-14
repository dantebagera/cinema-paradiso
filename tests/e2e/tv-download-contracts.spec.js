import { test, expect } from '@playwright/test';

test.skip(process.env.CP_TV_E2E !== '1', 'Requires disposable TV fixture server');
const evidence = 'docs/verification/tv-download-contracts';
async function config(request, data) {
  const response = await request.post('/api/prowlarr/config', {data});
  expect(response.ok()).toBeTruthy();
}
async function openSelector(page, domain) {
  await page.goto('/settings');
  const row = page.locator('#settings-prowlarr .dialog-field').filter({has:page.getByText(`${domain} trusted indexers`, {exact:true})});
  await row.getByRole('button', {name:'Select indexers'}).click();
  return page.getByRole('dialog', {name:`${domain} trusted indexers`, exact:true});
}

test('independent Settings selectors save through the real API and Cancel discards edits', async ({page, request}) => {
  await config(request, {download_trusted_indexers:['2'], tv_download_trusted_indexers:['7','9']});
  let dialog = await openSelector(page, 'Movie');
  await expect(dialog.getByRole('checkbox', {name:'YTS', exact:true})).toBeChecked();
  await dialog.getByRole('checkbox', {name:'LimeTorrents', exact:true}).check();
  await dialog.getByRole('button', {name:'Cancel', exact:true}).click();
  dialog = await openSelector(page, 'Movie');
  await expect(dialog.getByRole('checkbox', {name:'LimeTorrents', exact:true})).not.toBeChecked();
  await page.keyboard.press('Escape');
  dialog = await openSelector(page, 'TV');
  await expect(dialog.getByRole('checkbox', {name:'LimeTorrents', exact:true})).toBeChecked();
  await expect(dialog.getByRole('checkbox', {name:'1337x', exact:true})).toBeChecked();
  await dialog.getByRole('checkbox', {name:'1337x', exact:true}).uncheck();
  await dialog.getByRole('button', {name:'Save trusted indexers'}).focus();
  await page.keyboard.press('Tab');
  await expect(dialog.getByRole('button', {name:'Close TV trusted indexers'})).toBeFocused();
  await dialog.getByRole('button', {name:'Save trusted indexers'}).click();
  await expect(dialog).toHaveCount(0);
  const saved = await (await request.get('/api/prowlarr/config')).json();
  expect(saved.effective_download_trusted_indexers).toEqual(['2']);
  expect(saved.effective_tv_download_trusted_indexers).toEqual(['7']);
  const calls = await (await request.post('/__tv_fixture/source-policy')).json();
  expect(calls.automatic_indexers).toEqual(['7']);
  expect(calls.manual_indexers).toBeNull();
  await page.screenshot({path:`${evidence}/settings.png`});
  await config(request, {tv_download_trusted_indexers:['7','9']});
});

test('new unsaved collection stays read-only through review then reserves and publishes after explicit Download', async ({page, request}) => {
  await request.post('/__tv_fixture/new-home/begin');
  try {
    const before = (await (await request.get('/api/tv/acquisitions')).json()).items.length;
    await page.goto('/discover');
    await page.getByRole('tablist',{name:'Discover tools'}).getByRole('button',{name:'TV Shows'}).click();
    await page.getByRole('button',{name:'Search, filters & selection',exact:true}).click();
    await page.getByRole('textbox',{name:'Search TV shows',exact:true}).fill('Louie Fixture');
    await page.getByRole('button',{name:'Search TV',exact:true}).click();
    await page.getByRole('link',{name:'Open Louie Fixture',exact:true}).click();
    await page.getByRole('article',{name:/S01E01/}).getByRole('button',{name:'Download episode'}).click();
    const dialog = page.getByRole('dialog',{name:'TV release review'});
    await expect(dialog).toContainText('Louie Fixture (2010)');
    await expect(dialog).toContainText('Season 01');
    expect((await (await request.get('/api/tv/acquisitions')).json()).items.length).toBe(before);
    expect(await (await request.get('/__tv_fixture/new-home/state')).json()).toEqual({tracked:false,home_exists:false});
    await page.screenshot({path:`${evidence}/new-home-review.png`});
    await dialog.getByRole('button',{name:'Download selected releases',exact:true}).click();
    await expect(dialog.getByRole('button',{name:'Queued',exact:true})).toBeVisible();
    expect(await (await request.get('/__tv_fixture/new-home/state')).json()).toEqual({tracked:true,home_exists:false});
    const result = await (await request.post('/__tv_fixture/new-home/complete')).json();
    expect(result.job.state).toBe('imported');
    expect(result.source_exists).toBe(false);
    expect(result.binding_paths).toEqual(result.job.imported_paths);
    expect(result.binding_paths[0]).toMatch(/Louie Fixture \(2010\)[\\/]Season 01[\\/]Louie.Fixture.S01E01/);
    await page.goto(`/tv/series/${result.job.tv_request.series_id}`);
    await expect(page.getByRole('article',{name:/S01E01/})).toContainText('Available locally');
    await page.getByRole('article',{name:/S01E01/}).scrollIntoViewIfNeeded();
    await page.screenshot({path:`${evidence}/new-home-imported.png`});
  } finally { await request.post('/__tv_fixture/new-home/reset'); }
});

test('existing flat collection exposes destination blocker and preserves its media', async ({page, request}) => {
  await request.post('/__tv_fixture/new-home/begin');
  try {
    const flat = await (await request.post('/__tv_fixture/new-home/flat')).json();
    await page.goto(`/tv/series/${flat.series_id}`);
    await page.getByRole('button',{name:'Preview targets',exact:true}).click();
    await expect(page.getByRole('alert')).toContainText('Existing flat or unresolved TV collection requires destination review');
    await page.screenshot({path:`${evidence}/flat-destination.png`});
    const rows = (await (await request.get(`/api/tv/series/${flat.series_id}/selection`)).json()).items;
    expect(rows[0].versions[0].path).toBe(flat.path);
    expect(rows[0].available).toBe(true);
  } finally { await request.post('/__tv_fixture/new-home/reset'); }
});

test('selector keeps saved selection on failed save and exposes unavailable and empty states', async ({page}) => {
  const dialog = await openSelector(page, 'TV');
  await page.route('**/api/prowlarr/config', route => route.request().method() === 'POST'
    ? route.fulfill({status:400,json:{error:'Fixture save failure'}}) : route.continue());
  await dialog.getByRole('checkbox', {name:'LimeTorrents',exact:true}).uncheck();
  await dialog.getByRole('button', {name:'Save trusted indexers'}).click();
  await expect(dialog.getByRole('alert')).toContainText('not saved');
  await expect(dialog).toBeVisible();
  await page.screenshot({path:`${evidence}/settings-error.png`});
  await dialog.getByRole('button', {name:'Cancel',exact:true}).click();
  await page.unroute('**/api/prowlarr/config');
  await page.locator('#settings-prowlarr .dialog-field').filter({has:page.getByText('TV trusted indexers',{exact:true})}).getByRole('button',{name:'Select indexers'}).click();
  await expect(page.getByRole('dialog').getByRole('checkbox',{name:'LimeTorrents',exact:true})).toBeChecked();
});

test('shared selector contains long source lists, shows load errors and discards unavailable and empty drafts', async ({page, request}) => {
  const saved = await (await request.get('/api/prowlarr/config')).json();
  await page.route('**/api/prowlarr/config', route => route.fulfill({json:{...saved,
    tv_download_trusted_indexers:['7','999'], indexers_error:'Fixture enabled-indexer loading failed',
    indexers:[...saved.indexers, ...Array.from({length:30},(_,i)=>({id:100+i,name:`Long source fixture ${i} with a descriptive name`}))]}}));
  let dialog = await openSelector(page, 'TV');
  await expect(dialog.getByRole('alert')).toContainText('enabled-indexer loading failed');
  await expect(dialog.getByRole('checkbox',{name:/Unavailable indexer 999/})).toBeChecked();
  expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  expect(await dialog.locator('.trusted-indexer-list').evaluate(el => el.scrollHeight > el.clientHeight)).toBe(true);
  await page.screenshot({path:`${evidence}/settings-long-error.png`});
  await dialog.getByRole('checkbox',{name:/Unavailable indexer 999/}).click();
  await expect(dialog.getByRole('checkbox',{name:/Unavailable indexer 999/})).toHaveCount(0);
  await dialog.getByRole('checkbox',{name:'LimeTorrents',exact:true}).uncheck();
  await expect(dialog).toContainText('No trusted indexers selected.');
  await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
  dialog = await openSelector(page, 'TV');
  await expect(dialog.getByRole('checkbox',{name:/Unavailable indexer 999/})).toBeChecked();
  await page.keyboard.press('Escape');
});

test('multiple-season review reuses approved-home choice and refreshes every season destination', async ({page, request}) => {
  const fixture = await (await request.post('/__tv_fixture/ambiguous-home')).json();
  try {
    await page.goto('/tv/series/1');
    await page.getByRole('button',{name:'Download all seasons',exact:true}).click();
    const dialog = page.getByRole('dialog',{name:'TV release review'});
    await expect(dialog.getByRole('button',{name:/Download available|Download selected releases/})).toBeDisabled();
    await dialog.getByLabel('Approved TV show folder for season 2').selectOption(fixture.home);
    await expect(dialog.getByText(`Destination: ${fixture.destination}`,{exact:true})).toBeVisible();
    expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  } finally { await request.post('/__tv_fixture/reset-home'); }
});

test('lower checked-season and all-season review adds nothing before explicit submission and preserves destinations', async ({page, request}) => {
  const before = await (await request.get('/api/tv/acquisitions')).json();
  const tasks = await (await request.get('/api/tv/tasks?series_id=1')).json();
  await page.goto('/tv/series/1');
  await page.getByRole('button',{name:'Choose seasons…',exact:true}).click();
  const chooser = page.getByRole('dialog',{name:'Choose TV seasons'});
  await expect(chooser.getByRole('button',{name:'Review downloads'})).toBeDisabled();
  await expect(chooser).not.toContainText('Season 0');
  await chooser.getByRole('checkbox',{name:/Season 1/}).check();
  await chooser.getByRole('checkbox',{name:/Season 2/}).check();
  await expect(chooser).toContainText('missing');
  await chooser.getByRole('button',{name:'Review downloads'}).click();
  let dialog = page.getByRole('dialog',{name:'TV release review'});
  await expect(dialog.getByRole('heading',{name:'Season 1',exact:true})).toBeVisible();
  await expect(dialog.getByRole('heading',{name:'Season 2',exact:true})).toBeVisible();
  await expect(dialog).toContainText('Season 02');
  await expect(dialog.getByRole('button',{name:/Download selected releases|Download available/})).toBeEnabled();
  await page.screenshot({path:`${evidence}/multi-season.png`});
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Download all seasons',exact:true}).click();
  dialog = page.getByRole('dialog',{name:'TV release review'});
  await expect(dialog.getByRole('heading',{name:'Season 2',exact:true})).toBeVisible();
  expect((await (await request.get('/api/tv/acquisitions')).json()).items.length).toBe(before.items.length);
  expect((await (await request.get('/api/tv/tasks?series_id=1')).json()).items.length).toBe(tasks.items.length);
  const response = page.waitForResponse(r => r.url().endsWith('/api/tv/acquisitions/batch') && r.request().method() === 'POST');
  await dialog.getByRole('button',{name:'Download selected releases',exact:true}).click();
  const batch = await (await response).json();
  expect(batch.complete).toBe(true);
  expect(batch.items).toHaveLength(2);
  try {
    const acquisitions = (await (await request.get('/api/tv/acquisitions')).json()).items.filter(item => batch.items.some(member => member.intent_id === item.id));
    expect(acquisitions.map(item=>item.job.destination).sort()).toEqual([
      expect.stringMatching(/Harbor Signals[\\/]Season 01$/), expect.stringMatching(/Harbor Signals[\\/]Season 02$/)]);
    expect((await (await request.get('/api/tv/tasks?series_id=1')).json()).items.length).toBe(tasks.items.length);
  } finally {
    for (const item of batch.items) await request.post(`/api/tv/acquisitions/${item.intent_id}/action`,{data:{action:'cancel'}});
  }
});

test('empty TV trust preserves blocked draft and explicit Start failure is visible', async ({page, request}) => {
  await config(request,{tv_download_trusted_indexers:[]});
  try {
    await page.goto('/tv/series/1');
    await page.getByRole('button',{name:'Preview targets',exact:true}).click();
    await expect(page.getByRole('alert')).toContainText('Select TV trusted indexers in Settings');
    await page.getByRole('button',{name:'Save draft',exact:true}).click();
    const task = page.locator('.tv-follow-task').first();
    await expect(task).toContainText('draft');
    await task.getByRole('button',{name:'Start',exact:true}).click();
    await expect(page.getByRole('alert').last()).toContainText('Select TV trusted indexers in Settings');
    await expect(task).toContainText('draft');
    await page.screenshot({path:`${evidence}/blocked-draft.png`});
    const taskData = (await (await request.get('/api/tv/tasks?series_id=1')).json()).items.find(item => item.state === 'draft');
    const preview = await (await request.get(`/api/tv/tasks/${taskData.id}/cancel/preview`)).json();
    await request.post(`/api/tv/tasks/${taskData.id}/cancel`,{data:{mode:'keep',token:preview.token}});
  } finally { await config(request,{tv_download_trusted_indexers:['7','9']}); }
});

test('task polling renders backend counts, errors and Cairo times without stale navigation', async ({page}) => {
  let reads = 0;
  await page.route('**/api/tv/tasks?series_id=1', route => {
    reads++;
    return route.fulfill({json:{items:[{id:'poll-fixture',scope:'series',action:'missing',state:'running',profile_id:'safe-hd',selected_episodes:[],
      counts:{queued:reads > 1 ? 1 : 0, waiting:reads > 1 ? 1 : 2, review:1},last_search:1791406800,next_eligible_search:1791424800,
      episodes:[{episode_id:10,code:'S01E01',state:reads > 1 ? 'queued' : 'waiting_release',error:''},
        {episode_id:11,code:'S01E02',state:'retry',error:'8 releases found; none passed automatic validation',next_retry:1791424800},
        {episode_id:12,code:'S01E03',state:'needs_review',error:'Episode identity requires review'}],error:''}], total:1}});
  });
  await page.goto('/tv/series/1');
  await expect(page.locator('.tv-follow-task')).toContainText('8 releases found');
  await expect(page.locator('.tv-follow-task')).toContainText('Africa/Cairo');
  await expect(page.locator('.tv-follow-task')).toContainText('1 queued',{timeout:20000});
  await expect(page.locator('.tv-follow-task')).toContainText('0 / 3 acquired');
  await page.locator('.tv-follow-task').scrollIntoViewIfNeeded();
  await page.screenshot({path:`${evidence}/task-progress.png`});
  await page.goto('/discover');
  await page.goBack();
  await expect(page.getByRole('region',{name:'Harbor Signals series page'})).toBeVisible();
  await page.goForward();
  await expect(page.locator('.tv-follow-task')).toHaveCount(0);
});
