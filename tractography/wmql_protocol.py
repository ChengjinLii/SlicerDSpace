"""Pinned upstream WMQL inventory, atlas checks and per-bundle scientific status."""

from __future__ import annotations

import ast
from pathlib import Path


OFFICIAL_DIR = Path(__file__).resolve().parent / 'wmql_queries/official'
CATALOG_PRESETS = ('official', 'cerebellar', 'official_cerebellar')
CEREBELLAR_QUERIES = ('cerebellar_bilateral', 'cerebellar_brainstem.left', 'cerebellar_brainstem.right')


def official_query_names():
    names = []
    tree = ast.parse((OFFICIAL_DIR / 'freesurfer_queries.qry').read_text(encoding='utf-8'))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Attribute) and target.attr == 'side' and isinstance(target.value, ast.Name):
                names.extend(target.value.id.lower() + '.' + side for side in ('left', 'right'))
            elif isinstance(target, ast.Name):
                names.append(target.id.lower())
            else:
                raise ValueError('Unrecognized assignment in the pinned official WMQL inventory')
    return tuple(sorted(set(names)))


def preset_query_names(preset='official'):
    if preset == 'official':
        return official_query_names()
    if preset == 'cerebellar':
        return CEREBELLAR_QUERIES
    if preset == 'official_cerebellar':
        return tuple(sorted((*official_query_names(), *CEREBELLAR_QUERIES)))
    raise ValueError('Unknown bundled WMQL catalogue: ' + preset)


def canonical_wmql_selection(selection=(), preset='official'):
    """Empty means the selected catalogue; a family expands to both sides."""
    values = selection.split(',') if isinstance(selection, str) else selection
    requested = [str(value).strip().lower() for value in values if str(value).strip()]
    if not requested or requested == ['all']:
        return ()
    available = set(preset_query_names(preset))
    result = set()
    for name in requested:
        if name in available:
            result.add(name)
        elif {name + '.left', name + '.right'} <= available:
            result.update((name + '.left', name + '.right'))
        else:
            raise ValueError(f'Unknown {preset} WMQL query: {name}. Use all, a family such as AF, or an exact query name.')
    return tuple(sorted(result))


def atlas_compatibility(path):
    """Check decoded label conventions, not spatial/anatomical equivalence to FreeSurfer."""
    import nibabel as nib
    import numpy as np
    from anatomy.parcellation.qc import label_semantics

    image = nib.load(str(path))
    data = np.asarray(image.dataobj)
    if (data.ndim != 3 or not np.isfinite(data).all() or np.any(data < 0)
            or not np.all(data == np.floor(data)) or not np.isfinite(image.affine).all()
            or abs(np.linalg.det(image.affine[:3, :3])) < 1e-12):
        raise ValueError('WMQL requires finite, nonnegative integer 3-D labels and a nonsingular affine')
    labels = set(map(int, np.unique(data)))
    cortical = {n for n in labels if 1001 <= n <= 1035 or 2001 <= n <= 2035}
    regional = {n for n in labels if 3001 <= n <= 3035 or 4001 <= n <= 4035}
    if not cortical and not regional:
        raise ValueError('Official WMQL rules require FreeSurfer/DK regional label IDs; a tissue mask is not sufficient')
    warnings = []
    if not regional:
        warnings.append('No regional WM labels (3000/4000 series). This is expected for DDParcel, '
                        'but its generic WM (2/41) does not replace regional WM in the official '
                        'crossing/only rules, including on UKF tracks.')
    # The official aliases do not reference DDParcel's unsplit callosal label 192.
    callosal_aliases = {'left': sorted(labels & {1004, 3004}), 'right': sorted(labels & {2004, 4004})}
    unavailable_queries = []
    if not callosal_aliases['left'] or not callosal_aliases['right']:
        unavailable_queries.extend(('cc_5', 'cc_6'))
        if not callosal_aliases['left'] and not callosal_aliases['right']:
            unavailable_queries.append('cc')
        warnings.append('Official callosal aliases are missing on one or both sides; required label '
                        'conditions cannot be satisfied for: ' + ', '.join(sorted(unavailable_queries)) + '.')
        if 192 in labels:
            warnings.append('Corpus callosum is present as label 192, but the unchanged official '
                            'corpuscallosum.left/right aliases use 1004/3004 and 2004/4004, not 192. '
                            'This is a label-convention mismatch, not evidence of missing callosal anatomy.')
    missing_core = {10, 49, 11, 50, 12, 51, 17, 53, 18, 54, 16} - labels
    # A complete wmparc replaces generic 2/41 with regional/deep WM labels.
    for generic, base, deep in ((2, 3000, 5001), (41, 4000, 5002)):
        if generic not in labels and deep not in labels and not any(base < n <= base + 35 for n in labels):
            missing_core.add(generic)
    missing_core = sorted(missing_core)
    if missing_core:
        warnings.append('Some upstream subcortical/generic WM IDs are absent: ' + ', '.join(map(str, missing_core)))
    return dict(schema='wmql_dk_compatibility.v1', integer_labels=True, label_ids=sorted(labels),
                cortical_region_ids=sorted(cortical), regional_wm_ids=sorted(regional),
                official_callosal_alias_label_ids=callosal_aliases,
                official_queries_with_unavailable_required_labels=sorted(unavailable_queries),
                missing_core_ids=missing_core, label_semantics=label_semantics(data), warnings=warnings,
                anatomical_equivalence_verified=False, spatial_alignment_review='pending',
                scope='Numeric label convention only; no relabeling, dilation or substitution of author rules')


def bundle_assessment(summary, requested, minimum):
    records = {item['query_name']: item for item in summary.get('bundles', [])}
    bundles = []
    for name in requested:
        item = records.get(name)
        count = int(item.get('streamline_count', 0)) if item else 0
        state = ('not_extracted' if item is None else 'invalid' if 'streamline_count_error' in item
                 else 'empty' if count == 0 else 'insufficient_sampling' if count < minimum
                 else 'anatomical_review_pending')
        bundles.append(dict(query_name=name, streamline_count=count, state=state,
                            sampling_passed=state == 'anatomical_review_pending',
                            quantification_eligible=False, human_review='pending'))
    excluded = [item['query_name'] for item in bundles if not item['sampling_passed']]
    return dict(requested_count=len(requested), extracted_count=sum(item['streamline_count'] > 0 for item in bundles),
                minimum_streamlines=minimum, bundles=bundles, excluded_from_quantification=excluded,
                all_requested_sampling_passed=not excluded,
                scope='Queries may overlap; absent outputs are not manufactured. Sampling does not certify anatomy.')
