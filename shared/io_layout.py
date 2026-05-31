"""Canonical subject I/O layout for SlicerDDSurfer outputs.

The paths mirror the product-level tree documented in ``SlicerDDSurfer.html``.
Pipeline code should use this module for default locations while still honoring
explicit user-provided output paths for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import shutil


@dataclass(frozen=True)
class SubjectIOLayout:
    """Canonical output and cache directories for one subject root."""

    subject_root: Path
    output_root: Optional[Path] = None

    @property
    def outputs(self) -> Path:
        return self.output_root if self.output_root is not None else self.subject_root / "outputs"

    @property
    def run_metadata(self) -> Path:
        return self.outputs / "00_run_metadata"

    @property
    def preproc(self) -> Path:
        return self.outputs / "01_preproc"

    @property
    def microstructure(self) -> Path:
        return self.outputs / "02_microstructure"

    @property
    def microstructure_dti(self) -> Path:
        return self.microstructure / "dti"

    @property
    def microstructure_freewater(self) -> Path:
        return self.microstructure / "freewater"

    @property
    def microstructure_noddi(self) -> Path:
        return self.microstructure / "noddi"

    @property
    def structural(self) -> Path:
        return self.outputs / "03_structural"

    @property
    def ddseg(self) -> Path:
        return self.structural / "ddseg"

    @property
    def ddsurfer(self) -> Path:
        return self.structural / "ddsurfer"

    @property
    def ddparcel(self) -> Path:
        return self.structural / "ddparcel"

    @property
    def registered_to_dwi(self) -> Path:
        return self.structural / "registered_to_dwi"

    @property
    def tractography(self) -> Path:
        return self.outputs / "04_tractography"

    @property
    def csd(self) -> Path:
        return self.tractography / "csd"

    @property
    def act_prep(self) -> Path:
        return self.tractography / "act_prep"

    @property
    def tract_cloud(self) -> Path:
        return self.tractography / "tract_cloud"

    @property
    def tractograms(self) -> Path:
        return self.tractography / "tractograms"

    @property
    def tractograms_dti_det(self) -> Path:
        return self.tractograms / "dti_det"

    @property
    def tractograms_csd_prob(self) -> Path:
        return self.tractograms / "csd_prob"

    @property
    def tractograms_csd_act(self) -> Path:
        return self.tractograms / "csd_act"

    @property
    def saf(self) -> Path:
        return self.tractography / "saf"

    @property
    def bundles(self) -> Path:
        return self.tractography / "bundles"

    @property
    def bundles_wma(self) -> Path:
        return self.bundles / "wma_org_atlas"

    @property
    def bundles_tractcloud(self) -> Path:
        return self.bundles / "tract_cloud_dl"

    @property
    def bundles_wmql(self) -> Path:
        return self.bundles / "wmql"

    @property
    def connectome(self) -> Path:
        return self.tractography / "connectome"

    @property
    def statistics(self) -> Path:
        return self.outputs / "05_statistics"

    @property
    def regional_microstructure(self) -> Path:
        return self.statistics / "regional_microstructure"

    @property
    def bundle_profiles(self) -> Path:
        return self.statistics / "bundle_profiles"

    @property
    def slicer_scene_report(self) -> Path:
        return self.outputs / "06_slicer_scene_report"

    @property
    def cache(self) -> Path:
        return self.subject_root / "cache"


def subject_layout(subject_root: Path, output_root: Optional[Path] = None) -> SubjectIOLayout:
    return SubjectIOLayout(
        subject_root=subject_root.expanduser().resolve(),
        output_root=output_root.expanduser().resolve() if output_root is not None else None,
    )


def default_task_output_dir(subject_root: Path, task_name: str) -> Path:
    """Return the canonical default output directory for a workflow task."""

    layout = subject_layout(subject_root)
    normalized = task_name.lower().replace("-", "_")
    mapping = {
        "validation": layout.run_metadata / "validation",
        "input_validation": layout.run_metadata / "validation",
        "preproc": layout.preproc,
        "microstructure": layout.microstructure,
        "dti": layout.microstructure_dti,
        "freewater": layout.microstructure_freewater,
        "noddi": layout.microstructure_noddi,
        "segmentation": layout.ddseg,
        "ddseg": layout.ddseg,
        "surface": layout.ddsurfer,
        "ddsurfer": layout.ddsurfer,
        "parcellation": layout.ddparcel,
        "ddparcel": layout.ddparcel,
        "tractography": layout.tractography,
        "tractography_dti": layout.tractograms_dti_det,
        "dti_tractography": layout.tractograms_dti_det,
        "tractography_act": layout.tractograms_csd_act,
        "act": layout.tractograms_csd_act,
        "act_prep": layout.act_prep,
        "saf": layout.saf,
        "short_association_fibres": layout.saf,
        "short_association_fibers": layout.saf,
        "wma": layout.bundles_wma,
        "wma_org_atlas": layout.bundles_wma,
        "wmql": layout.bundles_wmql,
        "wmql_bundle_segmentation": layout.bundles_wmql,
        "tractcloud": layout.bundles_tractcloud,
        "tract_cloud": layout.tract_cloud,
        "connectome": layout.connectome,
        "statistics": layout.statistics,
        "regional_microstructure": layout.regional_microstructure,
        "slicer_scene_report": layout.slicer_scene_report,
    }
    return mapping.get(normalized, layout.outputs / normalized)


def default_task_output_dir_for_dependency(dependency_path: Path, task_name: str) -> Path:
    """Infer a canonical output directory from a dependency already under a subject tree."""

    resolved = dependency_path.expanduser().resolve()
    parts = resolved.parts
    if "outputs" in parts:
        outputs_index = parts.index("outputs")
        if outputs_index > 0:
            return default_task_output_dir(Path(*parts[:outputs_index]), task_name)
    if "input" in parts:
        input_index = parts.index("input")
        if input_index > 0:
            return default_task_output_dir(Path(*parts[:input_index]), task_name)
    return resolved.parent / task_name


def _safe_link_or_copy(src: Path, dest: Path, *, mode: str) -> None:
    if dest.exists() or dest.is_symlink():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if mode == "symlink":
        try:
            dest.symlink_to(src.resolve(), target_is_directory=src.is_dir())
            return
        except OSError:
            pass
    if src.is_dir():
        shutil.copytree(src, dest, symlinks=True)
    else:
        shutil.copy2(src, dest)


def _archive_legacy_path(src: Path, archive_root: Path) -> None:
    if not src.exists() or src.is_symlink():
        return
    archive_root.mkdir(parents=True, exist_ok=True)
    dest = archive_root / src.name
    if dest.exists():
        suffix = 1
        while (archive_root / f"{src.name}.{suffix}").exists():
            suffix += 1
        dest = archive_root / f"{src.name}.{suffix}"
    shutil.move(src.as_posix(), dest.as_posix())


def materialize_canonical_output_tree(
    subject_root: Path,
    *,
    output_root: Optional[Path] = None,
    mode: str = "symlink",
    archive_legacy: bool = False,
) -> dict[str, Path]:
    """Create canonical output-tree views for known legacy SlicerDDSurfer outputs.

    ``mode`` controls how existing legacy files are exposed in the canonical tree:
    ``symlink`` avoids duplicating large neuroimaging files, while ``copy`` creates
    standalone files. If ``archive_legacy`` is true, legacy top-level directories
    are moved under ``.legacy_flat_outputs`` after canonical links/copies are
    created so ``outputs`` remains a clean product tree.
    """

    if mode not in {"symlink", "copy"}:
        raise ValueError("mode must be 'symlink' or 'copy'")
    if archive_legacy and mode == "symlink":
        raise ValueError("archive_legacy=True requires mode='copy' so canonical links do not break")

    layout = subject_layout(subject_root, output_root=output_root)
    outputs = layout.outputs
    archive_root = layout.subject_root / ".legacy_flat_outputs"
    created: dict[str, Path] = {}

    directory_map = {
        "validation": layout.run_metadata / "validation",
        "ddseg": layout.ddseg,
        "ddseg_cpu": layout.structural / "ddseg_cpu",
        "ddseg_cuda": layout.structural / "ddseg_cuda",
        "ddsurfer": layout.ddsurfer,
        "ddparcel": layout.ddparcel,
    }
    for legacy_name, canonical_dir in directory_map.items():
        legacy_dir = outputs / legacy_name
        if legacy_dir.exists():
            _safe_link_or_copy(legacy_dir, canonical_dir, mode=mode)
            created[legacy_name] = canonical_dir

    legacy_microstructure = outputs / "microstructure"
    if legacy_microstructure.exists():
        subject_id = layout.subject_root.name
        file_map = {
            f"{subject_id}-dti-FractionalAnisotropy.nii.gz": layout.microstructure_dti / f"{subject_id}_dti_FA.nii.gz",
            f"{subject_id}-dti-MeanDiffusivity.nii.gz": layout.microstructure_dti / f"{subject_id}_dti_MD.nii.gz",
            f"{subject_id}-freewater-Fraction.nii.gz": layout.microstructure_freewater / f"{subject_id}_fw_fraction.nii.gz",
            f"{subject_id}-freewater-TissueFA.nii.gz": layout.microstructure_freewater / f"{subject_id}_fw_FA.nii.gz",
            f"{subject_id}-freewater-TissueMD.nii.gz": layout.microstructure_freewater / f"{subject_id}_fw_MD.nii.gz",
            f"{subject_id}-noddi-NDI.nii.gz": layout.microstructure_noddi / f"{subject_id}_noddi_NDI.nii.gz",
            f"{subject_id}-noddi-ODI.nii.gz": layout.microstructure_noddi / f"{subject_id}_noddi_ODI.nii.gz",
            f"{subject_id}-noddi-FWF.nii.gz": layout.microstructure_noddi / f"{subject_id}_noddi_IsoVF.nii.gz",
            "freewater_manifest.json": layout.microstructure_freewater / "freewater_manifest.json",
            "noddi_manifest.json": layout.microstructure_noddi / "noddi_manifest.json",
            f"{subject_id}-ROIWise-FA.csv": layout.regional_microstructure / f"{subject_id}_ROIWise-Microstructure.csv",
            f"{subject_id}-ROIWise-FA.json": layout.regional_microstructure / f"{subject_id}_ROIWise-Microstructure.json",
        }
        for legacy_name, canonical_path in file_map.items():
            legacy_path = legacy_microstructure / legacy_name
            if legacy_path.exists():
                _safe_link_or_copy(legacy_path, canonical_path, mode=mode)
                created[legacy_name] = canonical_path
        amico_dir = legacy_microstructure / "_amico_noddi"
        if amico_dir.exists():
            _safe_link_or_copy(amico_dir, layout.microstructure_noddi / "_amico_noddi", mode=mode)
            created["_amico_noddi"] = layout.microstructure_noddi / "_amico_noddi"

    legacy_tractography = outputs / "tractography"
    if legacy_tractography.exists():
        for legacy_path in legacy_tractography.iterdir():
            if legacy_path.is_file():
                _safe_link_or_copy(legacy_path, layout.tractograms_dti_det / legacy_path.name, mode=mode)
                created[f"tractography/{legacy_path.name}"] = layout.tractograms_dti_det / legacy_path.name

    tractcloud_root_map = {
        "AnatomicalTracts": layout.bundles_tractcloud / "AnatomicalTracts",
        "AnatomicalTracts_separated": layout.bundles_tractcloud / "AnatomicalTracts_separated",
    }
    for legacy_name, canonical_dir in tractcloud_root_map.items():
        legacy_dir = layout.subject_root / legacy_name
        if legacy_dir.exists():
            _safe_link_or_copy(legacy_dir, canonical_dir, mode=mode)
            created[legacy_name] = canonical_dir

    if archive_legacy:
        for legacy_name in [*directory_map.keys(), "microstructure", "microstructure_direct", "microstructure_regression", "tractography"]:
            _archive_legacy_path(outputs / legacy_name, archive_root)
        for legacy_name in tractcloud_root_map:
            _archive_legacy_path(layout.subject_root / legacy_name, archive_root)

    return created
