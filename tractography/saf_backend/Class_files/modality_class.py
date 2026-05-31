import numpy as np

from .surfproper_class import surfproper_class
from .saf_class import saf_class


class modality_class:
    def __init__(self, PS=None):
        self.rh = surfproper_class()
        self.lh = surfproper_class()
        self.cv = None
        self.cvi = None
        self.cvh = None
        self.cvt = None
        self.cvk = None
        self.sl_tracks = []
        self.sl_info = {}
        self.saf = saf_class()
        self.slx = None
        self.cv_pial_coord_file = ''
        self.cv_white_coord_file = ''
        self.seed_coords_file_in = ''
        self.seed_coords_file_out = ''
        self.sl_init = ''
        self.sl_weights = ''

    def calc_vandf(self):
        for hemi in ['rh', 'lh']:
            obj = getattr(self, hemi)
            obj.nverts = obj.white.shape[0]
            obj.nfaces = obj.faces.shape[0]
            obj.seeds = np.zeros((obj.nverts,), dtype=float)
        return self

    def mid_surf(self):
        for hemi in ['rh', 'lh']:
            obj = getattr(self, hemi)
            if obj.pial is not None and obj.white is not None:
                obj.mid = (obj.pial + obj.white) / 2.0
                obj.ht = np.sqrt(np.sum((obj.pial - obj.mid) ** 2, axis=1))
        return self

    def combine_verts(self, surf):
        for hemi in ['rh', 'lh']:
            obj = getattr(self, hemi)
            coords = getattr(obj, surf)
            if coords is None:
                continue
            lab_h = obj.usedv
            coords_i = np.where(lab_h)[0]
            if hemi == 'rh':
                self.cv = coords[coords_i]
                self.cvi = coords_i + 1
                self.cvh = np.zeros_like(coords_i, dtype=bool)
                if self.rh.ht is not None:
                    self.cvt = self.rh.ht[coords_i]
            else:
                self.cv = np.vstack([self.cv, coords[coords_i]])
                self.cvi = np.concatenate([self.cvi, coords_i + 1])
                self.cvh = np.concatenate([self.cvh, np.ones_like(coords_i, dtype=bool)])
                if self.lh.ht is not None:
                    self.cvt = np.concatenate([self.cvt, self.lh.ht[coords_i]])
        return self
