This directory contains local reference copies of SlicerDMRI tractography modules
from the installed Slicer 5.10.0 extension tree:

`/data/chengjin/software/Slicer-5.10.0-linux-amd64/slicer.org/Extensions-34045/SlicerDMRI/`

These files are not wired as SlicerDDSurfer runtime dependencies. They are kept
as implementation references for MRML FiberBundle handling, tractography import,
downsampling, and rasterization while SlicerDDSurfer designs its own
tractography, tract-cloud, bundle, and connectome glue.

No standalone module named `TractCloud` or `tract cloud` was found in the local
Slicer installation during this import. The closest installed Slicer-native
building blocks are SlicerDMRI FiberBundle and Tractography modules.
