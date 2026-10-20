#!/usr/bin/env python3
"""Read-only attribution of sparse ORG bundles to clustering pipeline stages."""

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.output_contracts import vtp_streamline_count
from tractography.wma import tract_sampling_eligibility
from scripts.validate_pipeline_cohort import digest, write_json


def diagnose(manifest_path):
    manifest = json.loads(manifest_path.read_text())
    summary = manifest['outputs']['summary']
    counts = summary['anatomical_tract_streamline_counts']
    atlas = Path(manifest['atlas_dir']) / 'ORG-800FC-100HCP'
    sampling = tract_sampling_eligibility(counts)
    records = {}
    tracked = [manifest_path]
    for name in sampling['excluded_from_quantification']:
        stem, side = Path(name).stem.rsplit('_', 1)
        mrml = atlas / (stem + '.mrml')
        clusters = sorted(set(re.findall(r'cluster_\d{5}\.vtp', mrml.read_text())))
        if not clusters:
            raise ValueError(f'No author cluster mapping found: {mrml}')
        tracked.append(mrml)
        stages = {}
        for stage, key in (('initial_bilateral', 'initial_clusters_dir'),
                           ('outlier_removed_bilateral', 'outlier_removed_dir'),
                           ('transformed_bilateral', 'transformed_clusters_dir'),
                           ('separated_left', 'separated_left_hemisphere_dir'),
                           ('separated_right', 'separated_right_hemisphere_dir'),
                           ('separated_commissural', 'separated_commissural_dir')):
            files = [Path(summary[key]) / cluster for cluster in clusters]
            tracked.extend(files)
            values = [vtp_streamline_count(path) for path in files]
            if any(value is None for value in values):
                raise ValueError(f'Missing or undecodable intermediate products: {stage}, {name}')
            stages[stage] = sum(values)
        appended = counts[name]
        checks = {'no_transform_loss': stages['outlier_removed_bilateral'] == stages['transformed_bilateral'],
                  'hemisphere_conservation': stages['transformed_bilateral'] == sum(stages[key] for key in (
                      'separated_left', 'separated_right', 'separated_commissural')),
                  'append_matches_author_cluster_mapping': stages['separated_' + side] == appended}
        records[name] = {'clusters': clusters, 'stages': stages, 'appended_count': appended,
                         'outlier_retention_ratio': stages['outlier_removed_bilateral'] / max(stages['initial_bilateral'], 1),
                         'structural_checks': checks,
                         'sampling_passed': False,
                         'interpretation': 'Low atlas assignment/retention is not repaired by relaxing outlier rejection or duplicating streamlines.'}
    return {'kind': 'wma_sparse_tract_stage_diagnosis', 'manifest': str(manifest_path), 'tract_sampling': sampling,
            'tracts': records, 'structural_checks_passed': all(all(item['structural_checks'].values()) for item in records.values()),
            'scientific_qc_passed': False if records else None, 'human_review': 'pending',
            'source_sha256': {str(path): digest(path) for path in tracked},
            'scope': 'Read-only stage conservation and atlas mapping, not proof of anatomy or rescued sampling.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Refusing to overwrite an existing diagnosis')
    outcome = diagnose(args.manifest.resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.report, outcome)
    print(json.dumps(outcome['tracts'], indent=2))
    raise SystemExit(0 if outcome['structural_checks_passed'] else 1)
