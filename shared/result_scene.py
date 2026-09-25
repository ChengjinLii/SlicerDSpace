"""Manifest-scoped result selection and ownership-aware Slicer scene management."""

from pathlib import Path
import json

PREFIX = "SlicerDDSurfer."
SUFFIXES = (".nii.gz", ".nii", ".mgz", ".csv", ".tsv", ".stl", ".vtk", ".vtp", ".trk", ".tck")


def source_stamp(path):
    stat = Path(path).stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def recorded_qc_summary(manifest):
    """Report recorded QC states without treating execution status as QC."""
    counts = {"passed": 0, "issues": 0, "unavailable": 0}
    for task in manifest.get("tasks", []) or []:
        if not isinstance(task, dict) or task.get("status") in {"planned", "blocked", "cancelled"}:
            continue
        value = task.get("qc_path") or (task.get("outputs") or {}).get("qc")
        try:
            if not value or not Path(value).is_absolute():
                raise ValueError("Missing absolute QC path")
            record = json.loads(Path(value).read_text())
            status = record.get("status")
            key = "passed" if status in {"passed", "completed"} else "issues" if status in {"failed", "partial_failed", "warning"} else "unavailable"
            counts[key] += 1
        except (OSError, ValueError, TypeError, AttributeError):
            counts["unavailable"] += 1
    return counts


def result_candidates(manifest):
    candidates, skipped, seen = [], [], set()
    for task in manifest.get("tasks", []) or []:
        if not isinstance(task, dict):
            continue
        name = str(task.get("name") or "task")
        reused = task.get("status") == "skipped" and task.get("reason") in {
            "completed outputs found", "completed DTI microstructure outputs found",
            "completed Free Water outputs found", "completed NODDI outputs found",
        }
        if task.get("status") not in {"completed", "reused"} and not reused:
            skipped.append({"label": name, "reason": "Task is not completed or explicitly reused"})
            continue
        if name.startswith("preprocessing."):
            continue
        for key, value in (task.get("outputs") or {}).items():
            if not isinstance(value, str) or not value:
                continue
            path = Path(value).expanduser()
            if not path.is_absolute():
                skipped.append({"path": value, "reason": "Relative output path needs an explicit source root"})
                continue
            if not path.name.lower().endswith(SUFFIXES):
                continue
            if path.name.endswith("_orig.stl") and path.with_name(path.name.replace("_orig.stl", ".stl")).is_file():
                continue
            identity = str(path.resolve())
            if identity in seen:
                continue
            seen.add(identity)
            if not path.is_file():
                skipped.append({"path": value, "reason": "Manifest output is missing"})
                continue
            # Prefer small anatomical/scalar products before expensive tractograms.
            priority = 2 if path.suffix in {".tck", ".trk", ".vtk", ".vtp"} else 1 if path.suffix == ".stl" else 0
            candidates.append({"path": identity, "label": name + "_" + str(key), "key": str(key), "product": name, "priority": priority})
    return sorted(candidates, key=lambda item: (item["priority"], item["label"])), skipped


def owned_nodes(slicer, run_id):
    return [node for node in slicer.util.getNodesByClass("vtkMRMLDisplayableNode")
            if node.GetAttribute(PREFIX + "Run") == run_id]


def clear_run(slicer, run_id):
    nodes = owned_nodes(slicer, run_id)
    for node in nodes:
        slicer.mrmlScene.RemoveNode(node)
    return len(nodes)


def register_node(slicer, node, run_id, subject, run_name, product, source):
    for key, value in {"Run": run_id, "Subject": subject, "Product": product, "SourcePath": source,
                       "SourceStamp": source_stamp(source)}.items():
        node.SetAttribute(PREFIX + key, value)
    hierarchy = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)

    def folder(parent, name, key):
        import vtk
        children = vtk.vtkIdList()
        hierarchy.GetItemChildren(parent, children)
        for index in range(children.GetNumberOfIds()):
            item = children.GetId(index)
            if hierarchy.GetItemAttribute(item, PREFIX + "FolderKey") == key:
                return item
        item = hierarchy.CreateFolderItem(parent, name)
        hierarchy.SetItemAttribute(item, PREFIX + "FolderKey", key)
        return item

    parent = folder(hierarchy.GetSceneItemID(), subject, "subject:" + subject)
    parent = folder(parent, run_name, "run:" + run_id)
    parent = folder(parent, product, "product:" + product)
    hierarchy.SetItemParent(hierarchy.GetItemByDataNode(node), parent)


def scalar_preset(node, label):
    """Stable conventional display ranges; scientific voxel data are unchanged."""
    display = node.GetDisplayNode()
    if display is None:
        return
    label = label.lower()
    if "md" in label or "ad" in label or "rd" in label:
        display.SetAndObserveColorNodeID("vtkMRMLColorTableNodeGrey")
    elif any(token in label for token in ("_fa", "_ndi", "_odi", "fraction")):
        display.SetAutoWindowLevel(False)
        display.SetWindowLevel(1.0, 0.5)
