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
conversion is under **Advanced settings > Input import / conversion**; preview
before writing. Install SlicerDMRI for Slicer-based DTI preparation.

Check the runtime under **Advanced settings > Environment and models**.
MRtrix3, FSL and FreeSurfer are not needed just to try a DTI-only route.
Missing dependencies are reported, not silently replaced by a different method.

---

## Run DTI Only

1. Enter Subject ID, Subject root and a fresh Output directory.
2. Select **Microstructure** and uncheck all other products, including preprocessing.
3. In **Advanced settings > Analysis parameters**, select only the DTI microstructure stage.
4. Check the environment, click **Run SlicerDDSurfer**, and inspect the log.
5. FA/MD automatically load as successful stages finish. In **Advanced settings > Results and QC**, select the completed run to inspect QC or use **Load / reuse** again without duplicating nodes.
6. Inspect the mask, finite-value checks, spatial alignment and QC summary before accepting results.

Generate a plan without execution:

~~~bash
python3 run_subject_pipeline.py --subject-root /path/to/sub-01 \
  --targets validation,microstructure --microstructure-stages dti --plan
~~~

MD loads in grayscale. Display settings do not change voxel values.
Execution completion, automated QC and human review are separate states.
DTI is the default; enable FW, NODDI and DKI separately in Advanced only when
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
Advanced before retrying. Cancel stops active jobs; installed packages are not
rolled back and partial downloads may resume. Redact identifiers before sharing logs.
