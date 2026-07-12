from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from shared.module_logic import SharedLogicMixin, _ensure_torch_via_extension, _release_version


class SharedModuleLogicTest(unittest.TestCase):
    def test_release_version_handles_torch_build_suffix(self) -> None:
        self.assertEqual(_release_version("2.2.2+cpu"), (2, 2, 2))
        self.assertLess(_release_version("1.8.1+cpu"), _release_version("2.0.0"))

    def test_old_installed_torch_is_rejected_before_inference(self) -> None:
        fake_torch = types.ModuleType("torch")
        fake_torch.__version__ = "1.8.1+cpu"

        fake_utils = types.ModuleType("PyTorchUtils")

        class FakeTorchLogic:
            @staticmethod
            def torchInstalled() -> bool:
                return True

        fake_utils.PyTorchUtilsLogic = FakeTorchLogic
        with patch.dict(sys.modules, {"torch": fake_torch, "PyTorchUtils": fake_utils}):
            with self.assertRaisesRegex(RuntimeError, r"requires torch>=2\.0\.0"):
                _ensure_torch_via_extension()

    def test_missing_model_assets_do_not_block_logic_initialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            asset_root = Path(tmp) / "model-assets"
            candidates = {
                "Resources/Data/template": asset_root / "Resources" / "Data" / "template",
                "Resources/Data/ckpts": asset_root / "Resources" / "Data" / "ckpts",
                "Resources/Data/100HCP-population-mean-T2.nii.gz": (
                    asset_root / "Resources" / "Data" / "100HCP-population-mean-T2.nii.gz"
                ),
            }

            def fake_candidates(relative: str, **_kwargs):
                return (candidates[relative],)

            class DummyLogic(SharedLogicMixin):
                pass

            with (
                patch("shared.module_logic.model_asset_candidates", side_effect=fake_candidates),
                patch.dict(
                    os.environ,
                    {
                        "DDSURFER_TEMPLATE_DIR": "",
                        "DDSURFER_CHECKPOINT_DIR": "",
                        "DDSURFER_REGISTRATION_ATLAS": "",
                    },
                ),
            ):
                logic = DummyLogic()
                logic._initialize_shared_logic_state()

            self.assertEqual(logic.template_dir, candidates["Resources/Data/template"])
            self.assertEqual(logic.checkpoint_root, candidates["Resources/Data/ckpts"])
            self.assertEqual(
                logic.registration_atlas,
                candidates["Resources/Data/100HCP-population-mean-T2.nii.gz"],
            )


if __name__ == "__main__":
    unittest.main()
