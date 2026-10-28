"""Test GUI input preparation using real DICOM and NIfTI/NRRD round trips."""

import json
import os
from pathlib import Path
import subprocess
import traceback

import nibabel as nib
import numpy as np
import qt
import slicer

ROOT = Path(os.environ["SLICERDSPACE_SMOKE_ROOT"])
FIXTURE = Path(os.environ["SLICERDSPACE_DICOM_FIXTURE"])


def run():
    try:
        slicer.util.selectModule("SlicerDSpace")
        widget = slicer.modules.slicerdspace.widgetRepresentation().self()
        slicer.app.temporaryPath = str(ROOT / "temp")
        slicer.util.infoDisplay = lambda message, *args, **kwargs: print(str(message), flush=True)
        errors = []
        widget._show_actionable_error = lambda **kwargs: errors.append(kwargs)
        source = FIXTURE / "subject/input"
        binary = Path(slicer.app.slicerHome) / "lib/Slicer-5.10/cli-modules/DWIConvert"
        nrrd = ROOT / "real_dwi.nrrd"
        command = [widget._slicer_launcher_program(), "--launch", str(binary), "--conversionMode", "FSLToNrrd",
                   "--inputVolume", str(source / "data.nii.gz"), "--inputBValues", str(source / "bvals"),
                   "--inputBVectors", str(source / "bvecs"), "--outputVolume", str(nrrd)]
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
        report = {"source": str(FIXTURE), "nrrd_export_command": command, "cases": []}
        for kind, path in (("nifti", source / "data.nii.gz"), ("dicom", FIXTURE / "dicom_source/ap"), ("nrrd", nrrd)):
            dest = ROOT / kind
            fields = {"source": str(path), "subject_root": str(dest), "subject_id": "input-test-" + kind,
                      "bval": str(source / "bvals") if kind == "nifti" else "",
                      "bvec": str(source / "bvecs") if kind == "nifti" else "", "metadata": "", "mask": ""}
            for key, value in fields.items():
                widget._set_prepare_inputs_widget_text(key, value)
            for key, value in (("source_kind", kind), ("backend", "auto"), ("output_kind", "canonical-nifti")):
                combo = widget._prepareInputWidgets[key]
                combo.setCurrentIndex(combo.findText(value))
            widget._prepareInputWidgets["preview_button"].click()
            assert not (dest / "input/data.nii.gz").exists(), "Preview mutated inputs"
            widget._prepareInputWidgets["prepare_button"].click()
            assert not errors, errors
            manifest = dest / "input/input_import_manifest.json"
            record = json.loads(manifest.read_text())
            assert record["status"] == "completed"
            assert widget._parameterNode.inputDirectory == str(dest)
            assert widget._parameterNode.subjectId == fields["subject_id"]
            image = nib.load(str(dest / "input/data.nii.gz"))
            values = np.loadtxt(dest / "input/bvals")
            vectors = np.loadtxt(dest / "input/bvecs")
            assert image.shape[-1] == values.size
            assert vectors.shape == (3, values.size)
            assert np.isfinite(np.asarray(image.dataobj)).all()
            reference = nib.load(str(source / "data.nii.gz"))
            if kind in {"nifti", "nrrd"}:
                np.testing.assert_allclose(image.affine, reference.affine, atol=1e-4)
                np.testing.assert_allclose(np.asarray(image.dataobj), np.asarray(reference.dataobj), rtol=0, atol=0)
                np.testing.assert_allclose(values, np.loadtxt(source / "bvals"), atol=1e-3)
                expected = np.loadtxt(source / "bvecs")
                np.testing.assert_allclose(vectors, expected, rtol=0, atol=1e-5)
            report["cases"].append({"kind": kind, "status": "PASS", "manifest": str(manifest),
                                     "shape": list(image.shape), "affine": image.affine.tolist(),
                                     "bvalue_range": [float(values.min()), float(values.max())]})
            (ROOT / "input_preparation.json").write_text(json.dumps(report, indent=2) + "\n")
            print("REAL_INPUT_IMPORT=" + kind + " PASS", flush=True)
        slicer.app.exit(0)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(2)


qt.QTimer.singleShot(5000, run)
