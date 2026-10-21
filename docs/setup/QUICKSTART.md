<div align="center">

# Quick Start

**A small, inspectable first workflow**

[Project](../../README.md) | [Documentation](../README.md) | [Platforms](SUPPORT_MATRIX.md) | [QC](GUI_RESULT_REVIEW.md) | [中文](QUICKSTART.zh-CN.md)

</div>

Use the source installation in the README. No automatic first-run wizard is
shown; this project is not yet in the official Extensions Catalog.

---

## Prepare A Subject

Use authorized, de-identified DWI, matching bval/bvec and a brain mask on the
same voxel grid. Follow the canonical input layout in the README. DICOM/NRRD
conversion is under **Advanced settings > Regions & input import > Input import / conversion**; preview
before writing. Install SlicerDMRI for Slicer-based DTI preparation.

Check the runtime in the separate **Environment and installation** section.
Choose **Prepare selected analysis environment**, confirm downloads and terms,
and restart when requested. Click Prepare again after restart to continue.
Checks run in a cancellable background process and update the inline summary.
Preparing an already-ready environment does not prompt, download or reinstall.
Dependency details, offline import, repair and manual paths are under
**More options (offline, repair, paths)** in the Environment section.
Use **Use offline model resources** for a predownloaded model directory, or
**Repair selected managed tools** for a damaged plugin-managed runtime.
See [managed setup](MANAGED_SETUP.md) for coverage and platform limits.
MRtrix3, FSL and FreeSurfer are not needed just to try a DTI-only route.
Missing dependencies are reported, not silently replaced by a different method.

The Microstructure, Tractography and Bundles rows show the current algorithm
selection: **DTI**, **MRtrix3 CSD / ACT** and **WMQL** by default. These labels
update when settings change; they describe the configuration, not completed or
QC-approved results. Click **Select…** beside each of these three products to
choose one or several methods. DTI remains required preparation; FW, NODDI and
DKI are independent options. Advanced settings uses four categories, showing
only the selected category's parameters. Environment installation is separate.

Multiple tracking methods run sequentially as separate `<run>__<backend>`
variants. Shared anatomy/microstructure runs once; selected bundle methods and
connectomes are computed for each tracking variant. Streamlines are not combined;
dependency checks and QC gates still apply. More methods require more time and disk space.

---

## Run DTI Only

1. Select Subject root. An empty subject ID is filled from the folder name;
   an existing custom ID is preserved. Selecting its canonical `input/` directory
   resolves to the subject root. An empty output directory uses `<subject>/outputs/`.
2. Select **Microstructure** and uncheck all other products, including preprocessing.
3. Click **Select…** beside Microstructure and retain only DTI.
4. Click **Run SlicerDDSurfer** and inspect the log. Necessary preflight checks
   run in the background. Missing dependencies stop submission and open the
   Environment section; prepare them and retry rather than silently omitting products.
5. FA/MD automatically load as successful stages finish. In the separate **Results and QC** section, select the completed run to inspect QC or use **Load / reuse** again without duplicating nodes.
6. Inspect the mask, finite-value checks, spatial alignment and QC summary before accepting results.

Generate a plan without execution:

~~~bash
python3 run_subject_pipeline.py --subject-root /path/to/sub-01 \
  --targets validation,microstructure --microstructure-stages dti --plan
~~~

MD loads in grayscale. Display settings do not change voxel values.
Execution completion, automated QC and human review are separate states.
DTI is the default; enable FW, NODDI and DKI with the main-screen selector only when
their acquisition requirements are met. A missing input mask uses the selected
backend (PNL CNN by default); an existing mask avoids that dependency. Configure
mask alternatives and external runtimes before running.

---

## Synthetic Installation Check

From the repository root, in a runtime with NumPy and nibabel:

~~~bash
python3 -c "from pathlib import Path; from shared.demo_data import create_synthetic_demo_subject; print(create_synthetic_demo_subject(Path('ignore/demo')))"
~~~

Use the resulting <code>ignore/demo/slicerdsurfer-demo</code> as Subject root.
This is a small constant tensor field with seven measurements, **not human
anatomy**. It checks installation/DTI plumbing, not surface accuracy, NODDI or
clinical validity.

The legacy Demo handler is retained for tests, not an advertised visible button.
A redistributable real-data tutorial and Sample Data registration remain future
milestones; neither is claimed as complete.

---

## If A Run Fails

Missing fields turn the waiting message red. Configure missing dependencies in
Environment and installation before retrying. Cancel stops active jobs; installed packages are not
rolled back and partial downloads may resume. Redact identifiers before sharing logs.
