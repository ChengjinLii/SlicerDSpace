#!/usr/bin/env python3
"""Tests for the SlicerDDSurfer batch CLI helpers."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_CLI_PATH = REPO_ROOT / "scripts" / "run_batch_pipeline.py"

spec = importlib.util.spec_from_file_location("run_batch_pipeline", BATCH_CLI_PATH)
assert spec is not None and spec.loader is not None
batch_cli = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = batch_cli
spec.loader.exec_module(batch_cli)


def _write_raw_subject(subject_root: Path, *, nested_input: bool = True) -> None:
    input_dir = subject_root / "input" if nested_input else subject_root
    input_dir.mkdir(parents=True, exist_ok=True)
    for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
        (input_dir / name).write_text("x", encoding="utf-8")


class RunBatchPipelineCliTest(unittest.TestCase):
    def test_discover_subject_roots_under_batch_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch_root = Path(tmp)
            _write_raw_subject(batch_root / "100307")
            _write_raw_subject(batch_root / "100408")
            (batch_root / "notes").mkdir()

            subjects, skipped = batch_cli.discover_subjects(batch_root)

            self.assertEqual([subject.subject_id for subject in subjects], ["100307", "100408"])
            self.assertEqual([subject.mode for subject in subjects], ["subject_root", "subject_root"])
            self.assertEqual([item["subject_id"] for item in skipped], ["notes"])

    def test_arrange_direct_raw_files_into_input_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_root = Path(tmp) / "sub-01"
            _write_raw_subject(subject_root, nested_input=False)

            subjects, skipped = batch_cli.discover_subjects(Path(tmp), arrange_inputs="copy")

            self.assertEqual(skipped, [])
            self.assertEqual(len(subjects), 1)
            self.assertEqual(subjects[0].mode, "subject_root+arranged")
            self.assertTrue((subject_root / "input" / "data.nii.gz").is_file())

    def test_build_subject_command_defaults_to_test1_and_subject_output_subdir(self) -> None:
        subject = batch_cli.BatchSubject(
            subject_id="100307",
            subject_root=Path("/tmp/batch/100307"),
            source="glob",
            mode="subject_root",
        )

        command = batch_cli.build_subject_command(
            subject,
            pipeline_script=Path("/repo/run_subject_pipeline.py"),
            python_executable=Path("/usr/bin/python3"),
            output_root=Path("/tmp/outputs"),
            run_name="Test1",
            execute=True,
            forwarded_args=["--all", "--bundle-backend", "all"],
        )

        self.assertIn("--run-name", command)
        self.assertEqual(command[command.index("--run-name") + 1], "Test1")
        # build_subject_command() resolves the output root (e.g. macOS's
        # /tmp -> /private/tmp symlink); compare against the resolved form.
        expected_output_root = (Path("/tmp/outputs").resolve() / "100307").as_posix()
        self.assertEqual(command[command.index("--output-root") + 1], expected_output_root)
        self.assertIn("--execute", command)
        self.assertEqual(command[-3:], ["--all", "--bundle-backend", "all"])

    def test_parser_accepts_batch_size_alias(self) -> None:
        args, forwarded = batch_cli.build_parser().parse_known_args(
            ["--batch-root", "/tmp/batch", "--batch-size", "3", "--targets", "microstructure"]
        )

        self.assertEqual(args.jobs, 3)
        self.assertEqual(forwarded, ["--targets", "microstructure"])


if __name__ == "__main__":
    unittest.main()
