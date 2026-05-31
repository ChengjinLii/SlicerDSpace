#!/usr/bin/env python3
"""Run the real-subject minimum closure: DTI maps -> tractogram -> WMQL -> connectome."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-root", default="/data/chengjin/SlicerDDSurfer-test/100307")
    parser.add_argument("--subject-id", default="100307")
    parser.add_argument("--fit-method", choices=["wls", "ls"], default="wls")
    parser.add_argument("--clean", action="store_true", help="Delete closure output directories before running.")
    parser.add_argument("--max-seed-voxels", type=int, default=1200)
    parser.add_argument("--min-fa", type=float, default=0.25)
    parser.add_argument("--wmql-execute", action="store_true", help="Run Tract Querier instead of only writing a WMQL plan.")
    parser.add_argument(
        "--tract-querier-root",
        default=None,
        help="Optional Tract Querier checkout. Defaults to third_party/tract_querier when present.",
    )
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_parcellation(subject_root: Path, subject_id: str) -> Path:
    candidates = [
        subject_root / "outputs" / "03_structural" / "ddparcel" / f"{subject_id}_ddparcel_wmparc_labels.nii.gz",
        subject_root / "outputs" / "03_structural" / "ddparcel" / f"{subject_id}-DDSurfer-wmparc.nii.gz",
        subject_root / ".legacy_flat_outputs" / "ddparcel" / f"{subject_id}-DDSurfer-wmparc.nii.gz",
        subject_root / "parcellation" / "wmparc.nii.gz",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("No wmparc/aparc parcellation found for closure test.")


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from connectome import ConnectomeConfig, run_connectome
    from microstructure import MicrostructureConfig, run_microstructure
    from shared import ensure_native_dti_bundle, find_subject_root, materialize_canonical_output_tree, subject_layout
    from tractography import DTITrackingConfig, WMQLConfig, run_dti_tracking, run_wmql_bundle_segmentation

    subject_root = Path(args.subject_root).expanduser().resolve()
    subject_id = args.subject_id
    layout = subject_layout(subject_root)
    output_dirs = [
        layout.microstructure,
        layout.tractograms_dti_det,
        layout.bundles_wmql,
        layout.connectome,
    ]
    if args.clean:
        for output_dir in output_dirs:
            if output_dir.exists():
                shutil.rmtree(output_dir)

    print(f"[closure] subject={subject_id} root={subject_root}")
    materialize_canonical_output_tree(subject_root, mode="symlink", archive_legacy=False)
    raw = find_subject_root(subject_root, subject_id)
    parcellation = _resolve_parcellation(subject_root, subject_id)
    native = ensure_native_dti_bundle(raw, fit_method=args.fit_method, reuse=True, log=print)

    micro = run_microstructure(
        MicrostructureConfig(
            subject_id=subject_id,
            raw_input_bundle=raw,
            native_bundle=native,
            output_dir=layout.microstructure,
            roi_label_map=parcellation,
            run_free_water=False,
            run_noddi=False,
            force_recompute=True,
        ),
        log=print,
    )
    dti_required = [micro.fa_path, micro.md_path, micro.ad_path, micro.rd_path, micro.l1_path, micro.l2_path, micro.l3_path]
    missing_dti = [path for path in dti_required if not path.is_file()]
    if missing_dti:
        raise FileNotFoundError("Missing DTI scalar outputs: " + ", ".join(path.as_posix() for path in missing_dti))

    tracking = run_dti_tracking(
        DTITrackingConfig(
            subject_id=subject_id,
            input_root=subject_root,
            output_dir=layout.tractograms_dti_det,
            fit_method=args.fit_method,
            output_format="trk",
            min_fa=args.min_fa,
            seed_density=1,
            max_seed_voxels=args.max_seed_voxels,
            execute=True,
        ),
        log=print,
    )
    tracking_qc = _read_json(tracking.qc_path)
    if int(tracking_qc.get("streamline_count") or 0) <= 0:
        raise RuntimeError(f"DTI tracking produced no streamlines: {tracking.qc_path}")

    tract_querier_root = Path(args.tract_querier_root).expanduser().resolve() if args.tract_querier_root else None
    default_tq_root = repo_root / "third_party" / "tract_querier"
    if tract_querier_root is None and default_tq_root.is_dir():
        tract_querier_root = default_tq_root
    wmql = run_wmql_bundle_segmentation(
        WMQLConfig(
            subject_id=subject_id,
            input_tractography=tracking.streamlines_path,
            atlas_path=parcellation,
            output_dir=layout.bundles_wmql,
            tract_querier_root=tract_querier_root,
            execute=bool(args.wmql_execute),
        ),
        log=print,
    )
    wmql_qc = _read_json(wmql.qc_path)
    if args.wmql_execute and wmql_qc.get("status") != "completed":
        raise RuntimeError(f"WMQL failed: {wmql.qc_path}")

    connectome = run_connectome(
        ConnectomeConfig(
            subject_id=subject_id,
            tractography_path=tracking.streamlines_path,
            parcellation_path=parcellation,
            output_dir=layout.connectome,
            metric="streamline_count",
            execute=True,
        ),
        log=print,
    )
    connectome_qc = _read_json(connectome.qc_path)
    if connectome_qc.get("status") != "completed":
        raise RuntimeError(f"Connectome failed: {connectome.qc_path}")

    summary = {
        "subject_id": subject_id,
        "microstructure": {
            "fa": micro.fa_path.as_posix(),
            "md": micro.md_path.as_posix(),
            "ad": micro.ad_path.as_posix(),
            "rd": micro.rd_path.as_posix(),
            "l1": micro.l1_path.as_posix(),
            "l2": micro.l2_path.as_posix(),
            "l3": micro.l3_path.as_posix(),
            "roi_stats": micro.roi_stats_csv_path.as_posix() if micro.roi_stats_csv_path else None,
        },
        "tractography": {
            "tractogram": tracking.streamlines_path.as_posix(),
            "streamline_count": tracking_qc.get("streamline_count"),
        },
        "wmql": {
            "status": wmql_qc.get("status"),
            "executed": wmql_qc.get("executed"),
            "bundle_count": wmql_qc.get("output_summary", {}).get("bundle_count") if isinstance(wmql_qc.get("output_summary"), dict) else None,
            "qc": wmql.qc_path.as_posix(),
        },
        "connectome": {
            "matrix": connectome.matrix_path.as_posix(),
            "edge_count": connectome_qc.get("edge_count"),
            "assigned_streamlines": connectome_qc.get("streamline_count_assigned"),
        },
    }
    summary_path = layout.run_metadata / "real_subject_minimal_closure.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[closure] summary={summary_path}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
