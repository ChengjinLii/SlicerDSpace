"""Subject-level report/provenance generation for SlicerDDSurfer outputs."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .io_layout import normalize_run_name, subject_layout


@dataclass(frozen=True)
class SubjectReportPaths:
    """Paths written by the subject report generator."""

    report_html: Path
    provenance_json: Path
    qc_summary_json: Path
    report_html_latest: Path
    provenance_json_latest: Path
    qc_summary_json_latest: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "report_html": self.report_html.as_posix(),
            "provenance_json": self.provenance_json.as_posix(),
            "qc_summary_json": self.qc_summary_json.as_posix(),
            "report_html_latest": self.report_html_latest.as_posix(),
            "provenance_json_latest": self.provenance_json_latest.as_posix(),
            "qc_summary_json_latest": self.qc_summary_json_latest.as_posix(),
        }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _collect_output_tree(output_root: Path, *, max_files: int = 2500) -> dict[str, Any]:
    top_dirs: dict[str, int] = {}
    files: list[dict[str, Any]] = []
    total_files = 0
    total_bytes = 0
    if not output_root.exists():
        return {
            "output_root": output_root.as_posix(),
            "exists": False,
            "top_dirs": top_dirs,
            "files": files,
            "file_count": 0,
            "total_bytes": 0,
            "truncated": False,
        }
    for child in sorted(output_root.iterdir()):
        if child.is_dir():
            top_dirs[child.name] = sum(1 for item in child.rglob("*") if item.is_file())
    for path in sorted(output_root.rglob("*")):
        if not path.is_file():
            continue
        total_files += 1
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        total_bytes += size
        if len(files) < max_files:
            files.append(
                {
                    "path": _relative(path, output_root),
                    "size_bytes": size,
                }
            )
    return {
        "output_root": output_root.as_posix(),
        "exists": True,
        "top_dirs": top_dirs,
        "files": files,
        "file_count": total_files,
        "total_bytes": total_bytes,
        "truncated": total_files > len(files),
    }


def _collect_qc_files(output_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not output_root.exists():
        return records
    for path in sorted(output_root.rglob("*qc.json")):
        payload = _read_json(path)
        records.append(
            {
                "path": _relative(path, output_root),
                "status": payload.get("status"),
                "kind": payload.get("kind"),
                "summary": {
                    key: value
                    for key, value in payload.items()
                    if key
                    in {
                        "status",
                        "streamline_count",
                        "assigned_streamlines",
                        "edge_count",
                        "node_count",
                        "bundle_count",
                        "anatomical_tract_count",
                        "warnings",
                        "errors",
                    }
                },
            }
        )
    return records


def _task_summary(manifest: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in manifest.get("tasks", []):
        status = str(task.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _build_provenance(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
    output_tree: dict[str, Any],
    qc_records: list[dict[str, Any]],
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "kind": "slicerddsurfer_subject_provenance",
        "version": 1,
        "generated_at": generated_at,
        "subject_id": manifest.get("subject_id"),
        "subject_root": manifest.get("subject_root"),
        "output_root": manifest.get("output_root"),
        "run_name": manifest.get("run_name"),
        "orchestration_manifest": manifest_path.as_posix(),
        "targets": manifest.get("targets", []),
        "run_targets": manifest.get("run_targets", []),
        "run_plan_summary": manifest.get("run_plan_summary", {}),
        "task_summary": _task_summary(manifest),
        "preflight_blocked_targets": manifest.get("preflight_blocked_targets", {}),
        "archived_development_outputs": manifest.get("archived_development_outputs", {}),
        "output_tree": {
            "top_dirs": output_tree.get("top_dirs", {}),
            "file_count": output_tree.get("file_count", 0),
            "total_bytes": output_tree.get("total_bytes", 0),
            "truncated": output_tree.get("truncated", False),
        },
        "qc_file_count": len(qc_records),
    }


def _build_qc_summary(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
    output_tree: dict[str, Any],
    qc_records: list[dict[str, Any]],
) -> dict[str, Any]:
    tasks = manifest.get("tasks", [])
    return {
        "kind": "slicerddsurfer_subject_qc_summary",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_id": manifest.get("subject_id"),
        "run_name": manifest.get("run_name"),
        "orchestration_manifest": manifest_path.as_posix(),
        "run_plan_summary": manifest.get("run_plan_summary", {}),
        "task_summary": _task_summary(manifest),
        "tasks": [
            {
                "name": task.get("name"),
                "status": task.get("status"),
                "reason": task.get("reason"),
                "qc_path": task.get("qc_path"),
                "manifest_path": task.get("manifest_path"),
            }
            for task in tasks
        ],
        "preflight_blocked_targets": manifest.get("preflight_blocked_targets", {}),
        "output_tree_audit_path": manifest.get("output_tree_audit_path"),
        "output_tree_warnings": manifest.get("output_tree_warnings", []),
        "output_tree": output_tree,
        "qc_files": qc_records,
    }


def _html_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "<p class=\"muted\">None.</p>"
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(column, '') or ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _build_html_report(
    *,
    manifest: dict[str, Any],
    provenance: dict[str, Any],
    qc_summary: dict[str, Any],
    paths: SubjectReportPaths,
) -> str:
    tasks = [
        {
            "name": task.get("name"),
            "status": task.get("status"),
            "reason": task.get("reason"),
        }
        for task in manifest.get("tasks", [])
    ]
    output_rows = [
        {"top_dir": key, "file_count": value}
        for key, value in sorted(qc_summary.get("output_tree", {}).get("top_dirs", {}).items())
    ]
    blocked_rows = [
        {"target": key, "reason": value}
        for key, value in sorted((manifest.get("preflight_blocked_targets") or {}).items())
    ]
    title = f"SlicerDDSurfer Report - {manifest.get('subject_id') or 'subject'}"
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #20323f; background: #f7f9fb; }}
    main {{ max-width: 1100px; margin: auto; background: white; border: 1px solid #d7e0e7; border-radius: 12px; padding: 28px; }}
    h1, h2 {{ margin-top: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 18px 0; }}
    .card {{ border: 1px solid #dce6ec; border-radius: 10px; padding: 14px; background: #fbfdff; }}
    .label {{ color: #607784; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .value {{ font-weight: 700; word-break: break-word; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0 24px; font-size: 13px; }}
    th, td {{ border: 1px solid #dce6ec; padding: 7px 9px; text-align: left; vertical-align: top; }}
    th {{ background: #edf4f8; }}
    .muted {{ color: #607784; }}
    code {{ background: #edf4f8; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
<main>
  <h1>{html.escape(title)}</h1>
  <p class=\"muted\">Generated at {html.escape(str(provenance.get('generated_at') or ''))}</p>
  <div class=\"grid\">
    <div class=\"card\"><div class=\"label\">Run name</div><div class=\"value\">{html.escape(str(manifest.get('run_name') or ''))}</div></div>
    <div class=\"card\"><div class=\"label\">Tasks</div><div class=\"value\">{html.escape(json.dumps(provenance.get('task_summary', {}), sort_keys=True))}</div></div>
    <div class=\"card\"><div class=\"label\">Output files</div><div class=\"value\">{html.escape(str(provenance.get('output_tree', {}).get('file_count', 0)))}</div></div>
    <div class=\"card\"><div class=\"label\">QC files</div><div class=\"value\">{html.escape(str(provenance.get('qc_file_count', 0)))}</div></div>
  </div>
  <h2>Artifacts</h2>
  <p><code>{html.escape(paths.provenance_json.as_posix())}</code></p>
  <p><code>{html.escape(paths.qc_summary_json.as_posix())}</code></p>
  <h2>Blocked Targets</h2>
  {_html_table(blocked_rows, ['target', 'reason'])}
  <h2>Task Status</h2>
  {_html_table(tasks, ['name', 'status', 'reason'])}
  <h2>Output Tree</h2>
  {_html_table(output_rows, ['top_dir', 'file_count'])}
</main>
</body>
</html>
"""


def write_subject_reports(
    *,
    subject_root: Path,
    manifest_path: Path,
    output_root: Optional[Path] = None,
    run_name: Optional[str] = None,
) -> SubjectReportPaths:
    """Write HTML, provenance, and QC summary artifacts for one run."""

    manifest_path = manifest_path.expanduser().resolve()
    manifest = _read_json(manifest_path)
    subject_root = subject_root.expanduser().resolve()
    layout = subject_layout(subject_root, output_root=output_root)
    normalized_run = normalize_run_name(run_name or str(manifest.get("run_name") or "run"))
    report_dir = layout.slicer_scene_report
    paths = SubjectReportPaths(
        report_html=report_dir / f"{normalized_run}_report.html",
        provenance_json=report_dir / f"{normalized_run}_provenance.json",
        qc_summary_json=report_dir / f"{normalized_run}_qc_summary.json",
        report_html_latest=report_dir / "report.html",
        provenance_json_latest=report_dir / "provenance.json",
        qc_summary_json_latest=report_dir / "qc_summary.json",
    )
    output_tree = _collect_output_tree(layout.outputs)
    qc_records = _collect_qc_files(layout.outputs)
    provenance = _build_provenance(
        manifest_path=manifest_path,
        manifest=manifest,
        output_tree=output_tree,
        qc_records=qc_records,
    )
    qc_summary = _build_qc_summary(
        manifest_path=manifest_path,
        manifest=manifest,
        output_tree=output_tree,
        qc_records=qc_records,
    )
    report_html = _build_html_report(
        manifest=manifest,
        provenance=provenance,
        qc_summary=qc_summary,
        paths=paths,
    )
    _write_json(paths.provenance_json, provenance)
    _write_json(paths.qc_summary_json, qc_summary)
    _write_text(paths.report_html, report_html)
    _write_json(paths.provenance_json_latest, provenance)
    _write_json(paths.qc_summary_json_latest, qc_summary)
    _write_text(paths.report_html_latest, report_html)
    return paths
