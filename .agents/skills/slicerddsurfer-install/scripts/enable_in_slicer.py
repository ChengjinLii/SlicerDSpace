"""Verify a staged module inside Slicer, then optionally persist its path."""

import importlib
import json
import os
from pathlib import Path


def activate(module_directory, *, persist=False):
    import qt
    import slicer

    directory = Path(module_directory).expanduser().resolve()
    entry = directory / 'SlicerDDSurfer.py'
    if not entry.is_file():
        raise ValueError('The staged module directory does not contain SlicerDDSurfer.py')
    settings = slicer.app.userSettings()
    existing = settings.value('Modules/AdditionalPaths', []) or []
    existing = [existing] if isinstance(existing, str) else list(existing)
    for path in existing:
        other = Path(str(path)).expanduser()
        if (other / 'SlicerDDSurfer.py').is_file() and other.resolve() != directory:
            raise RuntimeError('A different SlicerDDSurfer installation is configured: ' + str(other))
    factory = slicer.app.moduleManager().factoryManager()
    if not factory.isRegistered('SlicerDDSurfer'):
        factory.registerModule(qt.QFileInfo(str(entry)))
    factory.loadModules(['SlicerDDSurfer'])
    module = importlib.import_module('SlicerDDSurfer')
    if Path(module.__file__).resolve() != entry:
        raise RuntimeError('Slicer loaded a different module; restart after reviewing the configured paths.')
    slicer.util.selectModule('SlicerDDSurfer')
    widget = slicer.modules.slicerddsurfer.widgetRepresentation().self()
    if getattr(widget, '_parameterNode', None) is None:
        raise RuntimeError('The SlicerDDSurfer widget did not initialize')
    check = slicer.selfTests.get('SlicerDDSurfer')
    if check is None:
        raise RuntimeError('The installed module did not register its native Self Tests')
    before = slicer.mrmlScene.GetNumberOfNodes()
    check(msec=0)
    if slicer.mrmlScene.GetNumberOfNodes() != before:
        raise RuntimeError('Native Self Tests changed the current scene node count')
    if persist:
        normalized = {Path(str(path)).expanduser().resolve() for path in existing}
        if directory not in normalized:
            settings.setValue('Modules/AdditionalPaths', [*existing, str(directory)])
            settings.sync()
        persisted = settings.value('Modules/AdditionalPaths', []) or []
        persisted = [persisted] if isinstance(persisted, str) else list(persisted)
        if directory not in {Path(str(path)).expanduser().resolve() for path in persisted}:
            raise RuntimeError('The module loaded, but persistent path registration failed')
    return dict(status='passed', module_file=str(entry), native_self_tests='passed',
                persistent=bool(persist), slicer_version=str(slicer.app.applicationVersion),
                dependency_readiness='not_checked', scientific_qc='not_checked')


def main():
    receipt = os.environ.get('SLICERDDSURFER_AGENT_RECEIPT')
    result = {}
    code = 0
    try:
        directory = os.environ.get('SLICERDDSURFER_AGENT_MODULE_DIR')
        if not directory or not receipt:
            raise ValueError('Set SLICERDDSURFER_AGENT_MODULE_DIR and SLICERDDSURFER_AGENT_RECEIPT')
        result = activate(directory, persist=os.environ.get('SLICERDDSURFER_AGENT_PERSIST') == '1')
    except Exception as exc:
        result = dict(status='failed', error=str(exc))
        code = 1
    if receipt:
        destination = Path(receipt).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)
    if os.environ.get('SLICERDDSURFER_AGENT_EXIT') == '1':
        import slicer
        slicer.app.exit(code)
    return code


if __name__ == '__main__':
    main()
