"""Install a local package through Slicer's real Extension Manager model."""

from __future__ import annotations

import os
import runpy
import shutil
from pathlib import Path

import qt
import slicer


TEMP_ROOT = Path(os.environ.get("SLICERDDSURFER_SMOKE_ROOT", "/tmp/slicerdsurfer-extension-manager-install-smoke")) / "extension-manager"


def _run() -> None:
    try:
        archive_path = Path(os.environ["SLICERDDSURFER_EXTENSION_ARCHIVE"]).expanduser().resolve()
        shutil.rmtree(TEMP_ROOT, ignore_errors=True)
        TEMP_ROOT.mkdir(parents=True)
        # Load only this stdlib inspector, not scientific modules from the checkout.
        inspector_path = os.environ.get("SLICERDDSURFER_ARCHIVE_INSPECTOR") or str(
            Path(__file__).resolve().parents[2] / "scripts/extension_runtime/archive_layout.py")
        inspector = runpy.run_path(inspector_path)
        layout = inspector["inspect_archive_layout"](archive_path)
        archive_rooted = len(layout["module_roots"]) == 1 and not layout["unsafe"]
        archive_clean = not layout["development_artifacts"]

        settings_path = TEMP_ROOT / "settings.ini"
        install_root = TEMP_ROOT / "extensions"
        settings = qt.QSettings(settings_path.as_posix(), qt.QSettings.IniFormat)
        settings.setValue("Extensions/InstallPath", install_root.as_posix())
        settings.setValue("Extensions/ManagerEnabled", True)
        settings.sync()

        manager = slicer.app.extensionsManagerModel()
        manager.extensionsSettingsFilePath = settings_path.as_posix()
        manager.setInteractive(False)
        # Switching settings does not invalidate the manager's installed-item cache.
        manager.updateModel()
        assert not manager.isExtensionInstalled("SlicerDDSurfer"), "Private install root is not empty"
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
        runtime_resources_ready = False
        installed_imports_ready = False
        if installed_module:
            top_level_python = sorted(path.name for path in installed_module.parent.glob("*.py"))
            root = installed_module.parent.resolve()
            runtime_resources_ready = all((root / name).is_file() for name in (
                "tractography/wmql_queries/AF_CST.qry",
                "scripts/wsl/WslCommandBridge.cs", "scripts/wsl/requirements-runtime.txt",
                "LICENSE.txt", "THIRD_PARTY_NOTICES.md",
                "anatomy/parcellation/conversion/LICENSE.txt",
                "anatomy/surface/ddsurfer_backend/LICENSE.txt",
                "licenses/FreeSurfer.txt", "licenses/PyTorch3D.txt", "licenses/provenance.json",
                "anatomy/parcellation/conversion/data/FreeSurferColorLUT.txt"))
            import tractography.wmql as wmql
            import anatomy.segmentation.pipeline as ddseg
            import scripts.audit_third_party as license_audit
            installed_imports_ready = (
                Path(wmql.__file__).resolve().is_relative_to(root)
                and Path(ddseg.__file__).resolve().is_relative_to(root)
                and wmql.bundled_wmql_query_path().resolve().is_relative_to(root)
                and wmql.bundled_wmql_query_path().is_file()
                and Path(license_audit.__file__).resolve().is_relative_to(root)
                and license_audit.audit(root)["status"] == "pass"
            )

        print(f"SLICERDDSURFER_EXTMGR_ARCHIVE_ROOTED={archive_rooted}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_ARCHIVE_CLEAN={archive_clean}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_INSTALL_RETURNED={installed}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_REPORTS_INSTALLED={manager_reports_installed}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_MODULE_PATHS={module_paths}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_MODULE_REGISTERED={registered}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_MODULE_LOADED={loaded}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_MODULE_AVAILABLE={module_available}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_TOP_LEVEL_PY={top_level_python}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_RUNTIME_RESOURCES_READY={runtime_resources_ready}", flush=True)
        print(f"SLICERDDSURFER_EXTMGR_INSTALLED_IMPORTS_READY={installed_imports_ready}", flush=True)
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
            and runtime_resources_ready
            and installed_imports_ready
        )
        slicer.app.exit(0 if ready else 2)
    except Exception as exc:
        print(f"SLICERDDSURFER_EXTMGR_ERROR={exc}", flush=True)
        slicer.app.exit(2)


qt.QTimer.singleShot(3000, _run)
