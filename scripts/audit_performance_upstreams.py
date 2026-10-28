#!/usr/bin/env python3
"""Snapshot official release/head metadata and relevant source fingerprints.

Network access is explicit. The audit neither installs packages nor turns source
identity into a runtime speed claim. Historical measurements are not rewritten.
"""

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import pickletools
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def source_functions(source, names):
    lines = source.splitlines(keepends=True)
    records = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            first = min([node.lineno] + [part.lineno for part in node.decorator_list])
            body = ''.join(lines[first - 1:node.end_lineno])
            records[node.name] = hashlib.sha256(body.encode()).hexdigest()
    if records.keys() != set(names):
        raise ValueError('Requested source definitions were not all found')
    return records


def amico_config_version(path):
    # Inspect pickle opcodes only; never execute a data file via pickle.load.
    operations = list(pickletools.genops(path.read_bytes()))
    for index, (_, value, _) in enumerate(operations):
        if value == 'version':
            for _, candidate, _ in operations[index + 1:]:
                if isinstance(candidate, str):
                    if not candidate or not all(part.isdigit() for part in candidate.split('.')):
                        raise ValueError('Invalid AMICO version in recorded configuration')
                    return dict(version=candidate, filename=path.name,
                                sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    raise ValueError('No AMICO version in recorded configuration')


def fetch(url, optional=False):
    try:
        with urlopen(Request(url, headers={'User-Agent': 'SlicerDSpace-upstream-audit'}), timeout=45) as response:
            return response.read()
    except HTTPError as exc:
        if optional and exc.code == 404:
            return None
        raise


def repository(name):
    base = 'https://api.github.com/repos/' + name
    meta = json.loads(fetch(base))
    head = json.loads(fetch(base + '/commits/' + meta['default_branch']))
    release_bytes = fetch(base + '/releases/latest', optional=True)
    release = json.loads(release_bytes) if release_bytes else None
    return dict(repository=name, url=meta['html_url'], default_branch=meta['default_branch'],
                head_sha=head['sha'], head_date=head['commit']['committer']['date'],
                latest_release=None if release is None else dict(tag=release['tag_name'],
                    published_at=release['published_at'], url=release['html_url']))


def source(repo, revision, path, names=()):
    url = f'https://raw.githubusercontent.com/{repo}/{revision}/{path}'
    data = fetch(url)
    record = dict(url=url, revision=revision, path=path, sha256=hashlib.sha256(data).hexdigest())
    if names:
        record['functions_sha256'] = source_functions(data.decode(), names)
    return record


def audit(amico_configs=()):
    records = {name: repository(name) for name in (
        'dipy/dipy', 'SlicerDMRI/whitematteranalysis', 'daducci/AMICO',
        'zhangfanmark/MK-Curve', 'scipy/scipy')}
    for package, name in (('dipy', 'dipy/dipy'), ('dmri-amico', 'daducci/AMICO'), ('scipy', 'scipy/scipy')):
        info = json.loads(fetch(f'https://pypi.org/pypi/{package}/json'))
        latest = info['info']['version']
        files = info['releases'][latest]
        records[name]['pypi'] = dict(package=package, version=latest,
            published_at=min(row['upload_time_iso_8601'] for row in files),
            requires_python=info['info']['requires_python'], url=f'https://pypi.org/project/{package}/{latest}/')
    dipy = records['dipy/dipy']
    dipy['sources'] = {}
    definitions = {'dipy/reconst/fwdti.py': ('wls_iter', 'nls_iter', '_nls_err_func', '_nls_jacobian_func'),
                   'dipy/reconst/dti.py': ('decompose_tensor', 'from_lower_triangular'),
                   'dipy/reconst/dki.py': ('DiffusionKurtosisFit',)}
    for ref in dict.fromkeys(('1.11.0', dipy['latest_release']['tag'], dipy['head_sha'])):
        dipy['sources'][ref] = [source('dipy/dipy', ref, path, names) for path, names in definitions.items()]
    stable, head = (dipy['sources'][ref] for ref in (dipy['latest_release']['tag'], dipy['head_sha']))
    dipy['relevant_stable_and_head_definitions_equal'] = all(
        left['functions_sha256'] == right['functions_sha256'] for left, right in zip(stable, head))
    dipy['interpretation'] = ('Exact definition identity includes decorators, not imported dependency implementations. '
                              'Main-branch source inspection is not a main-branch runtime benchmark.')
    wma = records['SlicerDMRI/whitematteranalysis']
    historical = json.loads((ROOT / 'docs/release/benchmarks/author_wma_optimizations_20261020.json').read_text())
    wma['measured_reference_sha'] = historical['author_commit']
    wma['measured_reference_is_current_head'] = historical['author_commit'] == wma['head_sha']
    wma['sources'] = []
    for item in historical['upstream_verification']['records']:
        path = item['url'].split(historical['author_commit'] + '/')[1]
        current = source(wma['repository'], wma['head_sha'], path)
        current['equals_measured_source'] = current['sha256'] == item['remote_sha256']
        wma['sources'].append(current)
    mk = records['zhangfanmark/MK-Curve']
    mk['python_port_author_reference_sha'] = '9a213e1a5850fe50c998793f31ed852df00242f8'
    mk['author_reference_is_current_head'] = mk['head_sha'] == mk['python_port_author_reference_sha']
    mk['interpretation'] = 'Current MATLAB author reference; timings compare Python-port implementations, not MATLAB.'
    amico = records['daducci/AMICO']
    amico['measured_configurations'] = [amico_config_version(path) for path in amico_configs]
    amico['measured_versions_match_latest_stable'] = bool(amico_configs) and all(
        row['version'] == amico['pypi']['version'] for row in amico['measured_configurations'])
    scipy = records['scipy/scipy']
    scipy['sources'] = [source('scipy/scipy', ref, 'scipy/linalg/_basic.py', ('lstsq',))
                        for ref in ('v1.17.0', scipy['latest_release']['tag'])]
    scipy['lstsq_definition_equal_to_1_17_0'] = (scipy['sources'][0]['functions_sha256'] == scipy['sources'][1]['functions_sha256'])
    return dict(kind='performance_upstream_freshness_audit', schema_version=1,
                checked_at_utc=datetime.now(timezone.utc).isoformat(), repositories=records,
                policy='Version/source freshness is separate from numerical parity, scientific QC and paired timing.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--amico-config', type=Path, action='append', default=[])
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Refusing to replace a historical upstream audit')
    result = audit(args.amico_config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    for name, record in result['repositories'].items():
        print(name, record['head_sha'], record.get('latest_release'), flush=True)


if __name__ == '__main__':
    main()
