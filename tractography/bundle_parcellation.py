"""Unified bundle parcellation facade for tractography backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional, Union

from tractography.tractcloud import TractCloudConfig, TractCloudResult, run_tractcloud_parcellation
from tractography.wma import WMAOrgAtlasConfig, WMAOrgAtlasResult, run_wma_org_atlas
from tractography.wmql import WMQLConfig, WMQLResult, run_wmql_bundle_segmentation


BundleParcellationBackend = Literal["wma", "tractcloud", "wmql"]
BundleParcellationResult = Union[WMAOrgAtlasResult, TractCloudResult, WMQLResult]


@dataclass(frozen=True)
class BundleParcellationConfig:
    """Select exactly one supported bundle parcellation backend."""

    backend: BundleParcellationBackend
    wma: Optional[WMAOrgAtlasConfig] = None
    tractcloud: Optional[TractCloudConfig] = None
    wmql: Optional[WMQLConfig] = None


def run_bundle_parcellation(
    config: BundleParcellationConfig,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> BundleParcellationResult:
    """Run or prepare a bundle parcellation job with the selected backend."""

    if config.backend == "wma":
        if config.wma is None or config.tractcloud is not None or config.wmql is not None:
            raise ValueError("backend='wma' requires only the wma config.")
        return run_wma_org_atlas(config.wma, log=log)
    if config.backend == "tractcloud":
        if config.tractcloud is None or config.wma is not None or config.wmql is not None:
            raise ValueError("backend='tractcloud' requires only the tractcloud config.")
        return run_tractcloud_parcellation(config.tractcloud, log=log)
    if config.backend == "wmql":
        if config.wmql is None or config.wma is not None or config.tractcloud is not None:
            raise ValueError("backend='wmql' requires only the wmql config.")
        return run_wmql_bundle_segmentation(config.wmql, log=log)
    raise ValueError(f"Unsupported bundle parcellation backend: {config.backend}")
