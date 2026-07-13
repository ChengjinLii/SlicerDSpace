"""Tractography workflow package for SlicerDDSurfer."""

from __future__ import annotations

from .act import (
    ACTTrackingConfig,
    ACTTrackingResult,
    build_mrtrix_act_commands,
    inspect_mrtrix_backend,
    run_act_tracking,
)
from .act_prep import ACTPrepConfig, ACTPrepResult, run_act_prep
from .csd import CSDActConfig, CSDActResult, inspect_mrtrix_csd_backend, run_csd_act
from .dti import DTITrackingConfig, DTITrackingResult, run_dti_tracking
from .saf import SAFConfig, SAFResult, bundled_saf_backend_dir, inspect_saf_backend, run_saf
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
from .wmql import (
    WMQLConfig,
    WMQLResult,
    build_wmql_command,
    bundled_wmql_query_path,
    inspect_wmql_backend,
    run_wmql_bundle_segmentation,
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
    TractographyCSDActConfig,
    TractographyCSDActResult,
    TractographyDTIConfig,
    TractographyDTIResult,
    TractographySAFConfig,
    TractographySAFResult,
    TractographyTractCloudConfig,
    TractographyTractCloudResult,
    TractographyWMAConfig,
    TractographyWMAResult,
    TractographyWMQLConfig,
    TractographyWMQLResult,
    run_bundle_parcellation_pipeline,
    run_csd_act_pipeline,
    run_tractcloud_parcellation_pipeline,
    run_wmql_bundle_segmentation_pipeline,
    run_saf_pipeline,
    run_wma_org_atlas_pipeline,
)

SUPPORTED_WORKFLOWS: tuple[str, ...] = (
    "DTI tractography",
    "CSD/ACT tractography",
    "SAF short association fibres",
    "WMA ORG atlas clustering",
    "TractCloud parcellation",
    "WMQL AF/CST bundle segmentation",
)

# Compatibility alias for callers written before these workflows became
# executable.  New code should use SUPPORTED_WORKFLOWS.
PLANNED_WORKFLOWS = SUPPORTED_WORKFLOWS

__all__ = [
    "PLANNED_WORKFLOWS",
    "SUPPORTED_WORKFLOWS",
    "ACTTrackingConfig",
    "ACTTrackingResult",
    "ACTPrepConfig",
    "ACTPrepResult",
    "WMAOrgAtlasConfig",
    "WMAOrgAtlasResult",
    "TractCloudConfig",
    "TractCloudResult",
    "WMQLConfig",
    "WMQLResult",
    "BundleParcellationConfig",
    "BundleParcellationResult",
    "DTITrackingConfig",
    "DTITrackingResult",
    "SAFConfig",
    "SAFResult",
    "TractographyWMAConfig",
    "TractographyWMAResult",
    "TractographyTractCloudConfig",
    "TractographyTractCloudResult",
    "TractographyWMQLConfig",
    "TractographyWMQLResult",
    "TractographyBundleParcellationConfig",
    "TractographyBundleParcellationResult",
    "TractographyCSDActConfig",
    "TractographyCSDActResult",
    "TractographyACTConfig",
    "TractographyACTResult",
    "TractographyDTIConfig",
    "TractographyDTIResult",
    "TractographySAFConfig",
    "TractographySAFResult",
    "build_mrtrix_act_commands",
    "build_tractcloud_command",
    "build_wmql_command",
    "build_wma_org_atlas_command",
    "inspect_mrtrix_backend",
    "inspect_mrtrix_csd_backend",
    "inspect_saf_backend",
    "inspect_tractcloud_backend",
    "inspect_wmql_backend",
    "inspect_wma_backend",
    "inspect_wma_org_atlas",
    "resolve_tractcloud_python",
    "resolve_wma_root",
    "bundled_saf_backend_dir",
    "bundled_wmql_query_path",
    "run_act_tracking",
    "run_act_prep",
    "run_bundle_parcellation",
    "run_bundle_parcellation_pipeline",
    "run_csd_act",
    "run_csd_act_pipeline",
    "run_dti_tracking",
    "run_saf",
    "run_saf_pipeline",
    "run_tractcloud_parcellation",
    "run_tractcloud_parcellation_pipeline",
    "run_wmql_bundle_segmentation",
    "run_wmql_bundle_segmentation_pipeline",
    "run_wma_org_atlas",
    "run_wma_org_atlas_pipeline",
]
