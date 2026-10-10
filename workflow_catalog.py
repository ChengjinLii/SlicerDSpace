"""Compatibility imports; workflow metadata lives in shared.workflow_catalog."""

from shared.workflow_catalog import (
    IMPLEMENTED_WORKFLOW_AREAS,
    NAVIGATION_WORKFLOW_AREAS,
    WORKFLOW_AREAS,
    WorkflowArea,
)

__all__ = [
    "WorkflowArea",
    "WORKFLOW_AREAS",
    "IMPLEMENTED_WORKFLOW_AREAS",
    "NAVIGATION_WORKFLOW_AREAS",
]
