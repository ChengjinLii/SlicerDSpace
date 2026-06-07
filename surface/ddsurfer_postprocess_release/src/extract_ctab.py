#!/usr/bin/env python3

import argparse
import os
import sys

import nibabel as nib


def extract_and_save_ctab(annot_file_path, output_ctab_path):
    """Extract and save a FreeSurfer-style CTAB from a .annot file."""
    if not os.path.exists(annot_file_path):
        print(f"ERROR: Annotation file not found: {annot_file_path}")
        return False

    try:
        _, ctab_array, names = nib.freesurfer.io.read_annot(annot_file_path)
        n_entries = min(len(ctab_array), len(names))
        if n_entries == 0:
            print(f"ERROR: No entries found in annot file: {annot_file_path}")
            return False

        print(f"INFO: Loaded {len(names)} structures and {len(ctab_array)} ctab rows")
        if len(names) != len(ctab_array):
            print(f"WARN: Mismatch between names and ctab rows; using {n_entries} entries")

        os.makedirs(os.path.dirname(output_ctab_path), exist_ok=True)

        with open(output_ctab_path, "w") as f:
            f.write(f"# Colortable extracted from {os.path.basename(annot_file_path)}\n")
            f.write(f"# NEntries {n_entries}\n")
            f.write("# TableStart\n")
            for i in range(n_entries):
                row = ctab_array[i]
                struct_name = names[i].decode("utf-8")

                try:
                    label_id = int(row[0])
                    r_val = int(row[1])
                    g_val = int(row[2])
                    b_val = int(row[3])
                except Exception:
                    print(f"WARN: Skipping malformed CTAB row {i}")
                    continue

                a_val_output = 0
                f.write(
                    f"{label_id:<5} {struct_name:<40} {r_val:>3} {g_val:>3} {b_val:>3} {a_val_output:>3}\n"
                )
            f.write("# TableEnd\n")
        print(f"INFO: CTAB saved to: {output_ctab_path}")
        return True
    except Exception as exc:
        print(f"ERROR: Failed to extract CTAB: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Extract a FreeSurfer CTAB (.ctab) from an annotation (.annot)."
    )
    parser.add_argument("--annot_file", required=True, help="Input .annot file path.")
    parser.add_argument("--output_ctab", required=True, help="Output .ctab file path.")
    args = parser.parse_args()

    if not extract_and_save_ctab(args.annot_file, args.output_ctab):
        sys.exit(1)


if __name__ == "__main__":
    main()
