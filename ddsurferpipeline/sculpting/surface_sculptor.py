"""Topology-preserving surface sculpting helpers for SlicerDDSurfer.

This module adds a lightweight brush-based editor for vtkPolyData meshes.
It intentionally never changes mesh connectivity: only point coordinates
are updated to keep topology intact.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import slicer
import vtk
from qt import (
    QFileDialog,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from slicer.util import VTKObservationMixin
from vtk.util.numpy_support import vtk_to_numpy

import ctk

LOGGER = logging.getLogger(__name__)


BRUSH_TYPES = ("Smooth", "Paint (Grow)", "Erase (Shrink)", "Flatten")


@dataclass
class SculptStroke:
    """Stores the original coordinates for a single stroke to enable undo."""

    original_positions: Dict[int, np.ndarray]

    def record(self, point_ids: Iterable[int], points_array: np.ndarray) -> None:
        for pid in point_ids:
            if pid not in self.original_positions:
                self.original_positions[pid] = points_array[pid].copy()

    def is_empty(self) -> bool:
        return len(self.original_positions) == 0


class SurfaceSculptorLogic:
    """Brush-based editing on vtkPolyData without altering topology."""

    def __init__(self) -> None:
        self.model_node = None
        self.parent_transform = None
        self.polydata: Optional[vtk.vtkPolyData] = None
        self.points: Optional[vtk.vtkPoints] = None
        self.points_np: Optional[np.ndarray] = None
        self.normals_np: Optional[np.ndarray] = None
        self.locator: Optional[vtk.vtkPointLocator] = None
        self.undo_stack: List[SculptStroke] = []
        self._active_stroke: Optional[SculptStroke] = None
        self._dirty_locator: bool = False

    # ------------------------- public API ------------------------- #

    def set_target_model(self, model_node) -> None:
        """Attach the model to be edited."""
        self.model_node = model_node
        if model_node is None:
            self._clear_state()
            return

        polydata = model_node.GetPolyData() if hasattr(model_node, "GetPolyData") else None
        if not isinstance(polydata, vtk.vtkPolyData):
            raise ValueError("Selected node is not a vtkPolyData mesh.")
        if polydata.GetNumberOfPoints() == 0:
            raise ValueError("Selected mesh has no points.")

        self.polydata = polydata
        self.parent_transform = model_node.GetParentTransformNode()
        self.points = polydata.GetPoints()
        self.points_np = vtk_to_numpy(self.points.GetData())
        self._ensure_normals()
        self._build_locator()
        self.undo_stack.clear()
        self._active_stroke = None
        self._dirty_locator = False

    def begin_stroke(self) -> None:
        if self.polydata is None:
            raise RuntimeError("No active model available for sculpting.")
        self._active_stroke = SculptStroke(original_positions={})

    def end_stroke(self) -> None:
        if not self._active_stroke:
            return
        if not self._active_stroke.is_empty():
            self.undo_stack.append(self._active_stroke)
        self._active_stroke = None
        if self._dirty_locator and self.locator:
            self._build_locator()
            self._dirty_locator = False

    def apply_brush(
        self,
        center_world: Sequence[float],
        radius: float,
        strength: float,
        brush_type: str,
    ) -> None:
        if self.polydata is None or self.points_np is None or self.locator is None:
            return
        center_model = self._world_to_model_point(center_world)
        ids = vtk.vtkIdList()
        self.locator.FindPointsWithinRadius(radius, center_model, ids)
        if ids.GetNumberOfIds() == 0:
            return

        point_ids = np.fromiter((ids.GetId(i) for i in range(ids.GetNumberOfIds())), dtype=np.int64)
        # Record original coordinates to support undo
        if self._active_stroke:
            self._active_stroke.record(point_ids, self.points_np)

        points = self.points_np[point_ids]
        offsets = points - np.asarray(center_model, dtype=float)
        distances = np.linalg.norm(offsets, axis=1)
        # Cosine falloff, zero weight at the edge
        weights = np.cos(0.5 * np.pi * distances / radius)
        weights[distances >= radius] = 0.0
        weights = np.clip(weights, 0.0, 1.0)

        if brush_type.startswith("Smooth"):
            delta = self._compute_smooth_delta(points, weights, strength)
        elif "Paint" in brush_type:  # grow outward
            delta = self._compute_inflate_delta(point_ids, distances, weights, strength, radius, inflate=True)
            delta += self._compute_smooth_delta(points + delta, weights, strength * 0.2)
        elif "Erase" in brush_type:  # shrink inward
            delta = self._compute_inflate_delta(point_ids, distances, weights, strength, radius, inflate=False)
            delta += self._compute_smooth_delta(points + delta, weights, strength * 0.2)
        elif brush_type.startswith("Flatten"):
            delta = self._compute_flatten_delta(points, weights, strength)
        else:
            return

        self.points_np[point_ids] = points + delta
        self._mark_geometry_dirty()

    def undo(self) -> bool:
        if not self.undo_stack or self.points_np is None:
            return False
        stroke = self.undo_stack.pop()
        for pid, coords in stroke.original_positions.items():
            self.points_np[pid] = coords
        self._mark_geometry_dirty()
        self._build_locator()
        return True

    def recompute_normals(self) -> None:
        if self.polydata is None:
            return
        normal_gen = vtk.vtkPolyDataNormals()
        normal_gen.SetInputData(self.polydata)
        normal_gen.ComputePointNormalsOn()
        normal_gen.ComputeCellNormalsOff()
        normal_gen.SplittingOff()
        normal_gen.ConsistencyOn()
        normal_gen.AutoOrientNormalsOn()
        normal_gen.Update()
        computed = normal_gen.GetOutput().GetPointData().GetNormals()
        self.polydata.GetPointData().SetNormals(computed)
        self.normals_np = vtk_to_numpy(self.polydata.GetPointData().GetNormals())
        self.polydata.Modified()

    def is_ready(self) -> bool:
        return self.polydata is not None and self.locator is not None

    # ------------------------- helpers ------------------------- #

    def _compute_smooth_delta(self, points: np.ndarray, weights: np.ndarray, strength: float) -> np.ndarray:
        mean = points.mean(axis=0)
        factor = (weights * strength)[:, np.newaxis]
        return (mean - points) * factor

    def _compute_inflate_delta(
        self,
        point_ids: np.ndarray,
        distances: np.ndarray,
        weights: np.ndarray,
        strength: float,
        radius: float,
        inflate: bool,
    ) -> np.ndarray:
        if self.normals_np is None:
            self._ensure_normals()
        normals = self.normals_np[point_ids]
        direction = 1.0 if inflate else -1.0
        falloff = np.clip(1.0 - distances / max(radius, 1e-6), 0.0, 1.0)
        step = radius * 0.25
        magnitude = direction * strength * weights * falloff * step
        return normals * magnitude[:, np.newaxis]

    def _compute_flatten_delta(self, points: np.ndarray, weights: np.ndarray, strength: float) -> np.ndarray:
        centroid = points.mean(axis=0)
        centered = points - centroid
        if len(points) >= 3:
            _, _, vh = np.linalg.svd(centered, full_matrices=False)
            normal = vh[-1]
        else:
            normal = np.array([0.0, 0.0, 1.0])
        distances = centered @ normal
        return (-distances[:, np.newaxis] * normal) * (weights * strength)[:, np.newaxis]

    def _mark_geometry_dirty(self) -> None:
        if not self.points or not self.polydata:
            return
        self.points.Modified()
        self.polydata.Modified()
        if self.model_node:
            try:
                self.model_node.Modified()
                display_node = self.model_node.GetDisplayNode()
                if display_node:
                    display_node.Modified()
            except Exception:
                pass
        self._dirty_locator = True

    def _build_locator(self) -> None:
        if self.polydata is None:
            return
        locator = vtk.vtkPointLocator()
        locator.SetDataSet(self.polydata)
        locator.BuildLocator()
        self.locator = locator

    def _ensure_normals(self) -> None:
        if self.polydata is None:
            return
        normals = self.polydata.GetPointData().GetNormals()
        if normals is None:
            normal_gen = vtk.vtkPolyDataNormals()
            normal_gen.SetInputData(self.polydata)
            normal_gen.ComputePointNormalsOn()
            normal_gen.ComputeCellNormalsOff()
            normal_gen.SplittingOff()
            normal_gen.ConsistencyOn()
            normal_gen.AutoOrientNormalsOn()
            normal_gen.Update()
            normals = normal_gen.GetOutput().GetPointData().GetNormals()
            self.polydata.GetPointData().SetNormals(normals)
        self.normals_np = vtk_to_numpy(self.polydata.GetPointData().GetNormals())

    def _clear_state(self) -> None:
        self.polydata = None
        self.points = None
        self.points_np = None
        self.normals_np = None
        self.locator = None
        self.undo_stack.clear()
        self._active_stroke = None
        self._dirty_locator = False

    # ------------------------- transforms ------------------------- #

    def _world_to_model_point(self, pt: Optional[Sequence[float]]) -> Optional[np.ndarray]:
        if pt is None:
            return None
        if self.parent_transform:
            xform = vtk.vtkGeneralTransform()
            self.parent_transform.GetTransformFromWorld(xform)
            out = [0.0, 0.0, 0.0]
            xform.TransformPoint(pt, out)
            return np.asarray(out, dtype=float)
        return np.asarray(pt, dtype=float)

    def _model_to_world_point(self, pt: Sequence[float]) -> np.ndarray:
        if self.parent_transform:
            xform = vtk.vtkGeneralTransform()
            self.parent_transform.GetTransformToWorld(xform)
            out = [0.0, 0.0, 0.0]
            xform.TransformPoint(pt, out)
            return np.asarray(out, dtype=float)
        return np.asarray(pt, dtype=float)


class SurfaceSculptorWidget(VTKObservationMixin):
    """UI and interaction glue for the sculpting brush."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        VTKObservationMixin.__init__(self)
        self.logic = SurfaceSculptorLogic()
        self.parent = parent
        self.widget = ctk.ctkCollapsibleButton()
        self.widget.setText("Surface Sculptor (Topology-Preserving)")
        self.widget.setToolTip("Brush-based mesh fine-tuning that only moves vertex coordinates without changing topology.")
        self._dragging: bool = False
        self._picker = vtk.vtkCellPicker()
        self._picker.SetTolerance(0.001)
        self._view_observers: List[Tuple[vtk.vtkInteractorObserver, List[int]]] = []
        self._preview_actors: Dict[vtk.vtkRenderer, Tuple[str, object, object]] = {}
        self._slice_styles: Dict[vtk.vtkInteractorObserver, vtk.vtkMRMLSliceNode] = {}
        self._slice_renderers: Dict[vtk.vtkRenderer, vtk.vtkMRMLSliceNode] = {}

        self._build_ui()

    # ------------------------- UI setup ------------------------- #

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        node_row = QHBoxLayout()
        node_label = QLabel("Target model")
        node_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.modelSelector = slicer.qMRMLNodeComboBox()
        self.modelSelector.nodeTypes = ["vtkMRMLModelNode"]
        self.modelSelector.selectNodeUponCreation = False
        self.modelSelector.addEnabled = False
        self.modelSelector.removeEnabled = False
        self.modelSelector.renameEnabled = False
        self.modelSelector.noneEnabled = True
        self.modelSelector.setMRMLScene(slicer.mrmlScene)
        node_row.addWidget(node_label)
        node_row.addWidget(self.modelSelector)
        layout.addLayout(node_row)

        brush_row = QHBoxLayout()
        brush_label = QLabel("Brush type")
        brush_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.brushCombo = QComboBox()
        for name in BRUSH_TYPES:
            self.brushCombo.addItem(name)
        brush_row.addWidget(brush_label)
        brush_row.addWidget(self.brushCombo)
        layout.addLayout(brush_row)

        self.radiusSlider = ctk.ctkSliderWidget()
        self.radiusSlider.decimals = 1
        self.radiusSlider.minimum = 0.5
        self.radiusSlider.maximum = 20.0
        self.radiusSlider.singleStep = 0.5
        self.radiusSlider.value = 5.0
        self.radiusSlider.toolTip = "Brush radius (mm)"
        layout.addWidget(self._wrap_with_label("Radius (mm)", self.radiusSlider))

        self.strengthSlider = ctk.ctkSliderWidget()
        self.strengthSlider.decimals = 2
        self.strengthSlider.minimum = 0.05
        self.strengthSlider.maximum = 2.0
        self.strengthSlider.singleStep = 0.05
        self.strengthSlider.value = 0.3
        self.strengthSlider.toolTip = "Brush strength; higher values deform more"
        layout.addWidget(self._wrap_with_label("Strength", self.strengthSlider))

        options_row = QHBoxLayout()
        self.recomputeNormalsCheck = QCheckBox("Recompute normals on release")
        self.recomputeNormalsCheck.setChecked(True)
        options_row.addWidget(self.recomputeNormalsCheck)
        options_row.addStretch(1)
        layout.addLayout(options_row)

        slice_row = QHBoxLayout()
        self.sliceDisplayCheck = QCheckBox("Show model in slice views")
        self.sliceDisplayCheck.setChecked(True)
        slice_row.addWidget(self.sliceDisplayCheck)
        slice_row.addStretch(1)
        layout.addLayout(slice_row)

        button_row = QHBoxLayout()
        self.enableButton = QPushButton("Enable sculpt")
        self.enableButton.setCheckable(True)
        self.undoButton = QPushButton("Undo last")
        self.undoButton.setEnabled(False)
        self.exportButton = QPushButton("Export current model")
        button_row.addWidget(self.enableButton)
        button_row.addWidget(self.undoButton)
        button_row.addWidget(self.exportButton)
        layout.addLayout(button_row)

        self.statusLabel = QLabel("No model selected")
        layout.addWidget(self.statusLabel)

        self.widget.setLayout(layout)

        self.modelSelector.currentNodeChanged.connect(self._on_model_changed)
        self.enableButton.toggled.connect(self._on_enable_toggled)
        self.undoButton.clicked.connect(self._on_undo_clicked)
        self.radiusSlider.valueChanged.connect(self._update_preview_radius)
        self.sliceDisplayCheck.toggled.connect(self._on_slice_display_toggled)
        self.exportButton.clicked.connect(self._on_export_clicked)

    def _wrap_with_label(self, label_text: str, widget: QWidget) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel(label_text)
        label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        row.addWidget(label)
        row.addWidget(widget)
        return container

    # ------------------------- event handlers ------------------------- #

    def _on_model_changed(self, node) -> None:
        try:
            self.logic.set_target_model(node)
            self.statusLabel.setText("Ready: left-click and drag to sculpt")
            self._apply_slice_display()
        except Exception as exc:
            self.statusLabel.setText(str(exc))
            LOGGER.exception("Failed to set sculpt target: %s", exc)
        self.undoButton.setEnabled(False)

    def _on_enable_toggled(self, checked: bool) -> None:
        if checked:
            if not self.logic.is_ready():
                self.statusLabel.setText("Select a model before enabling sculpt")
                self.enableButton.setChecked(False)
                return
            self._add_interaction_observers()
            self.statusLabel.setText("Sculpt enabled: left-drag to edit; right-click/shift to navigate")
        else:
            self._remove_interaction_observers()
            self._remove_preview_actors()
            self.statusLabel.setText("Sculpt disabled")
            self._dragging = False

    def _on_undo_clicked(self) -> None:
        if self.logic.undo():
            self._refresh_display()
            self.undoButton.setEnabled(bool(self.logic.undo_stack))
            self.statusLabel.setText("Undo applied")
        else:
            self.statusLabel.setText("Nothing to undo")

    def _on_export_clicked(self) -> None:
        if not self.logic.polydata:
            self.statusLabel.setText("Select a model first")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self.widget, "Export model", "", "STL (*.stl);;VTK PolyData (*.vtp);;Legacy VTK (*.vtk)"
        )
        if not filename:
            return
        try:
            pd = vtk.vtkPolyData()
            pd.DeepCopy(self.logic.polydata)

            lower = filename.lower()
            if lower.endswith(".stl"):
                writer = vtk.vtkSTLWriter()
            elif lower.endswith(".vtp"):
                writer = vtk.vtkXMLPolyDataWriter()
            elif lower.endswith(".vtk"):
                writer = vtk.vtkPolyDataWriter()
            else:
                writer = vtk.vtkSTLWriter()
                if not lower.endswith(".stl"):
                    filename = filename + ".stl"
            writer.SetFileName(filename)
            writer.SetInputData(pd)
            writer.Write()
            self.statusLabel.setText(f"Exported: {filename}")
        except Exception as exc:
            self.statusLabel.setText(f"Export failed: {exc}")
            LOGGER.exception("Export failed: %s", exc)

    def _on_left_button_press(self, caller, event) -> None:
        if not self.logic.is_ready():
            return
        pick = self._pick_event_position(caller)
        if not pick:
            return
        position, renderer, event_xy = pick
        self._dragging = True
        self.logic.begin_stroke()
        self._apply_brush(position)
        self._show_preview(renderer, position, event_xy)
        caller.GetInteractor().Render()

    def _on_mouse_move(self, caller, event) -> None:
        pick = self._pick_event_position(caller)
        if not pick:
            return
        position, renderer, event_xy = pick
        self._show_preview(renderer, position, event_xy)
        if self._dragging:
            self._apply_brush(position)
            caller.GetInteractor().Render()

    def _on_left_button_release(self, caller, event) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self.logic.end_stroke()
        if self.recomputeNormalsCheck.isChecked():
            self.logic.recompute_normals()
        self._refresh_display()
        self.undoButton.setEnabled(bool(self.logic.undo_stack))

    # ------------------------- interaction helpers ------------------------- #

    def _apply_brush(self, position_world: Tuple[float, float, float]) -> None:
        self.logic.apply_brush(
            center_world=position_world,
            radius=float(self.radiusSlider.value),
            strength=float(self.strengthSlider.value),
            brush_type=str(self.brushCombo.currentText),
        )

    def _add_interaction_observers(self) -> None:
        self._remove_interaction_observers()
        lm = slicer.app.layoutManager()
        if lm is None:
            return
        for view_index in range(lm.threeDViewCount):
            view = lm.threeDWidget(view_index).threeDView()
            style = view.interactorStyle()
            tags = [
                style.AddObserver(vtk.vtkCommand.LeftButtonPressEvent, self._on_left_button_press, 1.0),
                style.AddObserver(vtk.vtkCommand.MouseMoveEvent, self._on_mouse_move, 1.0),
                style.AddObserver(vtk.vtkCommand.LeftButtonReleaseEvent, self._on_left_button_release, 1.0),
            ]
            self._view_observers.append((style, tags))
        # Slice views (sculpting in slice renders)
        try:
            for name in lm.sliceViewNames():
                slice_widget = lm.sliceWidget(name)
                slice_view = slice_widget.sliceView()
                style = slice_view.interactorStyle()
                renderer = slice_view.renderWindow().GetRenderers().GetFirstRenderer()
                tags = [
                    style.AddObserver(vtk.vtkCommand.LeftButtonPressEvent, self._on_left_button_press, 1.0),
                    style.AddObserver(vtk.vtkCommand.MouseMoveEvent, self._on_mouse_move, 1.0),
                    style.AddObserver(vtk.vtkCommand.LeftButtonReleaseEvent, self._on_left_button_release, 1.0),
                ]
                self._view_observers.append((style, tags))
                self._slice_styles[style] = slice_widget.sliceLogic().GetSliceNode()
                self._slice_renderers[renderer] = slice_widget.sliceLogic().GetSliceNode()
        except Exception:
            # If slice views are unavailable, keep 3D interaction working
            pass

    def _remove_interaction_observers(self) -> None:
        for style, tags in self._view_observers:
            for tag in tags:
                style.RemoveObserver(tag)
        self._view_observers.clear()
        self._slice_styles.clear()
        self._slice_renderers.clear()

    def _pick_event_position(self, caller) -> Optional[Tuple[Tuple[float, float, float], vtk.vtkRenderer, Tuple[float, float]]]:
        interactor = caller.GetInteractor() if hasattr(caller, "GetInteractor") else None
        if interactor is None or not self.logic.polydata:
            return None
        x, y = interactor.GetEventPosition()
        renderer = interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
        slice_node = self._slice_styles.get(caller)
        if slice_node and self.logic.locator is not None:
            xy_to_ras = slice_node.GetXYToRAS()
            ras = xy_to_ras.MultiplyPoint((x, y, 0, 1))
            ras_point = ras[:3]
            return (tuple(ras_point), renderer, (x, y))

        # Try direct pick (3D view)
        self._picker.Pick(x, y, 0, renderer)
        pos = self._picker.GetPickPosition()
        return (pos, renderer, (x, y))

    def _refresh_display(self) -> None:
        if self.logic.model_node:
            self.logic.model_node.StorableModified()
        slicer.app.processEvents()

    # ------------------------- brush preview ------------------------- #

    def _show_preview(self, renderer: vtk.vtkRenderer, position: Sequence[float], event_xy: Tuple[float, float]) -> None:
        radius_mm = float(self.radiusSlider.value)
        if renderer in self._slice_renderers:
            actor_tuple = self._preview_actors.get(renderer)
            if actor_tuple is None or actor_tuple[0] != "slice":
                poly = vtk.vtkRegularPolygonSource()
                poly.SetNumberOfSides(64)
                mapper = vtk.vtkPolyDataMapper2D()
                mapper.SetInputConnection(poly.GetOutputPort())
                actor2d = vtk.vtkActor2D()
                actor2d.SetMapper(mapper)
                prop = actor2d.GetProperty()
                prop.SetColor(0.95, 0.2, 0.1)
                prop.SetOpacity(0.4)
                prop.SetLineWidth(2.5)
                actor2d.SetPickable(False)
                renderer.AddActor2D(actor2d)
                actor_tuple = ("slice", poly, actor2d)
                self._preview_actors[renderer] = actor_tuple
            _, poly, actor2d = actor_tuple  # type: ignore
            # Compute pixel radius: mm / spacing
            slice_node = self._slice_renderers.get(renderer)
            pixel_radius = radius_mm
            center_xy = event_xy
            if slice_node:
                mat = slice_node.GetXYToRAS()
                m = np.array([[mat.GetElement(r, c) for c in range(4)] for r in range(4)])
                sx = np.linalg.norm(m[0:3, 0])
                sy = np.linalg.norm(m[0:3, 1])
                step = min(sx, sy) if min(sx, sy) > 1e-6 else 1.0
                pixel_radius = radius_mm / step
            poly.SetRadius(pixel_radius)
            poly.SetCenter(center_xy[0], center_xy[1], 0)
            poly.Update()
            actor2d.SetVisibility(True)
            actor2d.Modified()
            return

        actor_tuple = self._preview_actors.get(renderer)
        if actor_tuple is None or actor_tuple[0] != "3d":
            sphere = vtk.vtkSphereSource()
            sphere.SetThetaResolution(32)
            sphere.SetPhiResolution(32)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(sphere.GetOutputPort())
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            prop = actor.GetProperty()
            prop.SetColor(0.95, 0.2, 0.1)
            prop.SetOpacity(0.4)
            prop.SetLineWidth(2.5)
            prop.SetEdgeVisibility(True)
            prop.SetEdgeColor(0.95, 0.2, 0.1)
            prop.SetRepresentationToSurface()
            prop.SetAmbient(1.0)
            prop.SetDiffuse(0.0)
            actor.SetPickable(False)
            renderer.AddActor(actor)
            actor_tuple = ("3d", sphere, actor)
            self._preview_actors[renderer] = actor_tuple
        _, sphere, actor = actor_tuple  # type: ignore
        sphere.SetCenter(*position)
        sphere.SetRadius(radius_mm)
        sphere.Update()
        actor.SetVisibility(True)

    def _update_preview_radius(self, _value=None) -> None:
        radius_mm = float(self.radiusSlider.value)
        for entry in self._preview_actors.values():
            kind = entry[0]
            if kind == "3d":
                sphere = entry[1]
                sphere.SetRadius(radius_mm)
                sphere.Update()
            # Slice 2D preview radius recalculated in _show_preview; no update here

    def _remove_preview_actors(self) -> None:
        for renderer, entry in list(self._preview_actors.items()):
            actor = entry[2]
            try:
                if isinstance(actor, vtk.vtkActor2D):
                    renderer.RemoveActor2D(actor)
                else:
                    renderer.RemoveActor(actor)
            except Exception:
                pass
        self._preview_actors.clear()

    # ------------------------- cleanup ------------------------- #

    def cleanup(self) -> None:
        self._remove_interaction_observers()
        self._remove_preview_actors()
        self.logic._clear_state()
        self._dragging = False

    # ------------------------- slice display ------------------------- #

    def _apply_slice_display(self) -> None:
        if not self.logic.model_node:
            return
        display = self.logic.model_node.GetDisplayNode()
        if not display:
            return
        checked = bool(self.sliceDisplayCheck.isChecked())
        # Prefer new 2D visibility API
        if hasattr(display, "SetVisibility2D"):
            display.SetVisibility2D(1 if checked else 0)
        else:
            display.SetSliceIntersectionVisibility(1 if checked else 0)
        display.SetSliceIntersectionThickness(2)

    def _on_slice_display_toggled(self, checked: bool) -> None:
        self._apply_slice_display()
