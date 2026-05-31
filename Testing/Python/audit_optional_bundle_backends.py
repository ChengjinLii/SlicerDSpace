#!/usr/bin/env python3
"""Audit optional WMA and TractCloud bundle backends without executing models."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _safe_call(fn, *args, **kwargs) -> dict[str, Any]:
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
        }


def _file_info(path: Optional[Path]) -> Optional[dict[str, Any]]:
    if path is None:
        return None
    expanded = path.expanduser()
    if not expanded.exists():
        return {"path": expanded.as_posix(), "exists": False}
    stat = expanded.stat()
    return {
        "path": expanded.resolve().as_posix(),
        "exists": True,
        "is_file": expanded.is_file(),
        "size": stat.st_size,
    }


def _summarize_tractography_inputs(paths: list[Path]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for path in paths:
        info = _file_info(path)
        if info is not None:
            info["supported_by_wma"] = path.suffix.lower() in {".vtk", ".vtp"}
            info["supported_by_tractcloud"] = path.suffix.lower() in {".vtk", ".vtp"}
            summary.append(info)
    return summary


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    from tractography.tractcloud import inspect_tractcloud_backend
    from tractography.wma import inspect_wma_backend, inspect_wma_org_atlas

    wma_root = Path(args.wma_root).expanduser() if args.wma_root else None
    atlas_dir = Path(args.wma_atlas_dir).expanduser() if args.wma_atlas_dir else None
    tractcloud_root = Path(args.tractcloud_root).expanduser() if args.tractcloud_root else None
    tractcloud_python = Path(args.tractcloud_python).expanduser() if args.tractcloud_python else None
    tractography_inputs = [Path(value).expanduser() for value in args.input_tractography]

    wma_backend = _safe_call(
        inspect_wma_backend,
        wma_root,
        require_virtual_x=bool(args.require_virtual_x),
        require_diffusion_measurements=bool(args.require_diffusion_measurements),
    )
    wma_atlas = (
        _safe_call(inspect_wma_org_atlas, atlas_dir)
        if atlas_dir is not None
        else {"available": False, "error": "wma_atlas_dir was not provided"}
    )
    tractcloud_backend = _safe_call(
        inspect_tractcloud_backend,
        python_executable=tractcloud_python,
        tractcloud_root=tractcloud_root,
    )

    wma_ready = bool(wma_backend.get("available")) and bool(wma_atlas.get("available"))
    tractcloud_ready = bool(tractcloud_backend.get("available"))
    blockers: list[str] = []
    if not wma_ready:
        if not wma_backend.get("available"):
            blockers.append("WMA backend is incomplete or not configured")
        if not wma_atlas.get("available"):
            blockers.append("WMA ORG atlas is missing or incomplete")
    if not tractcloud_ready:
        packages = tractcloud_backend.get("packages")
        if isinstance(packages, dict):
            missing = [name for name, available in packages.items() if not available]
            blockers.append("TractCloud missing package(s): " + ", ".join(missing))
        else:
            blockers.append("TractCloud backend is incomplete or not configured")

    return {
        "kind": "optional_bundle_backend_audit",
        "version": 1,
        "ready": {
            "wma_org_atlas": wma_ready,
            "tractcloud": tractcloud_ready,
        },
        "blockers": blockers,
        "inputs": {
            "wma_root": _file_info(wma_root),
            "wma_atlas_dir": _file_info(atlas_dir),
            "tractcloud_root": _file_info(tractcloud_root),
            "tractcloud_python": _file_info(tractcloud_python),
            "input_tractography": _summarize_tractography_inputs(tractography_inputs),
        },
        "wma": {
            "backend": wma_backend,
            "atlas": wma_atlas,
        },
        "tractcloud": {
            "backend": tractcloud_backend,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wma-root", default=None, help="Explicit external WhiteMatterAnalysis checkout.")
    parser.add_argument("--wma-atlas-dir", default=None, help="Explicit ORG atlas directory.")
    parser.add_argument("--require-virtual-x", action="store_true", help="Require xvfb-run for WMA.")
    parser.add_argument(
        "--require-diffusion-measurements",
        action="store_true",
        help="Require wm_diffusion_measurements.py for WMA diffusion metrics export.",
    )
    parser.add_argument("--tractcloud-root", default=None, help="Explicit TractCloud source checkout.")
    parser.add_argument("--tractcloud-python", default=None, help="Python executable used for TractCloud probe.")
    parser.add_argument(
        "--input-tractography",
        action="append",
        default=[],
        help="Optional VTK/VTP tractography input candidates to include in the report.",
    )
    parser.add_argument("--output", required=True, help="Path to write audit JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    print(json.dumps(report["ready"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
