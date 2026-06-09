"""Verify that the Slicer output-tree button is wired to a generated HTML report."""

from __future__ import annotations

import os
from pathlib import Path

import qt
import slicer


MANIFEST_PATH = Path(
    os.environ.get(
        "SLICERDDSURFER_OUTPUT_TREE_MANIFEST",
        "/data/chengjin/SlicerDDSurfer-test/100307-release-candidate/outputs/00_run_metadata/rc_csd_act_orchestration_manifest.json",
    )
)


def _module_widget():
    try:
        return slicer.util.getModuleWidget("SlicerDDSurfer")
    except Exception:
        module = slicer.util.getModule("SlicerDDSurfer")
        return module.widgetRepresentation().self()


def _run() -> None:
    try:
        slicer.util.selectModule("SlicerDDSurfer")
        widget = _module_widget()
        if not MANIFEST_PATH.is_file():
            print(f"SLICERDDSURFER_OUTPUT_TREE_ERROR=missing manifest: {MANIFEST_PATH}", flush=True)
            slicer.app.exit(2)
            return

        opened_urls: list[str] = []
        original_open = qt.QDesktopServices.openUrl
        qt.QDesktopServices.openUrl = lambda url: opened_urls.append(url.toString()) or True
        try:
            widget._load_background_manifest_result(MANIFEST_PATH)
            button = getattr(widget, "_runOutputTreeButton", None)
            path = getattr(widget, "_latestOutputTreePath", None)
            print(f"SLICERDDSURFER_OUTPUT_TREE_BUTTON_ENABLED={bool(button and button.enabled)}", flush=True)
            print(f"SLICERDDSURFER_OUTPUT_TREE_PATH={path}", flush=True)
            if button and button.enabled:
                button.click()
            print(f"SLICERDDSURFER_OUTPUT_TREE_OPENED_URLS={opened_urls}", flush=True)
            ok = bool(
                button
                and button.enabled
                and path
                and Path(path).is_file()
                and opened_urls
                and any(str(path) in item for item in opened_urls)
            )
        finally:
            qt.QDesktopServices.openUrl = original_open
    except Exception as exc:
        print(f"SLICERDDSURFER_OUTPUT_TREE_ERROR={exc}", flush=True)
        slicer.app.exit(2)
        return
    slicer.app.exit(0 if ok else 2)


qt.QTimer.singleShot(6000, _run)
