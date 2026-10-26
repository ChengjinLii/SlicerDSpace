#!/usr/bin/env python3
"""Make a lightweight, StudyHub-style animated link to the original promo MP4."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"))
    parser.add_argument("--speed", type=float, default=1.0, help="Playback multiplier; 1 preserves normal speed")
    args = parser.parse_args()
    if not args.ffmpeg:
        parser.error("Set --ffmpeg to an installed FFmpeg executable")
    if not math.isfinite(args.speed) or args.speed <= 0:
        parser.error("--speed must be finite and positive")
    source = ROOT / "docs/site/media/SlicerDDSurfer_promo_1080p.mp4"
    target = ROOT / "docs/assets/readme/SlicerDDSurfer_preview.gif"
    target.parent.mkdir(parents=True, exist_ok=True)
    filters = (f"setpts=PTS/{args.speed:g},fps=6,scale=640:-2:flags=lanczos,split[a][b];"
               "[a]palettegen=max_colors=128:stats_mode=diff[p];"
               "[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle")
    subprocess.run([args.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                    "-filter_complex", filters, "-loop", "0", str(target)], check=True)
    print(json.dumps(dict(file=str(target.relative_to(ROOT)), bytes=target.stat().st_size,
                          width=640, fps=6, playback_speed=args.speed,
                          source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                          preview_sha256=hashlib.sha256(target.read_bytes()).hexdigest()), indent=2))


if __name__ == "__main__":
    main()
