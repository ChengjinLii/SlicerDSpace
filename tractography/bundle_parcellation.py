"""Unified bundle parcellation facade for tractography backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional, Union

from tractography.tractcloud import TractCloudConfig, TractCloudResult, run_tractcloud_parcellation
from tractography.wma import WMAOrgAtlasConfig, WMAOrgAtlasResult, run_wma_org_atlas


BundleParcellationBackend = Literal["wma", "tractcloud"]
BundleParcellationResult = Union[WMAOrgAtlasResult, TractCloudResult]


@dataclass(frozen=True)
class BundleParcellationConfig:
    """Select exactly one supported bundle parcellation backend."""

    backend: BundleParcellationBackend
    wma: Optional[WMAOrgAtlasConfig] = None
    tractcloud: Optional[TractCloudConfig] = None


def run_bundle_parcellation(
    config: BundleParcellationConfig,
    *,
    log: Optional[Callable[[str], None]] = None,
) -> BundleParcellationResult:
    """Run or prepare a bundle parcellation job with the selected backend."""

    if config.backend == "wma":
        if config.wma is None or config.tractcloud is not None:
            raise ValueError("backend='wma' requires only the wma config.")
        return run_wma_org_atlas(config.wma, log=log)
    if config.backend == "tractcloud":
        if config.tractcloud is None or config.wma is not None:
            raise ValueError("backend='tractcloud' requires only the tractcloud config.")
        return run_tractcloud_parcellation(config.tractcloud, log=log)
    raise ValueError(f"Unsupported bundle parcellation backend: {config.backend}")
