"""Load actual scientific case outputs through the latest packaged Slicer UI."""

import json
import os
from pathlib import Path
import time
import traceback

import numpy as np
import qt
import slicer
from vtk.util.numpy_support import vtk_to_numpy

ROOT = Path(os.environ["SLICERDSPACE_SMOKE_ROOT"])
REPORT = Path(os.environ["SLICERDSPACE_RESULTS_REPORT"])
config_path = os.environ.get("SLICERDSPACE_TASKS_CONFIG")
CONFIG = json.loads(Path(config_path).read_text()) if config_path else {}
EXPECTED_CASES = int(os.environ.get("SLICERDSPACE_RESULTS_EXPECTED_CASES", len(CONFIG.get("cases", []))))
if EXPECTED_CASES < 1:
    raise ValueError("Specify the expected case count or a scientific task configuration")
STATE = {"done": set(), "records": [], "started": time.monotonic()}


def poll():
    try:
        try:
            cases = json.loads(REPORT.read_text())["cases"]
        except (OSError, ValueError):
            cases = []
        for case in cases:
            if case.get("status") != "PASS" or case["name"] in STATE["done"] or "manifest_snapshot" not in case:
                continue
            from shared.result_scene import result_candidates, owned_nodes
            slicer.mrmlScene.Clear(0)
            payload = json.loads(Path(case["manifest_snapshot"]).read_text())
            candidates, _ = result_candidates(payload)
            expected = {c["path"] for c in candidates}
            logic = STATE["widget"].logic
            loaded = logic.loadKeyResultsFromManifest(Path(case["manifest_snapshot"]), max_items=200)
            actual = {c["path"] for c in loaded["loaded"] + loaded["reused"]}
            assert expected == actual, {"not_loaded": sorted(expected - actual), "skipped": loaded["skipped"]}
            for task in payload["tasks"]:
                if task["name"] in {"bundles.wmql", "bundles.wma", "bundles.tractcloud"} and task["status"] == "completed":
                    assert any(c["product"] == task["name"] and c["key"].startswith("bundle_") for c in candidates), "No bundle files loaded"
            nodes = owned_nodes(slicer, str(Path(case["manifest_snapshot"]).resolve()))
            assert len(nodes) == len(candidates)
            geometry = {}
            for node in nodes:
                if not node.IsA("vtkMRMLModelNode"):
                    continue
                polydata = node.GetPolyData()
                assert polydata is not None and polydata.GetNumberOfPoints() > 0, node.GetName()
                points = vtk_to_numpy(polydata.GetPoints().GetData())
                assert np.isfinite(points).all(), f"Non-finite geometry: {node.GetName()}"
                if node.IsA("vtkMRMLFiberBundleNode"):
                    assert polydata.GetNumberOfLines() > 0, f"Empty fiber bundle: {node.GetName()}"
                geometry[node.GetName()] = {
                    "points": polydata.GetNumberOfPoints(),
                    "lines": polydata.GetNumberOfLines(),
                    "bounds_ras": list(polydata.GetBounds()),
                    "finite_coordinates": True,
                }
            if slicer.mrmlScene.IsNodeClassRegistered("vtkMRMLFiberBundleNode"):
                fiber_paths = {c["path"] for c in candidates if Path(c["path"]).suffix in {".tck", ".trk", ".vtk", ".vtp"}}
                assert all(node.IsA("vtkMRMLFiberBundleNode") for node in nodes
                           if node.GetAttribute("SlicerDDSurfer.SourcePath") in fiber_paths)
            record = {"name": case["name"], "status": "PASS", "source_manifest": case["manifest_snapshot"],
                      "products": sorted({c["product"] for c in candidates}), "node_count": len(nodes),
                      "node_classes": {node.GetName(): node.GetClassName() for node in nodes},
                      "geometry": geometry, "loading": loaded}
            STATE["records"].append(record)
            STATE["done"].add(case["name"])
            (ROOT / "results.json").write_text(json.dumps(STATE["records"], indent=2) + "\n")
            slicer.util.mainWindow().grab().save(str(ROOT / (case["name"] + ".png")))
            print("REAL_RESULT_LOADING=" + json.dumps({k: record[k] for k in ("name", "status", "node_count", "products")}), flush=True)
        if len(STATE["done"]) >= EXPECTED_CASES:
            slicer.app.exit(0)
        elif time.monotonic() - STATE["started"] > CONFIG.get("case_timeout_seconds", 10800) * 2:
            raise AssertionError("Waiting for scientific outputs timed out")
        else:
            qt.QTimer.singleShot(1000, poll)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(2)


def start():
    slicer.util.selectModule("SlicerDSpace")
    STATE["widget"] = slicer.modules.slicerdspace.widgetRepresentation().self()
    poll()


qt.QTimer.singleShot(5000, start)
