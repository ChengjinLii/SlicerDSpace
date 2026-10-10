#!/usr/bin/env python3

import argparse
import os
import sys
import numpy as np
import trimesh
import nibabel as nib
from collections import OrderedDict

def log_step(message):
    """Print a formatted step message."""
    print(f"\n{'=' * 20} {message} {'=' * 20}")

def load_and_prepare_mesh(file_path):
    """Load an STL file and weld vertices to remove duplicates."""
    print(f"INFO: Loading and preprocessing mesh: {os.path.basename(file_path)}")
    if not os.path.exists(file_path):
        print(f"ERROR: File not found at {file_path}", file=sys.stderr)
        return None
    try:
        mesh = trimesh.load_mesh(file_path, process=False)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(list(mesh.geometry.values()))

        print(f"  -> Vertices before welding: {len(mesh.vertices)}")
        mesh.merge_vertices()
        print(f"  -> Vertices after welding: {len(mesh.vertices)}")
        return mesh
    except Exception as e:
        print(f"ERROR: Failed to load or process file {file_path}: {e}", file=sys.stderr)
        return None

def convert_to_freesurfer_format(mesh, output_path, reference_img):
    """Save a trimesh object to a spatially aligned FreeSurfer surface."""
    log_step(f"Converting to FreeSurfer format: {os.path.basename(output_path)}")

    # --- Step 1: Get coordinates and reference center ---
    # Input STL coordinates are assumed to be in the correct RAS orientation.
    vertices_ras = mesh.vertices

    # Get the header info from the reference MRI, especially its center (c_ras)
    vol_vox2ras = reference_img.header.get_vox2ras()
    volume_center_ras = vol_vox2ras[:3, 3]

    # --- Step 2: Coordinate transformation ---
    # Calculate vertex coordinates relative to the volume center.
    final_vertices = vertices_ras - volume_center_ras

    print("INFO: Applied center-based coordinate transform.")

    # --- Step 3: Build a self-consistent header ---
    volume_info = OrderedDict([
        ('head', np.array([2, 0, 20], dtype=np.int32)),
        ('valid', '1  # volume info valid'),
        # getattr is a safe way to call get_filename(), which may not exist
        ('filename', os.path.basename(getattr(reference_img, 'get_filename', lambda: 'unknown')())),
        ('volume', np.array(reference_img.shape, dtype=np.int32)),
        ('voxelsize', np.array(reference_img.header.get_zooms(), dtype=np.float32)),
        ('xras', vol_vox2ras[:3, 0].astype(np.float32)),
        ('yras', vol_vox2ras[:3, 1].astype(np.float32)),
        ('zras', vol_vox2ras[:3, 2].astype(np.float32)),
        # Use volume center as c_ras, consistent with relative vertex coordinates.
        ('cras', volume_center_ras.astype(np.float32))
    ])

    # --- Step 4: Save the file ---
    print(f"Saving FreeSurfer surface to: {output_path}")
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        nib.freesurfer.io.write_geometry(output_path, final_vertices, mesh.faces, volume_info=volume_info)
        print("INFO: File saved successfully.")
    except Exception as e:
        print(f"ERROR: Failed to save FreeSurfer surface: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description="An integrated tool to convert STL surfaces to spatially-aligned, self-consistent FreeSurfer native format.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # --- New, standard argument structure ---
    parser.add_argument("--subject_id", required=True, help="Subject ID (e.g., '100307').")
    parser.add_argument("--subjects_dir", required=True, help="Path to the directory containing all subject folders (the FreeSurfer SUBJECTS_DIR).")
    parser.add_argument("--mode", choices=["left", "right", "whole"], default="whole", help="Hemisphere selection for STL conversion.")

    args = parser.parse_args()

    # --- Derive all paths from the main arguments ---
    subject_path = os.path.join(args.subjects_dir, args.subject_id)
    input_dir = os.path.join(subject_path, "surf") # Assuming 'surf1' is the source STL directory
    out_dir = os.path.join(subject_path, "surf")   # Standard output directory
    ref_mri_dir = os.path.join(subject_path, "mri")

    # --- Smartly find the reference MRI file ---
    ref_mri_path = os.path.join(ref_mri_dir, 'brain.mgz')
    if not os.path.exists(ref_mri_path):
        print(f"INFO: 'brain.mgz' not found. Trying 'orig.mgz'...")
        ref_mri_path = os.path.join(ref_mri_dir, 'orig.mgz')
        if not os.path.exists(ref_mri_path):
            print(f"FATAL ERROR: Could not find 'brain.mgz' or 'orig.mgz' in {ref_mri_dir} to use as a reference.", file=sys.stderr)
            sys.exit(1)

    print(f"INFO: Using reference MRI: {ref_mri_path}")
    ref_img = nib.load(ref_mri_path)

    # --- Define the files to process ---
    surfaces_to_process = [
        ("predicted_wm_lh_orig.stl", "lh.white"),
        ("predicted_pial_lh_orig.stl", "lh.pial"),
        ("predicted_wm_rh_orig.stl", "rh.white"),
        ("predicted_pial_rh_orig.stl", "rh.pial")
    ]
    if args.mode == "left":
        surfaces_to_process = [item for item in surfaces_to_process if "_lh_" in item[0]]
    elif args.mode == "right":
        surfaces_to_process = [item for item in surfaces_to_process if "_rh_" in item[0]]

    # --- Process each file ---
    for input_basename, output_basename in surfaces_to_process:
        input_stl_file = os.path.join(input_dir, f"{args.subject_id}_{input_basename}")
        output_fs_file = os.path.join(out_dir, output_basename)

        if not os.path.exists(input_stl_file):
            print(f"\nWARNING: Input file not found, skipping: {input_stl_file}")
            continue

        mesh = load_and_prepare_mesh(input_stl_file)
        if mesh:
            convert_to_freesurfer_format(mesh, output_fs_file, ref_img)

    print("\nAll conversion tasks completed.")

if __name__ == "__main__":
    # Example usage:
    # python convert_stl_to_fs.py --subject_id 100307 --subjects_dir /path/to/subjects
    main()
