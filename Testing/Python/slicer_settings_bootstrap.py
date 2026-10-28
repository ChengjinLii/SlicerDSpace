"""Verify both Slicer settings stores are private before invoking a GUI test."""

import json
import os
from pathlib import Path
import runpy
import traceback

import slicer


def main():
    root = Path(os.environ["SLICERDSPACE_SMOKE_ROOT"]).resolve()
    private_home = Path(os.environ["SLICERDSPACE_PRIVATE_SLICER_HOME"]).resolve()
    stores = {}
    for name, settings, parent in (
        ("user", slicer.app.userSettings(), root / "settings"),
        ("revision", slicer.app.revisionUserSettings(), private_home / "slicer.org"),
    ):
        path = Path(settings.fileName()).resolve()
        settings.sync()
        stores[name] = {"path": str(path), "status": int(settings.status()),
                        "private": path.is_relative_to(parent)}
    record = {"stores": stores, "slicer_home": slicer.app.slicerHome,
              "passed": all(item["private"] and item["status"] == 0
                            for item in stores.values())}
    (root / "settings_isolation.json").write_text(json.dumps(record, indent=2) + "\n")
    if not record["passed"]:
        raise RuntimeError(f"Slicer settings are not isolated/writable: {record}")
    runpy.run_path(os.environ["SLICERDSPACE_TEST_SCRIPT"], run_name="__main__")


try:
    main()
except Exception:
    traceback.print_exc()
    slicer.app.exit(1)
