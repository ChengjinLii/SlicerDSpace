#!/usr/bin/env python3
"""Validate the copied 149741 WMA/ACT/connectome fixture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-root",
        type=Path,
        default=Path("/data/chengjin/SlicerDDSurfer-test/149741_wma_act"),
    )
    return parser.parse_args()


def _file(path: Path) -> dict[str, object]:
    return {
        "path": path.as_posix(),
        "exists": path.is_file(),
        "size": path.stat().st_size if path.is_file() else None,
    }


def main() -> int:
    args = parse_args()
    root = args.fixture_root.expanduser().resolve()
    expected = {
        "tractography_vtk": root / "tractography" / "149741_ukf_pp_downsampled.vtk",
        "wma_measurements": root / "wma" / "anatomical_tracts" / "diffusion_measurements_anatomical_tracts.csv",
        "wma_tract_1": root / "wma" / "anatomical_tracts" / "T_EmC_right.vtp",
        "wma_tract_2": root / "wma" / "anatomical_tracts" / "T_SP_left.vtp",
        "ddparcel_wmparc": root / "parcellation" / "wmparc.nii.gz",
        "mask": root / "input" / "nodif_brain_mask.nii.gz",
        "bvals": root / "input" / "bvals",
        "bvecs": root / "input" / "bvecs",
    }
    report = {
        "fixture_root": root.as_posix(),
        "files": {key: _file(path) for key, path in expected.items()},
        "wma_ready_input": expected["tractography_vtk"].is_file(),
        "note": "Real WMA execution still requires an external WMA backend and ORG atlas directory.",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    missing = [key for key, path in expected.items() if not path.is_file()]
    if missing:
        print("missing=" + ",".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
