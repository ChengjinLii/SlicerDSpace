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
- Note (outside this diff): with the CSS rule `.film-play[hidden]{display:none}` removed, the play button stays
  drawn over the playing film, and `startProof()` still passes, because it reads the `hidden` attribute. The proof
  shows that the start handler ran; it does not check the CSS.

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
  `re.split` line, the c9d46ec script passes and the new script fails.
  Limit (README r13 2, r14 1): Code pins accept dead code and other spellings. This holds for every code pin in
  `WORDING_FIXES`, not only this ban. A pinned line still counts when it does not run (under `if False:`, or below a
  `return` moved above it) and when a line added after it undoes it (for example `ran = checked`). A ban misses
  other spellings of the old code: six other spellings of the old split pass, for example `.split( "\n\n" )` or
  `.split(sep="\n\n")`; the old split under `if False:` still fails the ban, because a ban reads text.
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
  undoes it (`ran = checked`, `sample = CODE_SAMPLE_TEXT`, `problems = []`); each case needs two edits.
- r14 3 (P2). **Fixed 2026-10-21** (user request): a row on `(?m)^CODE_SAMPLE = .*$` wants
  `x = 1 # a trailing comment` (after whitespace normalization). With a sample that holds no comment, the 7d6b9ee
  script passes and the new script fails, also with a whole-line remover put back.
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

Not fixed (non-blocking, from the Opus review; Codex found nothing):
- r15 1 (P3), closed by the r14 1 rewrite: the r13 2 limit sentence under r11 2 named “dead code (a block under
  `if False:`)”, but the r10 1 ban is a text regex: the old split under `if False:` still fails it. The sentence now
  says that a pinned line under `if False:` still counts, and that the old split under `if False:` fails the ban.
- r15 2 (P3), closed by the B1 row: the summary flag moved above `RUN["compared"] = True` passed (stricter, not a
  false pass), but SPEC §7.1 item 16 (“the line above `failed = 0`”) no longer matched. The B1 row now fails it.

### Re-review of the r13 fix round (commit 5a8ade4; Opus and Codex: 0 blocking)

Not fixed (non-blocking, from the Opus re-review; Codex found nothing):
- r16 1 (P3, the dead-code limit; also on 5989f8b): with the `if RUN["compared"]:` block indented one level, it sits
  under the summary test, after `sys.exit(1)`, and never runs; the B2 row still matches (17/0; with a check after
  the comparison, 18/0). Fix ideas: name it under the r14 1 limit, or anchor the row on the indent, as the B1 row is.
- r16 2 (P3): r15 2 sits under “Not fixed”, but it says “closed by the B1 row”. Fix: move it, or rename the list.
- r16 3 (P3): the comment above the r13 1 order row still says “and the summary flag is in MAIN_TAIL (above
  failed = 0)”; that summary row has its own row and comment now. Fix: drop the clause.
- r16 4 (information): the B1 locator reads raw text, so a trailing comment on the flag line or a blank line
  before `failed = 0` fails it (a visible false FAIL, not a false pass).


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
