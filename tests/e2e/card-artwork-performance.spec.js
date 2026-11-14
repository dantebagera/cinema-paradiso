import { expect, test } from '@playwright/test';

test.use({ viewport: { width: 1600, height: 1000 }, reducedMotion: 'reduce' });

const image = '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300"><rect width="600" height="300" fill="#263038"/></svg>';
const movies = (prefix, count = 40) => Array.from({ length: count }, (_, index) => ({
  tmdb_id: `${prefix === 'library' ? 9200 : prefix === 'trending' ? 9300 : 9400}${index}`,
  title: `${prefix} artwork ${index + 1}`, year: '2027', release_date: '2027-12-01',
  genres: ['Drama'], tmdb_rating: '7.8', summary: 'Artwork request fixture.',
  poster_url: `data:image/svg+xml,${encodeURIComponent(image)}`,
  backdrop_url: `https://artwork.example.test/${prefix}-${index + 1}.svg`,
  cast: [], directors: [], recommendations: [], similar: [],
}));
const library = movies('library');
const trending = movies('trending', 20);
const upcoming = movies('upcoming', 20);
const files = library.map(movie => ({ ...movie, path: `C:/fixture/${movie.tmdb_id}.mkv`, metadata_accepted: true, canonical_metadata: { ...movie, accepted: true } }));

async function fixtures(page) {
  const requests = new Set();
  await page.route('https://artwork.example.test/**', route => {
    requests.add(new URL(route.request().url()).pathname);
    return route.fulfill({ contentType: 'image/svg+xml', body: image });
  });
  await page.route('**/api/tv/capabilities', route => route.fulfill({ json: { enabled: false } }));
  await page.route('**/api/user/lists**', route => route.fulfill({ json: { lists: [], curation_generation: 1 } }));
  await page.route('**/api/user/followed-releases**', route => route.fulfill({ json: { movies: [], curation_generation: 1 } }));
  await page.route('**/api/library/check', route => route.fulfill({ json: { results: [], catalog_generation: 1 } }));
  await page.route('**/api/tmdb/card-projections', route => route.fulfill({ json: { items: {}, catalog_generation: 1 } }));
  await page.route('**/api/library/search/advanced', route => route.fulfill({ json: {
    items: files, total: files.length, page: 1, total_pages: 1, page_start: 0, page_end: files.length,
    catalog_generation: 1, facets: { genres: [], countries: [], languages: [], sources: [] },
    stats: { total: files.length, matched: files.length, pending: 0, unmatched: 0, low: 0 },
  } }));
  await page.route('**/api/library/details**', route => route.fulfill({ json: { item: files[39], catalog_generation: 1 } }));
  await page.route('**/api/tmdb/details**', route => {
    const id = new URL(route.request().url()).searchParams.get('tmdb_id');
    return route.fulfill({ json: [...library, ...trending, ...upcoming].find(movie => movie.tmdb_id === id) || library[0] });
  });
  await page.route('**/api/tmdb/discover**', route => {
    const results = new URL(route.request().url()).searchParams.get('list') === 'upcoming' ? upcoming : trending;
    return route.fulfill({ json: { results, page: 1, total_pages: 1, total_results: results.length } });
  });
  await page.route('**/api/player/continue-watching**', route => route.fulfill({ json: { items: trending.map((movie, index) => ({
    ...movie, title: `continue artwork ${index + 1}`, backdrop_url: `https://artwork.example.test/continue-${index + 1}.svg`,
    path_key: `fixture-${index}`, movie_key: `tmdb:${movie.tmdb_id}`, position_ms: 300000, duration_ms: 600000, progress: 0.5, remaining_seconds: 300,
  })) } }));
  await page.route('**/api/tv/continue-watching**', route => route.fulfill({ json: { items: [] } }));
  return requests;
}

for (const surface of ['Discover Movie', 'Discover TV', 'Movie Library']) {
  test(`${surface} backdrops wait for every visible poster and recover from an image error`, async ({ page }) => {
    await fixtures(page);
    const isLibrary = surface === 'Movie Library';
    const isTV = surface === 'Discover TV';
    await page.route('**/api/tv/capabilities', route => route.fulfill({ json: { enabled: true } }));
    const rows = ['first', 'second', 'missing'].map((name, index) => ({
      tmdb_id: 98001 + index,
      title: `Priority artwork ${name}`,
      year: '2027',
      first_air_date: '2027-01-01',
      season_count: 1,
      status: 'Ended',
      genres: [],
      poster_url: name === 'missing' ? '' : `https://priority.example.test/${name}-poster.svg`,
      backdrop_url: `https://priority.example.test/${name}-backdrop.svg`
    }));
    await page.route('**/api/tmdb/discover/advanced', route => route.fulfill({ json: {
      results: isTV ? [] : rows, page: 1, total_pages: 1, total_results: rows.length
    } }));
    await page.route('**/api/tv/catalog/search', route => route.fulfill({ json: {
      items: rows, page: 1, total_pages: 1, total: rows.length, complete: true
    } }));
    if (isLibrary) {
      const items = rows.map((row, index) => ({ ...row, path: files[index].path, metadata_accepted: true,
        canonical_metadata: { ...row, accepted: true } }));
      await page.route('**/api/library/search/advanced', route => route.fulfill({ json: {
        items, total: items.length, page: 1, total_pages: 1, page_start: 0, page_end: items.length,
        catalog_generation: 1, facets: { genres: [], countries: [], languages: [], sources: [] }
      } }));
    }
    const first = Promise.withResolvers();
    const second = Promise.withResolvers();
    const requested = new Set();
    await page.route('https://priority.example.test/**', async route => {
      const file = new URL(route.request().url()).pathname;
      requested.add(file);
      if (file === '/first-poster.svg') await first.promise;
      if (file === '/second-poster.svg') {
        await second.promise;
        return route.fulfill({ status: 404 });
      }
      await route.fulfill({ contentType: 'image/svg+xml', body: image });
    });
    try {
      await page.goto(isLibrary ? '/library' : '/discover');
      if (isTV) {
        await page.getByRole('tablist', { name: 'Discover tools' }).getByRole('button', { name: 'TV Shows', exact: true }).click();
      }
      const cards = page.locator(isLibrary ? '.library-results .unified-movie-card'
        : isTV ? '.tv-discover-workspace .tv-series-card' : '.discover-movie-card');
      await expect(cards).toHaveCount(3);
      await expect.poll(() => [...requested].filter(file => file.endsWith('-poster.svg')).sort()).toEqual([
        '/first-poster.svg', '/second-poster.svg'
      ]);
      await expect(cards.first()).not.toHaveCSS('background-image', /first-backdrop/);
      first.resolve();
      await expect.poll(() => cards.first().locator('img').evaluate(img => img.naturalWidth)).toBeGreaterThan(0);
      await expect(cards.first()).not.toHaveCSS('background-image', /first-backdrop/);
      expect([...requested].filter(file => file.endsWith('-backdrop.svg'))).toEqual([]);
      second.resolve();
      await expect(cards.nth(1).locator('.unified-movie-poster svg.lucide-film')).toBeVisible();
      await expect.poll(() => [...requested].filter(file => file.endsWith('-backdrop.svg')).sort()).toEqual([
        '/first-backdrop.svg', '/missing-backdrop.svg', '/second-backdrop.svg'
      ]);
      await expect(cards.first()).toHaveCSS('background-image', /linear-gradient.*first-backdrop/);
      await expect(cards.nth(2)).toHaveCSS('background-image', /linear-gradient.*missing-backdrop/);
    } finally {
      first.resolve();
      second.resolve();
    }
  });
}

test('Discover backdrops can load while a nearby offscreen poster is still pending', async ({ page }) => {
  await fixtures(page);
  const rows = movies('trending', 18).map((row, index) => ({
    ...row,
    poster_url: `https://priority.example.test/poster-${index}.svg`,
    backdrop_url: `https://priority.example.test/backdrop-${index}.svg`
  }));
  await page.route('**/api/tmdb/discover/advanced', route => route.fulfill({ json: {
    results: rows, page: 1, total_pages: 1, total_results: rows.length
  } }));
  const selectHeldPoster = Promise.withResolvers();
  const releaseHeldPoster = Promise.withResolvers();
  const requested = new Set();
  await page.route('https://priority.example.test/**', async route => {
    const file = new URL(route.request().url()).pathname;
    requested.add(file);
    if (file.startsWith('/poster-') && file === await selectHeldPoster.promise) await releaseHeldPoster.promise;
    await route.fulfill({ contentType: 'image/svg+xml', body: image });
  });
  try {
    await page.goto('/discover');
    const cards = page.locator('.discover-movie-card');
    await expect(cards).toHaveCount(rows.length);
    const nearby = await cards.evaluateAll(elements => {
      const posters = elements.map(element => element.querySelector('.unified-movie-poster'));
      const firstBelow = posters.findIndex(poster => poster.getBoundingClientRect().top > innerHeight + 110);
      if (firstBelow < 0) return -1;
      const workspace = elements[0].closest('main.workspace');
      workspace.style.scrollBehavior = 'auto';
      workspace.scrollTop += Math.max(0, posters[firstBelow].getBoundingClientRect().top - innerHeight - 100);
      return firstBelow;
    });
    expect(nearby).toBeGreaterThan(0);
    await expect.poll(() => [...requested].filter(file => file.startsWith('/poster-')).length).toBeGreaterThan(0);
    expect([...requested].filter(file => file.startsWith('/backdrop-'))).toEqual([]);
    const held = cards.nth(nearby);
    const poster = held.locator('img');
    // Start the real image request, then move it offscreen before releasing the others.
    await held.scrollIntoViewIfNeeded();
    const heldPath = `/poster-${nearby}.svg`;
    await expect.poll(() => requested.has(heldPath)).toBe(true);
    await poster.evaluate(img => {
      const workspace = img.closest('main.workspace');
      workspace.scrollTop += img.getBoundingClientRect().top - innerHeight - 100;
    });
    const posterBox = await poster.boundingBox();
    const viewportHeight = page.viewportSize().height;
    expect(posterBox.y).toBeGreaterThan(viewportHeight);
    expect(posterBox.y).toBeLessThan(viewportHeight + 200);
    selectHeldPoster.resolve(heldPath);
    await expect.poll(() => [...requested].some(file => file.startsWith('/backdrop-'))).toBe(true);
    expect(await poster.evaluate(img => img.complete)).toBe(false);
    releaseHeldPoster.resolve();
    await held.scrollIntoViewIfNeeded();
    await expect.poll(() => poster.evaluate(img => img.naturalWidth)).toBeGreaterThan(0);
  } finally {
    selectHeldPoster.resolve('');
    releaseHeldPoster.resolve();
  }
});

test('Library defers offscreen backdrops while preserving visible artwork and scroll loading', async ({ page }) => {
  const requests = await fixtures(page);
  await page.goto('/library');
  const cards = page.locator('.library-results .unified-movie-card');
  await expect(cards).toHaveCount(40);
  await expect.poll(() => requests.has('/library-1.svg')).toBe(true);
  const last = cards.last();
  expect((await last.boundingBox()).y).toBeGreaterThan(1000);
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  console.log(`Library initial backdrop requests: ${requests.size}/40`);
  expect(requests.has('/library-40.svg')).toBe(false);
  expect(requests.size).toBeLessThan(20);
  await expect(cards.first()).toHaveCSS('background-size', 'cover, cover');
  await expect(cards.first()).toHaveCSS('background-image', /linear-gradient.*library-1\.svg/);
  await last.scrollIntoViewIfNeeded();
  await expect.poll(() => requests.has('/library-40.svg')).toBe(true);
  await expect(last).toHaveCSS('background-image', /library-40\.svg/);
});

test('Movie Library defers distant poster requests and preserves their images on scroll',async({page})=>{
  await fixtures(page);
  const requested=new Set();
  const items=files.map((row,index)=>{
    const poster_url=`https://posters.example.test/library-${index+1}.svg`;
    return {...row,poster_url,canonical_metadata:{...row.canonical_metadata,poster_url}};
  });
  await page.route('https://posters.example.test/**',route=>{
    requested.add(Number(new URL(route.request().url()).pathname.match(/library-(\d+)/)[1]));
    return route.fulfill({contentType:'image/svg+xml',body:image});
  });
  await page.route('**/api/library/search/advanced',route=>route.fulfill({json:{
    items,total:40,page:1,total_pages:1,page_start:0,page_end:40,catalog_generation:1,
    facets:{genres:[],countries:[],languages:[],sources:[]},stats:{total:40,matched:40,pending:0,unmatched:0,low:0}}}));
  await page.goto('/library');
  const cards=page.locator('.library-results .unified-movie-card');
  await expect(cards).toHaveCount(40);
  await expect.poll(()=>cards.first().locator('img').evaluate(img=>img.naturalWidth)).toBeGreaterThan(0);
  const distantIndex=await cards.evaluateAll(elements=>elements.findIndex(element=>{
    const rect=element.getBoundingClientRect();return rect.top>innerHeight+250&&rect.top<innerHeight+1800;
  }));
  expect(distantIndex).toBeGreaterThan(0);
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  expect(requested.has(distantIndex+1)).toBe(false);
  await cards.nth(distantIndex).scrollIntoViewIfNeeded();
  await expect.poll(()=>requested.has(distantIndex+1)).toBe(true);
  await expect.poll(()=>cards.nth(distantIndex).locator('img').evaluate(img=>img.naturalWidth)).toBeGreaterThan(0);
});

test('An expanded card has its artwork immediately even before its visibility notification', async ({ page }) => {
  await fixtures(page);
  await page.goto('/library');
  const last = page.locator('.library-results .unified-movie-card').last();
  await expect(last).toBeAttached();
  await last.locator('h3').evaluate(element => element.click());
  await expect(last).toHaveClass(/unified-movie-card-expanded/);
  await expect(last.locator('.unified-movie-main')).toHaveCSS('background-image', /library-40\.svg/);
});

test('Home poster rails defer clipped and below-screen artwork then load it on navigation', async ({ page }) => {
  const requests = await fixtures(page);
  const posterRows=(rows,prefix)=>rows.map((movie,index)=>({...movie,poster_url:`https://artwork.example.test/${prefix}-poster-${index+1}.svg`}));
  await page.route('**/api/tmdb/discover**',route=>{
    const isUpcoming=new URL(route.request().url()).searchParams.get('list')==='upcoming';
    const results=posterRows(isUpcoming?upcoming:trending,isUpcoming?'upcoming':'trending');
    return route.fulfill({json:{results,page:1,total_pages:1,total_results:results.length}});
  });
  await page.route('**/api/player/continue-watching**',route=>route.fulfill({json:{items:posterRows(trending,'continue').map((movie,index)=>({
    ...movie,title:`continue artwork ${index+1}`,path_key:`fixture-${index}`,position_ms:300000,duration_ms:600000,progress:0.5,remaining_seconds:300,
  }))}}));
  await page.goto('/');
  const continuing = page.locator('.continue-watching-viewport .continue-movie-card');
  const coming = page.locator('.coming-soon-grid .upcoming-movie-card');
  const popular = page.locator('.home-trending-track .upcoming-movie-card');
  await expect(continuing).toHaveCount(20);
  await expect(coming).toHaveCount(20);
  await expect(popular).toHaveCount(20);
  await continuing.first().scrollIntoViewIfNeeded();
  await expect.poll(() => requests.has('/continue-poster-1.svg')).toBe(true);
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  console.log(`Home initial poster requests: ${requests.size}/60`);
  expect(requests.has('/continue-poster-20.svg')).toBe(false);
  expect(requests.has('/upcoming-poster-20.svg')).toBe(false);
  expect(requests.has('/trending-poster-20.svg')).toBe(false);
  await expect(continuing.first()).toHaveCSS('background-image','none');
  for (const [cards, title, url] of [[continuing, 'continue artwork 20', '/continue-poster-20.svg'], [popular, 'trending artwork 20', '/trending-poster-20.svg'], [coming, 'upcoming artwork 20', '/upcoming-poster-20.svg']]) {
    const target = cards.filter({ hasText: title });
    await target.scrollIntoViewIfNeeded();
    await expect.poll(() => requests.has(url)).toBe(true);
    await expect(target.locator('img')).toHaveAttribute('src', new RegExp(url.replace('.', '\\.')));
    await expect.poll(()=>target.locator('img').evaluate(image=>image.naturalWidth)).toBeGreaterThan(0);
  }
});

test('Home Trending keeps its background photo behind the visible poster request', async ({ page }) => {
  const requests = await fixtures(page);
  const heldPoster = Promise.withResolvers();
  const movie = { ...trending[0], poster_url: 'https://artwork.example.test/home-held-poster.svg' };
  await page.route('**/api/tmdb/discover**', route => route.fulfill({ json: {
    results: new URL(route.request().url()).searchParams.get('list') === 'upcoming' ? [] : [movie],
    page: 1, total_pages: 1, total_results: 1
  } }));
  await page.route('**/api/player/continue-watching**', route => route.fulfill({ json: { items: [] } }));
  await page.route('**/home-held-poster.svg', async route => {
    requests.add('/home-held-poster.svg');
    await heldPoster.promise;
    await route.fulfill({ contentType: 'image/svg+xml', body: image });
  });
  try {
    await page.goto('/');
    const card = page.locator('.home-trending-track button.upcoming-movie-card')
      .filter({ hasText: movie.title });
    await expect(card).toBeVisible();
    await card.scrollIntoViewIfNeeded();
    await expect.poll(() => requests.has('/home-held-poster.svg')).toBe(true);
    await expect(card).not.toHaveCSS('background-image', /trending-1\.svg/);
    expect(requests.has('/trending-1.svg')).toBe(false);
    heldPoster.resolve();
    await expect.poll(() => card.locator('img').evaluate(img => img.naturalWidth)).toBeGreaterThan(0);
    await expect.poll(() => requests.has('/trending-1.svg')).toBe(true);
    await expect(card).toHaveCSS('background-image', /trending-1\.svg/);
  } finally {
    heldPoster.resolve();
  }
});

test('Browsers without IntersectionObserver still show supplied artwork', async ({ page }) => {
  await page.addInitScript(() => { delete window.IntersectionObserver; });
  const requests = await fixtures(page);
  await page.goto('/library');
  await expect(page.locator('.library-results .unified-movie-card')).toHaveCount(40);
  await expect.poll(() => requests.has('/library-40.svg')).toBe(true);
  await expect(page.locator('.library-results .unified-movie-card').first()).toHaveCSS('background-image', /library-1\.svg/);
});

test('Related titles defer clipped artwork and preserve navigation after scrolling', async ({ page }) => {
  const requests = await fixtures(page);
  const heldPoster = Promise.withResolvers();
  const related = movies('related', 20).map((movie, index) => ({ ...movie, tmdb_id: String(9500 + index),
    poster_url: `https://artwork.example.test/related-poster-${index + 1}.svg` }));
  await page.route('**/related-poster-1.svg', async route => {
    requests.add('/related-poster-1.svg');
    await heldPoster.promise;
    await route.fulfill({ contentType: 'image/svg+xml', body: image });
  });
  await page.route('**/api/tmdb/related**', route => route.fulfill({ json: { results: related, source: 'recommendations', page: 1, total_pages: 1, total_results: 20, has_next: false } }));
  await page.route('**/api/tmdb/details**', route => route.fulfill({ json: related.find(movie => movie.tmdb_id === new URL(route.request().url()).searchParams.get('tmdb_id')) || library[0] }));
  await page.goto('/library');
  await page.locator('.library-results .unified-movie-card').first().locator('h3').click();
  const cards = page.locator('.unified-movie-card-expanded .related-tile');
  await expect(cards).toHaveCount(20);
  await cards.first().scrollIntoViewIfNeeded();
  try {
    await expect.poll(() => requests.has('/related-poster-1.svg')).toBe(true);
    await expect(cards.first()).not.toHaveCSS('background-image', /related-1\.svg/);
    expect(requests.has('/related-20.svg')).toBe(false);
    await cards.last().scrollIntoViewIfNeeded();
    await expect.poll(() => requests.has('/related-20.svg')).toBe(true);
    expect(await cards.first().locator('img').evaluate(img => img.complete)).toBe(false);
    heldPoster.resolve();
    await cards.last().click();
    await expect(page.locator('.discover-card-expanded')).toContainText('related artwork 20');
  } finally {
    heldPoster.resolve();
  }
});

for (const pendingCount of [1, 2]) {
  test(`A stale artwork notification cannot activate a replacement poster in hidden Home (${pendingCount} pending cards)`, async ({ page }) => {
    // Control observer delivery to reproduce a browser notification queued before
    // URL replacement, including reuse of an observer with other pending cards.
    await page.addInitScript(() => {
      window.artworkObservers = [];
      window.IntersectionObserver = class {
        constructor(callback, options) { this.callback = callback; this.options = options; this.targets = []; window.artworkObservers.push(this); }
        observe(target) { this.targets.push(target); }
        unobserve() {}
        disconnect() {}
      };
    });
    const requests = await fixtures(page);
    await page.route('**/api/tmdb/discover**', route => route.fulfill({ json: { results: [], page: 1, total_pages: 1, total_results: 0 } }));
    let releaseReplacement;
    let replacementStarted;
    const started = new Promise(resolve => { replacementStarted = resolve; });
    const release = new Promise(resolve => { releaseReplacement = resolve; });
    let call = 0;
    await page.route('**/api/player/continue-watching**', async route => {
      call += 1;
      if (call > 1) { replacementStarted(); await release; }
      return route.fulfill({ json: { items: trending.slice(0, pendingCount).map((movie, index) => ({
        ...movie, title: call > 1 && index === 0 ? 'Replacement artwork' : movie.title,
        poster_url: call > 1 && index === 0 ? 'https://artwork.example.test/replacement.svg' : `https://artwork.example.test/pending-poster-${index}.svg`,
        backdrop_url: '',
        path_key: `pending-${index}`, progress: 0.5, remaining_seconds: 300,
      })) } });
    });
    await page.goto('/');
    const first = page.locator('.continue-movie-card').first();
    await expect(first).toBeAttached();
    await expect.poll(() => first.locator('.unified-movie-poster').evaluate(element =>
      window.artworkObservers.some(observer => observer.options?.rootMargin && observer.targets.includes(element))
    )).toBe(true);
    // Home's approved poster design suppresses card backgrounds. Retire their
    // registrations so the one/two pending cases exercise poster cleanup/reuse.
    await page.locator('.continue-movie-card').evaluateAll(elements=>{
      const observer=window.artworkObservers.find(observer => observer.options?.rootMargin);
      observer.callback(elements.map(target=>({target,isIntersecting:true,time:performance.now()})),observer);
    });
    await first.locator('.unified-movie-poster').evaluate(element => {
      window.retiredArtworkEntry = { target: element, isIntersecting: true, time: performance.now() };
      window.retiredArtworkObserver = window.artworkObservers.find(observer => observer.options?.rootMargin);
    });
    await page.getByRole('button', { name: 'Help', exact: true }).click();
    await page.getByRole('button', { name: 'Home', exact: true }).click();
    await started;
    await page.getByRole('button', { name: 'Help', exact: true }).click();
    releaseReplacement();
    await expect(first.locator('h3')).toHaveText('Replacement artwork');
    await page.evaluate(() => window.retiredArtworkObserver.callback([window.retiredArtworkEntry], window.retiredArtworkObserver));
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    expect(requests.has('/replacement.svg')).toBe(false);
    await expect(first.locator('img')).not.toHaveAttribute('src', /replacement/);
    await page.getByRole('button', { name: 'Home', exact: true }).click();
    await first.locator('.unified-movie-poster').evaluate(element => {
      const observer = window.artworkObservers.findLast(observer => observer.options?.rootMargin && observer.targets.includes(element));
      observer.callback([{ target: element, isIntersecting: true, time: performance.now() }], observer);
    });
    await expect.poll(() => requests.has('/replacement.svg')).toBe(true);
    await expect(first.locator('img')).toHaveAttribute('src', /replacement\.svg/);
  });
}
