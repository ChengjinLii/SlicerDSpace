"""Lazy exports for DDParcel conversion helpers."""

from __future__ import annotations

from importlib import import_module

from ._version import __version__

_EXPORTS = {
    "bvec_scaling": (".bval_bvec_io", "bvec_scaling"),
    "grad_avg": (".grad_avg", "grad_avg"),
    "grad_remove": (".grad_remove", "grad_remove"),
    "loadExecutable": (".util", "loadExecutable"),
    "nhdr_write": (".nhdr_write", "nhdr_write"),
    "nifti_write": (".nifti_write", "nifti_write"),
    "nrrd_bvals_bvecs": (".bval_bvec_io", "nrrd_bvals_bvecs"),
    "num2str": (".util", "num2str"),
    "parse_labels": (".fs_label_parser", "parse_labels"),
    "read_bvals": (".bval_bvec_io", "read_bvals"),
    "read_bvecs": (".bval_bvec_io", "read_bvecs"),
    "read_cases": (".util", "read_cases"),
    "read_grad_ind": (".bval_bvec_io", "read_grad_ind"),
    "read_imgs": (".util", "read_imgs"),
    "read_imgs_masks": (".util", "read_imgs_masks"),
    "transpose": (".bval_bvec_io", "transpose"),
    "write_bvals": (".bval_bvec_io", "write_bvals"),
    "write_bvecs": (".bval_bvec_io", "write_bvecs"),
}

__all__ = ["__version__", *_EXPORTS.keys()]


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = _EXPORTS[name]
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value
