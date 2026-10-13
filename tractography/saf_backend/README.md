<div align="center">

# SAF Python Backend

**Native-diffusion-space short association fibre filtering**

[Project](../../README.md) | [Implementation](../../docs/architecture/IMPLEMENTATION_PROVENANCE.md) | [Validation](../../docs/release/SAF_PYTHON_20261013.md) | [中文](README.zh-CN.md)

</div>

This directory contains SlicerDDSurfer's **unofficial Python port** of
[Dmitri Shastin's MATLAB SAF framework](https://github.com/dmitrishastin/SAF/tree/7e2a9d152caf1cf3e6bface64e7e176faac0c14f).
The original MIT [license](LICENSE.md) is retained. Python execution does not
require MATLAB. NumPy, SciPy, scikit-learn, NiBabel and route-specific MRtrix
commands are required; use the validated facade in [`../saf.py`](../saf.py).

---

## Scope

GG/HH cortical endpoint and hemisphere conditions, optional PG filtering,
initial-track maximum length, GWG crossing/truncation, and surface projections
follow the upstream method. Surfaces and tractograms **must already share
native diffusion physical coordinates**. This facade does not perform the
original optional ANTs registration or run recon-all on a supplied T1 image.

The outputs are SAF tractography **candidates**, not independently verified
adjacent-gyri U-fibres. Upstream's soft GWG rule preserves outer crossings and
does not require all interior points to stay in white matter. The original
90 mm default is not a universal short-fibre anatomical definition; record the
actual length limit and filtering options used in each study.

---

## Port Differences

Revision `python-native-20261013` pairs endpoint coordinates with the correct
crossed faces, preserves original indices for rejected short tracks and maps
hard-split weights through the original tractogram. The complete-intersection
branch retains edge/vertex crossings and handles shared-point duplicates;
the published MATLAB source clears its edge/vertex flags before its return.
scikit-learn k-means is deterministic here but need not reproduce MATLAB's
clusters, so whole-pipeline bitwise equivalence is not claimed.

Old surface density/length/scalar projections require recomputation. Do not
interpret copied hard-split weights as newly estimated SIFT2 weights. The
[verification report](../../docs/release/SAF_PYTHON_20261013.md) separates author
kernel parity, analytic geometry tests, real-product checks and manual review.
The inherited [`doc/`](doc/README.md) documents **the original MATLAB version**,
not the complete supported Python interface or current dependency requirements.

---

## Citation

Shastin D., Genc S., Parker G.D., Koller K., Tax C.M.W., Evans J., Hamandi K.,
Gray W.P., Jones D.K., Chamberland M. *Surface-based tracking for short
association fibre tractography*. NeuroImage (2022).
[doi:10.1016/j.neuroimage.2022.119423](https://doi.org/10.1016/j.neuroimage.2022.119423).
