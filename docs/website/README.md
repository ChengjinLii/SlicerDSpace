<div align="center">

# Project Website

**Static public assets, separate from private software documentation**

[Project](../../README.md) | [Website](https://chengjinlii.github.io/SlicerDSpace/) | [Original Notes](UPSTREAM_README.md) | [中文](README.zh-CN.md)

</div>

---

## Source And Attribution

The website was contributed by [xiaji](https://github.com/xiaji), whose original
Git author is `x1aji <jwjwei@gmail.com>`. Its three original commits
`935a5d9`, `444d8db` and `5b09bc2` are retained as ancestors of `main` through a
normal merge, not a squash, rebase or copied replacement commit. Their author,
committer, timestamps and co-author trailers are unchanged.

Public HTML, styles, scripts, fonts, images, subtitles and the 47,838,648-byte
promo film live under `docs/site/`. Integration moves the original files without
redesigning the site or re-encoding its media. [FACTS.md](FACTS.md),
[SPEC.md](SPEC.md) and [UPSTREAM_README.md](UPSTREAM_README.md) preserve the
contributor's historical source, design and review records. They are not current
installation instructions and are not part of the public deployment.

---

## Performance Section

The home page holds the performance evidence in its `#performance` section: one
closed disclosure, "Performance evidence", after the `#runtime` figures and before
the final bibliography. A footer link navigates within the home page.
There is no separate runtime or performance page; the legacy redirect was removed.
The evidence separates equivalent
implementation changes, native threads, workflow scheduling and Python-port controls.
Each record states its reference, measurement scope, output-equivalence checks and
limitations; no whole-workflow benefit is claimed.

`python3 scripts/build_performance_site.py` exports selected benchmark records and
renders their tables into `index.html`, between the `measured-evidence` markers.
`--check` verifies source hashes and detects stale HTML/JSON. Only the curated
`assets/data/performance.json` is public. Raw runtime snapshots, private filesystem
paths, subject data and internal reports are not copied into the site. The new files
and generator are excluded from the extension runtime.

The catalogue contains 13 scoped records. The optimization figure selects ten
reusable implementation, port, inherited-upstream and I/O changes, with timings
above a matching methods table. Thread counts, device switches, scheduling and
earlier-plugin-only API integration remain outside this figure. The catalogue
was expanded on 25 October; the upstream-source audit is still dated 22 October.

---

## Site Guide

The homepage's `#skills` section and navigation introduce the project's
install-and-use Agent Skill, its usage reference, CLI recipes and two copyable
prompts: installation and analysis. The prompts are also in both root READMEs
and the manuscript's setup instructions. The Skill contains
Agent-facing operating instructions rather than user prompts. Model downloads follow the user's confirmed storage choice; an
analysis request waits for plan confirmation. Skill files stay in
the repository: links require repository access during private pre-release.
The Skill runs through the user's Agent; it is separate from the local site guide.

The floating guide reproduces the mascot, motion and dialog style of Chengjin
Bot from the local personal-site source at `d30286f`: 150 ms gaze sampling,
per-frame 0.05 smoothing, 5 px eye range, blue pulse, blinking and seasonal hat.
It uses locally curated,
bilingual project answers in `docs/site/assets/js/guide-bot.js`. It makes no
network requests, does not persist questions, and does not call an AI model. Update its
answers alongside the relevant homepage sections when product behaviour or
installation instructions change. Keyboard, drag, responsive, privacy and
no-JavaScript behaviour are checked by `node Testing/Website/guide_bot_check.mjs`.
When the outer reading gutter is too narrow, or the viewport is short, the
mascot docks in a reserved 36 px header slot instead of covering page text.
Wide screens retain the floating mascot and its last dragged position. Opening
the guide closes an expanded navigation menu; outside clicks dismiss the
non-modal desktop panel. The browser checks cover 320--1440 px windows,
scrolling, header collisions and switching between docked and floating modes.

---

## Figures, Methods And References

The integration catalogue sits immediately before References. The product map
remains; the six example combinations and standalone In Slicer section are
removed. Header/footer branding and browser icons are transparent PNG exports
of `paper-latex:docs/figures/logo-ref.svg`. Verify them with
`python3 scripts/check_website_assets.py --check`.

- The WMQL gallery tile uses `assets/img/res-wmql-ukf.jpg`, an unchanged copy of
  the official multi-query UKF render in `paper-latex:docs/figures/src/results/`. Its source
  and hash are recorded in `wmql_sources.json`. `python3 scripts/check_website_assets.py --check`
  verifies the published copy; regenerate and import artwork from the independent repository when updating it. The full lateral view fits
  inside the gallery tile without cropping. The earlier CSD/ACT AF/CST thumbnail is retired.
- `assets/img/fig-product-map.png` (section `#choose`) and
  `assets/img/fig-runtime-resources.png` and `assets/img/fig-runtime-optimizations.png`
  (two independent figures in section `#runtime`) are rasterised from the
  editable SVG sources in `paper-latex:docs/figures/`, which are not published. See
  [the independent artwork repository](https://github.com/ChengjinLii/paper-latex/blob/main/docs/figures/README.md) to rebuild them. Each `<img>` carries
  the pixel size of its file and links to the full-size file.
- The standalone "What is integrated" section (`#integrated`) lists 35 concrete
  method/utility entries, including the available denoisers, masking alternatives,
  anatomical and microstructural models, tracking, fiber bundles and regional analysis.
  Each entry identifies its implementation, runtime
  requirements. Historical run-specific orange status badges and the optional
  reference-runtime row are removed. Runtime/access requirements remain explicit,
  including the UKF reference route for WMA and Python API scalar/length summaries.
  Detailed provenance and validation records remain linked; the table does not
  certify every output or promote historical failed runs.
- `#cite` is the last main-page section and displays the complete bibliography
  [1] to [53] without a disclosure. Primary papers and author software/documentation
  cover every method row. The original reference numbers remain stable.
  `docs/website/references.json` holds the reviewed bibliography; publisher-deposited
  metadata for the added DOI entries are retained in `reference_verification_20261026.json`.
  `python3 scripts/build_website_catalog.py` renders the method inventory and references;
  `--check` catches stale HTML, missing source entry points and missing citations.
  Bibliography URLs are allowlisted from this reviewed catalogue; other external
  links still require an explicit `ALLOWED_URLS` entry in `Testing/Website/check_site.py`.

The hero uses "SlicerDSpace" as its title, with the manuscript's descriptive
phrase underneath. The Idea, Workflows and Status sections are removed. Subject
identifiers stay in source records instead of repeated gallery introductions.
Get started includes
staging, module paths, extension requirements, canonical inputs, GUI environment
preparation and the first DTI run, with optional CLI/cohort instructions. The
homepage retains the contributor's established theme and original media.

---

## Publishing

The `Website` workflow validates the site and publishes **only `docs/site/`**
from `main`. It does not publish the repository root or the rest of `docs/`,
which contains internal scientific and release records. Website files are also
excluded from the Slicer extension's runtime package.

The film stays in ordinary Git for static playback. The repository size audit
permits only this exact public path, byte count and SHA256, not arbitrary large
videos or model files. Any replacement needs a separately reviewed update.

The repository owner must first open
[Settings > Pages](https://github.com/ChengjinLii/SlicerDSpace/settings/pages)
and set **Source: GitHub Actions**. Publishing from a private repository needs
an eligible paid plan. The website is public; the source repository stays private.
The current connector can read/write repository content but does not expose the
Pages administration endpoint. A successful merge is not proof that Pages is enabled.

The `Website` workflow is manual-only; a push or pull request does not run
validation or deploy the site. When explicitly dispatched, if Pages is off or
still configured for branch-based publishing, validation continues but deployment
is skipped with a setup notice. After enabling Pages, manually run `Website`
from the Actions page when publication is wanted.
A deployment is accepted only after the deploy job succeeds and the
public URL responds successfully.

Expected URL: `https://chengjinlii.github.io/SlicerDSpace/`. The canonical URL,
share tags and 404 home link assume this address. Review the original notes
before changing it. Do not configure `main /docs`: that would expose documents
outside the intended public website.

---

## Local Checks

```bash
python scripts/audit_pages_site.py
python -I Testing/Website/check_site.py
npm ci --prefix Testing/Website
node Testing/Website/browser_check.mjs
```

The browser test uses installed Google Chrome by default. `CHROME_EXECUTABLE`
can point to a compatible Chrome for Testing binary. Optional `PLAYWRIGHT_CORE`
selects an existing module; otherwise the pinned local dependency is used.
Video codec/playback checks are still required. Optional ffprobe checks clearly
report SKIP when ffprobe is unavailable.

Screenshots and browser results stay under ignored `Testing/Website/out/`.
Browser dependencies are test-only and do not ship in the website or Slicer
extension. The public-file allowlist rejects private documents and symlinks.

---

## Evidence Boundaries

The page describes the demonstrated workflow and its reviewed evidence, not a
guarantee that every scientific route passes on every subject or platform.
Keep its release-state and review caveats until stronger evidence exists.
The film's automatic transcript/timing checks do not replace listening to its
audio mix; the contributor recorded that human audio review is still pending.

Editable artwork, source renders and generation scripts are maintained in the independent [paper-latex repository](https://github.com/ChengjinLii/paper-latex). This software checkout retains reviewed website images and their SHA256 receipts.
