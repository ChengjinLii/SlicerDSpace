% Execute unmodified author kernels; fixtures are deliberately synthetic.
function saf_matlab_reference(upstream, input_file, output_file)
    addpath(fullfile(upstream, 'Filters', 'streamlineXmesh'));
    load(input_file);
    fast_intersections = trintersect_fast(P1, P2, P3, Q1, Q2);
    complete_intersections = trintersect_complete(P1, P2, P3, Q1, Q2, triangle_vertices, face_ids, segment_ids);
    [fast_tracks, fast_original, fast_vertices, fast_points] = ...
        crop_streamlines_outside_mesh_fast(vertices, faces, tracks, inside, outer_intersection);
    [complete_tracks, complete_original, complete_vertices, complete_points] = ...
        crop_streamlines_outside_mesh_complete(vertices, faces, tracks, inside, outer_intersection);
    save('-mat7-binary', output_file, 'fast_intersections', 'complete_intersections', ...
        'fast_tracks', 'fast_original', 'fast_vertices', 'fast_points', ...
        'complete_tracks', 'complete_original', 'complete_vertices', 'complete_points');
end
