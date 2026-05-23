#!/usr/bin/env python3
"""Run the copied 149741 tractography + parcellation connectome smoke test."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from connectome import ConnectomeConfig, run_connectome


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-root",
        type=Path,
        default=Path("/data/chengjin/SlicerDDSurfer-test/149741_wma_act"),
    )
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.fixture_root.expanduser().resolve()
    result = run_connectome(
        ConnectomeConfig(
            subject_id="149741",
            tractography_path=root / "tractography" / "149741_ukf_pp_downsampled.vtk",
            parcellation_path=root / "parcellation" / "wmparc.nii.gz",
            output_dir=root / "outputs" / ("connectome_execute_smoke" if args.execute else "connectome_dryrun_smoke"),
            execute=args.execute,
        )
    )
    qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
    print(f"executed={result.executed}")
    print(f"matrix={result.matrix_path}")
    print(f"nodes={result.nodes_path}")
    print(f"manifest={result.manifest_path}")
    print(f"qc={result.qc_path}")
    print("qc_summary=" + json.dumps(qc, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
