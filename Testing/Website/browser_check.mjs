// Headless Chrome checks for the SlicerDSpace project site (SPEC section 7.2).
//
// Run from the branch root:
//   npm ci --prefix Testing/Website
//   node Testing/Website/browser_check.mjs
//
// Serves docs/site/ with Range support (like GitHub Pages),
// opens it in Google Chrome (channel 'chrome': Playwright's Chromium lacks H.264/AAC)
// and writes screenshots to Testing/Website/out/ (git-ignored).

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const here = path.dirname(fileURLToPath(import.meta.url));
const DOCS = path.resolve(here, '..', '..', 'docs', 'site');
const OUT = path.resolve(here, 'out');
fs.mkdirSync(OUT, { recursive: true });

const coreDir = process.env.PLAYWRIGHT_CORE;
const require = createRequire(import.meta.url);
const { chromium } = coreDir ? require(path.resolve(coreDir)) : require('playwright-core');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mp4': 'video/mp4',
  '.srt': 'application/x-subrip',
  '.jpg': 'image/jpeg',
  '.png': 'image/png',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
};

// ---------------------------------------------------------------- server
function serve() {
  const server = http.createServer((req, res) => {
    let urlPath = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    if (urlPath.startsWith('/SlicerDSpace/')) urlPath = urlPath.slice('/SlicerDSpace'.length);
    if (urlPath.endsWith('/')) urlPath += 'index.html';
    const file = path.resolve(DOCS, '.' + urlPath);
    if (!file.startsWith(DOCS + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      const nf = path.join(DOCS, '404.html');
      res.writeHead(404, { 'Content-Type': MIME['.html'] });
      res.end(fs.readFileSync(nf));
      return;
    }
    const size = fs.statSync(file).size;
    const type = MIME[path.extname(file)] || 'application/octet-stream';
    const range = req.headers.range;
    const headers = { 'Content-Type': type, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-store' };
    if (range) {
      const m = /^bytes=(\d*)-(\d*)$/.exec(range);
      if (!m) { res.writeHead(416, { 'Content-Range': `bytes */${size}` }); res.end(); return; }
      let start = m[1] === '' ? size - Number(m[2]) : Number(m[1]);
      let end = m[1] === '' || m[2] === '' ? size - 1 : Math.min(Number(m[2]), size - 1);
      if (start > end || start >= size) { res.writeHead(416, { 'Content-Range': `bytes */${size}` }); res.end(); return; }
      res.writeHead(206, { ...headers, 'Content-Range': `bytes ${start}-${end}/${size}`, 'Content-Length': end - start + 1 });
      if (req.method === 'HEAD') { res.end(); return; }
      fs.createReadStream(file, { start, end }).on('error', () => res.destroy()).pipe(res);
      return;
    }
    res.writeHead(200, { ...headers, 'Content-Length': size });
    if (req.method === 'HEAD') { res.end(); return; }
    fs.createReadStream(file).on('error', () => res.destroy()).pipe(res);
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)));
}

// ---------------------------------------------------------------- reporting
const results = [];
function record(ok, name, detail = '') {
  results.push({ ok, name, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${ok ? '' : ' - ' + detail}`);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function scrollThrough(page) {
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  const vh = await page.evaluate(() => window.innerHeight);
  for (let y = 0; y < height; y += Math.floor(vh * 0.7)) {
    await page.evaluate((top) => window.scrollTo(0, top), y);
    await sleep(120);
  }
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await sleep(300);
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(200);
}

// ---------------------------------------------------------------- one viewport
async function runViewport(browser, origin, name, width, height, opts) {
  const tag = `${name}`;
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const consoleErrors = [];
  const failed = [];
  const foreign = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + e.message));
  page.on('request', (r) => {
    const u = new URL(r.url());
    if (u.origin !== origin && u.protocol !== 'data:' && u.protocol !== 'blob:' && u.protocol !== 'about:') foreign.push(r.url());
  });
  page.on('requestfailed', (r) => {
    const err = r.failure()?.errorText || '';
    // Chrome cancels and re-issues byte-range requests for video. Nothing else may fail.
    if (err.includes('ERR_ABORTED') && /\/media\/[^/?#]+\.mp4$/.test(new URL(r.url()).pathname)) return;
    failed.push(`${r.url()} (${err})`);
  });
  page.on('response', (r) => {
    if (r.status() >= 400) failed.push(`${r.url()} (HTTP ${r.status()})`);
  });

  await page.goto(origin + '/index.html', { waitUntil: 'load' });
  await page.waitForTimeout(400);

  // 2. no horizontal scroll
  const w = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
  record(w.sw <= w.iw, `${tag}: no horizontal scroll (scrollWidth ${w.sw} <= innerWidth ${w.iw})`,
    `scrollWidth ${w.sw} > innerWidth ${w.iw}`);

  if (opts.overflowOnly) {
    await scrollThrough(page);
    const w2 = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
    record(w2.sw <= w2.iw, `${tag}: no horizontal scroll after scrolling through`, `scrollWidth ${w2.sw} > ${w2.iw}`);
    const wide = await page.evaluate(() => {
      const iw = window.innerWidth;
      return [...document.querySelectorAll('body *')].filter((el) => {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) return false;
        if (el.closest('pre') || el.closest('.sr-only') || el.closest('.table-wrap') || el.closest('.perf-table-wrap')) return false;
        return r.right > iw + 0.5 || r.left < -0.5;
      }).slice(0, 5).map((el) => el.tagName.toLowerCase() + '.' + el.className);
    });
    record(wide.length === 0, `${tag}: no element sticks out of the viewport`, wide.join(', '));
    await page.screenshot({ path: path.join(OUT, `site-${width}.png`), fullPage: true });
    record(consoleErrors.length === 0 && failed.length === 0 && foreign.length === 0,
      `${tag}: no console error, failed request or foreign host`,
      JSON.stringify({ consoleErrors, failed, foreign }));
    await context.close();
    return;
  }

  // 3. images
  await scrollThrough(page);
  await page.waitForFunction(() => [...document.images].every((i) => i.complete), null, { timeout: 15000 }).catch(() => {});
  const imgs = await page.evaluate(() => [...document.images].map((i) => ({
    src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0,
  })));
  const bad = imgs.filter((i) => !i.ok).map((i) => i.src);
  record(bad.length === 0, `${tag}: all ${imgs.length} images loaded`, 'not loaded: ' + bad.join(', '));

  const wmql = await page.locator('.tile-wmql img').evaluate((img) => {
    const box = img.getBoundingClientRect();
    return { src: img.getAttribute('src'), width: img.naturalWidth, height: img.naturalHeight,
      fit: getComputedStyle(img).objectFit, ratio: box.width / box.height };
  });
  record(wmql.src === 'assets/img/res-wmql-ukf.jpg' && wmql.width === 1852 && wmql.height === 1000
      && wmql.fit === 'contain' && Math.abs(wmql.ratio - 4 / 3) < .01,
    `${tag}: current WMQL render fits the tile without cropping`, JSON.stringify(wmql));
  await page.locator('.tile-wmql').screenshot({ path: path.join(OUT, `wmql-${width}.png`) });

  const w2 = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
  record(w2.sw <= w2.iw, `${tag}: no horizontal scroll after scrolling through`, `scrollWidth ${w2.sw} > ${w2.iw}`);

  // Header fits and the right nav mode is on.
  const hdr = await page.evaluate(() => {
    const inner = document.querySelector('.header-inner');
    const btn = document.getElementById('menu-btn');
    const nav = document.getElementById('site-nav');
    const vis = (el) => { const s = getComputedStyle(el); return s.display !== 'none' && s.visibility !== 'hidden'; };
    return { fits: inner.scrollWidth <= inner.clientWidth, menuVisible: vis(btn), navVisible: vis(nav) };
  });
  const narrow = width <= 1023;
  record(hdr.fits, `${tag}: header content fits`, 'header-inner overflows');
  record(hdr.menuVisible === narrow, `${tag}: menu button ${narrow ? 'shown' : 'hidden'}`, JSON.stringify(hdr));
  if (!narrow) record(hdr.navVisible, `${tag}: nav links visible`, JSON.stringify(hdr));

  // 4. video
  await page.waitForFunction(() => document.getElementById('film-video').readyState >= 1, null, { timeout: 15000 }).catch(() => {});
  const vid = await page.evaluate(() => {
    const v = document.getElementById('film-video');
    return {
      readyState: v.readyState, duration: v.duration, videoWidth: v.videoWidth,
      can: v.canPlayType('video/mp4; codecs="avc1.640032, mp4a.40.2"'),
    };
  });
  record(vid.readyState >= 1 && Math.abs(vid.duration - 72.0) <= 0.05 && vid.videoWidth === 1920,
    `${tag}: video metadata (readyState ${vid.readyState}, duration ${vid.duration?.toFixed?.(3)}, width ${vid.videoWidth})`,
    JSON.stringify(vid));
  record(vid.can !== '', `${tag}: canPlayType for avc1.640032 + mp4a.40.2 is "${vid.can}"`, 'empty');

  // The play button replaces the native controls at start.
  const pre = await page.evaluate(() => {
    const v = document.getElementById('film-video');
    const b = document.querySelector('.film-play');
    return { controls: v.hasAttribute('controls'), btn: !!b && !b.hidden, label: b ? b.textContent.trim() : '' };
  });
  record(!pre.controls && pre.btn && pre.label === 'Play film · 1:12',
    `${tag}: play button shown, controls removed (label "${pre.label}")`, JSON.stringify(pre));

  // 6. menu with the keyboard (narrow only)
  if (narrow) {
    await page.evaluate(() => window.scrollTo(0, 0));
    const btn = page.locator('#menu-btn');
    await btn.focus();
    await page.keyboard.press('Enter');
    await page.waitForTimeout(150);
    let s = await page.evaluate(() => ({
      exp: document.getElementById('menu-btn').getAttribute('aria-expanded'),
      shown: getComputedStyle(document.getElementById('site-nav')).display !== 'none',
    }));
    record(s.exp === 'true' && s.shown, `${tag}: Enter opens the menu`, JSON.stringify(s));
    await page.screenshot({ path: path.join(OUT, `menu-open-${width}.png`) });
    await page.keyboard.press('Escape');
    await page.waitForTimeout(150);
    s = await page.evaluate(() => ({
      exp: document.getElementById('menu-btn').getAttribute('aria-expanded'),
      shown: getComputedStyle(document.getElementById('site-nav')).display !== 'none',
      focusOnBtn: document.activeElement && document.activeElement.id === 'menu-btn',
    }));
    record(s.exp === 'false' && !s.shown && s.focusOnBtn, `${tag}: Escape closes the menu and returns focus`, JSON.stringify(s));
    await page.keyboard.press('Space');
    await page.waitForTimeout(150);
    s = await page.evaluate(() => document.getElementById('menu-btn').getAttribute('aria-expanded'));
    await page.keyboard.press('Space');
    await page.waitForTimeout(150);
    const s2 = await page.evaluate(() => document.getElementById('menu-btn').getAttribute('aria-expanded'));
    record(s === 'true' && s2 === 'false', `${tag}: Space opens and closes the menu`, `${s} then ${s2}`);
    // A link click closes the menu and moves to the section.
    await page.keyboard.press('Enter');
    await page.waitForTimeout(150);
    await page.locator('#site-nav a[href="#integrated"]').click();
    // Smooth scrolling over a long page takes a while: wait until the position is stable.
    let last = -1;
    for (let i = 0; i < 40; i++) {
      await page.waitForTimeout(150);
      const y = await page.evaluate(() => Math.round(window.scrollY));
      if (y === last) break;
      last = y;
    }
    s = await page.evaluate(() => ({
      exp: document.getElementById('menu-btn').getAttribute('aria-expanded'),
      top: Math.round(document.getElementById('integrated').getBoundingClientRect().top),
    }));
    record(s.exp === 'false' && s.top >= 0 && s.top < 200, `${tag}: link click closes the menu and lands on #integrated (top ${s.top})`, JSON.stringify(s));
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);
  }

  // 7. screenshots (before playback, page fully revealed)
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(OUT, `site-${width}.png`), fullPage: true });
  await page.screenshot({ path: path.join(OUT, `fold-${width}.png`) });

  // 5. play button starts playback
  await page.locator('#film').scrollIntoViewIfNeeded();
  await page.evaluate(() => { document.getElementById('film-video').muted = true; });
  await page.locator('.film-play').click();
  const t0 = await page.evaluate(() => document.getElementById('film-video').currentTime);
  let advanced = false;
  let t1 = t0;
  for (let i = 0; i < 30 && !advanced; i++) {
    await sleep(100);
    t1 = await page.evaluate(() => document.getElementById('film-video').currentTime);
    advanced = t1 > t0 + 0.2;
  }
  const post = await page.evaluate(() => {
    const v = document.getElementById('film-video');
    const b = document.querySelector('.film-play');
    return { controls: v.hasAttribute('controls'), btnHidden: b.hidden, paused: v.paused };
  });
  record(advanced && !post.paused, `${tag}: click on the play button starts playback (currentTime ${t0.toFixed(2)} -> ${t1.toFixed(2)})`, JSON.stringify({ t0, t1, ...post }));
  record(post.controls && post.btnHidden, `${tag}: controls shown and play button hidden after start`, JSON.stringify(post));
  await page.screenshot({ path: path.join(OUT, `playing-${width}.png`) });

  // Ended state: jump near the end and wait for the button to return.
  await page.evaluate(() => { const v = document.getElementById('film-video'); v.currentTime = Math.max(0, v.duration - 0.6); });
  await page.waitForFunction(() => !document.querySelector('.film-play').hidden, null, { timeout: 8000 }).catch(() => {});
  const ended = await page.evaluate(() => {
    const b = document.querySelector('.film-play');
    return { hidden: b.hidden, label: b.textContent.trim(), controls: document.getElementById('film-video').hasAttribute('controls') };
  });
  record(!ended.hidden && ended.label === 'Play again' && !ended.controls, `${tag}: on ended the button returns as "${ended.label}"`, JSON.stringify(ended));

  // Hero button: scrolls to the film and plays.
  await page.evaluate(() => { const v = document.getElementById('film-video'); v.currentTime = 0; v.pause(); window.scrollTo(0, 0); });
  await page.waitForTimeout(300);
  await page.locator('[data-play-film]').click();
  await page.waitForTimeout(1500);
  const hero = await page.evaluate(() => {
    const v = document.getElementById('film-video');
    return { paused: v.paused, t: v.currentTime, top: Math.round(document.getElementById('film').getBoundingClientRect().top) };
  });
  record(!hero.paused && hero.t > 0.2 && hero.top >= -5 && hero.top < 250, `${tag}: "Watch the film" scrolls to #film and plays (top ${hero.top}, t ${hero.t.toFixed(2)})`, JSON.stringify(hero));

  // Other things worth a look: transcript, copy buttons, reduced motion is not tested here.
  await page.evaluate(() => { document.getElementById('film-video').pause(); });
  const tr = await page.evaluate(() => {
    const d = document.getElementById('transcript');
    d.open = true;
    return d.querySelectorAll('li').length;
  });
  record(tr === 13, `${tag}: transcript has ${tr} lines`, String(tr));

  record(consoleErrors.length === 0 && failed.length === 0 && foreign.length === 0,
    `${tag}: no console error, failed request or foreign host`,
    JSON.stringify({ consoleErrors, failed, foreign }));

  await context.close();
}

// ---------------------------------------------------------------- 404 and no-JS
async function run404AndNoJs(browser, origin) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, javaScriptEnabled: false });
  const page = await context.newPage();
  const failed = [];
  page.on('requestfailed', (r) => failed.push(r.url()));
  await page.goto(origin + '/index.html', { waitUntil: 'load' });
  const nojs = await page.evaluate(() => {
    const v = document.getElementById('film-video');
    const hidden = [...document.querySelectorAll('.reveal')].filter((e) => getComputedStyle(e).opacity !== '1').length;
    return { controls: v.hasAttribute('controls'), hidden, copyShown: [...document.querySelectorAll('.copy')].some((b) => getComputedStyle(b).display !== 'none') };
  }).catch((e) => ({ error: String(e) }));
  record(nojs.controls === true && nojs.hidden === 0 && nojs.copyShown === false,
    'no-JS: native controls stay, all sections visible, no dead Copy buttons', JSON.stringify(nojs));
  await page.screenshot({ path: path.join(OUT, 'nojs-1440.png') });
  await context.close();

  const c2 = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const p2 = await c2.newPage();
  const errs = [];
  p2.on('console', (m) => { if (m.type() === 'error' && !/404/.test(m.text())) errs.push(m.text()); });
  const resp = await p2.goto(origin + '/404.html', { waitUntil: 'load' });
  await p2.waitForTimeout(300);
  const sw = await p2.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  record(sw && errs.length === 0, '404 page renders without overflow or console errors', JSON.stringify({ sw, errs }));
  await p2.screenshot({ path: path.join(OUT, '404-390.png') });
  await c2.close();
}

// The performance evidence is a closed <details> on the home page (index.html#performance).
async function runPerformance(browser, origin, width, noJs = false) {
  const context = await browser.newContext({ viewport: { width, height: 900 }, javaScriptEnabled: !noJs });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('requestfailed', (request) => {
    // Chrome cancels and re-issues byte-range requests for video. Nothing else may fail.
    if ((request.failure()?.errorText || '').includes('ERR_ABORTED') && /\/media\/[^/?#]+\.mp4$/.test(new URL(request.url()).pathname)) return;
    errors.push(request.url());
  });
  page.on('request', (request) => { const u = new URL(request.url()); if (u.origin !== origin && u.protocol !== 'data:' && u.protocol !== 'blob:' && u.protocol !== 'about:') errors.push('External request: ' + request.url()); });
  page.on('response', (response) => { if (response.status() >= 400) errors.push('HTTP ' + response.status() + ': ' + response.url()); });
  await page.goto(origin + '/SlicerDSpace/index.html', { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  const prefix = `performance ${width}px${noJs ? ' no JS' : ''}`;
  const evidence = page.locator('#performance-evidence');
  record(await evidence.count() === 1 && await evidence.getAttribute('open') === null, prefix + ': evidence details closed by default');
  record(await page.locator('#performance-evidence .perf-table').isHidden(), prefix + ': table hidden while closed');
  await page.locator('#performance-evidence > summary').click();
  await page.waitForFunction(() => document.getElementById('performance-evidence').open);
  record(await page.locator('#performance-evidence .perf-table').isVisible(), prefix + ': click opens the evidence and shows the table');
  record(await page.locator('.perf-table tbody tr').count() === 13, prefix + ': thirteen scoped records');
  record(await page.locator('.perf-method[open]').count() === 0, prefix + ': method details initially collapsed');
  record(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), prefix + ': no page overflow with the evidence open');
  if (!noJs) {
    await page.locator('[data-perf-filter="parallel,workflow"]').click();
    record(await page.locator('.perf-table tbody tr:not([hidden])').count() === 2, prefix + ': thread/schedule filter');
    await page.locator('[data-perf-filter="port"]').click();
    record(await page.locator('.perf-table tbody tr:not([hidden])').count() === 1, prefix + ': port filter');
    await page.locator('[data-perf-filter="integration"]').click();
    record(await page.locator('.perf-table tbody tr:not([hidden])').count() === 1 && await page.locator('.perf-table a[href="#method-dki"]').isVisible(), prefix + ': existing upstream capability is separate');
    await page.locator('[data-perf-filter="all"]').click();
    await page.locator('.perf-table a[href="#method-freewater"]').click();
    await page.waitForFunction(() => document.getElementById('method-freewater').open);
    record(await page.locator('#method-freewater').getAttribute('open') !== null, prefix + ': measurement link opens method');
    // The hashchange handler of performance.js runs after the click. Let it finish before the key press,
    // or it can reopen the method that the key press just closed.
    await page.waitForFunction(() => location.hash === '#method-freewater');
    await page.waitForTimeout(200);
    await page.locator('#method-freewater summary').focus();
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => !document.getElementById('method-freewater').open);
    record(await page.locator('#method-freewater').getAttribute('open') === null, prefix + ': keyboard collapse');
    await page.locator('.perf-table a[href="#method-freewater"]').click();
    await page.waitForFunction(() => document.getElementById('method-freewater').open);
    record(await page.locator('#method-freewater').getAttribute('open') !== null, prefix + ': same-fragment link reopens method');
    const response = await context.request.get(origin + '/SlicerDSpace/assets/data/performance.json');
    const data = await response.json();
    record(response.ok() && data.records.length === 13 && !JSON.stringify(data).includes('/data/chengjin/'), prefix + ': sanitized evidence download');
    // The hash opens the evidence; the footer link reopens it after it was closed.
    await page.goto(origin + '/SlicerDSpace/index.html#performance', { waitUntil: 'load' });
    await page.waitForFunction(() => document.getElementById('performance-evidence').open);
    record(await page.locator('#performance-evidence .perf-table').isVisible(), prefix + ': #performance opens the evidence');
    await page.evaluate(() => { document.getElementById('performance-evidence').open = false; });
    await page.locator('footer a[href="#performance"]').click();
    await page.waitForFunction(() => document.getElementById('performance-evidence').open);
    record(await page.locator('#performance-evidence .perf-table').isVisible(), prefix + ': footer link reopens the evidence');
  } else {
    record(await page.locator('.perf-filters').isHidden(), prefix + ': no nonfunctional filter controls');
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(OUT, `performance-${width}${noJs ? '-nojs' : ''}.png`), fullPage: true });
  record(errors.length === 0, prefix + ': no errors or foreign requests', errors.join('; '));
  await context.close();
}

// The complete bibliography is always expanded at the end of the main page.
// Test table-to-reference navigation on desktop, mobile and without JavaScript.
async function runReferenceLinks(browser, origin) {
  for (const width of [1440, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    await page.goto(origin + '/index.html', { waitUntil: 'load' });
    const expanded = await page.evaluate(() => {
      const d = document.getElementById('reference-list');
      return !!d && !d.closest('details') && !!d.querySelector('#ref-1') && !!d.querySelector('#ref-53')
        && d.querySelectorAll('.ref-list > li').length === 53
        && document.querySelector('main > section:last-of-type').id === 'cite';
    });
    record(expanded, `references ${width}px: list [1] to [53] is expanded at the page end`, String(expanded));
    const link = page.locator('.int-table a[href="#ref-21"]').first();
    await link.scrollIntoViewIfNeeded();
    await link.click();
    // Smooth scrolling takes a while: wait until the position is stable.
    let s = null;
    let last = null;
    for (let i = 0; i < 60; i++) {
      await page.waitForTimeout(150);
      s = await page.evaluate(() => {
        const r = document.getElementById('ref-21').getBoundingClientRect();
        return { expanded: !document.getElementById('reference-list').closest('details'), top: Math.round(r.top), h: r.height, ih: innerHeight };
      });
      if (last !== null && s.top === last) break;
      last = s.top;
    }
    record(s.expanded && s.h > 0 && s.top >= 0 && s.top < s.ih / 2,
      `references ${width}px: a click on [21] in the table shows the matching entry (top ${s.top})`, JSON.stringify(s));
    await context.close();
  }
  const c2 = await browser.newContext({ viewport: { width: 1440, height: 900 }, javaScriptEnabled: false });
  const p2 = await c2.newPage();
  await p2.goto(origin + '/index.html#ref-21', { waitUntil: 'load' });
  // Poll from Node: requestAnimationFrame-based polling is unavailable when
  // page JavaScript is disabled. Allow native smooth scrolling to settle.
  let nojs;
  for (let i = 0; i < 60; i++) {
    await p2.waitForTimeout(150);
    nojs = await p2.evaluate(() => {
      const entry = document.getElementById('ref-21');
      const r = entry.getBoundingClientRect();
      return { expanded: !entry.closest('details'), top: r.top, bottom: r.bottom, h: r.height, ih: innerHeight };
    });
    if (nojs.top >= 0 && nojs.bottom < nojs.ih) break;
  }
  record(nojs.expanded && nojs.h > 0 && nojs.top >= 0 && nojs.bottom < nojs.ih,
    'references no-JS: index.html#ref-21 shows the visible bibliography entry', JSON.stringify(nojs));
  await c2.close();
}

// Run times, optimization figures and detailed evidence all stay on the home page.
async function runHomePerformanceNavigation(browser, origin) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.goto(origin + '/SlicerDSpace/index.html#runtime', { waitUntil: 'load' });
  const images = page.locator('#runtime img');
  record(await images.count() === 2,
    'home page: stage times and optimization figures share the runtime section');
  await page.locator('footer a[href="#performance"]').click();
  await page.waitForFunction(() => document.getElementById('performance-evidence').open);
  record(new URL(page.url()).pathname === '/SlicerDSpace/index.html' &&
    new URL(page.url()).hash === '#performance',
    'home page: evidence link opens the disclosure without navigating to another page', page.url());
  const retired = await context.request.get(origin + '/SlicerDSpace/performance.html');
  record(retired.status() === 404, 'retired performance page is not published', String(retired.status()));
  await context.close();
}

async function runSkills(browser, origin) {
  for (const width of [1440, 390, 320]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    await page.goto(origin + '/index.html#skills', { waitUntil: 'load' });
    const skills = page.locator('#skills');
    await skills.scrollIntoViewIfNeeded();
    await page.waitForFunction(() => getComputedStyle(document.getElementById('skills')).opacity === '1');
    record(await skills.locator('h2').innerText() === 'Install, run and review with your Agent.',
      `skills ${width}px: visible install-and-use introduction`);
    record(await skills.locator('.doc-links a').count() === 3 &&
      await page.locator('#site-nav a[href="#skills"]').count() === 1,
      `skills ${width}px: navigation, Skill, usage and CLI template links`);
    const fit = await page.evaluate(() => {
      const el = document.querySelector('#skills .code pre');
      return el.scrollWidth <= el.clientWidth && document.documentElement.scrollWidth <= innerWidth;
    });
    record(fit, `skills ${width}px: prompt wraps without horizontal overflow`);
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await skills.locator('.copy').click();
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    record(copied === await skills.locator('pre code').innerText(),
      `skills ${width}px: sample Agent prompt copies intact`);
    await skills.screenshot({ path: path.join(OUT, `skills-${width}.png`) });
    await context.close();
  }
}

// ---------------------------------------------------------------- main
const server = await serve();
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  browser = await chromium.launch({
    ...(process.env.CHROME_EXECUTABLE ? { executablePath: process.env.CHROME_EXECUTABLE } : { channel: 'chrome' }),
    headless: true,
    args: ['--autoplay-policy=no-user-gesture-required'],
  });
  await runViewport(browser, origin, '1440x900', 1440, 900, {});
  await runViewport(browser, origin, '390x844', 390, 844, {});
  await runViewport(browser, origin, '320x640', 320, 640, { overflowOnly: true });
  // Header edge widths around the nav fold (Codex code review r1 B1: at 861-930 px the nav row overlapped the brand
  // inside the header, which the scrollWidth check could not see). The header must fit, and the brand, the visible
  // nav links, the status chip and the Menu button must not overlap.
  for (const w of [861, 900, 1023, 1024, 1100]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 800 } });
    const pg = await ctx.newPage();
    await pg.goto(origin + '/index.html', { waitUntil: 'load' });
    const hdr = await pg.evaluate(() => {
      const inner = document.querySelector('.header-inner');
      const shown = (el) => { const s = getComputedStyle(el), r = el.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
      const items = [document.querySelector('.brand'), document.getElementById('menu-btn'),
        ...document.querySelectorAll('#site-nav a, #site-nav .chip-status')].filter(shown);
      const rects = items.map((el) => ({ name: (el.textContent || '').trim().slice(0, 20), r: el.getBoundingClientRect() }));
      const hits = [];
      for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
        const a = rects[i].r, b = rects[j].r;
        if (a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5) hits.push(`${rects[i].name} / ${rects[j].name}`);
      }
      const fits = inner.scrollWidth <= inner.clientWidth && document.documentElement.scrollWidth <= window.innerWidth;
      return { fits, hits };
    });
    record(hdr.fits, `${w}px: header fits and page does not scroll sideways`, 'overflow');
    record(!hdr.hits.length, `${w}px: brand, nav links, chip and Menu button do not overlap`, hdr.hits.join('; '));
    await ctx.close();
  }
  await run404AndNoJs(browser, origin);
  await runSkills(browser, origin);
  await runReferenceLinks(browser, origin);
  for (const width of [1440, 390, 360, 320]) await runPerformance(browser, origin, width);
  await runPerformance(browser, origin, 390, true);
  await runHomePerformanceNavigation(browser, origin);
} catch (err) {
  record(false, 'browser run', String(err && err.stack || err));
} finally {
  if (browser) await browser.close();
  server.close();
}

const failedCount = results.filter((r) => !r.ok).length;
console.log(`${results.length} checks, ${failedCount} failed`);
console.log(`Screenshots: ${OUT}`);
process.exit(failedCount ? 1 : 0);
