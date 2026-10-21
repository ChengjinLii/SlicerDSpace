# SlicerDDSurfer project site: spec v2

Date: 2026-10-20 (v2: fixes from the Opus spec review, round 1, listed in §9). Branch: `gh-pages` (orphan) of `ChengjinLii/SlicerDDSurfer`. Facts: [`FACTS.md`](FACTS.md) (cited
below as `[F<section>]`). The site makes no claim that is not in `FACTS.md`.

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
docs/assets/js/site.js
docs/assets/fonts/        InterTight, Inter, IBMPlexMono as .woff2 (Latin subset) + the three OFL .txt files
docs/assets/img/          icon-64.png, icon-180.png (from R/Resources/Icons/SlicerDDSurfer.png), poster.jpg,
                          social.jpg, idea.jpg, out-dec.jpg, out-tissue.jpg, out-regions.jpg, out-surfaces.jpg,
                          out-tracts.jpg, out-connectome.jpg, slicer.jpg
docs/media/SlicerDDSurfer_promo_1080p.mp4   copy of P/out/SlicerDDSurfer_promo_1080p.mp4 (41,070,370 bytes)
docs/media/SlicerDDSurfer.en.srt            copy of P/out/SlicerDDSurfer.en.srt
```

## 3. Images (all from the delivered film or cover; no new renders)

Frames come from `P/out/SlicerDDSurfer_promo_1080p.mp4` with `ffmpeg -ss <t> -i <film> -frames:v 1`. Crop boxes are
`x0,y0,x1,y1` in the 1920×1080 frame. A crop taken while a subtitle cue is on screen ends at y ≤ 945 (subtitle text
starts near y = 950; two-line cues reach y ≈ 1040). Frames at 43.0, 50.2 and 56.8 s show no cue. Check each output by eye; adjust a box by up to 60 px if a brain or label is cut, and record the final
boxes in `README.md`. JPEG quality 82, progressive, sRGB.

| File | t (s) | Crop box | Output size | Shows |
|---|---|---|---|---|
| poster.jpg | 43.0 | full frame | 1920×1080 | whole-brain DTI tractography in the glass pial surface (no subtitle at 43 s) |
| idea.jpg | 9.0 | 60,60,1760,945 | width 1400 | DWI slice, "registration" arrow, "+ T1-weighted scan" card |
| out-dec.jpg | 22.8 | 815,155,1855,935 | 1200×900 | DEC map on three planes |
| out-tissue.jpg | 27.0 | 725,150,1765,930 | 1200×900 | DDSeg tissue labels |
| out-regions.jpg | 30.6 | 700,150,1740,930 | 1200×900 | DDParcel regions |
| out-surfaces.jpg | 34.8 | 665,155,1705,935 | 1200×900 | DDSurfer pial surface |
| out-tracts.jpg | 43.0 | 470,0,1910,1080 | 1200×900 | tractography |
| out-connectome.jpg | 50.2 | 585,140,1838,1080 | 1200×900 | connectome nodes/edges and matrix |
| slicer.jpg | 56.8 | full frame | 1920×1080 | real 3D Slicer screenshot from the film (cue 11 ends at 56.5 s; the fade to the end card starts at 56.9 s) |
| social.jpg | — | from P/out/cover_1280x640.png | 1280×640 | the film's cover (og:image) |

Every `<img>` has `alt` (the “Shows” text above, or the icon’s name), `width`, `height` and `loading="lazy"`. (The
poster is the `<video poster>`, not an `<img>`.)

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
  `prefers-reduced-motion: reduce`. Content must be visible without JS (add the hidden state only from JS). The `js`
  class is set by `site.js` itself, not by an inline script, so a failed load of `site.js` also leaves everything
  visible; sections already on screen are marked shown before the class is set.
- Layout: max width `--max`, side gutter `--gutter`. Grids collapse: gallery 3 → 2 (≤ 900px) → 1 (≤ 560px);
  two-column sections → 1 (≤ 900px); workflow cards 5 → 2 → 1. No horizontal page scroll at 320px or wider; code
  blocks scroll inside themselves (`overflow-x: auto`), grid children have `min-width: 0`.
- Header: sticky, 64px, `--bg` at 80% with backdrop blur, bottom tri-rule. Left: icon (28px) + "SlicerDDSurfer".
  Centre/right: anchor links. Right: chip "Private pre-release". At ≤ 1023px the links fold into a "Menu" button
  (`aria-expanded`, keyboard operable, closes on link click, on Escape, and when focus moves to an element outside the menu; a focus change to nothing
  does not close it).
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
  On `ended`: show the button again (label “Play again”) and, when the video had focus, move focus to the play button. Without JS the native controls stay.
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
- H2: “From one diffusion dataset to six kinds of result.”
- Intro: “Every image here is a frame from the film. Each shows output from one SlicerDDSurfer run on one public
  dataset: EDDEN, OpenNeuro ds004666, subject sub-01 (CC0). The input is EDDEN’s AVG_mag series: five repeated
  acquisitions, averaged, so its SNR is higher than a typical single scan. The run used the b = 0 and b ≈ 1000 volumes
  (117 of 297).” [F9 Data; P/MAKING_OF.md:69-72, 142]
- Six tiles (image, chip, title, caption):

| Image | Chip | Title | Caption | Source |
|---|---|---|---|---|
| out-dec.jpg | “DTI · microstructure” | “Direction-encoded colour” | “Principal diffusion direction weighted by FA, from the DTI fit.” | F9 caveats (DEC = \|e1\| × FA) |
| out-tissue.jpg | “DDSeg · tissue” | “Tissue labels” | “White matter, grey matter and CSF, predicted from DTI features.” | F4 (five DTI features) |
| out-regions.jpg | “DDParcel · regions” | “Brain regions” | “Anatomical regions labelled in the diffusion volume.” | F7 (DDParcel title) |
| out-surfaces.jpg | “DDSurfer · surfaces” | “White and pial surfaces” | “Cortical surface meshes in native diffusion space.” | F2 FACTS:13 |
| out-tracts.jpg | “Tractography · DTI” | “Whole-brain tractography” | “Deterministic DTI tractography. Shown: a display subset of 24,000 of 130,780 streamlines.” | F9 caveats |
| out-connectome.jpg | “Connectome · DDParcel nodes” | “Structural connectome” | “The 260 strongest of 854 edges are drawn; the matrix shows all 84 × 84 nodes.” | F9 caveats |

- Note under the grid (small): “Colours, subsets and upsampling are display choices; they change the look, not the
  data. Automatic QC passed for the DTI, DDSeg, DDParcel and DDSurfer stages. No expert has reviewed these outputs.”
  [F9: MAKING_OF:26-33, 76-78]

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
  4. “White-matter pathways” — “DTI/CSD tractography, ACT/SIFT2, SAF, WMQL/WMA/TractCloud bundles” —
     “Backend-specific tools and assets”.
  5. “Structural connectivity” — “Regional matrices, Slicer scene inspection, QC and provenance” — “Compatible
     parcellation and tractogram; SIFT2 weights for weighted routes”.
- Note row (three short items with a small icon or chip each) [F3]:
  - “Microstructure runs DTI only by default. Free-water, NODDI and DKI are each enabled independently under Advanced.”
  - “MRtrix3, FSL, FreeSurfer and advanced bundle backends are optional and are not installed silently.”
  - “A missing backend is reported, never silently replaced.”

### 5.7 In Slicer (`#slicer`)

- Eyebrow: “In 3D Slicer”.
- H2: “One 3D Slicer module, with QC and a record of every run.” [F9 narration 11; F1 README:15-18]
- `slicer.jpg` full width in a panel. Caption: “From the film: a real screenshot of 3D Slicer 5.12.4 with the
  SlicerDDSurfer module and the results of the EDDEN run, loaded into the scene by the module. A capture script filled
  in the inputs and ticked the products to match the run; the run itself was started from the command line.”
  [F9 Software shown; MAKING_OF:34-42]
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

### 5.10 Cite (`#cite`)

- Eyebrow: “Cite”.
- H2: “Cite the software and the methods you use.”
- Text: “The SlicerDDSurfer protocol manuscript is in preparation. Cite the tested software version using
  CITATION.cff, together with the methods actually used.” Link “CITATION.cff” → repo `blob/main/CITATION.cff`. [F7]
- Three paper cards (authors, title, journal, year, DOI link), exactly as CITATION.cff [F7]:
  1. DDSurfer — “Chengjin Li, Wei Zhang, Xi Zhu, Yuqian Chen, Nir A. Sochen, Jarrett Rushmore, Carl-Fredrik Westin,
     Yogesh Rathi, Lauren J. O’Donnell, Ofer Pasternak, Fan Zhang.” “DDSurfer: A Weakly-Supervised Dual-Stream Deep
     Learning Framework for Cortical Surface Reconstruction From Diffusion MRI.” “Advanced Science, 2026, e76596.”
     `https://doi.org/10.1002/advs.76596`
  2. DDSeg — “Fan Zhang, Anna Breger, Kang Ik Kevin Cho, Lipeng Ning, Carl-Fredrik Westin, Lauren J. O’Donnell, Ofer
     Pasternak.” “Deep learning based segmentation of brain tissue from diffusion MRI.” “NeuroImage, 2021, 233,
     117934.” `https://doi.org/10.1016/j.neuroimage.2021.117934`
  3. DDParcel — “Fan Zhang, Kang Ik Kevin Cho, Johanna Seitz-Holland, Lipeng Ning, Jon Haitz Legarreta, Yogesh Rathi,
     Carl-Fredrik Westin, Lauren J. O’Donnell, Ofer Pasternak.” “DDParcel: Deep Learning Anatomical Brain Parcellation
     From Diffusion MRI.” “IEEE Transactions on Medical Imaging, 2024, 43(3), 1191–1202.”
     `https://doi.org/10.1109/TMI.2023.3331691`
  (Plain ASCII hyphens in the names and titles are fine; CITATION.cff uses U+2010 in two places.)

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
15. `menu_focus_wording`: the `site.js` focusout comment, the README “Opus N3” note and this spec (§4) each say “a
    focus change to nothing does not close it”, and none keeps the old wording that hands that case to the click
    handlers.
16. `spec_lists_checks`: this list names every check the script runs, in run order, numbered 1..n. §9 records every
    check added after v2 (items 15 on) as ``item <n> `<name>` ``, with n its number in this list, and a §9
    paragraph that records item 15 cites the review that limited it to §4 (the Codex P1 of the 90a6a03 review).
    After the last check, `main()` also fails it when the checks that ran differ from the list it was given.
17. `backlog_wording`: the fixes in the script's `WORDING_FIXES` table (README backlog r9 2–4 and r10 1, 2, 4, 5)
    stay in place: in the part of a file that each row names, the fixed phrase is there and, where there is one, the
    old phrase is not. In a `.py` part made of comment lines the `#` marks are removed before the test; from a `.py`
    part that holds code the comment lines are removed, so commented-out code does not count.

### 7.2 `tests/browser_check.mjs` (run: `PLAYWRIGHT_CORE=<dir of playwright-core> node tests/browser_check.mjs`)

Serves `docs/` from a local HTTP server with Range support (to match GitHub Pages), opens it in Google Chrome
(`channel: 'chrome'`; Playwright's Chromium lacks H.264/AAC), and checks at 1440×900 and 390×844 (and 320×640; and 861, 900,
1023, 1024 and 1100 px wide for header fit and no overlap of brand, nav links, chip and Menu button):

1. no console error; no failed request, except `net::ERR_ABORTED` on `media/*.mp4` (Chrome cancels and re-issues
   byte-range requests for video); no response with status ≥ 400; no request to another host;
2. `document.documentElement.scrollWidth <= innerWidth`;
3. every `<img>` is `complete` with `naturalWidth > 0` after scrolling the page through;
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

After code review (2026-10-20, README backlog Opus N1): §4 gains the sentence that `site.js` sets the `js` class itself.

After code review (2026-10-21, README backlog r4 B2, r6 1–2, r7 2 and the Codex P1 of the 90a6a03 review): §7.1 gains
item 15 `menu_focus_wording` (the wording in the `site.js` focusout comment, the README “Opus N3” note and §4 only)
and item 16 `spec_lists_checks` (§7.1 names every check in run order, numbered 1..n; this section names every check
added after v2).

After code review (2026-10-21, README backlog r8 1–2): item 16 `spec_lists_checks` now needs each check added after
v2 recorded here as ``item <n> `<name>` ``, with n its §7.1 number, and the paragraph that records item 15 must cite
the review that limited it to §4.

After code review (2026-10-21, README backlog r9 1–4): item 16 `spec_lists_checks` splits this section into
paragraphs also at lines that hold only spaces or tabs, and accepts the item-15 citation in any paragraph that
records item 15; §7.1 gains item 17 `backlog_wording` (the wording fixes r9 2–4 stay in place).

After code review (2026-10-21, README backlog r10 1–5): item 16 `spec_lists_checks` also fails when the checks that
ran differ from the list it was given; item 17 `backlog_wording` gains rows for r10 1, 2, 4 and 5 (the `re.split`
call in `spec_lists_checks`, that comparison in `main()`, and the r10 4 and r10 5 wording) and removes the `#`
comment marks in a `.py` part before the test.

After code review of af78411 (2026-10-21, Codex P1): item 17 `backlog_wording` removes the comment lines from a `.py`
part that holds code, so commented-out code does not satisfy a pin; in a part made of comment lines it still removes
only the marks.
