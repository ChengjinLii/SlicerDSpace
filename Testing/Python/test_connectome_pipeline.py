#!/usr/bin/env python3
"""Lightweight tests for connectome planning."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from connectome import ConnectomeConfig, run_connectome


class ConnectomePipelineTest(unittest.TestCase):
    def test_writes_manifest_matrix_header_and_nodes_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tractography = root / "streamlines.vtk"
            parcellation = root / "wmparc.nii.gz"
            tractography.write_text("# vtk DataFile Version 3.0\n", encoding="utf-8")
            parcellation.write_text("parcel", encoding="utf-8")

            result = run_connectome(
                ConnectomeConfig(
                    subject_id="149741",
                    tractography_path=tractography,
                    parcellation_path=parcellation,
                    output_dir=root / "connectome",
                )
            )

            self.assertFalse(result.executed)
            self.assertEqual(result.matrix_path.read_text(encoding="utf-8").strip(), "source_node,target_node,streamline_count")
            self.assertEqual(result.nodes_path.read_text(encoding="utf-8").strip(), "node_id\tlabel\tname")
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["dependencies"]["tractography"]["path"], tractography.resolve().as_posix())
            self.assertEqual(manifest["dependencies"]["ddparcel_parcellation"]["path"], parcellation.resolve().as_posix())
            self.assertEqual(qc["metric"], "streamline_count")

    def test_rejects_missing_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                run_connectome(
                    ConnectomeConfig(
                        subject_id="149741",
                        tractography_path=root / "missing.vtk",
                        parcellation_path=root / "missing.nii.gz",
                        output_dir=root / "connectome",
                    )
                )

    def test_execute_true_runs_fake_tck2connectome_for_tck_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "tck2connectome"
            fake.write_text(
                "#!/bin/sh\n"
                "printf '1,2,3\\n' > \"$3\"\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            tractography = root / "streamlines.tck"
            parcellation = root / "wmparc.nii.gz"
            tractography.write_text("tck", encoding="utf-8")
            parcellation.write_text("parcel", encoding="utf-8")

            with mock.patch.dict(os.environ, {"PATH": bin_dir.as_posix() + os.pathsep + os.environ.get("PATH", "")}):
                result = run_connectome(
                    ConnectomeConfig(
                        subject_id="149741",
                        tractography_path=tractography,
                        parcellation_path=parcellation,
                        output_dir=root / "connectome",
                        execute=True,
                    )
                )

            self.assertTrue(result.executed)
            self.assertEqual(result.return_code, 0)
            self.assertEqual(result.matrix_path.read_text(encoding="utf-8").strip(), "1,2,3")
            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            self.assertEqual(qc["status"], "completed")
            self.assertEqual(qc["backend"], "mrtrix3.tck2connectome")

    def test_execute_true_computes_endpoint_matrix_for_ascii_vtk(self) -> None:
        try:
            import nibabel as nib
            import numpy as np
        except ImportError:
            self.skipTest("nibabel/numpy are required for endpoint-label connectome test")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tractography = root / "streamlines.vtk"
            tractography.write_text(
                "# vtk DataFile Version 3.0\n"
                "test\n"
                "ASCII\n"
                "DATASET POLYDATA\n"
                "POINTS 4 float\n"
                "1 1 1 3 3 3 1 1 1 3 3 3\n"
                "LINES 2 6\n"
                "2 0 1\n"
                "2 2 3\n",
                encoding="utf-8",
            )
            labels = np.zeros((5, 5, 5), dtype=np.int16)
            labels[1, 1, 1] = 10
            labels[3, 3, 3] = 20
            parcellation = root / "wmparc.nii.gz"
            nib.save(nib.Nifti1Image(labels, np.eye(4)), parcellation.as_posix())

            result = run_connectome(
                ConnectomeConfig(
                    subject_id="vtk",
                    tractography_path=tractography,
                    parcellation_path=parcellation,
                    output_dir=root / "connectome",
                    execute=True,
                )
            )

            self.assertTrue(result.executed)
            self.assertIn("10,20,2", result.matrix_path.read_text(encoding="utf-8"))
            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            self.assertEqual(qc["streamline_count_total"], 2)
            self.assertEqual(qc["streamline_count_assigned"], 2)
            self.assertEqual(qc["edge_count"], 1)


if __name__ == "__main__":
    unittest.main()
