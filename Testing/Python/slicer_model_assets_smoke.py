"""Verify actual core model checksums and export a lockfile in real Slicer."""

import json
import os
from pathlib import Path
import time
import traceback

import qt
import slicer

ROOT = Path(os.environ["SLICERDDSURFER_SMOKE_ROOT"])
STATE = {"errors": [], "beats": 0}


def sentinel_downloaded(ok, message):
    try:
        assert ok and not STATE["errors"], {"message": message, "errors": STATE["errors"]}
        widget = STATE["widget"]
        module = widget._load_model_assets_module()
        manifest = module.load_manifest(Path(widget.logic.module_dir) / "models/assets_manifest.json")
        plan = module.resolve_asset_plan(manifest, "sentinel")
        verification = module.verify_asset_plan(ROOT / "sentinel", plan)
        assert verification["ok"] and verification["hashes_checked"] > 0, verification
        STATE["record"].update(public_sentinel_download=verification, gui_heartbeats=STATE["beats"])
        (ROOT / "model_assets.json").write_text(json.dumps(STATE["record"], indent=2) + "\n")
        print("REAL_CORE_ASSETS_AND_SENTINEL_PASS", flush=True)
        slicer.app.exit(0)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(2)


def core_downloaded(ok, message):
    try:
        assert ok, message
        STATE["record"]["existing_core_download_reuse"] = "PASS"
        widget = STATE["widget"]
        # Only the directory chooser is automated; the downloader is real.
        widget._choose_model_assets_root = lambda: ROOT / "sentinel"
        assert widget._install_model_assets_from_environment_dialog(
            profile="sentinel", prompt_for_root=True, on_complete=sentinel_downloaded)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(2)


def poll():
    try:
        widget = STATE["widget"]
        if time.monotonic() - STATE["started"] > 120:
            widget.cleanup()
            raise AssertionError("Asset verification timed out")
        if widget._setupJob is not None:
            qt.QTimer.singleShot(100, poll)
            return
        assert not STATE["errors"], STATE["errors"]
        lock = json.loads((ROOT / "core_asset_lock.json").read_text())
        assert lock["profile"] == "core"
        assert len(lock["records"]) > 0
        assert all(r["sha256"] == r["expected_sha256"] and r["size_bytes"] == r["expected_size_bytes"]
                   and not r["lfs_pointer"] for r in lock["records"])
        assert STATE["beats"] > 0
        STATE["record"] = {"status": "PASS", "asset_root": lock["asset_root"],
               "lockfile": str(ROOT / "core_asset_lock.json"), "checked_count": len(lock["records"]),
               "gui_heartbeats": STATE["beats"]}
        assert widget._install_model_assets_from_environment_dialog(
            profile="core", prompt_for_root=False, on_complete=core_downloaded)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(2)


def start():
    try:
        slicer.util.selectModule("SlicerDDSurfer")
        widget = slicer.modules.slicerddsurfer.widgetRepresentation().self()
        STATE["widget"] = widget
        widget._show_actionable_error = lambda **kwargs: STATE["errors"].append(str(kwargs))
        timer = qt.QTimer()
        timer.connect("timeout()", lambda: STATE.update(beats=STATE["beats"] + 1))
        timer.start(50)
        STATE["timer"] = timer
        STATE["started"] = time.monotonic()
        assert widget._start_model_asset_verification(lockfile=ROOT / "core_asset_lock.json")
        qt.QTimer.singleShot(100, poll)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(2)


qt.QTimer.singleShot(5000, start)
