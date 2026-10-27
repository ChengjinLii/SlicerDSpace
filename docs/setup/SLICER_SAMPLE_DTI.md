<div align="center">

# First DTI With Slicer Sample Data

[Quick start](QUICKSTART.md) | [Environment](MANAGED_SETUP.md) | [Recorded check](../release/benchmarks/slicer_sample_dti_20261028.json) | [中文](SLICER_SAMPLE_DTI.zh-CN.md)

</div>

Use Slicer's existing **DWIVolume** example to try input preparation and DTI.
The sample has 128 × 128 × 94 voxels, 1.5-mm spacing and 43 measurements:
one b0 and 42 directions at b = 1,000 s/mm². It is a single-shell DTI example,
not a multi-shell NODDI/DKI or anatomical reconstruction benchmark.

---

## In Slicer

1. Install SlicerDDSurfer and SlicerDMRI. Open **Sample Data** and download
   **DWIVolume**. If the button is not visible, the Python console command is
   `import SampleData; SampleData.downloadSample('DWIVolume')`.
2. Save the downloaded DWI node as a diffusion NRRD using Slicer's **Save** dialog.
   Use a new working folder, keeping the original download unchanged.
3. Open SlicerDDSurfer. Under **Advanced settings > Regions & input import >
   Input import / conversion**, select the saved NRRD and a new subject folder.
   Preview the plan, then prepare inputs with Dry run cleared.
4. Set Subject root to the prepared subject folder. Select only **Microstructure**
   and retain only **DTI** in its **...** selector. Leave preprocessing and the
   other products unchecked for this short example.
5. Prepare the selected environment. The default PNL mask needs its model/runtime;
   an explicitly chosen MRtrix mask instead needs MRtrix. Under **Advanced settings
   > Preprocessing & mask**, choose a method you have prepared. This recorded
   example uses MRtrix; methods are not substituted after errors.
6. Click **Run SlicerDDSurfer**. Successful FA/MD maps load automatically. Inspect
   the brain mask, orientation, scalar contrast and **Results and QC** before
   accepting results. There is no regional statistics table without a label map.

---

## Expected Files And Checks

Prepared input comprises `input/data.nii.gz`, `input/bvals` and `input/bvecs`.
DTI outputs are under `outputs/02_microstructure/dti/`; the run record is under
`outputs/00_run_metadata/`. The source NRRD can have a different storage order
from NIfTI: compare physical coordinates, not just raw array indices.

The Linux/Slicer 5.10 check verifies the upstream hashes, exact voxel values
after the recorded orientation change, affine/gradient consistency and recorded
DTI output QC. Its DTI task takes 9.46 s on the configured reference workstation;
this excludes download, import, mask preparation, environment checking and Slicer
startup. Human anatomical review remains separate.

For unsigned 16-bit NRRD rejected by DWIConvert, the importer uses a temporary
signed copy only after proving that all values fit int16 and preserving geometry
and gradient metadata. Values beyond that range are rejected. It does not enable
`--allowLossyConversion` or modify the source file.

---

## Source

The files are obtained from [Slicer's SampleData registry](https://github.com/Slicer/Slicer/blob/main/Modules/Scripted/SampleData/SampleData.py)
and [SlicerTestingData](https://github.com/Slicer/SlicerTestingData), not mirrored
in this repository. Follow the upstream terms for use and further redistribution.
The recorded source hashes and limited validation scope are in the linked JSON.
