"""Manifest-scoped result selection and ownership-aware Slicer scene management."""

from pathlib import Path
import json

PREFIX = "SlicerDDSurfer."
SUFFIXES = (".nii.gz", ".nii", ".mgz", ".csv", ".tsv", ".stl", ".vtk", ".vtp", ".trk", ".tck")


def result_file_suffix(path):
    """Compound extensions must not absorb dots in product/subject filenames."""
    name = Path(path).name.lower()
    return next((suffix for suffix in sorted(SUFFIXES, key=len, reverse=True) if name.endswith(suffix)), "")


def tract_file_coordinate_system(path):
    """Honor explicit Slicer SPACE metadata; pipeline tract points default to RAS."""
    try:
        import vtk
        reader = vtk.vtkXMLPolyDataReader() if Path(path).suffix.lower() == ".vtp" else vtk.vtkPolyDataReader()
        reader.SetFileName(str(path))
        reader.Update()
        fields = reader.GetOutput().GetFieldData()
        for key in ("SPACE", "CoordinateSystem"):
            array = fields.GetAbstractArray(key)
            if array is not None and array.GetNumberOfValues():
                value = str(array.GetVariantValue(0).ToString()).upper()
                if value in {"RAS", "LPS"}:
                    return value
    except (ImportError, AttributeError, ValueError):
        pass
    return "RAS"


def bundle_outputs(task, *, allow_directory_scan=True):
    """Resolve bundles from the successful task's own QC, not shared folders."""
    if task.get("name") not in {"bundles.wmql", "bundles.wma", "bundles.tractcloud"}:
        return {}
    path = task.get("qc_path") or (task.get("outputs") or {}).get("qc_path")
    try:
        if not path or not Path(path).is_absolute():
            return {}
        qc = json.loads(Path(path).read_text(encoding="utf-8"))
        if qc.get("status") not in {"completed", "passed"}:
            return {}
        summary = qc.get("output_summary") or {}
        files = summary.get("bundle_files") or summary.get("anatomical_tract_files") or []
        if not files and task["name"] == "bundles.wma" and allow_directory_scan:
            # Older WMA QC records name the exact anatomical-tract directory.
            # Require the recorded count; never scan the entire output root.
            folder = Path(str(summary.get("anatomical_tracts_dir") or ""))
            if folder.is_absolute() and folder.is_dir():
                files = [str(path) for path in sorted(folder.glob("*.vtp"))]
                if len(files) != int(summary.get("anatomical_tract_count") or 0):
                    return {}
        empty = set(summary.get("empty_bundle_files") or [])
        empty_names = set(summary.get("anatomical_empty_tracts") or [])
        return {"bundle_" + Path(value).name: value for value in files
                if isinstance(value, str) and value not in empty and Path(value).name not in empty_names}
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


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


def result_candidates(manifest, *, allow_bundle_directory_scan=True, include_preprocessing=False):
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
        if name.startswith("preprocessing.") and not include_preprocessing:
            continue
        outputs = dict(task.get("outputs") or {})
        outputs.update(bundle_outputs(task, allow_directory_scan=allow_bundle_directory_scan))
        for key, value in outputs.items():
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


def result_nodes(slicer):
    # Tables are storable MRML nodes but do not inherit DisplayableNode.
    nodes = {}
    for class_name in ("vtkMRMLDisplayableNode", "vtkMRMLTableNode"):
        for node in slicer.util.getNodesByClass(class_name):
            nodes[node.GetID()] = node
    return list(nodes.values())


def owned_nodes(slicer, run_id):
    return [node for node in result_nodes(slicer)
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


def annotate_automatic_result(node, candidate):
    """Recorded QC is not a human review, nor a claim of scientific validity."""
    for key, value in {"AutomaticLoaded": "true", "DisplayRole": candidate["display_role"],
                       "QCState": candidate.get("qc_state", "unavailable")}.items():
        node.SetAttribute(PREFIX + key, str(value))
    if not node.GetAttribute(PREFIX + "HumanReviewState"):
        node.SetAttribute(PREFIX + "HumanReviewState", "pending")
    if candidate["display_role"].startswith(("tractography", "bundle:")):
        node.SetAttribute(PREFIX + "DisplayPreview", "true")
        node.SetAttribute(PREFIX + "QuantitativeSourcePath", candidate["path"])
        node.SetAttribute(PREFIX + "MeasurementWarning", "Display preview; use the original file for quantitative measurements")


def automatic_display_preset(slicer, node, candidate, *, hide_pial=True):
    """Only display properties change; voxel values, label IDs and mesh data do not."""
    annotate_automatic_result(node, candidate)
    display = node.GetDisplayNode() if hasattr(node, "GetDisplayNode") else None
    if node.IsA("vtkMRMLFiberBundleNode") and hasattr(node, "GetLineDisplayNode"):
        display = node.GetLineDisplayNode() or display
        # Converted streamlines do not contain fitted tensors. Display true
        # geometry/orientation instead of fabricating tensor glyphs/scalars.
        for getter in ("GetTubeDisplayNode", "GetGlyphDisplayNode"):
            other = getattr(node, getter, lambda: None)()
            if other is not None:
                other.SetVisibility(False)
    if display is None:
        return
    role = candidate["display_role"]

    def color_node(*identities):
        for identity in identities:
            if slicer.mrmlScene.GetNodeByID(identity) is not None:
                display.SetAndObserveColorNodeID(identity)
                break

    if role.startswith("scalar:"):
        metric = role.split(":", 1)[1]
        color_node("vtkMRMLColorTableNodeGrey" if metric in {"fa", "md", "ad", "rd", "fw_fa", "fw_md", "kfa", "corrected_kfa", "b0"}
                   else "vtkMRMLColorTableNodeRainbow")
        if metric == "b0":
            display.SetAutoWindowLevel(True)
            return
        display.SetAutoWindowLevel(False)
        maximum = 0.003 if metric in {"md", "ad", "rd", "fw_md"} else 3.0 if metric.removeprefix("corrected_") in {"mk", "ak", "rk", "mkt", "rtk"} else 1.0
        display.SetWindowLevel(maximum, maximum / 2)
    elif role.startswith("categorical"):
        if candidate["product"].startswith("parcellation."):
            color_node("vtkMRMLColorTableNodeFileFreeSurferColorLUT.txt", "vtkMRMLColorTableNodeLabels")
        else:
            color_node("vtkMRMLColorTableNodeGenericAnatomyColors", "vtkMRMLColorTableNodeLabels")
    elif role.startswith("surface:"):
        pial = ":pial:" in role
        display.SetColor(*( (0.84, 0.64, 0.51) if pial else (0.88, 0.88, 0.82) ))
        display.SetOpacity(0.3 if pial else 1.0)
        display.SetVisibility(not (pial and hide_pial))
    elif role.startswith("bundle:"):
        if hasattr(display, "SetColorModeToSolid"):
            display.SetColorModeToSolid()
        display.SetColor(*{"af": (0.93, 0.48, 0.22), "cst": (0.24, 0.65, 0.88),
                            "cc": (0.83, 0.72, 0.28), "representative": (0.5, 0.7, 0.65)}[role.split(":", 1)[1]])
        display.SetOpacity(1.0)
        display.SetVisibility(True)
    elif role.startswith("tractography"):
        if hasattr(display, "SetColorModeToPointFiberOrientation"):
            display.SetColorModeToPointFiberOrientation()
        display.SetOpacity(0.5)
        display.SetVisibility(True)


def show_automatic_results(slicer, entries, *, newly_loaded=None):
    """Initialize views once after new loads, not on every checkpoint reuse."""
    backgrounds, labels = [], []
    for entry in entries:
        for identity in entry.get("node_ids", []):
            node = slicer.mrmlScene.GetNodeByID(identity)
            if node is None:
                continue
            role = entry.get("display_role", "")
            if role.startswith("scalar:") and node.IsA("vtkMRMLScalarVolumeNode"):
                rank = {"scalar:fa": 0, "scalar:fw_fa": 1, "scalar:md": 2,
                        "scalar:corrected_mk": 3, "scalar:mk": 4,
                        "scalar:ndi": 5, "scalar:odi": 6}.get(role, 10)
                backgrounds.append((rank, identity))
            elif role.startswith("categorical") and node.IsA("vtkMRMLLabelMapVolumeNode"):
                rank = 0 if entry["product"].startswith("segmentation.") else 2 if role == "categorical:mask" else 1
                labels.append((rank, identity))
    view = {}
    if backgrounds:
        view["background"] = sorted(backgrounds)[0][1]
    if labels:
        view["label"] = sorted(labels)[0][1]
    new = entries if newly_loaded is None else newly_loaded
    new_volumes = any(entry.get("display_role", "").startswith(("scalar:", "categorical")) for entry in new)
    if new_volumes and view and hasattr(slicer.util, "setSliceViewerLayers"):
        slicer.util.setSliceViewerLayers(**view, **({"labelOpacity": 0.35} if labels else {}))
        if hasattr(slicer.util, "resetSliceViews"):
            slicer.util.resetSliceViews()
        center_node = slicer.mrmlScene.GetNodeByID(view.get("background") or view.get("label"))
        slice_class = getattr(slicer, "vtkMRMLSliceNode", None)
        if center_node is not None and hasattr(center_node, "GetRASBounds") and slice_class is not None:
            bounds = [0.0] * 6
            center_node.GetRASBounds(bounds)
            center = [(bounds[index] + bounds[index + 1]) / 2 for index in (0, 2, 4)]
            # Fit/zoom alone may leave off-origin native data outside the
            # coronal/sagittal planes in a fresh scene.
            slice_class.JumpAllSlices(slicer.mrmlScene, *center, slice_class.CenteredJumpSlice)
    if any(entry.get("display_role", "").startswith(("surface:", "bundle:", "tractography")) for entry in new):
        if hasattr(slicer.util, "resetThreeDViews"):
            slicer.util.resetThreeDViews()
    return view
