"""Tractography pipeline entrypoints."""

from __future__ import annotations

from tractography.act import ACTTrackingConfig, ACTTrackingResult, run_act_tracking
from tractography.act_prep import ACTPrepConfig, ACTPrepResult, run_act_prep
from tractography.bundle_parcellation import (
    BundleParcellationConfig,
    BundleParcellationResult,
    run_bundle_parcellation,
)
from tractography.csd import CSDActConfig, CSDActResult, run_csd_act
from tractography.dti import DTITrackingConfig, DTITrackingResult, run_dti_tracking
from tractography.saf import SAFConfig, SAFResult, run_saf
from tractography.tractcloud import TractCloudConfig, TractCloudResult, run_tractcloud_parcellation
from tractography.wma import WMAOrgAtlasConfig, WMAOrgAtlasResult, run_wma_org_atlas
from tractography.wmql import WMQLConfig, WMQLResult, run_wmql_bundle_segmentation


TractographyWMAConfig = WMAOrgAtlasConfig
TractographyWMAResult = WMAOrgAtlasResult
TractographyTractCloudConfig = TractCloudConfig
TractographyTractCloudResult = TractCloudResult
TractographyWMQLConfig = WMQLConfig
TractographyWMQLResult = WMQLResult
TractographyBundleParcellationConfig = BundleParcellationConfig
TractographyBundleParcellationResult = BundleParcellationResult
TractographyDTIConfig = DTITrackingConfig
TractographyDTIResult = DTITrackingResult
TractographyCSDActConfig = CSDActConfig
TractographyCSDActResult = CSDActResult
TractographySAFConfig = SAFConfig
TractographySAFResult = SAFResult
TractographyACTConfig = ACTTrackingConfig
TractographyACTResult = ACTTrackingResult
TractographyACTPrepConfig = ACTPrepConfig
TractographyACTPrepResult = ACTPrepResult


def run_wma_org_atlas_pipeline(config: TractographyWMAConfig, *, log=None) -> TractographyWMAResult:
    """Run or prepare WMA ORG atlas clustering."""

    return run_wma_org_atlas(config, log=log)


def run_tractcloud_parcellation_pipeline(
    config: TractographyTractCloudConfig, *, log=None
) -> TractographyTractCloudResult:
    """Run or prepare TractCloud parcellation."""

    return run_tractcloud_parcellation(config, log=log)


def run_wmql_bundle_segmentation_pipeline(config: TractographyWMQLConfig, *, log=None) -> TractographyWMQLResult:
    """Run or prepare WMQL bundle segmentation."""

    return run_wmql_bundle_segmentation(config, log=log)


def run_bundle_parcellation_pipeline(
    config: TractographyBundleParcellationConfig, *, log=None
) -> TractographyBundleParcellationResult:
    """Run or prepare bundle parcellation with WMA or TractCloud."""

    return run_bundle_parcellation(config, log=log)


def run_saf_pipeline(config: TractographySAFConfig, *, log=None) -> TractographySAFResult:
    """Run or prepare Python SAF short association fibre extraction."""

    return run_saf(config, log=log)


def run_act_prep_pipeline(config: TractographyACTPrepConfig, *, log=None) -> TractographyACTPrepResult:
    """Run or prepare simple 5TT/GMWMI generation from tissue labels."""

    return run_act_prep(config, log=log)


def run_csd_act_pipeline(config: TractographyCSDActConfig, *, log=None) -> TractographyCSDActResult:
    """Run or prepare the external MRtrix3 CSD/FOD/ACT command chain."""

    return run_csd_act(config, log=log)


__all__ = [
    "TractographyWMAConfig",
    "TractographyWMAResult",
    "TractographyTractCloudConfig",
    "TractographyTractCloudResult",
    "TractographyWMQLConfig",
    "TractographyWMQLResult",
    "TractographyBundleParcellationConfig",
    "TractographyBundleParcellationResult",
    "TractographyDTIConfig",
    "TractographyDTIResult",
    "TractographyCSDActConfig",
    "TractographyCSDActResult",
    "TractographyACTConfig",
    "TractographyACTResult",
    "TractographyACTPrepConfig",
    "TractographyACTPrepResult",
    "TractographySAFConfig",
    "TractographySAFResult",
    "run_act_tracking",
    "run_act_prep_pipeline",
    "run_bundle_parcellation_pipeline",
    "run_csd_act_pipeline",
    "run_dti_tracking",
    "run_saf_pipeline",
    "run_tractcloud_parcellation_pipeline",
    "run_wmql_bundle_segmentation_pipeline",
    "run_wma_org_atlas_pipeline",
]
