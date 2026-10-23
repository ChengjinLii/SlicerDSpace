#!/usr/bin/env python3
"""NODDI runs amico.setup() when AMICO's rotation matrices are missing (macOS run, 2026-10-23)."""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def fake_amico(installed: bool):
    """AMICO 2.1.1 behaviour: util.ERROR() prints and calls exit(os.EX_USAGE) when the matrices are missing."""
    state = {"installed": installed, "setup": []}

    def load(lmax, ndirs):
        if not state["installed"]:
            raise SystemExit(64)
        return {"lmax": lmax, "ndirs": ndirs}

    def setup(lmax=12):
        state["setup"].append(lmax)
        state["installed"] = True

    module = types.SimpleNamespace(lut=types.SimpleNamespace(load_precomputed_rotation_matrices=load), setup=setup)
    return module, state


class AmicoRotationMatricesTest(unittest.TestCase):
    def test_missing_matrices_run_setup_once_instead_of_exiting(self) -> None:
        import microstructure.pipeline as pipeline

        module, state = fake_amico(installed=False)
        lines = []
        with mock.patch.object(pipeline, "amico", module):
            pipeline._ensure_amico_rotation_matrices(12, 500, lines.append)
            pipeline._ensure_amico_rotation_matrices(12, 500, lines.append)
        self.assertEqual(state["setup"], [12])
        self.assertTrue(any("amico.setup()" in line for line in lines), lines)

    def test_present_matrices_skip_setup(self) -> None:
        import microstructure.pipeline as pipeline

        module, state = fake_amico(installed=True)
        with mock.patch.object(pipeline, "amico", module):
            pipeline._ensure_amico_rotation_matrices(12, 500, None)
        self.assertEqual(state["setup"], [])


if __name__ == "__main__":
    unittest.main()
