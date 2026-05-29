"""Open SlicerDDSurfer in a real Slicer GUI session and keep Slicer running."""

from __future__ import annotations

import qt
import slicer


def _open_module() -> None:
    main_window = slicer.util.mainWindow()
    if main_window:
        main_window.resize(1600, 1000)
    slicer.util.selectModule("SlicerDDSurfer")
    slicer.app.processEvents()
    print("SLICERDDSURFER_GUI_READY=1")


qt.QTimer.singleShot(6000, _open_module)
