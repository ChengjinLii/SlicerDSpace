"""Real GUI input reuse, fresh Run validation and paired layout measurements."""

import hashlib
import json
import os
from pathlib import Path
import statistics
import time
import traceback
from unittest.mock import patch

import qt
import slicer


ROOT = Path(os.environ["SLICERDDSURFER_SMOKE_ROOT"])


def raw(root):
    folder = root / "input"
    folder.mkdir(parents=True)
    for name in ("data.nii.gz", "bvals", "bvecs", "nodif_brain_mask.nii.gz"):
        (folder / name).touch()


def measure(root, subject):
    from shared.pipeline import inspect_subject_directory
    from shared.ui_input_inspection import InputInspectionCache

    times = {"uncached": [], "cached": []}
    calls = 20
    expected = inspect_subject_directory(root, subject)
    for repeat in range(8):
        order = ("uncached", "cached") if repeat % 2 == 0 else ("cached", "uncached")
        for name in order:
            cache = InputInspectionCache(inspect_subject_directory)
            inspector = inspect_subject_directory if name == "uncached" else cache.inspect
            started = time.perf_counter()
            outputs = [inspector(root, subject) for _ in range(calls)]
            elapsed = time.perf_counter() - started
            assert all(result == expected for result in outputs)
            if repeat:
                times[name].append(elapsed)
    baseline, cached = (statistics.median(times[name]) for name in ("uncached", "cached"))
    return {"mode": expected["mode"], "calls_per_batch": calls, "seconds": times,
            "uncached_median_seconds": baseline, "cached_median_seconds": cached,
            "speedup": baseline / cached, "layout_results_exact": True}


def run():
    checks = {}
    try:
        import shared.dicom_input as dicom
        from shared.pipeline import inspect_subject_directory
        from shared.ui_input_inspection import InputInspectionCache

        slicer.util.selectModule("SlicerDDSurfer")
        owner = slicer.modules.slicerddsurfer.widgetRepresentation().self()
        owner._onboardingWidgets["language_combo"].setCurrentIndex(0)
        dicom_root = ROOT / "fixtures/dicom"
        series = dicom_root / "series"
        series.mkdir(parents=True)
        for index in range(128):
            (series / f"image-{index:04d}.bin").write_bytes(b"\0" * 132)
        header = series / "zz-valid.bin"
        header.write_bytes(b"\0" * 128 + b"DICM")
        raw_root = ROOT / "fixtures/raw/patient"
        raw(raw_root)

        with slicer.util.NodeModify(owner._parameterNode):
            owner._parameterNode.subjectId = "patient"
            owner._parameterNode.inputDirectory = str(dicom_root)
            owner._parameterNode.targetPreprocessing = False
        owner._inputInspectionCache = InputInspectionCache(inspect_subject_directory)
        with patch.object(dicom, "_dicom_file", wraps=dicom._dicom_file) as reader:
            assert owner._evaluateInputs()[0]
            initial_reads = reader.call_count
            for index in range(20):
                owner._parameterNode.orchestrationSelectStreamlines = 100000 + index
                owner._checkCanApply()
            repeated_reads = reader.call_count - initial_reads
        checks["algorithm_edits_reuse_input_layout"] = initial_reads == 129 and repeated_reads == 0
        kwargs = owner._environment_check_kwargs(external_paths={})
        checks["dicom_still_requires_missing_brain_mask"] = kwargs["brain_mask_required"]

        # Keep the same cache key and directory entries, but invalidate a nested
        # header in place. A real Run click must not trust the cached green light.
        owner._inputInspectionCache = InputInspectionCache(inspect_subject_directory, clock=lambda: 100.0)
        assert owner._evaluateInputs()[0]
        header.write_bytes(b"\0" * 132)
        assert owner._evaluateInputs()[0]
        with patch.object(owner, "_save_common_user_settings") as save:
            owner.ui.runSelectedButton.click()
            checks["run_rechecks_nested_dicom_change_before_setup"] = (
                not save.called and not owner._evaluateInputs()[0]
                and "Subject input layout" in owner.ui.statusLabel.text and not owner._pipelineActive)

        with slicer.util.NodeModify(owner._parameterNode):
            owner._parameterNode.inputDirectory = str(raw_root.parent)
            owner._parameterNode.subjectId = "patient"
        owner._inputInspectionCache = None
        checks["parent_subject_mask_found"] = not owner._environment_check_kwargs(external_paths={})["brain_mask_required"]
        (raw_root / "input/nodif_brain_mask.nii.gz").unlink()
        checks["removed_mask_requires_generator_immediately"] = owner._environment_check_kwargs(external_paths={})["brain_mask_required"]
        assert owner._evaluateInputs()[0]
        (raw_root / "input/bvals").unlink()
        checks["removed_raw_input_rejected_without_ttl_wait"] = not owner._evaluateInputs()[0]
        (raw_root / "input/bvals").touch()
        header.write_bytes(b"\0" * 128 + b"DICM")
        rows = [measure(dicom_root, "patient"), measure(raw_root, "patient")]
        result = {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
                  "initial_header_probes": initial_reads, "additional_probes_during_20_edits": repeated_reads,
                  "measurements": rows,
                  "pipeline_sha256": hashlib.sha256(Path(inspect_subject_directory.__code__.co_filename).read_bytes()).hexdigest(),
                  "scope": "Synthetic input-layout and real GUI contracts only; no DICOM conversion, scientific QC or total workflow speedup claim"}
    except Exception:
        traceback.print_exc()
        result = {"status": "failed", "checks": checks, "error": traceback.format_exc()}
    (ROOT / "input_inspection.json").write_text(json.dumps(result, indent=2) + "\n")
    print("INPUT_INSPECTION=" + json.dumps(result), flush=True)
    slicer.app.exit(0 if result["status"] == "passed" else 2)


qt.QTimer.singleShot(5000, run)
