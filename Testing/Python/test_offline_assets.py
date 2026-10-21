"""Offline import trusts only the bundled manifest and never downloads."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.verify_offline_assets import verify_offline_assets


class OfflineAssetsTests(unittest.TestCase):
    def test_missing_models_fail_without_network_or_writing_resources(self):
        with tempfile.TemporaryDirectory() as temp, patch("urllib.request.urlopen") as network:
            root = Path(temp)
            result = verify_offline_assets(root, ("segmentation",))
            self.assertEqual(result["status"], "failed")
            self.assertTrue(result["checks"]["segmentation"]["missing"])
            self.assertEqual(list(root.iterdir()), [])
            network.assert_not_called()

    def test_selected_profiles_are_hash_checked_using_bundled_manifest(self):
        with tempfile.TemporaryDirectory() as temp, \
                patch("scripts.download_model_assets.load_manifest", return_value={}) as load, \
                patch("scripts.download_model_assets.resolve_asset_plan", return_value="selected-plan") as resolve, \
                patch("scripts.download_model_assets.verify_asset_plan", return_value={"ok": True}) as verify:
            result = verify_offline_assets(Path(temp), ("segmentation",))
            self.assertEqual(result["status"], "completed")
            self.assertEqual(load.call_args.args[0].name, "assets_manifest.json")
            resolve.assert_called_once_with({}, "segmentation")
            verify.assert_called_once_with(Path(temp), "selected-plan", check_hashes=True)


if __name__ == "__main__":
    unittest.main()
