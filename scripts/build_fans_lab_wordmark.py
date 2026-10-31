#!/usr/bin/env python3
"""Trace the supplied lab wordmark into transparent, font-independent SVGs.

Requires Pillow, NumPy, OpenCV and potracer==0.0.4 for retracing.
"""

import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import potrace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/website/sources/fans-lab-reference.jpg'


def main():
    grey = np.asarray(Image.open(SOURCE).convert('L'))
    mask = (cv2.GaussianBlur(grey, (3, 3), 0) > 10).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    components = sorted((i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] > 40),
                        key=lambda i: stats[i, cv2.CC_STAT_LEFT])
    mask = np.isin(labels, components)
    ys, xs = np.where(mask)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    width, height = x1 - x0 + 24, y1 - y0 + 24
    paths = []
    for i in components:
        x, y, w, h, _ = stats[i]
        bitmap = labels[y:y+h, x:x+w] == i
        curves = potrace.Bitmap(~np.pad(bitmap, 2)).trace(turdsize=4, alphamax=1, opttolerance=.3)
        def point(p):
            return f'{p.x+x-x0+10:.3f},{p.y+y-y0+10:.3f}'
        d = []
        for curve in curves:
            d.append('M' + point(curve.start_point))
            for segment in curve:
                d.append(('L' + point(segment.c) + ' ' + point(segment.end_point)) if segment.is_corner else
                         ('C' + point(segment.c1) + ' ' + point(segment.c2) + ' ' + point(segment.end_point)))
            d.append('Z')
        paths.append(('lab' if x > grey.shape[1] * .54 else 'fan', ' '.join(d)))
    receipt_path = ROOT / 'docs/website/published_assets.json'
    receipt = json.loads(receipt_path.read_text())
    for name, primary, secondary in (('fans-lab-wordmark.svg', '#12171b', '#787f84'),
                                     ('fans-lab-wordmark-light.svg', '#f4f5f6', '#9ca3a9')):
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">',
               '<title id="title">Fan\'s Lab</title>']
        svg.extend(f'<path fill="{secondary if group == "lab" else primary}" fill-rule="evenodd" d="{d}"/>' for group, d in paths)
        svg.append('</svg>')
        data = ('\n'.join(svg) + '\n').encode()
        relative = 'docs/site/assets/img/' + name
        (ROOT / relative).write_bytes(data)
        receipt['files'][relative] = dict(sha256=hashlib.sha256(data).hexdigest(),
            source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            derivative='Reference-traced cubic outlines; transparent background; no fonts or embedded raster')
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'PASS two vector wordmarks, {width} x {height}, {len(paths)} components')


if __name__ == '__main__':
    main()
