"""Product-level workflow catalog for the SlicerDDSurfer extension.

This shared catalog keeps workflow taxonomy and navigation metadata in one
place while implementation code lives under product packages.
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
        package="anatomy.surface",
        status="implemented",
        navigation_label="Surface (DDSurfer)",
        navigation_target="LOCAL_DDSURFER",
    ),
    WorkflowArea(
        key="parcellation",
        title="Parcellation",
        summary="DDParcel 101-region parcellation built on shared diffusion features.",
        package="anatomy.parcellation",
        status="implemented",
        navigation_label="Parcellation (DDParcel)",
        navigation_target="DDParcel",
    ),
    WorkflowArea(
        key="segmentation",
        title="Segmentation",
        summary="DDSeg WM/GM/CSF segmentation from DWI or cached DTI features.",
        package="anatomy.segmentation",
        status="implemented",
        navigation_label="Segmentation (DDSeg)",
        navigation_target="DDSeg",
    ),
    WorkflowArea(
        key="microstructure",
        title="Microstructure",
        summary="Default DTI, optional Free Water, AMICO NODDI, guarded DKI and native Python MK-Curve.",
        package="microstructure",
        status="implemented",
        navigation_label="Microstructure",
        navigation_target="LOCAL_MICROSTRUCTURE",
    ),
    WorkflowArea(
        key="tractography",
        title="Tractography",
        summary="DTI and CSD/ACT tracking, SAF extraction, and WMQL/WMA/TractCloud bundle parcellation.",
        package="tractography",
        status="implemented",
    ),
    WorkflowArea(
        key="connectome",
        title="Connectome",
        summary="Python and MRtrix connectomes with parcel nodes and scalar, length, or SIFT2 edge weights.",
        package="connectome",
        status="implemented",
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
