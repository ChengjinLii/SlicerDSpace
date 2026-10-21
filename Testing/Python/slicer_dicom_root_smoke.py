"""Real converter and unchanged main input controls, using a deidentified fixture."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import traceback

import nibabel as nib
import numpy as np
import qt
import slicer


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    root = Path(os.environ["SLICERDDSURFER_SMOKE_ROOT"])
    try:
        fixture = Path(os.environ["SLICERDDSURFER_DICOM_FIXTURE"]) / "dicom_source/ap"
        source = root / "subject"
        shutil.copytree(fixture, source)
        before = {str(path.relative_to(source)): digest(path) for path in source.rglob("*") if path.is_file()}
        slicer.util.selectModule("SlicerDDSurfer")
        owner = slicer.modules.slicerddsurfer.widgetRepresentation().self()
        owner._parameterNode.subjectId = "subject"
        owner.ui.inputDirectoryPath.currentPath = str(source)
        assert owner.validateInputs(manual=True)
        assert not (source / "input").exists(), "Selecting a folder must not convert data on the Qt thread"
        module = Path(__import__("shared.dicom_input", fromlist=["__file__"]).__file__).parents[1]
        code = (f"import sys; sys.path.insert(0,{str(module)!r}); from shared.dicom_input import prepare_dicom_root; "
                f"from pathlib import Path; prepare_dicom_root(Path({str(source)!r}),'subject',log=print)")
        log = (root / "conversion.log").open("w")
        process = subprocess.Popen([owner._slicer_launcher_program(), "--launch", "PythonSlicer", "-c", code],
                                   stdout=log, stderr=subprocess.STDOUT)
        started = time.monotonic()
        beats = 0
        while process.poll() is None:
            if time.monotonic() - started > 120:
                process.kill()
                process.wait()
                raise TimeoutError("Conversion exceeded timeout")
            loop = qt.QEventLoop()
            qt.QTimer.singleShot(50, loop.quit)
            loop.exec_()
            beats += 1
        log.close()
        assert process.returncode == 0, (root / "conversion.log").read_text()
        assert beats > 0
        image = nib.load(source / "input/data.nii.gz")
        bvals = np.loadtxt(source / "input/bvals")
        assert image.shape[-1] == bvals.size and np.isfinite(np.asarray(image.dataobj)).all()
        assert before == {name: digest(source / name) for name in before}
        assert owner._parameterNode.inputDirectory == str(source)
        assert owner.validateInputs(manual=True)
        from shared.dicom_input import prepare_dicom_root
        record = prepare_dicom_root(source, "subject")
        assert record["status"] == "completed"
        (root / "dicom_root.json").write_text(json.dumps({"status": "passed", "source_unchanged": True,
            "shape": list(image.shape), "measurements": int(bvals.size), "qt_heartbeats": beats,
            "scope": "Real DWIConvert conversion, canonical validation/reuse and unchanged input GUI; not all scanner protocols"}, indent=2))
        result = 0
    except Exception:
        (root / "dicom_root.json").write_text(json.dumps({"status": "failed", "error": traceback.format_exc()}, indent=2))
        traceback.print_exc()
        result = 2
    slicer.app.exit(result)


qt.QTimer.singleShot(5000, run)
