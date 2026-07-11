"""Run the one-click beginner demo end to end in a real Slicer session."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from time import monotonic

import qt
import slicer


TIMEOUT_SECONDS = 90.0
state = {
    "started_at": monotonic(),
    "submitted": False,
    "errors": [],
    "original_info": None,
    "original_error": None,
}


def _restore_displays() -> None:
    if state["original_info"] is not None:
        slicer.util.infoDisplay = state["original_info"]
    if state["original_error"] is not None:
        slicer.util.errorDisplay = state["original_error"]


def _finish(exit_code: int, message: str) -> None:
    _restore_displays()
    print(message, flush=True)
    slicer.app.exit(exit_code)


def _loaded_paths() -> list[str]:
    paths: list[str] = []
    for index in range(slicer.mrmlScene.GetNumberOfNodes()):
        node = slicer.mrmlScene.GetNthNode(index)
        storage = node.GetStorageNode() if node and hasattr(node, "GetStorageNode") else None
        file_name = storage.GetFileName() if storage else None
        if file_name:
            paths.append(Path(str(file_name)).as_posix())
        source_path = node.GetAttribute("SlicerDDSurfer.SourcePath") if node else None
        if source_path:
            paths.append(Path(str(source_path)).as_posix())
    return paths


def _poll(widget, demo_root: Path) -> None:
    if monotonic() - state["started_at"] > TIMEOUT_SECONDS:
        _finish(2, "SLICERDDSURFER_DEMO_E2E_ERROR=timed out waiting for the background run")
        return
    if not state["submitted"] or getattr(widget, "_backgroundProcess", None) is not None:
        qt.QTimer.singleShot(250, lambda: _poll(widget, demo_root))
        return

    manifest_path = demo_root / "outputs" / "00_run_metadata" / "Demo_orchestration_manifest.json"
    if not manifest_path.is_file():
        _finish(2, f"SLICERDDSURFER_DEMO_E2E_ERROR=missing manifest: {manifest_path}")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    statuses = {str(item.get("name")): str(item.get("status")) for item in manifest.get("tasks", [])}
    loaded_paths = _loaded_paths()
    fa_loaded = any(path.endswith("_dti_FA.nii.gz") for path in loaded_paths)
    tractogram_loaded = any(path.endswith(".trk") for path in loaded_paths)
    task_status_ready = statuses == {
        "validation": "passed",
        "microstructure.dti": "completed",
        "tractography.dti_det": "completed",
    }
    print(f"SLICERDDSURFER_DEMO_E2E_MANIFEST={manifest_path}", flush=True)
    print(f"SLICERDDSURFER_DEMO_E2E_TASK_STATUSES={statuses}", flush=True)
    print(f"SLICERDDSURFER_DEMO_E2E_FA_LOADED={fa_loaded}", flush=True)
    print(f"SLICERDDSURFER_DEMO_E2E_TRACTOGRAM_LOADED={tractogram_loaded}", flush=True)
    print(f"SLICERDDSURFER_DEMO_E2E_SCENE_PATH_COUNT={len(loaded_paths)}", flush=True)
    if state["errors"]:
        print(f"SLICERDDSURFER_DEMO_E2E_UI_ERRORS={state['errors']}", flush=True)
    _finish(0 if task_status_ready and fa_loaded and tractogram_loaded and not state["errors"] else 2, "SLICERDDSURFER_DEMO_E2E_DONE=1")


def _start() -> None:
    try:
        slicer.util.selectModule("SlicerDDSurfer")
        module = slicer.util.getModule("SlicerDDSurfer")
        widget = module.widgetRepresentation().self()
        demo_root = Path(str(slicer.app.temporaryPath)) / "SlicerDDSurfer" / "demo" / "slicerdsurfer-demo"
        if demo_root.exists():
            shutil.rmtree(demo_root)
        state["original_info"] = slicer.util.infoDisplay
        state["original_error"] = slicer.util.errorDisplay
        slicer.util.infoDisplay = lambda *args, **kwargs: None
        slicer.util.errorDisplay = lambda message, *args, **kwargs: state["errors"].append(str(message))
        widget._on_try_demo_clicked()
        state["submitted"] = True
        qt.QTimer.singleShot(250, lambda: _poll(widget, demo_root))
    except Exception as exc:
        _finish(2, f"SLICERDDSURFER_DEMO_E2E_ERROR={exc}")


qt.QTimer.singleShot(6000, _start)
