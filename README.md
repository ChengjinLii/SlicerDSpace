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
  no H.264/AAC). It serves `docs/` with Range support and runs Chrome with its own autoplay policy. It runs the page
  checks at 1440×900 and 390×844, the overflow checks at 320×640, the header checks at 861, 900, 1023, 1024 and
  1100 px wide, the no-JS checks at 1440×900 and 390×844, the 404 checks at 390×844, the first-screen checks at
  1440×900, 390×844 and 375×667, and the focus checks at 1440×900 and 390×844. It writes screenshots to `tests/out/`
  (git-ignored).

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

- N2 (P2). **Closed** (marked 2026-10-22): SPEC v1 §3 said every crop must exclude the subtitle band, but the
  out-tracts and out-connectome boxes reach y = 1080. No cue is on screen at 43.0 s or 50.2 s, so the images are fine.
  SPEC v2 §3 rewords the rule.
- N12 (P3). **Fixed 2026-10-22** (user request): at 34.8 s the white→pial morph was at about 0.94; `out-surfaces.jpg`
  now comes from 35.4 s (the full pial mesh, before the glass fade at 35.6 s), same box, checked by eye (no subtitle,
  no cut-off brain). `images` pins the file by SHA-256; with the old file it fails.
- N15 (P3). **Fixed 2026-10-22** (user request): SPEC §2 names the font sources (`P/film/fonts/`) and tools
  (fontTools 4.67.0 `pyftsubset`, brotli 1.2.0); §3 and the crop section below name Pillow 13.0.0 for the JPEGs. Rows
  pin both; the old SPEC fails them.
- N16 (P3). **Closed** (marked 2026-10-22): an inline SVG with `xmlns="http://www.w3.org/2000/svg"` would fail the
  external-URL check. `check_site.py` exempts namespace URIs (`NAMESPACE_PREFIXES`).
- N18 (P3). **No change** (marked 2026-10-22): for DDSeg the QC that passed is the world-space QC (DDSeg-vs-DDParcel
  WM Dice 0.848). The Outputs note says “Automatic QC passed for the … DDSeg … stages”; the reviewer found that
  acceptable.
- N19 (P3). **Not on this branch** (marked 2026-10-22): `CITATION.cff` writes O'Donnell with an ASCII apostrophe in the
  DDSurfer entry; the page uses ’ (allowed by the SPEC typography rule). `CITATION.cff` is on `main`, which this branch
  does not change; fix it there if wanted. **Closed 2026-10-23, no change** (the user asked to close every open item):
  an ASCII apostrophe is the usual spelling in citation metadata (YAML, name matching), so the file's ' and the page's ’
  are both right, and this branch does not change `main` (the user's choice when the site went to `gh-pages`).

### Code review, round 1 (commit 935a5d9; Opus and Codex)

Fixed in the fix round (each with a check that fails on 935a5d9 and passes after):
- Opus B1 (P1): the Get started callout called the model-asset repository private; `SlicerDDSurfer-models` is public
  (R/docs/release/VALIDATION_20260816.md:36). The clause is gone; `claims_banned` now rejects it.
- Codex B1 (P1): at 861–930 px the nav row overlapped the brand inside the header. The nav now folds at ≤ 1023 px;
  `browser_check.mjs` checks brand, nav links, chip and Menu button for overlap at 861, 900, 1023, 1024 and 1100 px.

Not fixed (non-blocking):
- Codex B2–B5, reclassified from P1 to P2: each was a form that `check_site.py` would miss, and none occurs on the
  site. **Fixed 2026-10-22** (user request): B2: `external_urls` host-checks CSS `url()` and `@import` in `<style>`
  blocks and `style` attributes, and `local_refs` resolves `url()` in `style` attributes. B3: each `srcset` candidate is
  host-checked. B4: a CSS file's `url()` must resolve inside `docs/`. B5: a fragment after a page's file name
  (`index.html#x`) must name an `id` in that page. For each, a copy of `docs/` with the form added passes the 49806c6
  script and fails the new one.
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
- Opus N4 (P3). **No change** (user choice, 2026-10-22): `slicer.jpg` shows two path fields (“…fer-promo/runtime/
  subjects/sub-01”). Every frame of the film's Slicer segment (52–56.8 s) shows them, and the brain spans about
  y = 95–500, so no single crop removes the fields and keeps both the brain and the module panel. The embedded film
  shows the same frame, so an edit to the still would not remove the paths from the page. They are the film's local
  run folder names, not private data.
- Opus N5 (P3). **Fixed 2026-10-22** (user request): the two IBM Plex Mono subsets now carry the family name
  “DDS Mono” (name IDs 1, 3, 4 and 6; fontTools shows every other table unchanged and 291 glyphs in each), as SIL OFL
  1.1 §3 asks of a modified version. `site.css` loads them as “DDS Mono”, and the footer says so. `fonts_licensed`
  pins the `.woff2` files by SHA-256 and fails an `@font-face` family with “Plex”; with the old fonts or the old
  `site.css` it fails. The file names keep `IBMPlexMono`; `404.html` names “IBM Plex Mono” only as a local font and
  loads no file.
- Opus N6 (P3). **Fixed 2026-10-22** (user request): the canonical link must be the Pages root URL, and the Pages
  URLs and the `.git` URL may appear only in the places `PLACED_URLS` names (the canonical link, `og:url` and
  `og:image` of `index.html`, the home links of `404.html`, and right after `git clone `). A canonical link to the
  social image, a Pages link in the page body and the `.git` URL in a paragraph each pass the 49806c6 script and fail
  the new one.
- Opus N7 (P3). **Fixed 2026-10-22** (user request): on the 404 page, `browser_check.mjs` now ignores only the
  console error of the page's own 404 status; any other console error, failed request or response ≥ 400 fails, at
  `/404.html` and at a missing path. The fix showed a real miss: Chrome asked for `/favicon.ico` (404). `404.html` now
  names its inline icon as the favicon. With a `<link rel="icon" href="/missing.png">` added to `404.html`, the
  3ba7996 suite passes and the new one fails.
- Opus N8 (P3). **Fixed 2026-10-22** (user request): the no-JS block checks failed requests and responses ≥ 400,
  at 1440×900 and 390×844. A missing image in a `<noscript>` block, and a CSS rule that hides the sections without JS
  only at ≤ 400 px, each pass the 3ba7996 suite and fail the new one.
- Opus N9 (P3). **Fixed 2026-10-22** (user request): Chrome runs without `--autoplay-policy`, so its own policy
  applies, and the click test plays with sound. A new check makes a `play()` with sound from an init script (no user
  gesture; Playwright's `page.evaluate()` counts as one) and needs `NotAllowedError`. With the old flag the attempt
  plays and the check fails.
- Opus N10 (P3). **Fixed 2026-10-22** (user request): “How to test” lists every size the browser checks run at.
  A row pins the 375×667 entry.

### Re-review of the fix round (commit 444d8db; Opus and Codex: 0 blocking)

Not fixed (non-blocking, from the Opus re-review; Codex found nothing):
- r2 N1 (P3). **Closed** (marked 2026-10-22): the round-1 notes sat under “Image crop boxes”; they are now here,
  under “Review backlog”.
- r2 N2 (P3). **Fixed 2026-10-22** (user request): the header width loop records `menuVisible === (w <= 1023)`.
  With the CSS fold moved to ≤ 1000 px, the 3ba7996 suite passes and the new one fails at 1023 px.
- r2 N3 (P3). **Fixed 2026-10-22** (user request): SPEC §7.2 says “320×640 for overflow only” and names the other
  sizes. A row pins it.
- r2 N4 (P3). **Fixed 2026-10-22** (user request): SPEC §4 says that the links and the chip fold into the Menu
  button, and that the hero status line still shows “Private pre-release”. A row pins it.
- r2 N5 (P3). **Fixed 2026-10-22** (user request): `claims_banned` also bans the reverse order (“private
  model-asset repository”). A copy with that sentence passes the 49806c6 script and fails the new one.

### Review of the N1 fix round and of N2/N3 (commits cce86e2 and ceedd6f; Opus and Codex: 0 blocking)

Not fixed (non-blocking, from the Opus review; Codex found nothing):
- r4 A1 (P3). **Fixed 2026-10-22** (user request): the snapshot removes the `js` class, measures, and adds it back,
  so it measures in the no-JS layout as the `site.js` pre-pass does; the check also runs at 375×667. The old snapshot
  fails at 375×667 with no real blink, and the new one passes; with the pre-pass removed from `site.js`, the new one
  fails at 1440×900 and 390×844. At 375×667 it passes: no section is on the first screen of the no-JS layout there,
  so that run only guards a future layout (README r22 3).
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
- r4 B4 (P3). **Fixed 2026-10-22** (user request): SPEC §9 has a paragraph for the N2/N3 edits to §4 and §5.3. A
  row pins it.

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
- r8 1 (P3). **Fixed 2026-10-21** (user request): the item 16 rule for §9 passed when a post-v2 check name was in
  backticks anywhere in §9, also in a sentence that does not record that item. §9 must now say ``item <n> `<name>` ``,
  with n the §7.1 number (a scope change; §7.1 item 16 and a new §9 line say so). The ca62e10 check passed and the
  new check fails on two SPEC copies: the Opus copy (the 2026-10-21 line removed, both names in the N18/N19
  sentence) and the current SPEC with “item 15” changed to “item 14”. Limit (r9 3): a sentence that uses the form
  only in passing, without recording the item, still passes.
- r8 2 (P3). **Fixed 2026-10-21** (user request): the §9 line listed “README backlog r4 B2, r6 1–2 and r7 2” as its
  sources, but the “§4 only” scope of item 15 came from the Codex P1 of the 90a6a03 review; the list now names it.
  Test: `spec_lists_checks` needs a §9 paragraph that records item 15 to cite that review (`SECTION9_SOURCES`).
  It fails on the ca62e10 SPEC, and on a copy where the citation is in another §9 paragraph.
- Note (outside this diff), **fixed 2026-10-22** (user request): with the CSS rule `.film-play[hidden]{display:none}`
  removed, the play button stayed drawn over the playing film, and `startProof()` still passed, because it read the
  `hidden` attribute. The start checks (`startProof()` and the click test) now need the button not drawn (computed
  style), and the end checks need it drawn. With the rule removed, the 3ba7996 suite passes and the new one fails.

### Review of the r8 fix (commit 18827b4; Opus 0 blocking, Codex 1, reclassified P3)

Not fixed (non-blocking):
- r9 1 (Codex P1, Opus P3; reclassified P3). **Fixed 2026-10-21** (user request): `spec_lists_checks` split §9 on
  `\n\n`, so a blank line that holds a space joined two paragraphs: with the citation moved to the r8 paragraph and a
  space on the blank line between, the check passed. It now splits with `re.split(r"\n[ \t]*\n", …)`; on the same
  copy of the current SPEC (a space or a tab) it fails, and with the old split restored it passes. Why P3: the
  committed SPEC had no whitespace-only line, so the check passed for the right reason; it failed on both real forms
  of r8 2 (the ca62e10 SPEC and the moved citation); a false pass needed two edits at once. This differs from the
  Codex P1 of the 90a6a03 review, where the committed SPEC itself (item 15 quoting the phrase) made the check unable
  to fail on a wrong §4.
- r9 2 (Opus P3). **Fixed 2026-10-21** (user request): the code accepts the citation from any §9 paragraph that
  records item 15; §7.1 item 16 said “the §9 paragraph” and now says “a §9 paragraph that records item 15”.
- r9 3 (Opus P3). **Fixed 2026-10-21** (user request): a sentence that uses the ``item <n> `<name>` `` form in
  passing, without recording the item, still passes. This is the limit of a pinned-form text check; the r8 1 note
  now says so. The rule is not changed (a stricter rule would be a scope change).
- r9 4 (Opus P3, nit). **Fixed 2026-10-21** (user request): the comment above `V2_CHECKS` did not name the
  ``item <n> `<name>` `` form; it now does.
- Test for r9 2–4: a new check, SPEC §7.1 item 17 `backlog_wording` (a scope change). Its `WORDING_FIXES` table
  gives, for each finding, the part of the file it names (§7.1 item 16, the README r8 1 note, the comment above
  `V2_CHECKS`), the fixed phrase and, where there is one, the old phrase. It failed on all three before the fixes; a copy that undoes one
  fix fails on that finding only.
- Accepted limits of the pinned-text citation check (not findings): a negated citation and a citation inside an
  HTML comment both pass.

### Review of the r9 fix (commit 84c2ffd; Opus and Codex: 0 blocking)

Not fixed (non-blocking, from the Opus review; Codex found nothing):
- r10 1 (P2). **Fixed 2026-10-21** (user request): no committed test guarded the r9 1 fix; with `split("\n\n")` put
  back, every check passed. A `WORDING_FIXES` row now pins the `re.split(r"\n[ \t]*\n"` call in the body of
  `spec_lists_checks` and bans `.split("\n\n")` there. With the old split put back, the ebbeb2a script passes and the
  new script fails (`r10 1: … lacks …; … still says …`).
- r10 2 (P2). **Fixed 2026-10-21** (user request): `spec_lists_checks` trusted that the checks in `later` run. After
  the loop, `main()` now compares the names in `results` with the list that `spec_lists_checks` checked and adds a
  FAIL if they differ. With the loop deleted, the ebbeb2a script passes with 16 results and the new script fails
  (“the checks that ran … differ from the list it checked …”). A `WORDING_FIXES` row pins the comparison
  (`if ran != checked:`); with the comparison deleted, `backlog_wording` fails.
- r10 3 (P3). **Fixed 2026-10-21** (user request): in a `.py` part, `backlog_wording` now removes `^[ \t]*# ?` from
  each line before the join. Committed guard: the comment above `V2_CHECKS` now wraps the phrase
  ``item <n> `<name>` `` across two comment lines on purpose; without the strip the r9 4 row fails on it, and the
  ebbeb2a script fails on that comment too. With the old phrase wrapped across two comment lines, the ebbeb2a script
  passes and the new script fails.
- r10 4 (P3). **Fixed 2026-10-21** (user request): the comment above `SECTION9_SOURCES` and the r8 2 entry above
  now say “a §9 paragraph”. Test: two `WORDING_FIXES` rows; each fails when its old text is put back.
- r10 5 (P3). **Fixed 2026-10-21** (user request): SPEC §7.1 item 17 and the r9 test entry above now say “and,
  where there is one, the old phrase”. Test: two `WORDING_FIXES` rows; each fails when its old text is put back.
- The four new wording rows failed on the ebbeb2a wording before the fixes. SPEC §7.1 item 17 now lists the table's
  findings (r9 2–4 and r10 1, 2, 4, 5) instead of the three parts, and item 16 names the `main()` comparison.

### Review of the r10 fix (commit af78411; Opus 0 blocking, Codex 1)

- Codex P1 (Opus: P2), fixed in the fix round: in a code row, a pinned phrase inside a comment satisfied the pin.
  With the comparison in `main()` commented out, the r10 2 row passed (17/0), so one common edit removed the r10 2
  fix while the guard stayed green. I treated it as blocking for that reason (r9 1 needed two edits). Now a `.py`
  part that holds code loses its comment lines before the test; a part made of comment lines still loses only the
  marks. Committed guard: the comment in `spec_lists_checks` names the old `.split("\n\n")`; with the af78411
  logic the r10 1 row fails on it. With the comparison commented out, deleted with the phrase left in a comment,
  or the `re.split` line commented out and the old split put back with single quotes, the af78411 script passes and
  the fixed script fails.

Not fixed (non-blocking, from the Opus review):
- r11 1 (P2). **Fixed 2026-10-21** (user request): the r10 2 row sliced all of `main()`, so it passed when the
  comparison moved below the `print("%d checks…")` line. It now slices from `for f in later:` to `failed = 0`
  (`MAIN_TAIL`). With the comparison moved below the count, the c9d46ec script passes and the new script fails.
- r11 2 (P3). **Fixed 2026-10-21** (user request): the r10 1 row now bans the old split with a regex in both quote
  styles (a row's banned phrase may be a string, a compiled regex or `None`). With `.split('\n\n')` added after the
  `re.split` line, the c9d46ec script passes and the new script fails. Limit (README r13 2, r14 1): Code pins accept
  dead code and other spellings. This holds for every code pin in `WORDING_FIXES`, not only this ban. A pinned line
  still counts when it does not run (under `if False:`, or below a `return` moved above it) and when a line added after
  it undoes it (for example `sample = CODE_SAMPLE_TEXT` added below the line that makes the sample), and when code is
  added at its end (README r29 2: for example `labels = set().union(...) | listed`, since a fixed phrase only has to be
  in the text). A ban misses other spellings of the old code: six other spellings of the old split pass, for example
  `.split( "\n\n" )` or `.split(sep="\n\n")`; the old split under `if False:` still fails the ban, because a ban reads
  text.
- r11 3 (P3). **Fixed 2026-10-21** (user request): a check called after the run-order comparison was neither listed
  nor compared. `main()` now sets `RUN["compared"]` after the comparison, and the `check()` wrapper fails a check
  that runs after that. With `menu_focus_wording()` called again after the comparison, the c9d46ec script passes
  (18/0) and the new script fails (“runs after the run-order comparison”). Two rows pin the flag and the wrapper test.
  The `later` loop stays, because the r11 1 slice names it; so this is a flag, not the “one list” idea.
  (r13 1 later moved the flag to the line above the comparison and added the summary flag.)
- r11 4 (P3). **Fixed 2026-10-21** (user request): the comment in `backlog_wording` now speaks of each fix in
  `WORDING_FIXES` (wording, or a code line that guards a fix), with no finding numbers. A row pins it.
- Limit (not a finding): with the `later` loop deleted and the comparison commented out (two edits), the suite
  passes with 16 results, because the rows run inside that loop.

### Re-review of the r10 fix round (commit dfc17e5; Opus and Codex: 0 blocking)

Non-blocking items from the Opus re-review (Codex found nothing). Each item also passed on af78411, so the fix round
did not cause it:
- r12 1 (P2). **Fixed 2026-10-21** (user request): a code part lost only whole `#` lines. Now `code_text` blanks out
  every `COMMENT` token (`tokenize`), also at the end of a line. With the comparison deleted and the phrase left in a
  trailing comment, the c9d46ec script passes and the new script fails. A built-in sample (a trailing comment, a
  comment line, a `#` inside a string) tests the remover: a whole-line remover and a cut-at-`#` remover both fail
  it. Two rows pin the call `part = code_text(part)` and the sample test. SPEC §7.1 item 17 and the af78411 §9
  paragraph now say what the code does (two rows). Limit: code in a string still counts, so the comparison wrapped
  in `"""` still passes.
- r12 2 (P2). **Fixed 2026-10-21** (user request): a row on `MAIN_TAIL` now also pins the
  `results.append(("FAIL", "spec_lists_checks", …` line. With that body replaced by `pass`, the c9d46ec script passes
  and the new script fails.
- r12 3 (P3). **Fixed 2026-10-21** (user request): the review record of af78411 now says “the `re.split` line
  commented out and the old split put back with single quotes”. A row pins it.
- r12 4 (P3). **Fixed 2026-10-21** (user request): a row pins the guard comment above `paras = re.split` in
  `spec_lists_checks`. With its second sentence deleted, the c9d46ec script passes and the new script fails.
- Limit of this design (not a finding): a row cannot pin its own definition in `WORDING_FIXES` (a pin in the table
  would match its own text), so changing a row back (for example the r10 1 regex back to a string, or `MAIN_TAIL`
  back to all of `main()`) is not caught.

### Review of the r11/r12 fix (commit 8d0597f; Opus 0 blocking, Codex 3)

Rule used for severity (as in the af78411 review): an item is blocking when one common edit removes a fix while
every check stays green; when a false pass needs two edits, or the edit adds code where a guard does not reach,
it is P2/P3.
- Codex P1 (Opus: P2), fixed in the fix round: the r11 3 rows pinned `if RUN["compared"]:` but not its FAIL
  append; with the append replaced by `pass` (or by a bare `return`, plus a late check), all checks passed. A row
  now pins the append.
- Codex P1 (Opus: P2), fixed in the fix round: the sample-test rows pinned the condition but not the action; with
  the `problems.append` replaced by `pass`, all checks passed (also with a whole-line remover put back). Rows now pin
  the `problems.append` line and the line that makes the sample (with `sample = CODE_SAMPLE_TEXT`, the sample test
  was also off).
- Found in the fix round (not raised by a reviewer; present since af78411): with `ran = checked`, the comparison
  in `main()` was off in one edit. A row now pins `ran = [r[1] for r in results]`.
- For each of these six runs (`wrap_pass`, `wrap_noappend_late`, `sample_pass`, `iso2_sample_pass_wholeline`,
  `sample_const` and `ran_is_checked`) the 8d0597f script passes and the fixed script fails.
- Codex P1, reclassified P2 (Opus: P2): see r13 1. It does not remove a fix; it adds a check where the r11 3 guard
  does not reach, which is the class of r11 3 itself (P3). The committed tree is correct.

Not fixed (non-blocking):
- r13 1 (P2). **Fixed 2026-10-21** (user request): the r11 3 flag missed a late check in three places. Now `main()`
  sets `RUN["compared"]` on the line above `ran = …`, and sets `RUN["summary"]` on the line above `failed = 0`
  (my choice of place: the user asked for “after the summary”, and from that line on a result is not counted, so
  the gap between the summary loop and the count is covered too). A check that runs after the summary flag prints
  its FAIL and exits 1. Runs (bc7b1fa script → new script): a check between the comparison and the old flag line,
  18/0 → 18/1; a check between the summary loop and the count, 18/0 exit 0 → FAIL and exit 1; a check after the
  count, 17/0 exit 0 → FAIL printed after the count and exit 1. Rows pin the order `RUN["compared"] = True` →
  `ran = …` → `if ran != checked:`, the summary flag inside `MAIN_TAIL`, and the print and `sys.exit(1)` in
  `check()`; the flag moved into the `if` block or back below the comparison, the summary flag deleted or moved
  below `failed = 0`, and the exit branch replaced by `pass` or without `sys.exit(1)` each fail. SPEC §7.1 item 16
  now says this. Limit: a result added to `results` by hand, not through a check, is not covered.
- r13 2 (P3). **Fixed 2026-10-21** (user request): the r11 2 entry has its limit sentence back (“Code pins accept
  dead code and other spellings”), with the six spellings and `if False:`. A row pins it; the bc7b1fa README fails.
- r13 3 (P3). **Fixed 2026-10-21** (user request): the r11/r12 §9 paragraph now names `part = code_text(part)` and
  `if sample != CODE_SAMPLE_TEXT:`. Two rows pin them; the bc7b1fa SPEC fails both.

### Re-review of the 8d0597f fix round (commit 2740bb2; Opus and Codex: 0 blocking)

Not fixed (non-blocking, from the Opus re-review; Codex found nothing):
- r14 1 (P3). **Fixed 2026-10-21** (user request): the limit sentence under r11 2 now covers every code pin (a
  pinned line that does not run, or that a line added after it undoes, still counts). A row pins “This holds for
  every code pin”; the 7d6b9ee README fails it. The same rewrite corrects the `if False:` example (r15 1).
- r14 2 (P2/P3). Recorded as a limit, no code change: the r14 1 sentence names a line added after a pinned line that
  undoes it (`sample = CODE_SAMPLE_TEXT`, `problems = []`); each case needs two edits. (`ran = checked` added after
  the `ran` line now fails the r13 1 order row.)
- r14 3 (P2). **Fixed 2026-10-21** (user request): a row on `(?m)^CODE_SAMPLE = .*$` wants
  `x = 1 # a trailing comment` (after whitespace normalization). With a sample that holds no comment, the 7d6b9ee
  script passes and the new script fails, also with a whole-line remover put back. Limit (README r17 4): the row
  reads the source text, so `.replace('  # a trailing comment', '')` added to that line still passes (the “code in
  a string” class).
- r14 4 (P3). **Fixed 2026-10-21** (user request): the r12 3 locator is anchored on the words of the af78411 bullet
  (“in a code row, a pinned phrase inside a comment”). My addition: a row whose locator matches more than one part
  of its file now fails (“has N parts that match”), and a row pins that test. With the old locator, the new script
  fails (3 parts); with the af78411 bullet moved below the later records, the 7d6b9ee script fails (it binds a
  later bullet) and the new script passes.
- r14 5 (P3). **Fixed 2026-10-21** (user request): the 8d0597f §9 paragraph says that the author found the `ran`
  row in the fix round (no reviewer raised it). A row pins it; the 7d6b9ee SPEC fails it.
- r14 6 (P3). **Fixed 2026-10-21** (user request): the 8d0597f record says “these six runs” and names them. A row
  pins it and bans “these four edits”; the 7d6b9ee README fails it.

### Review of the r13 fix (commit 5989f8b; Opus 2 blocking, Codex 0)

- Opus B1 (P1), fixed in the fix round: with `RUN["summary"] = True` indented one level, it sat in the
  `if ran != checked:` block and was never set; a late check then passed (17/0 or 18/0, exit 0), and every check
  stayed green, because the row looked for the line anywhere in `MAIN_TAIL`. The row now wants the line with its
  indent, on the line above `failed = 0`.
- Opus B2 (P1), fixed in the fix round: with the `compared` test moved above the `summary` test in `check()`, the
  `compared` branch caught a late check first and the run exited 0. The `check()` row now wants the summary test
  followed by `if RUN["compared"]:`.
- For each of these edits (the Opus copies, alone and with a check after the count or between the summary loop and
  the count) the 5989f8b script passes and the fixed script fails.
- r15 2 (P3), closed by the B1 row: the summary flag moved above `RUN["compared"] = True` passed (stricter, not a
  false pass), but SPEC §7.1 item 16 (“the line above `failed = 0`”) no longer matched. The B1 row now fails it.

Not fixed (non-blocking, from the Opus review; Codex found nothing):
- r15 1 (P3), closed by the r14 1 rewrite: the r13 2 limit sentence under r11 2 named “dead code (a block under
  `if False:`)”, but the r10 1 ban is a text regex: the old split under `if False:` still fails it. The sentence now
  says that a pinned line under `if False:` still counts, and that the old split under `if False:` fails the ban.

### Re-review of the r13 fix round (commit 5a8ade4; Opus and Codex: 0 blocking)

Not fixed (non-blocking, from the Opus re-review; Codex found nothing):
- r16 1 (P3). **Fixed 2026-10-21** (user request): the B2 row's locator keeps the indent (from the
  `if RUN["summary"]:` line through `sys.exit(1)` to `if RUN["compared"]:` one level up), so the `compared` block
  indented under the summary test no longer matches. With that block indented, the old script passes (17/0; with a
  check after the comparison, 18/0) and the new script fails.
- r16 2 (P3). **Fixed 2026-10-21** (user request, as r15 2): r15 2 now sits with B1 and B2 in the record of 5989f8b,
  not in its “Not fixed” list. Two rows want it there and ban it from that list; the old README fails both.
- r16 3 (P3). **Fixed 2026-10-21** (user request): the comment above the r13 1 order row now says only that the
  run-order flag is on the line above the comparison. A row pins it and bans the old clause.
- r16 4 (information): no change. The B1 and B2 rows read raw text, so a trailing comment on a pinned line other
  than the print line, or a blank line there, fails them (a visible false FAIL, not a false pass). A trailing comment
  on the print line of the B2 part passes: `print\(.*\n` matches it, and `code_text` removes the comment.

### Review of the r14 fix (commit bca6f20; Opus and Codex: 0 blocking)

Not fixed (non-blocking):
- r17 1 (P2). **Fixed 2026-10-21** (user request): a row on `(?m)^    for f in later:$` wants that line, so the
  one-part rule (my r14 4 addition, which this fix depends on) fails a second start of `MAIN_TAIL`. With the Codex
  copy (a second `for f in later:` loop with `assert callable(f)` above the first), the old script passes and the
  new script fails (2 parts).
- r17 2 (P2). **Fixed 2026-10-21** (user request): a row wants the two adjacent lines
  `found = list(re.finditer(where, read(os.path.join(ROOT, rel))))` and `if not found:`. With `[:1]` added, or with
  `re.search` put back, the old script passes and the new script fails.
- r17 3 (P3). **Fixed 2026-10-21** (user request): the limit sentence under r11 2 now gives
  `sample = CODE_SAMPLE_TEXT` as the example; the r14 2 entry no longer lists `ran = checked` as an example and notes
  that it now fails the r13 1 order row. A row wants the new example and bans the old one; the old README fails it.
- r17 4 (P3). **Fixed 2026-10-21** (user request): the r14 3 entry has a limit sentence (the row reads the source
  text). A row pins it; the old README fails it.
- r17 5 (outside the bca6f20 diff; since 84c2ffd). **Fixed 2026-10-21** (user request), not with pins: the user asked
  for pins on the “lacks” line and the `return` line, but a pin cannot guard them. Every row reports through those
  lines, so with either line broken no pin can report, and no test copy can fail. My choice instead: `main()` runs
  `backlog_wording` on two built-in rows (`WORDING_SELF_TEST`) and fails it unless they give a “lacks”, a “still
  says” and a “still matches” problem; a row pins that call. With the “lacks”, “still says” or “still matches” line
  replaced by `pass`, or the return line changed to `return None`, the old script passes and the new script fails.
  Limit: an edit to the self-test call together with an edit to the “lacks” line or the return line (two edits)
  still passes.

### Review of the r15 2 / r16 fix (commit 59d7bf6; Opus and Codex: 0 blocking)

Not fixed (non-blocking, from the Opus review; Codex found nothing):
- r18 1 (P3). **Fixed 2026-10-22** (user request): the r16 4 sentence now names the print line as the exception. A
  row pins “a trailing comment on a pinned line other than the print line”; the old README fails it.
- r18 2 (P3). **Fixed 2026-10-22** (user request): the B2 (r16 1) locator now starts with the lookbehind
  `(?<=^        def run\(\*a, \*\*k\):\n)`, so the four lines count only right below `def run`. With the nest edit
  and a copy of the four lines in a module string (the Opus copy), the old script passes and the new script fails.
- r18 3 (P3). Closed by the r18 2 lookbehind: with `if RUN["compared"]: return` added above the summary test and
  a late check (the Opus copy), the old script passes and the new script fails.
- r18 4 (P3). **Fixed 2026-10-22** (user request): the r16 3 ban is now “summary flag is in MAIN_TAIL”. With the
  added comment line “The summary flag is in MAIN_TAIL (above failed = 0).” (the Opus copy), the old script passes
  and the new script fails.

### Review of the r17 fix (commit 49681a8; Opus 1 blocking, Codex 1 blocking)

- r19 1: Codex P1 and Opus B1 (P1), fixed in the fix round. The new `rows` parameter let one edit select fewer rows
  while every check stayed green: the default changed to `rows=WORDING_FIXES[:1]`, `rows=()` or
  `rows=WORDING_FIXES[-1:]`, or the call changed to `f(())` (17/0). The self-test passes its own rows, so it never
  reached those lines. I first rated the Codex item P2, because `[:1]` on the loop line also passed on 6a8cc16. The
  Opus evidence shows that the call `f(())` is new in this diff (6a8cc16 raised a TypeError), so it is blocking.
  Fix: `backlog_wording` counts the rows that its loop goes through (`WORDING_RUN["rows"]`), and `main()` fails it
  when the normal call went through fewer rows than `WORDING_FIXES` holds (the check runs before the self-test
  call). Two rows pin the counter and the check. For each of the four edits the 49681a8 script passes and the
  fixed script fails.

Not fixed (non-blocking, from the Opus review):
- r19 2 (P2). **Fixed 2026-10-22** (user request): the r17 1 locator is `(?m)^    for f in later:` (no `$`, as in
  `MAIN_TAIL`). With `for f in later: pass`, or a second loop line with a trailing comment, added above the loop (the
  Opus copies), the old script passes and the new script fails (2 parts).
- r19 3 (P3). **Fixed 2026-10-22** (user request): the r17 5 limit sentence now says “together with an edit to the
  “lacks” line or the return line”. A row wants it and bans the old phrase; the old README fails it.
- r19 4 (P3). **Fixed 2026-10-22** (user request): the self-test call is in a try; a crash gives
  `exception: …`, which fails the test of the three words, so the run prints a FAIL line and the count. With the
  “lacks” line's format broken (the Opus copy), the old script stops with a traceback before any result line, and
  the new script prints every result and the FAIL line. A row pins the try and the call right above the test.
- r19 5 (P3). **Fixed 2026-10-22** (user request): the r17 3 entry now says that the r14 2 entry no longer lists
  `ran = checked` as an example and notes that it now fails the r13 1 order row, which is what r14 2 says. A row
  pins the r17 3 wording (want and ban); the old README fails it. A row pins the r14 2 example list; the old README
  already passes it, and `ran = checked` put back into the list fails it.

### Re-review of the r17 fix round (commit afca992; Opus 1 blocking, Codex 0 blocking)

- r20 1: Opus B1 (P1, introduced by the fix round), fixed in the third round. With the three lines of the count test
  indented one level, into the `if ran != checked:` block, the test ran only when the run-order comparison had
  failed. The r19 1 row looks for the text anywhere in `MAIN_TAIL`, so every check stayed green (17/0), also
  together with `rows=WORDING_FIXES[:1]`. This is the 5989f8b B1 case again. Fix: a row on
  `(?m)^    if WORDING_RUN\["rows"\] != len\(WORDING_FIXES\):\n` followed by the FAIL line at 8 spaces. With the
  re-indent, the afca992 script passes and the new script fails. Limit: the re-indent together with an edit that
  selects fewer rows (two edits, for example `rows=WORDING_FIXES[:1]`) still passes (17/0), because the r20 1 row
  is then one of the rows that do not run. This was the last round the stop rule allows for this review.

Not fixed (non-blocking, from the Opus re-review):
- r20 2 (P2). **Fixed 2026-10-22** (user request): a row wants the self-test (`try:`, the call, the `except` line
  and the fallback) at the indent of `main()`'s body, right above `if not all(w in got`. With the self-test lines
  indented one level, into the count test (the Opus copy), the f3b0bd6 script passes and the new script fails.
- r20 3 (P3). **Recorded as a limit** (user choice, 2026-10-22): a `continue` added after the counter skips rows
  while the count stays at the table length (a line added). The counter counts entries into the loop body, not rows
  that reach the `want` test.
- r20 4 (P3). **Recorded as a limit** (user choice, 2026-10-22): `rows=WORDING_FIXES[:1] * len(WORDING_FIXES)`
  passes, because the test compares the count, not which rows ran (not a common edit).
- r20 5 (P3). **Recorded as a limit** (user choice, 2026-10-22): `WORDING_FIXES = WORDING_FIXES[:1]` above the
  `def` passes (a row's own definition). The same line after the `def` fails.
- r20 6 (P3). **Fixed 2026-10-22** (user request): SPEC item 17 and the 49681a8 §9 paragraph now say “went through
  fewer or more rows than `WORDING_FIXES` holds”. Two rows want it and ban the old phrase; the f3b0bd6 SPEC fails
  both.

### Re-review of the third round (commit 3d87fa2; Opus and Codex: 0 blocking)

Not fixed (non-blocking, from the Opus re-review; Codex found nothing):
- r21 1 (P3). **Fixed 2026-10-22** (user request): SPEC item 17 names r20 1 (and the rows this batch adds).
- r21 2 (P3). **Recorded as a limit** (dead code, user choice 2026-10-22): with `if False else None` added to the
  end of the FAIL line of the count test, the append is dead code and every check stays green.
- r21 3 (information): no change. The r20 1 row reads raw text, so a trailing comment on the `if` line, or a
  comment line below it, fails the row while the test still runs (a visible false FAIL, not a false pass).


### Review of the backlog batch (`git diff f3b0bd6 01ef29c`, commits 12cd7fb to 01ef29c; Opus 2 blocking, Codex 2 blocking)

Fixed in the fix round (the same two items from both reviewers):
- B1 (Opus B1, Codex P1; new in e544067): the autoplay check was flaky. Its init script listened for
  `loadedmetadata` only after `DOMContentLoaded`, and the metadata sometimes came first; the check then saw “no
  result” on a correct page (Opus: 1 of 3 full runs, 2 of 10 probe runs). Now the script tries at once when
  `readyState >= 1` and waits for `loadedmetadata` only otherwise. With `site.js` held for 3 s (so `DOMContentLoaded`
  comes after the metadata), the 01ef29c check fails 5 of 5 times (“no result”) and the new one passes 5 of 5
  (`NotAllowedError`); with the old flag the new one fails 5 of 5 (“played”). The full suite then gave 68/0 in 5 of 5
  runs (2 at a time).
- B2 (Opus B2, Codex P1; new in 12cd7fb): no row held the r21 1 fix (SPEC item 17 names r20 1). A row now wants
  “r20 1, r20 2, r20 6, r21 1” in item 17; with “r20 1, ” removed, the 01ef29c script passes and the new one fails.

Non-blocking (not fixed in that round; later fixes are marked):
- r22 1 (P2, Opus; the gap predates, the B4 check inherits it). **Fixed 2026-10-22** (user request): `resolve_local`
  now resolves `..` in a root-relative reference (`normpath`). With `url("/../README.md")` in `site.css`, in a tree
  where `docs/../README.md` exists, the 9a09b96 script passes and the script with only this fix fails `local_refs`
  (“does not resolve to a file in docs/”). With r22 2 in, that reference fails as root-relative first, so a row pins
  the `normpath` line; with the line put back as it was, the script fails r22 1.
- r22 2 (P3, Opus; predates). **Fixed 2026-10-22** (user request): `local_refs` fails every local reference whose path
  starts with `/` (HTML attributes, `srcset`, `style` attributes, `<style>` blocks and `.css` files). With `<a
  href="/index.html#film">` in `index.html`, or `url("/assets/img/poster.jpg")` in `site.css`, the 9a09b96 script
  passes and the new one fails. Limit: a URL that `site.js` builds is not covered; the browser suite serves `docs/` at
  `/` and cannot see it either.
- r22 3 (P2, Opus and Codex P3). **Fixed 2026-10-22** (user request): the r4 A1 entry names the two sizes that fail
  and says why 375×667 passes. A row pins it; with the old entry, the script fails r22 3.
- r22 4 (P2, Opus). **Fixed 2026-10-22** (user request): the click test needs `muted` false and `volume` above 0. With
  `video.muted = true` in `start()` in `site.js`, the 9a09b96 suite passes and the new one fails at 1440×900 and
  390×844.
- r22 5 (P2 Codex, P3 Opus). **Fixed 2026-10-22** (user request): at the missing path only the page's own “status of
  404” error at the page URL is exempt; at `/404.html` nothing is. Both 404 runs listen for `pageerror`. With
  `<script>console.error(…)</script>` or `<script>throw new Error(…)</script>` in `404.html`, the 9a09b96 suite passes
  and the new one fails at both paths.
- r22 6 (P3, Opus). **Fixed 2026-10-22** (user request): `fonts_licensed` reads every `.css` file in `docs/` and the
  `<style>` blocks of both pages. With a Plex `@font-face` in a `<style>` block of `index.html` or of `404.html`, the
  9a09b96 script passes and the new one fails.
- r22 7 (information, Opus). **Fixed 2026-10-22** (user request): the test of this item found a real fault. With the
  first film request held for 12 s (a slow machine), the 9a09b96 check failed 3 of 3 times with “played”, not “no
  result”: `page.waitForFunction()` runs through `page.evaluate()`, which Chrome counts as a user gesture, so when the
  metadata came after the wait started, the `play()` with sound was allowed. The init script now logs the result to
  the console, and the check waits up to 30 s for that message without any call into the page; only then does it read
  `readyState` and `networkState` for the detail. With the hold, the new check passes 3 of 3; with the old flag it
  fails 3 of 3 (“played”); without the hold it passes 3 of 3, and with the flag and no hold it fails 3 of 3.

Re-review of the fix round (3b027a2; Opus 0 blocking, Codex 0 blocking). Both reproduced the B1 and B2 runs; Opus also
found that both paths of the B1 fix run (`readyState` 4 or 0 at `DOMContentLoaded`) and that an aborted film request
gives a visible FAIL, not a false pass. The review is closed.
- r23 1 (P3, Opus; predates 3b027a2). **Fixed 2026-10-22** (user request): a row wants the whole item 17 list, first
  name to last. With “r18 1, ” or “N5, ” removed from it, the 9a09b96 script passes and the new one fails r23 1.
  Limit: a reorder of the list gives a false FAIL.
- r23 2 (P3, Opus; from 3b027a2): the heading of this record said “12cd7fb..01ef29c”, which in git leaves out 12cd7fb.
  Fixed in the record commit: the heading names `git diff f3b0bd6 01ef29c`.

### Review of the r22 1–7 and r23 1 fixes (7576da9; Opus 0 blocking, Codex 0 blocking)

Both reviewers ran the static suite on Python 3.9.6 and 3.15.0 and on CRLF copies (17/0). Opus also ran it on
3.12–3.14, ran the browser suite (68/0), and reproduced every fail-before with its own copies. For r22 7 it held the
film request in the test server, not with a Playwright route, and logged `navigator.userActivation` before the
`play()`: the 9a09b96 check had the page active at the attempt (“played” 3 of 3), the 7576da9 check did not
(`NotAllowedError` 3 of 3, also with a 25 s hold). The review is closed. Non-blocking items:
- r24 1 (P3, Opus; predates; “other spellings”). **Fixed 2026-10-22** (user request): `local_refs` fails a local
  reference whose path holds `%2F` or `%5C` (any case), in HTML and in CSS; a plain slash is the only spelling the
  site needs. With `href="%2Findex.html"`, `href="assets%2Fimg%2Fposter.jpg"` or
  `url("%2Fassets%2Fimg%2Fposter.jpg")`, the 14ff0aa script passes and the new one fails. Reason, corrected under r25
  1 (measured by Opus on a GitHub Pages project site): Pages decodes `%2F` and serves the file, and gives 404 for
  `%5C`; a `%2F` path stays below the folder of the file that refers to it. So the two `href` cases would work on
  Pages, but the CSS case breaks there (it resolves under `assets/css/`), and the 14ff0aa script passed it because it
  read the leading `%2F` as the `docs/` root. The test server decodes the path as Pages does. Since this ban comes
  first, a `%2F..%2F` reference no longer reaches the `normpath` line of r22 1; the r22 1 row is now that line's only
  guard.
- r24 2 (P3, Opus; predates; “other spellings”). **Fixed 2026-10-22** (user request): the `@font-face` test takes
  `re.I`. With `@FONT-FACE{FONT-FAMILY:"IBM Plex Sans";…}` in a `<style>` block of `index.html`, the 14ff0aa script
  passes and the new one fails.
- r24 3 (P3, Opus). **Fixed 2026-10-22** (user request): at the missing path only Chrome's own message for the page
  (“Failed to load resource: the server responded with a status of 404”) is exempt, and only once; a response ≥ 400 at
  the page URL fails unless it is the navigation itself. Two copies of `404.html` run a script only away from
  `/404.html` (at `/404.html` the 14ff0aa suite already fails any console error, so the copies would not show the old
  gap there): one logs that exact message, one calls `fetch(location.href)`. The 14ff0aa suite passes both copies at
  both paths. The new one fails both at the missing path: the logged message as a second exempt message, the fetch
  both as a second message and as a response ≥ 400 that is not the page itself.
- r24 4 (P3, Opus; predates; comment only). **Fixed 2026-10-22** (user request): a probe measured it. A `play()` with
  sound from a timer 2 s after load is refused (`NotAllowedError`, 2 of 2) when the test makes no call into the page,
  and runs (“played”, 2 of 2) after one `page.evaluate()`, which also sets `navigator.userActivation.hasBeenActive`.
  The comment on the click test now says that the earlier `page.evaluate()` calls already give the page a lasting user
  gesture, so the test does not show that the click alone allows the play, and that `runAutoplayPolicy` checks the
  policy. A row pins it; with the 14ff0aa comment, the script fails r24 4.

### Review of the r24 1–4 fixes (3dc2c4a; Opus 0 blocking, Codex 0 blocking)

Codex ran the static suite on Python 3.9 and 3.13–3.15 and on CRLF copies (17/0) and read the browser suite. Opus ran
the static suite on 3.9.6 and 3.13–3.15 with LF and CRLF, the browser suite (68/0), every fail-before with its own
copies, and its own r24 4 probe: with an 8 s timer the page still had sticky activation after one `page.evaluate()`
(“played” 2 of 2) and none without it (`NotAllowedError`), so the r24 4 comment holds. The review is closed.
Non-blocking items:
- r25 1 (P2, Opus; from 3dc2c4a). **Fixed 2026-10-22** (user choice: reword, keep the ban). The r24 1 reason was wrong
  for `%2F`. Opus measured a GitHub Pages project site (google.github.io/styleguide) with curl and Chrome 155: Pages
  decodes `%2F` and serves the file (`assets%2Fcss%2Fstyle.css` and `%2Fpyguide.html` give 200 with the same SHA-256
  as the plain paths), returns 404 for `%5C`, and resolves a decoded leading `/` below a subfolder against that
  folder. So `href="%2Findex.html"` and `href="assets%2Fimg%2Fposter.jpg"` in `docs/index.html` would work on Pages,
  and the test server, which decodes the path the same way, sees what Pages sees. The case the ban really closes is
  `url("%2Fassets%2Fimg%2Fposter.jpg")` in `site.css`: on Pages it resolves under `assets/css/` and breaks, while the
  14ff0aa script unquoted first and read the leading `/` as `docs/`. The comment in `local_refs` and the r24 1 entry
  now state these facts, and the ban stays, since a plain slash is the only spelling the site needs. Rows pin both;
  with the f1396e8 comment or entry, the script fails r25 1.
- r25 2 (P2, Opus; the same pattern as r22 2, r22 5 and r22 6): no committed check holds the r24 1–3 code; removing
  `re.I`, either ban, or the 404 changes leaves both suites green on the committed `docs/`. As before, the fixes are
  held by the test copies, and rows pin only lines that a copy cannot reach (r10 2, r11 3, r22 1). Fix if wanted: one
  row per fix (the HTML and CSS ban lines are the same text after `code_text`, so the row needs a part that holds one).
  **Fixed 2026-10-23** (user request: close every open item): rows pin the CSS ban line and its append, the `@font-face`
  line with `re.I`, and in `browser_check.mjs` the `expected` filter and the response filter; the r27 1 row already
  holds the HTML ban line. With `re.I` removed from the CSS ban or from the `@font-face` line, `exempted++ === 0`
  replaced by `true`, or the response filter turned off, the 3bc40be script passes and the new one fails r25 2. Limit: a
  part of a `.mjs` file is raw text, so a commented-out line there still holds a pin.
- r25 3 (P3, Opus; from 3dc2c4a): the response filter exempts every navigation at the page URL, also an iframe that
  loads it; the comment says “not the page itself”. No false pass was found (the once-only console rule still fails the
  iframe). Fix: add `r.frame() === p2.mainFrame()`, or say “a navigation”. **Fixed 2026-10-23** (user request): the
  response filter exempts a 404 at the page URL only for a navigation in the main frame (`r.frame() ===
  p2.mainFrame()`), and its comment says so; a row pins the line. With the 3bc40be filter line, the new script fails r25
  2, r25 3. Measured with a copy of `404.html` that, away from `/404.html`, adds an iframe loading the page URL: the
  3bc40be suite fails it only through the console rule (`bad` is empty), the new one also lists the iframe's 404 in
  `bad`.
- r25 4 (P3, Opus; from 3dc2c4a): the exemption matches Chrome's exact wording, measured on Chrome 155.0.8059.85
  (“Failed to load resource: the server responded with a status of 404 (Not Found)”, once, at the page URL). Other
  wording gives a visible FAIL, not a false pass. Fix: record the Chrome version next to the regex. **Fixed 2026-10-23**
  (user request): the comment next to the regex names Chrome 155.0.8059.85 (r24 3) and Chrome 156.0.8078.47 (measured
  2026-10-23 with `browser.version()`; the suite passes on it). A row pins it.

### Review of the r25 1 fix (134f246; Opus 0 blocking, Codex 0 blocking)

Codex ran the static suite and the r25 1 copies on Python 3.9–3.15 with LF and CRLF. Opus ran them on 3.9.6 and
3.12–3.15 with LF and CRLF (75 runs, all as expected), checked that the comment row finds one part made of comment
lines, re-checked the Pages facts with read-only requests, and replayed the test server's path handling (same results
as Pages for the `href` and CSS cases and for `%5C`). The review is closed. Non-blocking items:
- r26 1 (P3, Opus; from 134f246; recorded limit “a line added after it undoes it”). **Fixed 2026-10-23** (user
  request): the r25 1 comment row bans `re.compile(r"breaks the link on Pages|cannot see this")`. With the line `#
  (the test server decodes it, so the browser suite cannot see this)` added to the comment, the 416a91b script passes
  and the new one fails r25 1 (“still matches”).
- r26 2 (P3, Opus; from 134f246). **Fixed 2026-10-23** (user request): the comment says that `url("%2Fassets/...")` in
  a `.css` file “would pass here and break on Pages”. A row pins it; with the 416a91b comment, the script fails r26 2.

### Review of the r26 1–2 fixes (526e0ff; Opus 0 blocking, Codex 0 blocking)

Codex and Opus each ran the six test runs on Python 3.9–3.15 with LF and CRLF (84 runs each, all as expected). Opus
also checked that the regex ban and a string ban test the same normalized text, that the shared locator finds one
part, and ran 18 changed copies: every false pass is in a recorded limit. The review is closed. Non-blocking items:
- r27 1 (P3, Opus; the locator dates from 134f246; recorded limit “a line added that undoes a pinned one”). **Fixed
  2026-10-23** (user request; new rule): a second row holds the `if` line of the HTML encoded-slash ban and the line
  after it, with the same regex ban. As a plain ban that row could not fail: the comment remover takes every comment out
  of a part that holds code before the test, so with the claim as a trailing comment on the `if` line it passes. New
  rule (SPEC item 17): a ban marked `AlsoInComments` is also tested on the part as written, with its comments, and a ban
  of another kind is a FAIL. Three rows pin the new code in `backlog_wording`. Not used: a rule that every ban reads
  comments, since the `spec_lists_checks` comment quotes the r10 1 ban on purpose (the af78411 guard). The row's fixed
  phrase is the `if` line and the start of its `problems.append`, so it also holds the HTML ban line, one of the r25 2
  lines (r25 2 stays open for the rest). With the claim as a trailing comment on the `if` line or on the line after it,
  the 2b0af82 script passes and the new one fails r27 1 (“still matches”); with it as a comment line between the `if`
  line and the `problems.append` line, the new one fails r27 1 (“no part”). With the two unwrap lines deleted, the row
  fails (“a ban of unknown kind”). Limits (README r28 2): the claim still passes as a 16-space comment line above the
  comment block, as a comment line after the `problems.append` line, as a trailing comment on `continue`, or as a
  12-space comment line after `continue`; a blank line inside the block still shrinks the r25 1 part without a FAIL.
- r27 2 (P3, Opus; recorded limit “a row's own definition”). **Fixed 2026-10-23** (user request; new rule):
  `backlog_wording` compares the findings that the row labels name with the SPEC item 17 list, both ways
  (`label_problems`), and the r23 1 row that held the whole list as one phrase is gone. Four rows now name two findings,
  their own and the later one that changed them: `r16 1, r18 2`, `r16 3, r18 4`, `r17 1, r19 2` and `r25 1, r26 1` (the
  four names that had no row of their own). A row labelled `r23 1, r27 2` pins the call. With the r26 2 row deleted, or
  a row labelled `r99 1` added, the 2b0af82 script passes and the new one fails; with `r26 2` taken out of item 17, both
  fail; with two names swapped in item 17, the 2b0af82 script fails (a false FAIL, now gone) and the new one passes.
  Limit: deleting a row whose findings another row also names (for example one of the six r12 1 rows) still passes.
- r27 3 (P3, Opus; wording). **Fixed 2026-10-23** (user request): the comment says that `url("%2Fassets/...")` “in a
  .css file below the docs/ root would pass here and break on Pages”. A row pins it; with the 2b0af82 wording, the new
  script fails r27 3 (“lacks” and “still says”), and the r26 2 row still passes.

### Review of the r27 1–3 fixes (2f2ffd7; Opus 0 blocking, Codex 0 blocking)

Codex and Opus each ran the committed tree and the changed copies on Python 3.9–3.15 with LF and CRLF (Codex 48 runs,
Opus 140, all as expected), and each parsed SPEC item 17 and every row label on its own: both give the same 58 findings.
The review is closed. Non-blocking items:
- r28 1 (P2, Opus; from 2f2ffd7). **Fixed 2026-10-23** (user request): five rows pin the guard bodies: the `labels =
  set().union(` line and the `return` with both report lists in `label_problems`, the `re.fullmatch(` and `names.add("
  ".join(` lines in `finding_names`, and `self.banned = banned` in `AlsoInComments`. With `labels = listed`, the second
  list deleted, `tok` replaced by `"r0 0"` in the `re.fullmatch` call, the `names.add(" ".join(` line replaced by
  `pass`, or `self.banned = None`, the 4a9294a script passes and the new one fails r28 1. Limit (recorded “dead code”):
  `return []` as the first line of `label_problems`, or `return set()` as the first line of `finding_names`, still
  passes in both scripts.
- r28 2 (P3, Opus; from 2f2ffd7; README). **Fixed 2026-10-23** (user request): the r27 1 entry says “between the `if`
  line and the `problems.append` line”, and its limits name the three positions after the append. Measured on the new
  script: the claim as a comment line after the append, as a trailing comment on `continue`, or as a 12-space comment
  line after `continue` gives 17/0. A row pins the entry; with the 4a9294a entry, the new script fails r28 2.
- r28 3 (P3, Opus; from 2f2ffd7; SPEC wording). **Fixed 2026-10-23** (user request): item 17 says “a label may name two
  findings (for example `r16 1, r18 2`)”. A row pins it; with the old sentence, the new script fails r28 3.
- r28 4 (P3, Opus; recorded limits). **Fixed 2026-10-23** (user request): the unwrap remembers the mark, and the kind
  test also rejects `AlsoInComments(None)` (FAIL “a ban of unknown kind AlsoInComments(None)”). SPEC item 17 now says
  “`AlsoInComments` (of a string or a regex)”. The two r27 1 pin rows on these lines are now labelled `r27 1, r28 4`.
  With the r27 1 ban as `AlsoInComments(None)`, alone or with the claim as a trailing comment on the `if` line, the
  4a9294a script passes and the new one fails. Deleting the r27 1 row, or unwrapping it to a plain regex, still passes
  (recorded limit “a row's own definition”).
- r28 5 (P3, Opus; information). **Closed 2026-10-23, no change** (user request named it; the finding asks for none):
  the parser edges give a visible FAIL, not a false pass.

### Review of the r28 1–5 fixes (12d3a9a; Opus 0 blocking, Codex 0 blocking)

Codex and Opus each ran the committed tree on Python 3.9–3.15 with LF and CRLF (all 17/0) and reproduced every changed
copy; Codex found that the 9 locators with an r28 label each match once, and Opus that the new kind test rejects every
kind the old one did (about 90 runs). The review is closed. Non-blocking items:
- r29 1 (P2, Opus; left over from r28 1): one edit in `finding_names` that is not dead code still turns the r27 2 guard
  off with every check green: `return set()` in place of `return names`, `for tok in ():`, or `for n in range(0):`
  (17/0; with `r28 3` also taken out of item 17, still 17/0). The README r28 1 limit names only `return set()` as the
  first line, so it says less is open than is. Fix if wanted: a self-test of `finding_names` on a fixed list in
  `main()`, or a pin on `return names` with the loop lines recorded as a limit. **Fixed 2026-10-23** (user request:
  close every open item): `backlog_wording` checks `finding_names` on a built-in sample (`NAMES_SAMPLE`: a bare number
  after a round, a range, a letter name with and without a round, “and”, and a token that is not a name), next to the
  comment-remover sample, so `return []` at the top of `label_problems` does not switch it off; a row pins the test.
  With `return set()` in place of `return names` or as the first line, `for tok in ():` or `for n in range(0):`, the
  3bc40be script passes and the new one fails (“finding_names gives … for its sample”). This also closes the r28 1
  dead-code case for `finding_names`; `return []` at the top of `label_problems` stays in that limit.
- r29 2 (P3, Opus; predates): a fixed phrase only has to be in the text, so code added at the end of a pinned line
  passes (`labels = set().union(...) | listed` with an unlisted label; `self.banned = banned if 0 else
  re.compile("(?!)")` with the claim as a trailing comment). Both edits are deliberate. **Closed 2026-10-23 as a
  recorded limit** (user request: close every open item): a fixed phrase is a substring of the normalized text, so the
  end of a line is not visible to it; changing that would reopen the settled pin genre. The r11 2 limit now names this
  case; a row pins it.
- r29 3 (P3, Opus; predates): no row pins the line that reports a ban of unknown kind; replaced by `pass` it gives 17/0.
  Fix if wanted: a `WORDING_SELF_TEST` row with a bad kind, and “unknown kind” among the problems `main()` expects.
  **Fixed 2026-10-23** (user request): a third `WORDING_SELF_TEST` row has the ban `AlsoInComments(None)`, and `main()`
  fails `backlog_wording` unless the self-test rows also give “unknown kind” (the r17 5 row now has the label `r17 5,
  r29 3`). With the report line replaced by `pass`, the 3bc40be script passes and the new one fails (“not the four
  problems”, and the r29 5 row).
- r29 4 (P3, Opus; predates): `names.add(tok)` has no row; deleted, with an ASCII-hyphen range added to item 17, it
  gives 17/0. The r29 1 self-test would cover it. **Fixed 2026-10-23** (user request): the r29 1 sample holds a token
  that is not a name (`x 1-2`). With `names.add(tok)` deleted, the 3bc40be script passes and the new one fails.
- r29 5 (P3, Opus; from 12d3a9a; cosmetic): with the `if marked:` block deleted, the message wraps the ban twice
  (`AlsoInComments(AlsoInComments(...))`); the check still fails, and the pin reports “lacks”. **Fixed 2026-10-23**
  (user request): the message shows the ban as the row gives it (`shown`); two rows pin the lines. With the `if marked:`
  block deleted, the 3bc40be message is `AlsoInComments(AlsoInComments(re.compile(…)))` and the new one
  `AlsoInComments(re.compile(…))`.
- r29 6 (P3, Opus; wording; a cross-reference of r28 3): the README r27 2 entry still says “A label names two findings
  when a later fix changed that row”. **Fixed 2026-10-23** (user request): the entry says “Four rows now name two
  findings, their own and the later one that changed them”. A row pins it; with the old sentence, the new script fails
  r29 6.
- r29 7 (P3, Opus; wording): the r28 §9 paragraph says “rows pin the bodies”, but the rows pin five lines; no row pins
  the item 17 words “(of a string or a regex)”. **Fixed 2026-10-23** (user request): the r28 paragraph says “five rows
  pin lines in”, and a row pins the item 17 words “`AlsoInComments` (of a string or a regex)”. With either old text, the
  new script fails r29 7.
- r29 8 (P3, Opus; wording): the README r28 1 entry says “the `names.add` line”, but `finding_names` has two; the run
  changed the `names.add(" ".join(` line. **Fixed 2026-10-23** (user request): the r28 1 entry names the `names.add("
  ".join(` line. A row pins it; with the old words, the new script fails r29 8.

## Image crop boxes as finally used

Frames come from the delivered film with `ffmpeg -ss <t> -i <film> -frames:v 1`. Boxes are `x0,y0,x1,y1` in the
1920×1080 frame. JPEG quality 82, progressive, sRGB, written with Pillow 13.0.0. Every output was checked by eye: no subtitle text, no cut-off
brain, no cut-off label.

| File | t (s) | Crop box | Output size | Change from SPEC v2 §3 |
|---|---|---|---|---|
| poster.jpg | 43.0 | full frame | 1920×1080 | none |
| idea.jpg | 9.0 | 60,60,1760,945 | 1400×729 | none (SPEC v2 uses y1 = 945) |
| out-dec.jpg | 22.8 | 815,155,1855,935 | 1200×900 | none |
| out-tissue.jpg | 27.0 | 725,150,1765,930 | 1200×900 | none |
| out-regions.jpg | 30.6 | 700,150,1740,930 | 1200×900 | none |
| out-surfaces.jpg | 35.4 | 665,155,1705,935 | 1200×900 | 35.4 s, not 34.8 s (README N12): the full pial mesh |
| out-tracts.jpg | 43.0 | 470,0,1910,1080 | 1200×900 | none |
| out-connectome.jpg | 50.2 | 585,140,1838,1080 | 1200×900 | none |
| slicer.jpg | 56.8 | full frame | 1920×1080 | none (SPEC v2 uses 56.8 s: cue 11 ends at 56.5 s, the fade starts at 56.9 s) |
| social.jpg | – | `cover_1280x640.png` | 1280×640 | none (PNG converted to JPEG) |

`icon-64.png` and `icon-180.png` are resized from `Resources/Icons/SlicerDDSurfer.png` of the repository.
