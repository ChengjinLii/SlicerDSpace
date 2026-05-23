"""Tractography pipeline entrypoints."""

from __future__ import annotations

from tractography.act import ACTTrackingConfig, ACTTrackingResult, run_act_tracking
from tractography.dti import DTITrackingConfig, DTITrackingResult, run_dti_tracking
from tractography.wma import WMAOrgAtlasConfig, WMAOrgAtlasResult, run_wma_org_atlas


TractographyWMAConfig = WMAOrgAtlasConfig
TractographyWMAResult = WMAOrgAtlasResult
TractographyDTIConfig = DTITrackingConfig
TractographyDTIResult = DTITrackingResult
TractographyACTConfig = ACTTrackingConfig
TractographyACTResult = ACTTrackingResult


def run_wma_org_atlas_pipeline(config: TractographyWMAConfig, *, log=None) -> TractographyWMAResult:
    """Run or prepare WMA ORG atlas clustering."""

    return run_wma_org_atlas(config, log=log)


__all__ = [
    "TractographyWMAConfig",
    "TractographyWMAResult",
    "TractographyDTIConfig",
    "TractographyDTIResult",
    "TractographyACTConfig",
    "TractographyACTResult",
    "run_act_tracking",
    "run_dti_tracking",
    "run_wma_org_atlas_pipeline",
]
