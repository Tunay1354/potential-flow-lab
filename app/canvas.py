"""
canvas.py — the central plot area and the small bar above it.

The plot asks the physics engine for streamlines of the CURRENT view. After every
zoom / pan (and a short delay, LAYOUT["recompute_delay_ms"]) they are recomputed,
so the streamlines always fill whatever region is visible.

Layers planned for later phases (each will become a separate class in render/layers/):
animated particles, dividing streamline / body, equipotential lines, |V| and Cp contours, walls.
"""
import time

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGraphicsPathItem, QHBoxLayout, QLabel, QToolButton,
                               QVBoxLayout, QWidget)

from physics.streamlines import trace_streamlines

from .geometry import fluid_polygon, ray_in_rect, rect_polygon, sector_shading, visible_wall_segment
from .theme import FONT, LAYOUT, MARKERS


class CanvasBar(QWidget):
    """Bar above the plot: Static/Animated, Select/Pan, Fit view, Export."""
    message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CanvasBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(6)

        title = QLabel("Total-flow streamlines")
        title.setObjectName("CanvasTitle")
        lay.addWidget(title)
        lay.addSpacing(14)

        self.btn_static = self._tool("Static", "Streamlines with direction arrows", checkable=True)
        self.btn_anim = self._tool("Animated", "Particles moving with the flow", checkable=True)
        self.btn_static.setChecked(True)
        mode = QButtonGroup(self)
        mode.setExclusive(True)
        mode.addButton(self.btn_static)
        mode.addButton(self.btn_anim)
        lay.addWidget(self.btn_static)
        lay.addWidget(self.btn_anim)

        lay.addWidget(self._separator())
        self.btn_select = self._tool("Select / Drag", "Click an element to select, drag to move it",
                                     checkable=True)
        self.btn_pan = self._tool("Pan / Zoom", "Drag to pan, scroll to zoom", checkable=True)
        self.btn_select.setChecked(True)
        tools = QButtonGroup(self)
        tools.setExclusive(True)
        tools.addButton(self.btn_select)
        tools.addButton(self.btn_pan)
        lay.addWidget(self.btn_select)
        lay.addWidget(self.btn_pan)

        lay.addWidget(self._separator())
        self.btn_fit = self._tool("Fit view", "Fit plot limits to the elements")
        lay.addWidget(self.btn_fit)

        lay.addStretch(1)
        self.btn_export = self._tool("Export figure…", "Save the current plot as PNG / PDF / SVG")
        lay.addWidget(self.btn_export)

        for b in (self.btn_anim, self.btn_select, self.btn_pan, self.btn_export):
            b.clicked.connect(lambda _=False, b=b: self.message.emit(
                f"Prototype: “{b.text()}” is not connected yet."))

    def _tool(self, text, tip, checkable=False):
        b = QToolButton(self)
        b.setText(text)
        b.setToolTip(tip)
        b.setCheckable(checkable)
        b.setCursor(Qt.PointingHandCursor)
        return b

    @staticmethod
    def _separator():
        s = QFrame()
        s.setFrameShape(QFrame.VLine)
        s.setFixedWidth(10)
        s.setStyleSheet("color: transparent;")
        return s


class PlotCanvas(QWidget):
    """Bar + pyqtgraph plot showing the streamlines of `elements`."""
    probe = Signal(object)              # (x, y) in data coordinates, or None
    element_clicked = Signal(int)       # index of the clicked element, −1 = empty place (deselect)
    element_double_clicked = Signal(int)
    view_changed = Signal(tuple, tuple)  # (xmin, xmax), (ymin, ymax)
    computed = Signal(int, float)       # number of streamlines, computation time in ms

    def __init__(self, theme: dict, elements: list, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.elements = elements
        # streamline settings (changed from the Plot settings panel)
        self.density = 1.0
        self.arrows_per_line = 1
        self.show_arrows = True
        self.line_width = LAYOUT["streamline_width"]
        self.selected = -1                       # index of the selected element (highlighted)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.bar = CanvasBar(self)
        lay.addWidget(self.bar)

        # red strip shown while the scene has errors (e.g. a wall condition that cannot hold)
        self.banner = QLabel("")
        self.banner.setObjectName("ErrorBanner")
        self.banner.setWordWrap(True)
        self.banner.setVisible(False)
        lay.addWidget(self.banner)

        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget()
        self.plot.setAspectLocked(True)          # circles must look like circles
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()
        lay.addWidget(self.plot, 1)
        self.vb = self.plot.getPlotItem().getViewBox()

        self._lines = pg.PlotCurveItem(connect="finite")
        self._lines.setZValue(1)
        self.plot.addItem(self._lines)
        self._arrows, self._markers, self._walls = [], [], []

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(LAYOUT["recompute_delay_ms"])
        self._timer.timeout.connect(self.recompute)

        self.plot.scene().sigMouseMoved.connect(self._mouse_moved)
        self.plot.scene().sigMouseClicked.connect(self._mouse_clicked)
        self.vb.sigRangeChanged.connect(self._range_changed)
        self.bar.btn_fit.clicked.connect(self.fit_view)

        rng = LAYOUT["plot_initial_range"]
        self.plot.setRange(xRange=rng["x"], yRange=rng["y"], padding=0)
        self.apply_theme(theme)

    # ------------------------------------------------------------------ public API
    def set_elements(self, elements: list):
        self.elements = elements
        self.recompute()

    def set_selected(self, index: int):
        """Highlight one element (no streamline recomputation needed)."""
        self.selected = index
        self._draw_overlays()

    def set_banner(self, text: str | None):
        self.banner.setText(text or "")
        self.banner.setVisible(bool(text))

    def _selected_element(self):
        if 0 <= self.selected < len(self.elements):
            return self.elements[self.selected]
        return None

    def _draw_overlays(self):
        (x0, x1), (y0, y1) = self.vb.viewRange()
        self._draw_markers()
        self._draw_walls((x0, x1), (y0, y1))

    def set_density(self, density: float):
        self.density = density
        self.schedule()

    def set_arrows(self, show: bool, per_line: int | None = None):
        self.show_arrows = show
        if per_line is not None:
            self.arrows_per_line = per_line
        self.schedule()

    def set_line_width(self, width: float):
        self.line_width = width
        self._lines.setPen(pg.mkPen(self.theme["streamline"], width=width))

    def set_view(self, xr, yr):
        self.plot.setRange(xRange=xr, yRange=yr, padding=0)

    def schedule(self):
        """Recompute after a short pause (avoids recomputing on every mouse event)."""
        self._timer.start()

    def fit_view(self):
        """Show all elements with some margin (default view if there is nothing to fit)."""
        pts = [p for e in self.elements if e.enabled for p in e.marker_points()]
        if not pts:
            rng = LAYOUT["plot_initial_range"]
            self.set_view(rng["x"], rng["y"])
            return
        xs, ys = [p.real for p in pts], [p.imag for p in pts]
        span = max(max(xs) - min(xs), max(ys) - min(ys))
        pad = max(2.5, 0.6 * span)
        self.set_view((min(xs) - pad, max(xs) + pad), (min(ys) - pad, max(ys) + pad))

    # ------------------------------------------------------------------ drawing
    def apply_theme(self, theme: dict):
        self.theme = t = theme
        self.plot.setBackground(t["plot_bg"])
        pi = self.plot.getPlotItem()
        font = QFont()
        font.setPointSize(FONT["plot_label_size_pt"])
        for name in ("left", "bottom"):
            ax = pi.getAxis(name)
            ax.setPen(pg.mkPen(t["plot_axis"]))
            ax.setTextPen(pg.mkPen(t["plot_axis"]))
            ax.setTickFont(font)
        label_style = {"color": t["plot_axis"], "font-size": f"{FONT['plot_label_size_pt']}pt"}
        pi.setLabel("bottom", "x", **label_style)
        pi.setLabel("left", "y", **label_style)
        pi.showGrid(x=True, y=True, alpha=0.18 if t["name"] == "light" else 0.14)
        self._lines.setPen(pg.mkPen(t["streamline"], width=self.line_width))
        self.recompute()

    def recompute(self):
        self._timer.stop()
        (x0, x1), (y0, y1) = self.vb.viewRange()
        t0 = time.perf_counter()
        result = trace_streamlines(self.elements, (x0, x1), (y0, y1), density=self.density,
                                   arrows_per_line=self.arrows_per_line if self.show_arrows else 0)
        ms = (time.perf_counter() - t0) * 1000.0

        # all lines in one curve item, separated by NaN (much faster than one item per line)
        if result.lines:
            parts = []
            for ln in result.lines:
                parts.append(ln)
                parts.append(np.array([[np.nan, np.nan]]))
            xy = np.vstack(parts)
            self._lines.setData(xy[:, 0], xy[:, 1])
        else:
            self._lines.setData([], [])

        for it in self._arrows:
            self.plot.removeItem(it)
        self._arrows.clear()
        color = self.theme["streamline"]
        size = LAYOUT["arrow_size_px"]
        for x, y, ang in result.arrows:
            # pyqtgraph: angle = 0 points to the LEFT, angles grow clockwise on screen
            a = pg.ArrowItem(pos=(x, y), angle=180.0 - np.degrees(ang), headLen=1.35 * size, headWidth=size,
                             tailLen=0, brush=pg.mkBrush(color), pen=pg.mkPen(color))
            a.setZValue(2)
            self.plot.addItem(a)
            self._arrows.append(a)

        self._draw_overlays()
        self.computed.emit(len(result.lines), ms)

    def _draw_markers(self):
        for it in self._markers:
            self.plot.removeItem(it)
        self._markers.clear()
        t = self.theme
        for e in self.elements:
            if not e.enabled:
                continue
            pts = e.marker_points()
            if not pts:
                continue
            style = MARKERS.get(e.TYPE, MARKERS["default"])
            key = "el_sink" if getattr(e, "is_sink", False) else f"el_{e.TYPE}"
            color = t.get(key, t["plot_axis"])
            if style["filled"]:
                brush, pen = pg.mkBrush(color), pg.mkPen(t["plot_bg"], width=1.5)
            else:
                brush, pen = pg.mkBrush(None), pg.mkPen(color, width=2)
            if e is self._selected_element():               # selected: soft glow in the element's own color
                for extra, alpha in LAYOUT["selection_glow"]:
                    glow_color = QColor(color)
                    glow_color.setAlpha(alpha)
                    glow = pg.ScatterPlotItem([p.real for p in pts], [p.imag for p in pts],
                                              size=style["size"] + extra, symbol="o",
                                              brush=pg.mkBrush(glow_color), pen=pg.mkPen(None))
                    glow.setZValue(2.9)
                    self.plot.addItem(glow)
                    self._markers.append(glow)
            item = pg.ScatterPlotItem([p.real for p in pts], [p.imag for p in pts], size=style["size"],
                                      symbol=style["symbol"], brush=brush, pen=pen)
            item.setZValue(3)
            self.plot.addItem(item)
            self._markers.append(item)

    def _draw_walls(self, xr, yr):
        """Symmetry walls and the sides of a sector flow.
        Solid region shaded once; each wall drawn only where it borders the fluid (corners look like
        an L or a wedge); hatch marks on the solid side. A plate (β = 360°) has fluid on both sides."""
        for it in self._walls:
            self.plot.removeItem(it)
        self._walls.clear()
        walls = [e for e in self.elements if e.enabled and e.IS_BOUNDARY]
        sectors = [e for e in self.elements if e.enabled and e.TYPE == "sector"]
        if not walls and not sectors:
            return
        self._hatch_spacing = abs(complex(xr[1] - xr[0], yr[1] - yr[0])) / LAYOUT["wall_hatch_count"]

        # 1) shading of the solid region
        if walls:
            self._add_shading("cut", fluid_polygon(walls, xr, yr), xr, yr, self.theme["el_wall"])
        for sec in sectors:
            mode, poly = sector_shading(sec, xr, yr)
            self._add_shading(mode, poly, xr, yr, self.theme["el_sector"])

        # 2) symmetry walls: the part that borders the fluid
        sel = self._selected_element()
        for w in walls:
            seg = visible_wall_segment(w, [o for o in walls if o is not w], xr, yr)
            if seg is not None:
                self._add_wall_line(seg, w.normal, self.theme["el_wall"], glow=w is sel)

        # 3) sector sides: two rays from the vertex (fluid normal points into the wedge)
        for sec in sectors:
            plate = sec.beta_deg >= 360.0 - 1e-9
            for ang, turn in ((sec.theta1, 1j), (sec.theta1 + sec.beta_deg, -1j)):
                d = complex(np.cos(np.radians(ang)), np.sin(np.radians(ang)))
                seg = ray_in_rect(sec.z0, d, xr, yr)
                if seg is not None:
                    self._add_wall_line(seg, turn * d, self.theme["el_sector"], hatch=not plate, glow=sec is sel)
                if plate:
                    break                                   # both sides of the plate are the same ray

    def _add_shading(self, mode, poly, xr, yr, color):
        if mode == "none":
            return
        path = QPainterPath()
        if mode == "cut":                                   # view minus the fluid polygon
            path.setFillRule(Qt.OddEvenFill)
            path.addPolygon(QPolygonF([QPointF(z.real, z.imag) for z in rect_polygon(xr, yr)]))
        if len(poly) >= 3:
            path.addPolygon(QPolygonF([QPointF(z.real, z.imag) for z in poly]))
        elif mode == "fill":
            return
        fill = QColor(color)
        fill.setAlpha(38 if self.theme["name"] == "light" else 55)
        shade = QGraphicsPathItem(path)
        shade.setBrush(QBrush(fill))
        shade.setPen(QPen(Qt.NoPen))
        shade.setZValue(0.5)
        self.plot.addItem(shade)
        self._walls.append(shade)

    def _add_wall_line(self, seg, fluid_normal, color, hatch=True, glow=False):
        """Thick line from seg[0] to seg[1]; hatch marks on the side opposite to `fluid_normal`.
        glow=True (selected): wide, semi-transparent lines of the same color underneath."""
        a, b = seg
        color = QColor(color)
        if glow:
            for extra, alpha in LAYOUT["selection_glow"]:
                gc = QColor(color)
                gc.setAlpha(alpha)
                g = pg.PlotCurveItem([a.real, b.real], [a.imag, b.imag],
                                     pen=pg.mkPen(gc, width=LAYOUT["wall_width"] + 0.6 * extra))
                g.setZValue(3.9)
                self.plot.addItem(g)
                self._walls.append(g)
        line = pg.PlotCurveItem([a.real, b.real], [a.imag, b.imag], pen=pg.mkPen(color, width=LAYOUT["wall_width"]))
        line.setZValue(4)
        self.plot.addItem(line)
        self._walls.append(line)
        length = abs(b - a)
        n = int(length / self._hatch_spacing)
        if not hatch or n < 1:
            return
        d = (b - a) / length
        left = 1 if (np.conj(d) * fluid_normal).imag > 0 else -1      # fluid on the left of d?
        tick = 0.6 * self._hatch_spacing * (-fluid_normal * np.exp(1j * np.pi / 4 * left))
        base = a + (np.arange(n) + 0.5) * self._hatch_spacing * d
        xs = np.column_stack([base.real, (base + tick).real, np.full(n, np.nan)]).ravel()
        ys = np.column_stack([base.imag, (base + tick).imag, np.full(n, np.nan)]).ravel()
        marks = pg.PlotCurveItem(xs, ys, connect="finite", pen=pg.mkPen(color, width=1.2))
        marks.setZValue(4)
        self.plot.addItem(marks)
        self._walls.append(marks)

    # ------------------------------------------------------------------ events
    def _range_changed(self, *_):
        (x0, x1), (y0, y1) = self.vb.viewRange()
        self.view_changed.emit((x0, x1), (y0, y1))
        self.schedule()

    # ------------------------------------------------------------------ picking (click to select)
    def pick(self, scene_pos) -> list[int]:
        """Indices of the elements under a scene (pixel) position, nearest first.
        Markers (source, vortex, doublet, sector vertex) and drawn lines (walls, sector sides) can be
        picked; the uniform flow has no symbol on the plot and is selected from the list."""
        from PySide6.QtCore import QPointF
        tol = LAYOUT["pick_radius_px"]
        (x0, x1), (y0, y1) = self.vb.viewRange()
        sx, sy = scene_pos.x(), scene_pos.y()

        def to_scene(z):
            q = self.vb.mapViewToScene(QPointF(z.real, z.imag))
            return complex(q.x(), q.y())

        click = complex(sx, sy)
        hits = []
        for i, e in enumerate(self.elements):
            if not e.enabled:
                continue
            best = None
            for p in e.marker_points():
                d = abs(to_scene(p) - click)
                best = d if best is None else min(best, d)
            for seg in self._pick_segments(e, (x0, x1), (y0, y1)):
                a, b = to_scene(seg[0]), to_scene(seg[1])
                d = _point_segment_distance(click, a, b) + 0.5      # markers win a tie with a line
                best = d if best is None else min(best, d)
            if best is not None and best <= tol:
                hits.append((best, i))
        return [i for _, i in sorted(hits)]

    def _pick_segments(self, e, xr, yr):
        """Visible straight pieces of an element (same as drawn): walls and the sides of a sector."""
        if e.IS_BOUNDARY:
            walls = [w for w in self.elements if w.enabled and w.IS_BOUNDARY]
            seg = visible_wall_segment(e, [o for o in walls if o is not e], xr, yr)
            return [seg] if seg else []
        if e.TYPE == "sector":
            out = []
            for ang in (e.theta1, e.theta1 + e.beta_deg):
                d = complex(np.cos(np.radians(ang)), np.sin(np.radians(ang)))
                seg = ray_in_rect(e.z0, d, xr, yr)
                if seg:
                    out.append(seg)
            return out
        return []

    def _mouse_clicked(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        hits = self.pick(ev.scenePos()) if self.vb.sceneBoundingRect().contains(ev.scenePos()) else []
        if ev.double():
            if hits:
                self.element_double_clicked.emit(hits[0])
            return
        if not hits:
            self.element_clicked.emit(-1)
            return
        # clicking again on overlapping symbols (e.g. doublet + vortex) selects the next one
        if self.selected in hits:
            self.element_clicked.emit(hits[(hits.index(self.selected) + 1) % len(hits)])
        else:
            self.element_clicked.emit(hits[0])

    def _mouse_moved(self, pos):
        if not self.vb.sceneBoundingRect().contains(pos):
            self.probe.emit(None)
            return
        pt = self.vb.mapSceneToView(pos)
        self.probe.emit((pt.x(), pt.y()))


def _point_segment_distance(p: complex, a: complex, b: complex) -> float:
    ab = b - a
    if abs(ab) == 0:
        return abs(p - a)
    t = max(0.0, min(1.0, ((p - a) * ab.conjugate()).real / abs(ab) ** 2))
    return abs(p - (a + t * ab))
