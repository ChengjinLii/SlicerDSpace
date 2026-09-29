# SlicerDDSurfer Product Architecture

This repository is organized around six top-level workflow areas. Implemented
code now lives directly under the corresponding product package instead of
separate legacy pipeline directories.

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
  - planned
- `Connectome`
  - planned

## Implemented Packages

- `shared/`
  - subject-root discovery
  - native DTI cache
  - registered DTI cache
- `surface/`
  - preprocessing
  - prediction
  - postprocessing
  - sculpting
- `parcellation/`
  - pipeline
  - conversion
  - data loader
  - model code
  - weights
- `segmentation/`
  - DDSeg package
  - PythonSlicer runner
  - weights
- `microstructure/`
  - phase-based microstructure pipeline
- `tractography/`
  - reserved for future implementation
- `connectome/`
  - reserved for future implementation

## Rationale

This follows the common Slicer extension pattern of keeping a thin scripted
module entry point and moving substantial Python code into support packages.
It also follows the multi-workflow extension style used by large Slicer
extensions, where one extension bundles several distinct workflows while still
keeping clear package boundaries for each product area.
