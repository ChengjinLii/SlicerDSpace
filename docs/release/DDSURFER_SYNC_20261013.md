<div align="center">

# DDSurfer Synchronization

**13 October 2026: coordinate metadata and surface postprocessing**

[Project](../../README.md) | [Documentation](../README.md) | [Dependencies](../setup/EXTERNAL_DEPENDENCIES.md) | [Previous Snapshot](DDSURFER_SYNC_20261005.md)

</div>

---

## Source And Scope

The bundled backend now matches DDSurfer commit
`c3b2d40ead82b316f0adec900a23979f629da70b`, replacing
`a4ec44cf56651b411ab30b9c91cfac63cc3b2300`. `UPSTREAM.json` records
82 exact source, license, citation and documentation hashes.

No model, inference, checkpoint, template or acquisition-preprocessing algorithm
changed between these snapshots. All nine surface asset records are unchanged;
31 core assets passed checksum verification. The model mirror's source-version
metadata was refreshed, but no weight/template contents were changed. The sync
helper now leaves byte-identical assets and their timestamps intact.

---

## Integration

- Native OBJ exports explicitly declare `SPACE=RAS`. Coordinates, vertex indices and connectivity are unchanged. Existing Slicer LPS/RAS STL compatibility exports remain available.
- Regional labels are written in Python, preserving present unknown labels, vertex order, surface-RAS coordinates and FreeSurfer text precision.
- Regional surface-only statistics use the same measurement definitions, now with shared inputs and in-process execution.
- Four fsaverage overlays are packed for one `mri_surf2surf --split` invocation. FreeSurfer still performs registration/mapping and writes the output metadata.
- Python-stage receipts validate temporary outputs and content hashes. Old snapshot receipts cannot silently satisfy the new postprocess stage.
- Slicer's dependency doctor no longer requires unused `recon-all`, `mri_annotation2label` or `mri_segstats` for this route. It checks `mris_place_surface` or the explicit `mris_thickness` fallback, plus the six retained commands.
- A surface-only FreeSurfer installation can be discovered without `recon-all`; actual atlas/license checks remain in the backend.
- Chinese upstream guides, optimization notes, citation metadata and the restored optional training-loss helper are mirrored. MIT/BSD notices are retained; PyTorch3D is not added as an inference requirement.

---

## Verification

Local evidence is under `ignore/validation/ddsurfer_sync_20261013/`.

| Check | Outcome | Scope |
| --- | --- | --- |
| Plugin regression suite | 880 tests: 877 passed, three explicit existing skips | `plugin-tests.log` |
| Exact upstream CPU suite | 161 passed, no skips | Isolated copy with the nine current resources; retained legacy templates excluded only from the test layout |
| Core assets | 31 verified | `assets.log`; checkpoint/template hashes unchanged |
| Real FreeSurfer label export | 109 byte-identical files across aparc and aparc.a2009s | Existing subject 100307, left hemisphere |
| Regional statistics | Byte-identical to the previous surface-only writer | Both cortical atlases |
| Batched fsaverage transfer | Four MGH files byte-identical to four individual FreeSurfer commands | Thickness, curvature, sulcal depth, pial area; each has 163842 target vertices |
| Source integrity | All measured input-file hashes unchanged | Native surfaces, atlas annotations, metric arrays and registration inputs |
| Real Slicer coordinate test | Passed | Direct RAS-marked OBJ loading, compatibility STL loading and save/reload |
| Real Slicer environment button | Passed | Independent user/revision settings and X displays |
| Installed resource audit | Passed | Source code, new helpers, notices and citation data are packaged together |

Real-command comparisons used FreeSurfer 7.4.1 and existing HCP 100307 results.
Overlay values, geometry, headers and additional MGH bytes matched exactly.
The reference commands and timings are preserved in `real-postprocess-100307/`.

These are implementation, output-equivalence and GUI checks, not new multi-subject
clinical validation. The complete model-inference/FreeSurfer reconstruction was
not rerun: the changed postprocessing operations were tested on real existing
outputs, and complete scheduling/resume was covered by upstream tests.

---

## Deployment

The current changes are local and have not been committed or pushed. The model
repository has only matching source-version metadata changes. A running Slicer
using an older installed copy must be restaged/restarted to use this snapshot;
the isolated checks do not alter the active Slicer or MRI Agent sessions.

~~~bash
python3 scripts/sync_ddsurfer_upstream.py \
  --upstream /data/chengjin/DDSurfer \
  --asset-root /data/chengjin/SlicerDDSurfer-models
python3 scripts/download_model_assets.py --profile core --verify-only \
  --asset-root /data/chengjin/SlicerDDSurfer-models
~~~

Stage and validate the extension package before deploying. Tests do not replace
the outstanding official SDK/CPack and cross-platform scientific acceptance gates.
