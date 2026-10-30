#!/usr/bin/env python3
"""Verify the reviewed website and module assets without manuscript sources."""
import argparse
import hashlib
import json
from pathlib import Path

def check(root):
    receipt = json.loads((root / "docs/website/published_assets.json").read_text())
    failures = [name for name, entry in receipt["files"].items()
                if not (root / name).is_file()
                or hashlib.sha256((root / name).read_bytes()).hexdigest() != entry["sha256"]]
    if failures:
        raise ValueError("Published assets differ from their reviewed receipt: " + ", ".join(failures))
    return len(receipt["files"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify without writing (the default)")
    parser.parse_args()
    count = check(Path(__file__).resolve().parents[1])
    print(f"PASS {count} published assets match their reviewed hashes")
