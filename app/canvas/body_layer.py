"""
body_layer.py — "Solid bodies" layer: the inside of every body (cylinder, Rankine oval / half-body …)
filled like a solid cross-section, with a dark outline along its surface.

The body regions come from physics.bodies (fluid whose streamline starts at a source or a doublet,
bounded by the dividing streamlines); they are found on a grid of the visible region (about one cell
per screen pixel) and drawn as vector shapes (contourpy), so exports stay sharp. The fill hides what
the mathematics draws inside a body (streamlines, arrows, particles, pulses); the particles are also
not started inside a body (ParticleLayer asks contains()).

Recomputed when new streamlines (with their dividing streamlines) are drawn, and shortly after a zoom
/ pan. While an element is dragged the old shape is shown faintly.
"""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsPathItem

from physics.bodies import body_map, scene_map, surface_pieces

from .contours import filled_paths, mix
from .layer import PlotLayer

DELAY_MS = 90                   # after a zoom / pan
HATCH_ALPHA = 0.18
EDGE_PX = 2.0


class BodyLayer(PlotLayer):
    FADES_WHILE_DRAGGING = True

    def __init__(self, plot, vb):
        super().__init__(plot, vb)
        self.fill = self.add_item(QGraphicsPathItem(), 2.5)          # over the streamlines, arrows and the
        self.hatch = self.add_item(QGraphicsPathItem(), 2.51)        # animation; under the symbols
        for item in (self.fill, self.hatch):
            item.setPen(QPen(Qt.NoPen))
        self.edge = self.add_item(pg.PlotCurveItem(connect="finite"), 2.52)
        self.raster = None                     # without contourpy: a pixel image instead of the shapes
        self.map = None                        # physics.bodies.BodyMap of the view; None = no bodies
        self.lines = None                      # dividing streamlines of the drawn scene (None: none yet)
        self._scene_lines, self._hint = None, None   # the whole scene's (coarser) and its body map
        self.changed = []                      # callbacks: the bodies changed (particles)
        self._timer = QTimer(plot)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DELAY_MS)
        self._timer.timeout.connect(self.update)

    def items(self):
        return [self.fill, self.hatch, self.edge] + ([self.raster] if self.raster is not None else [])

    @property
    def on(self) -> bool:
        return self.canvas.layers.get("bodies", False)

    # ------------------------------------------------------------------ hooks
    def apply_theme(self, theme):
        super().apply_theme(theme)
        body, edge = QColor(theme["body_fill"]), QColor(theme["body_edge"])
        self.fill.setBrush(QBrush(body))
        self.hatch.setBrush(QBrush(QColor(*mix(body, edge, HATCH_ALPHA)), Qt.BDiagPattern))
        pen = QPen(edge)
        pen.setWidthF(EDGE_PX)
        pen.setCosmetic(True)
        self.edge.setPen(pen)
        if self.raster is not None:
            self._draw()

    def view_changed(self):
        if self.on:
            self._timer.start()

    def visibility_changed(self):
        for item in self.items():
            item.setVisible(self.on)

    def shutdown(self):
        self._timer.stop()

    # ------------------------------------------------------------------ data
    def set_result(self, result):
        """New streamlines with their dividing streamlines (full results only)."""
        self.lines = list(result.dividing)
        self._result = result
        if result.scene_dividing is not self._scene_lines:     # a new scene-wide search: a new hint
            self._scene_lines, self._hint = result.scene_dividing, None
        if self.on:
            self.update()

    def refresh(self):
        """The layer was switched on / off."""
        self.update()
        self.visibility_changed()

    @property
    def mask(self):
        """Bool picture of mask_box (True = body), None when there is none."""
        return None if self.map is None else self.map.mask

    @property
    def mask_box(self):
        return None if self.map is None else self.map.box

    def contains(self, z) -> np.ndarray:
        """True for the points (complex array) inside a body (as drawn)."""
        z = np.asarray(z, complex)
        if self.map is None or not self.on:
            return np.zeros(z.shape, bool)
        return self.map.contains(z)

    # ------------------------------------------------------------------ computing, drawing
    def update(self):
        self._timer.stop()
        if self.canvas.is_dragging():
            return                                   # (a new result follows the release)
        bmap = None
        if self.on and self.lines is not None:
            (x0, x1), (y0, y1) = self.canvas.view()
            size = self.vb.size()
            cols, rows = int(max(size.width(), 2)), int(max(size.height(), 2))
            if self._hint is None and self._scene_lines:
                self._hint = scene_map(self.canvas.elements, self._result) or False
            bmap = body_map(self.canvas.elements, (x0, x1, y0, y1), (rows, cols), self.lines,
                            hint=self._hint or None)
            if bmap is not None and bmap.count == 0:
                bmap = None
        self.map = bmap
        self._draw()
        for callback in self.changed:
            callback()

    def _draw(self):
        empty = QPainterPath()
        if self.raster is not None:
            self.plot.removeItem(self.raster)
            self.raster = None
        mask = self.mask
        if mask is None:
            self.fill.setPath(empty)
            self.hatch.setPath(empty)
            self.edge.setData([], [])
            return
        x0, x1, y0, y1 = self.mask_box
        rows, cols = mask.shape
        # cell centers, plus one cell past every side with the edge cells' values: the contour runs
        # through cell centers, and without the extra cells the fill would end half a pixel inside the
        # view (lines under the body showed through there)
        x = x0 + (np.arange(-1, cols + 1) + 0.5) * (x1 - x0) / cols
        y = y0 + (np.arange(-1, rows + 1) + 0.5) * (y1 - y0) / rows
        padded = np.pad(mask, 1, mode="edge").astype(float)
        paths = filled_paths(x, y, padded, [0.0, 0.5, 1.0])
        if paths is None:                                      # no contourpy: one pixel image
            c = QColor(self.theme["body_fill"])
            rgba = np.zeros((rows, cols, 4), np.uint8)
            rgba[mask] = (c.red(), c.green(), c.blue(), 255)
            self.raster = pg.ImageItem(np.ascontiguousarray(rgba.transpose(1, 0, 2)))
            self.raster.setRect(QRectF(x0, y0, x1 - x0, y1 - y0))
            self.add_item(self.raster, 2.5)
            path = empty
        else:
            path = paths[1] if len(paths) > 1 and paths[1] is not None else empty
        self.fill.setPath(path)
        self.hatch.setPath(path)
        xy = self._surface()
        self.edge.setData(xy[:, 0], xy[:, 1])
        self.visibility_changed()

    def _surface(self) -> np.ndarray:
        """The surfaces (the parts of the dividing streamlines with a body on one side), NaN rows
        between the parts."""
        out = []
        for _body, xy in surface_pieces(self.map, self.lines):
            out += [xy, np.full((1, 2), np.nan)]
        return np.vstack(out) if out else np.zeros((0, 2))
