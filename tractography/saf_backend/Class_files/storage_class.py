import os

from .modality_class import modality_class
from .tx_class import tx_class
from Support.sys_exec import sys_exec
from Support.convert_coords import convert_coords
from Support.process_coords import process_coords
from Support.pts_to_tck import pts_to_tck
from Support.Supp_gz_fileparts import Supp_gz_fileparts


class storage_class:
    def __init__(self, PS):
        self.T1 = modality_class(PS)
        self.DWI = modality_class(PS)

        self.T1.rh.pial_file = os.path.join(PS.fs_dir, 'surf', 'rh.pial')
        self.T1.rh.white_file = os.path.join(PS.fs_dir, 'surf', 'rh.white')
        self.T1.rh.infl_file = os.path.join(PS.fs_dir, 'surf', 'rh.inflated')
        self.T1.rh.sph_file = os.path.join(PS.fs_dir, 'surf', 'rh.sphere')
        self.T1.rh.curv_file = os.path.join(PS.fs_dir, 'surf', 'rh.curv')

        self.T1.lh.pial_file = os.path.join(PS.fs_dir, 'surf', 'lh.pial')
        self.T1.lh.white_file = os.path.join(PS.fs_dir, 'surf', 'lh.white')
        self.T1.lh.infl_file = os.path.join(PS.fs_dir, 'surf', 'lh.inflated')
        self.T1.lh.sph_file = os.path.join(PS.fs_dir, 'surf', 'lh.sphere')
        self.T1.lh.curv_file = os.path.join(PS.fs_dir, 'surf', 'lh.curv')

        self.tx = tx_class(PS)

    def tx_coords(self, surf, PS):
        if not PS.noregister:
            for hemi in ['rh', 'lh']:
                if getattr(self.T1, hemi).__dict__.get(surf) is not None:
                    in_name = os.path.join(PS.work_dir, f"T1_{hemi}_{surf}.csv")
                    out_name = os.path.join(PS.work_dir, f"DWI_{hemi}_{surf}.csv")
                    if (not os.path.exists(out_name)) or PS.force:
                        if not os.path.exists(in_name):
                            convert_coords(getattr(self.T1, hemi).__dict__[surf], in_name)
                        if self.tx.warp:
                            command = f"antsApplyTransformsToPoints -d 3 -p 1 -i {in_name} -o {out_name} -t {self.tx.warp} -t {self.tx.affine}"
                        elif self.tx.affine:
                            command = f"antsApplyTransformsToPoints -d 3 -p 1 -i {in_name} -o {out_name} -t {self.tx.affine}"
                        else:
                            raise RuntimeError('no registration info available')
                        sys_exec(command, PS)

                    dr, nm, ext = Supp_gz_fileparts(out_name)
                    if ext == '.csv':
                        out_txt = os.path.join(dr, nm + '.txt')
                        convert_coords(out_name, out_txt)
                        out_name = out_txt

                    setattr(self.T1, hemi, self.T1.__dict__[hemi])
                    getattr(self.T1, hemi).__dict__[surf + '_coord_file'] = in_name
                    getattr(self.DWI, hemi).__dict__[surf + '_coord_file'] = out_name
                    getattr(self.DWI, hemi).__dict__[surf] = process_coords(out_name)
                    getattr(self.T1, hemi).__dict__[surf] = None

                    if PS.dgn:
                        pts_to_tck(out_name, os.path.join(dr, nm + '.tck'))
        else:
            for hemi in ['rh', 'lh']:
                getattr(self.DWI, hemi).__dict__[surf] = getattr(self.T1, hemi).__dict__[surf]
                getattr(self.T1, hemi).__dict__[surf] = None
                if PS.dgn:
                    coord_file = os.path.join(PS.work_dir, f"DWI_{hemi}_{surf}.txt")
                    getattr(self.DWI, hemi).__dict__[surf + '_coord_file'] = coord_file
                    convert_coords(getattr(self.DWI, hemi).__dict__[surf], coord_file)
        return self
