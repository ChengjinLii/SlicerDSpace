"""Slicer facade for the manifest-configured, unchanged DDSurfer backend."""
from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from shared import find_subject_root, inspect_subject_directory
from shared.model_assets import model_asset_candidates
from .backend_bridge import BACKEND_ROOT, native_products, run_backend, runtime_info, sha256, upstream_record

ATLAS_NAME = '100HCP-population-mean-T2-1mm.nii.gz'


@dataclass(frozen=True)
class SurfaceConfig:
    subject_id: str
    subject_root: Path
    output_dir: Path
    predict_mode: str = 'all'
    device: str = 'cpu'
    template_dir: Optional[Path] = None
    checkpoint_root: Optional[Path] = None
    registration_atlas: Optional[Path] = None
    model_assets_dir: Optional[Path] = None
    cleanup_intermediates: bool = False
    execute: bool = False
    input_bundle: Optional[object] = None
    precision: str = 'auto'
    python_bin: Optional[Path] = None
    slicer_home: Optional[Path] = None


@dataclass(frozen=True)
class SurfaceResult:
    subject_id: str
    output_dir: Path
    manifest_path: Path
    qc_path: Path
    generated_models: tuple[Path, ...]
    executed: bool


def _resolve_resource(explicit, env_key, relative, required_child=None, model_assets_dir=None):
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    if os.environ.get(env_key):
        return Path(os.environ[env_key]).expanduser().resolve()
    candidates = model_asset_candidates(relative, repo_root=Path(__file__).resolve().parents[1],
                                        explicit_root=model_assets_dir)
    for candidate in candidates:
        if (candidate / required_child if required_child else candidate).exists():
            return candidate.resolve()
    return None


def resolve_surface_template_dir(template_dir=None, *, model_assets_dir=None):
    return _resolve_resource(template_dir, 'DDSURFER_TEMPLATE_DIR', 'surface/template',
                             'ddsurfer_lh_template.obj', model_assets_dir)


def resolve_surface_checkpoint_root(checkpoint_root=None, *, model_assets_dir=None):
    return _resolve_resource(checkpoint_root, 'DDSURFER_CHECKPOINT_DIR', 'surface/weights',
                             'manifest.json', model_assets_dir)


def resolve_surface_registration_atlas(registration_atlas=None, *, model_assets_dir=None):
    return _resolve_resource(registration_atlas, 'DDSURFER_REGISTRATION_ATLAS',
                             f'surface/template/{ATLAS_NAME}', model_assets_dir=model_assets_dir)


def inspect_surface_resources(config: SurfaceConfig) -> dict:
    template = resolve_surface_template_dir(config.template_dir, model_assets_dir=config.model_assets_dir)
    weights = resolve_surface_checkpoint_root(config.checkpoint_root, model_assets_dir=config.model_assets_dir)
    atlas = resolve_surface_registration_atlas(config.registration_atlas, model_assets_dir=config.model_assets_dir)
    missing, errors = [], []
    model_config = None
    if weights is None:
        missing.append('surface/weights/manifest.json')
    if template is None:
        missing.append('surface/template/ddsurfer_lh_template.obj')
    if atlas is None or not atlas.is_file():
        missing.append(f'surface/template/{ATLAS_NAME}')
    if weights is not None and template is not None:
        try:
            model_config = json.loads((weights / 'manifest.json').read_text())
            expected_assets = json.loads((Path(__file__).resolve().parents[1] / 'models/assets_manifest.json').read_text())['asset_records']
            for filename in ('manifest.json', 'SHA256SUMS'):
                path = weights / filename
                if sha256(path) != expected_assets[f'surface/weights/{filename}']['sha256']:
                    raise ValueError(f'Model release metadata mismatch: {path}')
            checksums = {}
            for line in (weights / 'SHA256SUMS').read_text().splitlines():
                if line.strip():
                    digest, filename = line.split(maxsplit=1)
                    filename = filename.lstrip('*')
                    if Path(filename).name != filename or filename in checksums:
                        raise ValueError('Invalid checkpoint checksum entry')
                    checksums[filename] = digest
            for hemi in ('left', 'right'):
                entry = model_config['templates'][hemi]
                if Path(entry['file']).name != entry['file']:
                    raise ValueError('Invalid template filename')
                paths = [(template / entry['file'], entry['sha256'])]
                for kind in ('white', 'pial') if config.predict_mode == 'all' else ('white',):
                    filename = model_config['checkpoint_files'][hemi][kind]
                    if Path(filename).name != filename:
                        raise ValueError('Invalid checkpoint filename')
                    paths.append((weights / filename, checksums[filename]))
                for path, digest in paths:
                    if not path.is_file():
                        missing.append(str(path))
                    elif sha256(path) != digest:
                        errors.append(f'Checksum mismatch: {path}')
            if atlas is not None and atlas.is_file():
                expected = expected_assets[f'surface/template/{ATLAS_NAME}']['sha256']
                if sha256(atlas) != expected:
                    errors.append('DDSurfer requires the matching trained 1-mm atlas; the DDParcel atlas is not interchangeable')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(str(exc))
    return dict(available=not missing and not errors, missing=missing + errors,
                template_dir=str(template) if template else None,
                checkpoint_root=str(weights) if weights else None,
                registration_atlas=str(atlas) if atlas else None,
                upstream_commit=upstream_record()['commit'], model_config=model_config)


def _raw_command(config, resources, output_dir):
    bundle = config.input_bundle or find_subject_root(config.subject_root, config.subject_id)
    command = [BACKEND_ROOT / 'run_ddsurfer_pipeline.py', '--subject', config.subject_id,
               '--output-root', output_dir / 'upstream', '--predict-mode', config.predict_mode,
               '--device', config.device, '--precision', config.precision,
               '--checkpoint-root', resources['checkpoint_root'], '--template-dir', resources['template_dir']]
    for flag, attribute in (('dwi', 'dwi_path'), ('bval', 'bval_path'), ('bvec', 'bvec_path'), ('mask', 'mask_path')):
        path = getattr(bundle, attribute)
        if path is None or not Path(path).is_file():
            raise FileNotFoundError(f'DDSurfer requires a prepared {flag}; run input preparation first')
        command.extend([f'--{flag}', path])
    if not config.cleanup_intermediates:
        command.append('--keep-cache')
    home = config.slicer_home or os.environ.get('DTI_SLICER_PATH') or os.environ.get('SLICER_HOME')
    if home is None:
        from shared.pipeline import resolve_launcher_executable
        home = Path(resolve_launcher_executable()).parent
    return command, dict(DTI_SLICER_PATH=str(home), DTI_REFERENCE_IMAGE=resources['registration_atlas'])


def _run_registered(config, resources, output_dir, subject_dir):
    from .preprocessing import SubjectPreprocessingConfig, preprocess_subject
    from .prediction import PredictionStageConfig, predict_subject
    metrics = {name: subject_dir / f'{config.subject_id}-dti-{name}-Reg.nii.gz' for name in
               ('FractionalAnisotropy', 'MinEigenvalue', 'MidEigenvalue', 'MaxEigenvalue', 'MeanDiffusivity')}
    prepared = preprocess_subject(SubjectPreprocessingConfig(config.subject_id, metrics,
        subject_dir / f'{config.subject_id}-mask-Reg.nii.gz',
        subject_dir / f'{config.subject_id}-b0ToAtlasT2.tfm', output_dir,
        Path(resources['registration_atlas']), python_bin=config.python_bin))
    for hemi in ('left', 'right'):
        predict_subject(PredictionStageConfig(config.subject_id, hemi, config.predict_mode,
            config.device, 0.02, 2, 3, Path(resources['template_dir']), Path(resources['checkpoint_root']),
            prepared.preprocessed_dir.parent, output_dir / 'pred_results_SlicerDDSurfer',
            precision=config.precision, python_bin=config.python_bin))
    run_backend([BACKEND_ROOT / 'inference/native.py', '--subject', config.subject_id,
        '--data-root', prepared.preprocessed_dir.parent, '--pred-root', output_dir / 'pred_results_SlicerDDSurfer',
        '--predict-mode', config.predict_mode, '--output-dir',
        output_dir / 'pred_results_SlicerDDSurfer/native' / config.subject_id], python_bin=config.python_bin)
    if config.cleanup_intermediates:
        for path in (prepared.raw_dir, prepared.preprocessed_dir,
                     output_dir / 'pred_results_SlicerDDSurfer/mni' / config.subject_id):
            shutil.rmtree(path, ignore_errors=True)


def run_surface(config: SurfaceConfig, *, log: Optional[Callable[[str], None]] = None) -> SurfaceResult:
    if not config.subject_id.strip() or Path(config.subject_id).name != config.subject_id or config.subject_id in ('.', '..', 'fsaverage'):
        raise ValueError('subject_id must be a nonempty directory name')
    if config.predict_mode not in ('all', 'wm') or config.precision not in ('auto', 'bf16', 'fp32'):
        raise ValueError('Invalid prediction mode or precision')
    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path, qc_path = output_dir / 'surface_manifest.json', output_dir / 'surface_qc.json'
    resources = inspect_surface_resources(config)
    manifest = dict(kind='ddsurfer_surface', version=2, subject_id=config.subject_id,
        subject_root=str(config.subject_root.expanduser().resolve()), output_dir=str(output_dir),
        input_dwi=str(config.input_bundle.dwi_path) if config.input_bundle is not None else None,
        predict_mode=config.predict_mode, device=config.device, precision=config.precision,
        upstream_commit=resources['upstream_commit'], resources=resources,
        executed=config.execute, status='planned', outputs={})
    qc = dict(subject_id=config.subject_id, status='planned', executed=False, model_count=0,
              elapsed_seconds=0., error=None, human_review='pending')
    products = []
    started, failure = time.monotonic(), None
    try:
        if config.execute:
            if not resources['available']:
                raise FileNotFoundError('DDSurfer resources invalid: ' + ', '.join(resources['missing']))
            manifest['status'] = 'running'
            manifest['runtime'] = runtime_info(config.python_bin)
            manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
            inspected = inspect_subject_directory(config.subject_root, config.subject_id)
            if inspected['mode'] == 'missing':
                for candidate in (config.subject_root, config.subject_root / config.subject_id):
                    required = [candidate / f'{config.subject_id}-dti-{name}-Reg.nii.gz' for name in
                                ('FractionalAnisotropy', 'MinEigenvalue', 'MidEigenvalue', 'MaxEigenvalue', 'MeanDiffusivity')]
                    required += [candidate / f'{config.subject_id}-mask-Reg.nii.gz', candidate / f'{config.subject_id}-b0ToAtlasT2.tfm']
                    if all(p.is_file() for p in required):
                        inspected = dict(mode='legacy_registered', subject_dir=str(candidate))
                        break
            native_dir = output_dir / 'pred_results_SlicerDDSurfer/native' / config.subject_id
            if config.input_bundle is not None or inspected['mode'] == 'subject_root':
                command, env = _raw_command(config, resources, output_dir)
                run_backend(command, python_bin=config.python_bin, env=env, log=log,
                            log_path=output_dir / 'backend.log')
                upstream = output_dir / 'upstream' / config.subject_id
                native_dir.mkdir(parents=True, exist_ok=True)
                for hemi in ('lh', 'rh'):
                    for kind in ('white', 'pial') if config.predict_mode == 'all' else ('white',):
                        shutil.copy2(upstream / 'ddsurfer' / f'{hemi}.{kind}.obj', native_dir / f'{hemi}.{kind}.obj')
                manifest['upstream_pipeline'] = json.loads((upstream / 'logs/pipeline.json').read_text())
                manifest['outputs']['native_dti'] = str(upstream / 'dti')
            elif inspected['mode'] != 'missing':
                _run_registered(config, resources, output_dir, Path(inspected['subject_dir']))
            else:
                raise FileNotFoundError(f'No DDSurfer subject input: {config.subject_root}')
            products, checks = native_products(native_dir, config.subject_id, config.predict_mode)
            qc.update(status='completed', executed=True, model_count=len(products), surfaces=checks,
                      automatic_qc_passed=all(c['finite'] and c['watertight'] and c['euler_number'] == 2 for c in checks.values()))
            manifest['outputs']['models'] = list(map(str, products))
            manifest['outputs']['indexed_RAS_models'] = [c['indexed_master'] for c in checks.values()]
            manifest['status'] = 'completed'
    except Exception as exc:
        failure = exc
        manifest['status'] = 'failed'
        qc.update(status='failed', executed=config.execute, error=str(exc), automatic_qc_passed=False)
    finally:
        qc['elapsed_seconds'] = time.monotonic() - started
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        qc_path.write_text(json.dumps(qc, indent=2) + '\n', encoding='utf-8')
    if failure is not None:
        raise RuntimeError(f'DDSurfer surface execution failed: {failure}') from failure
    if log:
        log(f'[Surface] Manifest: {manifest_path}')
    return SurfaceResult(config.subject_id, output_dir, manifest_path, qc_path, tuple(products), config.execute)
