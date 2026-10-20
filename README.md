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
  the moment the `js` class appears, at 1440 and 390 px. Not fixed (non-blocking, Opus): N1 (P2) on a phone, while a
  slow `site.js` loads, the no-JS header (182 px, wrapped links) shows and then drops to 64 px when the class arrives
  (one layout shift, CLS 0.13 with an 800 ms delay; none on a fast load); this is the accepted cost of keeping the
  content visible. N3 (P3) is done: SPEC §9 records the §4 sentence.
- Opus N2 (P2): when the film ends, focus falls to `body` (the `ended` handler removes `controls` from the focused
  video). Fix idea: focus the play button.
- Opus N3 (P2): with the phone menu open, Tab moves focus to controls under the menu panel. Fix idea: close on
  `focusout` outside the nav.
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
