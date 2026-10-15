#!/usr/bin/env python3
"""Audit independent saved task records, not a fabricated joint pipeline run."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def audit(task_root, report):
    from scripts import audit_scientific_outputs as science

    records = []
    for source in sorted(Path(task_root).rglob("manifest.json")):
        data = json.loads(source.read_text())
        if data.get("kind") != "slicerddsurfer_task_manifest":
            continue
        task = {"name": data["task_name"], "status": data["status"], "reason": data.get("reason"),
                "manifest_path": data.get("native_manifest_path"), "qc_path": data.get("native_qc_path") or data.get("qc_path"),
                "outputs": data.get("outputs") or {}}
        context = {"subject_id": data["subject_id"], "subject_root": data["subject_root"],
                   "output_root": data["output_root"], "run_name": data["run_name"], "tasks": [task]}
        context["analysis_inputs"] = data.get("inputs") or {}
        checks = []
        start = time.perf_counter()
        for function in (science._audit_validation, science._audit_preprocessing, science._audit_dti,
                         science._audit_tractography, science._audit_structural, science._audit_optional_microstructure,
                         science._audit_dki, science._audit_qc_routes, science._audit_connectomes):
            try:
                function(context, checks)
            except Exception as exc:
                checks.append({"name": function.__name__ + ".exception", "passed": False, "value": str(exc),
                               "requirement": "selected outputs decode and match their recorded geometry"})
        if task["name"] == "segmentation.ddseg_world_qc":
            try:
                from anatomy.segmentation.world_qc import evaluate_ddseg_world_qc

                previous = json.loads(Path(task["qc_path"]).read_text())
                paths = previous["inputs"]
                result = evaluate_ddseg_world_qc(Path(paths["segmentation"]["path"]), Path(paths["parcellation"]["path"]))
                checks.append({"name": "ddseg.world_alignment_recomputed", "passed": result["status"] == "passed",
                               "value": result, "requirement": "world-space WM Dice >= existing hard threshold 0.70"})
            except Exception as exc:
                checks.append({"name": "ddseg.world_alignment_recomputed", "passed": False, "value": str(exc),
                               "requirement": "current anatomy decodes and world-space overlap can be recomputed"})
        if task["name"] == "surface.ddsurfer_postprocess":
            from shared.orchestrator import _surface_postprocess_complete

            checks.append({"name": "surface.postprocess_current_output_contract", "passed": _surface_postprocess_complete(
                Path(data["subject_root"]), data["subject_id"], Path(data["output_root"])),
                "value": task["qc_path"], "requirement": "current postprocessing backend and complete decoded MRI/surface files"})
        failed = [item for item in checks if not item["passed"]]
        status = "failed" if failed or data["status"] not in {"completed", "skipped", "passed"} else "passed" if checks else "not_covered"
        row = {"subject_id": data["subject_id"], "run_name": data["run_name"], "task": data["task_name"],
               "recorded_execution_status": data["status"], "current_audit_status": status,
               "recorded_runtime_seconds": data.get("runtime_seconds"), "reused": data.get("reused"),
               "audit_seconds": time.perf_counter() - start, "check_count": len(checks), "failed_checks": failed,
               "source": str(source.resolve()), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "checks": checks}
        records.append(row)
        print(f"{row['subject_id']} {row['task']}: {status} ({len(failed)}/{len(checks)} failed)", flush=True)
    payload = {"kind": "independent_saved_task_audit", "created_at": datetime.now(timezone.utc).isoformat(),
               "records": records, "limitations": ["These are separate saved task scopes, not one jointly validated fresh execution.",
               "Uncovered tasks and failed scientific contracts cannot be interpreted as passed.",
               "Reuse/runtime records are not fresh computation timings; manual anatomy/model review remains required."]}
    report = Path(report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2) + "\n")
    columns = ("subject_id", "run_name", "task", "recorded_execution_status", "current_audit_status", "recorded_runtime_seconds", "reused", "audit_seconds", "check_count", "source", "source_sha256")
    with report.with_suffix(".csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    audit(args.task_root, args.report)
