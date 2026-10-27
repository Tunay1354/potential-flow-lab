"""
field_layers.py — the "field" layers of the plot (Phase 4):

  * equipotential lines φ = const   (dashed, spacing chosen so that with the streamlines they form a
                                     flow net: Δφ ≈ typical speed × streamline spacing)
  * speed |V| as a banded color map (contour bands) with a legend
  * pressure coefficient Cp = 1 − (V / V_ref)² as a banded, diverging color map with a legend

Everything is computed on a grid over the view (+ a margin, so a short pan shows no empty edge).
Points in the solid (behind walls, outside a wedge) and next to singular points are left out.
φ of a vortex (and of a sector flow) is multi-valued: it jumps across a branch cut. Grid cells where
φ jumps much more than the local velocity allows are left out, so no false lines bunch along the cut.
"""
import math

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsPathItem

from physics.field import compute_field, complex_potential
from physics.streamlines import view_spacing

from .theme import FONT, first_family

MARGIN = 0.25                    # grid covers the view + 25 % on every side
GRID_POINTS = {1: 150, 2: 240, 3: 400}      # points across the grid for Grid quality Low / Medium / High
MAP_ALPHA = 0.82                 # opacity of the color maps (streamlines stay readable on top)
BANDS = 12                       # about this many color bands
MAX_LEVELS = 400
CROWD_SPEED = 5.0                # φ lines are left out where |V| > 5 × the typical speed of the view


def nice_step(span: float, count: int) -> float:
    """A round step (1, 2, 2.5, 5 × 10^k) that divides `span` into about `count` parts."""
    if not np.isfinite(span) or span <= 0:
        return 1.0
    raw = span / max(count, 1)
    k = 10.0 ** math.floor(math.log10(raw))
    for m in (1.0, 2.0, 2.5, 5.0, 10.0):
        if raw <= m * k * 1.0001:
            return m * k
    return 10.0 * k


def cut_mask(f: np.ndarray, speed: np.ndarray, hx: float, hy: float, factor: float = 4.0) -> np.ndarray:
    """True at grid points next to a jump of f (a branch cut): |Δf| between neighbors much larger
    than |V| · h, the most a smooth potential can change over one grid step."""
    bad = np.zeros(f.shape, bool)
    for axis, h in ((1, hx), (0, hy)):
        df = np.abs(np.diff(f, axis=axis))
        sp = np.diff(speed, axis=axis) * 0.5 + np.take(speed, range(speed.shape[axis] - 1), axis=axis)
        jump = df > factor * np.nan_to_num(sp, nan=0.0) * h + 1e-12
        jump &= np.isfinite(df)
        if axis == 1:
            bad[:, :-1] |= jump
            bad[:, 1:] |= jump
        else:
            bad[:-1, :] |= jump
            bad[1:, :] |= jump
    return bad


def contour_xy(x, y, z, levels):
    """Contour lines of z (NaN = no data) at `levels`, as one (N, 2) array with NaN rows between
    lines (for one PlotCurveItem with connect='finite')."""
    import contourpy
    zm = np.ma.masked_invalid(z)
    if zm.mask.all() or not len(levels):
        return np.zeros((0, 2))
    gen = contourpy.contour_generator(x, y, zm, line_type=contourpy.LineType.ChunkCombinedNan)
    parts = []
    gap = np.array([[np.nan, np.nan]])
    for lev in levels:
        (chunks,) = gen.lines(lev)
        for pts in chunks:
            if pts is not None and len(pts):
                parts += [pts, gap]
    return np.vstack(parts) if parts else np.zeros((0, 2))


def filled_paths(x, y, z, edges):
    """Filled contour bands of z between consecutive `edges` (the first band is open downwards, the
    last upwards), as one QPainterPath per band (holes via the odd-even rule). Vector shapes: smooth
    on the screen and sharp in SVG / PDF exports."""
    import contourpy
    zm = np.ma.masked_invalid(z)
    if zm.mask.all():
        return []
    gen = contourpy.contour_generator(x, y, zm, fill_type=contourpy.FillType.OuterOffset)
    zmin, zmax = float(zm.min()), float(zm.max())
    out = []
    n = len(edges) - 1
    for k in range(n):
        lo = edges[k] if k > 0 else min(edges[0], zmin) - 1.0
        hi = edges[k + 1] if k < n - 1 else max(edges[-1], zmax) + 1.0
        points, offsets = gen.filled(lo, hi)
        xs, ys, conn = [], [], []
        for pts, offs in zip(points, offsets):
            for a, b in zip(offs[:-1], offs[1:]):
                ring = pts[a:b]
                if len(ring) < 3:
                    continue
                c = np.ones(len(ring), dtype=np.int32)
                c[-1] = 0
                xs.append(ring[:, 0])
                ys.append(ring[:, 1])
                conn.append(c)
        if not xs:
            out.append(None)
            continue
        path = pg.arrayToQPath(np.concatenate(xs), np.concatenate(ys), np.concatenate(conn))
        path.setFillRule(Qt.OddEvenFill)
        out.append(path)
    return out


def _mix(a: QColor, b: QColor, t: float) -> tuple:
    t = min(max(t, 0.0), 1.0)
    return tuple(int(round(a.getRgb()[i] + (b.getRgb()[i] - a.getRgb()[i]) * t)) for i in range(3))


def _ramp(stops: list, t: float) -> tuple:
    """Color at t (0…1) of a piecewise-linear ramp through `stops` (hex colors, equally spaced)."""
    t = min(max(t, 0.0), 1.0) * (len(stops) - 1)
    i = min(int(t), len(stops) - 2)
    return _mix(QColor(stops[i]), QColor(stops[i + 1]), t - i)


class ColorLegend(pg.GraphicsWidgetAnchor, pg.GraphicsWidget):
    """Small card in the top-right corner of the plot: title and the color bands with values.
    Part of the plot scene, so it is also in exported figures."""

    W, H = 92, 214

    def __init__(self):
        pg.GraphicsWidget.__init__(self)
        pg.GraphicsWidgetAnchor.__init__(self)
        self.setFlag(self.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setFixedWidth(self.W)
        self.setFixedHeight(self.H)
        self.theme = None
        self.title = ""
        self.edges, self.colors = [], []
        self.setZValue(20)

    def set_bands(self, title, edges, colors):
        self.title, self.edges, self.colors = title, list(edges), list(colors)
        self.update()

    def boundingRect(self):
        return QRectF(0, 0, self.W, self.H)

    def paint(self, p, *args):
        if self.theme is None or len(self.edges) < 2:
            return
        t = self.theme
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setPen(QPen(QColor(t["border"]), 1))
        p.setBrush(QColor(t["panel_bg"]))
        p.drawRect(QRectF(0.5, 0.5, self.W - 1, self.H - 1))
        mono = QFont(first_family("mono"))
        mono.setPointSizeF(FONT["mono_size_pt"] - 1.5)
        p.setFont(mono)
        p.setPen(QColor(t["text"]))
        p.drawText(QRectF(8, 5, self.W - 12, 16), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        top, bottom, x0, bw = 26.0, self.H - 10.0, 10.0, 14.0
        n = len(self.colors)
        hb = (bottom - top) / n
        for k, c in enumerate(self.colors):             # highest value on top
            y = bottom - (k + 1) * hb
            p.fillRect(QRectF(x0, y, bw, hb + 0.5), QColor(*c))
        p.setPen(QPen(QColor(t["border"]), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(x0, top, bw, bottom - top))
        every = max(1, int(math.ceil((n + 1) / 7)))       # at most ~7 labels
        shown = list(range(0, len(self.edges), every))
        if shown[-1] != len(self.edges) - 1:
            shown[-1] = len(self.edges) - 1                  # always the top value, never two crowded
        p.setPen(QColor(t["text"]))
        for k in shown:
            e = self.edges[k]
            y = bottom - k * hb
            p.drawLine(QPointF(x0 + bw, y), QPointF(x0 + bw + 4, y))
            p.drawText(QRectF(x0 + bw + 7, y - 7, self.W - x0 - bw - 9, 14), Qt.AlignLeft | Qt.AlignVCenter,
                       _label(e))


def _label(v: float) -> str:
    if abs(v) < 1e-12:
        return "0"
    return (f"{v:.3g}" if abs(v) >= 1e-3 else f"{v:.1e}").replace("-", "−")


class FieldLayers:
    """Items and drawing of the field layers of one PlotCanvas."""

    def __init__(self, plot, vb):
        self.plot, self.vb = plot, vb
        self.theme = None
        self.phi = pg.PlotCurveItem(connect="finite")
        self.phi.setZValue(0.6)
        self.bands = []                       # one filled path item per color band
        self.map_lines = pg.PlotCurveItem(connect="finite")
        self.map_lines.setZValue(-4)
        for it in (self.phi, self.map_lines):
            it.setVisible(False)
            plot.addItem(it)
        self.legend = ColorLegend()
        self.legend.setParentItem(vb)
        self.legend.anchor(itemPos=(1, 0), parentPos=(1, 0), offset=(-12, 12))
        self.legend.setVisible(False)
        self.covered = None          # region of the last computation (x0, x1, y0, y1)
        self.message = ""            # why a layer shows nothing (e.g. Cp without reference speed)

    def items(self):
        return [self.phi, self.map_lines, self.legend] + self.bands

    def apply_theme(self, theme):
        self.theme = theme
        self.legend.theme = theme
        pen = pg.mkPen(theme["equipotential"], width=1.1, style=Qt.DashLine)
        self.phi.setPen(pen)
        line = QColor(theme["plot_axis"])
        line.setAlphaF(0.28)
        self.map_lines.setPen(pg.mkPen(line, width=0.8))

    def hide_all(self):
        self._clear_map()
        self.phi.setVisible(False)

    def needs_update(self, view) -> bool:
        """True if the view left the computed region (or zoomed a lot)."""
        if self.covered is None:
            return True
        (x0, x1), (y0, y1) = view
        a0, a1, b0, b1 = self.covered
        inside = a0 <= x0 and x1 <= a1 and b0 <= y0 and y1 <= b1
        scale = (x1 - x0) / ((a1 - a0) / (1 + 2 * MARGIN))
        return not inside or not 0.7 < scale < 1.4

    def update(self, elements, view, layers: dict, quality: int = 2, v_ref=None, density: float = 1.0):
        """Recompute the field layers that are switched on (layers: key -> visible)."""
        want_phi = layers.get("equipotential", False)
        want_map = "cp" if layers.get("cp") else ("speed" if layers.get("speed") else None)
        self.message = ""
        if not (want_phi or want_map) or not any(e.enabled for e in elements):
            self.hide_all()
            self.covered = None
            return
        (x0, x1), (y0, y1) = view
        W, H = x1 - x0, y1 - y0
        gx = (x0 - MARGIN * W, x1 + MARGIN * W)
        gy = (y0 - MARGIN * H, y1 + MARGIN * H)
        nx = GRID_POINTS.get(int(quality), 240)
        ny = max(20, int(round(nx * (gy[1] - gy[0]) / (gx[1] - gx[0]))))
        f = compute_field(elements, gx, gy, nx, ny)
        self.covered = (gx[0], gx[1], gy[0], gy[1])
        x, y = f.grid.x, f.grid.y
        speed = f.speed

        # equipotential lines
        if want_phi:
            phi = complex_potential(elements, f.grid.Z).real
            phi[f.mask] = np.nan
            hx, hy = x[1] - x[0], y[1] - y[0]
            phi[cut_mask(phi, speed, hx, hy)] = np.nan
            inview = (f.grid.X >= x0) & (f.grid.X <= x1) & (f.grid.Y >= y0) & (f.grid.Y <= y1)
            typical = np.nanmedian(speed[inview]) if np.any(np.isfinite(speed[inview])) else np.nan
            if np.isfinite(typical):
                phi[speed > CROWD_SPEED * typical] = np.nan     # lines would crowd into a dark blot
            d = view_spacing(elements, (x0, x1), (y0, y1), density)
            step = typical * d if np.isfinite(typical) and typical > 0 else np.nan
            vals = phi[np.isfinite(phi)]
            if vals.size and np.isfinite(step):
                lo, hi = np.percentile(vals, 0.5), np.percentile(vals, 99.5)
                if (hi - lo) / step > MAX_LEVELS:
                    step = (hi - lo) / MAX_LEVELS
                levels = np.arange(math.floor(lo / step), math.ceil(hi / step) + 1) * step
                xy = contour_xy(x, y, phi, levels)
                self.phi.setData(xy[:, 0], xy[:, 1]) if len(xy) else self.phi.setData([], [])
            else:
                self.phi.setData([], [])
            self.phi.setVisible(True)
        else:
            self.phi.setVisible(False)

        # color map (|V| or Cp)
        if want_map is None:
            self._clear_map()
            return
        if want_map == "cp":
            v_ref = v_ref or f.v_ref
            if not v_ref:
                self.message = "Cp needs a reference speed: add a uniform flow or set V_ref in Computation."
                self._clear_map()
                return
            values = 1.0 - (speed / v_ref) ** 2
            edges, colors = self._cp_bands(values)
            title = "Cp"
        else:
            values = speed
            edges, colors = self._speed_bands(values)
            title = "|V|  [m/s]"
        if len(edges) < 2:
            self._clear_map()
            return
        self._clear_map()
        for path, c in zip(filled_paths(x, y, values, edges), colors):
            if path is None:
                continue
            item = QGraphicsPathItem(path)
            item.setPen(QPen(Qt.NoPen))
            item.setBrush(QBrush(QColor(c[0], c[1], c[2], int(255 * MAP_ALPHA))))
            item.setZValue(-5)
            self.plot.addItem(item)
            self.bands.append(item)
        xy = contour_xy(x, y, values, edges[1:-1])
        self.map_lines.setData(xy[:, 0], xy[:, 1]) if len(xy) else self.map_lines.setData([], [])
        self.legend.set_bands(title, edges, colors)
        self.map_lines.setVisible(True)
        self.legend.setVisible(True)

    def _clear_map(self):
        for it in self.bands:
            self.plot.removeItem(it)
        self.bands = []
        self.map_lines.setVisible(False)
        self.legend.setVisible(False)

    # ------------------------------------------------------------------ color bands
    def _speed_bands(self, speed):
        vals = speed[np.isfinite(speed)]
        if not vals.size:
            return [], []
        hi = float(np.percentile(vals, 98))
        step = nice_step(hi, BANDS)
        top = max(step, math.ceil(hi / step) * step)
        edges = np.arange(0.0, top + 0.5 * step, step)       # faster points: in the last band
        stops = self.theme["map_speed"]
        n = len(edges) - 1
        return edges, [_ramp(stops, (k + 0.5) / n) for k in range(n)]

    def _cp_bands(self, cp):
        vals = cp[np.isfinite(cp)]
        if not vals.size:
            return [], []
        lo = float(min(np.percentile(vals, 2), -0.25))
        step = nice_step(1.0 - lo, BANDS)
        bottom = math.floor(lo / step) * step
        edges = list(np.arange(bottom, 1.0 + 0.5 * step, step))
        if edges[-1] < 1.0 - 1e-9:
            edges.append(edges[-1] + step)
        neg, mid, pos = self.theme["map_cp"]
        colors = []
        for a, b in zip(edges[:-1], edges[1:]):
            c = 0.5 * (a + b)
            colors.append(_mix(QColor(mid), QColor(neg), c / bottom) if c < 0 else
                          _mix(QColor(mid), QColor(pos), c / max(edges[-1], 1e-9)))
        return np.asarray(edges, float), colors          # Cp below the first edge: in the first band
