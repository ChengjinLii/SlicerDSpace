#!/usr/bin/env python3
"""Package an independently verified native runtime; never include an activation key."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'anatomy/surface/ddsurfer_backend'))


def package(source, destination):
    from postprocessing.core.runtime import validate_runtime
    from postprocessing.core.config import recipe_digest
    source, destination = Path(source).resolve(), Path(destination).resolve()
    manifest = validate_runtime(source)
    if manifest['recipe_sha256'] != recipe_digest():
        raise ValueError('Runtime does not match the current build recipe')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('wb') as output, gzip.GzipFile(fileobj=output, mode='wb', mtime=0, filename='') as compressed:
        with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as archive:
            for name in sorted([*manifest['files'], 'runtime.json']):
                path = source / name
                info = archive.gettarinfo(str(path), arcname=name)
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ''
                with path.open('rb') as stream:
                    archive.addfile(info, stream)
    digest = hashlib.sha256()
    with destination.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    record = dict(kind='slicerdspace_prebuilt_surface_runtime', system=manifest['system'], machine=manifest['machine'],
                  recipe_sha256=manifest['recipe_sha256'], source_revision=manifest['source_revision'],
                  filename=destination.name, sha256=digest.hexdigest(), bytes=destination.stat().st_size,
                  unpacked_bytes=sum(item['bytes'] for item in manifest['files'].values()),
                  activation_key_included=False, files=len(manifest['files']))
    destination.with_suffix(destination.suffix + '.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.source, args.output), indent=2))
