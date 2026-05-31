import os


def Supp_gz_fileparts(fname):
    if fname.endswith('z') and fname.lower().endswith('.nii.gz'):
        pp, nn = os.path.split(fname[:-3])
        ext = '.nii.gz'
    else:
        pp, base = os.path.split(fname)
        nn, ext = os.path.splitext(base)
    return pp, nn, ext
