"""Install a local package through Slicer's real Extension Manager model."""

from __future__ import annotations

import os
import shutil
import tarfile
from pathlib import Path

import qt
import slicer


TEMP_ROOT = Path("/tmp/slicerdsurfer-extension-manager-install-smoke")


def _run() -> None:
    try:
        archive_path = Path(os.environ["SLICERDDSURFER_EXTENSION_ARCHIVE"]).expanduser().resolve()
        shutil.rmtree(TEMP_ROOT, ignore_errors=True)
        TEMP_ROOT.mkdir(parents=True)
        with tarfile.open(archive_path, "r:gz") as archive:
            archive_names = archive.getnames()
        archive_rooted = bool(archive_names) and all(
            name == "SlicerDDSurfer" or name.startswith("SlicerDDSurfer/") for name in archive_names
        )
        archive_clean = not any(
            "__pycache__" in name or name.endswith((".pyc", ".pyo")) for name in archive_names
        )

        settings_path = TEMP_ROOT / "settings.ini"
        install_root = TEMP_ROOT / "extensions"
        settings = qt.QSettings(settings_path.as_posix(), qt.QSettings.IniFormat)
        settings.setValue("Extensions/InstallPath", install_root.as_posix())
        settings.setValue("Extensions/ManagerEnabled", True)
        settings.sync()

        manager = slicer.app.extensionsManagerModel()
        manager.extensionsSettingsFilePath = settings_path.as_posix()
        manager.setInteractive(False)
        metadata = {
            "extensionname": "SlicerDDSurfer",
            "depends": "SlicerDMRI PyTorch",
            "slicer_revision": str(manager.slicerRevision),
            "os": str(manager.slicerOs),
            "arch": str(manager.slicerArch),
        }
        installed = bool(
            manager.installExtension(
                "SlicerDDSurfer",
                metadata,
                archive_path.as_posix(),
                False,
                True,
            )
        )
        manager_reports_installed = bool(manager.isExtensionInstalled("SlicerDDSurfer"))
        module_paths = tuple(str(path) for path in manager.extensionModulePaths("SlicerDDSurfer"))
        module_files = [Path(path) / "SlicerDDSurfer.py" for path in module_paths]
        installed_module = next((path for path in module_files if path.is_file()), None)

        factory = slicer.app.moduleManager().factoryManager()
        if installed_module:
            factory.registerModule(qt.QFileInfo(installed_module.as_posix()))
        registered = bool(factory.isRegistered("SlicerDDSurfer"))
        loaded = bool(registered and factory.loadModules(["SlicerDDSurfer"]))
        module_available = hasattr(slicer.modules, "slicerddsurfer")
        top_level_python = []
        if installed_module:
            top_level_python = sorted(path.name for path in installed_module.parent.glob("*.py"))

        print(f"SLICERDDSURFER_EXTMGR_ARCHIVE_ROOTED={archive_rooted}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_ARCHIVE_CLEAN={archive_clean}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_INSTALL_RETURNED={installed}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_REPORTS_INSTALLED={manager_reports_installed}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_MODULE_PATHS={module_paths}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_MODULE_REGISTERED={registered}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_MODULE_LOADED={loaded}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_MODULE_AVAILABLE={module_available}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_TOP_LEVEL_PY={top_level_python}", flush=True)
        ready = (
            archive_rooted
            and archive_clean
            and installed
            and manager_reports_installed
            and installed_module is not None
            and registered
            and loaded
            and module_available
            and top_level_python == ["SlicerDDSurfer.py"]
        )
        slicer.app.exit(0 if ready else 2)
    except Exception as exc:
        print(f"SLICERDDSURFER_EXTMGR_ERROR={exc}", flush=True)
        slicer.app.exit(2)


qt.QTimer.singleShot(3000, _run)
