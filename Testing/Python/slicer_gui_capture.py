"""Capture the SlicerDDSurfer module UI from a real Slicer GUI session."""

from __future__ import annotations

import os
from pathlib import Path

import qt
import slicer


OUTPUT_PATH = Path(os.environ.get("SLICERDDSURFER_GUI_CAPTURE", "/tmp/SlicerDDSurfer_gui.png"))


def _capture() -> None:
    try:
        main_window = slicer.util.mainWindow()
        main_window.resize(1600, 1000)
        slicer.util.selectModule("SlicerDDSurfer")
        slicer.app.processEvents()
        pixmap = main_window.grab()
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not pixmap.save(OUTPUT_PATH.as_posix()):
            raise RuntimeError(f"Failed to save GUI capture: {OUTPUT_PATH}")
        print(f"SLICERDDSURFER_GUI_CAPTURE={OUTPUT_PATH}")
    finally:
        slicer.app.exit(0)


qt.QTimer.singleShot(6000, _capture)
