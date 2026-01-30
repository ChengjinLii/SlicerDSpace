from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

ParameterType = Literal["DTI"]


@dataclass(frozen=True)
class DDSegConfig:
    input_mask_nii: Path
    parameter_type: ParameterType
    output_folder: Path
    weights_dir: Path
    device: str = "cpu"
    apply_softmax: bool = False
    dwi_nii: Optional[Path] = None
    bval: Optional[Path] = None
    bvec: Optional[Path] = None
    slicer_base: Optional[Path] = None
    slicer_ext: Optional[Path] = None
