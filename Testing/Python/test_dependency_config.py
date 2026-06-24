from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from shared.dependency_config import (
    DEPENDENCY_CONFIG_KEYS,
    UI_DEPENDENCY_PATHS,
    apply_dependency_config,
    load_dependency_config,
    write_dependency_config,
)


class DependencyConfigTest(unittest.TestCase):
    def test_loads_nested_external_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deps.json"
            path.write_text(
                json.dumps(
                    {
                        "kind": "slicerdsurfer_dependency_profile",
                        "external_dependencies": {
                            "python_executable": "/opt/Slicer/bin/PythonSlicer",
                            "python_environment": "slicerdsurfer",
                            "conda_executable": "/opt/conda/bin/conda",
                            "mrtrix_bin_dir": "/opt/mrtrix3/bin",
                            "tractcloud_root": "/opt/TractCloud",
                            "unknown_key": "/ignored",
                        },
                    }
                ),
                encoding="utf-8",
            )
            loaded = load_dependency_config(path)
            self.assertEqual(loaded["python_executable"], Path("/opt/Slicer/bin/PythonSlicer"))
            self.assertEqual(loaded["python_environment"], "slicerdsurfer")
            self.assertEqual(loaded["conda_executable"], Path("/opt/conda/bin/conda"))
            self.assertEqual(loaded["mrtrix_bin_dir"], Path("/opt/mrtrix3/bin"))
            self.assertEqual(loaded["tractcloud_root"], Path("/opt/TractCloud"))
            self.assertNotIn("unknown_key", loaded)

    def test_apply_does_not_override_explicit_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deps.json"
            path.write_text(
                json.dumps({"external_dependencies": {"mrtrix_bin_dir": "/from/config", "wma_root": "/from/config/wma"}}),
                encoding="utf-8",
            )
            args = Namespace(dependency_config=path, mrtrix_bin_dir=Path("/explicit"), wma_root=None)
            apply_dependency_config(args, args.dependency_config)
            self.assertEqual(args.mrtrix_bin_dir, Path("/explicit"))
            self.assertEqual(args.wma_root, Path("/from/config/wma"))

    def test_write_uses_shared_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = Namespace(
                python_executable=Path("/opt/Slicer/bin/PythonSlicer"),
                python_environment="slicerdsurfer",
                conda_executable=None,
                mrtrix_bin_dir=Path("/opt/mrtrix3/bin"),
                wma_root=None,
            )
            path = write_dependency_config(args, Path(tmp) / "deps.json")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["kind"], "slicerdsurfer_dependency_config")
            self.assertEqual(payload["version"], 1)
            self.assertEqual(
                payload["external_dependencies"],
                {
                    "python_executable": "/opt/Slicer/bin/PythonSlicer",
                    "python_environment": "slicerdsurfer",
                    "mrtrix_bin_dir": "/opt/mrtrix3/bin",
                },
            )

    def test_ui_dependency_paths_are_config_keys(self) -> None:
        config_keys = set(DEPENDENCY_CONFIG_KEYS)
        ui_ids = {item["id"] for item in UI_DEPENDENCY_PATHS}
        self.assertTrue(ui_ids)
        self.assertTrue(ui_ids.issubset(config_keys))


if __name__ == "__main__":
    unittest.main()
