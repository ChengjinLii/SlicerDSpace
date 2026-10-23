"""Pure, inspectable preparation plan for only the selected workflow."""

from shared.managed_runtimes import supported_platform
from shared.ui_environment_panel import environment_missing_items


def build_setup_plan(result, *, installed_extensions=(), loaded_extensions=None, need_dti=False, need_torch=False, need_ukf=False,
                     brain_mask_backend="pnl_cnn", gpu_available=False, system=None, machine=None,
                     existing_managed_profiles=(), repair=False):
    installed = set(installed_extensions)
    required_extensions = (["SlicerDMRI"] if need_dti else []) + (["PyTorch"] if need_torch else [])
    if need_ukf:
        required_extensions.extend(("SlicerDMRI", "UKFTractography"))
    missing = [item for item in environment_missing_items(result) if item.required]
    groups = {item.install_group for item in missing}
    managed = list(existing_managed_profiles)
    if "mrtrix" in groups:
        managed.append("mrtrix")
    if "fsl" in groups:
        managed.append("fsl_cuda" if gpu_available else "fsl_cpu")
    if brain_mask_backend == "pnl_cnn" and any(item.key == "brain_mask_backend" for item in missing):
        managed.append("pnl_cnn")
    managed = list(dict.fromkeys(managed))
    platforms_ok = supported_platform(system, machine)
    covered = {"model-resources", "python", "slicer-runtime", "slicer-dmri", "ukf"}
    surface_build = platforms_ok and any(item.key == 'surface_postprocess_runtime' and
        (item.details or {}).get('build_required') for item in missing)
    if surface_build:
        covered.add('surface-runtime')
    if platforms_ok:
        covered.update(("mrtrix", "fsl"))
        if "pnl_cnn" in managed:
            covered.add("brain_mask")
    assets = tuple(name for name in ("surface", "segmentation", "parcellation")
                   if any(name in item.targets and item.install_group == "model-resources" for item in missing))
    packages = tuple(dict.fromkeys((item.details or {}).get("install_requirement") or (item.details or {}).get("package")
                                  for item in missing if item.kind == "python" and
                                  ((item.details or {}).get("install_requirement") or (item.details or {}).get("package"))))
    from shared.optional_assets import missing_optional_profiles
    from scripts.setup_optional_assets import prepare
    optional = missing_optional_profiles(result, brain_mask_backend)
    optional_plan = prepare(optional) if optional else {}
    handled_keys = {item.key for item in missing if
                    ("wma" in optional and item.key.startswith("wma_org_atlas")) or
                    ("tractcloud" in optional and (item.key == "tractcloud_data_dir" or item.key.startswith("tractcloud_data:")))}
    return {"kind": "slicerdsurfer_selected_setup_plan", "extensions": list(dict.fromkeys(
                name for name in required_extensions if name not in installed)),
            "restart_extensions": list(dict.fromkeys(name for name in required_extensions
                if loaded_extensions is not None and name in installed and name not in loaded_extensions)),
            "python_packages": list(packages), "asset_profiles": list(assets),
            "optional_asset_profiles": optional,
            "optional_asset_size_bytes": optional_plan.get("size_bytes", 0),
            "optional_asset_terms": optional_plan.get("terms", []),
            "managed_profiles": managed if platforms_ok else [],
            "surface_build_required": surface_build,
            "unsupported_profiles": managed if not platforms_ok else [],
            "manual_items": [{"key": item.key, "label": item.label, "hint": item.install_hint}
                             for item in missing if item.install_group not in covered and item.key not in handled_keys],
            "fsl_license_required": any(name.startswith("fsl_") for name in managed) and platforms_ok,
            "pnl_terms_required": "pnl_cnn" in managed and platforms_ok,
            "repair": bool(repair),
            "scope": "Dependency preparation only; installation is not scientific QC"}
