#!/usr/bin/env python3
"""Run real MRtrix CSD/FOD/ACT, WMQL, and connectome on one subject root."""

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
    parser.add_argument("--mrtrix-bin-dir", default="/data/chengjin/software/mrtrix3_env/bin")
    parser.add_argument("--select-streamlines", type=int, default=1000)
    parser.add_argument("--run-name", default="csd_act", help="Output namespace under tractography/connectome/bundles.")
    parser.add_argument("--no-sift2", action="store_true")
    parser.add_argument("--clean", action="store_true", help="Delete CSD/ACT, WMQL, and connectome smoke outputs first.")
    parser.add_argument(
        "--tract-querier-root",
        default=None,
        help="Optional Tract Querier checkout. Defaults to third_party/tract_querier when present.",
    )
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_segmentation(subject_root: Path) -> Path:
    from shared.io_layout import subject_layout
    directory = subject_layout(subject_root).anatomy_input_dir("ddseg")
    candidates = [
        directory / "SegmentationMap_GMWMCSF.nii.gz",
        subject_root / ".legacy_flat_outputs" / "ddseg" / "SegmentationMap_GMWMCSF.nii.gz",
        subject_root / "segmentation" / "SegmentationMap_GMWMCSF.nii.gz",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("No DDSeg WM/GM/CSF segmentation found for ACT prep.")


def _resolve_parcellation(subject_root: Path, subject_id: str) -> Path:
    from shared.io_layout import subject_layout
    directory = subject_layout(subject_root).anatomy_input_dir("ddparcel")
    candidates = [
        directory / f"{subject_id}_ddparcel_wmparc_labels.nii.gz",
        directory / f"{subject_id}-DDSurfer-wmparc.nii.gz",
        subject_root / ".legacy_flat_outputs" / "ddparcel" / f"{subject_id}-DDSurfer-wmparc.nii.gz",
        subject_root / "parcellation" / "wmparc.nii.gz",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("No wmparc/aparc parcellation found for connectome/WMQL.")


def _optional_dti_scalar(layout, subject_id: str, suffix: str) -> Path | None:
    path = layout.microstructure_dti / f"{subject_id}_dti_{suffix}.nii.gz"
    return path if path.is_file() else None


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from connectome import ConnectomeConfig, run_connectome
    from shared import canonical_connectome_output_dir, materialize_canonical_output_tree, normalize_run_name, subject_layout
    from tractography.act_prep import ACTPrepConfig, run_act_prep
    from tractography.csd import CSDActConfig, run_csd_act
    from tractography.wmql import WMQLConfig, run_wmql_bundle_segmentation

    subject_root = Path(args.subject_root).expanduser().resolve()
    subject_id = args.subject_id
    layout = subject_layout(subject_root)
    run_name = normalize_run_name(args.run_name)
    csd_dir = layout.csd if run_name == "csd_act" else layout.csd / run_name.replace("/", "_")
    tractogram_dir = layout.tractograms / run_name.replace("/", "_")
    wmql_dir = layout.bundles_wmql / run_name.replace("/", "_")
    connectome_dir = canonical_connectome_output_dir(subject_root, run_name, "streamline_count")
    sift2_connectome_dir = canonical_connectome_output_dir(subject_root, run_name, "sift2_weighted_streamline_count")
    if args.clean:
        for output_dir in (
            csd_dir,
            tractogram_dir,
            wmql_dir,
            connectome_dir,
            sift2_connectome_dir,
        ):
            if output_dir.exists():
                shutil.rmtree(output_dir)

    materialize_canonical_output_tree(subject_root, mode="symlink", archive_legacy=False)
    raw = subject_root / "input"
    dwi = raw / "data.nii.gz"
    bval = raw / "bvals"
    bvec = raw / "bvecs"
    mask = raw / "nodif_brain_mask.nii.gz"
    segmentation = _resolve_segmentation(subject_root)
    parcellation = _resolve_parcellation(subject_root, subject_id)

    act_prep = run_act_prep(
        ACTPrepConfig(
            subject_id=subject_id,
            segmentation_path=segmentation,
            output_dir=layout.act_prep,
            execute=True,
        ),
        log=print,
    )
    csd = run_csd_act(
        CSDActConfig(
            subject_id=subject_id,
            dwi_path=dwi,
            bval_path=bval,
            bvec_path=bvec,
            mask_path=mask,
            five_tt_path=act_prep.five_tt_path,
            gmwmi_path=act_prep.gmwmi_path,
            output_dir=csd_dir,
            tractogram_dir=tractogram_dir,
            select_streamlines=args.select_streamlines,
            use_sift2=not args.no_sift2,
            export_trk=True,
            mrtrix_bin_dir=Path(args.mrtrix_bin_dir).expanduser().resolve(),
            execute=True,
        ),
        log=print,
    )
    csd_qc = _read_json(csd.qc_path)
    if csd_qc.get("status") != "completed":
        raise RuntimeError(f"CSD/ACT failed: {csd.qc_path}")
    if csd.tractogram_trk_path is None or not csd.tractogram_trk_path.is_file():
        raise RuntimeError("CSD/ACT did not export a TRK tractogram for WMQL.")

    tract_querier_root = Path(args.tract_querier_root).expanduser().resolve() if args.tract_querier_root else None
    default_tq_root = repo_root / "third_party" / "tract_querier"
    if tract_querier_root is None and default_tq_root.is_dir():
        tract_querier_root = default_tq_root
    wmql = run_wmql_bundle_segmentation(
        WMQLConfig(
            subject_id=subject_id,
            input_tractography=csd.tractogram_trk_path,
            atlas_path=parcellation,
            output_dir=wmql_dir,
            tract_querier_root=tract_querier_root,
            execute=True,
        ),
        log=print,
    )
    wmql_qc = _read_json(wmql.qc_path)
    if wmql_qc.get("status") != "completed":
        raise RuntimeError(f"WMQL failed: {wmql.qc_path}")

    connectome = run_connectome(
        ConnectomeConfig(
            subject_id=subject_id,
            tractography_path=csd.tractogram_path,
            parcellation_path=parcellation,
            output_dir=connectome_dir,
            metric="streamline_count",
            backend="python",
            execute=True,
        ),
        log=print,
    )
    connectome_qc = _read_json(connectome.qc_path)
    if connectome_qc.get("status") != "completed":
        raise RuntimeError(f"Connectome failed: {connectome.qc_path}")

    weighted_connectome = None
    weighted_connectome_qc: dict[str, object] | None = None
    extra_connectomes: dict[str, dict[str, object]] = {}
    if csd.sift2_weights_path is not None and csd.sift2_weights_path.is_file():
        weighted_connectome = run_connectome(
            ConnectomeConfig(
                subject_id=subject_id,
                tractography_path=csd.tractogram_path,
                parcellation_path=parcellation,
                output_dir=sift2_connectome_dir,
                metric="sift2_weighted_streamline_count",
                sift2_weights_path=csd.sift2_weights_path,
                backend="python",
                execute=True,
            ),
            log=print,
        )
        weighted_connectome_qc = _read_json(weighted_connectome.qc_path)
        if weighted_connectome_qc.get("status") != "completed":
            raise RuntimeError(f"SIFT2 weighted connectome failed: {weighted_connectome.qc_path}")

    scalar_metric_specs = [
        ("mean_fa", _optional_dti_scalar(layout, subject_id, "FA")),
        ("mean_md", _optional_dti_scalar(layout, subject_id, "MD")),
    ]
    for metric, scalar_path in scalar_metric_specs:
        if scalar_path is None:
            extra_connectomes[metric] = {"status": "skipped", "reason": "missing_scalar_map"}
            continue
        result = run_connectome(
            ConnectomeConfig(
                subject_id=subject_id,
                tractography_path=csd.tractogram_path,
                parcellation_path=parcellation,
                output_dir=canonical_connectome_output_dir(subject_root, run_name, metric),
                metric=metric,
                scalar_map_path=scalar_path,
                backend="python",
                execute=True,
            ),
            log=print,
        )
        qc = _read_json(result.qc_path)
        if qc.get("status") != "completed":
            raise RuntimeError(f"{metric} connectome failed: {result.qc_path}")
        extra_connectomes[metric] = {
            "matrix": result.matrix_path.as_posix(),
            "node_count": qc.get("node_count"),
            "edge_count": qc.get("edge_count"),
            "sampled_streamlines": qc.get("streamline_count_scalar_sampled"),
            "qc": result.qc_path.as_posix(),
        }

    for metric in ("mean_length_mm", "total_length_mm"):
        result = run_connectome(
            ConnectomeConfig(
                subject_id=subject_id,
                tractography_path=csd.tractogram_path,
                parcellation_path=parcellation,
                output_dir=canonical_connectome_output_dir(subject_root, run_name, metric),
                metric=metric,
                backend="python",
                execute=True,
            ),
            log=print,
        )
        qc = _read_json(result.qc_path)
        if qc.get("status") != "completed":
            raise RuntimeError(f"{metric} connectome failed: {result.qc_path}")
        extra_connectomes[metric] = {
            "matrix": result.matrix_path.as_posix(),
            "node_count": qc.get("node_count"),
            "edge_count": qc.get("edge_count"),
            "sampled_streamlines": qc.get("streamline_count_length_sampled"),
            "qc": result.qc_path.as_posix(),
        }

    summary = {
        "subject_id": subject_id,
        "run_name": run_name,
        "select_streamlines": args.select_streamlines,
        "csd_act": {
            "wm_fod_norm": csd.wm_fod_norm_path.as_posix(),
            "tractogram_tck": csd.tractogram_path.as_posix(),
            "tractogram_trk": csd.tractogram_trk_path.as_posix(),
            "sift2_weights": csd.sift2_weights_path.as_posix() if csd.sift2_weights_path else None,
            "qc": csd.qc_path.as_posix(),
        },
        "wmql": {
            "status": wmql_qc.get("status"),
            "bundle_count": wmql_qc.get("output_summary", {}).get("bundle_count")
            if isinstance(wmql_qc.get("output_summary"), dict)
            else None,
            "qc": wmql.qc_path.as_posix(),
        },
        "connectome": {
            "matrix": connectome.matrix_path.as_posix(),
            "node_count": connectome_qc.get("node_count"),
            "edge_count": connectome_qc.get("edge_count"),
            "assigned_streamlines": connectome_qc.get("streamline_count_assigned"),
            "qc": connectome.qc_path.as_posix(),
        },
        "sift2_weighted_connectome": {
            "matrix": weighted_connectome.matrix_path.as_posix() if weighted_connectome else None,
            "node_count": weighted_connectome_qc.get("node_count") if weighted_connectome_qc else None,
            "edge_count": weighted_connectome_qc.get("edge_count") if weighted_connectome_qc else None,
            "assigned_weight": weighted_connectome_qc.get("streamline_count_assigned") if weighted_connectome_qc else None,
            "qc": weighted_connectome.qc_path.as_posix() if weighted_connectome else None,
        },
        "extra_connectomes": extra_connectomes,
    }
    summary_path = layout.run_metadata / f"{run_name}_real_subject_smoke.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"[csd-act-smoke] summary={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
