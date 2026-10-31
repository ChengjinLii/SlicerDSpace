#!/usr/bin/env python3
"""Prepare a dark website derivative of the reviewed workflow SVG."""

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from prepare_website_results import validate_static_svg

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = 'docs/site/assets/img/workflow-overview.svg'
NS = '{http://www.w3.org/2000/svg}'
PALETTE = {
    '#ffffff': '#10151b', '#24292e': '#edf0f3', '#495057': '#b5bec7',
    '#DFEAF3': '#192c3d', '#9EB4C6': '#6686a1',
    '#F3E1D7': '#362b27', '#C8A58D': '#a88a75',
    '#E4EDDC': '#263229', '#ABB995': '#829775',
    '#b7bdc1': '#64707b', '#aeb4b8': '#77848e', '#747b81': '#a4afb8',
    '#2c4c6b': '#9bbbd7', '#6b6b6b': '#a4afb8',
}


def render(source):
    root = ET.fromstring(source)
    # Publication metadata is not needed by the public display copy.
    for parent in root.iter():
        for child in list(parent):
            if child.tag.rsplit('}', 1)[-1] == 'metadata' or child.get('data-workflow-frame'):
                parent.remove(child)
    validate_static_svg(root)
    for node in root.iter():
        for key in ('fill', 'stroke'):
            if node.get(key) in PALETTE:
                node.set(key, PALETTE[node.get(key)])
    background = next(n for n in root if n.tag == NS + 'rect' and n.get('width') == '100%')
    background.set('fill', '#06080b')
    logo = next(n for n in root.iter() if n.get('id') == 'vector-logo')
    for node in logo.iter():
        if node.tag == NS + 'path' and node.get('fill') not in (None, 'none'):
            node.set('fill', '#a8b0b8' if node.get('fill') in ('#787f84', '#a8b0b8') else '#edf0f3')
    parents = {child: parent for parent in root.iter() for child in parent}
    clips = {node.get('id'): node for node in root.iter(NS + 'clipPath')}
    for parent in list(root.iter()):
        for node in list(parent):
            if node.tag == NS + 'image':
                frame = ET.Element(NS + 'rect', {key: node.get(key) for key in ('x', 'y', 'width', 'height')})
                frame.attrib.update(fill='none', stroke='#ffffff', **{'stroke-width': '2', 'data-workflow-frame': 'true'})
                if parent.get('clip-path'):
                    # Outline the rounded tile outside its clip so the full stroke survives.
                    frame.attrib.update(rx='18', **{'stroke-width': '1', 'vector-effect': 'non-scaling-stroke'})
                    clip_id = parent.get('clip-path')[5:-1]
                    for corner in clips[clip_id].iter(NS + 'rect'):
                        corner.set('rx', '18')
                    container = parents[parent]
                    container.insert(list(container).index(parent) + 1, frame)
                else:
                    parent.insert(list(parent).index(node) + 1, frame)
    ET.register_namespace('', NS[1:-1])
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    args = parser.parse_args()
    source = args.source.read_bytes()
    output = render(source)
    (ROOT / OUTPUT).write_bytes(output)
    path = ROOT / 'docs/website/published_assets.json'
    receipt = json.loads(path.read_text())
    receipt['files'][OUTPUT] = dict(sha256=hashlib.sha256(output).hexdigest(),
        source_sha256=hashlib.sha256(source).hexdigest(),
        derivative='Dark website palette and white image outlines; original workflow layout, labels and embedded result images retained')
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    assert args.source.read_bytes() == source
    print('PASS website workflow SVG; paper source unchanged')


if __name__ == '__main__':
    main()
