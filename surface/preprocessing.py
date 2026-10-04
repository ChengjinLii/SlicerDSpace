"""Prepare registered volumes with the upstream fixed-grid implementation."""
from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Dict, Optional
from .backend_bridge import BACKEND_ROOT, run_backend


@dataclass(frozen=True)
class SubjectPreprocessingConfig:
    subject_id: str
    metric_paths: Dict[str, Path]
    mask_path: Path
    transform_path: Path
    work_dir: Path
    template_volume_path: Path
    python_bin: Optional[Path] = None


@dataclass(frozen=True)
class SubjectPreprocessingResult:
    subject_id: str
    raw_dir: Path
    preprocessed_dir: Path
    resampled_mask_path: Path
    transform_copy_path: Path


def preprocess_subject(config):
    raw = config.work_dir / 'raw' / config.subject_id
    output = config.work_dir / 'preprocessed' / config.subject_id
    raw.mkdir(parents=True, exist_ok=True)
    for name, path in config.metric_paths.items():
        shutil.copy2(path, raw / f'{config.subject_id}-dti-{name}-Reg.nii.gz')
    shutil.copy2(config.mask_path, raw / f'{config.subject_id}-mask-Reg.nii.gz')
    transform_name = f'{config.subject_id}-b0ToAtlasT2.tfm'
    shutil.copy2(config.transform_path, raw / transform_name)
    run_backend([BACKEND_ROOT / 'preprocessing/volumes.py', '--subject', config.subject_id,
                 '--input-dir', raw, '--output-dir', output, '--minimal'], python_bin=config.python_bin)
    return SubjectPreprocessingResult(config.subject_id, raw, output,
        output / f'{config.subject_id}-brainmask_resampled.nii.gz', output / transform_name)
