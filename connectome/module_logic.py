"""Connectome workflow logic glue for SlicerDDSurfer."""

from __future__ import annotations

from pathlib import Path

from connectome.pipeline import ConnectomeConfig, ConnectomeResult, run_connectome


class ConnectomeLogicMixin:
    """Logic entrypoints for connectome-related workflows."""

    def runConnectomePipeline(
        self,
        *,
        subject_id: str,
        tractography_path: Path,
        parcellation_path: Path,
        output_dir: Path,
        metric: str = "streamline_count",
        node_source: str = "ddparcel",
        execute: bool = False,
    ) -> ConnectomeResult:
        config = ConnectomeConfig(
            subject_id=subject_id,
            tractography_path=tractography_path,
            parcellation_path=parcellation_path,
            output_dir=output_dir,
            metric=metric,
            node_source=node_source,
            execute=execute,
        )
        return run_connectome(config, log=self.log)
