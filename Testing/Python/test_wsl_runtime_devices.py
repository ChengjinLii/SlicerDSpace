"""Device plans/bridges are tested here, not actual Windows/WSL computation."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.wsl.configure_device import cuda_available, device_plan, configure
from shared.wsl_bridge import bridge_config, preprocessing_launcher


class WslRuntimeDeviceTest(unittest.TestCase):
    def test_auto_selects_cuda_only_with_a_visible_gpu(self):
        gpu = device_plan("auto", True)
        self.assertEqual(gpu["resolved"], "cuda")
        self.assertIn("+cu126", gpu["torch_requirement"])
        self.assertIn("fsl-eddy-cuda", gpu["fsl_cuda_package"])
        cpu = device_plan("auto", False)
        self.assertEqual(cpu["resolved"], "cpu")
        self.assertIsNone(cpu["fsl_cuda_package"])
        self.assertIn("+cpu", cpu["torch_requirement"])

    def test_explicit_cpu_avoids_gpu_probe_and_cuda_is_strict(self):
        with patch("scripts.wsl.configure_device.cuda_available", side_effect=AssertionError("No CPU probe")):
            self.assertEqual(device_plan("cpu")["resolved"], "cpu")
            self.assertEqual(device_plan("cpu", True)["resolved"], "cpu")
        with self.assertRaisesRegex(RuntimeError, "no CPU fallback"):
            device_plan("cuda", False)
        with self.assertRaises(ValueError):
            device_plan("mps", True)

    def test_hidden_gpus_do_not_start_discovery(self):
        for visible in ("", "-1"):
            with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": visible}), patch("subprocess.run") as run:
                self.assertFalse(cuda_available())
                run.assert_not_called()

    def test_driver_errors_are_not_silent_cpu_fallbacks(self):
        with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": "0"}), \
                patch("scripts.wsl.configure_device.shutil.which", return_value="nvidia-smi"), \
                patch("subprocess.run", return_value=SimpleNamespace(returncode=1, stderr="driver mismatch")):
            with self.assertRaisesRegex(RuntimeError, "discovery failed"):
                cuda_available()

    def test_installed_cuda_wheel_requires_real_cuda_allocation_probe(self):
        plan = device_plan("cuda", True)
        actual = {"version": "2.11.0+cu126", "cuda_available": True, "cuda_version": "12.6"}
        with patch("subprocess.run", side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(stdout=json.dumps(actual))]) as run:
            result = configure(plan)
            self.assertEqual(result["status"], "ready")
            self.assertIn("torch.empty", run.call_args_list[1].args[0][2])
            self.assertIn("--index-url", run.call_args_list[0].args[0])
        actual["cuda_available"] = False
        with patch("subprocess.run", side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(stdout=json.dumps(actual))]):
            with self.assertRaisesRegex(RuntimeError, "no CPU fallback"):
                configure(plan)


class WslPreprocessingBridgeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def bridge(self, name, argument, distro="Ubuntu"):
        path = self.root / name
        path.write_bytes(b"MZ fixture, never executed")
        Path(str(path) + ".slicerdsurfer-owner").write_text("SlicerDDSurfer WSL bridge v1")
        Path(str(path) + ".conf").write_text(
            f"distribution={distro}\ntarget=/home/user/bin/run-in-runtime\narg={argument}\n", encoding="utf-8-sig")
        return path

    def test_binary_bridge_delegates_policy_to_the_linux_python(self):
        script = self.bridge("dwifslpreproc.exe", "/home/user/runtime/bin/dwifslpreproc")
        python = self.bridge("python.exe", "/home/user/runtime/bin/python")
        record = self.root / "path with spaces" / "eddy_device.json"
        command = [str(script), "D:/data with spaces/in.nii.gz", "D:/out.nii.gz", "-eddy_options", "--nthr=4 --slm=linear"]
        result = preprocessing_launcher(command, record, {})
        self.assertEqual(result[0], str(python))
        self.assertTrue(result[1].endswith("mrtrix_preproc_runner.py"))
        self.assertEqual(result[result.index("--script") + 1], "/home/user/runtime/bin/dwifslpreproc")
        self.assertEqual(result[result.index("--") + 1:], command[1:])
        self.assertEqual(result[result.index("--record") + 1], str(record))

    def test_old_bridge_fails_actionably_instead_of_bypassing_policy(self):
        script = self.bridge("dwifslpreproc", "/home/user/runtime/bin/dwifslpreproc")
        with self.assertRaisesRegex(FileNotFoundError, "rerun scripts/install_deps_windows"):
            preprocessing_launcher([str(script)], self.root / "receipt.json", {})

    def test_mixed_wsl_distributions_and_runtimes_are_rejected(self):
        script = self.bridge("dwifslpreproc.exe", "/home/user/runtime/bin/dwifslpreproc")
        self.bridge("python.exe", "/home/user/runtime/bin/python", "OtherDistro")
        with self.assertRaisesRegex(ValueError, "same distribution and runtime"):
            preprocessing_launcher([str(script)], self.root / "receipt.json", {})
        self.bridge("python.exe", "/other/runtime/bin/python")
        with self.assertRaises(ValueError):
            preprocessing_launcher([str(script)], self.root / "receipt.json", {})

    def test_native_windows_exe_without_bridge_is_not_run_as_python(self):
        path = self.root / "dwifslpreproc.exe"
        path.write_bytes(b"MZ")
        with self.assertRaisesRegex(RuntimeError, "managed WSL bridges"):
            preprocessing_launcher([str(path)], self.root / "receipt.json", {})

    def test_owned_bridge_missing_config_is_an_error(self):
        path = self.bridge("dwifslpreproc.exe", "/home/user/runtime/bin/dwifslpreproc")
        Path(str(path) + ".conf").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "WSL bridge configuration missing"):
            bridge_config(path)

    def test_native_mrtrix_script_retains_same_policy_and_non_mrtrix_fixture_is_unchanged(self):
        path = self.root / "dwifslpreproc"
        path.write_text("from mrtrix3 import app")
        with patch("shutil.which", return_value="/runtime/bin/python"):
            result = preprocessing_launcher([str(path), "input"], self.root / "receipt.json", {})
        self.assertEqual(result[0], "/runtime/bin/python")
        path.write_text("# a contract fixture, not real MRtrix")
        self.assertEqual(preprocessing_launcher([str(path)], self.root / "receipt.json", {}), [str(path)])


if __name__ == "__main__":
    unittest.main()
