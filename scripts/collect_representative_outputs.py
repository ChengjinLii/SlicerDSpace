#!/usr/bin/env python3
"""Collect representative output evidence for release/manuscript review.

The collector is intentionally metadata-only. It scans a SlicerDSpace output
tree for representative product files, QC/provenance records, and timing values
that can support manuscript figures or release validation without copying
restricted neuroimaging data into the repository.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any


REPRESENTATIVE_PATTERNS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("segmentation", "tissue segmentation maps", ("*Segmentation*.nii.gz", "*segmentation*.nii.gz")),
    ("parcellation", "anatomical parcellation labels", ("*parcel*.nii.gz", "*parcellation*.nii.gz", "*.mgz")),
    ("surface", "cortical and white-matter surfaces", ("*.stl", "*.obj", "*.vtk", "*.vtp")),
    ("microstructure", "DTI and optional microstructure maps", ("*FA*.nii.gz", "*MD*.nii.gz", "*freewater*.nii.gz", "*noddi*.nii.gz")),
    ("tractography", "whole-brain or SAF tractograms", ("*.tck", "*.trk")),
    ("bundles", "bundle-level outputs", ("*bundle*.vtk", "*bundle*.vtp", "*wmql*", "*wma*", "*tractcloud*")),
    ("connectome", "connectome matrices", ("*connectome*.csv", "*matrix*.csv", "*.tsv")),
    ("qc", "quality-control records", ("*qc*.json", "*QC*.json")),
    ("provenance", "provenance and processing records", ("*provenance*.json", "*manifest*.json", "*summary*.md")),
)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _find_matches(root: Path, patterns: tuple[str, ...], *, limit: int) -> list[Path]:
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(path for path in root.rglob(pattern) if path.is_file())
    unique = sorted(dict.fromkeys(matches))
    return unique[:limit]


def _json_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def _collect_timing_records(root: Path) -> list[dict[str, Any]]:
    timing_keys = {
        "elapsed_seconds",
        "duration_seconds",
        "runtime_seconds",
        "started_at",
        "finished_at",
        "created_at_unix",
    }
    records: list[dict[str, Any]] = []
    for path in _json_files(root):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        stack = [payload]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                present = {key: item.get(key) for key in timing_keys if key in item}
                if present:
                    records.append(
                        {
                            "source": _relative(path, root),
                            "name": item.get("name") or item.get("target") or item.get("kind") or "",
                            **present,
                        }
                    )
                stack.extend(value for value in item.values() if isinstance(value, (dict, list)))
            elif isinstance(item, list):
                stack.extend(value for value in item if isinstance(value, (dict, list)))
    return records


def collect_representative_outputs(output_root: Path, *, per_category_limit: int = 12) -> dict[str, Any]:
    root = output_root.expanduser().resolve()
    categories = []
    for category, role, patterns in REPRESENTATIVE_PATTERNS:
        matches = _find_matches(root, patterns, limit=per_category_limit)
        categories.append(
            {
                "category": category,
                "role": role,
                "patterns": list(patterns),
                "count": len(matches),
                "examples": [
                    {
                        "path": _relative(path, root),
                        "size_bytes": path.stat().st_size,
                    }
                    for path in matches
                ],
            }
        )
    timing_records = _collect_timing_records(root)
    return {
        "kind": "slicerdsurfer_representative_outputs",
        "version": 1,
        "created_at_unix": int(time.time()),
        "output_root": root.as_posix(),
        "categories": categories,
        "timing_records": timing_records,
        "summary": {
            "categories_with_examples": sum(1 for category in categories if category["count"]),
            "example_file_count": sum(category["count"] for category in categories),
            "timing_record_count": len(timing_records),
        },
    }


def write_reports(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "representative_outputs.json"
    csv_path = output_dir / "representative_outputs_source_data.csv"
    timing_path = output_dir / "representative_outputs_timing.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("category", "role", "path", "size_bytes"))
        writer.writeheader()
        for category in report["categories"]:
            for example in category["examples"]:
                writer.writerow(
                    {
                        "category": category["category"],
                        "role": category["role"],
                        "path": example["path"],
                        "size_bytes": example["size_bytes"],
                    }
                )
    timing_path.write_text(json.dumps(report["timing_records"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"json": json_path, "source_csv": csv_path, "timing_json": timing_path}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--dest-dir", type=Path, required=True)
    parser.add_argument("--per-category-limit", type=int, default=12)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = collect_representative_outputs(args.output_root, per_category_limit=max(1, args.per_category_limit))
    written = write_reports(report, args.dest_dir)
    print(json.dumps({key: path.as_posix() for key, path in written.items()}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
