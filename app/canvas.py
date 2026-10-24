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
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from physics.streamlines import trace_streamlines

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

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.bar = CanvasBar(self)
        lay.addWidget(self.bar)

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
        self._arrows, self._markers = [], []

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(LAYOUT["recompute_delay_ms"])
        self._timer.timeout.connect(self.recompute)

        self.plot.scene().sigMouseMoved.connect(self._mouse_moved)
        self.vb.sigRangeChanged.connect(self._range_changed)
        self.bar.btn_fit.clicked.connect(self.fit_view)

        rng = LAYOUT["plot_initial_range"]
        self.plot.setRange(xRange=rng["x"], yRange=rng["y"], padding=0)
        self.apply_theme(theme)

    # ------------------------------------------------------------------ public API
    def set_elements(self, elements: list):
        self.elements = elements
        self.recompute()

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
        pts = [p for e in self.elements if e.enabled for p in e.singular_points()]
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
            a = pg.ArrowItem(pos=(x, y), angle=180.0 - np.degrees(ang), headLen=size + 3, headWidth=size,
                             tailLen=0, brush=pg.mkBrush(color), pen=pg.mkPen(color))
            a.setZValue(2)
            self.plot.addItem(a)
            self._arrows.append(a)

        self._draw_markers()
        self.computed.emit(len(result.lines), ms)

    def _draw_markers(self):
        for it in self._markers:
            self.plot.removeItem(it)
        self._markers.clear()
        t = self.theme
        for e in self.elements:
            if not e.enabled:
                continue
            pts = e.singular_points()
            if not pts:
                continue
            style = MARKERS.get(e.TYPE, MARKERS["default"])
            key = "el_sink" if getattr(e, "is_sink", False) else f"el_{e.TYPE}"
            color = t.get(key, t["plot_axis"])
            if style["filled"]:
                brush, pen = pg.mkBrush(color), pg.mkPen(t["plot_bg"], width=1.5)
            else:
                brush, pen = pg.mkBrush(None), pg.mkPen(color, width=2)
            item = pg.ScatterPlotItem([p.real for p in pts], [p.imag for p in pts], size=style["size"],
                                      symbol=style["symbol"], brush=brush, pen=pen)
            item.setZValue(3)
            self.plot.addItem(item)
            self._markers.append(item)

    # ------------------------------------------------------------------ events
    def _range_changed(self, *_):
        (x0, x1), (y0, y1) = self.vb.viewRange()
        self.view_changed.emit((x0, x1), (y0, y1))
        self.schedule()

    def _mouse_moved(self, pos):
        if not self.vb.sceneBoundingRect().contains(pos):
            self.probe.emit(None)
            return
        pt = self.vb.mapSceneToView(pos)
        self.probe.emit((pt.x(), pt.y()))
