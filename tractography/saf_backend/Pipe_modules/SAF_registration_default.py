import os

from Support.sys_exec import sys_exec
from Support.verb_msg import verb_msg


def SAF_registration_default(PS, SD):
    if not PS.noregister:
        ants_anat = os.path.join(PS.work_dir, 'ants_anatomical.nii.gz')
        if os.path.exists(ants_anat) and PS.force:
            sys_exec(f"rm {os.path.join(PS.work_dir, 'ants_*')}", PS)

        if not os.path.exists(ants_anat):
            if not PS.fa:
                raise RuntimeError('FA file is required for registration')
            verb_msg('Performing FA to T1 registration using ANTS', PS)
            command = f"antsIntermodalityIntrasubject.sh -d 3 -i {PS.fa} -r {SD.tx.t1} -t 3 -x {SD.tx.t1} -w {os.path.join(PS.work_dir, 'a')} -o {os.path.join(PS.work_dir, 'ants_')}"
            sys_exec(command, PS)

        SD.tx.affine = os.path.join(PS.work_dir, 'ants_0GenericAffine.mat')
        SD.tx.warp = os.path.join(PS.work_dir, 'ants_1Warp.nii.gz')
        SD.tx.iwarp = os.path.join(PS.work_dir, 'ants_1InverseWarp.nii.gz')
        SD.tx.in_dwi = os.path.join(PS.work_dir, 'brain_DWI.nii.gz')

        if not os.path.exists(SD.tx.in_dwi) or PS.force:
            command = f"antsApplyTransforms -d 3 -i {SD.tx.t1} -r {PS.fa} -t [{SD.tx.affine}, 1] -t {SD.tx.iwarp} -o {SD.tx.in_dwi}"
            sys_exec(command, PS)
    else:
        verb_msg('Assuming T1 and DWI are co-registered', PS)
        SD.tx.in_dwi = SD.tx.t1
        nn = os.path.basename(SD.tx.t1)
        command = f"ln -s {SD.tx.t1} {os.path.join(PS.work_dir, nn)}"
        sys_exec(command, PS)

    return SD
