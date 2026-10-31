#!/usr/bin/env python3
"""Install qualified prebuilt surface tools; source compilation is an expert opt-in."""

import argparse
from functools import partial
import json
from pathlib import Path
import platform
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def prepare(*, execute=False, accept_terms=False, prefix=None, asset_root=None, jobs=4,
            cmake=None, source_root=None, work_dir=None, offline=False, build_from_source=False):
    if not build_from_source:
        from shared.prebuilt_surface import prepare as install_prebuilt
        return install_prebuilt(prefix=prefix, asset_root=asset_root, execute=execute,
                                accept_terms=accept_terms, offline=offline)
    from anatomy.surface.backend_bridge import BACKEND_ROOT
    from shared.surface_runtime import default_surface_runtime
    from shared.optional_assets import verified_resource_directory
    from scripts.setup_optional_assets import prepare as prepare_assets

    if platform.system() != 'Linux':
        raise ValueError('Automatic source preparation is validated on Linux only; use a configured platform-native FreeSurfer installation. Native Windows is unsupported; WSL setup is separate.')
    if jobs < 1:
        raise ValueError('Build jobs must be positive')
    prefix = Path(prefix or default_surface_runtime()).expanduser().absolute()
    result = dict(kind='slicerdsurfer_runtime_setup', status='planned', prefix=str(prefix),
                  external_dependencies={}, changes_slicer_python=False,
                  scope='Local source compilation and integrity, not anatomical accuracy')
    if not execute:
        return result
    if not accept_terms:
        raise PermissionError('Explicit acceptance of source/data terms is required before preparing surface components')
    # Fresh process only: keep generic upstream package names out of Slicer.
    sys.path.insert(0, str(BACKEND_ROOT))
    from postprocessing.core import build as upstream
    from postprocessing.core.archive import install_assets
    from postprocessing.core.runtime import validate_runtime
    from postprocessing.core.config import recipe_digest
    if prefix.exists():
        record = validate_runtime(prefix)
        if record.get('recipe_sha256') != recipe_digest():
            raise ValueError('Existing local runtime uses a different recipe; choose a fresh prefix')
        print('[Surface setup] Reusing verified local components', flush=True)
    else:
        package = verified_resource_directory('surface-postprocess', asset_root=asset_root)
        if package is None:
            if offline:
                raise FileNotFoundError('Offline preparation needs the verified surface-postprocess atlas profile')
            prepare_assets(('surface-postprocess',), asset_root=asset_root, execute=True, accept_terms=True)
            package = verified_resource_directory('surface-postprocess', asset_root=asset_root)
        if package is None:
            raise FileNotFoundError('Surface atlas package is unavailable')
        # Only the data location differs: the compiled source and recipe are exact
        # upstream snapshots. Keep the 29-MB archive outside the extension package.
        for name in ('manifest.json', 'LICENSE.txt'):
            source = BACKEND_ROOT / 'postprocessing/assets' / name
            destination = package / name
            if destination.is_symlink():
                raise ValueError('Refusing linked surface data metadata: ' + name)
            if destination.exists() and destination.read_bytes() != source.read_bytes():
                raise ValueError('Existing surface data metadata differs: ' + name)
            if not destination.exists():
                shutil.copyfile(source, destination)
        upstream.install_assets = partial(install_assets, package=package)
        upstream.build(argparse.Namespace(jobs=jobs, prefix=prefix, cmake=cmake, source_root=source_root,
                                          work_dir=work_dir, offline=offline))
    validate_runtime(prefix)
    result.update(status='completed', external_dependencies={'postprocess_runtime': str(prefix)})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--accept-terms', action='store_true')
    parser.add_argument('--prefix', type=Path)
    parser.add_argument('--asset-root', type=Path)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--cmake', type=Path)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--build-from-source', action='store_true',
                        help='Expert opt-in: compile the source instead of using qualified prebuilt components')
    parser.add_argument('--result', type=Path)
    args = parser.parse_args(argv)
    options = vars(args).copy()
    path = options.pop('result')
    try:
        result = prepare(**options)
    except Exception as exc:
        result = dict(kind='slicerdsurfer_runtime_setup', status='failed', error=str(exc))
    if path:
        from shared.managed_runtimes import write_json
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, result)
    print(json.dumps(result, indent=2), flush=True)
    return int(result['status'] == 'failed')


if __name__ == '__main__':
    raise SystemExit(main())
