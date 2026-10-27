"""
field_layer.py — the "field" layers of the plot:

  * equipotential lines φ = const   (dashed, spacing chosen so that with the streamlines they form a
                                     flow net: Δφ ≈ typical speed × streamline spacing)
  * speed |V| as a banded color map (contour bands) with a legend
  * pressure coefficient Cp = 1 − (V / V_ref)² as a banded, diverging color map with a legend

Everything is computed on a grid over the view (+ a margin, so a short pan shows no empty edge), after
the view has settled for a moment. Points in the solid (behind walls, outside a wedge) are left out;
φ lines keep out of a circle round every singular point (inside it they would crowd into a blot: φ → ∞
there) and out of solid bodies; the color bands are filled right up to the singular points. φ of a vortex
(and of a sector flow) is multi-valued: it jumps across a branch cut. Grid cells where φ jumps much
more than the local velocity allows are left out, so no false lines bunch along the cut.

`update(...)` works without a canvas (tests); in the plot, `refresh()` calls it with the canvas state.
"""
import math

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsPathItem

from physics.field import (active, complex_potential, complex_velocity, compute_field, fluid_mask,
                           singular_points, singularity_mask)
from physics.images import resolve
from physics.streamlines import view_spacing

from .contours import CROWD_SPEED, contour_xy, cp_bands, cut_mask, filled_paths, speed_bands
from .layer import PlotLayer
from .legend import ColorLegend

KEYS = ("equipotential", "speed", "cp")     # the layer switches (canvas.layers) of this layer
MARGIN = 0.25                    # grid covers the view + 25 % on every side
GRID_POINTS = {1: 150, 2: 240, 3: 400}      # points across the grid for Grid quality Low / Medium / High
MAP_ALPHA = 0.82                 # opacity of the color maps (streamlines stay readable on top)
MAX_LEVELS = 400
PHI_DASH = (3.0, 3.0)            # φ lines: dash, gap (× the line width)
EXTREME_SPEED = 3.0              # φ lines are also left out where |V| > this × CROWD_SPEED × typical
SETTLE_MS = 90                   # computed this long after the last zoom / pan step


def crowd_circles(elements, limit: float, r_min: float, r_max: float, n_ring: int = 48, n_radii: int = 40):
    """[(singular point, radius)]: the smallest circle round each singular point outside of which the
    speed on the circle stays below `limit` (r_min … r_max)."""
    els = active(elements)
    flows = resolve(els)
    radii = np.geomspace(r_min, max(r_max, 1.01 * r_min), n_radii)
    ring = np.exp(2j * np.pi * (np.arange(n_ring) + 0.5) / n_ring)
    out = []
    for s in singular_points(els):
        z = (s + radii[:, None] * ring[None, :]).ravel()
        with np.errstate(all="ignore"):
            sp = np.abs(complex_velocity(flows, z))
        sp = np.where(np.isfinite(sp) & fluid_mask(els, z), sp, 0.0).reshape(n_radii, n_ring)
        ok = (sp <= limit).all(axis=1)
        out.append((complex(s), float(radii[int(np.argmax(ok))] if ok.any() else radii[-1])))
    return out


class FieldLayer(PlotLayer):
    FADES_WHILE_DRAGGING = True

    def __init__(self, plot, vb):
        super().__init__(plot, vb)
        self.phi = self.add_item(pg.PlotCurveItem(connect="finite"), 0.6)
        self.map_lines = self.add_item(pg.PlotCurveItem(connect="finite"), -4)
        self.phi.setVisible(False)
        self.map_lines.setVisible(False)
        self.bands = []                       # one filled path item per color band
        self.legend = ColorLegend()
        self.legend.setParentItem(vb)
        self.legend.anchor(itemPos=(1, 0), parentPos=(1, 0), offset=(-12, 12))
        self.legend.setVisible(False)
        self.covered = None          # region of the last computation (x0, x1, y0, y1)
        self.message = ""            # why a layer shows nothing (e.g. Cp without reference speed)
        self._timer = QTimer(plot)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SETTLE_MS)
        self._timer.timeout.connect(self.refresh)

    def items(self):
        return [self.phi, self.map_lines, self.legend] + self.bands

    # ------------------------------------------------------------------ hooks
    def apply_theme(self, theme):
        super().apply_theme(theme)
        self.legend.theme = theme
        # exactly 1 px: Qt draws 1-px lines on a fast path; any other width (1.1) goes through its general
        # stroker, ~30× slower with the many short pieces of the φ lines
        pen = pg.mkPen(theme["equipotential"], width=1.0)
        pen.setDashPattern(list(PHI_DASH))
        self.phi.setPen(pen)
        line = QColor(theme["plot_axis"])
        line.setAlphaF(0.28)
        self.map_lines.setPen(pg.mkPen(line, width=0.8))
        if self.canvas is not None:
            self.schedule(force=True)

    def scene_changed(self):
        self.schedule(force=True)

    def view_changed(self):
        if self.is_on() and self.needs_update(self.canvas.view()):
            self.schedule()

    # ------------------------------------------------------------------ in the plot
    def is_on(self) -> bool:
        return any(self.canvas.layers[k] for k in KEYS)

    def schedule(self, force: bool = False, now: bool = False):
        """Recompute soon (after the view settles); force = also if the view is still covered (scene,
        settings or theme changed); now = at once."""
        if force:
            self.covered = None
        if not self.is_on():
            self.hide_all()
            return
        if now:
            self._timer.stop()
            self.refresh()
        else:
            self._timer.start()

    def refresh(self):
        """Compute with the canvas state (not while an element is dragged: done on release)."""
        cv = self.canvas
        if cv.is_dragging():
            return
        s = cv.settings
        try:
            self.update(cv.elements, cv.view(), cv.layers, s.field_quality, s.cp_reference, s.density)
        except Exception as exc:                     # never let a field layer break the window
            self.hide_all()
            cv.message.emit(f"Field layers could not be drawn: {exc}")
            return
        if self.message:
            cv.message.emit(self.message)

    # ------------------------------------------------------------------ computation
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
        # only the singular points themselves are left out (the color bands are filled up to them)
        f = compute_field(elements, gx, gy, nx, ny, mask_radius=1e-9 * (gx[1] - gx[0]))
        self.covered = (gx[0], gx[1], gy[0], gy[1])
        fluid = fluid_mask(elements, f.grid.Z)
        inview = (f.grid.X >= x0) & (f.grid.X <= x1) & (f.grid.Y >= y0) & (f.grid.Y <= y1)
        if want_phi:
            self._draw_equipotentials(elements, f, fluid, inview, view, density)
        self.phi.setVisible(want_phi)
        if want_map is None:
            self._clear_map()
        else:
            self._draw_map(want_map, elements, f, fluid, inview, view, v_ref)

    def _draw_equipotentials(self, elements, f, fluid, inview, view, density):
        x, y, speed = f.grid.x, f.grid.y, f.speed
        phi = complex_potential(elements, f.grid.Z).real
        phi[f.mask | singularity_mask(elements, f.grid.Z, 1.5 * f.grid.spacing) | ~fluid] = np.nan
        phi[cut_mask(phi, speed, x[1] - x[0], y[1] - y[0])] = np.nan
        typical = np.nanmedian(speed[inview]) if np.any(np.isfinite(speed[inview])) else np.nan
        if np.isfinite(typical):                        # lines would crowd into a dark blot:
            (x0, x1), (y0, y1) = view
            h = max(x[1] - x[0], y[1] - y[0])
            for s, r in crowd_circles(elements, CROWD_SPEED * typical, 1.5 * h, 0.5 * max(x1 - x0, y1 - y0)):
                phi[np.abs(f.grid.Z - s) < r] = np.nan      # a clean circle round a singular point
            phi[speed > EXTREME_SPEED * CROWD_SPEED * typical] = np.nan
        bodies = getattr(self.canvas, "bodies", None)
        if bodies is not None and bodies.map is not None:
            phi[bodies.contains(f.grid.Z)] = np.nan          # not inside solid bodies
        step = typical * view_spacing(elements, *view, density) if np.isfinite(typical) and typical > 0 else np.nan
        vals = phi[np.isfinite(phi)]
        xy = np.zeros((0, 2))
        if vals.size and np.isfinite(step):
            lo, hi = np.percentile(vals, 0.5), np.percentile(vals, 99.5)
            if (hi - lo) / step > MAX_LEVELS:
                step = (hi - lo) / MAX_LEVELS
            levels = np.arange(math.floor(lo / step), math.ceil(hi / step) + 1) * step
            xy = contour_xy(x, y, phi, levels)
        self.phi.setData(xy[:, 0], xy[:, 1])

    def _draw_map(self, kind, elements, f, fluid, inview, view, v_ref):
        """Color bands of |V| (kind 'speed') or Cp (kind 'cp') with the legend."""
        x, y, speed = f.grid.x, f.grid.y, f.speed
        (x0, x1), _ = view
        # the legend range comes from the visible fluid, away from singular points (otherwise a zoom
        # near a source or into a body would stretch it to huge values and wash out the bands)
        keep_off = max(3 * f.grid.spacing, 0.04 * (x1 - x0))
        sample = fluid & inview & ~singularity_mask(elements, f.grid.Z, keep_off) & np.isfinite(speed)
        if not sample.any():
            sample = fluid & inview & np.isfinite(speed)
        if kind == "cp":
            v_ref = v_ref or f.v_ref
            if not v_ref:
                self.message = "Cp needs a reference speed: add a uniform flow or set V_ref in Computation."
                self._clear_map()
                self.legend.set_note("Cp", "Cp = 1 − (V / V∞)² needs a reference speed. This scene has no "
                                     "uniform flow (V∞).", "Set V_ref in Computation  →")
                self.legend.setVisible(True)
                return
            values = 1.0 - (speed / v_ref) ** 2
            edges, colors = cp_bands(values[sample], self.theme["map_cp"])
            title = "Cp"
        else:
            values = speed
            edges, colors = speed_bands(values[sample], self.theme["map_speed"])
            title = "|V|  [m/s]"
        self._clear_map()
        if len(edges) < 2:
            return
        # next to a singular point |V| -> ∞ (Cp -> −∞): beyond the legend, so the last (first) band
        # is filled right up to the point instead of leaving a hole whose shape depends on the grid
        span = edges[-1] - edges[0]
        lo_cap, hi_cap = edges[0] - span, edges[-1] + span
        values = np.where(fluid & ~np.isfinite(values), lo_cap if kind == "cp" else hi_cap, values)
        values = np.where(fluid, np.clip(values, lo_cap, hi_cap), np.nan)
        paths = filled_paths(x, y, values, edges)
        if paths is None:                                   # no contourpy: one pixel image of the bands
            self._raster_bands(x, y, values, edges, colors)
            paths = []
        for path, c in zip(paths, colors):
            if path is None:
                continue
            item = QGraphicsPathItem(path)
            item.setPen(QPen(Qt.NoPen))
            item.setBrush(QBrush(QColor(c[0], c[1], c[2], int(255 * MAP_ALPHA))))
            self.bands.append(self.add_item(item, -5))
        xy = contour_xy(x, y, values, edges[1:-1])
        self.map_lines.setData(xy[:, 0], xy[:, 1])
        self.legend.set_bands(title, edges, colors)
        self.map_lines.setVisible(True)
        self.legend.setVisible(True)

    def _raster_bands(self, x, y, values, edges, colors):
        idx = np.clip(np.searchsorted(edges, values, side="right") - 1, 0, len(colors) - 1)
        lut = np.array([(*c, int(255 * MAP_ALPHA)) for c in colors], dtype=np.uint8)
        rgba = lut[idx]
        rgba[~np.isfinite(values)] = (0, 0, 0, 0)
        img = pg.ImageItem(np.ascontiguousarray(rgba.transpose(1, 0, 2)))
        hx, hy = x[1] - x[0], y[1] - y[0]
        img.setRect(QRectF(x[0] - hx / 2, y[0] - hy / 2, hx * len(x), hy * len(y)))
        self.bands.append(self.add_item(img, -5))

    def _clear_map(self):
        for it in self.bands:
            self.plot.removeItem(it)
        self.bands = []
        self.map_lines.setVisible(False)
        self.legend.setVisible(False)
