#!/usr/bin/env python3
"""Read-only saved-scalar revalidation plus opt-in isolated full-brain DKI."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(subject_root, report_dir, run_dki=False, refit_noddi=False):
    from microstructure.pipeline import (
        MicrostructureConfig, DTI_KEYS, _output_paths, _write_dti_qc, _write_free_water_qc,
        _write_noddi_qc, _export_dti_scalar_maps, _file_signature,
    )
    from shared.pipeline import RawInputBundle

    subject_root, report_dir = Path(subject_root).resolve(), Path(report_dir).resolve()
    if subject_root == report_dir or subject_root in report_dir.parents:
        raise ValueError("Evidence must be outside the original subject directory")
    report_dir.mkdir(parents=True, exist_ok=True)
    micro = subject_root / "outputs/02_microstructure"
    manifest = json.loads((micro / "manifest.json").read_text())
    subject_id = manifest["subject_id"]
    sources = {key: Path(value["path"]) for key, value in manifest["raw_input_bundle"].items()}
    raw = RawInputBundle(subject_root, subject_id, sources["dwi"].parent, sources["dwi"],
                         sources["bval"], sources["bvec"], sources["mask"])
    native_root = Path(manifest["native_bundle"]["dir"])
    native = SimpleNamespace(manifest_path=native_root / "manifest.json")
    for attr, metric in (("fa_nii_path", "FractionalAnisotropy"), ("trace_nii_path", "Trace"),
                         ("mean_diffusivity_nii_path", "MeanDiffusivity"), ("max_eig_nii_path", "MaxEigenvalue"),
                         ("mid_eig_nii_path", "MidEigenvalue"), ("min_eig_nii_path", "MinEigenvalue")):
        setattr(native, attr, native_root / f"{subject_id}-dti-{metric}.nii.gz")
    config = MicrostructureConfig(subject_id, raw, native, report_dir / "exports")
    before = {key: _file_signature(path) for key, path in sources.items()}
    paths = _output_paths(subject_id, micro)
    checks = []
    for stage, writer in (("dti", _write_dti_qc), ("free_water", _write_free_water_qc), ("noddi", _write_noddi_qc)):
        scoped = dict(paths)
        scoped[f"{stage}_qc"] = report_dir / f"{stage}_qc.json"
        start = time.perf_counter()
        try:
            payload = writer(config, scoped)
            checks.append({"stage": stage, "status": payload["status"], "qc": str(scoped[f"{stage}_qc"]),
                           "seconds": time.perf_counter() - start, "scope": "saved full-brain scalar integrity, not a refit"})
        except FileNotFoundError as exc:
            checks.append({"stage": stage, "status": "missing", "error": str(exc)})
        except Exception as exc:
            checks.append({"stage": stage, "status": "failed", "error": str(exc), "seconds": time.perf_counter() - start})
        print(f"[Scalar QC] {stage}: {checks[-1]['status']}", flush=True)
    from anatomy.parcellation.qc import validate_outputs

    from shared.io_layout import subject_layout
    parcel = subject_layout(subject_root).anatomy_input_dir("ddparcel")
    if parcel.is_dir():
        # QC writes are redirected by a shallow copy of only the six products.
        # Keep saved scientific data untouched and use links where supported.
        evidence_parcel = report_dir / "ddparcel"
        evidence_parcel.mkdir(exist_ok=True)
        import shutil
        for path in parcel.iterdir():
            if path.name.endswith((".nii.gz", "-Reg.mgz")):
                target = evidence_parcel / path.name
                if not target.exists():
                    try:
                        target.symlink_to(path.resolve())
                    except OSError:
                        shutil.copy2(path, target)
        start = time.perf_counter()
        try:
            result = validate_outputs(subject_id, evidence_parcel, sources["mask"])
            checks.append({"stage": "ddparcel", "status": result["status"], "seconds": time.perf_counter() - start,
                           "qc": str(evidence_parcel / "ddparcel_qc.json"), "scope": "saved product integrity, no inference"})
        except Exception as exc:
            checks.append({"stage": "ddparcel", "status": "failed", "error": str(exc)})
    if checks[0]["status"] == "completed":
        export_paths = _output_paths(subject_id, config.output_dir)
        start = time.perf_counter()
        _export_dti_scalar_maps(config, export_paths)
        fresh_seconds = time.perf_counter() - start
        before_export = {key: _file_signature(export_paths[key]) for key in DTI_KEYS}
        start = time.perf_counter()
        _export_dti_scalar_maps(config, export_paths)
        cache_seconds = time.perf_counter() - start
        checks.append({"stage": "dti_export_cache", "status": "completed", "fresh_export_seconds": fresh_seconds,
                       "cache_seconds": cache_seconds, "cached_output_stamps_unchanged": before_export == {
                           key: _file_signature(export_paths[key]) for key in DTI_KEYS}, "scope": "eight scalar export+QC, NOT tensor fitting"})
    if run_dki:
        from microstructure.dki import DkiConfig, inspect_dki_inputs, run_dki as fit_dki

        dki_config = DkiConfig(subject_id, raw, report_dir / "full_brain_dki")
        info = inspect_dki_inputs(dki_config)
        (report_dir / "dki_eligibility.json").write_text(json.dumps(info, indent=2) + "\n")
        start = time.perf_counter()
        if info["eligible"]:
            try:
                result = fit_dki(dki_config, log=lambda message: print(message, flush=True))
                checks.append({"stage": "dki", "status": result.status, "seconds": time.perf_counter() - start,
                               "scope": "full supplied brain mask; unsmoothed WLS", "qc": str(result.qc_path)})
            except Exception as exc:
                checks.append({"stage": "dki", "status": "failed", "error": str(exc), "seconds": time.perf_counter() - start})
        else:
            checks.append({"stage": "dki", "status": "ineligible", "reasons": info["reasons"]})
    if refit_noddi:
        from microstructure.pipeline import _compute_noddi_maps, _expected_noddi_manifest, _write_json
        from dataclasses import replace

        # Keep the new protocol-keyed kernel cache and fit outputs in evidence.
        fit_raw = replace(raw, subject_root=report_dir / "noddi_fit_subject")
        fit_config = replace(config, raw_input_bundle=fit_raw, output_dir=report_dir / "noddi_refit")
        fit_paths = _output_paths(subject_id, fit_config.output_dir)
        fit_paths["noddi_ndi"].parent.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        try:
            _compute_noddi_maps(config=fit_config, paths=fit_paths, log=lambda message: print(message, flush=True))
            _write_json(fit_paths["noddi_manifest"], _expected_noddi_manifest(fit_config))
            checks.append({"stage": "noddi_refit", "status": "completed", "seconds": time.perf_counter() - start,
                           "scope": "new full-brain AMICO fit; isolated protocol-keyed cache; automatic bounded CPU threads",
                           "qc": str(fit_paths["noddi_qc"])})
        except Exception as exc:
            checks.append({"stage": "noddi_refit", "status": "failed", "error": str(exc), "seconds": time.perf_counter() - start})
    payload = {"kind": "saved_scalar_and_optional_full_brain_dki_acceptance", "subject_id": subject_id,
               "created_at": datetime.now(timezone.utc).isoformat(), "checks": checks,
               "inputs_unchanged": before == {key: _file_signature(path) for key, path in sources.items()},
               "inputs": before, "limitations": ["Saved maps are not refitted unless --run-dki is requested.",
                                                  "Automatic integrity checks do not certify anatomical/model accuracy."]}
    (report_dir / "acceptance.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2), flush=True)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-root", required=True, type=Path)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--run-dki", action="store_true")
    parser.add_argument("--refit-noddi", action="store_true")
    args = parser.parse_args()
    run(args.subject_root, args.report_dir, args.run_dki, args.refit_noddi)
