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
from vtp_fixture import vtp_lines


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
index=1
while [ "$index" -le 73 ]; do
  printf 'VTP_FIXTURE\n' > "$out/$case_id/AnatomicalTracts/T_$(printf '%03d' "$index").vtp"
  index=$((index + 1))
done
exit 0
""".replace("VTP_FIXTURE", vtp_lines(1)),
            encoding="utf-8",
        )
        self.wma_script.chmod(0o755)
        (self.wma_root / "VENDORED_SOURCE.md").write_text(
            "# Vendored source\n\n"
            "- Repository: https://github.com/SlicerDMRI/whitematteranalysis\n"
            "- Commit: 0123456789abcdef\n"
            "- Date added: 2026-07-25\n",
            encoding="utf-8",
        )
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
        self.assertEqual(result.status, "planned")
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
        self.assertEqual(manifest["backend"]["source"]["commit"], "0123456789abcdef")
        self.assertEqual(manifest["backend"]["source"]["date_added"], "2026-07-25")
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

    def test_wma_auto_discovery_excludes_saf_and_bundle_outputs(self) -> None:
        from shared.orchestrator import _resolve_wma_input_tractography

        subject_root = self.tmp_path / "subject"
        tractography_root = subject_root / "outputs" / "04_tractography"
        saf = tractography_root / "saf" / "SAF.vtk"
        bundle = tractography_root / "bundles" / "tractcloud" / "bundle.vtp"
        saf.parent.mkdir(parents=True)
        bundle.parent.mkdir(parents=True)
        saf.write_text("", encoding="utf-8")
        bundle.write_text("", encoding="utf-8")

        self.assertIsNone(_resolve_wma_input_tractography(subject_root, None))

        whole_brain = tractography_root / "cache" / "exports" / "whole_brain.vtk"
        whole_brain.parent.mkdir(parents=True)
        whole_brain.write_text("", encoding="utf-8")
        self.assertIsNone(_resolve_wma_input_tractography(subject_root, None))

        ukf_whole_brain = tractography_root / "cache" / "exports" / "subject_ukf_whole_brain.vtk"
        ukf_whole_brain.write_text("", encoding="utf-8")
        self.assertEqual(
            _resolve_wma_input_tractography(subject_root, None),
            ukf_whole_brain.resolve(),
        )

    def test_tck_input_is_converted_before_wma_execution(self) -> None:
        from tractography import WMAOrgAtlasConfig, run_wma_org_atlas

        tck_input = self.tmp_path / "whole_brain.tck"
        tck_input.write_text("tck", encoding="utf-8")
        mrtrix_bin = self.tmp_path / "mrtrix" / "bin"
        mrtrix_bin.mkdir(parents=True)
        tckconvert = mrtrix_bin / "tckconvert"
        tckconvert.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib, sys\n"
            "pathlib.Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)\n"
            "pathlib.Path(sys.argv[2]).write_text('# vtk DataFile Version 3.0\\n')\n",
            encoding="utf-8",
        )
        tckconvert.chmod(0o755)

        result = run_wma_org_atlas(
            WMAOrgAtlasConfig(
                subject_id="100307",
                input_tractography=tck_input,
                atlas_dir=self.atlas_dir,
                output_dir=self.output_dir,
                slicer_executable=self.slicer_executable,
                wma_root=self.wma_root,
                mrtrix_bin_dir=mrtrix_bin,
                execute=True,
            )
        )

        self.assertEqual(result.status, "completed")
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertTrue(manifest["input_conversion"]["required"])
        prepared_input = Path(manifest["prepared_input_tractography"])
        self.assertEqual(prepared_input.suffix, ".vtk")
        self.assertTrue(prepared_input.is_file())
        self.assertIn(prepared_input.as_posix(), result.command)

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
        self.assertEqual(result.status, "completed")
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
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.return_code, 0)
        qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
        self.assertEqual(qc["status"], "failed")
        self.assertIn("complete AnatomicalTracts output", qc["error"])
        self.assertTrue(Path(qc["logs"]["stdout"]).is_file())
        self.assertTrue(Path(qc["logs"]["stderr"]).is_file())

    def test_execute_true_records_nonzero_backend_failure_before_returning(self) -> None:
        from tractography import WMAOrgAtlasConfig, run_wma_org_atlas

        self.wma_script.write_text(
            "#!/bin/sh\n"
            "printf 'backend failed\\n' >&2\n"
            "exit 7\n",
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

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.return_code, 7)
        qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
        self.assertEqual(qc["status"], "failed")
        self.assertIn("returned non-zero exit status 7", qc["error"])
        self.assertIn("backend failed", Path(qc["logs"]["stderr"]).read_text(encoding="utf-8"))

    def test_keyboard_interrupt_is_persisted_as_failed_qc(self) -> None:
        from tractography import WMAOrgAtlasConfig, run_wma_org_atlas

        with mock.patch("tractography.wma.subprocess.run", side_effect=KeyboardInterrupt):
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
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.return_code, 130)
        self.assertEqual(qc["error"], "Interrupted by user.")
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["return_code"], 130)

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
        self.assertEqual(result.status, "partial_failed")
        self.assertEqual(qc["status"], "partial_failed")
        self.assertEqual(qc["output_summary"]["initial_cluster_count"], 1)
        self.assertEqual(qc["output_summary"]["anatomical_tract_count"], 0)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "partial_failed")
        self.assertIn("runtime_seconds", manifest)

    def test_execute_true_marks_partial_failed_below_required_tract_count(self) -> None:
        from tractography import WMAOrgAtlasConfig, run_wma_org_atlas

        script = self.wma_script.read_text(encoding="utf-8").replace(
            'while [ "$index" -le 73 ]; do',
            'while [ "$index" -le 72 ]; do',
        )
        self.wma_script.write_text(script, encoding="utf-8")
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
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(result.status, "partial_failed")
        self.assertEqual(qc["output_summary"]["anatomical_tract_count"], 72)
        self.assertEqual(qc["acceptance_criteria"]["minimum_anatomical_tract_count"], 73)
        self.assertIn("expected at least 73 files", qc["error"])
        self.assertEqual(manifest["error"], qc["error"])

    def test_execute_true_rejects_atlas_filenames_when_most_tracts_are_empty(self) -> None:
        from tractography import WMAOrgAtlasConfig, run_wma_org_atlas

        script = self.wma_script.read_text(encoding="utf-8").replace(
            vtp_lines(1),
            vtp_lines(0),
        )
        self.wma_script.write_text(script, encoding="utf-8")
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
        self.assertEqual(result.status, "partial_failed")
        self.assertEqual(qc["output_summary"]["anatomical_tract_nonempty_count"], 0)
        self.assertEqual(qc["acceptance_criteria"]["minimum_nonempty_anatomical_tract_count"], 55)
        self.assertIn("under-populated", qc["error"])

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

    def test_runtime_library_paths_discover_installed_slicer_version(self) -> None:
        from tractography.wma import _slicer_runtime_library_paths

        slicer_root = self.tmp_path / "SlicerRoot56"
        slicer_exec = slicer_root / "Slicer.exe"
        slicer_library = slicer_root / "lib" / "Slicer-5.6"
        qt_scripted = (
            slicer_root
            / "slicer.org"
            / "Extensions-32448"
            / "SlicerDMRI"
            / "lib"
            / "Slicer-5.6"
            / "qt-scripted-modules"
        )
        slicer_library.mkdir(parents=True)
        qt_scripted.mkdir(parents=True)
        slicer_exec.write_text("", encoding="utf-8")

        paths = _slicer_runtime_library_paths(slicer_exec)

        self.assertIn(slicer_library.resolve(), paths)
        self.assertIn(qt_scripted.resolve(), paths)
        self.assertIn(qt_scripted.parent.resolve(), paths)

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

    def test_summarize_wma_outputs_includes_registration_progress(self) -> None:
        from tractography.wma import summarize_wma_outputs

        case_id = self.tractography.stem
        registration_dir = self.output_dir / case_id / "TractRegistration" / case_id / "iteration_00001_sigma_00030"
        registration_dir.mkdir(parents=True)
        progress = registration_dir.parent / "progress.txt"
        progress.write_text(
            (
                "Beginning registration. Total iterations will be: 10\n"
                "Done iteration 1 / 10. Percent finished approx: 0.57. Time: 11:06:08. Minutes Elapsed: 2.37\n"
                "Done iteration 2 / 10. Percent finished approx: 1.14. Time: 11:08:31. Minutes Elapsed: 2.38\n"
            ),
            encoding="utf-8",
        )

        summary = summarize_wma_outputs(self.output_dir, self.tractography)

        self.assertTrue(summary["registration_dir_exists"])
        self.assertTrue(summary["progress_file_exists"])
        self.assertEqual(summary["registration_iteration_dir_count"], 1)
        self.assertEqual(summary["progress"]["completed_iterations"], 2)
        self.assertEqual(summary["progress"]["total_iterations"], 10)
        self.assertAlmostEqual(summary["progress"]["latest_percent_finished"], 1.14)

    def test_summarize_wma_outputs_distinguishes_empty_anatomical_tracts(self) -> None:
        from tractography.wma import summarize_wma_outputs

        anatomical_dir = self.output_dir / self.tractography.stem / "AnatomicalTracts"
        anatomical_dir.mkdir(parents=True)
        (anatomical_dir / "T_AF_left.vtp").write_text(
            vtp_lines(3),
            encoding="utf-8",
        )
        (anatomical_dir / "T_AF_right.vtp").write_text(
            vtp_lines(0),
            encoding="utf-8",
        )

        summary = summarize_wma_outputs(self.output_dir, self.tractography)

        self.assertEqual(summary["anatomical_tract_count"], 2)
        self.assertEqual(summary["anatomical_tract_readable_count"], 2)
        self.assertEqual(summary["anatomical_tract_nonempty_count"], 1)
        self.assertEqual(summary["anatomical_streamline_count"], 3)
        self.assertEqual(summary["anatomical_empty_tracts"], ["T_AF_right.vtp"])


if __name__ == "__main__":
    unittest.main()
