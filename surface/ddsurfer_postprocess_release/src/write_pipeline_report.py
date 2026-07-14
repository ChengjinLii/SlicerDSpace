#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write manifest/QC/provenance for optimized DDSurfer postprocess.")
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--input-subject-dir", required=True)
    parser.add_argument("--structural-root", required=True)
    parser.add_argument("--stats-root", required=True)
    parser.add_argument("--subject-path", required=True)
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--stages", required=True)
    parser.add_argument("--atlases", required=True)
    parser.add_argument("--freesurfer-home", default="")
    parser.add_argument("--stage-mode", required=True)
    parser.add_argument("--freesurfer-available", default="false")
    parser.add_argument("--validation-json", required=True)
    parser.add_argument("--manifest-json", required=True)
    parser.add_argument("--qc-json", required=True)
    parser.add_argument("--provenance-json", required=True)
    return parser.parse_args()


def file_record(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def find_outputs(subject_path: Path, structural_root: Path, stats_root: Path) -> dict[str, object]:
    surf = subject_path / "surf"
    label = subject_path / "label"
    stats = subject_path / "stats"
    fsaverage_root = structural_root / "fsaverage"
    return {
        "mri_dir": str((subject_path / "mri").resolve()) if (subject_path / "mri").exists() else str(subject_path / "mri"),
        "surf_dir": str(surf.resolve()) if surf.exists() else str(surf),
        "label_dir": str(label.resolve()) if label.exists() else str(label),
        "stats_dir": str(stats.resolve()) if stats.exists() else str(stats),
        "canonical_stats_dir": str(stats_root.resolve()) if stats_root.exists() else str(stats_root),
        "fsaverage_dir": str(fsaverage_root.resolve()) if fsaverage_root.exists() else str(fsaverage_root),
    }


def list_matching(root: Path, pattern: str) -> list[str]:
    if not root.exists():
        return []
    return sorted(str(path.resolve()) for path in root.glob(pattern))


def stats_data_row_count(path: Path) -> int:
    """Return the number of non-empty, non-comment records in a stats file."""
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        return sum(1 for line in stream if line.strip() and not line.lstrip().startswith("#"))


def requested_hemispheres(mode: str) -> tuple[str, ...]:
    normalized = mode.strip().lower()
    if normalized == "left":
        return ("lh",)
    if normalized == "right":
        return ("rh",)
    if normalized == "whole":
        return ("lh", "rh")
    raise ValueError(f"Unsupported postprocess mode: {mode!r}")


def stats_integrity(subject_path: Path, mode: str, atlases: list[str]) -> dict[str, object]:
    """Describe whether every requested regional and wmparc stats file has data."""
    atlas_names = list(dict.fromkeys(atlas.strip() for atlas in atlases if atlas.strip()))
    expected_paths = [
        subject_path / "stats" / filename
        for hemi in requested_hemispheres(mode)
        for filename in (
            f"{hemi}.wmparc.stats",
            *(f"{hemi}.{atlas}.stats" for atlas in atlas_names),
        )
    ]
    row_counts = {
        path.name: stats_data_row_count(path)
        for path in expected_paths
        if path.is_file()
    }
    missing = [path.name for path in expected_paths if not path.is_file()]
    empty = [path.name for path in expected_paths if path.is_file() and row_counts[path.name] == 0]
    nonempty = [path.name for path in expected_paths if path.is_file() and row_counts[path.name] > 0]
    return {
        "stats_expected_count": len(expected_paths),
        "stats_nonempty_count": len(nonempty),
        "stats_expected_files": [path.name for path in expected_paths],
        "stats_nonempty_files": nonempty,
        "stats_missing_files": missing,
        "stats_empty_files": empty,
        "stats_data_rows": row_counts,
    }


def stage_statuses(
    subject_path: Path,
    structural_root: Path,
    stats_root: Path,
    requested_stages: list[str],
    mode: str,
    atlases: list[str],
) -> dict[str, str]:
    statuses = {stage: "not_requested" for stage in [
        "validate_inputs",
        "stage_inputs",
        "convert_surfaces",
        "build_fs_surfaces",
        "project_annotations",
        "extract_labels",
        "compute_stats",
        "resample_fsaverage",
        "sync_outputs",
    ]}
    for stage in requested_stages:
        statuses[stage] = "requested"

    if (structural_root / "validation.json").is_file():
        statuses["validate_inputs"] = "completed"
    if (subject_path / "mri" / "DDSurfer-wmparc.nii.gz").exists() and (subject_path / "surf").exists():
        statuses["stage_inputs"] = "completed"
    if (subject_path / "surf" / "lh.white").exists() or (subject_path / "surf" / "rh.white").exists():
        statuses["convert_surfaces"] = "completed"
    if (subject_path / "surf" / "lh.sphere.reg").exists() or (subject_path / "surf" / "rh.sphere.reg").exists():
        statuses["build_fs_surfaces"] = "completed"
    if list_matching(subject_path / "label", "*.annot"):
        statuses["project_annotations"] = "completed"
    if list_matching(subject_path / "label", "regions_*"):
        statuses["extract_labels"] = "completed"
    stats_qc = stats_integrity(subject_path, mode, atlases)
    if (
        stats_qc["stats_expected_count"] > 0
        and stats_qc["stats_nonempty_count"] == stats_qc["stats_expected_count"]
    ):
        statuses["compute_stats"] = "completed"
    if list_matching(structural_root / "fsaverage", "*.fsaverage.mgh"):
        statuses["resample_fsaverage"] = "completed"
    sync_ready = (structural_root / "surf").exists()
    if "compute_stats" not in requested_stages and "resample_fsaverage" not in requested_stages:
        if sync_ready:
            statuses["sync_outputs"] = "completed"
    elif sync_ready and (stats_root / "stats").exists():
        statuses["sync_outputs"] = "completed"
    for stage, status in list(statuses.items()):
        if status == "requested":
            statuses[stage] = "running"
    return statuses


def main() -> int:
    args = parse_args()
    subject_path = Path(args.subject_path).expanduser().resolve()
    structural_root = Path(args.structural_root).expanduser().resolve()
    stats_root = Path(args.stats_root).expanduser().resolve()
    validation_path = Path(args.validation_json).expanduser().resolve()
    manifest_path = Path(args.manifest_json).expanduser().resolve()
    qc_path = Path(args.qc_json).expanduser().resolve()
    provenance_path = Path(args.provenance_json).expanduser().resolve()
    stages = [item.strip() for item in args.stages.split(",") if item.strip()]
    atlases = [item.strip() for item in args.atlases.split(",") if item.strip()]
    validation_payload = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.is_file() else {}

    outputs = find_outputs(subject_path, structural_root, stats_root)
    stats_qc = stats_integrity(subject_path, args.mode, atlases)
    statuses = stage_statuses(subject_path, structural_root, stats_root, stages, args.mode, atlases)

    manifest = {
        "kind": "ddsurfer_postprocess",
        "version": 1,
        "subject_id": args.subject_id,
        "mode": args.mode,
        "stage_mode": args.stage_mode,
        "stages_requested": stages,
        "atlases_requested": atlases,
        "freesurfer_home": args.freesurfer_home,
        "freesurfer_available": args.freesurfer_available.lower() == "true",
        "inputs": {
            "subject_dir": str(Path(args.input_subject_dir).expanduser().resolve()),
            "validation": file_record(validation_path),
            "validated_files": validation_payload.get("checks", {}),
        },
        "outputs": outputs,
        "stage_status": statuses,
    }

    qc = {
        "kind": "ddsurfer_postprocess_qc",
        "subject_id": args.subject_id,
        "status": "completed" if all(statuses[s] in {"completed", "not_requested"} for s in statuses) else "partial",
        "core_outputs": {
            "lh_white": file_record(subject_path / "surf" / "lh.white"),
            "rh_white": file_record(subject_path / "surf" / "rh.white"),
            "lh_pial": file_record(subject_path / "surf" / "lh.pial"),
            "rh_pial": file_record(subject_path / "surf" / "rh.pial"),
            "annot_count": len(list_matching(subject_path / "label", "*.annot")),
            "stats_count": len(list_matching(subject_path / "stats", "*.stats")),
            "fsaverage_overlay_count": len(list_matching(structural_root / "fsaverage", "*.fsaverage.mgh")),
            **stats_qc,
        },
    }

    provenance = {
        "kind": "ddsurfer_postprocess_provenance",
        "subject_id": args.subject_id,
        "cwd": os.getcwd(),
        "env": {
            "FREESURFER_HOME": args.freesurfer_home,
            "PYTHON_BIN": os.environ.get("PYTHON_BIN", ""),
        },
        "paths": {
            "subject_path": str(subject_path),
            "structural_root": str(structural_root),
            "stats_root": str(stats_root),
            "log_file": str(Path(args.log_file).expanduser().resolve()),
        },
        "stages_requested": stages,
        "atlases_requested": atlases,
    }

    for path, payload in (
        (manifest_path, manifest),
        (qc_path, qc),
        (provenance_path, provenance),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
