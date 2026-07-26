import os

from .modality_class import modality_class
from .tx_class import tx_class
from Support.convert_coords import convert_coords


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
        for hemi in ['rh', 'lh']:
            getattr(self.DWI, hemi).__dict__[surf] = getattr(self.T1, hemi).__dict__[surf]
            getattr(self.T1, hemi).__dict__[surf] = None
            if PS.dgn:
                coord_file = os.path.join(PS.work_dir, f"DWI_{hemi}_{surf}.txt")
                getattr(self.DWI, hemi).__dict__[surf + '_coord_file'] = coord_file
                convert_coords(getattr(self.DWI, hemi).__dict__[surf], coord_file)
        return self
