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
    from tractography.wmql import (AUTHOR_ALIAS_SHA256, AUTHOR_BUNDLE_QUERY_SHA256, official_query_names,
                                  bundled_wmql_query_path, wmql_query_dependencies)
    from tractography.wmql_protocol import CATALOG_PRESETS
    from shared.external_process import python_tool_environment
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline-manifest', type=Path,
                        help='For the extension, compare all original outputs with an archived official run.')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    preset = manifest.get('query_preset', 'official')
    if (preset not in CATALOG_PRESETS or manifest.get('status') != 'completed'
            or not (manifest.get('official_multibundle') or manifest.get('coverage_report_mode'))):
        raise ValueError('Requires a completed bundled-catalogue extraction')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    backend = manifest['backend']['commands']
    author = Path(manifest['backend']['root']) / 'tract_querier/data'
    original, aliases = author / 'freesurfer_queries.qry', author / 'FreeSurfer.qry'
    if digest(original) != AUTHOR_BUNDLE_QUERY_SHA256 or digest(aliases) != AUTHOR_ALIAS_SHA256:
        raise ValueError('Reference is not the pinned upstream rule set')
    rules = original if preset == 'official' else bundled_wmql_query_path(preset)
    include_dirs = [rules.parent, author]
    dependencies = wmql_query_dependencies(rules, include_dirs)
    expected = {Path(path).name: sha for path, sha in manifest['query_dependencies'].items()}
    if {Path(path).name: sha for path, sha in dependencies.items()} != expected:
        raise ValueError('Reference queries differ from the executed query snapshot')
    source, atlas = Path(manifest['input_tractography']), Path(manifest['atlas_path'])
    before = {str(path): digest(path) for path in (source, atlas, original, aliases, *map(Path, dependencies))}
    prefix = output / 'reference'
    command = [backend['python'], backend['root_script'], '-t', str(source), '-a', str(atlas),
               '-q', str(rules), '-I', os.pathsep.join(map(str, include_dirs)), '-o', str(prefix),
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
    baseline_comparisons = []
    if args.baseline_manifest:
        baseline = json.loads(args.baseline_manifest.read_text())
        if (not baseline.get('official_multibundle') or baseline.get('status') != 'completed'
                or preset != 'official_cerebellar'
                or baseline['threshold'] != manifest['threshold']
                or baseline['length_threshold'] != manifest['length_threshold']
                or digest(baseline['input_tractography']) != before[str(source)]
                or digest(baseline['atlas_path']) != before[str(atlas)]):
            raise ValueError('Baseline must be a completed official extraction with identical input and parameters')
        baseline_files = {item['query_name']: Path(item['path']) for item in baseline['outputs']['summary']['bundles']}
        for name in official_query_names():
            archived = Counter(line_hash(track) for track in tracks_from_file(baseline_files[name])) if name in baseline_files else Counter()
            current = Counter(line_hash(track) for track in tracks_from_file(observed[name])) if name in observed else Counter()
            baseline_comparisons.append(dict(query=name, baseline_streamlines=sum(archived.values()),
                                            current_streamlines=sum(current.values()), exact_multiset_equal=archived == current))
        checks['all_48_original_queries_unchanged'] = all(item['exact_multiset_equal'] for item in baseline_comparisons)
    payload = dict(status='passed' if all(checks.values()) else 'failed', checks=checks,
                   query_preset=preset, official_rule_bytes_unchanged=True,
                   source_hashes=before, command=command, reference_runtime_seconds=reference_seconds,
                   comparisons=comparisons, anatomical_review='pending',
                   original_query_comparison=baseline_comparisons,
                   scope='Wrapper versus direct author-engine execution of the recorded query definitions, and exact source membership; not anatomical accuracy')
    (output / 'parity.json').write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps(dict(status=payload['status'], queries=len(comparisons), extracted=len(observed),
                         reference_runtime_seconds=reference_seconds, report=str(output / 'parity.json'))))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
