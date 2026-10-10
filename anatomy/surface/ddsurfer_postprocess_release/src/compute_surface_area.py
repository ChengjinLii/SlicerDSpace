#!/usr/bin/env python3

import argparse
import os
import sys

import nibabel as nib
import numpy as np
import trimesh


def load_fs_surface(surface_path):
    """Load a FreeSurfer surface file."""
    print(f"[INFO] Loading FreeSurfer surface: {surface_path}")
    if not os.path.exists(surface_path):
        print(f"[ERROR] Surface file not found: {surface_path}")
        return None, None
    try:
        vertices, faces = nib.freesurfer.io.read_geometry(surface_path)
        print(f"[INFO] Loaded {len(vertices)} vertices and {len(faces)} faces.")
        return vertices, faces
    except Exception as exc:
        print(f"[ERROR] Failed to load surface {surface_path}: {exc}")
        return None, None


def save_fs_overlay(output_path, data_per_vertex, vertices, faces):
    """Save per-vertex data as a FreeSurfer overlay file."""
    print(f"[INFO] Saving FreeSurfer overlay: {output_path}")
    if data_per_vertex is None or len(data_per_vertex) != len(vertices):
        print(
            "[ERROR] Data length does not match vertex count "
            f"({len(data_per_vertex) if data_per_vertex is not None else 'None'} != {len(vertices)})."
        )
        return False

    num_verts = len(vertices)
    num_faces = len(faces)
    header = np.array([num_verts, num_faces, 1], dtype=np.int32)
    magic_bytes = (16777215).to_bytes(3, byteorder="big")

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(magic_bytes)
            f.write(header.byteswap().tobytes())
            f.write(data_per_vertex.astype(np.float32).byteswap().tobytes())
        print(f"[INFO] Overlay saved: {output_path}")
        return True
    except Exception as exc:
        print(f"[ERROR] Failed to save overlay {output_path}: {exc}")
        return False


def calculate_and_save_vertex_area(surface_path, output_area_path):
    """Compute per-vertex surface area and save to .area file."""
    vertices, faces = load_fs_surface(surface_path)
    if vertices is None or faces is None:
        return False

    print("[INFO] Building trimesh object for area computation...")
    try:
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    except Exception as exc:
        print(f"[ERROR] Failed to build trimesh object: {exc}")
        return False

    print("[INFO] Computing per-vertex area...")
    try:
        vertex_areas = np.zeros(len(mesh.vertices))
        face_areas = mesh.area_faces
        np.add.at(vertex_areas, mesh.faces[:, 0], face_areas / 3.0)
        np.add.at(vertex_areas, mesh.faces[:, 1], face_areas / 3.0)
        np.add.at(vertex_areas, mesh.faces[:, 2], face_areas / 3.0)
        print(
            "[INFO] Area range: "
            f"min={np.min(vertex_areas):.6f}, max={np.max(vertex_areas):.6f}, total={np.sum(vertex_areas):.4f}"
        )
        print(f"[INFO] Trimesh total surface area: {mesh.area:.4f}")
    except Exception as exc:
        print(f"[ERROR] Failed to compute vertex area: {exc}")
        return False

    return save_fs_overlay(output_area_path, vertex_areas, vertices, faces)


def main():
    parser = argparse.ArgumentParser(
        description="Compute per-vertex surface area from a FreeSurfer surface."
    )
    parser.add_argument("--surf", required=True, help="Input surface (e.g., lh.white, rh.pial).")
    parser.add_argument("--out_area", required=True, help="Output .area file path.")
    args = parser.parse_args()

    print("\n--- [ Config ] ---")
    print(f"Input surface: {args.surf}")
    print(f"Output area:   {args.out_area}")

    print("\n--- [ Running ] ---")
    success = calculate_and_save_vertex_area(args.surf, args.out_area)
    if success:
        print("\n[DONE] Vertex area completed.")
    else:
        print("\n[FAILED] Vertex area failed. Check logs above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
