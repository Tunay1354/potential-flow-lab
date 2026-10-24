"""
canvas.py — the central plot area and the small bar above it.

Layers planned for the real program (each will be a separate class in render/layers/):
streamlines, animated particles, dividing streamline, equipotential lines,
|V| contours, Cp contours, element markers, walls.
"""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGraphicsEllipseItem, QHBoxLayout, QLabel,
                               QToolButton, QVBoxLayout, QWidget)

from . import demo_flow
from .theme import FONT, LAYOUT


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
    """Bar + pyqtgraph plot. Shows a demo lifting-cylinder flow in the prototype."""
    probe = Signal(object)          # emits (x, y) in data coordinates or None

    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self.theme = theme
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

        self.plot.scene().sigMouseMoved.connect(self._mouse_moved)
        self.bar.btn_fit.clicked.connect(self.fit_view)

        self._items = []
        self.apply_theme(theme)

    # ------------------------------------------------------------------ drawing
    def apply_theme(self, theme: dict):
        self.theme = theme
        t = theme
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
        self.redraw()

    def redraw(self):
        for it in self._items:
            self.plot.removeItem(it)
        self._items.clear()
        t = self.theme
        rng = LAYOUT["plot_initial_range"]

        # streamlines + one arrow per line
        pen = pg.mkPen(t["streamline"], width=LAYOUT["streamline_width"])
        for k, (xs, ys) in enumerate(demo_flow.trace_streamlines(rng["x"], rng["y"])):
            curve = pg.PlotCurveItem(xs, ys, pen=pen)
            self._add(curve)
            self._add_arrow(xs, ys, t["streamline"], frac=0.3 if k % 2 else 0.7)

        # body (cylinder) — in the real program: shaded region inside the dividing streamline
        a = demo_flow.A
        body = QGraphicsEllipseItem(-a, -a, 2 * a, 2 * a)
        body.setBrush(QBrush(QColor(t["body_fill"])))
        p = QPen(QColor(t["body_edge"]))
        p.setWidthF(LAYOUT["dividing_streamline_width"])
        p.setCosmetic(True)
        body.setPen(p)
        self._add(body)

        # element markers (both elements sit at the origin in this demo)
        self._add(pg.ScatterPlotItem([0.0], [0.0], size=13, symbol="d",
                                     brush=pg.mkBrush(t["el_doublet"]), pen=pg.mkPen(t["plot_bg"], width=1.5)))
        self._add(pg.ScatterPlotItem([0.0], [0.0], size=24, symbol="o", brush=pg.mkBrush(None),
                                     pen=pg.mkPen(t["el_vortex"], width=2)))
        lbl = pg.TextItem("doublet + vortex", color=t["text_muted"], anchor=(0.5, -0.6))
        lbl.setPos(0, 0)
        self._add(lbl)

        self.plot.setRange(xRange=rng["x"], yRange=rng["y"], padding=0)

    def _add(self, item):
        self.plot.addItem(item)
        self._items.append(item)

    def _add_arrow(self, xs, ys, color, frac=0.5):
        """Arrow head at fraction `frac` of the visible part of the line (staggered between lines)."""
        rng = LAYOUT["plot_initial_range"]["x"]
        visible = np.where((xs > rng[0]) & (xs < rng[1]))[0]
        if len(visible) < 4:
            return
        i = visible[min(int(len(visible) * frac), len(visible) - 2)]
        dx, dy = xs[i + 1] - xs[i - 1], ys[i + 1] - ys[i - 1]
        ang = np.degrees(np.arctan2(dy, dx))
        # pyqtgraph: angle=0 points to the LEFT, angles grow clockwise on screen
        arrow = pg.ArrowItem(pos=(xs[i], ys[i]), angle=180.0 - ang, headLen=LAYOUT["arrow_size_px"] + 3,
                             headWidth=LAYOUT["arrow_size_px"], tailLen=0,
                             brush=pg.mkBrush(color), pen=pg.mkPen(color))
        self._add(arrow)

    def fit_view(self):
        rng = LAYOUT["plot_initial_range"]
        self.plot.setRange(xRange=rng["x"], yRange=rng["y"], padding=0)

    # ------------------------------------------------------------------ probe
    def _mouse_moved(self, pos):
        vb = self.plot.getPlotItem().getViewBox()
        if not vb.sceneBoundingRect().contains(pos):
            self.probe.emit(None)
            return
        pt = vb.mapSceneToView(pos)
        self.probe.emit((pt.x(), pt.y()))
