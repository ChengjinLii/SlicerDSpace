"""Native, editable tissue copies that never replace scientific source products."""

from pathlib import Path

from shared.result_scene import PREFIX, source_stamp

TISSUES = ((1, "White matter", (.33, .54, .71)),
           (2, "Gray matter", (.42, .66, .56)),
           (3, "CSF", (.78, .61, .39)))


def editable_tissue_copy(slicer, source):
    import numpy as np

    if not source.IsA("vtkMRMLLabelMapVolumeNode") or not str(source.GetAttribute(PREFIX + "Product") or "").startswith("segmentation."):
        raise ValueError("Select a loaded DDSeg tissue labelmap, not a parcellation or scalar map")
    path = Path(source.GetAttribute(PREFIX + "SourcePath") or "")
    if not path.is_file() or source.GetAttribute(PREFIX + "SourceStamp") != source_stamp(path):
        raise ValueError("The source product changed; reload this run before creating an edit copy")
    labels = slicer.util.arrayFromVolume(source)
    if not np.isfinite(labels).all() or not set(np.unique(labels)) <= {0, 1, 2, 3} or not np.any(labels):
        raise ValueError("DDSeg editing requires nonempty labels 0/1/2/3; no relabeling was performed")
    for node in slicer.util.getNodesByClass("vtkMRMLSegmentationNode"):
        if (node.GetNodeReferenceID("SlicerDDSurfer.ReviewSource") == source.GetID() and
                node.GetAttribute(PREFIX + "ReviewSourceStamp") == source_stamp(path)):
            return node
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", source.GetName() + "_review")
    try:
        node.CreateDefaultDisplayNodes()
        node.SetAndObserveTransformNodeID(source.GetTransformNodeID())
        node.SetReferenceImageGeometryParameterFromVolumeNode(source)
        for value, name, color in TISSUES:
            if not np.any(labels == value):
                continue
            segment_id = node.GetSegmentation().AddEmptySegment("tissue_" + str(value), name, color)
            slicer.util.updateSegmentBinaryLabelmapFromArray((labels == value).astype(np.uint8), node, segment_id, source)
        node.SetNodeReferenceID("SlicerDDSurfer.ReviewSource", source.GetID())
        for key, value in {"ReviewOfRun": source.GetAttribute(PREFIX + "Run") or "",
                           "ReviewSourcePath": str(path), "ReviewSourceStamp": source_stamp(path),
                           "HumanReviewState": "editing", "QCState": "manual_revision_not_assessed",
                           "MeasurementWarning": "Manual review copy; save separately. Original quantitative results and QC are unchanged."}.items():
            node.SetAttribute(PREFIX + key, value)
        hierarchy = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
        source_item = hierarchy.GetItemByDataNode(source)
        hierarchy.SetItemParent(hierarchy.GetItemByDataNode(node), hierarchy.GetItemParent(source_item))
    except Exception:
        slicer.mrmlScene.RemoveNode(node)
        raise
    # Deliberately omit the automatic run ownership attribute: clearing/replacing
    # machine-generated previews must not delete a user's edited segmentation.
    return node
