"""CUDA device-index helpers that do not import PyTorch."""

from __future__ import annotations

import os
from typing import Optional


def logical_cuda_index(requested_gpu: str, visible_devices: Optional[str] = None) -> int:
    """Map a requested physical GPU ID into the current visible-device index."""

    requested = str(requested_gpu).split(",", 1)[0].strip()
    if not requested or requested == "-1":
        return 0
    visible = visible_devices if visible_devices is not None else os.environ.get("CUDA_VISIBLE_DEVICES")
    if visible:
        visible_ids = [value.strip() for value in str(visible).split(",") if value.strip()]
        if requested in visible_ids:
            return visible_ids.index(requested)
    return int(requested)


__all__ = ["logical_cuda_index"]
