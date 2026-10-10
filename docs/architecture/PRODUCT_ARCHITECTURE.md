# SlicerDDSurfer Product Architecture

This repository is organized around six top-level workflow areas. Implemented
code now lives directly under the corresponding product package instead of
older standalone pipeline directories.

## Product Areas

- `Surface`
  - DDSurfer preprocessing, prediction, native-space postprocessing, sculpting
- `Parcellation`
  - DDParcel
- `Segmentation`
  - DDSeg
- `Microstructure`
  - FA / MD
  - ROI-wise statistics
  - Free Water
  - NODDI
- `Tractography`
  - DTI tracking scaffold
  - ACT dependency/readiness scaffold
  - WMA ORG atlas clustering scaffold
  - planned CSD methods
- `Connectome`
  - tractography + DDParcel dependency checks
  - optional streamline-count matrix execution

## Implemented Packages

- `shared/`
  - subject-root discovery
  - input validation and lightweight QC report
  - native DTI cache
  - registered DTI cache
- `anatomy/surface/`
  - preprocessing
  - prediction
  - postprocessing
  - sculpting
- `anatomy/parcellation/`
  - pipeline
  - conversion
  - data loader
  - model code
  - weights
- `anatomy/segmentation/`
  - DDSeg package
  - PythonSlicer runner
  - weights
- `microstructure/`
  - phase-based microstructure pipeline
- `tractography/`
  - DTI tracking manifest and QC scaffold
  - ACT manifest and QC scaffold
  - MRtrix3 backend availability checks
  - DDParcel/parcellation dependency checks
  - 5TT/GMWMI readiness checks for standard ACT
  - WMA dry-run command wrapper
  - WMA manifest writer
  - WMA backend / atlas structure checks
  - WMA QC JSON output
  - optional external WMA backend discovery
  - reserved for future CSD implementation
- `connectome/`
  - tractography dependency checks
  - DDParcel parcellation dependency checks
  - streamline-count matrix and node table outputs
  - optional MRtrix3 `tck2connectome` backend
  - Python endpoint-label fallback for `.trk`/`.tck` and legacy `.vtk`

## Rationale

This follows the common Slicer extension pattern of keeping a thin scripted
module entry point and moving substantial Python code into support packages.
It also follows the multi-workflow extension style used by large Slicer
extensions, where one extension bundles several distinct workflows while still
keeping clear package boundaries for each product area.
