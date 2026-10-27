#!/usr/bin/env python3
"""Render the homepage's method inventory and always-visible bibliography."""

import argparse
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "docs/website/references.json"
PAGE = ROOT / "docs/site/index.html"

# Keep implementation scope explicit: an API-only measure is not a GUI default.
# Each entry identifies a real entry point and its primary method/software sources.
METHODS = (
    ("input", "Input", "DICOM / NIfTI / NRRD", "Conversion, gradient validation and spatial checks.", "dcm2niix or Slicer DWIConvert; supplied masks accepted", [36, 27, 28], "scripts/prepare_inputs.py"),
    ("pnl_cnn", "Brain mask", "PNL CNN (default)", "Author diffusion-CNN brain masking and registration.", "Managed PNL runtime, weights and ANTs", [37, 38], "shared/brain_mask.py"),
    ("synthstrip", "Brain mask", "SynthStrip", "Brain extraction with the author model.", "Isolated runtime and weights", [32], "shared/brain_mask.py"),
    ("dwi2mask", "Brain mask", "MRtrix3 dwi2mask", "Native diffusion-volume masking.", "MRtrix3", [29], "shared/brain_mask.py"),
    ("mppca", "Preprocessing", "MP-PCA", "Random-matrix denoising and noise estimation.", "DIPY or MRtrix3 dwidenoise", [39, 52, 53, 29, 30], "preprocessing/pipeline.py"),
    ("localpca", "Preprocessing", "Local PCA", "Overcomplete local-PCA denoising.", "DIPY; optional denoising choice", [40, 30], "preprocessing/pipeline.py"),
    ("patch2self", "Preprocessing", "Patch2Self", "Self-supervised diffusion-volume denoising.", "DIPY; optional denoising choice", [41, 30], "preprocessing/pipeline.py"),
    ("gibbs", "Preprocessing", "Gibbs removal", "Local subvoxel-shift ringing correction.", "DIPY or MRtrix3 mrdegibbs", [42, 29, 30], "preprocessing/pipeline.py"),
    ("motion", "Preprocessing", "Volume registration", "Between-volume motion correction and gradient rotation.", "DIPY; does not perform FSL eddy correction", [30], "preprocessing/pipeline.py"),
    ("eddy", "Preprocessing", "FSL eddy", "Eddy-current and motion correction.", "MRtrix3 dwifslpreproc; FSL", [43, 29], "preprocessing/pipeline.py"),
    ("topup", "Preprocessing", "FSL topup", "Susceptibility-distortion estimation and correction.", "FSL; reverse-phase data and acquisition metadata", [44, 29], "preprocessing/pipeline.py"),
    ("dti", "Microstructure", "DTI (default)", "LS/WLS tensor fitting; FA, MD, AD, RD, eigenvalues and trace.", "SlicerDMRI", [45, 27, 28], "shared/pipeline.py"),
    ("freewater", "Microstructure", "Free water", "Free-water fraction and tissue-corrected FA/MD; WLS or NLS fitting.", "DIPY; suitable multi-shell sampling", [4, 5, 6, 30], "microstructure/pipeline.py"),
    ("noddi", "Microstructure", "NODDI / AMICO", "NDI, ODI, IsoVF and fit residuals.", "AMICO; suitable multi-shell sampling", [7, 31], "microstructure/pipeline.py"),
    ("dki", "Microstructure", "DKI", "WLS/OLS fitting; MK, AK, RK, KFA, MKT, RTK and validity masks.", "DIPY; shell, direction and design-rank checks", [8, 30], "microstructure/dki.py"),
    ("mkcurve", "Microstructure", "MK-Curve", "Correction curves, corrected kurtosis maps and metric-specific validity.", "Bundled Python backend; DKI eligibility checks", [9], "microstructure/mkcurve.py"),
    ("ddseg", "Anatomy", "DDSeg", "Tissue labels and probabilities from converted PyTorch models.", "PyTorch; DDSeg weights", [2], "anatomy/segmentation/pipeline.py"),
    ("ddparcel", "Anatomy", "DDParcel", "Anatomical region inference with author-derived models.", "PyTorch; weights and registration template", [3], "anatomy/parcellation/pipeline.py"),
    ("ddsurfer", "Anatomy", "DDSurfer", "Native white and pial mesh reconstruction.", "PyTorch; DDSurfer weights", [1], "anatomy/surface/pipeline.py"),
    ("brainsfit", "Anatomy", "BRAINSFit registration", "Template registration for eligible anatomical routes.", "Slicer BRAINSFit / BRAINSResample", [51, 27], "shared/pipeline.py"),
    ("surface_postprocess", "Anatomy", "Surface post-processing", "Thickness, curvature, spherical registration and DK/Destrieux atlas mapping.", "Licensed native component runtime; full suite optional", [33, 47, 48, 49], "anatomy/surface/pipeline.py"),
    ("response", "Tractography", "Response estimation", "Dhollander three-tissue response estimation.", "MRtrix3", [12, 13, 29], "tractography/pipeline.py"),
    ("csd", "Tractography", "CSD / MSMT-CSD", "Single- or multi-tissue fibre-orientation distributions.", "MRtrix3; selected acquisition route", [11, 46, 10, 29], "tractography/pipeline.py"),
    ("mtnormalise", "Tractography", "Multi-tissue normalization", "Log-domain intensity and inhomogeneity normalization.", "MRtrix3 mtnormalise", [17, 18, 29], "tractography/pipeline.py"),
    ("csd_act", "Tractography", "iFOD2 / ACT (default)", "Probabilistic tracking with DDSeg-derived tissue constraints.", "MRtrix3; reviewed anatomical priors", [14, 15, 29], "tractography/pipeline.py"),
    ("dti_tracking", "Tractography", "DTI deterministic", "Tensor-based direction tracking with stopping criteria.", "SlicerDMRI; DIPY", [45, 28, 30], "tractography/dti.py"),
    ("ukf", "Tractography", "UKF two-tensor", "Automatic invocation of the official tracking CLI.", "UKFTractography extension; SlicerDMRI", [19, 28], "tractography/ukf.py"),
    ("saf", "Tractography", "SAF", "Surface-constrained short-association tracking and geometric filtering.", "MRtrix3; post-processed native surfaces", [20], "tractography/saf.py"),
    ("wmql", "Bundles", "WMQL (default)", "Official multi-bundle queries with optional subset selection.", "Author tract_querier; DDParcel labels", [21], "tractography/wmql.py"),
    ("wma", "Bundles", "WMA", "ORG-atlas registration and clustering; automatic UKF handoff.", "WMA; ORG atlas; UKF reference route", [22, 23, 24, 26], "tractography/wma.py"),
    ("tractcloud", "Bundles", "TractCloud", "Author learned tract parcellation and bundle export.", "PyTorch backend; model and centroids", [25, 22], "tractography/tractcloud.py"),
    ("count", "Connectome", "Streamline count", "Endpoint assignment to DDParcel nodes.", "Python or eligible MRtrix3 backend", [50, 29], "connectome/pipeline.py"),
    ("sift2", "Connectome", "SIFT2-weighted count", "FOD-informed weighting and matrix construction with matched tracks.", "MRtrix3; corresponding tractogram and weights", [16, 29, 50], "connectome/pipeline.py"),
    ("scalar_length", "Connectome", "Scalar / length summaries", "Mean FA, MD, ODI or another scalar; mean and total streamline length.", "Python API; matched maps, nodes and tracks", [50, 29, 30], "connectome/pipeline.py"),
    ("regional", "Regional analysis", "Selected-region analysis", "Reuse maps for ROI statistics, filter tracks and extract node submatrices.", "Advanced settings; workflow utility using completed outputs", [3, 30, 50], "shared/region_analysis.py"),
)


def render_methods(references):
    ids = {row["id"] for row in references}
    lines, previous = [], None
    for identifier, stage, method, summary, runtime, citations, source in METHODS:
        if not (ROOT / source).is_file():
            raise ValueError("Method entry point is missing: " + source)
        if not citations or not set(citations) <= ids:
            raise ValueError("Method has incomplete references: " + identifier)
        links = " ".join(f'<a href="#ref-{n}" aria-label="Reference {n}">[{n}]</a>' for n in citations)
        group = ' class="stage-start"' if stage != previous else ""
        lines.append(f'            <tr data-method="{identifier}"{group}><th scope="row">{escape(stage)}</th><td>{escape(method)}</td><td>{escape(summary)}</td><td class="st-cell">{escape(runtime)}</td><td class="ref-cell">{links}</td></tr>')
        previous = stage
    return "\n".join(lines)


def render_references(references):
    if [row["id"] for row in references] != list(range(1, len(references) + 1)):
        raise ValueError("Reference IDs must be unique and consecutive")
    lines = []
    for row in references:
        if not row["url"].startswith("https://"):
            raise ValueError("A reference needs a primary HTTPS link")
        n = row["id"]
        lines.append(f'          <li id="ref-{n}"><span class="ref-n">[{n}]</span><span class="ref-text">{escape(row["citation"])} <a class="doi" href="{escape(row["url"], quote=True)}" target="_blank" rel="noopener">{escape(row["link_label"])}</a></span></li>')
    return "\n".join(lines)


def render(page, references):
    for key, value in (("methods-catalog", render_methods(references)),
                       ("references-catalog", render_references(references))):
        start, end = f"<!-- {key}:start -->", f"<!-- {key}:end -->"
        if page.count(start) != 1 or page.count(end) != 1:
            raise ValueError("Expected one generated catalog region: " + key)
        page = page.split(start)[0] + start + "\n" + value + "\n" + end + page.split(end)[1]
    return page


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    references = json.loads(REFERENCES.read_text(encoding="utf-8"))["references"]
    original = PAGE.read_text(encoding="utf-8")
    expected = render(original, references)
    if args.check:
        if original != expected:
            raise SystemExit("Homepage catalogs are stale; run scripts/build_website_catalog.py")
    else:
        PAGE.write_text(expected, encoding="utf-8")
    print(f"PASS {len(METHODS)} method entries and {len(references)} linked references")


if __name__ == "__main__":
    main()
