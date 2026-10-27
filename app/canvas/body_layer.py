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

from physics.bodies import body_mask

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
        self.mask = None                       # bool (rows, cols) of mask_box; None = no bodies
        self.mask_box = None
        self.lines = []                        # dividing streamlines of the drawn scene
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
        if self.on:
            self.update()

    def refresh(self):
        """The layer was switched on / off."""
        self.update()
        self.visibility_changed()

    def contains(self, z) -> np.ndarray:
        """True for the points (complex array) inside a body (as drawn)."""
        z = np.asarray(z, complex)
        if self.mask is None or not self.on:
            return np.zeros(z.shape, bool)
        x0, x1, y0, y1 = self.mask_box
        rows, cols = self.mask.shape
        with np.errstate(invalid="ignore"):
            i = np.floor((z.real - x0) / (x1 - x0) * cols)
            j = np.floor((z.imag - y0) / (y1 - y0) * rows)
        ok = (i >= 0) & (i < cols) & (j >= 0) & (j < rows)
        out = np.zeros(z.shape, bool)
        out[ok] = self.mask[j[ok].astype(np.int64), i[ok].astype(np.int64)]
        return out

    # ------------------------------------------------------------------ computing, drawing
    def update(self):
        self._timer.stop()
        if self.canvas.is_dragging():
            return                                   # (a new result follows the release)
        mask = None
        if self.on and self.lines:
            (x0, x1), (y0, y1) = self.canvas.view()
            size = self.vb.size()
            cols, rows = int(max(size.width(), 2)), int(max(size.height(), 2))
            self.mask_box = (x0, x1, y0, y1)
            mask = body_mask(self.canvas.elements, self.mask_box, (rows, cols), self.lines)
            if mask is not None and not mask.any():
                mask = None
        self.mask = mask
        self._draw()
        for callback in self.changed:
            callback()

    def _draw(self):
        empty = QPainterPath()
        if self.raster is not None:
            self.plot.removeItem(self.raster)
            self.raster = None
        if self.mask is None:
            self.fill.setPath(empty)
            self.hatch.setPath(empty)
            self.edge.setData([], [])
            return
        x0, x1, y0, y1 = self.mask_box
        rows, cols = self.mask.shape
        x = x0 + (np.arange(cols) + 0.5) * (x1 - x0) / cols
        y = y0 + (np.arange(rows) + 0.5) * (y1 - y0) / rows
        paths = filled_paths(x, y, self.mask.astype(float), [0.0, 0.5, 1.0])
        if paths is None:                                      # no contourpy: one pixel image
            c = QColor(self.theme["body_fill"])
            rgba = np.zeros((rows, cols, 4), np.uint8)
            rgba[self.mask] = (c.red(), c.green(), c.blue(), 255)
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
        """The parts of the dividing streamlines with a body on one side (and free stream on the
        other), NaN rows between the parts."""
        x0, x1, y0, y1 = self.mask_box
        rows, cols = self.mask.shape
        probe = 3.0 * (x1 - x0) / cols                       # 3 cells to each side
        out = []
        for xy in self.lines:
            if len(xy) < 2:
                continue
            z = xy[:, 0] + 1j * xy[:, 1]
            t = np.gradient(z)
            n = 1j * t / np.where(np.abs(t) > 0, np.abs(t), 1.0)
            a, b = self.contains(z + probe * n), self.contains(z - probe * n)
            keep = a != b
            if not keep.any():
                continue
            pts = np.where(keep[:, None], xy, np.nan)
            out.append(pts)
            out.append(np.full((1, 2), np.nan))
        return np.vstack(out) if out else np.zeros((0, 2))
