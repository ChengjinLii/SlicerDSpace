"""Tractography pipeline entrypoints."""

from __future__ import annotations

from tractography.act import ACTTrackingConfig, ACTTrackingResult, run_act_tracking
from tractography.bundle_parcellation import (
    BundleParcellationConfig,
    BundleParcellationResult,
    run_bundle_parcellation,
)
from tractography.dti import DTITrackingConfig, DTITrackingResult, run_dti_tracking
from tractography.tractcloud import TractCloudConfig, TractCloudResult, run_tractcloud_parcellation
from tractography.wma import WMAOrgAtlasConfig, WMAOrgAtlasResult, run_wma_org_atlas


TractographyWMAConfig = WMAOrgAtlasConfig
TractographyWMAResult = WMAOrgAtlasResult
TractographyTractCloudConfig = TractCloudConfig
TractographyTractCloudResult = TractCloudResult
TractographyBundleParcellationConfig = BundleParcellationConfig
TractographyBundleParcellationResult = BundleParcellationResult
TractographyDTIConfig = DTITrackingConfig
TractographyDTIResult = DTITrackingResult
TractographyACTConfig = ACTTrackingConfig
TractographyACTResult = ACTTrackingResult


def run_wma_org_atlas_pipeline(config: TractographyWMAConfig, *, log=None) -> TractographyWMAResult:
    """Run or prepare WMA ORG atlas clustering."""

    return run_wma_org_atlas(config, log=log)


def run_tractcloud_parcellation_pipeline(
    config: TractographyTractCloudConfig, *, log=None
) -> TractographyTractCloudResult:
    """Run or prepare TractCloud parcellation."""

    return run_tractcloud_parcellation(config, log=log)


def run_bundle_parcellation_pipeline(
    config: TractographyBundleParcellationConfig, *, log=None
) -> TractographyBundleParcellationResult:
    """Run or prepare bundle parcellation with WMA or TractCloud."""

    return run_bundle_parcellation(config, log=log)


__all__ = [
    "TractographyWMAConfig",
    "TractographyWMAResult",
    "TractographyTractCloudConfig",
    "TractographyTractCloudResult",
    "TractographyBundleParcellationConfig",
    "TractographyBundleParcellationResult",
    "TractographyDTIConfig",
    "TractographyDTIResult",
    "TractographyACTConfig",
    "TractographyACTResult",
    "run_act_tracking",
    "run_bundle_parcellation_pipeline",
    "run_dti_tracking",
    "run_tractcloud_parcellation_pipeline",
    "run_wma_org_atlas_pipeline",
]
