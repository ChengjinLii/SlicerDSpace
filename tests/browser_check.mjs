// Headless Chrome checks for the SlicerDDSurfer project site (SPEC section 7.2).
//
// Run from the branch root:
//   PLAYWRIGHT_CORE=<dir of playwright-core> node tests/browser_check.mjs
//
// Serves docs/ from a local HTTP server with Range support (like GitHub Pages),
// opens it in Google Chrome (channel 'chrome': Playwright's Chromium lacks H.264/AAC)
// and writes full-page screenshots to tests/out/ (git-ignored).

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const here = path.dirname(fileURLToPath(import.meta.url));
const DOCS = path.resolve(here, '..', 'docs');
const OUT = path.resolve(here, 'out');
fs.mkdirSync(OUT, { recursive: true });

const coreDir = process.env.PLAYWRIGHT_CORE;
if (!coreDir) {
  console.error('FAIL setup - set PLAYWRIGHT_CORE to the directory of playwright-core');
  process.exit(2);
}
const require = createRequire(import.meta.url);
const { chromium } = require(path.resolve(coreDir));

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
};

// ---------------------------------------------------------------- server
function serve() {
  const server = http.createServer((req, res) => {
    let urlPath = decodeURIComponent(new URL(req.url, 'http://x').pathname);
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
        if (el.closest('pre') || el.closest('.sr-only')) return false;
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
  record(vid.readyState >= 1 && Math.abs(vid.duration - 64.8) <= 0.05 && vid.videoWidth === 1920,
    `${tag}: video metadata (readyState ${vid.readyState}, duration ${vid.duration?.toFixed?.(3)}, width ${vid.videoWidth})`,
    JSON.stringify(vid));
  record(vid.can !== '', `${tag}: canPlayType for avc1.640032 + mp4a.40.2 is "${vid.can}"`, 'empty');

  // The play button replaces the native controls at start.
  const pre = await page.evaluate(() => {
    const v = document.getElementById('film-video');
    const b = document.querySelector('.film-play');
    return { controls: v.hasAttribute('controls'), btn: !!b && !b.hidden, label: b ? b.textContent.trim() : '' };
  });
  record(!pre.controls && pre.btn && pre.label === 'Play film · 1:05',
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
    await page.locator('#site-nav a[href="#status"]').click();
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
      top: Math.round(document.getElementById('status').getBoundingClientRect().top),
    }));
    record(s.exp === 'false' && s.top >= 0 && s.top < 200, `${tag}: link click closes the menu and lands on #status (top ${s.top})`, JSON.stringify(s));
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
  record(tr === 12, `${tag}: transcript has ${tr} lines`, String(tr));

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

// ---------------------------------------------------------------- focus after the film ends, and the open menu
// Opus N2 (code review round 1): when the film ended, the handler removed `controls` from the focused video and focus
// fell to <body>. Opus N3: with the phone menu open, Tab moved focus to controls under the menu panel.
async function runFocusChecks(browser, origin) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(origin + '/index.html', { waitUntil: 'load' });
  await page.waitForFunction(() => document.getElementById('film-video').readyState >= 1, null, { timeout: 15000 }).catch(() => {});
  const toEnd = async () => {
    await page.evaluate(() => { const v = document.getElementById('film-video'); v.muted = true; v.currentTime = Math.max(0, v.duration - 0.4); if (v.paused) v.play(); });
    await page.waitForFunction(() => document.getElementById('film-video').ended, null, { timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(100);
  };
  const active = () => page.evaluate(() => { const a = document.activeElement; return a ? (a.className || a.tagName) + (a.id ? '#' + a.id : '') : 'null'; });
  // Keyboard start: focus the play button, press Enter (focus goes to the video), let the film end.
  await page.focus('.film-play');
  await page.keyboard.press('Enter');
  await toEnd();
  const a1 = await active();
  record(/film-play/.test(a1), '1440x900: when the film ends, focus moves to the play button', `active: ${a1}`);
  // Focus the user moved elsewhere stays there.
  await page.keyboard.press('Enter');
  await page.focus('#site-nav a[href="#idea"]');
  await toEnd();
  const a2 = await active();
  record(!/film-play/.test(a2) && /A/.test(a2), '1440x900: when the film ends, focus on a nav link stays there', `active: ${a2}`);
  // Opus r4 B1: a mouse user who starts the film and then clicks plain text (focus on <body>, and the Tab start point at
  // the click) keeps that focus when the film ends; it does not jump to the play button.
  await page.click('.film-play');
  const b0 = await active();
  await page.click('.hero .lead', { position: { x: 4, y: 4 } });
  const b1 = await active();
  await toEnd();
  const b2 = await active();
  record(/VIDEO/.test(b0) && b1 === 'BODY' && b2 === 'BODY',
    '1440x900: when the film ends after a click on plain text, focus stays on <body>', JSON.stringify({ afterStart: b0, afterClick: b1, afterEnd: b2 }));
  await ctx.close();

  const c2 = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const p2 = await c2.newPage();
  await p2.goto(origin + '/index.html', { waitUntil: 'load' });
  const state = () => p2.evaluate(() => {
    const nav = document.getElementById('site-nav'), btn = document.getElementById('menu-btn'), a = document.activeElement;
    return { expanded: btn.getAttribute('aria-expanded'), navShown: getComputedStyle(nav).display !== 'none',
             inMenu: !!a && (a === btn || nav.contains(a)), active: a ? (a.textContent || '').trim().slice(0, 20) : 'null' };
  });
  // Shift+Tab from the first link back to the Menu button keeps the menu open.
  await p2.focus('#menu-btn');
  await p2.keyboard.press('Enter');
  await p2.keyboard.press('Tab');
  await p2.keyboard.press('Shift+Tab');
  const back = await state();
  record(back.expanded === 'true' && back.navShown && back.active === 'Menu',
    '390x844: Shift+Tab from the first menu link to the Menu button keeps the menu open', JSON.stringify(back));
  // Tab past the last link closes the menu as soon as focus leaves it.
  let left = null;
  for (let i = 0; i < 12 && !left; i++) {
    await p2.keyboard.press('Tab');
    const s = await state();
    if (!s.inMenu) left = s;
  }
  record(!!left && left.expanded === 'false' && !left.navShown,
    '390x844: Tab out of the open menu closes it', JSON.stringify(left));
  await c2.close();
}

// ---------------------------------------------------------------- site.js fails to load
// Opus N1 (code review round 1): an inline script set the js class, so when site.js failed to load every .reveal
// section stayed at opacity 0 and the folded nav could not open. site.js now sets the class itself.
async function runScriptBlocked(browser, origin) {
  for (const [w, h] of [[1440, 900], [390, 844]]) {
    const context = await browser.newContext({ viewport: { width: w, height: h } });
    await context.route('**/assets/js/site.js', (r) => r.abort());
    const page = await context.newPage();
    await page.goto(origin + '/index.html', { waitUntil: 'load' });
    await page.waitForTimeout(1200);
    const st = await page.evaluate(() => {
      const shown = (el) => { const s = getComputedStyle(el), r = el.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
      const reveal = [...document.querySelectorAll('.reveal')];
      return {
        js: document.documentElement.classList.contains('js'),
        sections: reveal.length,
        hidden: reveal.filter((e) => getComputedStyle(e).opacity !== '1' || !shown(e)).length,
        links: [...document.querySelectorAll('#site-nav a')].filter(shown).length,
        overflow: document.documentElement.scrollWidth > window.innerWidth,
      };
    });
    record(!st.js && st.sections > 0 && st.hidden === 0 && st.links === 8 && !st.overflow,
      `${w}x${h} with site.js blocked: all ${st.sections} sections and 8 nav links visible, no sideways scroll`, JSON.stringify(st));
    await page.screenshot({ path: path.join(OUT, `noscript-file-${w}.png`), fullPage: true });
    await context.close();
  }
  // With site.js loaded, the sections on the first screen must already be shown when the js class appears, so they do
  // not blink. Codex review of bd002dd (P1): reading the page after DOMContentLoaded raced the IntersectionObserver,
  // which could add `in` first. An init script now records the state at the moment the class is set.
  for (const [w, h] of [[1440, 900], [390, 844]]) {
    const context = await browser.newContext({ viewport: { width: w, height: h } });
    await context.addInitScript(() => {
      new MutationObserver((records, obs) => {
        const html = document.documentElement;
        if (!html || !html.classList.contains('js')) return;
        obs.disconnect();
        const vh = window.innerHeight;
        const reveal = [...document.querySelectorAll('.reveal')];
        const onScreen = reveal.filter((e) => { const r = e.getBoundingClientRect(); return r.top < vh && r.bottom > 0; });
        window.__jsSnap = { reveal: reveal.length, onScreen: onScreen.map((e) => e.id), notIn: onScreen.filter((e) => !e.classList.contains('in')).map((e) => e.id) };
      }).observe(document, { subtree: true, attributes: true, attributeFilter: ['class'] });
    });
    const page = await context.newPage();
    await page.goto(origin + '/index.html', { waitUntil: 'load' });
    const st = await page.evaluate(() => window.__jsSnap || null);
    record(!!st && st.reveal > 0 && st.onScreen.length > 0 && st.notIn.length === 0,
      `${w}x${h} with site.js: when the js class appears, every on-screen section is already shown`, JSON.stringify(st));
    await context.close();
  }
}

// ---------------------------------------------------------------- main
const server = await serve();
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  browser = await chromium.launch({
    channel: 'chrome',
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
  await runScriptBlocked(browser, origin);
  await runFocusChecks(browser, origin);
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
