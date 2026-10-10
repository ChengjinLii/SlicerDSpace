#!/usr/bin/env python3

import argparse
import os
import sys
import time

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
    num_faces = len(faces) if faces is not None else 0
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


def calculate_thickness(white_surf_path, pial_surf_path, output_thickness_path):
    """Compute cortical thickness via point-to-surface distance."""
    print(f"\n--- [ Thickness: {os.path.basename(output_thickness_path)} ] ---")
    vertices_white, faces_white = load_fs_surface(white_surf_path)
    vertices_pial, faces_pial = load_fs_surface(pial_surf_path)

    if vertices_white is None or faces_white is None or vertices_pial is None or faces_pial is None:
        print("[ERROR] Failed to load white or pial surface. Cannot compute thickness.")
        return False

    if len(vertices_white) != len(vertices_pial):
        print(
            f"[WARN] Vertex count mismatch: white={len(vertices_white)} pial={len(vertices_pial)}. "
            "Distance computation will proceed."
        )

    print("[INFO] Building trimesh objects...")
    try:
        white_mesh = trimesh.Trimesh(vertices=vertices_white, faces=faces_white, process=False)
        pial_mesh = trimesh.Trimesh(vertices=vertices_pial, faces=faces_pial, process=False)
    except Exception as exc:
        print(f"[ERROR] Failed to build trimesh objects: {exc}")
        return False

    print("[INFO] Computing closest-point distances (this may take a while)...")
    start_time = time.time()
    try:
        _, distances, _ = trimesh.proximity.closest_point(pial_mesh, white_mesh.vertices)
        elapsed = time.time() - start_time
        print(f"[INFO] Thickness computed in {elapsed:.2f}s")
        print(
            f"[INFO] Range: min={np.min(distances):.4f}, max={np.max(distances):.4f}, "
            f"mean={np.mean(distances):.4f}"
        )
    except Exception as exc:
        print(f"[ERROR] Distance computation failed: {exc}")
        return False

    return save_fs_overlay(output_thickness_path, distances, vertices_white, faces_white)


def calculate_vertex_areas(surface_path, output_area_path):
    """Compute per-vertex area for a surface."""
    print(f"\n--- [ Vertex Area: {os.path.basename(output_area_path)} ] ---")
    vertices, faces = load_fs_surface(surface_path)
    if vertices is None or faces is None:
        print("[ERROR] Failed to load surface. Cannot compute area.")
        return False

    print("[INFO] Building trimesh object...")
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
        description="Compute FreeSurfer thickness and/or per-vertex surface area."
    )
    parser.add_argument("--subjects_dir", required=True, help="FreeSurfer SUBJECTS_DIR path.")
    parser.add_argument("--subject_id", required=True, help="Subject ID.")
    parser.add_argument("--hemi", required=True, choices=["lh", "rh"], help="Hemisphere.")
    parser.add_argument("--calc_thickness", action="store_true", help="Compute cortical thickness.")
    parser.add_argument("--calc_area", action="store_true", help="Compute per-vertex area.")
    args = parser.parse_args()

    print("\n--- [ Config ] ---")
    print(f"Subjects Dir: {args.subjects_dir}")
    print(f"Subject ID:   {args.subject_id}")
    print(f"Hemisphere:   {args.hemi}")
    print(f"Thickness:    {'yes' if args.calc_thickness else 'no'}")
    print(f"Area:         {'yes' if args.calc_area else 'no'}")

    surf_dir = os.path.join(args.subjects_dir, args.subject_id, "surf")
    white_surf_path = os.path.join(surf_dir, f"{args.hemi}.white")
    pial_surf_path = os.path.join(surf_dir, f"{args.hemi}.pial")
    thickness_path = os.path.join(surf_dir, f"{args.hemi}.thickness")
    area_white_path = os.path.join(surf_dir, f"{args.hemi}.area")
    area_pial_path = os.path.join(surf_dir, f"{args.hemi}.area.pial")

    print("\n--- [ Running ] ---")
    overall_success = True
    tasks_executed = 0

    if args.calc_thickness:
        tasks_executed += 1
        if os.path.exists(white_surf_path) and os.path.exists(pial_surf_path):
            if not calculate_thickness(white_surf_path, pial_surf_path, thickness_path):
                overall_success = False
        else:
            print("[ERROR] Missing .white or .pial surface for thickness computation.")
            overall_success = False

    if args.calc_area:
        tasks_executed += 1
        area_ok = True
        if os.path.exists(white_surf_path):
            if not calculate_vertex_areas(white_surf_path, area_white_path):
                area_ok = False
        else:
            print("[ERROR] Missing .white surface for area computation.")
            area_ok = False

        if os.path.exists(pial_surf_path):
            if not calculate_vertex_areas(pial_surf_path, area_pial_path):
                area_ok = False
        else:
            print("[ERROR] Missing .pial surface for area computation.")
            area_ok = False

        if not area_ok:
            overall_success = False

    if tasks_executed == 0:
        print("[WARN] No tasks requested. Use --calc_thickness and/or --calc_area.")
        overall_success = False

    if overall_success:
        print("\n[DONE] Requested computations completed.")
    else:
        print("\n[FAILED] One or more steps failed. Check logs above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
