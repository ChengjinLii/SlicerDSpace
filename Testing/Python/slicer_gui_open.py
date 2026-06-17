"""Open SlicerDDSurfer in a real Slicer GUI session and keep Slicer running."""

from __future__ import annotations

from pathlib import Path

import qt
import slicer


MAX_ATTEMPTS = 20
RETRY_MS = 1500
READY_MARKER = Path("/tmp/slicerdsurfer_gui_ready.txt")
_attempt = 0


def _open_module() -> None:
    global _attempt
    _attempt += 1
    main_window = slicer.util.mainWindow()
    if main_window:
        main_window.resize(1600, 1000)
        main_window.raise_()
        main_window.activateWindow()

    module_manager = slicer.app.moduleManager()
    factory_manager = module_manager.factoryManager() if module_manager else None
    module_names = set(factory_manager.instantiatedModuleNames()) if factory_manager else set()
    if "SlicerDDSurfer" in module_names:
        slicer.util.selectModule("SlicerDDSurfer")
        slicer.app.processEvents()
        READY_MARKER.write_text("SLICERDDSURFER_GUI_READY=1\n", encoding="utf-8")
        print("SLICERDDSURFER_GUI_READY=1", flush=True)
        return

    print(
        f"SLICERDDSURFER_GUI_WAIT attempt={_attempt} module_loaded={'SlicerDDSurfer' in module_names}",
        flush=True,
    )
    if _attempt < MAX_ATTEMPTS:
        qt.QTimer.singleShot(RETRY_MS, _open_module)
    else:
        READY_MARKER.write_text("SLICERDDSURFER_GUI_TIMEOUT=1\n", encoding="utf-8")
        print("SLICERDDSURFER_GUI_TIMEOUT=1", flush=True)


READY_MARKER.unlink(missing_ok=True)
qt.QTimer.singleShot(6000, _open_module)
