# SlicerDDSurfer project site: spec v2

Integration addendum, 22 October 2026 (revised 23 October 2026): the historical one-page design below is
retained for the overview. Measured performance evidence is now a section of the home page, `#performance`, reached
through one closed `<details>` ("Performance evidence"). It sits at the end of the page, after `#cite` and the visible
`#runtime` figure section, and opens by script when the URL hash is `#performance`. `performance.html` is only a stub:
a `refresh` to `index.html#performance`, a canonical link and one visible link. The section reuses the existing design
and local fonts; no extra runtime service is required. `assets/data/performance.json` is the only allowlisted public
data export. Tables are generated from verified benchmark records into `index.html` (between the
`measured-evidence` markers); methods are collapsed by default. Full-module/ROI/substage scopes and
implementation/thread/scheduling/Python-port categories must stay distinct. The independent measurements do not change
the film's claims or provenance. See [README.md](README.md#performance-section) for current generation and checks.

Addendum, 23 October 2026: the home page also has a "What is integrated" status table (in `#workflows`), a route
guide figure (`#choose`), a run-time figure (`#runtime`) and a numbered reference list (`#cite`). §5.6.1, §5.6a,
§5.10, §5.10a and §5.10b below describe them. Their sources are listed in §1, rule 7.

Addendum 2, 23 October 2026: `#outputs` (§5.5) is a results gallery with one tab per module (seven groups, 26 tiles),
built from the outputs of the film's run and of the 23 October 2026 runs on the same subject; `slicer.jpg` (§5.7) is a
new full-window screenshot of the module. Their sources are in §1, rule 7.

Date: 2026-10-20 (v2: fixes from the Opus spec review, round 1, listed in §9). Branch: `gh-pages` (orphan) of `ChengjinLii/SlicerDDSurfer`. Facts: [`FACTS.md`](FACTS.md) (cited
below as `[F<section>]`). The site makes no claim that is not in `FACTS.md`, except in the parts added on 23 October
2026 (§5.6.1, §5.6a, §5.10, §5.10a, §5.10b, and the performance section). Those parts have their own sources, named in
§1, rule 7.

## 1. Goal and limits

- A one-page project site for SlicerDDSurfer, with the promo film embedded and playable.
- Audience: diffusion MRI researchers who meet the project for the first time, and collaborators who will install it.
- The site must stay true while the repository is private. It states the pre-release status as the README does.
- Publishing is the owner's step: Settings → Pages → Deploy from a branch → `gh-pages`, folder `/docs`. Nothing in this
  branch enables Pages.

Settled decisions (not to be reopened in review):

1. Static HTML, CSS and a small vanilla JS file. No build step, no framework, no third-party requests at run time
   (fonts are self-hosted). Relative paths only, so the site works from any base path.
2. The served site is `docs/`. The branch root (`README.md`, `SPEC.md`, `FACTS.md`, `tests/`) is not served.
3. English only. Dark theme only (it matches the film). Phone to wide desktop.
4. The film file is the delivered film, byte for byte (no re-encode). Its `moov` box is already before `mdat`
   (faststart) [F9]. Subtitles are burned in, so the page has no `<track>`; it offers the `.srt` as a download and a
   transcript in the page.
5. No asset downloads (weights, templates, data) and no install-from-Extension-Manager claim for SlicerDDSurfer [F12.11].
6. Links into the repository are allowed; they need access while the repository is private. One note on the page says so.
7. Sources of the parts added on 23 October 2026. A row, a caption or a reference never claims more than its source:
   - Status table (§5.6.1): the code (`shared/orchestrator.py`, `shared/pipeline.py`, `microstructure/dki.py`,
     `microstructure/pipeline.py`, `tractography/*.py`, `connectome/pipeline.py`) and the dated records
     `docs/release/MODULE_RUNTIMES_20261017.md`, `docs/release/BUNDLE_WORKFLOW_20261021.md`,
     `docs/release/BUNDLE_BACKENDS_20261013.md`, `docs/release/SAF_PYTHON_20261013.md`,
     `docs/release/ALGORITHM_SELECTION_20261021.md`, `docs/setup/SUPPORT_MATRIX.md`, `docs/setup/UKF.md`,
     `docs/setup/MICROSTRUCTURE.md` and `docs/architecture/IMPLEMENTATION_PROVENANCE.md`.
   - Figures (§5.6a, §5.10a): `docs/figures/README.md` (legends, generators and data files) and the data files it names
     (`docs/release/benchmarks/module_runtimes_20261017.json`, `docs/site/assets/data/performance.json`).
   - Performance section (§5.10b): `docs/release/benchmarks/*.json`, through `scripts/build_performance_site.py`.
   - References (§5.10): the DOI record of each entry (Crossref or DataCite) and the page of the tool that asks for the
     citation. Entries that could not be checked are left out.
   - Results gallery (§5.5) and `slicer.jpg` (§5.7): the pipeline outputs and QC files of the runs, through the promo
     project's exporters (`P/tools/export_gallery.py`, `P/tools/render_slices.py`, `P/tools/make_site_tiles.py`; each
     tile's source file and SHA-256 in `P/renders/site_tiles/tiles.json`) and `P/runtime/gui_workflow_capture.py`
     for the screenshot. A tile shows only products that the pipeline published (not withheld as failed); a caption
     states any automatic QC result that did not pass.

## 2. Files

```
README.md                 owner notes: what this branch is, how to publish, how to test, lines to revisit at public release
SPEC.md                   this file
FACTS.md                  fact sheet
tests/check_site.py       static checks (Python 3 stdlib; ffprobe optional)
tests/browser_check.mjs   headless Chrome checks (playwright-core)
docs/.nojekyll
docs/index.html
docs/404.html             small page, same header/footer style, link home
docs/assets/css/site.css
docs/assets/css/performance.css   styles of the performance evidence inside `#performance`
docs/assets/js/site.js
docs/assets/js/performance.js     filters and method links of the performance evidence
docs/performance.html             stub: refresh to index.html#performance, canonical link, one visible link
docs/assets/fonts/        InterTight, Inter, IBMPlexMono as .woff2 (Latin subset) + the three OFL .txt files
docs/assets/img/          icon-64.png, icon-180.png (from R/Resources/Icons/SlicerDDSurfer.png), poster.jpg,
                          social.jpg, idea.jpg, out-dec.jpg, slicer.jpg, fig-route-guide.png, fig-runtime-resources.png
                          (the two figures are rasterised from `docs/figures/*.svg`, which is not served), and the 25
                          result tiles res-*.jpg of §5.5
docs/media/SlicerDDSurfer_promo_1080p.mp4   copy of P/out/SlicerDDSurfer_promo_1080p.mp4 (41,070,370 bytes)
docs/media/SlicerDDSurfer.en.srt            copy of P/out/SlicerDDSurfer.en.srt
```

## 3. Images (film frames, the cover, the two figures of §5.6a and §5.10a, the result tiles of §5.5 and the screenshot of §5.7)

Frames come from `P/out/SlicerDDSurfer_promo_1080p.mp4` with `ffmpeg -ss <t> -i <film> -frames:v 1`. Crop boxes are
`x0,y0,x1,y1` in the 1920×1080 frame. A crop taken while a subtitle cue is on screen ends at y ≤ 945 (subtitle text
starts near y = 950; two-line cues reach y ≈ 1040). Frames at 43.0, 50.2 and 56.8 s show no cue. Check each output by eye; adjust a box by up to 60 px if a brain or label is cut, and record the final
boxes in `README.md`. JPEG quality 82, progressive, sRGB.

| File | t (s) | Crop box | Output size | Shows |
|---|---|---|---|---|
| poster.jpg | 43.0 | full frame | 1920×1080 | whole-brain DTI tractography in the glass pial surface (no subtitle at 43 s) |
| idea.jpg | 9.0 | 60,60,1760,945 | width 1400 | DWI slice, "registration" arrow, "+ T1-weighted scan" card |
| out-dec.jpg | 22.8 | 815,155,1855,935 | 1200×900 | DEC map on three planes |
| slicer.jpg | — | from `P/runtime/shots_workflow_ms2/results_window.png` (3840×2054), resized | 1920×1027 | real 3D Slicer screenshot (§5.7) |
| social.jpg | — | from P/out/cover_1280x640.png | 1280×640 | the film's cover (og:image) |

Every `<img>` has `alt` (the “Shows” text above, the tile's description, or the icon’s name), `width`, `height` and
`loading="lazy"`. (The poster is the `<video poster>`, not an `<img>`.)

Result tiles (`res-*.jpg`, 1200×900, JPEG quality 84, progressive) come from `P/tools/make_site_tiles.py`: 3D stills
rendered in the film's look by `P/film/gallery.js` (resized from 1600×1200), or axial slices from
`P/tools/render_slices.py` with a colour bar of the display window or a legend. Grey marks voxels outside the method's
validity mask. Nothing else is drawn on the data. The screenshot shows the subject folder through a short link
(`/Users/Shared/EDDEN/sub-01` → the run's subject folder), the log cleared with its own Clear button and the Reason
column widened, so no path of the build machine is in view.

## 4. Look

- Tokens (CSS custom properties on `:root`):
  `--bg #06080b; --bg-2 #0a0e13; --panel #0e131a; --line rgba(236,232,223,.09); --line-2 rgba(236,232,223,.16);
  --text #ece8df; --muted #9ba5b0; --red #ff5a52; --green #46d38a; --blue #5b8cff; --orange #f0913f; --ivory #efe6d2;
  --csf #4d86e8; --radius 14px; --max 1200px; --gutter clamp(16px, 4vw, 40px)`.
- Type: Inter Tight (headings, 600, letter-spacing −0.02 to −0.035em), Inter (body, 16–18px, line-height 1.6),
  IBM Plex Mono (eyebrows, labels, chips, code; 12–13px, uppercase only for eyebrows, letter-spacing .08em).
  H1 `clamp(40px, 6.2vw, 84px)`; H2 `clamp(30px, 3.8vw, 52px)`.
- Motif: the DEC colours. A 2px "tri-rule" (`linear-gradient(90deg, var(--red), var(--green), var(--blue))`, 70%
  opacity) under the header and above each section eyebrow. Chips look like the film's labels: mono text,
  1px `--line-2` border, 6px radius, the product name in `--text` and the qualifier in `--muted`
  (e.g. `DDSeg · tissue`).
- Background: `--bg` with two fixed soft radial glows (blue upper left, faint green lower right, ≤ 10% opacity).
- Panels: `--panel`, 1px `--line`, `--radius`. No drop shadows except a soft DEC glow behind the film frame.
- Motion: sections fade and rise 12px once when they enter the viewport (IntersectionObserver, 600ms). None under
  `prefers-reduced-motion: reduce`. Content must be visible without JS (add the hidden state only from JS).
- Layout: max width `--max`, side gutter `--gutter`. Grids collapse: gallery 3 → 2 (≤ 900px) → 1 (≤ 560px), with
  2-column groups (2 → 2 → 1) and a 4-column group (4 → 2 → 1) in §5.5;
  two-column sections → 1 (≤ 900px); workflow cards 5 → 2 → 1. No horizontal page scroll at 320px or wider; code
  blocks scroll inside themselves (`overflow-x: auto`), grid children have `min-width: 0`.
- Header: sticky, 64px, `--bg` at 80% with backdrop blur, bottom tri-rule. Left: icon (28px) + "SlicerDDSurfer".
  Centre/right: anchor links. Right: chip "Private pre-release". At ≤ 1023px the links fold into a "Menu" button
  (`aria-expanded`, keyboard operable, closes on link click and Escape).
- Accessibility: skip link to `#main`; visible `:focus-visible` outline (2px `--blue`, 2px offset); one `<h1>`;
  headings in order; landmarks (`header`, `nav`, `main`, `footer`); body text contrast ≥ 7:1, small text never below
  `--muted`.

## 5. Page content (exact copy)

Typography marks: use the real characters “ ” ’ – — · › × in the HTML. Text in quotes below is the copy. `[F…]` marks
are sources for review and do not appear on the page.

### 5.0 Head

- `<html lang="en">`, `<meta charset="utf-8">`, viewport `width=device-width, initial-scale=1`.
- Title: “SlicerDDSurfer — Brain anatomy from diffusion MRI, inside 3D Slicer”.
- Description: “SlicerDDSurfer brings diffusion-MRI anatomical reconstruction, microstructural mapping and white-matter
  connectivity analysis into one 3D Slicer module.” [F1 README:15-18]
- `theme-color` `#06080b`; `color-scheme: dark`.
- Open Graph / Twitter: `og:type website`, `og:title` = the title, `og:description` = the description,
  `og:url https://chengjinlii.github.io/SlicerDDSurfer/`, `og:image
  https://chengjinlii.github.io/SlicerDDSurfer/assets/img/social.jpg` (1280×640), `twitter:card summary_large_image`.
  `<link rel="canonical">` to the same `og:url`. (These two absolute URLs are the expected Pages address; README lists
  them under “revisit”.)
- Icons: `assets/img/icon-64.png` (`rel=icon`), `assets/img/icon-180.png` (`rel=apple-touch-icon`).
- Fonts: `@font-face` with `font-display: swap`; preload the Inter Tight and Inter files.

### 5.1 Header nav

Links: “Film” `#film`, “Idea” `#idea`, “Outputs” `#outputs`, “Workflows” `#workflows`, “In Slicer” `#slicer`,
“Status” `#status`, “Get started” `#start`, “Cite” `#cite`. Chip: “Private pre-release” [F1 README:20-22].

### 5.2 Hero (`#top`)

- Eyebrow: “3D Slicer module · Diffusion MRI”.
- H1: “Brain anatomy from diffusion MRI, inside 3D Slicer.” [F9 narration 12; F1 README:15-18]
- Lead: “SlicerDDSurfer reconstructs tissue labels, brain regions and cortical surfaces directly from diffusion MRI,
  with no T1-weighted scan needed at analysis time. The same module maps microstructure, traces white-matter pathways
  and builds structural connectomes.” [F2 FACTS:10; F3 README table]
- Buttons: primary “Watch the film” (scrolls to the `#film` section and calls `play()` on `#film-video`), secondary “Get started” (`#start`).
- Status line under the buttons (small, `--muted`): “Research software · Private pre-release · BSD-3-Clause code”
  [F1 README:20; LICENSE].

### 5.3 Film (`<section id="film">`, with a visually hidden `<h2>Film</h2>`)

- A wide frame (max 1200px, 16:9, `--radius`, 1px `--line-2`, soft DEC glow) holding:
  `<video id="film-video" controls playsinline preload="metadata" poster="assets/img/poster.jpg" width="1920"
  height="1080" aria-label="SlicerDDSurfer film, 65 seconds, narrated, with subtitles in the picture">` with
  `<source src="media/SlicerDDSurfer_promo_1080p.mp4" type="video/mp4">` and a fallback link “Download the film (MP4)”.
- Progressive enhancement: JS removes `controls` at start and shows a centred play button (round, 88px, glass,
  triangle icon, label “Play film · 1:05”). Click/Enter/Space: hide the button, add `controls`, `play()` with sound.
  On `ended`: show the button again (label “Play again”). Without JS the native controls stay.
- Meta row under the frame (mono, small): “64.8 s · 1920 × 1080 · narrated · subtitles in the picture” and links
  “Download MP4 (41 MB)” `media/SlicerDDSurfer_promo_1080p.mp4` (`download`), “Subtitles (.srt)”
  `media/SlicerDDSurfer.en.srt` (`download`). [F9]
- `<details>` “Transcript”: an ordered list of the 12 narration lines, verbatim from the `.srt`, in order [F9]:
  1. Diffusion MRI records how water moves through the living brain.
  2. Mapping anatomy has usually meant a second, T1-weighted scan, registered into diffusion space.
  3. SlicerDDSurfer reconstructs anatomy directly from diffusion MRI, without a T1-weighted scan.
  4. It maps microstructure, from DTI to free water, NODDI and kurtosis.
  5. Tissue labels.
  6. Brain regions.
  7. White and pial surfaces,
  8. all in native diffusion space.
  9. Whole-brain tractography, traced in the same native space.
  10. And structural connectomes, built on the same anatomy.
  11. One 3D Slicer module, with automatic QC and a record of every run.
  12. SlicerDDSurfer. Brain anatomy from diffusion MRI, inside 3D Slicer.
- Note under the transcript (small): “The film shows one SlicerDDSurfer run on one public dataset (EDDEN sub-01). Free
  water, NODDI and kurtosis are optional routes; they were not run for the film.” [F9; F12.15]

### 5.4 The idea (`#idea`)

Two columns: text left, `idea.jpg` right.

- Eyebrow: “The idea”.
- H2: “Anatomy from the diffusion scan itself.”
- P1: “Mapping anatomy for a diffusion study has usually meant a second, T1-weighted scan, registered into diffusion
  space.” [F2 FACTS:9]
- P2: “SlicerDDSurfer works from the diffusion scan. DDSeg labels tissue, DDParcel labels brain regions and DDSurfer
  builds white and pial surfaces, all in native diffusion space.” [F2; F3; F9 narration 5–8]
- Input card (mono, panel), title “Canonical input”:
  ```
  sub-01/
    input/
      data.nii.gz
      bvals
      bvecs
      nodif_brain_mask.nii.gz   # optional; generation needs a supported backend
  ```
  caption: “A DWI series, its gradient files and an optional brain mask. DWI and mask must share one voxel grid.”
  [F6 README:100-113]
- Footnote (small, `--muted`): “‘No T1-weighted scan’ describes analysis time. The models were trained with labels
  derived from T1-weighted MRI.” [F2 FACTS:10]
- Image caption: “From the film: the usual route registers a separate T1-weighted scan into diffusion space.”

### 5.5 Outputs (`#outputs`)

- Eyebrow: “One subject, one space”.
- H2: “From one diffusion dataset to seven kinds of result.”
- Intro: “Every image shows output of SlicerDDSurfer on one public dataset: EDDEN, OpenNeuro ds004666, subject sub-01 (CC0). The input is EDDEN’s AVG_mag series: five repeated acquisitions, averaged, so its SNR is higher than a typical single scan. Anatomy, DTI and DTI tractography come from the film’s run (b = 0 and b ≈ 1000, 117 of 297 volumes). The other methods ran on 23 October 2026 with the repository code of that day: UKF on the same input, the multi-shell methods on b = 0, 1000 and 2000 (207 of 297 volumes).” [F9 Data; P/MAKING_OF.md:69-72, 142; P/tools/make_subject_ms.py; P/runtime/r2.sh]
- Tabs (`.result-tabs`, `role="tablist"`, `hidden` in the HTML): one button per group, `role="tab"`, with the
  group's tile count. `site.js` shows the list, hides every group but the selected one, and supports click, ←/→,
  Home and End; a hash `#res-<group>` selects that group. Without JS the list stays hidden and every group is shown
  under its H3 (`.group-title`, “<module> · <methods>”). With JS the H3 stays for screen readers only.
- Groups and tiles (image, chip, H4 title, caption, `alt`); 1200×900 each:

| Image | Chip | Title | Caption | alt |
|---|---|---|---|---|
| **Segmentation · DDSeg** (`res-seg`, `cols-2`) | | | | |
| res-tissue.jpg | “DDSeg · tissue” | “Tissue labels” | “White matter, grey matter and CSF, predicted from DTI features.” | DDSeg tissue labels on three planes |
| res-tissue-axial.jpg | “DDSeg · axial slice” | “Tissue labels, axial” | “The same labels on one slice. Neurological view: the subject’s left is on the left.” | DDSeg tissue labels on one axial slice |
| **Parcellation · DDParcel** (`res-parc`, `cols-2`) | | | | |
| res-parcel.jpg | “DDParcel · regions” | “Brain regions” | “Anatomical regions labelled in the diffusion volume.” | DDParcel regions on three planes |
| res-parcel-axial.jpg | “DDParcel · axial slice” | “Brain regions, axial” | “FreeSurfer colour table; cerebral white matter is drawn in grey.” | DDParcel regions on one axial slice |
| **Cortical surfaces · DDSurfer** (`res-surf`, `cols-2`) | | | | |
| res-white.jpg | “DDSurfer · white” | “White surface” | “Cortical surface mesh in native diffusion space.” | DDSurfer white-matter surface |
| res-pial.jpg | “DDSurfer · pial” | “Pial surface” | “Cortical surface mesh in native diffusion space.” | DDSurfer pial surface |
| **Microstructure · DTI, free water, NODDI, DKI, MK-Curve** (`res-micro`, `cols-4`) | | | | |
| out-dec.jpg | “DTI · DEC” | “Direction-encoded colour” | “Principal diffusion direction weighted by FA, from the DTI fit.” | DEC map on three planes |
| res-fa.jpg | “DTI · FA” | “Fractional anisotropy” | “Tensor fit by SlicerDMRI modules on b = 0 and 1000.” | DTI fractional anisotropy, axial slice |
| res-md.jpg | “DTI · MD” | “Mean diffusivity” | “Same fit. 1 µm²/ms = 10^−3 mm²/s.” | DTI mean diffusivity, axial slice |
| res-fw.jpg | “Free water · FW” | “Free-water fraction” | “DIPY free-water tensor model on b = 0, 1000 and 2000. Grey: outside the tissue validity mask.” | Free-water fraction, axial slice |
| res-ndi.jpg | “NODDI · NDI” | “Neurite density” | “AMICO fit on two shells. Grey: outside the tissue validity mask.” | NODDI neurite density index, axial slice |
| res-odi.jpg | “NODDI · ODI” | “Orientation dispersion” | “Same AMICO fit. Grey: outside the tissue validity mask.” | NODDI orientation dispersion index, axial slice |
| res-mk.jpg | “DKI · MK, WLS” | “Mean kurtosis” | “DIPY kurtosis model, WLS fit. Grey: voxels outside the DKI validity mask.” | DKI mean kurtosis from the WLS fit, axial slice |
| res-mkcurve.jpg | “MK-Curve · MK” | “Mean kurtosis, MK-Curve” | “Unofficial Python port, same data. Automatic QC did not pass: 98.7% of mask voxels are valid; the check needs all.” | Mean kurtosis after MK-Curve correction, axial slice |
| **Tractography · DTI deterministic, UKF, CSD/ACT** (`res-tract`, `cols-3`) | | | | |
| res-tr-dti.jpg | “Tractography · DTI” | “DTI deterministic” | “Tracking by DIPY. Shown: a display subset of 24,000 of 130,780 streamlines.” | Deterministic DTI tractography |
| res-tr-ukf.jpg | “Tractography · UKF” | “UKF two-tensor” | “UKFTractography. Input mask without 21 voxels where the mean b = 0 signal is zero. Shown: 24,000 of 208,295.” | UKF two-tensor tractography |
| res-tr-csd.jpg | “Tractography · CSD / ACT” | “MSMT-CSD with ACT” | “MRtrix3 iFOD2 on b = 0, 1000 and 2000; ACT tissue image from DDSeg. Shown: 24,000 of 1,000,000.” | MSMT-CSD tractography with ACT |
| **Bundles · WMQL, TractCloud** (`res-bund`, `cols-3`) | | | | |
| res-wmql-csd.jpg | “WMQL · on CSD / ACT” | “AF and CST, both sides” | “Author’s tract_querier, adapted ddparcel_act preset: 4 bundles, 706 streamlines. Anatomical review pending.” | WMQL arcuate and corticospinal bundles from CSD tractography |
| res-wmql-ukf.jpg | “WMQL · on UKF” | “AF and CST, both sides” | “Same queries on the UKF tractogram: 4 bundles, 798 streamlines. Anatomical review pending.” | WMQL arcuate and corticospinal bundles from UKF tractography |
| res-tc-dti.jpg | “TractCloud · on DTI” | “42 tracts” | “Author’s model (v1.0.0): 53,522 streamlines classified. Shown: 8,994.” | TractCloud bundles from DTI tractography |
| res-tc-ukf.jpg | “TractCloud · on UKF” | “42 tracts” | “84,356 streamlines classified. Shown: 9,321.” | TractCloud bundles from UKF tractography |
| res-tc-csd.jpg | “TractCloud · on CSD / ACT” | “42 tracts” | “417,180 streamlines classified. Shown: 9,886.” | TractCloud bundles from CSD tractography |
| **Connectome · streamline count, SIFT2** (`res-conn`, `cols-2`) | | | | |
| res-net-dti.jpg | “Connectome · DTI, count” | “Streamline count, DTI” | “84 DDParcel nodes. The 260 strongest of 854 edges are drawn; the matrix shows all 84 × 84 nodes (log scale).” | Connectome from DTI tractography: nodes, edges and matrix |
| res-net-ukf.jpg | “Connectome · UKF, count” | “Streamline count, UKF” | “The 260 strongest of 2,689 edges are drawn.” | Connectome from UKF tractography: nodes, edges and matrix |
| res-net-csd.jpg | “Connectome · CSD / ACT, count” | “Streamline count, CSD/ACT” | “The 260 strongest of 2,726 edges are drawn.” | Connectome from CSD tractography: nodes, edges and matrix |
| res-net-sift2.jpg | “Connectome · CSD / ACT, SIFT2” | “SIFT2-weighted count” | “Weights from tcksift2 on the same tractogram. The 260 strongest of 2,726 edges are drawn.” | SIFT2-weighted connectome from CSD tractography |

- Note in the Bundles group (small): “WMA (ORG atlas) also ran on the UKF tractogram and completed all steps (74 tracts), but failed the pipeline’s sampling check: the right arcuate fasciculus had 6 streamlines, below the minimum of 20. The pipeline withheld its products, so none is shown.” [P/runtime/subjects_ukf/sub-01/outputs/04_tractography/bundles/wma_org_atlas/ukf/wma_org_atlas_qc.json]
- Note under the groups (small): “All runs: 3D Slicer 5.12.4 on macOS (x86_64 build under Rosetta, CPU only), outside the Linux validation. Colours, subsets, slices and upsampling are display choices; they change the look, not the data. Where a stage records an automatic QC result, it passed, except MK-Curve. No expert has reviewed these outputs.” [the QC files of each run; `microstructure/mkcurve.py:265`]
- Counts in the captions come from `P/film/data/gallery/index.json` (tractograms, bundles, networks) and the QC files.
  The DTI tractography caption keeps “a display subset of 24,000 of 130,780” (§7.1, check 10).

### 5.6 Workflows (`#workflows`)

- Eyebrow: “Workflows”.
- H2: “One module, five workflow families.” [F3 README:28]
- Intro: “Select only the products you need. Install dependencies for the route you select, not for every possible
  product.” [F3 README:38]
- Five cards, numbered 01–05. Each: title, “Products” list, “Needs” line. Text verbatim from the README table [F3]:
  1. “Input preparation” — Products: “DICOM/NIfTI/NRRD import, gradient validation, optional mask generation and
     preprocessing” — Needs: “Appropriate import/preprocessing backend”.
  2. “Anatomical reconstruction” — “DDSeg tissue labels, DDParcel regions, DDSurfer white/pial surfaces” —
     “Matching model assets, PyTorch and SlicerDMRI for the selected route”.
  3. “Microstructural analysis” — “DTI FA/MD/AD/RD, optional Free-water, NODDI and DKI, regional summaries” —
     “Route-specific packages and acquisition suitability checks”.
  4. “White-matter pathways” — “DTI/CSD tractography, ACT/SIFT2, partial UKF and SAF routes, WMQL/WMA/TractCloud bundles” —
     “Backend-specific tools and assets”.
  5. “Structural connectivity” — “Regional matrices (streamline count; SIFT2-weighted for CSD/ACT), Slicer scene
     inspection, QC and provenance” — “Compatible parcellation and tractogram; SIFT2 weights for the weighted matrix.
     Scalar and length weights are Python API only”.
  (Cards 4 and 5 differ from the README table on purpose: UKF and SAF are partial, and the GUI and CLI reach only the
  streamline-count and SIFT2-weighted matrices.)
- Note row (three short items with a small icon or chip each) [F3]:
  - “Microstructure runs DTI only by default. Free-water, NODDI and DKI are each enabled independently under Advanced.”
  - “MRtrix3, FSL, FreeSurfer and advanced bundle backends are optional and are not installed silently.”
  - “A missing backend is reported, never silently replaced.”

#### 5.6.1 What is integrated (inside `#workflows`, after the note row)

- H3 “What is integrated”, then a table in a scroll wrapper (`.table-wrap`, `tabindex="0"`, `role="region"`; the table
  has `min-width: 980px`, so it scrolls inside the wrapper on small screens and the page never scrolls sideways).
- Columns: Stage · Method · How it is integrated · Status · Reference [n]. One row per method, 26 rows.
- Status values: “Supported (Linux test subjects)”; “Partial: <one-line reason>”; “Needs <tool>” as a second line where
  an external tool is required (FreeSurfer, MATLAB, MRtrix3, FSL, dcm2niix or DWIConvert, UKF extension). A row that is
  both partial and tool-dependent shows both lines; Partial is never dropped.
- Partial rows: MK-Curve (MATLAB reference), UKF two-tensor, SAF, WMQL on sparse input, WMA on CSD input, TractCloud on
  CSD input, scalar and length connectome weights (Python API only).
- Reference cells link to `#ref-<n>` in the reference list (§5.10).

### 5.6a Which route when (`#choose`, after `#workflows`)

- Eyebrow “Choosing routes”, H2 “Which route when.”, then `fig-route-guide.png` in a panel, wrapped in a link
  to the full-size file (`target="_blank" rel="noopener"`), with `width`, `height`, `loading="lazy"`, `decoding="async"`.
- Caption: a guide to choosing routes, built from the coded gates and documented dependencies; it shows which methods
  each acquisition and input allows (including the b-value limit for DKI), and three example routes; the rules come from the planner and method code; status
  is recorded for Linux test subjects. The caption must not say that a single-shell scan can use CSD/ACT.

### 5.7 In Slicer (`#slicer`)

- Eyebrow: “In 3D Slicer”.
- H2: “One 3D Slicer module, with QC and a record of every run.” [F9 narration 11; F1 README:15-18]
- `slicer.jpg` (1920×1027) full width in a panel. Caption: “A real screenshot of 3D Slicer 5.12.4 on macOS with the SlicerDDSurfer module. The module loaded the key results of the multi-shell EDDEN runs into the scene: FA in the slice views; the CSD/ACT tractogram with the WMQL and TractCloud bundles in the 3D view. Results and QC shows the selected run and its recorded QC. A capture script set the inputs and products to match the runs; the runs themselves were started from the command line.”
  [P/runtime/gui_workflow_capture.py; P/runtime/shots_workflow_ms2/capture.log]
- Ordered list “A run in six steps” [F6 README:89-94]:
  1. “Open SlicerDDSurfer from the module selector and choose English or Chinese.”
  2. “Enter the Subject ID, the subject root and, if you like, a separate output directory.”
  3. “Tick only the products you need.”
  4. “In Advanced settings, set routes, dependencies and models, and check the environment.”
  5. “Click Run SlicerDDSurfer. Missing inputs turn red; the log says what to correct.”
  6. “Key results from successful stages load into the scene. Review QC, reload, replace or clear them in Advanced
     settings › Results and QC.”
- Side note (panel, mono command) [F3 README:144-152]: title “From the command line”, text “Check inputs and the
  environment without running any algorithm:”, code
  `python3 run_subject_pipeline.py --subject-root /path/to/sub-01 --targets validation,microstructure --microstructure-stages dti --doctor`,
  then “Use `--plan` instead of `--doctor` to write a run plan.”

### 5.8 Status (`#status`)

- Eyebrow: “Status”.
- H2: “Research software, stated plainly.”
- Three columns, each a panel with a coloured top edge (green, orange, blue):
  - “Recorded” (green): “Linux real-data and GUI evidence is documented for specific checkouts, routes and
    datasets.” / “The compact interface has its own UI validation record.” [F5 README:158-163]
  - “Not certified” (orange): “Native Windows and macOS scientific workflows.” / “Three-platform SDK builds.”
    [F5 README:174]
  - “Not yet released” (blue): “Private pre-release; not in the official Extensions Catalog.” / “The Extension Index
    JSON is a draft Tier 1 proposal, not a submitted catalog entry and not acceptance by Slicer.” / “Public source access, third-party licence clearance and
    asset redistribution review remain release gates.” [F1; F5 README:175-176; EXTENSION_READINESS.md:106-107]
- Block “Implementation origins” [F4 README:42-45; PROVENANCE:25]: “DDSeg is a MATLAB-to-Python/PyTorch
  reimplementation. SAF and MK-Curve are unofficial Python ports of author MATLAB methods. PNL CNN masking invokes the
  author’s existing Python backend, not a rewritten PNL pipeline. DDSurfer runs bundled upstream Python code.”
  Link: “Implementation provenance and verification limits” → repo `docs/architecture/IMPLEMENTATION_PROVENANCE.md`.
- Callout (full width, panel, larger text): “A completed run is not a clinical assessment or proof of scientific
  correctness.” [F1 README:21-22]

### 5.9 Get started (`#start`)

- Eyebrow: “Get started”.
- H2: “Install from source.”
- Callout (top): “The repository is private during pre-release. Use an authorized checkout; links into the
  repository need access.” [F1 README:51] (Not the model-asset repository: `SlicerDDSurfer-models` is public,
  R/docs/release/VALIDATION_20260816.md:36.)
- Steps, each with a short title, text and (where given) a code block with a “Copy” button [F6 README:51-81]:
  1. “Stage the extension” —
     ```
     git clone https://github.com/ChengjinLii/SlicerDDSurfer.git
     cd SlicerDDSurfer
     python3 scripts/stage_slicer_extension.py \
       --install-root ~/SlicerDDSurfer-extension --link-mode copy --clean
     ```
     “Set `--slicer-version` to your Slicer version. This is a source/staging installation, not an official CPack
     release.”
  2. “Add the module path” — “In Edit › Application Settings › Modules, add the expanded absolute path of
     `~/SlicerDDSurfer-extension/SlicerDDSurfer/lib/Slicer-5.10/qt-scripted-modules` to Additional module paths, then
     restart Slicer. Local GUI validation uses Slicer 5.10.”
  3. “Add the extensions your routes need” — “Install SlicerDMRI and PyTorch from Slicer’s Extension Manager.”
  4. “Get the model files” — “Review the asset terms first, then download only the profile you need to a writable
     folder outside the checkout:”
     ```
     python3 scripts/download_model_assets.py --profile surface \
       --asset-root ~/SlicerDDSurfer-model-assets --source url \
       --source-id slicerdsurfer_models_git
     ```
     “Availability and SHA256 verification do not establish redistribution rights.”
  5. “Prepare the input” — “Use the canonical layout shown above. Gradient files must match the DWI measurements;
     corrected gradients must accompany motion-corrected DWI.”
- Doc links (chips/buttons, `target="_blank" rel="noopener"`): “Quick Start” → `docs/setup/QUICKSTART.md`,
  “Support matrix” → `docs/setup/SUPPORT_MATRIX.md`, “Model asset terms” → `docs/assets/MODEL_ASSET_TERMS.md`,
  “Repository” → repo root. All under `https://github.com/ChengjinLii/SlicerDDSurfer/blob/main/` (root: the repo URL).

### 5.10 Cite and references (`#cite`)

- Eyebrow “Cite”, H2 “Cite the software and the methods you use.”
- Text: “The SlicerDDSurfer protocol manuscript is in preparation. Cite the tested software version using
  CITATION.cff, together with the methods actually used.” Link “CITATION.cff” → repo `blob/main/CITATION.cff`. [F7]
- Three paper cards for DDSurfer, DDSeg and DDParcel, exactly as CITATION.cff [F7], numbered [1] to [3]
  (`id="ref-1"` to `ref-3`).
- H3 “References”: one numbered list, [4] to [35], in groups (H4): Microstructure; Tractography and connectomes; Bundles;
  Platform and tools; Data. Each item: lead author (“Surname Initials, et al.”; both names for two authors), title,
  venue, volume(issue):pages, year, and a DOI link `https://doi.org/<doi>`. Items without a DOI (ISMRM abstracts) link to
  the ISMRM archive page; the 2016 Dhollander workshop abstract has no link. Items marked unverified in the review notes
  are left out (for example the LNCS volume of TractCloud). Every external URL is in the allowed set (§6).
- Left out on purpose: SlicerDMRI (Norton 2017) and FastSurfer, because their titles contain “Open Source” and
  “accurate”, which `claims_banned` rejects in the site's text; optional entries the review notes did not tie to code
  (Reddy and Rathi 2016, Destrieux 2010, PyTorch).

### 5.10a Run times (`#runtime`, directly before `#performance`)

- Eyebrow “Recorded run times”, H2 “Recorded run times, per module.”, then `fig-runtime-resources.png`, same markup as
  §5.6a (the width and height attributes equal the pixel size of the file).
- Caption: one scoped measurement per row, log scale, rows are not summed; panel a is the recorded run time per module
  on Linux, GPU runs marked; panel b is the run time before and after seven code-path changes, one pair per row, on a
  shared Linux host, outputs match. The caption names no CPU or GPU model, no workstation, no macOS laptop, no EDDEN
  subject and no memory value: the ledger's host field is the report host, not necessarily the execution host. It
  adds that the SAF row re-filters 100,000 existing tracks (new initial tracking is not included) and that the
  TractCloud row ran on 50,000 tracks.

### 5.10b Performance (`#performance`, after `#runtime`)

- Eyebrow “Performance”, H2 “Measured changes and their limits.”, then one `<details id="performance-evidence"
  class="transcript perf-evidence">`, closed by default, with the summary “Performance evidence”.
- Inside: the intro and the two disclaimers, the filter buttons (shown by script only), the generated evidence region
  (charts, table, note, method records; written by `scripts/build_performance_site.py`), the four “levers” and the
  “boundary of the evidence” list. The headline of the old subpage (“Same methods. Less overhead.”) is not kept.
- Without JavaScript the native `<details>` still opens and shows the table. With JavaScript, `site.js` opens the
  details when the hash is `#performance` (on load, on `hashchange` and on a click on a link to it) and opens any closed
  `<details>` that contains the target of a hash (for example `#method-freewater`).

### 5.11 Footer

Three columns, then a bottom line.

- Column 1: icon + “SlicerDDSurfer”, “Diffusion MRI workflows in 3D Slicer.” [F1 README:5], “© 2026 Chengjin Li and the
  SlicerDDSurfer contributors.” [F8 LICENSE:1-3]
- Column 2 “Licence”: “Project code: BSD-3-Clause. Bundled components keep their own licences and notices. Model
  weights, templates and subject-derived data are not relicensed by the project licence.” Links “LICENSE.txt”,
  “Third-party notices” → repo `blob/main/LICENSE.txt`, `blob/main/THIRD_PARTY_NOTICES.md`. [F8]
- Column 3 “About the film” [F9 credits]: “Data: EDDEN, OpenNeuro ds004666 (CC0), Manzano-Patron et al., Imaging
  Neuroscience 2024.” (links: “ds004666” → `https://openneuro.org/datasets/ds004666`, “2024” paper →
  `https://doi.org/10.1162/imag_a_00060`). “Run: SlicerDDSurfer a48fc95, started from the command line, with 3D Slicer
  5.12.4, SlicerDMRI and PyTorch on macOS (x86_64 build under Rosetta, CPU only). This run is outside the Linux
  validation and needed local run-time workarounds that are not in the repository.” “Made with lemo-opuscar (MIT) and
  three.js (MIT). Voice: Kokoro TTS (Apache-2.0). Fonts: Inter, Inter Tight, IBM Plex Mono (SIL OFL 1.1). Music and
  sound: original, synthesized in code.” (link “lemo-opuscar” → `https://github.com/lemomo-ai/lemo-opuscar`)
  [F5 MAKING_OF:73-74, 144-145, 168; P/runtime/STATUS.md]
- Bottom line (small): “Static site: no cookies, no trackers, no third-party requests.” and “Back to top” `#top`.

## 6. Allowed external URLs (exact set)

`https://github.com/ChengjinLii/SlicerDDSurfer`, `https://github.com/ChengjinLii/SlicerDDSurfer.git` (in the code
block only), `https://github.com/ChengjinLii/SlicerDDSurfer/blob/main/` + one of `CITATION.cff`, `LICENSE.txt`,
`THIRD_PARTY_NOTICES.md`, `docs/setup/QUICKSTART.md`, `docs/setup/SUPPORT_MATRIX.md`,
`docs/assets/MODEL_ASSET_TERMS.md`, `docs/architecture/IMPLEMENTATION_PROVENANCE.md`;
the DOI links of the reference list (§5.10) and the four ISMRM archive pages (`https://archive.ismrm.org/<year>/<abstract>.html`),
`https://doi.org/10.1002/advs.76596`, `https://doi.org/10.1016/j.neuroimage.2021.117934`,
`https://doi.org/10.1109/TMI.2023.3331691`, `https://doi.org/10.1162/imag_a_00060`,
`https://openneuro.org/datasets/ds004666`, `https://github.com/lemomo-ai/lemo-opuscar`,
`https://chengjinlii.github.io/SlicerDDSurfer/` and `https://chengjinlii.github.io/SlicerDDSurfer/assets/img/social.jpg`
(head meta and `<link rel="canonical">` only; `404.html` may also link home with the first one, because GitHub Pages
serves it at nested paths where relative links break, so `404.html` inlines its CSS). Nothing is loaded from any external host.

## 7. Tests (must pass before push)

### 7.1 `tests/check_site.py` (run: `python3 -I tests/check_site.py [--film PATH]`; exit 1 on any FAIL)

Prints one `PASS name` / `FAIL name - reason` line per check; `SKIP` only where stated.

1. `html_basics`: `docs/index.html` and `docs/404.html` parse; doctype, `lang="en"`, `<title>`, viewport,
   description; exactly one `<h1>` in index; heading levels never skip (h2 → h4); every `id` is unique.
2. `local_refs`: every local `href`, `src`, `poster`, `srcset` and CSS `url()` resolves to a file inside `docs/`;
   every `#fragment` link resolves to an `id` in the page.
3. `external_urls`: every absolute URL in `docs/` (HTML, CSS, JS) is in the §6 set; `<link>`, `<script>`, `<img>`,
   `<source>`, `<video>` and CSS `url()`/`@import` never point to another host, except `<link rel="canonical">` with
   the §6 Pages URL. Inline SVG carries no `xmlns` (or namespace URIs are exempt).
4. `film_bytes`: `docs/media/SlicerDDSurfer_promo_1080p.mp4` is 41,070,370 bytes and, when `--film` is given, equal in
   SHA-256 to that file.
5. `film_faststart`: top-level MP4 boxes: `ftyp` first, `moov` before `mdat` (pure Python box scan).
6. `film_probe`: with `ffprobe` on PATH: h264 1920×1080 yuv420p, aac, duration 64.8 ± 0.05 s. `SKIP` without ffprobe.
7. `transcript_matches_srt`: the transcript list equals the 12 cue texts of `docs/media/SlicerDDSurfer.en.srt`, in order.
8. `sizes`: no file in `docs/` is over 50 MB; `docs/` is under 100 MB in total.
9. `images`: every `<img>` has non-empty `alt`, integer `width` and `height`; each image file's pixel size matches its
   attributes' aspect ratio within 2% (PNG/JPEG header parse, stdlib only).
    In checks 10 and 11, “visible text” means the text content of both pages plus every `alt`, `aria-label`,
    `title` attribute, `<title>`, `<meta name="description">`/`og:*` content, and the string literals in `site.js`.
10. `claims_required`: the visible text contains each of: “at analysis time”, “Private pre-release”, “not a clinical
    assessment”, “not certified” (case-insensitive), “24,000 of 130,780”, “not installed silently”, “in preparation”, “display subset”, “not acceptance by Slicer”,
    “not run for the film”, “No expert has reviewed”, “SNR is higher than a typical single scan”, “workarounds that are
    not in the repository”, “must share one voxel grid”.
11. `claims_banned`: the visible text matches none of (case-insensitive): `T1w?-free`, `T1-weighted-free`, `fully
    automatic`, `no registration`, `no preprocessing`, `U-shaped`, `\bthe first\b`, `\bthe only\b`, `clinical-grade`,
    `diagnos`, `FDA`, `available now`, `open[- ]source`, `\bfaster\b`, `\baccura(te|cy)\b`,
    `state[- ]of[- ]the[- ]art`, `cross-platform`, `(install|get|download)\w*\s+(SlicerDDSurfer|it)\b.{0,40}Extensions?
    (Manager|Catalog|Index)`, `(?<!not )(available )?(in|from|through) the (official )?Extensions? (Manager|Catalog)`
    (the allowed copy “not in the official Extensions Catalog” must pass). Also: `Extension Manager` occurs exactly
    once, inside “Install SlicerDMRI and PyTorch from Slicer’s Extension Manager.”
12. `no_local_paths`: no file in `docs/` contains `/Volumes/`, `/Users/`, `/private/tmp`, `file://`.
13. `links_safe`: every `target="_blank"` link has `rel` containing `noopener`.
14. `fonts_licensed`: every `.woff2` in `docs/assets/fonts/` has its OFL text next to it.

### 7.2 `tests/browser_check.mjs` (run: `PLAYWRIGHT_CORE=<dir of playwright-core> node tests/browser_check.mjs`)

Serves `docs/` from a local HTTP server with Range support (to match GitHub Pages), opens it in Google Chrome
(`channel: 'chrome'`; Playwright's Chromium lacks H.264/AAC), and checks at 1440×900 and 390×844 (and 320×640; and 861, 900,
1023, 1024 and 1100 px wide for header fit and no overlap of brand, nav links, chip and Menu button):

1. no console error; no failed request, except `net::ERR_ABORTED` on `media/*.mp4` (Chrome cancels and re-issues
   byte-range requests for video); no response with status ≥ 400; no request to another host;
2. `document.documentElement.scrollWidth <= innerWidth`;
3. the results tabs: the list is shown, 7 tabs, one group open, the first tab selected; a click on Microstructure and
   then → selects Tractography and shows only its group; every `<img>` is `complete` with `naturalWidth > 0` after
   each tab has been opened (each image scrolled into view) and the page scrolled through; without JS the tab list
   is not displayed and all seven groups are shown;
4. the video: `readyState >= 1`, `duration` 64.8 ± 0.05 s, `videoWidth` 1920; `canPlayType` for
   `video/mp4; codecs="avc1.640032, mp4a.40.2"` (High, level 5.0, as ffprobe reports) is not empty;
5. clicking the play button starts playback (`currentTime` advances within 3 s; muted in the test only) and shows
   `controls`;
6. at 390px the Menu button opens and closes the nav with the keyboard;
7. full-page screenshots to `tests/out/` (git-ignored) for a human look.

## 8. README.md (branch root) must say

1. What the branch is: the project site, made from the repo docs at a48fc95 and the delivered promo film (render 8).
2. How to publish (owner only): Settings → Pages → Deploy from a branch → `gh-pages` / `/docs`. The site is public
   once on, even while the repository is private; GitHub Pages on a private repository needs a paid plan.
3. How to test: the two commands in §7.
4. “Revisit at public release”: the status chip, the hero status line, the Status section, the “private” callout in
   Get started, the og:url/og:image/canonical URLs if the address differs, the Slicer version lines (README says 5.10,
   the film used 5.12.4; `--slicer-version` takes the form `Slicer-5.10` and the module path follows it).
   Before publishing: nobody has listened to the film's final mix yet (the ASR check is automatic); listen to it first.
   This is an owner note, not page copy.
6. Links into the repository use `blob/main`, so they follow `main`, not a48fc95.
5. Image crop boxes as finally used (§3).

## 9. Changes in v2 (Opus spec review, round 1)

Blocking items fixed: B1 unique ids (`film-video`; test); B2 slicer.jpg at 56.8 s, before the fade; B3 Outputs H2 and the
AVG_mag SNR caveat; B4 the film-run line names the CLI start and the local workarounds; B5 “Install dependencies …”
(an instruction, not an automatic install); B6 Extension Index JSON is a draft, not a submitted entry; B7 mask hedge
and “must share”; B8 Extension Manager / Catalog test; B9 ERR_ABORTED exemption for video range requests.
Non-blocking items taken in the same edit (copy precision or test scope): N1, N3, N4 (overflow widths), N5, N6, N7,
N8, N9, N10, N11, N13, N14, N17. Not taken (recorded in `README.md` → “Review backlog”): N2 (rule text only; boxes
fine), N12 (surfaces frame at 35.4 s), N15 (tool names), N16 (no inline SVG with xmlns is used), N18, N19.

Code review round 1 (commit 935a5d9): Opus B1 removed the “model-asset repository … private” clause from §5.9 (that
repository is public); Codex B1 moved the nav fold from ≤ 860px to ≤ 1023px and added the header overlap check to
§7.2. Non-blocking items are in `README.md` → “Review backlog”.

