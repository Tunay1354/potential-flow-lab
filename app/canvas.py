"""
canvas.py — the central plot area and the small bar above it.

The plot asks the physics engine for streamlines of the CURRENT view. After every
zoom / pan they are extended, so the streamlines always fill whatever region is visible.

Streamlines come from a StreamlineCache (physics/streamlines.py): lines already computed never move,
a margin around the view is computed in advance (panning shows lines that are already there), and
zooming changes the line spacing in steps of 2 while keeping the coarser lines in place.

The computation runs in a background thread, so the window never freezes. While it runs, new
view requests are collected and only the newest is computed next. A change of the scene or the
density starts a new cache and cancels the running computation (generation number); results of
old generations are thrown away. `recompute()` is the synchronous version (tests and scripts).

Layers planned for later phases (each will become a separate class in render/layers/):
animated particles, dividing streamline / body, equipotential lines, |V| and Cp contours, walls.
"""
import time

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QObject, QPointF, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGraphicsPathItem, QHBoxLayout, QLabel, QToolButton,
                               QVBoxLayout, QWidget)

from physics.streamlines import FADE_LEVELS, Cancelled, StreamlineCache, fade_piece_lists

from .arrows_item import ArrowsItem
from .chrome import TitleBlock, button_font, font
from .geometry import fluid_polygon, ray_in_rect, rect_polygon, sector_shading, visible_wall_segment
from .icons import make_tool_icon
from .theme import FONT, LAYOUT, MARKERS


def _stagnation_symbol() -> QPainterPath:
    """Marker of a stagnation point: a ring with a cross in it (⊗), unit size, centered."""
    path = QPainterPath()
    path.addEllipse(-0.5, -0.5, 1.0, 1.0)
    a = 0.5 / np.sqrt(2.0)
    path.moveTo(-a, -a)
    path.lineTo(a, a)
    path.moveTo(-a, a)
    path.lineTo(a, -a)
    return path


class _ResultSignal(QObject):
    """Carries background results to the GUI thread (queued connection)."""
    done = Signal(int, object, float)        # generation, StreamlineSet / None / exception, time in ms
    partial = Signal(int, object)            # generation, StreamlineSet of the visible part (more follows)


class _Job(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.setAutoDelete(True)

    def run(self):
        self.fn()


class CanvasBar(QWidget):
    """Bar above the plot: Static/Animated, Select/Pan, Fit view, Export."""
    message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CanvasBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(46)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)

        self.btn_static = self._tool("Static", "Streamlines with direction arrows", checkable=True)
        self.btn_anim = self._tool("Animated", "Particles moving with the flow", checkable=True)
        self.btn_static.setChecked(True)
        mode = QButtonGroup(self)
        mode.setExclusive(True)
        mode.addButton(self.btn_static)
        mode.addButton(self.btn_anim)
        pair = QHBoxLayout()                      # the two mode buttons touch each other
        pair.setSpacing(0)
        pair.addWidget(self.btn_static)
        pair.addWidget(self.btn_anim)
        lay.addLayout(pair)

        lay.addWidget(self._separator())
        self.btn_select = self._tool("Select", "Click an element to select, drag to move it",
                                     checkable=True, icon="select")
        self.btn_pan = self._tool("Pan", "Drag to pan, scroll to zoom", checkable=True, icon="pan")
        self.btn_select.setChecked(True)
        tools = QButtonGroup(self)
        tools.setExclusive(True)
        tools.addButton(self.btn_select)
        tools.addButton(self.btn_pan)
        lay.addWidget(self.btn_select)
        lay.addWidget(self.btn_pan)
        self.btn_fit = self._tool("Fit", "Fit plot limits to the elements   [F]", icon="fit")
        lay.addWidget(self.btn_fit)

        lay.addStretch(1)
        self.btn_export = self._tool("Export", "Save the current plot as PNG / PDF / SVG", icon="export")
        self.btn_export.setObjectName("Export")
        lay.addWidget(self.btn_export)

        for b in (self.btn_anim, self.btn_select, self.btn_pan, self.btn_export):
            b.clicked.connect(lambda _=False, b=b: self.message.emit(
                f"Prototype: “{b.text()}” is not connected yet."))

    def _tool(self, text, tip, checkable=False, icon=None):
        b = QToolButton(self)
        b.setText(text)
        b.setToolTip(tip)
        b.setCheckable(checkable)
        b.setCursor(Qt.PointingHandCursor)
        b.setFont(button_font())
        b.setFixedHeight(30)
        if icon:
            b.setProperty("tool_icon", icon)
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setIconSize(QSize(15, 15))
        return b

    def apply_theme(self, theme: dict):
        """Icons in the text color of each button (rust for Export, paper on a checked button)."""
        for b in self.findChildren(QToolButton):
            name = b.property("tool_icon")
            if name:
                col = theme["accent"] if b is self.btn_export else theme["text"]
                icon = make_tool_icon(name, col)
                icon.addPixmap(make_tool_icon(name, theme["toggle_on_text"]).pixmap(32, 32),
                               QIcon.Normal, QIcon.On)
                b.setIcon(icon)

    @staticmethod
    def _separator():
        s = QFrame()
        s.setFrameShape(QFrame.VLine)
        s.setFixedWidth(14)
        s.setStyleSheet("color: transparent;")
        return s


class PlotCanvas(QWidget):
    """Bar + pyqtgraph plot showing the streamlines of `elements`."""
    probe = Signal(object)              # (x, y) in data coordinates, or None
    element_clicked = Signal(int)       # index of the clicked element, −1 = empty place (deselect)
    element_double_clicked = Signal(int)
    stagnation_clicked = Signal(int)    # index of the clicked stagnation point
    view_changed = Signal(tuple, tuple)  # (xmin, xmax), (ymin, ymax)
    computed = Signal(int, float)       # number of streamlines, computation time in ms

    def __init__(self, theme: dict, elements: list, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.elements = elements
        # streamline settings (changed from the Plot settings panel)
        self.density = 1.0
        self.arrow_density = 1.0
        self.show_arrows = True
        self.line_width = LAYOUT["streamline_width"]
        self.selected = -1                       # index of the selected element (highlighted)

        # the plot card: a strong ink frame (painted in paintEvent) around bar, plot and title block
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
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
        self.title_block = TitleBlock(self)          # SCENE | ELEMENTS | VIEW | FILE (filled by the window)
        lay.addWidget(self.title_block)
        self.vb = self.plot.getPlotItem().getViewBox()

        # background grid: one GridItem (the axis-based grid of pyqtgraph is ~15× slower to draw)
        self._grid = pg.GridItem(textPen=None)
        self._grid.setTickSpacing(x=[None, None], y=[None, None])     # major + minor lines (as before)
        self._grid.setZValue(-10)
        self.plot.addItem(self._grid)

        # streamlines: one curve item per opacity level (index 0 = full opacity, then the
        # steps of the fading line ends); lines are separated by NaN inside each item
        self._line_items = []
        for _ in range(FADE_LEVELS + 1):
            item = pg.PlotCurveItem(connect="finite")
            item.setSegmentedLineMode("on")      # drawn as separate segments: ~7× faster with antialiasing
            item.setZValue(1)
            self.plot.addItem(item)
            self._line_items.append(item)
        self._lines = self._line_items[0]
        self._arrow_item = ArrowsItem(LAYOUT["arrow_size_px"])     # all direction arrows, one item
        self._arrow_item.setZValue(2)
        self.plot.addItem(self._arrow_item)
        # dividing streamlines (through stagnation points) and the stagnation points themselves
        self._dividing_item = pg.PlotCurveItem(connect="finite")
        self._dividing_item.setSegmentedLineMode("on")
        self._dividing_item.setZValue(1.6)
        self.plot.addItem(self._dividing_item)
        style = MARKERS["stagnation"]
        self._stag_symbol = _stagnation_symbol()
        self._stag_item = pg.ScatterPlotItem(symbol=self._stag_symbol, size=style["size"])
        self._stag_item.setZValue(3.5)
        self.plot.addItem(self._stag_item)
        self._stag_glow = []                     # glow of the selected stagnation point
        self._stag_label = pg.TextItem(anchor=(0.0, 1.0))
        self._stag_label.setZValue(6)
        self._stag_label.setVisible(False)
        self.plot.addItem(self._stag_label)
        self.stagnation_points = []
        self._dividing_lines, self._dividing_owner = [], []
        self.selected_stagnation = None          # index of the selected stagnation point (or None)
        # "dividing": ALL dividing streamlines; those of a selected stagnation point are always shown
        self.layers = {"streamlines": True, "dividing": False, "stagnation": True, "markers": True, "walls": True}
        self._markers, self._walls = [], []

        # background computation: one worker thread; requests during a computation are collected
        self.background = True
        self._generation = 0
        self._cache = None                       # StreamlineCache of the current scene and density
        self._busy = False                       # a job is running
        self._pending = False                    # a newer view was requested meanwhile
        self._force = True                       # next result must be drawn even if the lines are the same
        self._drawn_domain = None                # region filled by the drawn lines (x0, x1, y0, y1)
        self._pieces = None                      # per opacity level: (pieces, bounding boxes) of the result
        self._arrows_all = np.zeros((0, 3))
        self._cull_rect = None                   # lines / arrows handed to the plot: those meeting this rect
        self._drawn_level = None
        self._overlay_rect = None                # region the walls were drawn for
        self._first_job = True                   # the very first job may compile the kernel (kernel.py)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._results = _ResultSignal(self)
        self._results.done.connect(self._on_result)
        self._results.partial.connect(self._on_partial)

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
        self._new_cache()
        self._draw_overlays()                # symbols and walls at once, streamlines when ready
        self.request()

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
        self._draw_markers()
        self._draw_walls_around_view()

    def _draw_walls_around_view(self):
        """Walls are drawn for a region 3× the view, so panning does not need a redraw at once;
        the hatch spacing follows the view size."""
        (x0, x1), (y0, y1) = self.vb.viewRange()
        W, H = x1 - x0, y1 - y0
        self._overlay_rect = (x0 - W, x1 + W, y0 - H, y1 + H, W)
        self._hatch_spacing = abs(complex(W, H)) / LAYOUT["wall_hatch_count"]
        self._draw_walls((x0 - W, x1 + W), (y0 - H, y1 + H))
        self._apply_layers()

    def _walls_need_redraw(self) -> bool:
        if self._overlay_rect is None:
            return True
        (x0, x1), (y0, y1) = self.vb.viewRange()
        a0, a1, b0, b1, w = self._overlay_rect
        return not (a0 <= x0 and x1 <= a1 and b0 <= y0 and y1 <= b1) or not 0.7 < (x1 - x0) / w < 1.4

    def set_density(self, density: float):
        self.density = density
        self._new_cache()
        self.request()

    def set_arrows(self, show: bool, density: float | None = None):
        self.show_arrows = show
        if density is not None:
            self.arrow_density = density
        self._force = True
        self.request()

    def set_layer(self, key: str, on: bool):
        """Show / hide a layer: streamlines, dividing (all dividing streamlines), stagnation, markers,
        walls."""
        if key not in self.layers:
            return
        self.layers[key] = on
        if key == "stagnation" and not on:
            self.selected_stagnation = None
        self._draw_stagnation()

    def _apply_layers(self):
        on = self.layers
        for item in self._line_items:
            item.setVisible(on["streamlines"])
        self._arrow_item.setVisible(on["streamlines"])
        self._stag_item.setVisible(on["stagnation"])
        for item in self._stag_glow:
            item.setVisible(on["stagnation"])
        self._stag_label.setVisible(on["stagnation"] and self.selected_stagnation is not None)
        for item in self._markers:
            item.setVisible(on["markers"])
        for item in self._walls:
            item.setVisible(on["walls"])

    # ------------------------------------------------------------------ stagnation points
    def select_stagnation(self, index):
        """Select a stagnation point (index in stagnation_points) or none (None): the selected one
        glows, shows its dividing streamlines and a box with its coordinates."""
        if index is not None and not 0 <= index < len(self.stagnation_points):
            index = None
        self.selected_stagnation = index
        self._draw_stagnation()

    def _draw_stagnation(self):
        t = self.theme
        pts = self.stagnation_points
        self._stag_item.setData([p.x for p in pts], [p.y for p in pts])
        for item in self._stag_glow:
            self.plot.removeItem(item)
        self._stag_glow.clear()
        k = self.selected_stagnation
        if k is not None:
            p = pts[k]
            size = MARKERS["stagnation"]["size"]
            for extra, alpha in LAYOUT["selection_glow"]:
                c = QColor(t["stagnation"])
                c.setAlpha(alpha)
                g = pg.ScatterPlotItem([p.x], [p.y], size=size + extra, symbol="o",
                                       brush=pg.mkBrush(c), pen=pg.mkPen(None))
                g.setZValue(3.4)
                self.plot.addItem(g)
                self._stag_glow.append(g)
            x, y = round(p.x, 4) + 0.0, round(p.y, 4) + 0.0
            where = {"flow": "in the flow", "wall": "on the wall", "vertex": "corner vertex",
                     "body": "on the body surface"}[p.kind]
            self._stag_label.setHtml(
                f'<div style="color:{t["text"]}; font-family:{self._mono_css}; font-size:9pt; padding:2px 4px;">'
                f'<b>Stagnation point</b> <span style="color:{t["text_muted"]}">({where})</span><br>'
                f'x = {x:.4f}<br>y = {y:.4f}</div>')
            self._stag_label.fill = pg.mkBrush(t["panel_bg"])
            self._stag_label.border = pg.mkPen(t["border"])
            self._place_stag_label()
        # dividing streamlines: all of them (layer) or only those of the selected point
        lines = [ln for ln, o in zip(self._dividing_lines, self._dividing_owner)
                 if self.layers["dividing"] or o == k]
        if lines:
            gap = np.array([[np.nan, np.nan]])
            xy = np.vstack([x for ln in lines for x in (ln, gap)])
            self._dividing_item.setData(xy[:, 0], xy[:, 1])
        else:
            self._dividing_item.setData([], [])
        self._apply_layers()

    def _place_stag_label(self):
        """The coordinate box sits a few pixels up-right of the selected point (at any zoom)."""
        k = self.selected_stagnation
        if k is None:
            return
        p = self.stagnation_points[k]
        px, py = self.vb.viewPixelSize()
        off = LAYOUT["stagnation_label_offset_px"]
        # above the point, on the side away from the nearest element symbol (not over the body)
        marks = [m for e in self.elements if e.enabled for m in e.marker_points()]
        left = bool(marks) and min(marks, key=lambda m: abs(m - p.z)).real > p.x
        self._stag_label.setAnchor((1.0, 1.0) if left else (0.0, 1.0))
        self._stag_label.setPos(p.x + (-off if left else off) * px, p.y + off * py)

    def _pick_stagnation(self, scene_pos):
        """[(distance in pixels, index)] of the stagnation points under a scene position."""
        from PySide6.QtCore import QPointF
        if not self.layers["stagnation"]:
            return []
        click = complex(scene_pos.x(), scene_pos.y())
        out = []
        for k, p in enumerate(self.stagnation_points):
            q = self.vb.mapViewToScene(QPointF(p.x, p.y))
            d = abs(complex(q.x(), q.y()) - click)
            if d <= LAYOUT["pick_radius_px"]:
                out.append((d, k))
        return sorted(out)

    def stagnation_near(self, x: float, y: float):
        """The stagnation point within the pick radius (screen pixels) of (x, y), or None."""
        if not self.layers["stagnation"] or not self.stagnation_points:
            return None
        px, py = self.vb.viewPixelSize()
        r = LAYOUT["pick_radius_px"]
        best = min(self.stagnation_points, key=lambda p: ((p.x - x) / px) ** 2 + ((p.y - y) / py) ** 2)
        return best if ((best.x - x) / px) ** 2 + ((best.y - y) / py) ** 2 <= r * r else None

    def set_line_width(self, width: float):
        self.line_width = width
        self._set_line_pens()

    def set_view(self, xr, yr):
        self.plot.setRange(xRange=xr, yRange=yr, padding=0)

    def schedule(self):
        """The view changed: fill it with streamlines (at once; requests are collected while busy)."""
        self.request()

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
        self.update()                                # frame color
        self.bar.apply_theme(t)
        self.plot.setBackground(t["plot_bg"])
        pi = self.plot.getPlotItem()
        tick_font = font("mono", FONT["plot_label_size_pt"] - 1)
        self._mono_css = "'" + tick_font.family() + "'"      # for the HTML of the stagnation box
        for name in ("left", "bottom"):
            ax = pi.getAxis(name)
            ax.setPen(pg.mkPen(t["plot_axis"]))
            ax.setTextPen(pg.mkPen(t["plot_axis"]))
            ax.setTickFont(tick_font)
        label_style = {"color": t["plot_axis"], "font-size": f"{FONT['plot_label_size_pt']}pt",
                       "font-family": tick_font.family()}
        pi.setLabel("bottom", "x", **label_style)
        pi.setLabel("left", "y", **label_style)
        grid_color = QColor(t["plot_axis"])
        grid_color.setAlphaF(0.22)
        self._grid.setPen(pg.mkPen(grid_color, width=1))
        self._set_line_pens()
        self._dividing_item.setPen(pg.mkPen(t["dividing_streamline"], width=LAYOUT["dividing_streamline_width"]))
        self._stag_item.setPen(pg.mkPen(t["stagnation"], width=2))
        self._stag_item.setBrush(pg.mkBrush(t["plot_bg"]))
        if hasattr(self, "_stag_glow"):
            self._draw_stagnation()
        self._force = True
        self.request()

    def paintEvent(self, _event):
        """Frame of the plot card (2 px ink line)."""
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self.theme["plot_bg"]))
        p.setPen(QPen(QColor(self.theme["ink"]), 2))
        p.drawRect(self.rect().adjusted(1, 1, -1, -1))
        p.end()

    def _set_line_pens(self):
        n = len(self._line_items)
        for k, item in enumerate(self._line_items):
            color = QColor(self.theme["streamline"])
            color.setAlphaF(color.alphaF() * (n - k) / n)
            item.setPen(pg.mkPen(color, width=self.line_width))

    def _new_cache(self):
        """Scene or density changed: start a new cache and cancel the running computation."""
        self._generation += 1
        self._cache = StreamlineCache(tuple(self.elements), self.density)
        self._force = True

    def _view(self):
        (x0, x1), (y0, y1) = self.vb.viewRange()
        return (float(x0), float(x1)), (float(y0), float(y1))

    def covers_view(self) -> bool:
        """True if the drawn streamlines fill the visible region at the right spacing level."""
        if self._drawn_domain is None or self._cache is None:
            return False
        (x0, x1), (y0, y1) = self._view()
        a0, a1, b0, b1 = self._drawn_domain
        inside = a0 <= x0 and x1 <= a1 and b0 <= y0 and y1 <= b1
        return inside and self._cache._choose_level(self._view(), self._drawn_level) == self._drawn_level

    def request(self):
        """Bring the streamlines up to date: in the background thread (normal use) or synchronously."""
        if self._cache is None:
            self._new_cache()
        if not self.background:
            self.recompute()
            return
        if self._busy:
            self._pending = True                       # computed when the running job is finished
            return
        self._start_job()

    def _start_job(self):
        if self._first_job:
            self._first_job = False
            QTimer.singleShot(2500, self._first_job_slow)    # cached engine + first picture: < 1 s
        self._busy, self._pending = True, False
        gen, cache, view = self._generation, self._cache, self._view()
        arrows = self.arrow_density if self.show_arrows else 0.0
        force, self._force = self._force, False

        def cancelled():
            return gen != self._generation

        def work():
            t0 = time.perf_counter()
            try:
                result = cache.update(view, arrows, cancelled=cancelled, force=force,
                                      progress=lambda r: self._results.partial.emit(gen, (r, cache.level)))
                result = (result, cache.level)
            except Cancelled:
                result = None
            except Exception as exc:                     # report bugs in the GUI thread
                result = exc
            self._results.done.emit(gen, result, (time.perf_counter() - t0) * 1000.0)

        self._pool.start(_Job(work))

    def _first_job_slow(self):
        if self._busy and self._drawn_domain is None:
            self.bar.message.emit("Preparing the fast streamline engine (only after installing / updating)…")

    def _on_partial(self, gen, payload):
        if gen == self._generation:
            self._draw_result(*payload, None)

    def _on_result(self, gen, payload, ms):
        self._busy = False
        current = gen == self._generation
        if current and isinstance(payload, tuple) and payload[0] is not None:
            self._draw_result(*payload, ms)
        if self._pending or not current:
            self._start_job()                            # newer view or newer scene
        if isinstance(payload, BaseException):
            raise payload

    def recompute(self):
        """Synchronous computation (cancels a running background one)."""
        if self._cache is None:
            self._new_cache()
        self._generation += 1                            # results of running jobs are not drawn
        self._pool.waitForDone(10000)
        self._busy = self._pending = False
        self._cache = StreamlineCache(tuple(self.elements), self.density)
        arrows = self.arrow_density if self.show_arrows else 0.0
        t0 = time.perf_counter()
        result = self._cache.update(self._view(), arrows, force=True)
        self._force = False
        self._draw_result(result, self._cache.level, (time.perf_counter() - t0) * 1000.0)

    def wait_idle(self, msecs: int = 10000) -> bool:
        """Wait until the background thread is idle (results still arrive via the event loop)."""
        return self._pool.waitForDone(msecs)

    def shutdown(self):
        """Cancel and wait for the background computation (call before the window closes)."""
        self._generation += 1
        self._pool.waitForDone(10000)

    def _draw_result(self, result, level, ms):
        """Draw a StreamlineSet. ms = None for a partial result (the visible part; more follows)."""
        self._drawn_domain, self._drawn_level = result.domain, level
        self._pieces = []
        for parts in fade_piece_lists(result.lines, result.tapers, result.separation):
            boxes = np.array([(p[:, 0].min(), p[:, 0].max(), p[:, 1].min(), p[:, 1].max()) for p in parts]) \
                if parts else np.zeros((0, 4))
            self._pieces.append((parts, boxes))
        self._arrows_all = np.asarray(result.arrows, dtype=float).reshape(-1, 3)
        self._cull()

        self._arrow_item.setColor(self.theme["streamline"])
        old = (self.stagnation_points[self.selected_stagnation]
               if self.selected_stagnation is not None else None)
        self.stagnation_points = list(result.stagnation)
        self._dividing_lines = list(result.dividing)
        self._dividing_owner = list(result.dividing_owner)
        self.selected_stagnation = None                 # keep the selection if the point is still there
        if old is not None:
            for k, p in enumerate(self.stagnation_points):
                if abs(p.z - old.z) <= 1e-9 * (1.0 + abs(old.z)):
                    self.selected_stagnation = k
        self._draw_stagnation()

        if self._walls_need_redraw():
            self._draw_walls_around_view()
        if ms is not None:
            self.computed.emit(self._lines_in_view(result), ms)

    def _cull(self):
        """Hand to the plot only the line pieces and arrows near the view (the computed region is
        about 4× the view; drawing everything would cost 4× the time). Redone when the view leaves
        the rectangle or the zoom changes."""
        if self._pieces is None:
            return
        (x0, x1), (y0, y1) = self._view()
        W, H = x1 - x0, y1 - y0
        m = 0.3
        r = (x0 - m * W, x1 + m * W, y0 - m * H, y1 + m * H)
        self._cull_rect = (*r, W)
        gap = np.array([[np.nan, np.nan]])
        for item, (parts, boxes) in zip(self._line_items, self._pieces):
            if boxes.size:
                keep = np.nonzero((boxes[:, 1] >= r[0]) & (boxes[:, 0] <= r[1]) &
                                  (boxes[:, 3] >= r[2]) & (boxes[:, 2] <= r[3]))[0]
            else:
                keep = []
            if len(keep):
                xy = np.vstack([x for i in keep for x in (parts[i], gap)])
                item.setData(xy[:, 0], xy[:, 1])
            else:
                item.setData([], [])
        a = self._arrows_all
        inside = (a[:, 0] >= r[0]) & (a[:, 0] <= r[1]) & (a[:, 1] >= r[2]) & (a[:, 1] <= r[3])
        self._arrow_item.setData(a[inside])

    def _needs_cull(self) -> bool:
        if self._cull_rect is None:
            return self._pieces is not None
        (x0, x1), (y0, y1) = self._view()
        a0, a1, b0, b1, w = self._cull_rect
        return not (a0 <= x0 and x1 <= a1 and b0 <= y0 and y1 <= b1) or not 0.8 < (x1 - x0) / w < 1.25

    def _lines_in_view(self, result) -> int:
        (x0, x1), (y0, y1) = self._view()
        n = 0
        for ln in result.lines:
            if np.any((ln[:, 0] > x0) & (ln[:, 0] < x1) & (ln[:, 1] > y0) & (ln[:, 1] < y1)):
                n += 1
        return n

    def _draw_markers(self):
        self._draw_element_markers()
        self._apply_layers()

    def _draw_element_markers(self):
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
        """Symmetry walls and the sides of a sector flow inside the rectangle xr × yr.
        Solid region shaded once; each wall drawn only where it borders the fluid (corners look like
        an L or a wedge); hatch marks on the solid side. A plate (β = 360°) has fluid on both sides."""
        for it in self._walls:
            self.plot.removeItem(it)
        self._walls.clear()
        walls = [e for e in self.elements if e.enabled and e.IS_BOUNDARY]
        sectors = [e for e in self.elements if e.enabled and e.TYPE == "sector"]
        if not walls and not sectors:
            return

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
        if self._walls_need_redraw():
            self._draw_walls_around_view()
        self._place_stag_label()
        if self._needs_cull():
            self._cull()
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
        inside = self.vb.sceneBoundingRect().contains(ev.scenePos())
        elements = self.pick(ev.scenePos()) if inside else []
        stags = self._pick_stagnation(ev.scenePos()) if inside else []
        if ev.double():
            if elements:
                self.element_double_clicked.emit(elements[0])
            return
        # everything under the mouse, nearest first: ("e", element index) or ("s", stagnation index)
        hits = [("s", k) for _, k in stags] + [("e", i) for i in elements]
        if not hits:
            self.element_clicked.emit(-1)
            return
        current = ("e", self.selected) if self.selected >= 0 else ("s", self.selected_stagnation)
        # clicking again on overlapping symbols (e.g. doublet + vortex) selects the next one
        kind, k = hits[(hits.index(current) + 1) % len(hits)] if current in hits else hits[0]
        if kind == "e":
            self.element_clicked.emit(k)
        else:
            self.stagnation_clicked.emit(k)

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
