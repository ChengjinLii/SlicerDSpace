"""Shared subject-root pipeline helpers for SlicerDDSurfer."""

from .pipeline import (
    RawInputBundle,
    NativeDTIBundle,
    RegisteredDTIBundle,
    ensure_native_dti_bundle,
    ensure_registered_dti_bundle,
    find_subject_root,
    inspect_subject_directory,
    is_raw_subject_root,
    resolve_cli_executable,
    resolve_launcher_executable,
    resolve_pythonslicer_executable,
)
from .validation import InputValidationConfig, InputValidationResult, ValidationIssue, validate_subject_inputs
from .io_layout import (
    SubjectIOLayout,
    archive_development_outputs,
    canonical_connectome_output_dir,
    default_task_output_dir,
    default_task_output_dir_for_dependency,
    materialize_canonical_output_tree,
    normalize_run_name,
    subject_layout,
)
from .orchestrator import ProductOrchestratorConfig, ProductOrchestratorResult, ProductTaskRecord, run_subject_products

__all__ = [
    "InputValidationConfig",
    "InputValidationResult",
    "RawInputBundle",
    "NativeDTIBundle",
    "RegisteredDTIBundle",
    "SubjectIOLayout",
    "archive_development_outputs",
    "canonical_connectome_output_dir",
    "ProductOrchestratorConfig",
    "ProductOrchestratorResult",
    "ProductTaskRecord",
    "ValidationIssue",
    "default_task_output_dir",
    "default_task_output_dir_for_dependency",
    "ensure_native_dti_bundle",
    "ensure_registered_dti_bundle",
    "find_subject_root",
    "inspect_subject_directory",
    "is_raw_subject_root",
    "materialize_canonical_output_tree",
    "normalize_run_name",
    "resolve_cli_executable",
    "resolve_launcher_executable",
    "resolve_pythonslicer_executable",
    "subject_layout",
    "run_subject_products",
    "validate_subject_inputs",
]
