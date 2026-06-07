"""Validate an extension-like SlicerDDSurfer staged install in real Slicer."""

from __future__ import annotations

import os
from pathlib import Path

import qt
import slicer


MODULE_DIR = Path(os.environ.get("SLICERDDSURFER_EXTENSION_MODULE_DIR", ""))
FORBIDDEN_MODULES = (
    "workflow_catalog",
    "run_subject_pipeline",
    "release_audit",
    "generate_subject_report",
    "install_dependencies",
)


def _module_registered(name: str) -> bool:
    return hasattr(slicer.modules, name.lower())


def _run() -> None:
    try:
        top_level_py = sorted(path.name for path in MODULE_DIR.glob("*.py")) if MODULE_DIR.is_dir() else []
        forbidden_registered = [name for name in FORBIDDEN_MODULES if _module_registered(name)]
        slicer.util.selectModule("SlicerDDSurfer")
        module = slicer.util.getModule("SlicerDDSurfer")
        target_registered = _module_registered("SlicerDDSurfer") or module is not None
        widget = module.widgetRepresentation().self()
        logic_ready = bool(getattr(widget, "logic", None))
        parameter_node_ready = bool(getattr(widget, "_parameterNode", None))
        run_panel_ready = bool(getattr(widget, "_runStatusPanel", None))
        env_paths_ready = bool(getattr(widget, "_environmentPathLineEdits", None))
        module_file = MODULE_DIR / "SlicerDDSurfer.py"
        module_file_is_symlink = module_file.is_symlink()
        print(f"SLICERDDSURFER_EXTENSION_MODULE_DIR={MODULE_DIR}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_TOP_LEVEL_PY={top_level_py}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_TARGET_REGISTERED={target_registered}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_FORBIDDEN_REGISTERED={forbidden_registered}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_MODULE_FILE_SYMLINK={module_file_is_symlink}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_LOGIC_READY={logic_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_PARAMETER_NODE_READY={parameter_node_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_RUN_PANEL_READY={run_panel_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTENSION_ENV_PATHS_READY={env_paths_ready}", flush=True)
        bad = (
            top_level_py != ["SlicerDDSurfer.py"]
            or not target_registered
            or forbidden_registered
            or module_file_is_symlink
            or not logic_ready
            or not parameter_node_ready
            or not run_panel_ready
            or not env_paths_ready
        )
        slicer.app.exit(2 if bad else 0)
    except Exception as exc:
        print(f"SLICERDDSURFER_EXTENSION_INSTALL_ERROR={exc}", flush=True)
        slicer.app.exit(2)


qt.QTimer.singleShot(6000, _run)
