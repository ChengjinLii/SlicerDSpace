"""Exercise the Advanced region panel, real background CLI, and scene reintegration."""

import csv
import json
import os
from pathlib import Path
import time
import traceback
import tempfile

import nibabel as nib
import numpy as np
import qt
import slicer

ROOT = Path(os.environ["SLICERDSPACE_SMOKE_ROOT"])
STATE = {"phase": "start", "ticks": 0, "started": time.monotonic()}


def fixture():
    from shared.region_analysis import write_json, sha256

    folder = Path(tempfile.mkdtemp(prefix="subject-", dir=ROOT))
    (folder / "input").mkdir()
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    atlas = np.zeros((7, 5, 5), dtype=np.int32)
    atlas[1:3, 1:4, 1:4] = 1001
    atlas[4:6, 1:4, 1:4] = 2001
    for name, data in (
        ("atlas.nii.gz", atlas),
        ("fa.nii.gz", np.full(atlas.shape, 0.6, np.float32)),
        ("input/nodif_brain_mask.nii.gz", np.ones(atlas.shape, np.uint8)),
    ):
        nib.save(nib.Nifti1Image(data, affine), folder / name)
    lut = folder / "regions.txt"
    lut.write_text("0 Background 0 0 0 0\n1001 ctx-lh-precentral 80 100 200 0\n2001 ctx-rh-precentral 200 100 80 0\n")
    tissue = np.zeros(atlas.shape, np.int16)
    tissue[atlas == 1001] = 1
    tissue[atlas == 2001] = 2
    nib.save(nib.Nifti1Image(tissue, affine), folder / "tissue.nii.gz")
    (folder / "surf").mkdir()
    (folder / "label").mkdir()
    for hemi in ("lh", "rh"):
        nib.freesurfer.write_annot(str(folder / f"label/{hemi}.aparc.annot"), np.array([1, 1, 0, 0]),
                                  np.array([[0, 0, 0, 0], [80, 120, 200, 0]]), ["unknown", "precentral"])
        for key, values in (("thickness", [2, 4, 0, 0]), ("area", [3, 5, 0, 0]), ("curv", [-0.2, 0.4, 0, 0])):
            nib.freesurfer.write_morph_data(str(folder / f"surf/{hemi}.{key}"), np.array(values, np.float32))
    tracts = folder / "tracts.trk"
    lines = [np.array([[0, 4, 4], [12, 4, 4]], np.float32), np.array([[2, 4, 4], [4, 4, 4]], np.float32),
             np.array([[2, 4, 4], [8, 4, 4]], np.float32)]
    nib.streamlines.save(nib.streamlines.Tractogram(lines, affine_to_rasmm=np.eye(4)), str(tracts))
    matrix, nodes = folder / "matrix.csv", folder / "nodes.tsv"
    matrix.write_text("source_node,target_node,streamline_count\n1001,2001,7\n")
    nodes.write_text("node_id\tlabel\tname\n1\t1001\tLeft\n2\t2001\tRight\n")
    stage = folder / "graph.json"
    write_json(
        stage,
        dict(
            status="completed",
            symmetric=True,
            dependencies={
                "ddparcel_parcellation": {
                    "path": str(folder / "atlas.nii.gz"),
                    "sha256": sha256(folder / "atlas.nii.gz"),
                }
            },
        ),
    )
    tasks = []
    for name, outputs in (
        ("parcellation.ddparcel", {"wmparc": str(folder / "atlas.nii.gz")}),
        ("microstructure.dti", {"fa": str(folder / "fa.nii.gz")}),
        ("segmentation.ddseg", {"segmentation": str(folder / "tissue.nii.gz")}),
        ("tractography.ukf", {"tractogram_trk": str(tracts)}),
        ("connectome.streamline_count", {"matrix_path": str(matrix), "nodes_path": str(nodes)}),
    ):
        qc = folder / (name + "_qc.json")
        write_json(
            qc,
            dict(
                status="completed",
                automatic_qc_passed=True,
                sources={key: {"path": value, "sha256": sha256(value)} for key, value in outputs.items()},
            ),
        )
        tasks.append(dict(name=name, status="completed", qc_path=str(qc), outputs=outputs))
    tasks[-1]["manifest_path"] = str(stage)
    qc = folder / "surface_qc.json"
    write_json(qc, dict(status="completed", automatic_qc_passed=True))
    tasks.append(dict(name="surface.ddsurfer_postprocess", status="completed", qc_path=str(qc),
                      outputs=dict(surf=str(folder / "surf"), label=str(folder / "label"))))
    parent = folder / "parent.json"
    write_json(
        parent,
        dict(
            kind="slicerddsurfer_product_orchestration",
            status="completed",
            subject_id="synthetic",
            subject_root=str(folder),
            output_root=str(folder / "outputs"),
            run_name="regions",
            tasks=tasks,
        ),
    )
    return parent, lut


def heartbeat():
    STATE["ticks"] += 1
    qt.QTimer.singleShot(100, heartbeat)


def tick():
    try:
        if STATE["phase"] == "start":
            slicer.util.selectModule("SlicerDSpace")
            owner = slicer.modules.slicerdspace.widgetRepresentation().self()
            STATE["owner"] = owner
            widgets = owner._regionWidgets
            assert widgets["panel"].collapsed and owner._advancedSettingsPanel.collapsed
            assert widgets["options"].collapsed
            assert widgets["options"].isAncestorOf(widgets["source"])
            assert widgets["options"].isAncestorOf(widgets["metric_list"])
            assert not widgets["options"].isAncestorOf(widgets["search"])
            assert owner._advancedSettingsPanel.isAncestorOf(widgets["panel"])
            from shared.ui_regions import apply_region_language

            apply_region_language(owner, "zh")
            assert "脑区" in widgets["panel"].text
            apply_region_language(owner, "en")
            assert "Regional" in widgets["panel"].text
            parent, lut = fixture()
            STATE["parent"] = str(parent)
            widgets["source"].setCurrentPath(str(parent))
            widgets["lut"].setCurrentPath(str(lut))
            window = slicer.util.mainWindow()
            window.showNormal()
            window.resize(1280, 900)
            panel = slicer.util.findChild(window, "PanelDockWidget")
            panel.setFixedWidth(440)
            owner._advancedSettingsPanel.collapsed = False
            owner._advancedCategorySelector.setCurrentIndex(3)
            widgets["panel"].collapsed = False
            widgets["inspect"].click()
            assert owner._setupJob is not None and owner._pipelineActive
            STATE["phase"] = "inspect"
        elif STATE["phase"] == "inspect":
            owner = STATE["owner"]
            if owner._setupJob is None and str(owner._regionWidgets["status"].text).startswith("failed:"):
                raise AssertionError(owner._regionWidgets["status"].text)
            if owner._setupJob is None and owner._regionCatalog is not None:
                widgets = owner._regionWidgets
                assert owner._regionCatalog, widgets["status"].text
                assert widgets["regions"].count == 2
                assert widgets["metric_list"].count == 1
                assert widgets["metrics"].checked
                assert not widgets["tracts"].checked and not widgets["graph"].checked
                assert owner._uiWidget.width <= 440, owner._uiWidget.width
                widgets["search"].text = "左中央前回"
                assert not widgets["regions"].item(0).isHidden()
                assert widgets["regions"].item(1).isHidden()
                widgets["select"].click()
                assert widgets["regions"].item(0).checkState() == qt.Qt.Checked
                assert widgets["regions"].item(1).checkState() == qt.Qt.Unchecked
                widgets["search"].clear()
                widgets["select"].click()
                widgets["tracts"].checked = True
                widgets["graph"].checked = True
                assert widgets["tissue"].visible and widgets["surface"].visible
                widgets["tissue"].checked = True
                widgets["surface"].checked = True
                owner._uiWidget.grab().save(str(ROOT / "regional_panel.png"))
                widgets["run"].click()
                assert owner._setupJob is not None, widgets["status"].text
                STATE["phase"] = "analysis"
        elif STATE["phase"] == "analysis":
            owner = STATE["owner"]
            if owner._setupJob is None and getattr(owner, "_latestRegionalManifestPath", None):
                manifest = getattr(owner, "_latestRegionalManifestPath", None)
                assert manifest, owner._regionWidgets["status"].text
                record = json.loads(Path(manifest).read_text())
                assert record["status"] == "completed", record
                folder = Path(manifest).parent
                stats = json.loads((folder / "selected_microstructure.json").read_text())
                assert len(stats["rows"]) == 2
                assert abs(stats["rows"][0]["fa_mean"] - 0.6) < 1e-6
                tracks = json.loads((folder / "selected_tractography.json").read_text())
                assert tracks["selected_streamlines"] == 3
                with (folder / "selected_connectome_matrix.csv").open() as stream:
                    matrix = list(csv.reader(stream))
                assert float(matrix[1][2]) == 7.0
                from shared.result_scene import owned_nodes

                nodes = owned_nodes(slicer, str(manifest))
                assert len(nodes) == 9, [(node.GetName(), node.GetClassName()) for node in nodes]
                tract = next(
                    node for node in nodes if node.GetAttribute("SlicerDDSurfer.Product") == "tractography.regions"
                )
                assert tract.GetAttribute("SlicerDDSurfer.QuantitativeSourcePath") == tracks["output"]
                assert tract.GetAttribute("SlicerDDSurfer.DisplayPreview") == "true"
                volume = next(node for node in nodes if node.IsA("vtkMRMLLabelMapVolumeNode"))
                color = volume.GetDisplayNode().GetColorNode()
                assert color.GetNumberOfColors() > 2001, color.GetNumberOfColors()
                assert color.GetColorName(1001) == "ctx-lh-precentral", color.GetColorName(1001)
                assert color.GetLookupTable().GetTableValue(1001)[3] == 1.
                assert color.GetLookupTable().GetTableValue(0)[3] == 0.
                from shared.result_scene import regional_color_node
                fallback = regional_color_node(slicer, {'region_label_ids': [1001, 2001]})
                assert fallback.GetLookupTable().GetTableValue(2001)[3] == 1.
                assert regional_color_node(slicer, {'region_label_ids': [1001, 2001]}).GetID() == fallback.GetID()
                before = len(nodes)
                owner.logic.loadKeyResultsFromManifest(Path(manifest), automatic=True)
                assert len(owned_nodes(slicer, str(manifest))) == before
                assert STATE["ticks"] > 5, STATE["ticks"]
                owner._uiWidget.grab().save(str(ROOT / "regional_completed.png"))
                assert owner._regionWidgets["report"].enabled
                assert Path(owner._regionalReportPath).is_file()
                widgets = owner._regionWidgets
                widgets["clear"].click()
                widgets["search"].text = "1001"
                widgets["select"].click()
                widgets["search"].clear()
                widgets["options"].collapsed = False
                widgets["rule"].setCurrentIndex(4)
                assert widgets["target"].visible and widgets["target"].enabled
                widgets["target"].text = "2001"
                widgets["graph"].checked = False
                color.SetColor(2001, "ctx-rh-precentral", 0.8, 0.4, 0.3, 0.)
                widgets["run"].click()
                assert owner._setupJob is not None, widgets["status"].text
                STATE["first_manifest"] = str(manifest)
                STATE["phase"] = "paired"
        elif STATE["phase"] == "paired":
            owner = STATE["owner"]
            manifest = getattr(owner, "_latestRegionalManifestPath", None)
            if owner._setupJob is None and str(manifest) != STATE["first_manifest"]:
                tracks = json.loads((Path(manifest).parent / "selected_tractography.json").read_text())
                assert tracks["selection_rule"] == "endpoint_pair"
                assert tracks["selected_streamlines"] == 1
                from shared.result_scene import owned_nodes

                region_map = next(node for node in owned_nodes(slicer, str(manifest)) if node.IsA("vtkMRMLLabelMapVolumeNode"))
                assert region_map.GetDisplayNode().GetColorNode().GetLookupTable().GetTableValue(2001)[3] == 1.
                from scripts.validate_region_analysis import validate

                assert validate(manifest)["status"] == "PASS"
                owner._uiWidget.grab().save(str(ROOT / "regional_pair.png"))
                # Input changes must invalidate the catalogue, not reuse old selected labels.
                owner._regionWidgets["atlas"].setCurrentPath(str(ROOT / "changed_atlas.nii.gz"))
                assert owner._regionCatalog is None
                assert not owner._regionWidgets["run"].enabled
                report = dict(
                    status="PASS",
                    elapsed_seconds=time.monotonic() - STATE["started"],
                    heartbeat_ticks=STATE["ticks"],
                    checks=[
                        "Advanced-only collapsed default",
                        "EN/ZH",
                        "440px panel",
                        "async inspect and analyze",
                        "search and check visible",
                        "microstructure mean",
                        "complete ROI streamlines",
                        "unchanged connectivity weights",
                        "nine auto-loaded grouped nodes",
                        "source vs preview metadata",
                        "custom LUT IDs above 1000",
                        "duplicate reuse",
                        "changed inputs invalidate",
                        "simple main panel with collapsed details",
                        "A-B endpoint selection and independent verification",
                        "local HTML report",
                        "tissue and cortical statistics via GUI",
                        "Chinese region alias search",
                    ],
                    scene_nodes=9,
                    manifest=str(manifest),
                )
                (ROOT / "regions.json").write_text(json.dumps(report, indent=2))
                print("REGIONS_GUI_PASS", flush=True)
                slicer.app.exit(0)
                return
        qt.QTimer.singleShot(250, tick)
    except Exception:
        traceback.print_exc()
        slicer.app.exit(2)


qt.QTimer.singleShot(5000, tick)
qt.QTimer.singleShot(100, heartbeat)
qt.QTimer.singleShot(150000, lambda: slicer.app.exit(3))
