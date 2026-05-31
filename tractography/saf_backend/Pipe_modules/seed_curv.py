import os
import numpy as np

from Support.verb_msg import verb_msg
from Filters.snap2mesh.coordinate_clustering import coordinate_clustering
from Filters.snap2mesh.find_closest_vertex import find_closest_vertex
from Support.write_curv import write_curv
from Support.process_coords import process_coords


def seed_curv(PS, SD):
    if PS.dgn and not PS.noseed:
        out_dir = os.path.join(PS.work_dir, 'surf_data')
        os.makedirs(out_dir, exist_ok=True)

        surffile = {
            'rh': os.path.join(out_dir, 'rh.seeds'),
            'lh': os.path.join(out_dir, 'lh.seeds'),
        }

        if (not os.path.exists(surffile['rh'])) or (not os.path.exists(surffile['lh'])) or PS.force:
            verb_msg('Projecting seeds on the white matter surface', PS)
            seeds_all = process_coords(SD.DWI.seed_coords_file_out)
            wsm_clustering, _ = coordinate_clustering(SD.DWI.cv, seeds_all.shape[0])
            gg_idx, _ = find_closest_vertex(SD.DWI.cv, seeds_all, wsm_clustering)
            hh_idx = SD.DWI.cvh[gg_idx - 1]
            gg_idx = SD.DWI.cvi[gg_idx - 1]

            seeds = {
                'rh': gg_idx[~hh_idx],
                'lh': gg_idx[hh_idx],
            }
            total_count = 0
            for hemi in ['rh', 'lh']:
                uv_idx, uv_p = np.unique(seeds[hemi], return_inverse=True)
                uv_c = np.bincount(uv_p)
                cvc = np.zeros((getattr(SD.DWI, hemi).nverts,), dtype=np.uint32)
                cvc[uv_idx - 1] = uv_c
                total_count += len(uv_idx)
                write_curv(surffile[hemi], cvc, getattr(SD.DWI, hemi).nfaces)
                getattr(SD.DWI, hemi).seeds = cvc.astype(bool)

            PS.logt.append(['Cortical seed density (%):', round(total_count / np.sum(np.concatenate([SD.DWI.rh.usedv, SD.DWI.lh.usedv])) * 100, 2)])

    return PS, SD
