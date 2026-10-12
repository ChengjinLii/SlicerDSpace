<div align="center">

# Brain Mask CLI Options

[Project](../../README.md) | [Documentation](../README.md) | [Shared Configuration](USER_CONFIG.md)

</div>

---

The subject CLI and batch CLI use `pnl_cnn` by default. Select a backend
explicitly with `--brain-mask-backend pnl_cnn|synthstrip|mrtrix|provided`.
Missing dependencies are reported, not replaced with another backend.
`provided` requires an existing `input/nodif_brain_mask.nii.gz`.

Configure the PNL runtime through external dependency paths:

```bash
python shared/run_subject_pipeline_cli.py \
  --subject-root /data/sub-01 --targets preprocessing,microstructure \
  --brain-mask-backend pnl_cnn \
  --pnl-mask-python /opt/pnl/bin/python \
  --pnl-mask-script /opt/pnl/dwi_masking.py \
  --pnl-mask-model-dir /opt/pnl/models \
  --pnl-mask-ants-bin-dir /opt/ants/bin \
  --doctor
```

`--doctor` checks dependencies and writes reports without running masking or
product inference, even when `--execute` is also present. Known missing masks
for selected DWI work, or new automatic masks needed after preprocessing, make
backend dependencies required. Checks without known subject inputs do not
require masking dependencies. `provided` only requires a canonical input mask,
not an inference runtime when the final preprocessing mask needs refreshing.
The shared-logic doctor entrypoints accept `brain_mask_required=False`;
subject-aware callers can pass `True` for a known missing or newly needed mask.

SynthStrip reuses `--postprocess-freesurfer-home /opt/freesurfer`; there is no
separate SynthStrip installation-path option. MRtrix uses the existing
`--mrtrix-bin-dir` and preprocessing MRtrix path settings.

The four PNL paths can also be supplied in `external_dependencies` in
`--dependency-config` or `--user-config` JSON. The backend is stored in
`run_defaults.brain_mask_backend` in the user config. Explicit CLI values take
precedence; dependency-profile paths take precedence over saved user paths.
Use `--no-user-config` to ignore saved GUI/CLI defaults. Use
`--save-user-config PATH` and `--save-dependency-config PATH` to persist the
resolved settings.

Batch runs forward the selected backend and paths unchanged to every subject:

```bash
python scripts/run_batch_pipeline.py \
  --batch-root /data/subjects --jobs 2 \
  --targets preprocessing,microstructure \
  --brain-mask-backend synthstrip \
  --postprocess-freesurfer-home /opt/freesurfer \
  --doctor
```

Omit `--doctor` and add `--execute` to run products. Without `--execute`, the
subject and batch CLIs perform dry-run planning.
