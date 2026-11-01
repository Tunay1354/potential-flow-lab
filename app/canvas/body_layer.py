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
from .scaled_curve import ScaledCurve

DELAY_MS = 90                   # after a zoom / pan
HATCH_ALPHA = 0.18
EDGE_PX = 2.0
JOIN_PX = 14                    # a surface piece ending this close to a stagnation point is drawn up to it


class BodyLayer(PlotLayer):
    FADES_WHILE_DRAGGING = True

    def __init__(self, plot, vb):
        super().__init__(plot, vb)
        self.fill = self.add_item(QGraphicsPathItem(), 2.5)          # over the streamlines, arrows and the
        self.hatch = self.add_item(QGraphicsPathItem(), 2.51)        # animation; under the symbols
        for item in (self.fill, self.hatch):
            item.setPen(QPen(Qt.NoPen))
        self.edge = self.add_item(ScaledCurve(connect="finite"), 2.52)
        self.raster = None                     # without contourpy: a pixel image instead of the shapes
        self.map = None                        # physics.bodies.BodyMap of the view; None = no bodies
        self.lines = None                      # dividing streamlines of the drawn scene (None: none yet)
        self._inner = []                       # branches into bodies (borders only, see set_result)
        self._scene_lines, self._hint = None, None   # the whole scene's (coarser) and its body map
        self._result = None                    # the streamline result the lines came from
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
        self._inner = list(result.inner)              # branches into bodies: borders, never drawn
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
            bmap = body_map(self.canvas.elements, (x0, x1, y0, y1), (rows, cols), self.lines + self._inner,
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
        x0, x1, _y0, _y1 = self.map.box
        join = JOIN_PX * (x1 - x0) / self.map.mask.shape[1]
        stag = np.array([p.z for p in getattr(self.canvas, "stagnation_points", [])], dtype=complex)
        pieces = [_to_stagnation(xy, stag, join) for _body, xy in surface_pieces(self.map, self.lines)]
        for xy in pieces + _bridges(pieces, join):
            out += [xy, np.full((1, 2), np.nan)]
        return np.vstack(out) if out else np.zeros((0, 2))


def _to_stagnation(xy, stag, reach):
    """The piece with its ends joined to a stagnation point within `reach`: a body surface runs
    through its stagnation points, but next to them a piece can stop a few pixels short (where the
    surface is another line, e.g. a branch into a practically closed body)."""
    if not stag.size or len(xy) < 2:
        return xy
    z = xy[:, 0] + 1j * xy[:, 1]
    head, tail = [], []
    for end, lst in ((z[0], head), (z[-1], tail)):
        d = np.abs(stag - end)
        k = int(np.argmin(d))
        if 1e-12 < d[k] < reach:
            lst.append(stag[k])
    z = np.concatenate([head, z, tail])
    return np.column_stack([z.real, z.imag])


def _bridges(pieces, reach):
    """Short segments joining piece ends that are within `reach` of an end of another piece (each
    end once, nearest first): the surface of a practically closed body changes from one line to
    another a few pixels before a stagnation point."""
    ends = []
    for k, xy in enumerate(pieces):
        if len(xy) >= 2:
            ends += [(k, complex(*xy[0])), (k, complex(*xy[-1]))]
    pairs = []
    for a in range(len(ends)):
        for b in range(a + 1, len(ends)):
            if ends[a][0] != ends[b][0]:
                d = abs(ends[a][1] - ends[b][1])
                if 1e-12 < d < reach:
                    pairs.append((d, a, b))
    used, out = set(), []
    for _d, a, b in sorted(pairs):
        if a in used or b in used:
            continue
        used |= {a, b}
        za, zb = ends[a][1], ends[b][1]
        out.append(np.array([[za.real, za.imag], [zb.real, zb.imag]]))
    return out
