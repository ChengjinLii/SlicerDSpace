"""Prepare SAF inputs that are already expressed in native dMRI space."""

import os
import shutil

from Support.verb_msg import verb_msg


def SAF_native_space(PS, SD):
    verb_msg('Using surfaces supplied in native dMRI space', PS)
    SD.tx.in_dwi = SD.tx.t1
    target = os.path.join(PS.work_dir, os.path.basename(SD.tx.t1))
    if not os.path.lexists(target):
        try:
            os.symlink(SD.tx.t1, target)
        except OSError:
            shutil.copy2(SD.tx.t1, target)
    return SD
