"""
canvas.py — the plot card: the bar above the plot, the pyqtgraph plot with its layers and the title
block below it.

What is drawn is split into layers (layer.py): streamlines, stagnation points with their dividing
streamlines, the field layers (φ, |V|, Cp) and the elements themselves. The canvas holds the shared
state (elements, plot settings, layer switches, selection) and passes every event on to all layers;
what the mouse does is in interaction.py.
"""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from physics.field import reference_speed

from ..chrome import TitleBlock, device_line_rect, font
from ..theme import FONT, LAYOUT
from .bar import CanvasBar
from .element_layer import ElementLayer
from .field_layer import KEYS as FIELD_KEYS
from .field_layer import FieldLayer
from .interaction import DRAG_OPACITY, MOUSE_MODES, PlotInteraction, PlotViewBox
from .settings import PlotSettings
from .stagnation_layer import StagnationLayer
from .streamline_layer import StreamlineLayer

# layer switches: key, label (Plot settings → Layers, View → Layers), shown at the start.
# "dividing": ALL dividing streamlines (those of a selected stagnation point are always shown)
LAYERS = (
    ("streamlines", "Streamlines", True),
    ("dividing", "All dividing streamlines", False),
    ("stagnation", "Stagnation points", True),
    ("equipotential", "Equipotential lines (φ)", False),
    ("speed", "Speed |V| (color bands)", False),
    ("cp", "Pressure coefficient Cp (color bands)", False),
    ("markers", "Element markers", True),
    ("walls", "Walls", True),
)


class PlotCanvas(QWidget):
    """Bar + pyqtgraph plot of `elements` + title block."""
    probe = Signal(object)              # (x, y) in data coordinates, or None
    element_clicked = Signal(int)       # index of the clicked element, −1 = empty place (deselect)
    element_double_clicked = Signal(int)
    stagnation_clicked = Signal(int)    # index of the clicked stagnation point
    view_changed = Signal(tuple, tuple)  # (xmin, xmax), (ymin, ymax)
    computed = Signal(int, float)       # number of streamlines in the view, computation time in ms
    element_moved = Signal(int, object)  # Move mode: element index, the moved copy (released)
    element_dropped = Signal(str, object)   # palette drag: element type, (x, y) or None (no position)
    mode_changed = Signal(str)          # mouse mode: "select", "move", "pan"
    cp_reference_requested = Signal()   # the "Set V_ref" note of the Cp legend was clicked
    message = Signal(str)               # a short note for the status bar

    def __init__(self, theme: dict, elements: list, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.elements = elements
        self.settings = PlotSettings()
        self.layers = {key: on for key, _label, on in LAYERS}
        self.selected = -1                       # index of the selected element (highlighted)
        self.last_result = None                  # the drawn StreamlineSet (File → Export data)

        # the plot card: a thin ink frame (painted in paintEvent) around bar, plot and title block
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)      # children never cover the frame (also at 125 % scaling)
        lay.setSpacing(0)
        self.bar = CanvasBar(self)
        lay.addWidget(self.bar)
        self.banner = QLabel("")                 # red strip while the scene has errors
        self.banner.setObjectName("ErrorBanner")
        self.banner.setWordWrap(True)
        self.banner.setVisible(False)
        lay.addWidget(self.banner)
        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget(viewBox=PlotViewBox())
        self.plot.setAspectLocked(True)          # circles must look like circles
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()
        lay.addWidget(self.plot, 1)
        self.title_block = TitleBlock(self)      # SCENE | ELEMENTS | VIEW | FILE (filled by the window)
        lay.addWidget(self.title_block)
        self.vb = self.plot.getPlotItem().getViewBox()
        # background grid: one GridItem (the axis-based grid of pyqtgraph is ~15× slower to draw)
        self._grid = pg.GridItem(textPen=None)
        self._grid.setTickSpacing(x=[None, None], y=[None, None])
        self._grid.setZValue(-10)
        self.plot.addItem(self._grid)

        # the layers (drawn in z order, see each class); every event goes to all of them
        self._layers = []
        self.streamlines = self.add_layer(StreamlineLayer(self.plot, self.vb))
        self.stagnation = self.add_layer(StagnationLayer(self.plot, self.vb))
        self.fields = self.add_layer(FieldLayer(self.plot, self.vb))
        self.fields.legend.clicked = self.cp_reference_requested.emit
        self.element_layer = self.add_layer(ElementLayer(self.plot, self.vb))
        self.interaction = PlotInteraction(self)

        self.bar.message.connect(self.message)
        self.bar.btn_fit.clicked.connect(self.fit_view)
        self.bar.mode_selected.connect(self.set_mode)
        rng = LAYOUT["plot_initial_range"]
        self.plot.setRange(xRange=rng["x"], yRange=rng["y"], padding=0)
        self.vb.sigRangeChanged.connect(self._range_changed)
        self.apply_theme(theme)

    def add_layer(self, layer):
        layer.canvas = self
        self._layers.append(layer)
        return layer

    # ------------------------------------------------------------------ state
    def view(self):
        """The visible region ((x0, x1), (y0, y1))."""
        (x0, x1), (y0, y1) = self.vb.viewRange()
        return (float(x0), float(x1)), (float(y0), float(y1))

    def shown_elements(self) -> list:
        """The elements as drawn: while an element is dragged, its moved copy replaces it."""
        moving = self.interaction.preview()
        if moving is None:
            return self.elements
        out = list(self.elements)
        out[moving[0]] = moving[1]
        return out

    def set_elements(self, elements: list):
        self.elements = elements
        for layer in self._layers:
            layer.scene_changed()

    def set_selected(self, index: int):
        """Highlight one element (no streamline recomputation needed)."""
        self.selected = index
        for layer in self._layers:
            layer.selection_changed()

    def set_banner(self, text: str | None):
        self.banner.setText(text or "")
        self.banner.setVisible(bool(text))

    def set_layer(self, key: str, on: bool):
        """Show / hide a layer (see LAYERS)."""
        if key not in self.layers:
            return
        self.layers[key] = on
        if key in FIELD_KEYS:
            self.fields.schedule(force=True, now=True)
        elif key == "stagnation" and not on:
            self.stagnation.select(None)
        else:
            self.stagnation.draw()                   # (the dividing lines depend on the switches too)

    def apply_visibility(self):
        for layer in self._layers:
            layer.visibility_changed()

    # ------------------------------------------------------------------ plot settings
    def apply_settings(self, settings: PlotSettings):
        """Settings of an opened scene (the scene itself follows, which computes everything)."""
        self.settings = settings
        self.streamlines.set_line_pens()

    def set_density(self, density: float):
        self.settings.density = density
        self.streamlines.restart()
        self.fields.schedule(force=True)            # φ line spacing follows the streamline spacing

    def set_arrows(self, show: bool, density: float | None = None):
        self.settings.show_arrows = show
        if density is not None:
            self.settings.arrow_density = density
        self.streamlines.redraw()

    def set_line_width(self, width: float):
        self.settings.line_width = width
        self.streamlines.set_line_pens()

    def set_field_quality(self, quality: int):
        self.settings.field_quality = int(quality)
        self.fields.schedule(force=True)

    def set_cp_reference(self, v_ref):
        """None = V∞ of the uniform flow(s); a number = the user's reference speed."""
        self.settings.cp_reference = v_ref or None
        self.fields.schedule(force=True)

    def cp_reference(self):
        return self.settings.cp_reference or reference_speed(self.elements)

    # ------------------------------------------------------------------ view
    def set_view(self, xr, yr):
        self.plot.setRange(xRange=xr, yRange=yr, padding=0)

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

    def _range_changed(self, *_):
        self.view_changed.emit(*self.view())
        for layer in self._layers:
            layer.view_changed()

    # ------------------------------------------------------------------ streamlines (computation)
    def recompute(self):
        """Compute the streamlines now, synchronously (tests and scripts)."""
        self.streamlines.recompute()

    def wait_idle(self, msecs: int = 10000) -> bool:
        """Wait until the background computation is idle (results still arrive via the event loop)."""
        return self.streamlines.wait_idle(msecs)

    def shutdown(self):
        """Stop background work (call before the window closes)."""
        for layer in self._layers:
            layer.shutdown()

    def streamlines_drawn(self, result, ms):
        """A streamline result was drawn (ms = None: a partial result, more follows)."""
        self.last_result = result
        self.stagnation.set_result(result)
        self.element_layer.view_changed()            # walls follow if the view moved meanwhile
        if ms is not None:
            self.computed.emit(self._lines_in_view(result), ms)

    def _lines_in_view(self, result) -> int:
        (x0, x1), (y0, y1) = self.view()
        return sum(1 for ln in result.lines
                   if np.any((ln[:, 0] > x0) & (ln[:, 0] < x1) & (ln[:, 1] > y0) & (ln[:, 1] < y1)))

    # ------------------------------------------------------------------ stagnation points
    @property
    def stagnation_points(self) -> list:
        return self.stagnation.points

    @property
    def selected_stagnation(self):
        return self.stagnation.selected

    def select_stagnation(self, index):
        """Select a stagnation point (index) or none (None): it glows, shows its dividing streamlines
        and a box with its coordinates."""
        self.stagnation.select(index)

    def stagnation_near(self, x: float, y: float):
        return self.stagnation.near(x, y)

    # ------------------------------------------------------------------ mouse
    @property
    def mode(self) -> str:
        return self.interaction.mode

    def set_mode(self, mode: str):
        """Mouse mode: select, move or pan (see interaction.py)."""
        if mode not in MOUSE_MODES:
            return
        changed = self.interaction.set_mode(mode)
        self.bar.set_mode(mode)
        if changed:
            self.mode_changed.emit(mode)

    def is_dragging(self) -> bool:
        return self.interaction.is_dragging()

    def cancel_drag(self) -> bool:
        return self.interaction.cancel_drag()

    def drag_started(self):
        for layer in self._layers:
            for item in layer.items() if layer.FADES_WHILE_DRAGGING else ():
                item.setOpacity(DRAG_OPACITY)
            layer.drag_started()
        self.apply_visibility()

    def drag_finished(self):
        for layer in self._layers:
            for item in layer.items() if layer.FADES_WHILE_DRAGGING else ():
                item.setOpacity(1.0)
            layer.drag_finished()
        self.apply_visibility()

    def pick(self, scene_pos) -> list[int]:
        """Indices of the elements under a scene (pixel) position, nearest first."""
        return self.element_layer.pick(scene_pos)

    # ------------------------------------------------------------------ appearance
    def apply_theme(self, theme: dict):
        self.theme = t = theme
        self.update()                                # frame color
        self.bar.apply_theme(t)
        self.plot.setBackground(t["plot_bg"])
        pi = self.plot.getPlotItem()
        tick_font = font("mono", FONT["plot_label_size_pt"] - 1)
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
        for layer in self._layers:
            layer.apply_theme(t)

    def paintEvent(self, _event):
        """Frame of the plot card: one thin ink line (cosmetic pen: the same width on every side,
        whatever the Windows display scaling is)."""
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self.theme["plot_bg"]))
        pen = QPen(QColor(self.theme["ink"]), 0)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.drawRect(device_line_rect(self))       # on the outermost screen pixels, all four sides
        p.end()
