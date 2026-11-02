"""
surface_layer.py — "Surface pressure" layer: the surfaces of the solid bodies and the walls drawn as
thick lines colored by Cp (blue = suction, red = stagnation, Cp = 1), with a legend in the top-left
corner. It also holds the surfaces for the Surface pressure panel (app/surface_panel.py).

The body surfaces belong to the whole scene (physics.surface.body_surfaces: independent of the view)
and are computed in a background thread whenever the scene changes — only while someone needs them
(this layer is on or the panel is open). The walls are infinite: their wetted part over the view is
sampled again after a zoom / pan (quick, in the GUI thread). Cp uses the plot's reference speed
(V∞, or Computation → Cp reference).
"""
import math

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QObject, QThreadPool, QTimer, Qt, Signal

from physics.surface import body_surfaces, wall_surfaces

from .contours import nice_step, ramp
from .layer import BackgroundJob, PlotLayer
from .legend import ColorLegend
from .scaled_curve import ScaledCurve

BINS = 48                        # colors along the lines
LINE_PX = 4.5
WALL_DELAY_MS = 120


class _Done(QObject):
    done = Signal(int, object)           # generation, list of Surface / exception


def cp_scale(values) -> float:
    """The lowest Cp of the color scale: a round value at (about) the lowest Cp on the surfaces —
    robust: a few points next to a singular point do not stretch it. At most −0.5."""
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    if not v.size:
        return -1.0
    lo = float(np.percentile(v, 0.5))
    step = nice_step(1.0 - lo, 6)
    return min(-0.5, math.floor(lo / step) * step)


def cp_color_t(cp, lo: float) -> np.ndarray:
    """Position 0 … 1 on the color ramp: lo … 0 on the lower half (suction), 0 … 1 on the upper."""
    cp = np.asarray(cp, float)
    return np.where(cp < 0, 0.5 * np.clip((cp - lo) / (0.0 - lo), 0.0, 1.0), 0.5 + 0.5 * np.clip(cp, 0.0, 1.0))


def cp_bins(cp, lo: float) -> np.ndarray:
    """Color bin 0 … BINS − 1 of every Cp value (NaN — a surface point on a singular point — gets bin 0
    without a cast warning; the surfaces leave those points out)."""
    t = np.nan_to_num(cp_color_t(cp, lo), nan=0.0)
    return np.clip((t * BINS).astype(int), 0, BINS - 1)


class SurfaceLayer(PlotLayer):
    FADES_WHILE_DRAGGING = True

    def __init__(self, plot, vb):
        super().__init__(plot, vb)
        # bodies under the element symbols; walls over the wall line (the element layer draws it at z 4)
        self.curves = [self.add_item(ScaledCurve(connect="finite"), 2.55) for _ in range(BINS)]
        self.wall_curves = [self.add_item(ScaledCurve(connect="finite"), 4.05) for _ in range(BINS)]
        self.marker = self.add_item(pg.ScatterPlotItem(size=11, symbol="o"), 2.6)     # panel hover
        self.marker.setVisible(False)
        self.legend = ColorLegend()
        self.legend.setParentItem(vb)
        self.legend.anchor(itemPos=(0, 0), parentPos=(0, 0), offset=(12, 12))
        self.legend.setVisible(False)
        self.bodies = []                         # physics.surface.Surface of the whole scene
        self.walls = []                          # … of the walls over the view
        self.computing = False                   # bodies being computed (the panel says so)
        self.panel_open = False                  # the Surface pressure panel needs the surfaces too
        self.changed = []                        # callbacks: new surfaces / colors (the panel)
        self.lo = -1.0                           # lowest Cp of the color scale
        self._gen = 0
        self._stale = True                       # the bodies are not of the current scene
        self.background = True                   # False: computed at once (tests, scripts)
        self._pool = QThreadPool(plot)
        self._pool.setMaxThreadCount(1)
        self._done = _Done(plot)
        self._done.done.connect(self._on_done)
        self._wall_timer = QTimer(plot)
        self._wall_timer.setSingleShot(True)
        self._wall_timer.setInterval(WALL_DELAY_MS)
        self._wall_timer.timeout.connect(self._update_walls)

    def items(self):
        return self.curves + self.wall_curves + [self.marker]

    @property
    def on(self) -> bool:
        return self.canvas.layers.get("surface", False)

    @property
    def wanted(self) -> bool:
        return self.on or self.panel_open

    def surfaces(self) -> list:
        return list(self.bodies) + list(self.walls)

    # ------------------------------------------------------------------ hooks
    def apply_theme(self, theme):
        super().apply_theme(theme)
        self.legend.theme = theme
        self.marker.setPen(pg.mkPen(theme["ink"], width=1.5))
        self.marker.setBrush(pg.mkBrush(theme["panel_bg"]))
        self.redraw()

    def scene_changed(self):
        self._gen += 1
        self._stale = True
        self.bodies, self.walls = [], []
        if self.wanted:
            self.refresh()
        else:
            self.redraw()

    def view_changed(self):
        if self.wanted:
            self._wall_timer.start()

    def visibility_changed(self):
        on = self.on
        for c in self.curves + self.wall_curves:
            c.setVisible(on)
        # without a reference speed: the same note card as the Cp color bands (click: Cp reference)
        missing = self._v_ref() is None and self._has_elements()           # (an empty page: nothing missing)
        self.legend.setVisible(on and (missing or (bool(self.surfaces()) and self._v_ref() is not None)))

    def shutdown(self):
        self._wall_timer.stop()
        self._gen += 1
        self._pool.waitForDone(10000)

    # ------------------------------------------------------------------ computing
    def refresh(self):
        """The layer was switched on or the panel opened: bring the surfaces up to date."""
        if not self.wanted:
            self.visibility_changed()
            return
        self._update_walls(notify=False)
        if self._stale:
            self._start()
        else:
            self.redraw()
        self.visibility_changed()

    def _start(self):
        self._stale = False
        self.computing = True
        gen, elements = self._gen, list(self.canvas.elements)

        def work():
            try:
                result = body_surfaces(elements)
            except Exception as exc:                     # reported in the GUI thread
                result = exc
            self._done.done.emit(gen, result)

        if self.background:
            self._pool.start(BackgroundJob(work))
        else:
            work()
        self.redraw()

    def _on_done(self, gen, result):
        if gen != self._gen:
            return
        self.computing = False
        if isinstance(result, BaseException):
            self.bodies = []
            self.redraw()
            raise result
        self.bodies = result
        self.redraw()

    def wait(self, msecs: int = 30000) -> bool:
        return self._pool.waitForDone(msecs)

    def _update_walls(self, notify: bool = True):
        if not self.wanted:
            return
        try:
            self.walls = wall_surfaces(self.canvas.elements, self.canvas.view())
        except Exception:                                # noqa: BLE001 - an invalid scene: no walls drawn
            self.walls = []
        if notify:
            self.redraw()

    # ------------------------------------------------------------------ drawing
    def _has_elements(self) -> bool:
        return self.canvas is not None and any(e.enabled for e in self.canvas.elements)

    def _v_ref(self):
        return self.canvas.cp_reference() if self.canvas is not None else None

    def redraw(self):
        """Colors of the lines (and the legend) from the current surfaces and reference speed."""
        if self.theme is None or self.canvas is None:
            return
        v_ref = self._v_ref()
        surfaces = self.surfaces()
        cps = [s.cp(v_ref) for s in surfaces]
        self.lo = cp_scale(np.concatenate(cps)) if cps and v_ref else -1.0
        stops = self.theme["surface_cp"]
        colors = [ramp(stops, (k + 0.5) / BINS) for k in range(BINS)]
        for kind, curves in (("body", self.curves), ("wall", self.wall_curves)):
            parts = [[] for _ in range(BINS)]
            if v_ref:
                for s, cp in zip(surfaces, cps):
                    if s.kind != kind:
                        continue
                    z = s.z if not s.closed else np.append(s.z, s.z[0])
                    cp = cp if not s.closed else np.append(cp, cp[0])
                    mid = 0.5 * (cp[:-1] + cp[1:])
                    k = cp_bins(mid, self.lo)
                    for b in np.unique(k[np.isfinite(mid)]):
                        idx = np.nonzero(k == b)[0]
                        seg = np.empty(3 * idx.size, complex)          # a, b, NaN for every segment
                        seg[0::3], seg[1::3], seg[2::3] = z[idx], z[idx + 1], np.nan
                        parts[b].append(seg)
            for b, curve in enumerate(curves):
                pen = pg.mkPen(colors[b], width=LINE_PX)
                pen.setCapStyle(Qt.RoundCap)
                pen.setCosmetic(True)
                if parts[b]:
                    seg = np.concatenate(parts[b])
                    curve.setData(seg.real, seg.imag, pen=pen)
                else:
                    curve.setData([], [], pen=pen)
        if not v_ref:
            self.legend.set_note("Cp surface", "Cp = 1 − (V / V∞)² needs a reference speed. This scene has "
                                 "no uniform flow (V∞).", "Set V_ref in Computation  →")
        elif surfaces:
            edges, band_colors = self.legend_bands(colors)
            self.legend.set_bands("Cp surface", edges, band_colors)
        self.visibility_changed()
        for callback in self.changed:
            callback()

    def legend_bands(self, colors=None):
        """Band edges (lo … 1) and their colors for the legend."""
        lo = self.lo
        step = nice_step(-lo, 5)
        edges = list(np.arange(0.0, lo - 1e-9, -step)) + [lo, 0.5, 1.0]          # even steps down from 0
        edges = sorted(set(round(float(e), 9) for e in edges if e >= lo - 1e-9))
        stops = self.theme["surface_cp"]
        mids = [0.5 * (a + b) for a, b in zip(edges[:-1], edges[1:])]
        return edges, [ramp(stops, float(cp_color_t(m, lo))) for m in mids]

    def color_of(self, cp) -> list:
        """RGB colors (0–255) of Cp values on this layer's scale, in its BINS steps (the panel's curve)."""
        stops = self.theme["surface_cp"]
        k = cp_bins(cp, self.lo)
        table = [ramp(stops, (b + 0.5) / BINS) for b in range(BINS)]
        return [table[b] for b in k]

    def show_marker(self, z):
        """A ring at the point z of a surface (hover in the panel's graph); None hides it."""
        if z is None or not np.isfinite(z):
            self.marker.setVisible(False)
            return
        self.marker.setData([z.real], [z.imag])
        self.marker.setVisible(True)
