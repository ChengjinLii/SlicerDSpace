#!/usr/bin/env python3
"""Create the reviewed, dark-gutter website derivative of the paper result SVG."""

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("docs/site/assets/img/results-overview.svg")
SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"


def validate_static_svg(root):
    allowed = {"svg", "title", "desc", "defs", "linearGradient", "stop", "rect", "text", "tspan",
               "image", "path", "line", "circle", "g", "polygon", "polyline", "clipPath", "marker"}
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] not in allowed:
            raise ValueError("Unexpected SVG element: " + node.tag)
        for key, value in node.attrib.items():
            local = key.rsplit("}", 1)[-1].lower()
            if local.startswith("on") or local == "style":
                raise ValueError("Active SVG attributes are not supported")
            if local == "href" and not value.startswith(("#", "data:image/jpeg;base64,", "data:image/png;base64,")):
                raise ValueError("The results SVG must contain only embedded images")
            if "url(" in value and not value.startswith("url(#"):
                raise ValueError("External SVG resources are not supported")


def render(source):
    root = ET.fromstring(source)
    validate_static_svg(root)
    background = next((n for n in root if n.tag == f"{{{SVG}}}rect" and n.get("width") == "100%"), None)
    panels = [n for n in root if n.tag == f"{{{SVG}}}rect" and n.get("rx") == "16"]
    if background is None or len(panels) != 5:
        raise ValueError("Expected the complete five-panel paper result overview")
    background.set("fill", "#06080b")
    for panel in panels:
        panel.set("stroke", "#ffffff")
        panel.set("stroke-width", "1.5")
    ET.register_namespace("", SVG)
    ET.register_namespace("xlink", XLINK)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Reviewed paper result overview SVG")
    parser.add_argument("--wmql-provenance", type=Path, help="WMQL renderer receipt for the regional extension")
    args = parser.parse_args()
    source = args.source.read_bytes()
    visible = ''.join(ET.fromstring(source).itertext())
    extended = 'CBL-BrS' in visible or 'CBL-CBL' in visible
    if extended and args.wmql_provenance is None:
        parser.error('The cerebellar extension requires --wmql-provenance')
    provenance = json.loads(args.wmql_provenance.read_text()) if args.wmql_provenance else None
    if provenance and (provenance.get('query_provenance', {}).get('preset') != 'official_cerebellar'
                       or not provenance.get('source_files_unchanged') or not extended):
        raise ValueError('The WMQL receipt does not identify the displayed regional extension')
    output = render(source)
    (ROOT / OUTPUT).write_bytes(output)
    receipt_path = ROOT / "docs/website/published_assets.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["files"][OUTPUT.as_posix()] = {
        "sha256": hashlib.sha256(output).hexdigest(),
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "derivative": "Black website gutters and white panel outlines; scientific artwork unchanged",
        "query_preset": "official_cerebellar" if extended else "official_multibundle",
    }
    if provenance:
        receipt['files'][OUTPUT.as_posix()]['query_provenance_sha256'] = hashlib.sha256(args.wmql_provenance.read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print("PASS website SVG and asset receipt; paper source unchanged")


if __name__ == "__main__":
    main()
