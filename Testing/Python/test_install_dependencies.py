from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "install_dependencies.py"


def _load_install_dependencies_module():
    spec = importlib.util.spec_from_file_location("install_dependencies", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class InstallDependenciesProfileTest(unittest.TestCase):
    def test_named_profiles_are_exposed_by_parser(self) -> None:
        module = _load_install_dependencies_module()
        parser = module.build_parser()

        args = parser.parse_args(["--profile", "core", "--platform", "Linux"])

        self.assertEqual(args.profile, "core")
        self.assertIn("core", module.DEPENDENCY_PROFILES)
        self.assertIn("segmentation", module.DEPENDENCY_PROFILES["core"])
        self.assertIn("bundles", module.DEPENDENCY_PROFILES)
        self.assertIn("full", module.DEPENDENCY_PROFILES)

    def test_all_and_profile_conflict_is_documented_by_main(self) -> None:
        module = _load_install_dependencies_module()

        with self.assertRaises(SystemExit) as raised:
            module.main(["--all", "--profile", "core"])

        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
