"""Product-level workflow catalog for the SlicerDDSurfer extension.

This catalog keeps workflow taxonomy and navigation metadata in one place while
implementation code lives under product packages.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowArea:
    key: str
    title: str
    summary: str
    package: str
    status: str
    navigation_label: str | None = None
    navigation_target: str | None = None


WORKFLOW_AREAS: tuple[WorkflowArea, ...] = (
    WorkflowArea(
        key="surface",
        title="Surface",
        summary="DDSurfer cortical surface reconstruction and native-space mesh export.",
        package="surface",
        status="implemented",
        navigation_label="Surface (DDSurfer)",
        navigation_target="LOCAL_DDSURFER",
    ),
    WorkflowArea(
        key="parcellation",
        title="Parcellation",
        summary="DDParcel 101-region parcellation built on shared diffusion features.",
        package="parcellation",
        status="implemented",
        navigation_label="Parcellation (DDParcel)",
        navigation_target="DDParcel",
    ),
    WorkflowArea(
        key="segmentation",
        title="Segmentation",
        summary="DDSeg WM/GM/CSF segmentation from DWI or cached DTI features.",
        package="segmentation",
        status="implemented",
        navigation_label="Segmentation (DDSeg)",
        navigation_target="DDSeg",
    ),
    WorkflowArea(
        key="microstructure",
        title="Microstructure",
        summary="FA/MD, ROI-wise microstructure, Free Water, and AMICO NODDI.",
        package="microstructure",
        status="implemented",
        navigation_label="Microstructure",
        navigation_target="LOCAL_MICROSTRUCTURE",
    ),
    WorkflowArea(
        key="tractography",
        title="Tractography",
        summary="Diffusion tractography area with DTI tracking and WMA ORG atlas clustering scaffolds; CSD/ACT planned.",
        package="tractography",
        status="partial",
    ),
    WorkflowArea(
        key="connectome",
        title="Connectome",
        summary="Planned connectivity workflow area built on tractography and parcel nodes.",
        package="connectome",
        status="planned",
    ),
)


IMPLEMENTED_WORKFLOW_AREAS: tuple[WorkflowArea, ...] = tuple(
    area for area in WORKFLOW_AREAS if area.status == "implemented"
)


NAVIGATION_WORKFLOW_AREAS: tuple[WorkflowArea, ...] = tuple(
    area
    for area in WORKFLOW_AREAS
    if area.navigation_label is not None and area.navigation_target is not None
)
