#!/usr/bin/env python3
"""Isolated scientific acceptance without replacing existing products."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def fingerprint(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return {"path": str(path), "sha256": digest.hexdigest(), "size": path.stat().st_size}


def run_postprocess(args, record):
    import nibabel as nib
    import numpy as np
    from anatomy.surface.backend_bridge import native_surface_hashes, upstream_record
    from anatomy.surface.postprocess_release import DDSurferPostprocessConfig, run_ddsurfer_postprocess
    from shared.orchestrator import _surface_postprocess_complete

    before = native_surface_hashes(args.native_dir)
    output_root = args.existing_output_root or args.output_dir / "outputs"
    result = run_ddsurfer_postprocess(DDSurferPostprocessConfig(
        subject_id=args.subject_id, subject_root=args.subject_root, output_root=output_root,
        native_dir=args.native_dir, freesurfer_home=args.freesurfer_home, python_bin=Path(sys.executable),
    ), log=lambda message: print(message, flush=True))
    record["manifest"] = str(result.manifest_path)
    record["qc"] = str(result.qc_path)
    checks = {"current_output_contract": _surface_postprocess_complete(args.subject_root, args.subject_id, output_root),
              "native_inputs_unchanged": before == native_surface_hashes(args.native_dir)}
    details = {}
    for hemi in ("lh", "rh"):
        white, faces = nib.freesurfer.read_geometry(result.structural_root / "surf" / f"{hemi}.white")
        pial, pial_faces = nib.freesurfer.read_geometry(result.structural_root / "surf" / f"{hemi}.pial")
        checks[f"{hemi}_finite_corresponding_surfaces"] = bool(np.isfinite(white).all() and np.isfinite(pial).all()
            and white.shape == pial.shape and np.array_equal(faces, pial_faces))
        metrics = {}
        for name in ("thickness", "curv", "sulc", "area"):
            array = nib.freesurfer.read_morph_data(result.structural_root / "surf" / f"{hemi}.{name}")
            checks[f"{hemi}_{name}_finite_vertex_count"] = bool(array.size == len(white) and np.isfinite(array).all())
            metrics[name] = {"vertices": int(array.size), "min": float(array.min()), "median": float(np.median(array)), "max": float(array.max())}
        for atlas in ("aparc", "aparc.a2009s"):
            labels, _, names = nib.freesurfer.read_annot(result.structural_root / "label" / f"{hemi}.{atlas}.annot")
            checks[f"{hemi}_{atlas}_annotation_count"] = len(labels) == len(white) and bool(len(names) > 1)
        details[hemi] = metrics
    record.update(checks=checks, metrics=details, upstream=upstream_record(), native_sha256=before,
                  automatic_qc_passed=all(checks.values()), human_review="pending")


def run_wma(args, record):
    from tractography.wma import WMAOrgAtlasConfig, run_wma_org_atlas

    before = fingerprint(args.tractogram)
    result = run_wma_org_atlas(WMAOrgAtlasConfig(
        subject_id=args.subject_id, input_tractography=args.tractogram, atlas_dir=args.atlas_dir,
        output_dir=args.output_dir / "products", slicer_executable=args.slicer,
        wma_root=args.wma_root, mrtrix_bin_dir=args.mrtrix_bin_dir,
        num_threads=args.threads, use_virtual_x=True, clean_files=0, execute=True,
    ), log=lambda message: print(message, flush=True))
    qc = json.loads(result.qc_path.read_text())
    unchanged = before == fingerprint(args.tractogram)
    record.update(manifest=str(result.manifest_path), qc=str(result.qc_path), input=before,
                  inputs_unchanged=unchanged,
                  automatic_qc_passed=unchanged and qc.get("automatic_qc_passed") is True,
                  backend_status=result.status, output_summary=qc.get("output_summary"),
                  error=qc.get("error"), human_review="pending")


def compare_arrays(expected, actual, *, rtol=2e-5, atol=2e-6):
    import numpy as np

    expected, actual = np.asarray(expected), np.asarray(actual)
    same_shape = expected.shape == actual.shape
    finite = bool(np.isfinite(expected).all() and np.isfinite(actual).all())
    return {"passed": same_shape and finite and bool(np.allclose(expected, actual, rtol=rtol, atol=atol)),
            "max_absolute_error": float(np.max(np.abs(expected - actual))) if same_shape and finite else None,
            "rtol": rtol, "atol": atol}


def run_dki_audit(args, record):
    import nibabel as nib
    import numpy as np
    from dipy.core.gradients import gradient_table
    from dipy.reconst.dki import DiffusionKurtosisModel
    from microstructure.dki import DkiConfig, DKI_METRICS, dki_outputs_current, expected_dki_signature
    from scripts.audit_scientific_outputs import _audit_dki
    from shared.diffusion_io import diffusion_image
    from shared.pipeline import RawInputBundle

    manifest = json.loads(args.stage_manifest.read_text())
    signature = manifest["signature"]
    inputs = {key: Path(value["path"]) for key, value in signature["inputs"].items()}
    before = {key: fingerprint(path) for key, path in inputs.items()}
    raw = RawInputBundle(args.subject_root, args.subject_id, inputs["dwi"].parent,
                         inputs["dwi"], inputs["bval"], inputs["bvec"], inputs["mask"])
    settings = signature["settings"]
    config = DkiConfig(args.subject_id, raw, args.stage_manifest.parent,
                       fit_method=settings["fit_method"], b0_threshold=settings["b0_threshold"],
                       shell_tolerance=settings["shell_tolerance"], max_bvalue=settings["max_bvalue"],
                       min_directions_per_shell=settings["min_directions_per_shell"],
                       voxels_per_chunk=settings["voxels_per_chunk"],
                       display_min_kurtosis=settings["display_bounds"][0],
                       display_max_kurtosis=settings["display_bounds"][1])
    outputs = manifest["outputs"]
    qc = json.loads(Path(outputs["qc"]).read_text())
    checks = []
    _audit_dki({"subject_root": str(args.subject_root), "analysis_inputs": inputs,
                "tasks": [{"name": "microstructure.dki", "status": manifest["status"], "outputs": outputs}]}, checks)
    arrays = {key: np.asarray(nib.load(value).dataobj) for key, value in outputs.items()
              if key not in {"manifest", "qc", "progress"}}
    mask = np.asarray(nib.load(inputs["mask"]).dataobj) > 0
    fit, valid = arrays["fit_mask"] > 0, arrays["valid_mask"] > 0
    strict_checks = {
        "source_and_library_signature_current": signature == expected_dki_signature(config),
        "current_cache_contract": dki_outputs_current(config),
        "fit_inside_actual_brain_mask": not bool(np.any(fit & ~mask)),
        "full_mask_count": int(mask.sum()) == qc["mask_voxels"],
    }
    for key, array in arrays.items():
        strict_checks[f"{key}_outside_mask_zero"] = bool(np.all(array[~mask] == 0))
        if key not in {"fit_mask", "valid_mask"}:
            strict_checks[f"{key}_unfitted_in_mask_nan"] = bool(np.isnan(array[mask & ~fit]).all())
    strict_checks["valid_parameters_and_S0"] = bool(np.isfinite(arrays["params"][valid]).all()
        and np.isfinite(arrays["s0"][valid]).all() and np.all(arrays["s0"][valid] > 0))
    selected = np.asarray(qc["eligibility"]["selected_volumes"], dtype=int)
    bvals = np.loadtxt(inputs["bval"]).reshape(-1)
    bvecs = np.loadtxt(inputs["bvec"])
    if bvecs.shape == (3, len(bvals)):
        bvecs = bvecs.T
    bvecs = bvecs.copy()
    bvecs[bvals <= settings["b0_threshold"]] = 0
    gtab = gradient_table(bvals[selected], bvecs=bvecs[selected], b0_threshold=settings["b0_threshold"], atol=.01)
    model = DiffusionKurtosisModel(gtab, fit_method=qc["fit_method"], return_S0_hat=True, min_signal=1e-6)
    fitted_indices = np.flatnonzero(fit.ravel())
    indices = fitted_indices[np.linspace(0, len(fitted_indices) - 1, min(args.sample_voxels, len(fitted_indices)), dtype=int)]
    xyz = np.unravel_index(indices, mask.shape)
    # Decompress once, then sample the original scaled measurements. No map or
    # input is rewritten; the reference fit uses upstream DIPY directly.
    with diffusion_image(inputs["dwi"], work_dir=args.output_dir) as image:
        proxy = image.dataobj
        unscaled = proxy.get_unscaled()
        observed = np.asarray(unscaled[xyz[0], xyz[1], xyz[2], :][:, selected], dtype=float) * proxy.slope + proxy.inter
        fitted = model.fit(observed)
        s0 = np.asarray(fitted.model_S0).reshape(-1)
        prediction = fitted.predict(gtab, S0=s0)
        rmse = np.sqrt(np.mean((prediction - observed) ** 2, axis=1))
        references = {"params": fitted.model_params, "s0": s0, "rmse": rmse, "nrmse": rmse / s0,
                      "kfa_raw": np.asarray(fitted.kfa).reshape(-1)}
        references.update({key + "_raw": np.asarray(getattr(fitted, key)(min_kurtosis=None, max_kurtosis=None)).reshape(-1)
                           for key in DKI_METRICS if key != "kfa"})
        parity = {key: compare_arrays(value, arrays[key][xyz]) for key, value in references.items()}
        del unscaled
    strict_checks["direct_upstream_sample_parity"] = all(value["passed"] for value in parity.values())
    strict_checks["inputs_unchanged"] = before == {key: fingerprint(path) for key, path in inputs.items()}
    residuals = {key: {str(q): float(np.percentile(arrays[key][valid], q)) for q in (50, 95, 99)}
                 for key in ("rmse", "nrmse")}
    record.update(manifest=str(args.stage_manifest.resolve()), input=before,
                  full_fit_runtime_seconds=manifest["runtime_seconds"], independent_checks=checks,
                  checks=strict_checks, sampled_voxels=len(indices), sample_voxel_ijk=np.column_stack(xyz).tolist(),
                  sample_parity=parity, residual_percentiles=residuals,
                  mask_voxels=int(mask.sum()), fitted_voxels=int(fit.sum()), valid_voxels=int(valid.sum()),
                  automatic_qc_passed=all(strict_checks.values()) and all(check["passed"] for check in checks),
                  human_review="pending", scope="Read-only full-grid audit plus deterministic direct-DIPY sample refit; not a new full fit")


def run_bundle_audit(args, record):
    from scripts.audit_bundle_products import audit

    deadline = time.monotonic() + args.wait_seconds
    while True:
        manifest = json.loads(args.stage_manifest.read_text())
        if manifest.get("status") != "running":
            break
        if time.monotonic() >= deadline:
            raise TimeoutError("Bundle stage still running; final independent QC is not available")
        time.sleep(min(15, max(0, deadline - time.monotonic())))
    result = audit(args.stage_manifest)
    path = args.output_dir / "bundle_audit.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    record.update(manifest=str(args.stage_manifest.resolve()), audit=str(path),
                  checks=result["checks"], automatic_qc_passed=all(result["checks"].values()),
                  human_review="pending", input_streamlines=result["input_streamlines"],
                  current_contract_error=result["current_contract_error"],
                  scope="Independent finished-stage bundle decode/source-membership audit; runtime includes optional wait, NOT extraction time")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("route", choices=("postprocess", "wma", "dki-audit", "bundle-audit"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--subject-root", type=Path)
    parser.add_argument("--native-dir", type=Path)
    parser.add_argument("--freesurfer-home", type=Path)
    parser.add_argument("--tractogram", type=Path)
    parser.add_argument("--atlas-dir", type=Path)
    parser.add_argument("--wma-root", type=Path)
    parser.add_argument("--mrtrix-bin-dir", type=Path)
    parser.add_argument("--slicer", type=Path)
    parser.add_argument("--stage-manifest", type=Path)
    parser.add_argument("--sample-voxels", type=int, default=128)
    parser.add_argument("--existing-output-root", type=Path, help="Surface stage resume/audit only; not a fresh compute timing")
    parser.add_argument("--wait-seconds", type=int, default=0, help="Wait at most this long for an existing bundle stage before independent audit")
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()
    required = {"postprocess": ("subject_root", "native_dir", "freesurfer_home"),
                "wma": ("tractogram", "atlas_dir", "wma_root", "slicer"),
                "dki-audit": ("stage_manifest", "subject_root"),
                "bundle-audit": ("stage_manifest",)}[args.route]
    for name in required:
        if getattr(args, name) is None:
            parser.error(f"{args.route} requires --{name.replace('_', '-')}")
    if args.threads < 1 or args.sample_voxels < 1 or args.wait_seconds < 0:
        parser.error("threads/sample-voxels must be positive; wait-seconds must be nonnegative")
    args.output_dir = args.output_dir.resolve()
    if args.output_dir.exists():
        raise FileExistsError("Choose a new evidence directory; previous products are preserved")
    args.output_dir.mkdir(parents=True)
    # Native WMA launches helper Slicers. User settings are private; no running
    # application or MRI Agent is terminated/reconfigured.
    os.environ["XDG_CONFIG_HOME"] = str(args.output_dir / "user_settings")
    os.environ["XDG_CACHE_HOME"] = str(args.output_dir / "user_cache")
    record = {"kind": "real_scientific_followup", "route": args.route, "subject_id": args.subject_id,
              "created_at": datetime.now(timezone.utc).isoformat(), "status": "running",
              "scope": "New real route execution; automatic checks are not anatomical certification"}
    if args.existing_output_root:
        if args.route != "postprocess":
            parser.error("existing-output-root is only valid for postprocess")
        record["scope"] = "Surface stage resume plus strengthened integrity QC; NOT a fresh postprocessing timing"
    report = args.output_dir / "acceptance.json"
    report.write_text(json.dumps(record, indent=2) + "\n")
    started = time.perf_counter()
    try:
        {"postprocess": run_postprocess, "wma": run_wma, "dki-audit": run_dki_audit,
         "bundle-audit": run_bundle_audit}[args.route](args, record)
        record["status"] = "passed" if record.get("automatic_qc_passed") else "failed"
    except Exception as exc:
        record.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        record["runtime_seconds"] = time.perf_counter() - started
        report.write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record, indent=2), flush=True)
    return 0 if record["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
