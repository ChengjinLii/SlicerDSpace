from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from shared.environment import DependencySpec, EnvironmentDoctorConfig, _check_spec, run_environment_doctor


REPO_ROOT = Path(__file__).resolve().parents[2]


class EnvironmentDoctorDiscoveryTest(unittest.TestCase):
    def _make_mrtrix_bin(self, root: Path) -> Path:
        bin_dir = root / "mrtrix_bin"
        bin_dir.mkdir(parents=True)
        for command in ("mrconvert", "dwi2response", "dwi2fod", "mtnormalise", "tckgen", "tcksift2"):
            command_path = bin_dir / command
            command_path.write_text("#!/usr/bin/env sh\n", encoding="utf-8")
            command_path.chmod(0o755)
        return bin_dir

    def _make_freesurfer_home(self, root: Path) -> Path:
        freesurfer_home = root / "software" / "freesurfer"
        bin_dir = freesurfer_home / "bin"
        bin_dir.mkdir(parents=True)
        (freesurfer_home / "subjects" / "fsaverage").mkdir(parents=True)
        for command in (
            "recon-all",
            "mris_sphere",
            "mris_curvature",
            "mris_inflate",
            "mris_register",
            "mri_label2label",
            "mri_surf2surf",
            "mri_annotation2label",
            "mri_segstats",
        ):
            command_path = bin_dir / command
            command_path.write_text("#!/usr/bin/env sh\n", encoding="utf-8")
            command_path.chmod(0o755)
        return freesurfer_home

    def test_user_path_source_overrides_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            user_bin = self._make_mrtrix_bin(tmp_path / "user")
            env_bin = self._make_mrtrix_bin(tmp_path / "env")
            old_env = os.environ.get("SLICERDDSURFER_MRTRIX_BIN_DIR")
            os.environ["SLICERDDSURFER_MRTRIX_BIN_DIR"] = env_bin.as_posix()
            try:
                result = run_environment_doctor(
                    EnvironmentDoctorConfig(
                        targets=("tractography",),
                        repo_root=REPO_ROOT,
                        tractography_backend="csd_act",
                        mrtrix_bin_dir=user_bin,
                    )
                )
            finally:
                if old_env is None:
                    os.environ.pop("SLICERDDSURFER_MRTRIX_BIN_DIR", None)
                else:
                    os.environ["SLICERDDSURFER_MRTRIX_BIN_DIR"] = old_env

            mrconvert = next(item for item in result.statuses if item.key == "command:mrconvert")
            self.assertEqual(mrconvert.status, "available")
            self.assertEqual(mrconvert.details["detected_source"], "user setting")
            self.assertTrue(mrconvert.details["resolved"].startswith(user_bin.as_posix()))

    def test_environment_path_source_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_bin = self._make_mrtrix_bin(Path(tmp))
            old_env = os.environ.get("SLICERDDSURFER_MRTRIX_BIN_DIR")
            os.environ["SLICERDDSURFER_MRTRIX_BIN_DIR"] = env_bin.as_posix()
            try:
                result = run_environment_doctor(
                    EnvironmentDoctorConfig(
                        targets=("tractography",),
                        repo_root=REPO_ROOT,
                        tractography_backend="csd_act",
                    )
                )
            finally:
                if old_env is None:
                    os.environ.pop("SLICERDDSURFER_MRTRIX_BIN_DIR", None)
                else:
                    os.environ["SLICERDDSURFER_MRTRIX_BIN_DIR"] = old_env

            mrconvert = next(item for item in result.statuses if item.key == "command:mrconvert")
            self.assertEqual(mrconvert.status, "available")
            self.assertEqual(mrconvert.details["detected_source"], "env:SLICERDDSURFER_MRTRIX_BIN_DIR")

    def test_path_source_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path_bin = self._make_mrtrix_bin(Path(tmp))
            old_path = os.environ.get("PATH", "")
            old_env = os.environ.get("SLICERDDSURFER_MRTRIX_BIN_DIR")
            os.environ.pop("SLICERDDSURFER_MRTRIX_BIN_DIR", None)
            os.environ["PATH"] = path_bin.as_posix() + os.pathsep + old_path
            try:
                result = run_environment_doctor(
                    EnvironmentDoctorConfig(
                        targets=("tractography",),
                        repo_root=REPO_ROOT,
                        tractography_backend="csd_act",
                    )
                )
            finally:
                os.environ["PATH"] = old_path
                if old_env is not None:
                    os.environ["SLICERDDSURFER_MRTRIX_BIN_DIR"] = old_env

            mrconvert = next(item for item in result.statuses if item.key == "command:mrconvert")
            self.assertEqual(mrconvert.status, "available")
            self.assertEqual(mrconvert.details["detected_source"], "PATH")

    def test_common_path_source_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            common_bin = Path(tmp) / "common"
            common_bin.mkdir()
            fake_tool = common_bin / "fake_tool"
            fake_tool.write_text("#!/usr/bin/env sh\n", encoding="utf-8")
            fake_tool.chmod(0o755)
            status = _check_spec(
                DependencySpec(
                    key="command:fake_tool",
                    kind="command",
                    label="fake_tool",
                    required=True,
                    targets=("fake",),
                    command="fake_tool",
                    install_group="fake",
                    common_paths=(common_bin,),
                ),
                "Linux",
            )
            self.assertEqual(status.status, "available")
            self.assertEqual(status.details["detected_source"], "common path")

    def test_windows_common_path_checks_executable_suffixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            common_bin = Path(tmp) / "common"
            common_bin.mkdir()
            fake_tool = common_bin / "fake_tool.exe"
            fake_tool.write_text("", encoding="utf-8")
            status = _check_spec(
                DependencySpec(
                    key="command:fake_tool",
                    kind="command",
                    label="fake_tool",
                    required=True,
                    targets=("fake",),
                    command="fake_tool",
                    install_group="fake",
                    common_paths=(common_bin,),
                ),
                "Windows",
            )
            self.assertEqual(status.status, "available")
            self.assertEqual(status.details["detected_source"], "common path")
            self.assertEqual(status.details["resolved"], fake_tool.as_posix())
            self.assertIn(fake_tool.as_posix(), status.details["checked_locations"])

    def test_python_install_requirement_survives_default_python_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing_python = Path(tmp) / "missing-python"
            result = run_environment_doctor(
                EnvironmentDoctorConfig(
                    targets=("bundles",),
                    repo_root=REPO_ROOT,
                    python_executable=missing_python,
                )
            )
            tract_querier = next(item for item in result.statuses if item.key == "python:tract_querier")
            self.assertEqual(
                tract_querier.details["install_requirement"],
                "git+https://github.com/demianw/tract_querier.git",
            )
            self.assertIn("git+https://github.com/demianw/tract_querier.git", result.missing_python_packages)

    def test_freesurfer_home_is_discovered_from_local_software_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            freesurfer_home = self._make_freesurfer_home(tmp_path)
            old_home = os.environ.get("HOME")
            old_user = os.environ.get("USER")
            old_fs_home = os.environ.get("FREESURFER_HOME")
            old_slicer_fs_home = os.environ.get("SLICERDDSURFER_FREESURFER_HOME")
            os.environ["HOME"] = tmp_path.as_posix()
            os.environ["USER"] = "slicerddsurfer-test-user"
            os.environ.pop("FREESURFER_HOME", None)
            os.environ.pop("SLICERDDSURFER_FREESURFER_HOME", None)
            try:
                result = run_environment_doctor(
                    EnvironmentDoctorConfig(
                        targets=("surface_postprocess",),
                        repo_root=REPO_ROOT,
                    )
                )
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home
                if old_user is None:
                    os.environ.pop("USER", None)
                else:
                    os.environ["USER"] = old_user
                if old_fs_home is None:
                    os.environ.pop("FREESURFER_HOME", None)
                else:
                    os.environ["FREESURFER_HOME"] = old_fs_home
                if old_slicer_fs_home is None:
                    os.environ.pop("SLICERDDSURFER_FREESURFER_HOME", None)
                else:
                    os.environ["SLICERDDSURFER_FREESURFER_HOME"] = old_slicer_fs_home

            freesurfer_env = next(item for item in result.statuses if item.key == "env:freesurfer_home")
            recon_all = next(item for item in result.statuses if item.key == "command:recon-all")
            rtree = next(item for item in result.statuses if item.key == "python:rtree")
            self.assertEqual(freesurfer_env.status, "available")
            self.assertEqual(freesurfer_env.details["detected_source"], "common path")
            self.assertEqual(freesurfer_env.details["resolved"], freesurfer_home.as_posix())
            self.assertEqual(recon_all.status, "available")
            self.assertEqual(recon_all.details["detected_source"], "common path")
            self.assertTrue(recon_all.details["resolved"].startswith((freesurfer_home / "bin").as_posix()))
            self.assertTrue(rtree.required)
            self.assertEqual(rtree.details["package"], "rtree")

    def test_cli_dependency_config_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            subject_root = tmp_path / "subject"
            subject_root.mkdir()
            user_bin = self._make_mrtrix_bin(tmp_path)
            config_path = tmp_path / "deps.json"
            first = subprocess.run(
                [
                    sys.executable,
                    (REPO_ROOT / "run_subject_pipeline.py").as_posix(),
                    "--subject-root",
                    subject_root.as_posix(),
                    "--targets",
                    "tractography",
                    "--doctor",
                    "--mrtrix-bin-dir",
                    user_bin.as_posix(),
                    "--save-dependency-config",
                    config_path.as_posix(),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Dependency config written", first.stderr)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["external_dependencies"]["mrtrix_bin_dir"], user_bin.as_posix())

            second = subprocess.run(
                [
                    sys.executable,
                    (REPO_ROOT / "run_subject_pipeline.py").as_posix(),
                    "--subject-root",
                    subject_root.as_posix(),
                    "--targets",
                    "tractography",
                    "--doctor",
                    "--dependency-config",
                    config_path.as_posix(),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(second.stdout)
            mrconvert = next(
                item for item in payload["environment"]["dependencies"] if item["key"] == "command:mrconvert"
            )
            self.assertEqual(mrconvert["details"]["detected_source"], "user setting")


if __name__ == "__main__":
    unittest.main()
