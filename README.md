# SlicerDDSurfer project site (`gh-pages` branch)

## What this branch is

This branch holds the project site for SlicerDDSurfer. It is an orphan branch of `ChengjinLii/SlicerDDSurfer`.
The site is made from the repository docs at a48fc95 and the delivered promo film (render 8).

- The served site is `docs/`. The branch root (`README.md`, `SPEC.md`, `FACTS.md`, `tests/`) is not served.
- `SPEC.md` is the build spec. `FACTS.md` is the fact sheet. The site makes no claim that is not in `FACTS.md`.
- The site is static HTML, CSS and one small vanilla JS file. No build step. No third-party request at run time.
  Fonts are self-hosted (Latin subsets of Inter, Inter Tight and IBM Plex Mono, SIL OFL 1.1; the licence texts sit
  next to the fonts).
- The film in `docs/media/` is the delivered file, byte for byte (41,070,370 bytes). Nobody re-encoded it.

## How to publish (owner only)

Nothing in this branch turns Pages on. Do these steps in GitHub:

1. Open Settings → Pages.
2. Choose "Deploy from a branch".
3. Choose branch `gh-pages` and folder `/docs`.

The site is public once Pages is on, even while the repository is private. GitHub Pages on a private repository
needs a paid plan. Links from the site into the repository need repository access while it is private. The page says so.

## How to test

Run both commands from the branch root.

```
python3 -I tests/check_site.py [--film PATH]
PLAYWRIGHT_CORE=<dir of playwright-core> node tests/browser_check.mjs
```

- `check_site.py` uses the Python 3 standard library. It uses `ffprobe` when it is on PATH. With `--film PATH` it also
  compares the SHA-256 of the film with that file.
- `browser_check.mjs` needs Node, `playwright-core` and Google Chrome (`channel: 'chrome'`; Playwright's Chromium has
  no H.264/AAC). It serves `docs/` with Range support, runs the checks at 1440×900, 390×844 and 320×640, and writes
  screenshots to `tests/out/` (git-ignored).

## Revisit at public release

- The status chip "Private pre-release" in the header.
- The hero status line.
- The Status section.
- The "private" callout in Get started.
- The `og:url`, `og:image` and canonical URLs, and the home link in `404.html`, if the Pages address differs from
  `https://chengjinlii.github.io/SlicerDDSurfer/`. Also change the allowed set in `tests/check_site.py`.
- The Slicer version lines. The README says 5.10 (Get started). The film used 5.12.4 (In Slicer, footer).
  `--slicer-version` takes the form `Slicer-5.10`, and the module path follows it.

Owner note (not page copy): before you publish, listen to the final mix of the film. Nobody has listened to it yet.
The speech check (ASR) is automatic.

Links into the repository use `blob/main`. They follow `main`, not a48fc95. The page text describes the repository at
a48fc95, so check the linked files again at release.

Known limit: GitHub Pages serves `404.html` at any missing path, where relative links break. So `404.html` has inline
CSS and an inline icon, and it links home with the absolute Pages address.

## Review backlog

Items from the spec review (SPEC §9) that were not taken. They do not block the site.

- N2 (P2): SPEC v1 §3 said every crop must exclude the subtitle band, but the out-tracts and out-connectome boxes reach y = 1080. No cue is on screen at 43.0 s or 50.2 s, so the images are fine. SPEC v2 §3 rewords the rule.
- N12 (P3): at 34.8 s the white→pial morph is at about 0.94. At 35.4 s the full pial mesh shows, before the glass fade starts at 35.6 s.
- N15 (P3): SPEC §2/§3 do not name the font source or the JPEG tool (ffmpeg's mjpeg encoder alone cannot make progressive JPEG at quality 82).
- N16 (P3): an inline SVG with `xmlns="http://www.w3.org/2000/svg"` would fail the external-URL check. `check_site.py` now exempts namespace URIs.
- N18 (P3): for DDSeg the QC that passed is the world-space QC (DDSeg-vs-DDParcel WM Dice 0.848). The Outputs note says “Automatic QC passed for the … DDSeg … stages”; the reviewer found that acceptable.
- N19 (P3): CITATION.cff writes O'Donnell with an ASCII apostrophe in the DDSurfer entry; the page uses ’ (allowed by the SPEC typography rule).

### Code review, round 1 (commit 935a5d9; Opus and Codex)

Fixed in the fix round (each with a check that fails on 935a5d9 and passes after):
- Opus B1 (P1): the Get started callout called the model-asset repository private; `SlicerDDSurfer-models` is public
  (R/docs/release/VALIDATION_20260816.md:36). The clause is gone; `claims_banned` now rejects it.
- Codex B1 (P1): at 861–930 px the nav row overlapped the brand inside the header. The nav now folds at ≤ 1023 px;
  `browser_check.mjs` checks brand, nav links, chip and Menu button for overlap at 861, 900, 1023, 1024 and 1100 px.

Not fixed (non-blocking):
- Codex B2–B5, reclassified from P1 to P2: each is a form that `check_site.py` would miss, and none occurs on the site,
  so the site stays correct. B2: CSS `url()` in inline `<style>` blocks and `style` attributes is not host-checked.
  B3: `srcset` is host-checked as one URL, not per candidate. B4: CSS `url()` targets are not checked to stay inside
  `docs/`. B5: fragments on filename links (`index.html#x`) are not checked.
- Opus N1 (P2). **Fixed 2026-10-20** (user request): `site.js` now sets the `js` class itself (the inline script is
  gone) and first marks the sections already on screen as shown. `browser_check.mjs` blocks `site.js` at 1440 and
  390 px and needs all sections and the 8 nav links visible; it failed on 5b09bc2 (8 sections hidden; 0 links at 390 px).
  Review of bd002dd (Opus 0 blocking; Codex 1): Codex P1, the DOMContentLoaded check raced the IntersectionObserver
  (it passed 2 of 3 runs on 5b09bc2). Fixed in the fix round: an init script records the on-screen sections' state at
  the moment the `js` class appears, at 1440 and 390 px. Not fixed (non-blocking, Opus item 1, P2): on a phone, while a
  slow `site.js` loads, the no-JS header (182 px, wrapped links) shows and then drops to 64 px when the class arrives
  (one layout shift, CLS 0.13 with an 800 ms delay; none on a fast load); this is the accepted cost of keeping the
  content visible. Opus item 3 (P3) is done: SPEC §9 records the §4 sentence.
- Opus N2 (P2). **Fixed 2026-10-20** (user request): when the film ends and the video had focus, focus moves to the
  play button; focus the user put elsewhere stays (narrowed by r4 B1 below). `browser_check.mjs` checks both cases; the first failed
  on bd002dd (focus on `BODY`).
- Opus N3 (P2). **Fixed 2026-10-20** (user request): the open menu closes when focus moves to an element outside the
  nav and the Menu button (a focus change to nothing does not close it). `browser_check.mjs` tabs out
  of the open menu at 390 px and needs it closed (failed on bd002dd: still open), and checks that Shift+Tab back to the
  Menu button keeps it open.
- Opus N4 (P3): `slicer.jpg` shows path fragments from the film frame ("fer-promo/runtime/subjects/sub-01").
- Opus N5 (P3): the IBM Plex Mono subset keeps the name "IBM Plex Mono", while the OFL text names the Reserved Font
  Name "Plex". Option: use IBM's published Latin-1 subset files.
- Opus N6 (P3): `check_site.py` accepts any §6 URL in `<link rel="canonical">` and does not limit where the Pages URLs
  and the `.git` URL may appear.
- Opus N7 (P3): on the 404 page, `browser_check.mjs` ignores console errors that contain "404", so a missing asset
  there would pass.
- Opus N8 (P3): the no-JS block collects failed requests but does not check them; it runs only at 1440 px.
- Opus N9 (P3): Chrome runs with `--autoplay-policy=no-user-gesture-required`, so a future `play()` outside a user
  gesture would still pass.
- Opus N10 (P3): the "How to test" section lists 1440, 390 and 320 px only.

### Re-review of the fix round (commit 444d8db; Opus and Codex: 0 blocking)

Not fixed (non-blocking, from the Opus re-review; Codex found nothing):
- r2 N1 (P3): the round-1 notes sat under “Image crop boxes”; they are now here, under “Review backlog”.
- r2 N2 (P3): the header width loop checks fit and overlap, not that the Menu button shows at 1023 px and hides at
  1024 px; a moved CSS fold or a CSS/JS breakpoint drift would still pass. Fix idea: record
  `menuVisible === (w <= 1023)` in the loop.
- r2 N3 (P3): SPEC §7.2 should say “320×640 for overflow only”, as the code runs it.
- r2 N4 (P3): SPEC §4 should say that the status chip folds with the links at ≤ 1023 px (the hero status line still
  shows “Private pre-release”).
- r2 N5 (P3): the model-asset banned pattern does not catch the reverse order (“private model-asset repository”).

### Review of the N1 fix round and of N2/N3 (commits cce86e2 and ceedd6f; Opus and Codex: 0 blocking)

Not fixed (non-blocking, from the Opus review; Codex found nothing):
- r4 A1 (P3): the blink check measures “on screen” in the JS layout (64 px header); the `site.js` pre-pass measures in
  the no-JS layout (182 px header on phones). They agree at 1440×900 and 390×844 but not at 375×667 (the film is
  off screen without JS, on screen with it), so adding that size would fail the check with no real blink. Fix idea:
  in the snapshot, remove `js`, measure, add it back.
- r4 B1 (P2). **Fixed 2026-10-21** (user request): `hadFocus = document.activeElement === video`, so focus moves to
  the play button at film end only when the video had it; SPEC §5.3 says “move focus to the play button”.
  `browser_check.mjs` starts the film with a click, clicks plain text (focus on `<body>`) and needs focus still on
  `<body>` after the end; it failed on 484bf17 (focus on the play button).
- r4 B2 (P3). **Fixed 2026-10-21** (user request): the `focusout` comment, the N3 note above and SPEC §4 claimed that
  the click handlers deal with a focus change to nothing; none closes the menu then. All three now say “a focus change
  to nothing does not close it”. `check_site.py` `menu_focus_wording` needs that phrase in `site.js`, `README.md` and
  `SPEC.md` and rejects the old wording; it failed on c08a743.
- r4 B3 (P3). **Fixed 2026-10-21** (user request): `browser_check.mjs` opens the menu at 390×844 with a click on the
  Menu button, clicks `.chip-status` (focus moves to `<body>`) and needs the menu still open. It passes on c08a743 and
  fails on a copy of its `site.js` without the `to &&` test (the menu closes).
- r4 B4 (P3): SPEC §9 has no line for the N2/N3 edits to §4 and §5.3.

### Review of the r4 B1 fix (commit c08a743; Opus and Codex: 0 blocking)

Not fixed (non-blocking, from the Opus review; Codex found nothing):
- r5 1 (P3). **Fixed 2026-10-21** (user request): the three film-end focus checks now also need `video.ended` and
  the play button shown again (`endProof()`), and print both. With the seek in `toEnd()` skipped once (a copy of the
  test), the old checks for the nav link and for `<body>` passed with no film end; the new ones fail.

### Review of the r4 B2/B3 fix (commit 42e316d; Opus and Codex: 0 blocking)

Not fixed (non-blocking, from the Opus review; Codex found nothing):
- r6 1 (P3). **Fixed 2026-10-21** (user request): in README, `menu_focus_wording` now reads only the Opus N3 note, so
  a wrong N3 note fails even when another entry carries the phrase, and this history may quote the old wording
  (“is left to the click handlers”) again.
- r6 2 (P3). **Fixed 2026-10-21** (user request): SPEC §7.1 lists `menu_focus_wording` as item 15. Its test is a new
  check, item 16 `spec_lists_checks`: §7.1 must name every check the script runs, in run order, numbered 1..n. It
  failed on the badbad2 SPEC.
- r6 3 (P3). **Fixed 2026-10-21** (user request): `state()` returns `BODY` when `<body>` has focus. The status chip
  check now needs `active === 'BODY'` after the click (the separate `onBody` probe is gone); with the old `state()` it
  fails.

### Review of the r5/r6 fix (commit 90a6a03; Opus 0 blocking, Codex 1)

- Codex P1 (Opus: P3), fixed in the fix round: SPEC §7.1 item 15 quotes the phrase, and `menu_focus_wording` read all of
  SPEC, so a wrong §4 passed (it failed on badbad2). The check now reads SPEC only from `## 4.` to `## 5.`. With §4
  changed to “a focus change to nothing closes it too” and item 15 kept, it passed on 90a6a03 and fails now.

Not fixed (non-blocking, from the Opus review):
- r7 1 (P3). **Fixed 2026-10-21** (user request): film-end checks 1 and 2 did not prove that the film started (check 3
  does, with `/VIDEO/`); if Enter did not start the film, `toEnd()` played it to the end and check 1 still passed. Now
  each start is followed by `startProof()`: focus on the video, `video.ended` false and the play button hidden, printed
  as `start`. With the first or the second Enter press removed (copies of the test), the 3e1cbeb check 1 or 2 passed;
  the new one fails. The proof shows that the start handler ran, not that playback advanced.
- r7 2 (P3). **Fixed 2026-10-21** (user request): SPEC §9 gains a line for §7.1 items 15 and 16. Its test is a new
  rule in item 16 `spec_lists_checks`: §9 must name, in backticks, every §7.1 check that is not in the v2 list
  (`V2_CHECKS`, items 1–14). It failed on the 3e1cbeb SPEC (“§9 does not name `menu_focus_wording`; §9 does not name
  `spec_lists_checks`”). §7.1 item 16 now states the rule. The rule is a scope change (a new rule in an existing
  check), not only a fix.

### Review of the r7 fix (commit 06b6bb8; Opus and Codex: 0 blocking)

Not fixed (non-blocking, from the Opus review; Codex found nothing):
- r8 1 (P3): the item 16 rule for §9 passes when a post-v2 check name is in backticks anywhere in §9, also in a
  sentence that does not record that item. With the 2026-10-21 line removed and both names put into the N18/N19
  sentence, `spec_lists_checks` passed. Fix idea (a new rule, so a scope change): need ``item <n> `<name>` `` in §9,
  with `<n>` equal to the §7.1 number.
- r8 2 (P3): the new §9 line lists “README backlog r4 B2, r6 1–2 and r7 2” as its sources, but the “§4 only” scope
  of item 15 came from the Codex P1 of the 90a6a03 review. Fix: add that source to the list.
- Note (outside this diff): with the CSS rule `.film-play[hidden]{display:none}` removed, the play button stays
  drawn over the playing film, and `startProof()` still passes, because it reads the `hidden` attribute. The proof
  shows that the start handler ran; it does not check the CSS.


## Image crop boxes as finally used

Frames come from the delivered film with `ffmpeg -ss <t> -i <film> -frames:v 1`. Boxes are `x0,y0,x1,y1` in the
1920×1080 frame. JPEG quality 82, progressive, sRGB. Every output was checked by eye: no subtitle text, no cut-off
brain, no cut-off label.

| File | t (s) | Crop box | Output size | Change from SPEC v2 §3 |
|---|---|---|---|---|
| poster.jpg | 43.0 | full frame | 1920×1080 | none |
| idea.jpg | 9.0 | 60,60,1760,945 | 1400×729 | none (SPEC v2 uses y1 = 945) |
| out-dec.jpg | 22.8 | 815,155,1855,935 | 1200×900 | none |
| out-tissue.jpg | 27.0 | 725,150,1765,930 | 1200×900 | none |
| out-regions.jpg | 30.6 | 700,150,1740,930 | 1200×900 | none |
| out-surfaces.jpg | 34.8 | 665,155,1705,935 | 1200×900 | none |
| out-tracts.jpg | 43.0 | 470,0,1910,1080 | 1200×900 | none |
| out-connectome.jpg | 50.2 | 585,140,1838,1080 | 1200×900 | none |
| slicer.jpg | 56.8 | full frame | 1920×1080 | none (SPEC v2 uses 56.8 s: cue 11 ends at 56.5 s, the fade starts at 56.9 s) |
| social.jpg | – | `cover_1280x640.png` | 1280×640 | none (PNG converted to JPEG) |

`icon-64.png` and `icon-180.png` are resized from `Resources/Icons/SlicerDDSurfer.png` of the repository.
