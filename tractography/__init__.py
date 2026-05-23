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
    TractographyDTIConfig,
    TractographyDTIResult,
    TractographyWMAConfig,
    TractographyWMAResult,
    run_wma_org_atlas_pipeline,
)

PLANNED_WORKFLOWS: tuple[str, ...] = (
    "DTI tractography",
    "CSD tractography",
    "ACT",
    "WMA ORG atlas clustering",
    "Additional candidate methods",
)

__all__ = [
    "PLANNED_WORKFLOWS",
    "ACTTrackingConfig",
    "ACTTrackingResult",
    "WMAOrgAtlasConfig",
    "WMAOrgAtlasResult",
    "DTITrackingConfig",
    "DTITrackingResult",
    "TractographyWMAConfig",
    "TractographyWMAResult",
    "TractographyACTConfig",
    "TractographyACTResult",
    "TractographyDTIConfig",
    "TractographyDTIResult",
    "build_mrtrix_act_commands",
    "build_wma_org_atlas_command",
    "inspect_mrtrix_backend",
    "inspect_wma_backend",
    "inspect_wma_org_atlas",
    "resolve_wma_root",
    "run_act_tracking",
    "run_dti_tracking",
    "run_wma_org_atlas",
    "run_wma_org_atlas_pipeline",
]
