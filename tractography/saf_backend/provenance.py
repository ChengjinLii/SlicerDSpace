"""Scientific implementation identity, independent of run-specific parameters."""

UPSTREAM_COMMIT = '7e2a9d152caf1cf3e6bface64e7e176faac0c14f'
IMPLEMENTATION_REVISION = 'python-native-20261013'


def implementation_record():
    return {
        'kind': 'unofficial_matlab_to_python_port',
        'revision': IMPLEMENTATION_REVISION,
        'upstream_repository': 'https://github.com/dmitrishastin/SAF',
        'upstream_commit': UPSTREAM_COMMIT,
        'surface_space': 'native_dMRI_only_no_automatic_registration',
        'endpoint_vertex_assignment': 'paired_coordinates_and_crossed_faces',
        'clustering': 'sklearn_KMeans_random_state_0_n_init_10_nearest_cluster_search',
        'documented_deviations': [
            'Correct MATLAB/Python endpoint-layout ambiguity in surface projection.',
            'Retain complete-mode edge/vertex intersections and remove duplicate shared-point crossings.',
            'Preserve original indices for rejected one-/two-point streamlines.',
            'Map hard-split weights through original whole-tractogram indices; split weights are not refitted.',
            'No ANTs registration wrapper or automatic recon-all from a T1 image is exposed by the facade.',
        ],
        'scientific_claim': 'Surface-constrained tractographic SAF candidates, not guaranteed U-fibres or adjacent-gyri ground truth.',
    }
