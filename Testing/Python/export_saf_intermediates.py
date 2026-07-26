from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import sys
from pathlib import Path

import nibabel as nib
import numpy as np


def _work_or_cache_path(work_dir: Path, name: str) -> Path:
    direct = work_dir / name
    if direct.exists() or direct.is_symlink():
        return direct
    return work_dir / "cache" / name


@contextmanager
def _temporary_cached_progress_links(work_dir: Path):
    """Expose cached SAF progress files where the translated loader expects them."""

    created: list[Path] = []
    for name in ("PS.mat", "SD.mat"):
        direct = work_dir / name
        cached = work_dir / "cache" / name
        if direct.exists() or direct.is_symlink() or not cached.exists():
            continue
        direct.symlink_to(cached)
        created.append(direct)
    try:
        yield
    finally:
        for path in created:
            path.unlink(missing_ok=True)


def _load_saf_progress(work_dir: Path):
    sys.path.insert(0, str((Path(__file__).resolve().parents[2] / "tractography" / "saf_backend")))
    from SAF_pipeline import load_progress  # type: ignore
    from Class_files.init_class import init_class  # type: ignore

    manifest = json.loads((work_dir / "saf_manifest.json").read_text())
    fs_dir = manifest["inputs"]["fs_dir"]["path"]
    fod = manifest["inputs"]["fod"]["path"]
    args = [
        "fs_dir",
        fs_dir,
        "fod",
        fod,
        "outf",
        work_dir.as_posix(),
        "dgn",
    ]
    ps = init_class(args)
    with _temporary_cached_progress_links(work_dir):
        return load_progress(ps)


def _save_tck(streamlines, path: Path) -> None:
    tractogram = nib.streamlines.Tractogram(streamlines, affine_to_rasmm=np.eye(4))
    nib.streamlines.save(tractogram, path.as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description="Export SAF intermediate tractograms from a diagnostics run.")
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    work_dir = args.work_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    surf_tracks_path = _work_or_cache_path(work_dir, "surf_tracks.tck")
    if not surf_tracks_path.is_file():
        raise FileNotFoundError(f"Missing surf_tracks.tck under {work_dir}")

    sd = _load_saf_progress(work_dir)
    sl_tracks = list(nib.streamlines.load(surf_tracks_path.as_posix()).streamlines)

    valid_after_gghh = np.all(sd.DWI.saf.t_gghh, axis=0) & ~sd.DWI.saf.pg & ~sd.DWI.saf.ml
    final_after_gwg = np.all(sd.DWI.saf.t_gwg, axis=0)
    rejected_by_gwg = valid_after_gghh & ~final_after_gwg

    gghh_streamlines = [sl for sl, keep in zip(sl_tracks, valid_after_gghh) if keep]
    final_candidate_streamlines = [sl for sl, keep in zip(sl_tracks, final_after_gwg) if keep]
    gwg_rejected_streamlines = [sl for sl, keep in zip(sl_tracks, rejected_by_gwg) if keep]

    _save_tck(gghh_streamlines, output_dir / "post_GGHH_pre_GWG.tck")
    _save_tck(final_candidate_streamlines, output_dir / "final_SAF_from_masks.tck")
    _save_tck(gwg_rejected_streamlines, output_dir / "rejected_by_GWG.tck")

    print(f"post_GGHH_pre_GWG={len(gghh_streamlines)}")
    print(f"final_SAF_from_masks={len(final_candidate_streamlines)}")
    print(f"rejected_by_GWG={len(gwg_rejected_streamlines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
