#!/usr/bin/env python3
"""Lightweight tests for the WMA tractography integration."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class WMAIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.wma_root = self.tmp_path / "wma"
        self.wma_bin = self.wma_root / "bin"
        self.wma_bin.mkdir(parents=True)
        self.wma_script = self.wma_bin / "wm_apply_ORG_atlas_to_subject.sh"
        self.wma_script.write_text(
            """#!/bin/sh
while [ "$#" -gt 0 ]; do
  case "$1" in
    -i) input="$2"; shift 2 ;;
    -o) out="$2"; shift 2 ;;
    *) shift ;;
  esac
done
case_id=$(basename "$input")
case_id=${case_id%.*}
mkdir -p "$out/$case_id/FiberClustering" "$out/$case_id/AnatomicalTracts"
printf '' > "$out/$case_id/AnatomicalTracts/T_AF_left.vtp"
exit 0
""",
            encoding="utf-8",
        )
        self.wma_script.chmod(0o755)
        for script_name in (
            "wm_append_clusters_to_anatomical_tracts.py",
            "wm_assess_cluster_location_by_hemisphere.py",
            "wm_cluster_from_atlas.py",
            "wm_cluster_remove_outliers.py",
            "wm_harden_transform.py",
            "wm_register_to_atlas_new.py",
            "wm_separate_clusters_by_hemisphere.py",
            "wm_diffusion_measurements.py",
            "xvfb-run",
        ):
            script = self.wma_bin / script_name
            script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            script.chmod(0o755)
        self.tractography = self.tmp_path / "subject.vtk"
        self.tractography.write_text("# vtk DataFile Version 3.0\n", encoding="utf-8")
        self.atlas_dir = self.tmp_path / "ORG-Atlases"
        self.atlas_dir.mkdir()
        (self.atlas_dir / "ORG-RegAtlas-100HCP").mkdir()
        (self.atlas_dir / "ORG-800FC-100HCP").mkdir()
        self.slicer_executable = self.tmp_path / "Slicer"
        self.slicer_executable.write_text("#!/bin/sh\n", encoding="utf-8")
        self.slicer_executable.chmod(0o755)
        self.output_dir = self.tmp_path / "out"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_builds_org_atlas_command_without_running_wma(self) -> None:
        from tractography import WMAOrgAtlasConfig, run_wma_org_atlas

        result = run_wma_org_atlas(
            WMAOrgAtlasConfig(
                subject_id="100307",
                input_tractography=self.tractography,
                atlas_dir=self.atlas_dir,
                output_dir=self.output_dir,
                slicer_executable=self.slicer_executable,
                wma_root=self.wma_root,
                registration_mode="rig",
                num_threads=2,
                use_virtual_x=True,
                clean_files=1,
                execute=False,
            )
        )

        self.assertFalse(result.executed)
        self.assertTrue(result.manifest_path.is_file())
        self.assertTrue(result.qc_path.is_file())
        self.assertTrue(result.backend_status["available"])
        self.assertTrue(result.atlas_status["available"])
        command = list(result.command)
        self.assertEqual(command[0], self.wma_script.resolve().as_posix())
        self.assertIn("-i", command)
        self.assertIn(self.tractography.resolve().as_posix(), command)
        self.assertIn("-a", command)
        self.assertIn(self.atlas_dir.resolve().as_posix(), command)
        self.assertIn("-s", command)
        self.assertIn(self.slicer_executable.resolve().as_posix(), command)
        self.assertIn("-x", command)
        self.assertIn("1", command)

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["subject_id"], "100307")
        self.assertFalse(manifest["executed"])
        self.assertEqual(manifest["status"], "planned")
        self.assertEqual(manifest["registration_mode"], "rig")
        self.assertEqual(manifest["num_threads"], 2)
        self.assertEqual(manifest["backend"]["source"]["repository"], "https://github.com/SlicerDMRI/whitematteranalysis.git")
        self.assertTrue(manifest["atlas"]["available"])
        qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
        self.assertEqual(qc["status"], "planned")
        self.assertFalse(qc["executed"])

    def test_rejects_non_vtk_inputs(self) -> None:
        from tractography import WMAOrgAtlasConfig, run_wma_org_atlas

        bad_input = self.tmp_path / "subject.trk"
        bad_input.write_text("", encoding="utf-8")
        with self.assertRaises(ValueError):
            run_wma_org_atlas(
                WMAOrgAtlasConfig(
                    subject_id="100307",
                    input_tractography=bad_input,
                    atlas_dir=self.atlas_dir,
                    output_dir=self.output_dir,
                    slicer_executable=self.slicer_executable,
                    wma_root=self.wma_root,
                )
            )

    def test_wma_root_is_external_and_explicit_by_default(self) -> None:
        from tractography.wma import resolve_wma_root

        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("shutil.which", return_value=None):
            with self.assertRaisesRegex(FileNotFoundError, "optional external backend"):
                resolve_wma_root()

    def test_rejects_incomplete_org_atlas_layout(self) -> None:
        from tractography import WMAOrgAtlasConfig, run_wma_org_atlas

        bad_atlas = self.tmp_path / "bad-atlas"
        bad_atlas.mkdir()
        with self.assertRaisesRegex(FileNotFoundError, "ORG atlas directory is incomplete"):
            run_wma_org_atlas(
                WMAOrgAtlasConfig(
                    subject_id="100307",
                    input_tractography=self.tractography,
                    atlas_dir=bad_atlas,
                    output_dir=self.output_dir,
                    slicer_executable=self.slicer_executable,
                    wma_root=self.wma_root,
                )
            )

    def test_execute_true_records_completed_qc_with_fake_backend(self) -> None:
        from tractography import WMAOrgAtlasConfig, run_wma_org_atlas

        result = run_wma_org_atlas(
            WMAOrgAtlasConfig(
                subject_id="100307",
                input_tractography=self.tractography,
                atlas_dir=self.atlas_dir,
                output_dir=self.output_dir,
                slicer_executable=self.slicer_executable,
                wma_root=self.wma_root,
                execute=True,
            )
        )

        self.assertTrue(result.executed)
        self.assertEqual(result.return_code, 0)
        qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
        self.assertEqual(qc["status"], "completed")
        self.assertEqual(qc["return_code"], 0)
        self.assertTrue(Path(qc["logs"]["stdout"]).is_file())
        self.assertTrue(Path(qc["logs"]["stderr"]).is_file())

    def test_execute_true_marks_failed_when_script_returns_zero_without_outputs(self) -> None:
        from tractography import WMAOrgAtlasConfig, run_wma_org_atlas

        self.wma_script.write_text(
            """#!/bin/sh
exit 0
""",
            encoding="utf-8",
        )
        self.wma_script.chmod(0o755)

        result = run_wma_org_atlas(
            WMAOrgAtlasConfig(
                subject_id="100307",
                input_tractography=self.tractography,
                atlas_dir=self.atlas_dir,
                output_dir=self.output_dir,
                slicer_executable=self.slicer_executable,
                wma_root=self.wma_root,
                execute=True,
            )
        )

        self.assertTrue(result.executed)
        self.assertEqual(result.return_code, 0)
        qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
        self.assertEqual(qc["status"], "failed")
        self.assertIn("required FiberClustering/AnatomicalTracts outputs", qc["error"])
        self.assertTrue(Path(qc["logs"]["stdout"]).is_file())
        self.assertTrue(Path(qc["logs"]["stderr"]).is_file())

    def test_execute_true_marks_partial_failed_when_clusters_exist_but_anatomical_tracts_do_not(self) -> None:
        from tractography import WMAOrgAtlasConfig, run_wma_org_atlas

        self.wma_script.write_text(
            """#!/bin/sh
while [ "$#" -gt 0 ]; do
  case "$1" in
    -i) input="$2"; shift 2 ;;
    -o) out="$2"; shift 2 ;;
    *) shift ;;
  esac
done
case_id=$(basename "$input")
case_id=${case_id%.*}
mkdir -p "$out/$case_id/FiberClustering/InitialClusters/${case_id}_reg"
printf '' > "$out/$case_id/FiberClustering/InitialClusters/${case_id}_reg/cluster_00001.vtp"
exit 0
""",
            encoding="utf-8",
        )
        self.wma_script.chmod(0o755)

        result = run_wma_org_atlas(
            WMAOrgAtlasConfig(
                subject_id="100307",
                input_tractography=self.tractography,
                atlas_dir=self.atlas_dir,
                output_dir=self.output_dir,
                slicer_executable=self.slicer_executable,
                wma_root=self.wma_root,
                execute=True,
            )
        )

        qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
        self.assertEqual(qc["status"], "partial_failed")
        self.assertEqual(qc["output_summary"]["initial_cluster_count"], 1)
        self.assertEqual(qc["output_summary"]["anatomical_tract_count"], 0)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "partial_failed")
        self.assertIn("runtime_seconds", manifest)

    def test_runtime_library_paths_include_slicerdmri_extension_dirs(self) -> None:
        from tractography.wma import _slicer_runtime_library_paths

        slicer_root = self.tmp_path / "SlicerRoot"
        slicer_exec = slicer_root / "Slicer"
        qt_loadable = (
            slicer_root
            / "slicer.org"
            / "Extensions-99999"
            / "SlicerDMRI"
            / "lib"
            / "Slicer-5.10"
            / "qt-loadable-modules"
        )
        qt_loadable.mkdir(parents=True)
        (slicer_root / "lib" / "Slicer-5.10").mkdir(parents=True)
        (slicer_root / "lib").mkdir(exist_ok=True)
        slicer_exec.write_text("#!/bin/sh\n", encoding="utf-8")
        slicer_exec.chmod(0o755)

        paths = _slicer_runtime_library_paths(slicer_exec)
        self.assertIn((slicer_root / "lib" / "Slicer-5.10").resolve(), paths)
        self.assertIn(qt_loadable.resolve(), paths)
        self.assertIn(qt_loadable.parent.resolve(), paths)

    def test_resolve_slicer_launcher_prefers_run_slicer_sh_when_present(self) -> None:
        from tractography.wma import _resolve_slicer_launcher

        software_root = self.tmp_path / "software"
        slicer_exec = software_root / "Slicer-5.10.0-linux-amd64" / "Slicer"
        slicer_exec.parent.mkdir(parents=True)
        slicer_exec.write_text("#!/bin/sh\n", encoding="utf-8")
        launcher = software_root / "run-slicer.sh"
        launcher.write_text("#!/bin/sh\n", encoding="utf-8")

        self.assertEqual(_resolve_slicer_launcher(slicer_exec), launcher.resolve())

    def test_runtime_display_prefers_explicit_env_then_display(self) -> None:
        from tractography.wma import _resolve_runtime_display

        with mock.patch.dict(os.environ, {"DISPLAY": ":99"}, clear=True):
            self.assertEqual(_resolve_runtime_display(), ":99")
        with mock.patch.dict(os.environ, {"DISPLAY": ":99", "SLICERDDSURFER_DISPLAY": ":88"}, clear=True):
            self.assertEqual(_resolve_runtime_display(), ":88")


if __name__ == "__main__":
    unittest.main()
