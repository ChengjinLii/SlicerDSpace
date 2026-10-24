#!/usr/bin/env python3
"""Compare wrapper outputs with a direct pinned-author invocation, read-only inputs."""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    from scripts.audit_bundle_products import tracks_from_file, line_hash
    from tractography.wmql import AUTHOR_ALIAS_SHA256, AUTHOR_BUNDLE_QUERY_SHA256, official_query_names
    from shared.external_process import python_tool_environment
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if not manifest.get('official_multibundle') or manifest.get('status') != 'completed':
        raise ValueError('Requires a completed official-mode run, not scientific all-bundle acceptance')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    backend = manifest['backend']['commands']
    author = Path(manifest['backend']['root']) / 'tract_querier/data'
    rules, aliases = author / 'freesurfer_queries.qry', author / 'FreeSurfer.qry'
    if digest(rules) != AUTHOR_BUNDLE_QUERY_SHA256 or digest(aliases) != AUTHOR_ALIAS_SHA256:
        raise ValueError('Reference is not the pinned upstream rule set')
    source, atlas = Path(manifest['input_tractography']), Path(manifest['atlas_path'])
    before = {str(path): digest(path) for path in (source, atlas, rules, aliases)}
    prefix = output / 'reference'
    command = [backend['python'], backend['root_script'], '-t', str(source), '-a', str(atlas),
               '-q', str(rules), '-I', str(author), '-o', str(prefix),
               '--threshold', str(manifest['threshold']), '--length_threshold', str(manifest['length_threshold'])]
    if manifest['query_selection']:
        command += ['--query_selection', ','.join(manifest['query_selection'])]
    env = python_tool_environment(backend['python'])
    env['PYTHONPATH'] = manifest['backend']['root'] + os.pathsep + env.get('PYTHONPATH', '')
    start = time.monotonic()
    with (output / 'author.log').open('w') as log:
        subprocess.run(command, check=True, env=env, stdout=log, stderr=subprocess.STDOUT)
    reference_seconds = time.monotonic() - start
    expected = manifest.get('requested_queries') or official_query_names()
    observed = {item['query_name']: Path(item['path']) for item in manifest['outputs']['summary']['bundles']}
    references = {path.stem.removeprefix('reference_'): path for path in output.glob('reference_*')
                  if path.suffix in {'.vtk', '.vtp', '.trk'}}
    source_tracks = Counter(line_hash(track) for track in tracks_from_file(source))
    comparisons = []
    for name in expected:
        original = Counter(line_hash(track) for track in tracks_from_file(observed[name])) if name in observed else Counter()
        reference = Counter(line_hash(track) for track in tracks_from_file(references[name])) if name in references else Counter()
        comparisons.append(dict(query=name, streamlines=sum(original.values()), author_streamlines=sum(reference.values()),
                                exact_streamline_multiset_equal=original == reference,
                                all_streamlines_from_input=not bool(original - source_tracks)))
    unchanged = all(digest(path) == value for path, value in before.items())
    checks = dict(source_files_unchanged=unchanged,
                  output_query_sets_equal=set(observed) == set(references),
                  all_query_multisets_equal=all(c['exact_streamline_multiset_equal'] for c in comparisons),
                  all_source_membership_passed=all(c['all_streamlines_from_input'] for c in comparisons))
    payload = dict(status='passed' if all(checks.values()) else 'failed', checks=checks,
                   source_hashes=before, command=command, reference_runtime_seconds=reference_seconds,
                   comparisons=comparisons, anatomical_review='pending',
                   scope='Wrapper versus direct author execution and exact source membership; not anatomical accuracy')
    (output / 'parity.json').write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps(dict(status=payload['status'], queries=len(comparisons), extracted=len(observed),
                         reference_runtime_seconds=reference_seconds, report=str(output / 'parity.json'))))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
