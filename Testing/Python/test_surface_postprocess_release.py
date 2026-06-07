#!/usr/bin/env python3
"""Tests for the bundled DDSurfer postprocess wrapper."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import nibabel as nib
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class SurfacePostprocessReleaseTest(unittest.TestCase):
    def test_stage_inputs_respects_left_mode(self) -> None:
        from surface.postprocess_release import stage_postprocess_inputs

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            native_dir = root / "native"
            mri_dir = root / "mri"
            native_dir.mkdir()
            mri_dir.mkdir()
            for name in ("brain.mgz", "DDSurfer-wmparc.nii.gz"):
                (mri_dir / name).write_text(name, encoding="utf-8")
            for name in (
                "877168_predicted_wm_lh_orig.stl",
                "877168_predicted_pial_lh_orig.stl",
                "877168_predicted_wm_rh_orig.stl",
                "877168_predicted_pial_rh_orig.stl",
            ):
                (native_dir / name).write_text(name, encoding="utf-8")

            staged = stage_postprocess_inputs(
                subject_id="877168",
                native_dir=native_dir,
                wmparc_path=mri_dir / "DDSurfer-wmparc.nii.gz",
                brain_mgz_path=mri_dir / "brain.mgz",
                staging_inputs_root=root / "staging",
                mode="left",
                force=False,
            )

            surf_names = sorted(path.name for path in (staged / "surf").iterdir())
            self.assertEqual(
                surf_names,
                ["877168_predicted_pial_lh_orig.stl", "877168_predicted_wm_lh_orig.stl"],
            )

    def test_run_returns_canonical_paths(self) -> None:
        from surface.postprocess_release import DDSurferPostprocessConfig, run_ddsurfer_postprocess

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            native_dir = root / "native"
            mri_dir = root / "mri"
            backend_root = root / "backend"
            output_root = root / "outputs"
            native_dir.mkdir()
            mri_dir.mkdir()
            (backend_root / "config").mkdir(parents=True)

            for name in ("brain.mgz", "DDSurfer-wmparc.nii.gz"):
                (mri_dir / name).write_text(name, encoding="utf-8")
            for name in (
                "877168_predicted_wm_lh_orig.stl",
                "877168_predicted_pial_lh_orig.stl",
            ):
                (native_dir / name).write_text(name, encoding="utf-8")

            run_sh = backend_root / "run.sh"
            run_sh.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
subject_id=""
outputs_dir=""
nested="${NEST_SUBJECT_OUTPUTS:-1}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --subject-id) subject_id="$2"; shift 2 ;;
    --outputs-dir) outputs_dir="$2"; shift 2 ;;
    *) shift ;;
  esac
done
if [[ "$nested" = "0" ]]; then
  structural_root="${outputs_dir}/03_structural/ddsurfer/postprocess"
  stats_root="${outputs_dir}/05_statistics/ddsurfer/postprocess/stats"
else
  structural_root="${outputs_dir}/${subject_id}/03_structural/ddsurfer/postprocess"
  stats_root="${outputs_dir}/${subject_id}/05_statistics/ddsurfer/postprocess/stats"
fi
mkdir -p "${structural_root}/surf" "${structural_root}/label" "${stats_root}"
printf '{"kind":"ddsurfer_postprocess","stage_status":{"sync_outputs":"completed"}}' > "${structural_root}/manifest.json"
printf '{"status":"completed"}' > "${structural_root}/qc.json"
""",
                encoding="utf-8",
            )
            run_sh.chmod(0o755)

            result = run_ddsurfer_postprocess(
                DDSurferPostprocessConfig(
                    subject_id="877168",
                    native_dir=native_dir,
                    mri_dir=mri_dir,
                    output_root=output_root,
                    backend_root=backend_root,
                    mode="left",
                )
            )

            self.assertEqual(
                result.structural_root,
                output_root / "03_structural" / "ddsurfer" / "postprocess",
            )
            self.assertEqual(
                result.stats_root,
                output_root / "05_statistics" / "ddsurfer" / "postprocess",
            )
            self.assertTrue(result.manifest_path.is_file())
            self.assertTrue(result.qc_path.is_file())
            self.assertTrue((result.staged_input_dir / "surf" / "877168_predicted_wm_lh_orig.stl").exists())
            self.assertTrue((output_root / "03_structural").is_dir())
            self.assertTrue((output_root / "05_statistics").is_dir())
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["kind"], "ddsurfer_postprocess")
            self.assertEqual(qc["status"], "completed")

    def test_run_generates_brain_mgz_from_subject_fa_when_missing(self) -> None:
        from surface.postprocess_release import DDSurferPostprocessConfig, run_ddsurfer_postprocess

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subject_root = root / "100307"
            output_root = subject_root / "outputs"
            native_dir = output_root / "03_structural" / "ddsurfer" / "pred_results_SlicerDDSurfer" / "native" / "100307"
            mri_dir = output_root / "03_structural" / "ddparcel"
            dti_dir = output_root / "02_microstructure" / "dti"
            backend_root = root / "backend"
            native_dir.mkdir(parents=True)
            mri_dir.mkdir(parents=True)
            dti_dir.mkdir(parents=True)
            (backend_root / "config").mkdir(parents=True)

            for name in (
                "100307_predicted_wm_lh_orig.stl",
                "100307_predicted_pial_lh_orig.stl",
            ):
                (native_dir / name).write_text(name, encoding="utf-8")
            (mri_dir / "100307-DDSurfer-wmparc.nii.gz").write_text("wmparc", encoding="utf-8")
            fa = nib.Nifti1Image(np.ones((8, 9, 10), dtype=np.float32), np.diag([-1.25, 1.25, 1.25, 1.0]))
            nib.save(fa, dti_dir / "100307_dti_FA.nii.gz")

            run_sh = backend_root / "run.sh"
            run_sh.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
subject_id=""
outputs_dir=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --subject-id) subject_id="$2"; shift 2 ;;
    --outputs-dir) outputs_dir="$2"; shift 2 ;;
    *) shift ;;
  esac
done
structural_root="${outputs_dir}/${subject_id}/03_structural/ddsurfer/postprocess"
stats_root="${outputs_dir}/${subject_id}/05_statistics/ddsurfer/postprocess/stats"
mkdir -p "${structural_root}/surf" "${structural_root}/label" "${stats_root}"
printf '{"kind":"ddsurfer_postprocess","stage_status":{"sync_outputs":"completed"}}' > "${structural_root}/manifest.json"
printf '{"status":"completed"}' > "${structural_root}/qc.json"
""",
                encoding="utf-8",
            )
            run_sh.chmod(0o755)

            with mock.patch("surface.postprocess_release.FS_BRAIN_TEMPLATE_SHAPE", (32, 32, 32)), mock.patch(
                "surface.postprocess_release.FS_BRAIN_TEMPLATE_AFFINE",
                np.eye(4, dtype=np.float32),
            ):
                result = run_ddsurfer_postprocess(
                    DDSurferPostprocessConfig(
                        subject_id="100307",
                        subject_root=subject_root,
                        output_root=output_root,
                        backend_root=backend_root,
                        mode="left",
                    )
                )

            generated = output_root / "03_structural" / "cache" / "ddsurfer_postprocess_runtime" / "generated_mri" / "100307" / "brain.mgz"
            staged = result.staged_input_dir / "mri" / "brain.mgz"
            self.assertTrue(generated.is_file())
            self.assertTrue(staged.exists())
            generated_img = nib.load(str(generated))
            self.assertEqual(generated_img.shape, (32, 32, 32))


if __name__ == "__main__":
    unittest.main()
