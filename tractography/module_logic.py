"""Tractography workflow logic glue for SlicerDDSurfer."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from shared import default_task_output_dir_for_dependency
from tractography.act import ACTTrackingConfig, ACTTrackingResult, run_act_tracking
from tractography.bundle_parcellation import (
    BundleParcellationConfig,
    BundleParcellationResult,
    run_bundle_parcellation,
)
from tractography.dti import DTITrackingConfig, DTITrackingResult, run_dti_tracking
from tractography.tractcloud import TractCloudConfig, TractCloudResult, run_tractcloud_parcellation
from tractography.wma import WMAOrgAtlasConfig, WMAOrgAtlasResult, run_wma_org_atlas


class TractographyLogicMixin:
    """Logic entrypoints for tractography-related workflows."""

    def runDTITrackingPipeline(
        self,
        *,
        subject_id: str,
        input_root: Path,
        output_dir: Optional[Path] = None,
        fit_method: str = "wls",
        tracking_method: str = "deterministic",
        output_format: str = "trk",
        step_size_mm: float = 0.5,
        max_angle_deg: float = 30.0,
        seed_density: int = 1,
        min_fa: float = 0.2,
        force_recompute: bool = False,
        execute: bool = False,
    ) -> DTITrackingResult:
        config = DTITrackingConfig(
            subject_id=subject_id,
            input_root=input_root,
            output_dir=output_dir,
            fit_method=fit_method,
            tracking_method=tracking_method,
            output_format=output_format,
            step_size_mm=step_size_mm,
            max_angle_deg=max_angle_deg,
            seed_density=seed_density,
            min_fa=min_fa,
            force_recompute=force_recompute,
            execute=execute,
        )
        return run_dti_tracking(config, log=self.log)

    def runACTTrackingPipeline(
        self,
        *,
        subject_id: str,
        parcellation_path: Path,
        output_dir: Optional[Path] = None,
        tractography_path: Optional[Path] = None,
        dwi_path: Optional[Path] = None,
        bval_path: Optional[Path] = None,
        bvec_path: Optional[Path] = None,
        mask_path: Optional[Path] = None,
        five_tt_path: Optional[Path] = None,
        gmwmi_path: Optional[Path] = None,
        wm_fod_path: Optional[Path] = None,
        algorithm: str = "iFOD2",
        seed_count: int = 1_000_000,
        sift2: bool = True,
        execute: bool = False,
    ) -> ACTTrackingResult:
        resolved_output_dir = (
            output_dir
            if output_dir is not None
            else default_task_output_dir_for_dependency(parcellation_path, "tractography_act")
        )
        config = ACTTrackingConfig(
            subject_id=subject_id,
            parcellation_path=parcellation_path,
            output_dir=resolved_output_dir,
            tractography_path=tractography_path,
            dwi_path=dwi_path,
            bval_path=bval_path,
            bvec_path=bvec_path,
            mask_path=mask_path,
            five_tt_path=five_tt_path,
            gmwmi_path=gmwmi_path,
            wm_fod_path=wm_fod_path,
            algorithm=algorithm,
            seed_count=seed_count,
            sift2=sift2,
            execute=execute,
        )
        return run_act_tracking(config, log=self.log)

    def runWMAOrgAtlasPipeline(
        self,
        *,
        subject_id: str,
        input_tractography: Path,
        atlas_dir: Path,
        output_dir: Optional[Path] = None,
        slicer_executable: Path,
        wma_root: Optional[Path] = None,
        transform_path: Optional[Path] = None,
        registration_mode: str = "rig",
        num_threads: int = 1,
        use_virtual_x: bool = False,
        export_diffusion_measures: bool = False,
        fiber_tract_measurements_cli: Optional[Path] = None,
        clean_files: int = 0,
        execute: bool = False,
    ) -> WMAOrgAtlasResult:
        resolved_output_dir = (
            output_dir
            if output_dir is not None
            else default_task_output_dir_for_dependency(input_tractography, "wma_org_atlas")
        )
        config = WMAOrgAtlasConfig(
            subject_id=subject_id,
            input_tractography=input_tractography,
            atlas_dir=atlas_dir,
            output_dir=resolved_output_dir,
            slicer_executable=slicer_executable,
            wma_root=wma_root,
            transform_path=transform_path,
            registration_mode=registration_mode,
            num_threads=num_threads,
            use_virtual_x=use_virtual_x,
            export_diffusion_measures=export_diffusion_measures,
            fiber_tract_measurements_cli=fiber_tract_measurements_cli,
            clean_files=clean_files,
            execute=execute,
        )
        return run_wma_org_atlas(config, log=self.log)

    def runTractCloudParcellationPipeline(
        self,
        *,
        subject_id: str,
        input_tractography: Path,
        output_dir: Optional[Path] = None,
        python_executable: Optional[Path] = None,
        include_other: bool = False,
        device: str = "auto",
        batch_size: int = 2048,
        data_dir: Optional[Path] = None,
        create_mrb: bool = False,
        execute: bool = False,
    ) -> TractCloudResult:
        resolved_output_dir = (
            output_dir
            if output_dir is not None
            else default_task_output_dir_for_dependency(input_tractography, "tractcloud")
        )
        config = TractCloudConfig(
            subject_id=subject_id,
            input_tractography=input_tractography,
            output_dir=resolved_output_dir,
            python_executable=python_executable,
            include_other=include_other,
            device=device,
            batch_size=batch_size,
            data_dir=data_dir,
            create_mrb=create_mrb,
            execute=execute,
        )
        return run_tractcloud_parcellation(config, log=self.log)

    def runBundleParcellationPipeline(
        self,
        *,
        config: BundleParcellationConfig,
    ) -> BundleParcellationResult:
        return run_bundle_parcellation(config, log=self.log)
