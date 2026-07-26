from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from shared.environment import (
    DependencySpec,
    EnvironmentDoctorConfig,
    _apply_default_python,
    _check_spec,
    _common_command_dirs,
    _common_freesurfer_homes,
    _common_slicer_executables,
    _parse_json_probe_output,
    _python_requirement_details,
    build_dependency_specs,
    run_environment_doctor,
    write_environment_report,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class EnvironmentDoctorDiscoveryTest(unittest.TestCase):
    def test_default_pythonpath_does_not_leak_into_an_external_python(self) -> None:
        default_python = Path(sys.executable).resolve()
        external_python = default_python.with_name("external-python.exe")
        default_packages = default_python.parent / "slicer-packages"
        external_packages = external_python.parent / "tractcloud-src"
        specs = (
            DependencySpec(
                key="python:default",
                kind="python",
                label="default",
                required=True,
                targets=("validation",),
                python_import="default_package",
            ),
            DependencySpec(
                key="python:external",
                kind="python",
                label="external",
                required=True,
                targets=("tractcloud",),
                python_import="tractcloud",
                python_executable=external_python,
                python_path_entries=(external_packages,),
            ),
        )

        default_spec, external_spec = _apply_default_python(
            specs,
            default_python,
            (default_packages,),
        )

        self.assertEqual(default_spec.python_executable, default_python)
        self.assertEqual(default_spec.python_path_entries, (default_packages.resolve(),))
        self.assertEqual(external_spec.python_executable, external_python.resolve())
        self.assertEqual(external_spec.python_path_entries, (external_packages,))

    def test_python_probe_prioritizes_configured_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            (package_root / "doctor_external_package.py").write_text(
                "VALUE = 'external'\n",
                encoding="utf-8",
            )
            status = _check_spec(
                DependencySpec(
                    key="python:doctor_external_package",
                    kind="python",
                    label="doctor_external_package",
                    required=True,
                    targets=("validation",),
                    python_import="doctor_external_package",
                    python_package="",
                    python_executable=Path(sys.executable),
                    python_path_entries=(package_root,),
                ),
                sys.platform,
            )

        self.assertEqual(status.status, "available")
        self.assertEqual(status.details["pythonpath"], [package_root.as_posix()])

    def test_python_version_requirement_rejects_old_torch(self) -> None:
        specifier, satisfied = _python_requirement_details("torch>=2.0.0", "1.8.1+cpu")
        self.assertEqual(specifier, ">=2.0.0")
        self.assertFalse(satisfied)
        self.assertTrue(_python_requirement_details("torch>=2.0.0", "2.2.2+cpu")[1])

    def test_python_probe_ignores_launcher_startup_notice(self) -> None:
        self.assertEqual(
            _parse_json_probe_output('No module named \'logic\'\n{"available": true}\n'),
            {"available": True},
        )

    def _make_mrtrix_bin(self, root: Path) -> Path:
        bin_dir = root / "mrtrix_bin"
        bin_dir.mkdir(parents=True)
        for command in ("mrconvert", "dwi2response", "dwi2fod", "mtnormalise", "tckgen", "tcksift2"):
            command_path = bin_dir / command
            command_path.write_text("#!/usr/bin/env sh\n", encoding="utf-8")
            command_path.chmod(0o755)
        return bin_dir

    def _make_windows_mrtrix_bin(self, root: Path) -> Path:
        bin_dir = root / "MRtrix3" / "bin"
        bin_dir.mkdir(parents=True)
        for command in ("mrconvert", "dwi2response", "dwi2fod", "mtnormalise", "tckgen", "tcksift2"):
            command_path = bin_dir / f"{command}.exe"
            command_path.write_text("", encoding="utf-8")
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

    def test_fsl_preprocessing_requires_corrected_dwi_mask_command(self) -> None:
        specs = build_dependency_specs(
            EnvironmentDoctorConfig(
                targets=("preprocessing",),
                repo_root=REPO_ROOT,
                preprocessing_backend="mrtrix_fsl",
            )
        )
        self.assertIn("command:dwi2mask", {spec.key for spec in specs})

    def test_dti_runtime_requires_real_slicer_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_python = Path(tmp) / "python-without-slicer"
            fake_python.write_text(
                f"#!{sys.executable}\nprint('{{\"available\": false}}')\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            result = run_environment_doctor(
                EnvironmentDoctorConfig(
                    targets=("microstructure", "tractography"),
                    repo_root=REPO_ROOT,
                    python_executable=fake_python,
                    tractography_backend="dti_det",
                )
            )

        runtime = next(item for item in result.statuses if item.key == "python:slicer.util")
        self.assertEqual(runtime.status, "missing")
        self.assertEqual(runtime.details["package"], "")
        self.assertIn("slicer-runtime", result.missing_external_groups)
        self.assertNotIn("slicer.util", result.missing_python_packages)
        self.assertEqual(set(result.blocked_targets), {"microstructure", "tractography"})

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

    def test_platform_override_is_reported_and_used_for_windows_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            user_bin = self._make_windows_mrtrix_bin(tmp_path)
            result = run_environment_doctor(
                EnvironmentDoctorConfig(
                    targets=("tractography",),
                    repo_root=REPO_ROOT,
                    platform_name="Windows",
                    tractography_backend="csd_act",
                    mrtrix_bin_dir=user_bin,
                )
            )
            self.assertEqual(result.platform, "Windows")
            self.assertTrue(result.host_platform)
            mrconvert = next(item for item in result.statuses if item.key == "command:mrconvert")
            self.assertEqual(mrconvert.status, "available")
            self.assertEqual(mrconvert.details["detected_source"], "user setting")
            self.assertEqual(mrconvert.details["resolved"], (user_bin / "mrconvert.exe").as_posix())
            self.assertIn((user_bin / "mrconvert.exe").as_posix(), mrconvert.details["checked_locations"])

            written = write_environment_report(result, tmp_path / "report")
            profile = json.loads(written["profile"].read_text(encoding="utf-8"))
            self.assertEqual(profile["platform"], "Windows")
            self.assertEqual(profile["host_platform"], result.host_platform)
            self.assertTrue(profile["portability_policy"]["revalidate_after_import"])

    def test_common_platform_paths_include_macos_and_windows_runtime_locations(self) -> None:
        mac_slicers = {path.as_posix() for path in _common_slicer_executables("Darwin")}
        win_slicers = {path.as_posix() for path in _common_slicer_executables("Windows")}
        mac_mrtrix = {path.as_posix() for path in _common_command_dirs("mrtrix", "Darwin")}
        win_mrtrix = {path.as_posix() for path in _common_command_dirs("mrtrix", "Windows")}
        win_fsl = {path.as_posix() for path in _common_command_dirs("fsl", "Windows")}
        mac_freesurfer = {path.as_posix() for path in _common_freesurfer_homes("Darwin")}
        win_freesurfer = {path.as_posix() for path in _common_freesurfer_homes("Windows")}

        self.assertIn("/Applications/Slicer.app/Contents/MacOS/Slicer", mac_slicers)
        self.assertIn("C:/Program Files/Slicer 5.10.0/Slicer.exe", win_slicers)
        self.assertIn("/Applications/MRtrix3.app/Contents/bin", mac_mrtrix)
        self.assertIn("C:/Program Files/MRtrix3/bin", win_mrtrix)
        self.assertIn("C:/Program Files/FSL/bin", win_fsl)
        self.assertIn("/Applications/FreeSurfer", mac_freesurfer)
        self.assertIn("C:/Program Files/FreeSurfer", win_freesurfer)

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
                    "--no-user-config",
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
                    "--no-user-config",
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

    def test_environment_doctor_resolves_conda_environment_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected_python = root / "envs" / "slicerdsurfer" / "bin" / "python"
            expected_python.parent.mkdir(parents=True)
            expected_python.write_text("", encoding="utf-8")
            conda = root / "conda"
            conda.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "assert sys.argv[1:4] == ['run', '-n', 'slicerdsurfer']\n"
                f"print({expected_python.as_posix()!r})\n",
                encoding="utf-8",
            )
            conda.chmod(0o755)

            result = run_environment_doctor(
                EnvironmentDoctorConfig(
                    targets=("validation",),
                    repo_root=REPO_ROOT,
                    python_environment="slicerdsurfer",
                    conda_executable=conda,
                )
            )

            self.assertEqual(result.python_executable, expected_python.resolve().as_posix())


if __name__ == "__main__":
    unittest.main()
