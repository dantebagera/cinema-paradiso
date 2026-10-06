const { chromium, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const evidence = path.join(process.cwd(), 'docs/verification/tv-numeric-repair');
  const manifest = JSON.parse(fs.readFileSync(path.join(evidence, 'manifest.json'), 'utf8'));
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
    // This is a read-only live inspection: block startup writes and all actions.
    await page.route('**/api/**', route => {
      const request = route.request();
      if (request.method() === 'POST' && !['/api/tv/catalog/search', '/api/library/search/advanced'].includes(new URL(request.url()).pathname)) {
        return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
      }
      return route.continue();
    });
    const results = [];
    for (const folder of manifest.folders) {
      const moves = manifest.moves.filter(move => move.series_id === folder.series_id);
      await page.goto(`http://127.0.0.1:5000/tv/series/${folder.series_id}`);
      await expect(page.getByRole('heading', { name: folder.title, exact: true })).toBeVisible({ timeout: 20000 });
      const season = moves[0].bindings[0].season_number;
      await page.getByLabel('TV season').selectOption(String(season));
      for (let i = 0; i < moves.length; i++) {
        const move = moves[i];
        const binding = move.bindings[0];
        const code = `S${String(binding.season_number).padStart(2, '0')}E${String(binding.episode_number).padStart(2, '0')}`;
        const row = page.getByRole('article', { name: new RegExp(`^${code} `) });
        await row.getByRole('button', { name: /^Versions \(/ }).click();
        const dialog = page.getByRole('dialog', { name: `${code} versions`, exact: true });
        await expect(dialog.locator('code')).toContainText(move.target);
        if (i === 0) await page.screenshot({ path: path.join(evidence, `live-series-${folder.series_id}.png`) });
        await dialog.getByRole('button', { name: 'Close', exact: true }).click();
        results.push({ show: folder.title, episode: code, path: move.target });
      }
    }
    fs.writeFileSync(path.join(evidence, 'live-desktop-verification.json'), JSON.stringify({ state: 'live_desktop_verified', viewport: '1600x1000', files: results }, null, 2));
    console.log(`Verified ${results.length} corrected episode paths in rendered desktop Versions dialogs.`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
