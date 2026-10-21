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
  // Opus r1 N9: with sound, under Chrome's own autoplay policy (the click is the user gesture).
  await page.locator('#film').scrollIntoViewIfNeeded();
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
    // README r7 note: the CSS must hide the button too; the hidden attribute alone does not.
    const drawn = getComputedStyle(b).display !== 'none' && b.getBoundingClientRect().width > 0;
    return { controls: v.hasAttribute('controls'), btnHidden: b.hidden, btnDrawn: drawn, paused: v.paused };
  });
  record(advanced && !post.paused, `${tag}: click on the play button starts playback (currentTime ${t0.toFixed(2)} -> ${t1.toFixed(2)})`, JSON.stringify({ t0, t1, ...post }));
  record(post.controls && post.btnHidden && !post.btnDrawn, `${tag}: controls shown and play button hidden after start`, JSON.stringify(post));
  await page.screenshot({ path: path.join(OUT, `playing-${width}.png`) });

  // Ended state: jump near the end and wait for the button to return.
  await page.evaluate(() => { const v = document.getElementById('film-video'); v.currentTime = Math.max(0, v.duration - 0.6); });
  await page.waitForFunction(() => !document.querySelector('.film-play').hidden, null, { timeout: 8000 }).catch(() => {});
  const ended = await page.evaluate(() => {
    const b = document.querySelector('.film-play');
    const drawn = getComputedStyle(b).display !== 'none' && b.getBoundingClientRect().width > 0;
    return { hidden: b.hidden, drawn, label: b.textContent.trim(), controls: document.getElementById('film-video').hasAttribute('controls') };
  });
  record(!ended.hidden && ended.drawn && ended.label === 'Play again' && !ended.controls, `${tag}: on ended the button returns as "${ended.label}"`, JSON.stringify(ended));

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
  // Opus r1 N8: the no-JS run checks its failed loads, and it runs on a phone too.
  for (const [w, h] of [[1440, 900], [390, 844]]) {
    const context = await browser.newContext({ viewport: { width: w, height: h }, javaScriptEnabled: false });
    const page = await context.newPage();
    const failed = [];
    page.on('requestfailed', (r) => {
      const err = r.failure()?.errorText || '';
      if (err.includes('ERR_ABORTED') && /\/media\/[^/?#]+\.mp4$/.test(new URL(r.url()).pathname)) return;
      failed.push(`${r.url()} (${err})`);
    });
    page.on('response', (r) => { if (r.status() >= 400) failed.push(`${r.url()} (HTTP ${r.status()})`); });
    await page.goto(origin + '/index.html', { waitUntil: 'load' });
    await page.waitForTimeout(300);
    const nojs = await page.evaluate(() => {
      const v = document.getElementById('film-video');
      const hidden = [...document.querySelectorAll('.reveal')].filter((e) => getComputedStyle(e).opacity !== '1').length;
      return { controls: v.hasAttribute('controls'), hidden, copyShown: [...document.querySelectorAll('.copy')].some((b) => getComputedStyle(b).display !== 'none') };
    }).catch((e) => ({ error: String(e) }));
    record(nojs.controls === true && nojs.hidden === 0 && nojs.copyShown === false && failed.length === 0,
      `${w}x${h} no-JS: native controls stay, all sections visible, no dead Copy buttons, no failed load`,
      JSON.stringify({ ...nojs, failed }));
    await page.screenshot({ path: path.join(OUT, `nojs-${w}.png`) });
    await context.close();
  }

  // Opus r1 N7: on the 404 page only the page's own 404 status is expected. Any other console error, failed request
  // or response >= 400 fails, at /404.html and at a missing path (where GitHub Pages serves this file).
  for (const [p, status] of [['/404.html', 200], ['/no-such/page', 404]]) {
    const c2 = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const p2 = await c2.newPage();
    const docUrl = origin + p;
    const errs = [], bad = [];
    p2.on('console', (m) => { if (m.type() === 'error' && m.location().url !== docUrl) errs.push(m.text() + ' @ ' + m.location().url); });
    p2.on('requestfailed', (r) => bad.push(`${r.url()} (${r.failure()?.errorText || ''})`));
    p2.on('response', (r) => { if (r.status() >= 400 && r.url() !== docUrl) bad.push(`${r.url()} (HTTP ${r.status()})`); });
    const resp = await p2.goto(docUrl, { waitUntil: 'load' });
    await p2.waitForTimeout(300);
    const sw = await p2.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
    record(resp.status() === status && sw && errs.length === 0 && bad.length === 0,
      `404 page at ${p} (HTTP ${resp.status()}) renders without overflow, console errors or failed loads`,
      JSON.stringify({ status: resp.status(), sw, errs, bad }));
    if (status === 200) await p2.screenshot({ path: path.join(OUT, '404-390.png') });
    await c2.close();
  }
}

// ---------------------------------------------------------------- autoplay policy
// Opus r1 N9: the test browser keeps Chrome's own autoplay policy (no --autoplay-policy flag), so a play() with sound
// that no user gesture starts is refused here as it is for visitors. Playwright's page.evaluate() counts as a user
// gesture, so an init script makes the attempt. Review of 01ef29c (Opus B1, Codex P1): the metadata can load before
// DOMContentLoaded, so the script tries at once when it is there and waits for loadedmetadata only when it is not.
async function runAutoplayPolicy(browser, origin) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => {
    document.addEventListener('DOMContentLoaded', () => {
      const v = document.getElementById('film-video');
      if (!v) return;
      const go = () => {
        v.play().then(() => { window.__autoplay = 'played'; v.pause(); }, (e) => { window.__autoplay = e.name; });
      };
      if (v.readyState >= 1) go();
      else v.addEventListener('loadedmetadata', go, { once: true });
    });
  });
  const page = await ctx.newPage();
  await page.goto(origin + '/index.html', { waitUntil: 'load' });
  await page.waitForFunction(() => window.__autoplay, null, { timeout: 10000 }).catch(() => {});
  const r = await page.evaluate(() => window.__autoplay || 'no result');
  record(r === 'NotAllowedError', `1440x900: a play() with sound and no user gesture is refused (${r})`, r);
  await ctx.close();
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
  // Opus r5 1: toEnd() does not fail on its own, so each film-end check also needs proof that the film ended:
  // video.ended and the play button shown again.
  const endProof = () => page.evaluate(() => {
    const v = document.getElementById('film-video'), b = document.querySelector('.film-play');
    return { ended: v.ended, btnShown: !b.hidden && getComputedStyle(b).display !== 'none' && b.getBoundingClientRect().width > 0 };
  });
  // Opus r7 1: toEnd() plays the film even when Enter did not start it, so checks 1 and 2 also need proof that the start
  // ran: focus on the video, video.ended false and the play button hidden. The wait covers the seek to 0 on a replay.
  const startProof = async () => {
    await page.waitForFunction(() => {
      const v = document.getElementById('film-video'), b = document.querySelector('.film-play');
      return document.activeElement === v && !v.ended && b.hidden;
    }, null, { timeout: 3000 }).catch(() => {});
    // README r7 note: "shown" means drawn (CSS), not only the hidden attribute.
    const s = await page.evaluate(() => {
      const v = document.getElementById('film-video'), b = document.querySelector('.film-play');
      return { ended: v.ended, btnShown: getComputedStyle(b).display !== 'none' && b.getBoundingClientRect().width > 0 };
    });
    return { active: await active(), ...s };
  };
  const started = (s) => /VIDEO/.test(s.active) && !s.ended && !s.btnShown;
  // Keyboard start: focus the play button, press Enter (focus goes to the video), let the film end.
  await page.focus('.film-play');
  await page.keyboard.press('Enter');
  const s1 = await startProof();
  await toEnd();
  const a1 = await active(), e1 = await endProof();
  record(started(s1) && e1.ended && e1.btnShown && /film-play/.test(a1), '1440x900: when the film ends, focus moves to the play button',
    JSON.stringify({ start: s1, active: a1, ...e1 }));
  // Focus the user moved elsewhere stays there.
  await page.keyboard.press('Enter');
  const s2 = await startProof();
  await page.focus('#site-nav a[href="#idea"]');
  await toEnd();
  const a2 = await active(), e2 = await endProof();
  record(started(s2) && e2.ended && e2.btnShown && !/film-play/.test(a2) && /A/.test(a2), '1440x900: when the film ends, focus on a nav link stays there',
    JSON.stringify({ start: s2, active: a2, ...e2 }));
  // Opus r4 B1: a mouse user who starts the film and then clicks plain text (focus on <body>, and the Tab start point at
  // the click) keeps that focus when the film ends; it does not jump to the play button.
  await page.click('.film-play', { timeout: 5000 }).catch(() => {});
  const b0 = await active();
  await page.click('.hero .lead', { position: { x: 4, y: 4 } });
  const b1 = await active();
  await toEnd();
  const b2 = await active(), e3 = await endProof();
  record(e3.ended && e3.btnShown && /VIDEO/.test(b0) && b1 === 'BODY' && b2 === 'BODY',
    '1440x900: when the film ends after a click on plain text, focus stays on <body>',
    JSON.stringify({ afterStart: b0, afterClick: b1, afterEnd: b2, ...e3 }));
  await ctx.close();

  const c2 = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const p2 = await c2.newPage();
  await p2.goto(origin + '/index.html', { waitUntil: 'load' });
  const state = () => p2.evaluate(() => {
    const nav = document.getElementById('site-nav'), btn = document.getElementById('menu-btn'), a = document.activeElement;
    return { expanded: btn.getAttribute('aria-expanded'), navShown: getComputedStyle(nav).display !== 'none',
             inMenu: !!a && (a === btn || nav.contains(a)),
             // Opus r6 3: <body> is named by its tag; its text would be the whole page.
             active: !a ? 'null' : a === document.body ? 'BODY' : (a.textContent || '').trim().slice(0, 20) };
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
  // Opus r4 B3: a focus change to nothing must not close the open menu. A click on the Menu button focuses it; a click on
  // the status chip inside the open nav then moves focus to <body> (focusout with relatedTarget null).
  await p2.click('#menu-btn');
  const chip0 = await state();
  await p2.click('#site-nav .chip-status');
  await p2.waitForTimeout(100);
  const chip1 = await state();
  record(chip0.expanded === 'true' && chip0.active === 'Menu' && chip1.active === 'BODY' && chip1.expanded === 'true' && chip1.navShown,
    '390x844: a click on the status chip in the open menu keeps it open', JSON.stringify({ before: chip0, after: chip1 }));
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
  // Opus r4 A1: site.js picks the on-screen sections in the no-JS layout (before it adds the class), and the no-JS
  // header is taller on phones, so the snapshot measures there too: it removes the class, measures, and adds it back.
  // At 375x667 the two layouts disagree about the film section. There the no-JS hero fills the first screen, so no
  // section is on it (needOn false).
  for (const [w, h, needOn] of [[1440, 900, true], [390, 844, true], [375, 667, false]]) {
    const context = await browser.newContext({ viewport: { width: w, height: h } });
    await context.addInitScript(() => {
      new MutationObserver((records, obs) => {
        const html = document.documentElement;
        if (!html || !html.classList.contains('js')) return;
        obs.disconnect();
        const vh = window.innerHeight;
        const reveal = [...document.querySelectorAll('.reveal')];
        html.classList.remove('js');
        const onScreen = reveal.filter((e) => { const r = e.getBoundingClientRect(); return r.top < vh && r.bottom > 0; });
        html.classList.add('js');
        window.__jsSnap = { reveal: reveal.length, onScreen: onScreen.map((e) => e.id), notIn: onScreen.filter((e) => !e.classList.contains('in')).map((e) => e.id) };
      }).observe(document, { subtree: true, attributes: true, attributeFilter: ['class'] });
    });
    const page = await context.newPage();
    await page.goto(origin + '/index.html', { waitUntil: 'load' });
    const st = await page.evaluate(() => window.__jsSnap || null);
    record(!!st && st.reveal > 0 && (!needOn || st.onScreen.length > 0) && st.notIn.length === 0,
      `${w}x${h} with site.js: when the js class appears, every on-screen section is already shown`, JSON.stringify(st));
    await context.close();
  }
}

// ---------------------------------------------------------------- main
const server = await serve();
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  // Opus r1 N9: no --autoplay-policy flag, so Chrome's own policy applies (see runAutoplayPolicy).
  browser = await chromium.launch({ channel: 'chrome', headless: true });
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
      return { fits, hits, menuVisible: shown(document.getElementById('menu-btn')) };
    });
    record(hdr.fits, `${w}px: header fits and page does not scroll sideways`, 'overflow');
    record(!hdr.hits.length, `${w}px: brand, nav links, chip and Menu button do not overlap`, hdr.hits.join('; '));
    // Opus r2 N2: the Menu button shows up to 1023 px and hides from 1024 px, so a moved CSS fold fails.
    record(hdr.menuVisible === (w <= 1023), `${w}px: Menu button ${w <= 1023 ? 'shown' : 'hidden'}`, JSON.stringify(hdr));
    await ctx.close();
  }
  await run404AndNoJs(browser, origin);
  await runScriptBlocked(browser, origin);
  await runFocusChecks(browser, origin);
  await runAutoplayPolicy(browser, origin);
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
