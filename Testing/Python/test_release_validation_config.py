from __future__ import annotations

import unittest
from pathlib import Path

from scripts import release_validation


class ReleaseValidationConfigTest(unittest.TestCase):
    def test_subject_root_has_no_repository_local_default(self) -> None:
        parser = release_validation.build_parser()
        args = parser.parse_args([])
        self.assertIsNone(args.subject_root)

    def test_build_steps_skip_slicer_smoke_without_local_paths(self) -> None:
        parser = release_validation.build_parser()
        args = parser.parse_args(["--subject-root", "/tmp/slicerdsurfer-subject", "--skip-slicer-smoke"])
        args.report_dir = Path("/tmp/slicerdsurfer-release-report")
        steps = release_validation.build_validation_steps(args, [])
        slicer_steps = [step for step in steps if step.name.startswith("slicer_") and step.name.endswith("_smoke")]
        self.assertEqual(len(slicer_steps), 5)
        self.assertTrue(all(step.skipped for step in slicer_steps))

        fresh_clone = [step for step in steps if step.name == "fresh_clone_smoke"]
        self.assertEqual(len(fresh_clone), 1)
        self.assertTrue(fresh_clone[0].skipped)

        mirror_steps = [step for step in steps if step.name in {"asset_mirror_core_verify", "asset_mirror_all_verify"}]
        self.assertEqual(len(mirror_steps), 2)
        self.assertTrue(all(step.skipped for step in mirror_steps))


if __name__ == "__main__":
    unittest.main()
