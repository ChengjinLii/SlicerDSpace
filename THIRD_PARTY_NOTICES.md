# Third-Party Notices

SlicerDDSurfer's own source code is licensed under the BSD 3-Clause license
in [LICENSE](LICENSE). This file documents bundled third-party code, data,
and reference material that carries different terms, and states honestly
where full license/provenance information is not yet available in this
repository.

This replaces an earlier reference to a `third_party/REFERENCE_SOURCES.md`
file: that path is listed in `.gitignore`, is never committed, and does not
exist in a fresh checkout, so the link was broken for every user who was not
the original developer.

## FastSurfer-derived code (Apache License 2.0)

- `parcellation/models/losses.py`
- `parcellation/models/networks.py`
- `parcellation/models/solver.py`
- `parcellation/models/sub_module.py`
- `parcellation/data_loader/augmentation.py`
- `parcellation/data_loader/conform.py`
- `parcellation/data_loader/load_neuroimaging_data.py`

These files carry an in-file copyright header ("Copyright 2019 Image
Analysis Lab, German Center for Neurodegenerative Diseases (DZNE), Bonn")
and are derived from [FastSurfer](https://github.com/Deep-MI/FastSurfer),
licensed under the Apache License, Version 2.0. The full license text is in
[`licenses/Apache-2.0.txt`](licenses/Apache-2.0.txt); the notice text
reproduced from these files is in
[`licenses/NOTICE-FastSurfer.txt`](licenses/NOTICE-FastSurfer.txt).

## SAF (short association fibre tractography) backend (MIT License)

- `tractography/saf_backend/` (all files; bundled and packaged as runtime
  code -- see `docs/architecture/REPOSITORY_LAYOUT.md`)

Translated/bundled from [SAF](https://github.com/dmitrishastin/SAF)
(Dmitri Shastin), licensed under the MIT License. The full license text is
in [`tractography/saf_backend/LICENSE.md`](tractography/saf_backend/LICENSE.md),
which CMake packaging now includes alongside the module's Python sources
(see `CMakeLists.txt`). Method paper: D. Shastin, S. Genc, G.D. Parker,
K. Koller, C.M.W. Tax, J. Evans, K. Hamandi, W.P. Gray, D.K. Jones,
M. Chamberland, "Surface-based tracking for short association fibre
tractography", NeuroImage 2022,
[doi:10.1016/j.neuroimage.2022.119423](https://doi.org/10.1016/j.neuroimage.2022.119423).

## `parcellation/conversion/` (NRRD/NHDR conversion utilities)

- `parcellation/conversion/` (all files under this directory)

This code is attributed in-repo to the
[pnlbwh/conversion](https://github.com/pnlbwh/conversion) project (Tashrif
Billah): `parcellation/conversion/nhdr_write.py` writes
`"See https://github.com/pnlbwh/conversion for more info"` directly into its
output file header, and `parcellation/conversion/_version.py` records
`__version__ = '2.4'`, consistent with that project's own versioning.

**License status: not recorded in this repository.** No `LICENSE` file for
this code, and no license header in its source files, is present here.
**Confirm the exact license terms directly against
[github.com/pnlbwh/conversion](https://github.com/pnlbwh/conversion) before
redistributing this code or a build that includes it.**

## `parcellation/conversion/data/FreeSurferColorLUT.txt`

This is FreeSurfer's own color lookup table (RCS header:
`$Id: FreeSurferColorLUT.txt,v 1.105 2015/07/29 18:23:03 greve Exp $`),
copied verbatim from a FreeSurfer distribution. It is packaged as a Slicer
extension resource by `CMakeLists.txt`.

**License status: governed by the [FreeSurfer Software
License](https://surfer.nmr.mgh.harvard.edu/fswiki/FreeSurferSoftwareLicense),
not SlicerDDSurfer's BSD-3-Clause license.** Confirm the FreeSurfer license's
redistribution terms for this file before redistributing a build that
includes it; do not assume it is as permissive as BSD-3-Clause.

## Method papers requiring citation but not yet documented here

`docs/assets/MODEL_ASSET_TERMS.md` states that the DDSeg and DDParcel model
weights each "require ... citation of the peer-reviewed [DDSeg/DDParcel]
method paper," but this repository does not record either paper's title,
authors, journal, or DOI anywhere. `CITATION.cff` records a `references:`
entry for the DDSurfer method paper with a `TODO` for its DOI (the
DOI proposed in the review that produced this notice,
10.1002/advs.76596, does not appear anywhere in this repository's own
README or docs/, so it was not recorded without independent confirmation)
and a `notes:` line naming DDParcel and DDSeg as also requiring citation
once their bibliographic metadata is available.
