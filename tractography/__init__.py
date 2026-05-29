"""Tractography workflow package for SlicerDDSurfer."""

from __future__ import annotations

from .act import (
    ACTTrackingConfig,
    ACTTrackingResult,
    build_mrtrix_act_commands,
    inspect_mrtrix_backend,
    run_act_tracking,
)
from .dti import DTITrackingConfig, DTITrackingResult, run_dti_tracking
from .bundle_parcellation import (
    BundleParcellationConfig,
    BundleParcellationResult,
    run_bundle_parcellation,
)
from .tractcloud import (
    TractCloudConfig,
    TractCloudResult,
    build_tractcloud_command,
    inspect_tractcloud_backend,
    resolve_tractcloud_python,
    run_tractcloud_parcellation,
)
from .wma import (
    WMAOrgAtlasConfig,
    WMAOrgAtlasResult,
    build_wma_org_atlas_command,
    inspect_wma_backend,
    inspect_wma_org_atlas,
    resolve_wma_root,
    run_wma_org_atlas,
)
from .pipeline import (
    TractographyACTConfig,
    TractographyACTResult,
    TractographyBundleParcellationConfig,
    TractographyBundleParcellationResult,
    TractographyDTIConfig,
    TractographyDTIResult,
    TractographyTractCloudConfig,
    TractographyTractCloudResult,
    TractographyWMAConfig,
    TractographyWMAResult,
    run_bundle_parcellation_pipeline,
    run_tractcloud_parcellation_pipeline,
    run_wma_org_atlas_pipeline,
)

PLANNED_WORKFLOWS: tuple[str, ...] = (
    "DTI tractography",
    "CSD tractography",
    "ACT",
    "WMA ORG atlas clustering",
    "TractCloud parcellation",
    "Additional candidate methods",
)

__all__ = [
    "PLANNED_WORKFLOWS",
    "ACTTrackingConfig",
    "ACTTrackingResult",
    "WMAOrgAtlasConfig",
    "WMAOrgAtlasResult",
    "TractCloudConfig",
    "TractCloudResult",
    "BundleParcellationConfig",
    "BundleParcellationResult",
    "DTITrackingConfig",
    "DTITrackingResult",
    "TractographyWMAConfig",
    "TractographyWMAResult",
    "TractographyTractCloudConfig",
    "TractographyTractCloudResult",
    "TractographyBundleParcellationConfig",
    "TractographyBundleParcellationResult",
    "TractographyACTConfig",
    "TractographyACTResult",
    "TractographyDTIConfig",
    "TractographyDTIResult",
    "build_mrtrix_act_commands",
    "build_tractcloud_command",
    "build_wma_org_atlas_command",
    "inspect_mrtrix_backend",
    "inspect_tractcloud_backend",
    "inspect_wma_backend",
    "inspect_wma_org_atlas",
    "resolve_tractcloud_python",
    "resolve_wma_root",
    "run_act_tracking",
    "run_bundle_parcellation",
    "run_bundle_parcellation_pipeline",
    "run_dti_tracking",
    "run_tractcloud_parcellation",
    "run_tractcloud_parcellation_pipeline",
    "run_wma_org_atlas",
    "run_wma_org_atlas_pipeline",
]
