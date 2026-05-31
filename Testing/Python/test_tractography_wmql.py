#!/usr/bin/env python3
"""Tests for WMQL bundle segmentation integration."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class WMQLIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.python = self.tmp_path / "python"
        self.python.write_text(
            """#!/bin/sh
if [ "$1" = "-c" ]; then
  echo '{"tract_querier": true, "nibabel": true, "numpy": true}'
  exit 0
fi
script="$1"
shift
out=""
prev=""
for arg in "$@"; do
  if [ "$prev" = "-o" ]; then
    out="$arg"
  fi
  prev="$arg"
done
mkdir -p "$(dirname "$out")"
printf '# vtk DataFile Version 3.0\\n' > "${out}_AF.left.vtk"
printf '# vtk DataFile Version 3.0\\n' > "${out}_CST.left.vtk"
exit 0
""",
            encoding="utf-8",
        )
        self.python.chmod(0o755)
        self.tract_querier_root = self.tmp_path / "tract_querier_root"
        scripts = self.tract_querier_root / "scripts"
        data = self.tract_querier_root / "tract_querier" / "data"
        scripts.mkdir(parents=True)
        data.mkdir(parents=True)
        (scripts / "cli_tract_querier.py").write_text("# fake cli\n", encoding="utf-8")
        (data / "FreeSurfer.qry").write_text("brain_stem |= 16\n", encoding="utf-8")
        self.tractography = self.tmp_path / "wholebrain.vtk"
        self.tractography.write_text("# vtk DataFile Version 3.0\n", encoding="utf-8")
        self.atlas = self.tmp_path / "wmparc.nii.gz"
        self.atlas.write_text("atlas", encoding="utf-8")
        self.output_dir = self.tmp_path / "wmql_out"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_default_query_is_bundled(self) -> None:
        from tractography import bundled_wmql_query_path

        query = bundled_wmql_query_path()
        self.assertTrue(query.is_file())
        text = query.read_text(encoding="utf-8")
        self.assertIn("AF.side", text)
        self.assertIn("CST.side", text)

    def test_builds_wmql_command_without_running(self) -> None:
        from tractography import WMQLConfig, run_wmql_bundle_segmentation

        result = run_wmql_bundle_segmentation(
            WMQLConfig(
                subject_id="100307",
                input_tractography=self.tractography,
                atlas_path=self.atlas,
                output_dir=self.output_dir,
                tract_querier_root=self.tract_querier_root,
                python_executable=self.python,
                execute=False,
            )
        )

        self.assertFalse(result.executed)
        self.assertTrue(result.backend_status["available"])
        self.assertTrue(result.manifest_path.is_file())
        self.assertTrue(result.qc_path.is_file())
        command = list(result.command)
        self.assertEqual(command[0], self.python.resolve().as_posix())
        self.assertIn("-t", command)
        self.assertIn("-a", command)
        self.assertIn("-q", command)
        self.assertIn("--query_selection", command)
        self.assertIn("af.left,af.right,cst.left,cst.right", command)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["kind"], "wmql_bundle_segmentation")
        self.assertEqual(manifest["status"], "planned")
        self.assertEqual(manifest["backend"]["repository"], "https://github.com/demianw/tract_querier")
        self.assertTrue((self.output_dir / "queries" / "AF_CST.qry").is_file())

    def test_execute_true_summarizes_created_bundles_with_fake_backend(self) -> None:
        from tractography import WMQLConfig, run_wmql_bundle_segmentation

        result = run_wmql_bundle_segmentation(
            WMQLConfig(
                subject_id="100307",
                input_tractography=self.tractography,
                atlas_path=self.atlas,
                output_dir=self.output_dir,
                tract_querier_root=self.tract_querier_root,
                python_executable=self.python,
                execute=True,
            )
        )

        self.assertTrue(result.executed)
        self.assertEqual(result.return_code, 0)
        qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
        self.assertEqual(qc["status"], "completed")
        self.assertEqual(qc["output_summary"]["bundle_count"], 2)
        self.assertEqual(len(qc["output_summary"]["bundles"]), 2)
        self.assertIn("size", qc["output_summary"]["bundles"][0])

    def test_bundle_parcellation_dispatches_wmql_backend(self) -> None:
        from tractography import BundleParcellationConfig, WMQLConfig, run_bundle_parcellation

        result = run_bundle_parcellation(
            BundleParcellationConfig(
                backend="wmql",
                wmql=WMQLConfig(
                    subject_id="100307",
                    input_tractography=self.tractography,
                    atlas_path=self.atlas,
                    output_dir=self.output_dir,
                    tract_querier_root=self.tract_querier_root,
                    python_executable=self.python,
                ),
            )
        )

        self.assertEqual(result.manifest_path.name, "wmql_manifest.json")

    def test_rejects_backend_config_mix(self) -> None:
        from tractography import BundleParcellationConfig, run_bundle_parcellation

        with self.assertRaisesRegex(ValueError, "requires only the wmql config"):
            run_bundle_parcellation(BundleParcellationConfig(backend="wmql"))


if __name__ == "__main__":
    unittest.main()
