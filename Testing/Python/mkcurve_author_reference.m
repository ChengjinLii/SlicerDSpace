% Execute unmodified author numeric routines for independent port verification.
% Requires a separately obtained MK-Curve checkout; not used in production.
args = argv();
addpath(genpath(args{1}));
load(args{2});
[orig_s0, orig_dt] = dki_fit(dwi, grad, mask, [0 0 0]);
[orig_fa, orig_md, orig_rd, orig_ad, ~, orig_mk, orig_rk, orig_ak] = dki_parameters(orig_dt, mask);
curves = zeros(length(grid), sum(mask(:) > 0));
working = dwi;
for i = 1:length(grid)
    working(:,:,:,1) = grid(i);
    [~, dt] = dki_fit(working, grad, mask, [0 0 0]);
    mk = dki_mk_only(dt, mask);
    curves(i,:) = vectorize(mk, mask);
end
[zero_b0, max_b0, max_mk, abnormal, unusual] = abnormal_voxel_detection(curves, dwi, mask, grid, .5, '');
corrected_b0 = dwi(:,:,:,1);
correction = zero_b0 * .5 + max_b0 * .5;
corrected_b0(abnormal) = correction(abnormal);
working = dwi;
working(:,:,:,1) = corrected_b0;
[corr_s0, corr_dt] = dki_fit(working, grad, mask, [0 0 0]);
[corr_fa, corr_md, corr_rd, corr_ad, ~, corr_mk, corr_rk, corr_ak] = dki_parameters(corr_dt, mask);
save('-mat7-binary', args{3}, 'curves', 'orig_s0', 'orig_dt', 'corr_s0', 'corr_dt',
     'orig_fa','orig_md','orig_rd','orig_ad','orig_mk','orig_rk','orig_ak',
     'corr_fa','corr_md','corr_rd','corr_ad','corr_mk','corr_rk','corr_ak',
     'zero_b0','max_b0','max_mk','abnormal','unusual','corrected_b0');
