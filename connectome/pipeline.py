"""Connectome construction planning and dependency checks."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional


SUPPORTED_TRACTOGRAPHY_EXTENSIONS = {".trk", ".tck", ".vtk", ".vtp"}
SUPPORTED_PARCELLATION_SUFFIXES = (".nii", ".nii.gz", ".nrrd", ".mgz")


@dataclass(frozen=True)
class ConnectomeConfig:
    subject_id: str
    tractography_path: Path
    parcellation_path: Path
    output_dir: Path
    metric: str = "streamline_count"
    node_source: str = "ddparcel"
    symmetric: bool = True
    execute: bool = False


@dataclass(frozen=True)
class ConnectomeResult:
    subject_id: str
    output_dir: Path
    matrix_path: Path
    nodes_path: Path
    manifest_path: Path
    qc_path: Path
    backend_status: dict[str, object]
    executed: bool
    return_code: Optional[int] = None


def _emit(message: str, log: Optional[Callable[[str], None]] = None) -> None:
    if log:
        log(message)


def _file_info(path: Path) -> dict[str, object]:
    expanded = path.expanduser()
    if not expanded.exists():
        return {"path": expanded.as_posix(), "exists": False}
    stat = expanded.stat()
    return {
        "path": expanded.resolve().as_posix(),
        "exists": True,
        "is_file": expanded.is_file(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _has_supported_parcellation_suffix(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(suffix) for suffix in SUPPORTED_PARCELLATION_SUFFIXES)


def inspect_connectome_backends() -> dict[str, object]:
    """Inspect optional backends for tractography-to-parcellation assignment."""

    status: dict[str, object] = {
        "tck2connectome": shutil.which("tck2connectome"),
        "python": {
            "nibabel": False,
            "numpy": False,
            "vtk": False,
        },
    }
    for module_name in ("nibabel", "numpy", "vtk"):
        try:
            __import__(module_name)
        except Exception:
            status["python"][module_name] = False  # type: ignore[index]
        else:
            status["python"][module_name] = True  # type: ignore[index]
    return status


def _load_label_volume(path: Path):
    try:
        import nibabel as nib
        import numpy as np
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Connectome execution requires nibabel and numpy for label lookup.") from exc

    image = nib.load(path.as_posix())
    data = np.asarray(image.dataobj)
    inverse_affine = np.linalg.inv(image.affine)
    return data, inverse_affine


def _label_at_point(point, data, inverse_affine) -> int:
    import numpy as np

    voxel = np.rint((inverse_affine @ np.array([point[0], point[1], point[2], 1.0]))[:3]).astype(int)
    if np.any(voxel < 0) or np.any(voxel >= np.array(data.shape[:3])):
        return 0
    return int(data[tuple(voxel)])


def _iter_trk_tck_streamlines(path: Path) -> Iterable[object]:
    try:
        import nibabel as nib
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("TRK/TCK connectome execution requires nibabel.") from exc

    tractogram = nib.streamlines.load(path.as_posix())
    yield from tractogram.streamlines


def _iter_vtk_streamlines(path: Path) -> Iterable[list[tuple[float, float, float]]]:
    try:
        import vtk  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        if path.suffix.lower() == ".vtk":
            yield from _iter_legacy_vtk_polydata_streamlines(path)
            return
        raise RuntimeError("VTP connectome execution requires the vtk Python module.") from exc

    if path.suffix.lower() == ".vtp":
        reader = vtk.vtkXMLPolyDataReader()
    else:
        reader = vtk.vtkPolyDataReader()
    reader.SetFileName(path.as_posix())
    reader.Update()
    polydata = reader.GetOutput()
    points = polydata.GetPoints()
    lines = polydata.GetLines()
    lines.InitTraversal()
    id_list = vtk.vtkIdList()
    while lines.GetNextCell(id_list):
        streamline: list[tuple[float, float, float]] = []
        for index in range(id_list.GetNumberOfIds()):
            streamline.append(points.GetPoint(id_list.GetId(index)))
        if streamline:
            yield streamline


def _read_vtk_ascii_token(blob: bytes, offset: int) -> tuple[str, int]:
    while offset < len(blob) and chr(blob[offset]).isspace():
        offset += 1
    start = offset
    while offset < len(blob) and not chr(blob[offset]).isspace():
        offset += 1
    return blob[start:offset].decode("ascii"), offset


def _iter_legacy_vtk_polydata_streamlines(path: Path) -> Iterable[list[tuple[float, float, float]]]:
    """Read endpoints from legacy VTK POLYDATA without the optional vtk module.

    This supports the common ASCII and BINARY legacy VTK layout used by UKF/WMA
    tractography. It intentionally handles only POINTS plus LINES/POLYLINES.
    """

    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Legacy VTK connectome fallback requires numpy.") from exc

    blob = path.read_bytes()
    header = blob[:512].decode("ascii", errors="ignore").upper()
    is_binary = "\nBINARY\n" in header
    points_marker = blob.find(b"POINTS ")
    if points_marker < 0:
        raise RuntimeError(f"Legacy VTK file has no POINTS section: {path}")
    token, offset = _read_vtk_ascii_token(blob, points_marker)
    if token != "POINTS":
        raise RuntimeError(f"Unexpected VTK POINTS marker: {token}")
    n_points_token, offset = _read_vtk_ascii_token(blob, offset)
    n_points = int(n_points_token)
    point_type, offset = _read_vtk_ascii_token(blob, offset)
    while offset < len(blob) and blob[offset] in b" \t\r\n":
        offset += 1

    if point_type.lower() not in {"float", "double"}:
        raise RuntimeError(f"Unsupported VTK point type: {point_type}")
    dtype = ">f4" if point_type.lower() == "float" else ">f8"
    if is_binary:
        count = n_points * 3
        points = np.frombuffer(blob, dtype=dtype, count=count, offset=offset).reshape((n_points, 3))
        offset += points.nbytes
    else:
        text_start = offset
        lines_marker = blob.find(b"\nLINES ", text_start)
        if lines_marker < 0:
            lines_marker = blob.find(b"\nPOLYLINES ", text_start)
        if lines_marker < 0:
            raise RuntimeError(f"Legacy VTK file has no LINES section: {path}")
        points = np.fromstring(blob[text_start:lines_marker].decode("ascii"), sep=" ").reshape((n_points, 3))
        offset = lines_marker + 1

    if blob[offset : offset + len(b"LINES ")].upper() == b"LINES ":
        lines_marker = offset
        marker_len = len(b"LINES ")
    elif blob[offset : offset + len(b"POLYLINES ")].upper() == b"POLYLINES ":
        lines_marker = offset
        marker_len = len(b"POLYLINES ")
    else:
        lines_marker = blob.find(b"\nLINES ", offset)
        marker_len = len(b"\nLINES ")
        if lines_marker < 0:
            lines_marker = blob.find(b"\nPOLYLINES ", offset)
            marker_len = len(b"\nPOLYLINES ")
    if lines_marker < 0:
        raise RuntimeError(f"Legacy VTK file has no LINES/POLYLINES section: {path}")
    offset = lines_marker + marker_len
    n_lines_token, offset = _read_vtk_ascii_token(blob, offset)
    n_lines = int(n_lines_token)
    total_size, offset = _read_vtk_ascii_token(blob, offset)
    n_indices = int(total_size)
    while offset < len(blob) and blob[offset] in b" \t\r\n":
        offset += 1

    if blob[offset : offset + len(b"OFFSETS")].upper() == b"OFFSETS":
        _, offset = _read_vtk_ascii_token(blob, offset)
        offset_type, offset = _read_vtk_ascii_token(blob, offset)
        while offset < len(blob) and blob[offset] in b" \t\r\n":
            offset += 1
        offset_dtype = ">i8" if offset_type.lower().endswith("int64") else ">i4"
        offsets = np.frombuffer(blob, dtype=offset_dtype, count=n_lines, offset=offset)
        offset += offsets.nbytes
        while offset < len(blob) and blob[offset] in b" \t\r\n":
            offset += 1
        connectivity_marker, offset = _read_vtk_ascii_token(blob, offset)
        if connectivity_marker.upper() != "CONNECTIVITY":
            raise RuntimeError(f"Expected VTK CONNECTIVITY section, got: {connectivity_marker}")
        connectivity_type, offset = _read_vtk_ascii_token(blob, offset)
        while offset < len(blob) and blob[offset] in b" \t\r\n":
            offset += 1
        connectivity_dtype = ">i8" if connectivity_type.lower().endswith("int64") else ">i4"
        connectivity = np.frombuffer(blob, dtype=connectivity_dtype, count=n_indices, offset=offset)
        for index in range(n_lines):
            start = int(offsets[index])
            end = int(offsets[index + 1]) if index + 1 < n_lines else n_indices
            if end - start >= 2:
                first = int(connectivity[start])
                last = int(connectivity[end - 1])
                yield [tuple(float(value) for value in points[first]), tuple(float(value) for value in points[last])]
        return

    if is_binary:
        cells = np.frombuffer(blob, dtype=">i4", count=n_indices, offset=offset)
        cursor = 0
        for _ in range(n_lines):
            n_cell_points = int(cells[cursor])
            cursor += 1
            if n_cell_points >= 2:
                first = int(cells[cursor])
                last = int(cells[cursor + n_cell_points - 1])
                yield [tuple(float(value) for value in points[first]), tuple(float(value) for value in points[last])]
            cursor += n_cell_points
    else:
        numbers = np.fromstring(blob[offset:].decode("ascii", errors="ignore"), sep=" ", dtype=np.int64)
        cursor = 0
        for _ in range(n_lines):
            n_cell_points = int(numbers[cursor])
            cursor += 1
            if n_cell_points >= 2:
                first = int(numbers[cursor])
                last = int(numbers[cursor + n_cell_points - 1])
                yield [tuple(float(value) for value in points[first]), tuple(float(value) for value in points[last])]
            cursor += n_cell_points


def _iter_streamlines(path: Path) -> Iterable[object]:
    suffix = path.suffix.lower()
    if suffix in {".trk", ".tck"}:
        yield from _iter_trk_tck_streamlines(path)
        return
    if suffix in {".vtk", ".vtp"}:
        yield from _iter_vtk_streamlines(path)
        return
    raise ValueError(f"Unsupported tractography format: {suffix}")


def _write_nodes_table(path: Path, labels: Iterable[int]) -> int:
    unique_labels = sorted({int(label) for label in labels if int(label) != 0})
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write("node_id\tlabel\tname\n")
        for index, label in enumerate(unique_labels, start=1):
            stream.write(f"{index}\t{label}\tROI-{label}\n")
    return len(unique_labels)


def _write_python_connectome(config: ConnectomeConfig, matrix_path: Path, nodes_path: Path) -> dict[str, int]:
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Connectome execution requires numpy.") from exc

    data, inverse_affine = _load_label_volume(config.parcellation_path.expanduser().resolve())
    all_labels = np.unique(data)
    node_count = _write_nodes_table(nodes_path, (int(label) for label in all_labels))
    edge_counts: Counter[tuple[int, int]] = Counter()
    skipped_streamlines = 0
    total_streamlines = 0

    for streamline in _iter_streamlines(config.tractography_path.expanduser().resolve()):
        total_streamlines += 1
        if len(streamline) < 2:
            skipped_streamlines += 1
            continue
        source = _label_at_point(streamline[0], data, inverse_affine)
        target = _label_at_point(streamline[-1], data, inverse_affine)
        if source == 0 or target == 0:
            skipped_streamlines += 1
            continue
        edge = tuple(sorted((source, target))) if config.symmetric else (source, target)
        edge_counts[edge] += 1

    with matrix_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["source_node", "target_node", config.metric])
        for (source, target), count in sorted(edge_counts.items()):
            writer.writerow([source, target, count])

    return {
        "node_count": node_count,
        "edge_count": len(edge_counts),
        "streamline_count_total": total_streamlines,
        "streamline_count_assigned": sum(edge_counts.values()),
        "streamline_count_skipped": skipped_streamlines,
    }


def build_tck2connectome_command(config: ConnectomeConfig, matrix_path: Path) -> tuple[str, ...]:
    command = shutil.which("tck2connectome")
    if command is None:
        raise RuntimeError("tck2connectome was not found on PATH.")
    cmd = [
        command,
        config.tractography_path.expanduser().resolve().as_posix(),
        config.parcellation_path.expanduser().resolve().as_posix(),
        matrix_path.as_posix(),
        "-stat_edge",
        "sum",
    ]
    if config.symmetric:
        cmd.append("-symmetric")
    return tuple(cmd)


def _validate_config(config: ConnectomeConfig) -> None:
    if not config.subject_id.strip():
        raise ValueError("subject_id is required.")
    tractography = config.tractography_path.expanduser()
    parcellation = config.parcellation_path.expanduser()
    if not tractography.is_file():
        raise FileNotFoundError(f"Tractography dependency does not exist: {tractography}")
    if tractography.suffix.lower() not in SUPPORTED_TRACTOGRAPHY_EXTENSIONS:
        raise ValueError(f"Unsupported tractography format: {tractography.suffix}")
    if not parcellation.is_file():
        raise FileNotFoundError(f"DDParcel/parcellation dependency does not exist: {parcellation}")
    if not _has_supported_parcellation_suffix(parcellation):
        raise ValueError(f"Unsupported parcellation format: {parcellation.name}")
    if config.metric != "streamline_count":
        raise ValueError("Only metric='streamline_count' is currently planned.")


def run_connectome(config: ConnectomeConfig, *, log: Optional[Callable[[str], None]] = None) -> ConnectomeResult:
    """Prepare connectome outputs that explicitly depend on tractography and DDParcel."""

    _validate_config(config)
    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{config.subject_id}-connectome-{config.metric}"
    matrix_path = output_dir / f"{stem}.csv"
    nodes_path = output_dir / f"{config.subject_id}-connectome-nodes.tsv"
    manifest_path = output_dir / f"{stem}_manifest.json"
    qc_path = output_dir / f"{stem}_qc.json"

    backend_status = inspect_connectome_backends()

    manifest = {
        "kind": "connectome",
        "version": 1,
        "subject_id": config.subject_id,
        "executed": False,
        "status": "planned",
        "metric": config.metric,
        "node_source": config.node_source,
        "symmetric": config.symmetric,
        "backend": backend_status,
        "dependencies": {
            "tractography": _file_info(config.tractography_path),
            "ddparcel_parcellation": _file_info(config.parcellation_path),
        },
        "outputs": {
            "matrix": matrix_path.as_posix(),
            "nodes": nodes_path.as_posix(),
            "qc": qc_path.as_posix(),
        },
    }
    qc = {
        "subject_id": config.subject_id,
        "status": "planned",
        "executed": False,
        "metric": config.metric,
        "node_count": None,
        "edge_count": None,
        "streamline_count_total": None,
        "streamline_count_assigned": None,
        "streamline_count_skipped": None,
        "return_code": None,
        "elapsed_seconds": 0.0,
        "backend": "planned",
        "error": None,
    }
    return_code: Optional[int] = None
    execution_error: Optional[str] = None
    start_time = time.monotonic()
    if config.execute:
        manifest["executed"] = True
        manifest["status"] = "running"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            if config.tractography_path.suffix.lower() == ".tck" and backend_status["tck2connectome"]:
                command = build_tck2connectome_command(config, matrix_path)
                manifest["command"] = list(command)
                completed = subprocess.run(command, check=True)
                return_code = completed.returncode
                _write_nodes_table(nodes_path, [])
                qc.update({"backend": "mrtrix3.tck2connectome"})
            else:
                summary = _write_python_connectome(config, matrix_path, nodes_path)
                qc.update(summary)
                qc.update({"backend": "python.endpoint_labels"})
                return_code = 0
        except Exception as exc:
            execution_error = str(exc)
            return_code = 1
        finally:
            elapsed_seconds = time.monotonic() - start_time
            qc.update(
                {
                    "status": "failed" if execution_error else "completed",
                    "executed": True,
                    "return_code": return_code,
                    "elapsed_seconds": elapsed_seconds,
                    "error": execution_error,
                }
            )
    else:
        with matrix_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["source_node", "target_node", config.metric])
        try:
            data, _ = _load_label_volume(config.parcellation_path.expanduser().resolve())
            _write_nodes_table(nodes_path, data.ravel())
        except Exception:
            nodes_path.write_text("node_id\tlabel\tname\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    qc_path.write_text(json.dumps(qc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if execution_error is not None:
        raise RuntimeError(f"Connectome execution failed: {execution_error}")
    _emit(f"[Connectome] Prepared connectome scaffold: {manifest_path}", log)

    return ConnectomeResult(
        subject_id=config.subject_id,
        output_dir=output_dir,
        matrix_path=matrix_path,
        nodes_path=nodes_path,
        manifest_path=manifest_path,
        qc_path=qc_path,
        backend_status=backend_status,
        executed=bool(config.execute),
        return_code=return_code,
    )
