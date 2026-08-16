#!/usr/bin/env python3
"""Audit multi-subject anatomical, DTI, and tractography outputs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DTI_KEYS = ("fa", "md", "ad", "rd", "l1", "l2", "l3", "trace")
FULL_ROUTE_NAMES = {"freewater", "noddi", "saf", "wmql", "wma", "tractcloud", "connectome"}


def _manifest_for_run(subject_output: Path, run_name: str | None = None) -> Path | None:
    metadata_dir = subject_output / "00_run_metadata"
    if run_name:
        candidate = metadata_dir / f"{run_name}_orchestration_manifest.json"
        return candidate if candidate.is_file() else None
    candidates = list(metadata_dir.glob("*_orchestration_manifest.json"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def _record_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    value: Any,
    requirement: str,
) -> None:
    checks.append(
        {
            "name": name,
            "passed": bool(passed),
            "value": value,
            "requirement": requirement,
        }
    )


def _task_outputs(manifest: dict[str, Any], task_name: str) -> dict[str, Any]:
    for task in manifest.get("tasks", []):
        if task.get("name") == task_name and task.get("status") in {"completed", "skipped"}:
            return dict(task.get("outputs") or {})
    return {}


def _task_entry(manifest: dict[str, Any], task_name: str) -> dict[str, Any] | None:
    for task in manifest.get("tasks", []):
        if task.get("name") == task_name:
            return dict(task)
    return None


def _audit_dti(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> bool:
    import nibabel as nib
    import numpy as np

    outputs = _task_outputs(manifest, "microstructure.dti")
    if not outputs:
        return False

    subject_root = Path(str(manifest["subject_root"]))
    mask_path = subject_root / "input" / "nodif_brain_mask.nii.gz"
    _record_check(checks, "dti.mask_exists", mask_path.is_file(), mask_path.as_posix(), "file exists")
    if not mask_path.is_file():
        return True

    mask_image = nib.load(mask_path.as_posix())
    mask = np.asarray(mask_image.dataobj) > 0
    maps: dict[str, Any] = {}
    for key in DTI_KEYS:
        path_value = outputs.get(key)
        path = Path(str(path_value)) if path_value else None
        exists = bool(path and path.is_file())
        _record_check(checks, f"dti.{key}.exists", exists, path.as_posix() if path else None, "file exists")
        if not exists or path is None:
            continue
        image = nib.load(path.as_posix())
        array = np.asarray(image.dataobj, dtype=np.float64)
        maps[key] = array
        _record_check(checks, f"dti.{key}.shape", array.shape == mask.shape, list(array.shape), list(mask.shape))
        _record_check(
            checks,
            f"dti.{key}.affine",
            bool(np.allclose(image.affine, mask_image.affine, atol=1e-4)),
            float(np.max(np.abs(image.affine - mask_image.affine))),
            "maximum absolute difference <= 1e-4",
        )
        _record_check(checks, f"dti.{key}.finite", bool(np.isfinite(array).all()), None, "all values finite")

    if any(key not in maps for key in DTI_KEYS) or not np.any(mask):
        return True

    fa = maps["fa"][mask]
    _record_check(
        checks,
        "dti.fa.range",
        bool(np.min(fa) >= -1e-6 and np.max(fa) <= 1.0 + 1e-6),
        {"min": float(np.min(fa)), "max": float(np.max(fa))},
        "0 <= FA <= 1",
    )
    for key in ("md", "ad", "rd", "l1", "l2", "l3"):
        values = maps[key][mask]
        _record_check(
            checks,
            f"dti.{key}.nonnegative",
            bool(np.min(values) >= -1e-8),
            float(np.min(values)),
            "minimum >= -1e-8 mm^2/s",
        )

    l1, l2, l3 = (maps[key][mask] for key in ("l1", "l2", "l3"))
    md, ad, rd, trace = (maps[key][mask] for key in ("md", "ad", "rd", "trace"))
    eigen_order_fraction = float(np.mean((l1 >= l2 - 1e-8) & (l2 >= l3 - 1e-8)))
    _record_check(checks, "dti.eigenvalue_order", eigen_order_fraction >= 0.999, eigen_order_fraction, ">= 0.999")

    identities = {
        "ad_equals_l1": np.abs(ad - l1),
        "rd_equals_l2_l3_mean": np.abs(rd - (l2 + l3) / 2.0),
        "md_equals_eigenvalue_mean": np.abs(md - (l1 + l2 + l3) / 3.0),
    }
    for name, error in identities.items():
        max_error = float(np.max(error))
        _record_check(checks, f"dti.{name}", max_error <= 1e-6, max_error, "maximum absolute error <= 1e-6")

    # SlicerDMRI computes Trace from the unconstrained tensor while its exported
    # eigenvalue maps clamp negative eigenvalues. Compare the unaffected voxels
    # by coverage instead of requiring an invalid exact identity everywhere.
    trace_close_fraction = float(np.mean(np.isclose(trace, 3.0 * md, rtol=1e-4, atol=1e-8)))
    _record_check(
        checks,
        "dti.trace_md_consistency",
        trace_close_fraction >= 0.95,
        trace_close_fraction,
        ">= 0.95 of masked voxels satisfy Trace ~= 3*MD",
    )
    return True


def _audit_tractography(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> bool:
    import nibabel as nib
    import numpy as np

    task_name = "tractography.dti_det"
    outputs = _task_outputs(manifest, task_name)
    if not outputs:
        task_name = "tractography.csd_act"
        outputs = _task_outputs(manifest, task_name)
    path_value = outputs.get("tractogram_trk") or outputs.get("tractogram")
    if not path_value:
        return False
    tractogram_path = Path(str(path_value))
    _record_check(checks, "tractography.exists", tractogram_path.is_file(), tractogram_path.as_posix(), "file exists")
    if not tractogram_path.is_file():
        return True

    tractogram = nib.streamlines.load(tractogram_path.as_posix())
    streamlines = list(tractogram.streamlines)
    _record_check(checks, "tractography.streamline_count", len(streamlines) > 0, len(streamlines), "> 0")
    if not streamlines:
        return True

    points = np.concatenate(streamlines, axis=0)
    lengths = np.asarray(
        [np.linalg.norm(np.diff(streamline, axis=0), axis=1).sum() for streamline in streamlines],
        dtype=np.float64,
    )
    _record_check(checks, "tractography.points_finite", bool(np.isfinite(points).all()), None, "all points finite")
    _record_check(
        checks,
        "tractography.lengths_positive",
        bool(np.isfinite(lengths).all() and np.min(lengths) > 0),
        {
            "min_mm": float(np.min(lengths)),
            "median_mm": float(np.median(lengths)),
            "max_mm": float(np.max(lengths)),
        },
        "all streamline lengths are finite and > 0 mm",
    )

    task = _task_entry(manifest, task_name) or {}
    tracking_manifest_value = task.get("manifest_path")
    tracking_manifest_path = Path(str(tracking_manifest_value)) if tracking_manifest_value else None
    if tracking_manifest_path and tracking_manifest_path.is_file():
        tracking_manifest = json.loads(tracking_manifest_path.read_text(encoding="utf-8"))
        parameters = tracking_manifest.get("parameters") or {}
        configured_min = parameters.get("min_length_mm")
        configured_max = parameters.get("max_length_mm")
        if configured_min is not None and configured_max is not None:
            within_configured_range = bool(
                np.min(lengths) + 1e-3 >= float(configured_min)
                and np.max(lengths) - 1e-3 <= float(configured_max)
            )
            _record_check(
                checks,
                "tractography.configured_length_range",
                within_configured_range,
                {
                    "configured_min_mm": float(configured_min),
                    "configured_max_mm": float(configured_max),
                    "observed_min_mm": float(np.min(lengths)),
                    "observed_max_mm": float(np.max(lengths)),
                },
                "all saved streamlines satisfy the configured millimetre range",
            )

    qc_value = task.get("qc_path")
    qc_path = Path(str(qc_value)) if qc_value else None
    if qc_path and qc_path.is_file():
        qc = json.loads(qc_path.read_text(encoding="utf-8"))
        qc_count = qc.get("streamline_count")
        if qc_count is not None:
            _record_check(
                checks,
                "tractography.qc_streamline_count",
                int(qc_count) == len(streamlines),
                {"qc": int(qc_count), "file": len(streamlines)},
                "QC and saved tractogram streamline counts match",
            )
        qc_min = qc.get("length_min_mm")
        qc_max = qc.get("length_max_mm")
        if qc_min is not None and qc_max is not None:
            summary_matches = bool(
                math.isclose(float(qc_min), float(np.min(lengths)), rel_tol=1e-5, abs_tol=1e-5)
                and math.isclose(float(qc_max), float(np.max(lengths)), rel_tol=1e-5, abs_tol=1e-5)
            )
            _record_check(
                checks,
                "tractography.qc_length_summary",
                summary_matches,
                {
                    "qc_min_mm": float(qc_min),
                    "file_min_mm": float(np.min(lengths)),
                    "qc_max_mm": float(qc_max),
                    "file_max_mm": float(np.max(lengths)),
                },
                "QC and saved tractogram length extrema match",
            )

    subject_root = Path(str(manifest["subject_root"]))
    dwi_path = subject_root / "input" / "data.nii.gz"
    if dwi_path.is_file():
        dwi = nib.load(dwi_path.as_posix())
        corners = np.asarray(
            [
                [i, j, k, 1.0]
                for i in (0, dwi.shape[0] - 1)
                for j in (0, dwi.shape[1] - 1)
                for k in (0, dwi.shape[2] - 1)
            ],
            dtype=np.float64,
        )
        world = (dwi.affine @ corners.T).T[:, :3]
        margin = 2.0 * max(float(value) for value in dwi.header.get_zooms()[:3])
        lower = world.min(axis=0) - margin
        upper = world.max(axis=0) + margin
        within = bool(np.all((points >= lower) & (points <= upper)))
        _record_check(
            checks,
            "tractography.world_bounds",
            within,
            {"point_min": points.min(axis=0).tolist(), "point_max": points.max(axis=0).tolist()},
            "all points within DWI world bounds plus a two-voxel margin",
        )
    return True


def _audit_optional_microstructure(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> set[str]:
    import nibabel as nib
    import numpy as np

    route_specs = {
        "freewater": {
            "task": "microstructure.freewater",
            "maps": {"fwf": (0.0, 1.0), "fw_fa": (0.0, 1.0), "fw_md": (0.0, None)},
        },
        "noddi": {
            "task": "microstructure.noddi",
            "maps": {"ndi": (0.0, 1.0), "odi": (0.0, 1.0), "isovf": (0.0, 1.0)},
        },
    }
    selected: set[str] = set()
    subject_root = Path(str(manifest["subject_root"]))
    mask_path = subject_root / "input" / "nodif_brain_mask.nii.gz"
    mask_image = nib.load(mask_path.as_posix()) if mask_path.is_file() else None
    mask = np.asarray(mask_image.dataobj) > 0 if mask_image is not None else None

    for route, spec in route_specs.items():
        task = _task_entry(manifest, str(spec["task"]))
        if task is None:
            continue
        selected.add(route)
        _record_check(
            checks,
            f"{route}.task_status",
            task.get("status") in {"completed", "skipped"},
            task.get("status"),
            "completed or skipped/reused",
        )
        outputs = dict(task.get("outputs") or {})
        for key, (minimum, maximum) in dict(spec["maps"]).items():
            value = outputs.get(key)
            path = Path(str(value)) if value else None
            exists = bool(path and path.is_file())
            _record_check(
                checks,
                f"{route}.{key}.exists",
                exists,
                path.as_posix() if path else None,
                "file exists",
            )
            if not exists or path is None:
                continue
            image = nib.load(path.as_posix())
            array = np.asarray(image.dataobj, dtype=np.float64)
            finite = bool(np.isfinite(array).all())
            _record_check(checks, f"{route}.{key}.finite", finite, None, "all values finite")
            if mask_image is not None and mask is not None:
                _record_check(
                    checks,
                    f"{route}.{key}.shape",
                    array.shape == mask.shape,
                    list(array.shape),
                    list(mask.shape),
                )
                _record_check(
                    checks,
                    f"{route}.{key}.affine",
                    bool(np.allclose(image.affine, mask_image.affine, atol=1e-4)),
                    float(np.max(np.abs(image.affine - mask_image.affine))),
                    "maximum absolute difference <= 1e-4",
                )
            values = array[mask] if mask is not None and array.shape == mask.shape and np.any(mask) else array.ravel()
            if not finite or values.size == 0:
                continue
            observed_min = float(np.min(values))
            observed_max = float(np.max(values))
            in_range = observed_min >= float(minimum) - 1e-6
            requirement = f">= {minimum}"
            if maximum is not None:
                in_range = in_range and observed_max <= float(maximum) + 1e-6
                requirement = f"{minimum} <= value <= {maximum}"
            _record_check(
                checks,
                f"{route}.{key}.range",
                in_range,
                {"min": observed_min, "max": observed_max},
                requirement,
            )
    return selected


def _json_record(path_value: Any) -> tuple[Path | None, dict[str, Any] | None]:
    path = Path(str(path_value)) if path_value else None
    if path is None or not path.is_file():
        return path, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return path, None
    return path, payload if isinstance(payload, dict) else None


def _audit_qc_routes(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> set[str]:
    route_specs = {
        "saf": ("tractography.saf", "streamline_count", 1),
        "wmql": ("bundles.wmql", "bundle_count", 1),
        "wma": ("bundles.wma", "anatomical_tract_count", 73),
        "tractcloud": ("bundles.tractcloud", "bundle_count", 1),
    }
    selected: set[str] = set()
    for route, (task_name, count_key, minimum_count) in route_specs.items():
        task = _task_entry(manifest, task_name)
        if task is None:
            continue
        selected.add(route)
        _record_check(
            checks,
            f"{route}.task_status",
            task.get("status") in {"completed", "skipped"},
            task.get("status"),
            "completed or skipped/reused",
        )
        outputs = dict(task.get("outputs") or {})
        qc_path, qc = _json_record(task.get("qc_path") or outputs.get("qc"))
        _record_check(
            checks,
            f"{route}.qc_exists",
            qc is not None,
            qc_path.as_posix() if qc_path else None,
            "readable QC JSON exists",
        )
        if qc is None:
            continue
        _record_check(checks, f"{route}.qc_status", qc.get("status") == "completed", qc.get("status"), "completed")
        summary = dict(qc.get("output_summary") or {})
        count_value = qc.get(count_key)
        if count_value is None:
            count_value = summary.get(count_key)
        try:
            count = int(count_value)
        except (TypeError, ValueError):
            count = 0
        _record_check(
            checks,
            f"{route}.{count_key}",
            count >= minimum_count,
            count,
            f">= {minimum_count}",
        )

        bundle_files = [Path(str(value)) for value in summary.get("bundle_files", [])]
        if bundle_files:
            valid_files = [path for path in bundle_files if path.is_file() and path.stat().st_size > 0]
            _record_check(
                checks,
                f"{route}.bundle_files",
                len(valid_files) == len(bundle_files) == count,
                {"declared": count, "listed": len(bundle_files), "valid": len(valid_files)},
                "declared, listed, and non-empty bundle counts match",
            )
        if route == "wma":
            anatomy_dir = Path(str(summary.get("anatomical_tracts_dir") or ""))
            anatomy_files = [path for path in anatomy_dir.glob("**/*") if path.is_file() and path.stat().st_size > 0] if anatomy_dir.is_dir() else []
            _record_check(
                checks,
                "wma.anatomical_tract_files",
                len(anatomy_files) >= minimum_count,
                len(anatomy_files),
                f">= {minimum_count} non-empty files",
            )
        if route == "saf":
            for key in ("saf_tractogram", "saf_vtk"):
                record = summary.get(key) or {}
                path = Path(str(record.get("path") or outputs.get("tractogram" if key == "saf_tractogram" else "tractogram_vtk") or ""))
                _record_check(
                    checks,
                    f"saf.{key}_file",
                    path.is_file() and path.stat().st_size > 0,
                    path.as_posix(),
                    "non-empty file exists",
                )
    return selected


def _audit_cross_route_inputs(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    route_pairs = (
        ("tractography.saf", "tractogram_vtk", "bundles.tractcloud", "tractcloud.input_matches_same_run_saf"),
        ("tractography.csd_act", "tractogram", "bundles.wma", "wma.input_matches_same_run_tractography"),
    )
    for source_task_name, source_key, consumer_task_name, check_name in route_pairs:
        source_task = _task_entry(manifest, source_task_name)
        consumer_task = _task_entry(manifest, consumer_task_name)
        if source_task is None or consumer_task is None:
            continue
        expected_value = dict(source_task.get("outputs") or {}).get(source_key)
        _, consumer_manifest = _json_record(consumer_task.get("manifest_path"))
        actual_value = consumer_manifest.get("input_tractography") if consumer_manifest else None
        expected = Path(str(expected_value)).resolve() if expected_value else None
        actual = Path(str(actual_value)).resolve() if actual_value else None
        _record_check(
            checks,
            check_name,
            expected is not None and actual == expected,
            {
                "expected": expected.as_posix() if expected else None,
                "actual": actual.as_posix() if actual else None,
            },
            "consumer input equals the producing task output from this run",
        )


def _audit_connectomes(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> bool:
    tasks = [
        task
        for task in manifest.get("tasks", [])
        if str(task.get("name") or "").startswith("connectome.")
    ]
    if not tasks:
        return False
    for task in tasks:
        task_name = str(task.get("name"))
        prefix = task_name.replace(".", "_")
        _record_check(
            checks,
            f"{prefix}.task_status",
            task.get("status") in {"completed", "skipped"},
            task.get("status"),
            "completed or skipped/reused",
        )
        outputs = dict(task.get("outputs") or {})
        qc_path, qc = _json_record(task.get("qc_path") or outputs.get("qc"))
        manifest_path, native_manifest = _json_record(task.get("manifest_path") or outputs.get("manifest"))
        _record_check(checks, f"{prefix}.qc_exists", qc is not None, qc_path.as_posix() if qc_path else None, "readable QC JSON exists")
        _record_check(
            checks,
            f"{prefix}.manifest_exists",
            native_manifest is not None,
            manifest_path.as_posix() if manifest_path else None,
            "readable manifest JSON exists",
        )
        if qc is None or native_manifest is None:
            continue
        _record_check(checks, f"{prefix}.qc_status", qc.get("status") == "completed", qc.get("status"), "completed")
        native_outputs = dict(native_manifest.get("outputs") or {})
        matrix_path = Path(str(outputs.get("matrix") or native_outputs.get("matrix") or ""))
        nodes_path = Path(str(outputs.get("nodes") or native_outputs.get("nodes") or ""))
        _record_check(checks, f"{prefix}.matrix_exists", matrix_path.is_file(), matrix_path.as_posix(), "file exists")
        _record_check(checks, f"{prefix}.nodes_exists", nodes_path.is_file(), nodes_path.as_posix(), "file exists")
        if not matrix_path.is_file() or not nodes_path.is_file():
            continue
        with matrix_path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        with nodes_path.open("r", encoding="utf-8", newline="") as stream:
            node_rows = list(csv.DictReader(stream, delimiter="\t"))
        metric = str(qc.get("metric") or native_manifest.get("metric") or "streamline_count")
        required_columns = {"source_node", "target_node", metric}
        columns = set(rows[0]) if rows else set()
        _record_check(checks, f"{prefix}.columns", required_columns.issubset(columns), sorted(columns), sorted(required_columns))
        try:
            pairs = [(int(row["source_node"]), int(row["target_node"])) for row in rows]
            values = [float(row[metric]) for row in rows]
        except (KeyError, TypeError, ValueError):
            pairs, values = [], []
        finite_nonnegative = bool(values) and all(math.isfinite(value) and value >= 0 for value in values)
        _record_check(checks, f"{prefix}.values", finite_nonnegative, len(values), "non-empty, finite, and non-negative")
        _record_check(checks, f"{prefix}.unique_edges", len(pairs) == len(set(pairs)), len(pairs), "no duplicate edges")
        _record_check(checks, f"{prefix}.upper_triangle", bool(pairs) and all(a <= b for a, b in pairs), None, "source_node <= target_node")
        node_labels = {int(row["label"]) for row in node_rows if str(row.get("label") or "").strip().lstrip("-").isdigit()}
        edge_labels = {value for pair in pairs for value in pair}
        _record_check(checks, f"{prefix}.node_labels", bool(node_labels) and edge_labels.issubset(node_labels), len(node_labels), "all edge labels occur in nodes TSV")
        edge_count = int(qc.get("edge_count") or 0)
        node_count = int(qc.get("node_count") or 0)
        _record_check(checks, f"{prefix}.edge_count", edge_count == len(rows), {"qc": edge_count, "file": len(rows)}, "QC and CSV match")
        _record_check(checks, f"{prefix}.node_count", node_count == len(node_rows), {"qc": node_count, "file": len(node_rows)}, "QC and TSV match")
        if metric == "streamline_count" and qc.get("streamline_count_assigned") is not None and values:
            assigned = int(qc["streamline_count_assigned"])
            _record_check(
                checks,
                f"{prefix}.assigned_streamlines",
                math.isclose(sum(values), assigned, rel_tol=0.0, abs_tol=1e-6),
                {"qc": assigned, "csv_sum": sum(values)},
                "CSV edge counts sum to QC assigned streamlines",
            )
    return True


def _audit_structural(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> set[str]:
    import nibabel as nib
    import numpy as np
    from nibabel.processing import resample_from_to

    output_root_value = manifest.get("output_root")
    if not output_root_value:
        return set()
    output_root = Path(str(output_root_value))
    subject_root = Path(str(manifest["subject_root"]))
    subject_id = str(manifest["subject_id"])
    structural_root = output_root / "03_structural"
    ddseg_dir = structural_root / "ddseg"
    ddparcel_dir = structural_root / "ddparcel"
    surface_dir = structural_root / "ddsurfer"
    task_names = {
        "ddseg": "segmentation.ddseg",
        "ddparcel": "parcellation.ddparcel",
        "ddsurfer": "surface.ddsurfer",
    }
    selected = {
        route
        for route, task_name in task_names.items()
        if _task_entry(manifest, task_name) is not None
    }
    if not selected:
        return set()

    mask_path = subject_root / "input" / "nodif_brain_mask.nii.gz"
    if not mask_path.is_file():
        _record_check(checks, "structural.mask_exists", False, mask_path.as_posix(), "file exists")
        return selected
    mask_image = nib.load(mask_path.as_posix())
    mask = np.asarray(mask_image.dataobj) > 0

    ddseg_outputs = _task_outputs(manifest, task_names["ddseg"])
    segmentation_path = Path(
        str(ddseg_outputs.get("segmentation") or ddseg_dir / "SegmentationMap_GMWMCSF.nii.gz")
    )
    probability_paths = {
        "gm": Path(str(ddseg_outputs.get("gm_probability") or ddseg_dir / "ProbabilisticMap_GM.nii.gz")),
        "wm": Path(str(ddseg_outputs.get("wm_probability") or ddseg_dir / "ProbabilisticMap_WM.nii.gz")),
        "csf": Path(str(ddseg_outputs.get("csf_probability") or ddseg_dir / "ProbabilisticMap_CSF.nii.gz")),
    }
    if "ddseg" in selected:
        _record_check(
            checks,
            "structural.ddseg.segmentation_exists",
            segmentation_path.is_file(),
            segmentation_path.as_posix(),
            "file exists",
        )
    if "ddseg" in selected and segmentation_path.is_file():
        segmentation_image = nib.load(segmentation_path.as_posix())
        segmentation = np.asarray(segmentation_image.dataobj, dtype=np.float64)
        rounded = np.rint(segmentation)
        _record_check(
            checks,
            "structural.ddseg.labels_discrete",
            bool(np.allclose(segmentation, rounded, atol=1e-4)),
            sorted(float(value) for value in np.unique(segmentation)),
            "all labels are integers",
        )
        label_set = {int(value) for value in np.unique(rounded)}
        _record_check(
            checks,
            "structural.ddseg.labels",
            label_set.issubset({0, 1, 2, 3}) and {1, 2, 3}.issubset(label_set),
            sorted(label_set),
            "labels are 0/1/2/3 and all three tissue classes are present",
        )
        native_segmentation = np.asarray(
            resample_from_to(segmentation_image, mask_image, order=0).dataobj
        ) > 0
        denominator = int(mask.sum()) + int(native_segmentation.sum())
        dice = (
            2.0 * float(np.count_nonzero(mask & native_segmentation)) / denominator
            if denominator
            else 0.0
        )
        _record_check(
            checks,
            "structural.ddseg.world_overlap",
            dice >= 0.95,
            dice,
            "foreground Dice with input mask after world-space resampling >= 0.95",
        )

        probability_arrays: dict[str, Any] = {}
        for name, path in probability_paths.items():
            exists = path.is_file()
            _record_check(
                checks,
                f"structural.ddseg.{name}_probability_exists",
                exists,
                path.as_posix(),
                "file exists",
            )
            if not exists:
                continue
            image = nib.load(path.as_posix())
            array = np.asarray(image.dataobj, dtype=np.float64)
            probability_arrays[name] = array
            _record_check(
                checks,
                f"structural.ddseg.{name}_probability_shape",
                array.shape == segmentation.shape,
                list(array.shape),
                list(segmentation.shape),
            )
            _record_check(
                checks,
                f"structural.ddseg.{name}_probability_range",
                bool(np.isfinite(array).all() and np.min(array) >= -1e-6 and np.max(array) <= 1.0 + 1e-6),
                {"min": float(np.min(array)), "max": float(np.max(array))},
                "all values finite and within [0, 1]",
            )
        if len(probability_arrays) == 3:
            foreground = rounded > 0
            probability_stack = np.stack(
                [probability_arrays[name] for name in ("gm", "wm", "csf")],
                axis=-1,
            )
            probability_sum = np.sum(probability_stack, axis=-1)
            foreground_mass = probability_sum[foreground]
            valid_mass = np.isfinite(foreground_mass) & (foreground_mass > 0.0) & (
                foreground_mass <= 1.0 + 1e-5
            )
            valid_mass_fraction = float(np.mean(valid_mass)) if foreground_mass.size else 0.0
            _record_check(
                checks,
                "structural.ddseg.probability_mass",
                valid_mass_fraction >= 0.999,
                {
                    "valid_fraction": valid_mass_fraction,
                    "min": float(np.min(foreground_mass)) if foreground_mass.size else None,
                    "max": float(np.max(foreground_mass)) if foreground_mass.size else None,
                },
                ">= 0.999 of segmented voxels have finite, non-zero GM+WM+CSF mass <= 1",
            )
            predicted_labels = np.asarray((2, 1, 3), dtype=np.int16)[
                np.argmax(probability_stack, axis=-1)
            ]
            label_agreement = float(np.mean(predicted_labels[foreground] == rounded[foreground]))
            _record_check(
                checks,
                "structural.ddseg.probability_label_agreement",
                label_agreement >= 0.999,
                label_agreement,
                ">= 0.999 agreement between the maximum tissue probability and segmentation label",
            )

    ddparcel_outputs = _task_outputs(manifest, task_names["ddparcel"])
    parcellation_path = Path(
        str(ddparcel_outputs.get("wmparc") or ddparcel_dir / f"{subject_id}-DDSurfer-wmparc.nii.gz")
    )
    if "ddparcel" in selected:
        _record_check(
            checks,
            "structural.ddparcel.exists",
            parcellation_path.is_file(),
            parcellation_path.as_posix(),
            "file exists",
        )
    if "ddparcel" in selected and parcellation_path.is_file():
        image = nib.load(parcellation_path.as_posix())
        array = np.asarray(image.dataobj, dtype=np.float64)
        rounded = np.rint(array)
        labels = np.unique(rounded)
        _record_check(
            checks,
            "structural.ddparcel.shape",
            array.shape == mask.shape,
            list(array.shape),
            list(mask.shape),
        )
        _record_check(
            checks,
            "structural.ddparcel.affine",
            bool(np.allclose(image.affine, mask_image.affine, atol=1e-4)),
            float(np.max(np.abs(image.affine - mask_image.affine))),
            "maximum absolute affine difference <= 1e-4",
        )
        _record_check(
            checks,
            "structural.ddparcel.labels_discrete",
            bool(np.isfinite(array).all() and np.allclose(array, rounded, atol=1e-4)),
            None,
            "all labels finite and integer-valued",
        )
        nonzero_label_count = int(np.count_nonzero(labels > 0))
        _record_check(
            checks,
            "structural.ddparcel.label_count",
            nonzero_label_count >= 50,
            nonzero_label_count,
            ">= 50 nonzero anatomical labels",
        )

    ddsurfer_outputs = _task_outputs(manifest, task_names["ddsurfer"])
    expected_models = {
        f"{surface}_{hemi}": Path(
            str(
                ddsurfer_outputs.get(
                    {"wm": "white", "pial": "pial"}[surface] + f"_{hemi}"
                )
                or surface_dir
                / "pred_results_SlicerDDSurfer"
                / "native"
                / subject_id
                / f"{subject_id}_predicted_{surface}_{hemi}.stl"
            )
        )
        for surface in ("wm", "pial")
        for hemi in ("lh", "rh")
    }
    for name, model_path in expected_models.items():
        if "ddsurfer" not in selected:
            continue
        exists = model_path.is_file()
        _record_check(
            checks,
            f"structural.ddsurfer.{name}_exists",
            exists,
            model_path.as_posix(),
            "file exists",
        )
        if not exists:
            continue
        import trimesh

        mesh = trimesh.load(model_path.as_posix(), process=False)
        vertices = np.asarray(mesh.vertices)
        faces = np.asarray(mesh.faces)
        extents = np.ptp(vertices, axis=0) if vertices.size else np.zeros(3)
        valid = bool(
            len(vertices) >= 1000
            and len(faces) >= 1000
            and np.isfinite(vertices).all()
            and np.all(extents > 10.0)
        )
        _record_check(
            checks,
            f"structural.ddsurfer.{name}_geometry",
            valid,
            {
                "vertices": int(len(vertices)),
                "faces": int(len(faces)),
                "extents_mm": extents.tolist(),
            },
            ">= 1000 vertices/faces, finite coordinates, and > 10 mm extent on each axis",
        )
    return selected


def audit_output_root(
    output_root: Path,
    *,
    require_dti: bool = False,
    require_tractography: bool = False,
    require_structural: bool = False,
    require_full_routes: bool = False,
    min_subjects: int = 1,
    run_name: str | None = None,
) -> dict[str, Any]:
    root = output_root.expanduser().resolve()
    subjects: list[dict[str, Any]] = []
    for subject_output in sorted(path for path in root.iterdir() if path.is_dir() and path.name != "00_batch_metadata"):
        manifest_path = _manifest_for_run(subject_output, run_name)
        if manifest_path is None:
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        checks: list[dict[str, Any]] = []
        has_dti = _audit_dti(manifest, checks)
        has_tractography = _audit_tractography(manifest, checks)
        structural_routes = _audit_structural(manifest, checks)
        optional_microstructure_routes = _audit_optional_microstructure(manifest, checks)
        qc_routes = _audit_qc_routes(manifest, checks)
        _audit_cross_route_inputs(manifest, checks)
        has_connectome = _audit_connectomes(manifest, checks)
        if require_dti:
            _record_check(checks, "required.dti", has_dti, has_dti, "DTI outputs present")
        if require_tractography:
            _record_check(
                checks,
                "required.tractography",
                has_tractography,
                has_tractography,
                "tractography output present",
            )
        if require_structural:
            required_routes = {"ddseg", "ddparcel", "ddsurfer"}
            has_structural = required_routes.issubset(structural_routes)
            _record_check(
                checks,
                "required.structural",
                has_structural,
                has_structural,
                "DDSeg, DDParcel, and DDSurfer tasks present",
            )
        if require_full_routes:
            observed_routes = set(optional_microstructure_routes) | set(qc_routes)
            if has_connectome:
                observed_routes.add("connectome")
            missing_routes = sorted(FULL_ROUTE_NAMES - observed_routes)
            _record_check(
                checks,
                "required.full_routes",
                not missing_routes,
                {"observed": sorted(observed_routes), "missing": missing_routes},
                "Free Water, NODDI, SAF, WMQL, WMA, TractCloud, and connectome tasks present",
            )
        failed = [check for check in checks if not check["passed"]]
        subjects.append(
            {
                "subject_id": str(manifest.get("subject_id") or subject_output.name),
                "manifest_path": manifest_path.as_posix(),
                "status": "failed" if failed else "passed",
                "failed_check_count": len(failed),
                "checks": checks,
            }
        )

    enough_subjects = len(subjects) >= int(min_subjects)
    failed_subjects = [subject for subject in subjects if subject["status"] != "passed"]
    status = "passed" if enough_subjects and not failed_subjects else "failed"
    return {
        "kind": "slicerdsurfer_scientific_output_audit",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "output_root": root.as_posix(),
        "status": status,
        "requirements": {
            "require_dti": bool(require_dti),
            "require_tractography": bool(require_tractography),
            "require_structural": bool(require_structural),
            "require_full_routes": bool(require_full_routes),
            "min_subjects": int(min_subjects),
            "run_name": run_name,
        },
        "summary": {
            "subject_count": len(subjects),
            "passed_subjects": len(subjects) - len(failed_subjects),
            "failed_subjects": len(failed_subjects),
            "minimum_subject_count_met": enough_subjects,
        },
        "subjects": subjects,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True, help="Batch output root containing subject directories.")
    parser.add_argument("--report", type=Path, help="JSON report path. Defaults under 00_batch_metadata.")
    parser.add_argument("--require-dti", action="store_true", help="Fail when a subject lacks completed DTI outputs.")
    parser.add_argument(
        "--require-tractography",
        action="store_true",
        help="Fail when a subject lacks completed DTI or CSD/ACT tractography output.",
    )
    parser.add_argument(
        "--require-structural",
        action="store_true",
        help="Fail when a subject lacks any of DDSeg, DDParcel, or DDSurfer outputs.",
    )
    parser.add_argument(
        "--require-full-routes",
        action="store_true",
        help="Fail unless Free Water, NODDI, SAF, WMQL, WMA, TractCloud, and connectome outputs are audited.",
    )
    parser.add_argument("--min-subjects", type=int, default=1, help="Minimum number of audited subjects.")
    parser.add_argument(
        "--run-name",
        help="Audit this exact orchestration run instead of the most recently modified manifest.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.min_subjects < 1:
        raise SystemExit("--min-subjects must be >= 1")
    report = audit_output_root(
        args.output_root,
        require_dti=bool(args.require_dti),
        require_tractography=bool(args.require_tractography),
        require_structural=bool(args.require_structural),
        require_full_routes=bool(args.require_full_routes),
        min_subjects=int(args.min_subjects),
        run_name=args.run_name,
    )
    report_path = args.report or (
        args.output_root.expanduser().resolve() / "00_batch_metadata" / "scientific_output_audit.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    print(report_path)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
