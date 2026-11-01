"""
layer.py — the common interface of everything drawn on the plot.

A PlotLayer owns some pyqtgraph items and reacts to what happens to the plot. PlotCanvas calls the
hooks below for every registered layer, so a new layer (e.g. animated particles) is one class with the
hooks it needs plus one `add_layer(...)` line in PlotCanvas.__init__.

    apply_theme(theme)    colors changed (also when a figure is exported in print colors)
    scene_changed()       the elements changed (also: a setting that changes the computation)
    selection_changed()   another element is selected
    view_changed()        zoom / pan
    visibility_changed()  a layer switch (canvas.layers) or the drag state changed
    drag_started()        an element is being dragged
    drag_moved()          ... and moved (canvas.shown_elements() has its new position)
    drag_finished()
    shutdown()            the window closes

Layers whose fades_while_dragging() is True have their items() drawn faintly while an element is
dragged (they show the old position until it is released).
"""
import pyqtgraph as pg
from PySide6.QtCore import QRunnable
from PySide6.QtGui import QColor

from ..chrome import font
from ..theme import FONT, LAYOUT


class PlotLayer:
    FADES_WHILE_DRAGGING = False

    def __init__(self, plot, vb):
        self.plot, self.vb = plot, vb
        self.canvas = None                     # set by PlotCanvas.add_layer
        self.theme = None

    def add_item(self, item, z: float):
        item.setZValue(z)
        if self.canvas is not None and self.canvas.static_cache:
            from .animation_layer import STATIC_CACHE
            item.setCacheMode(STATIC_CACHE)                 # animating: drawn once, then copied
        for name in ("sigPlotChanged", "sigImageChanged"):  # new data: the stored picture is thrown away
            signal = getattr(item, name, None)
            if signal is not None:
                signal.connect(lambda *_a, it=item: drop_picture(it))
        self.plot.addItem(item)
        return item

    def items(self) -> list:
        """Items drawn faintly while an element is dragged (see fades_while_dragging)."""
        return []

    def fades_while_dragging(self) -> bool:
        return self.FADES_WHILE_DRAGGING

    # hooks (see the module docstring); a layer overrides the ones it needs
    def apply_theme(self, theme: dict):
        self.theme = theme

    def scene_changed(self):
        pass

    def selection_changed(self):
        pass

    def view_changed(self):
        pass

    def visibility_changed(self):
        pass

    def drag_started(self):
        pass

    def drag_moved(self):
        pass

    def drag_finished(self):
        pass

    def shutdown(self):
        pass


class BackgroundJob(QRunnable):
    """A function run by a QThreadPool (the layers' background computations). It never touches widgets:
    its results go back to the GUI thread through a signal."""

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.setAutoDelete(True)

    def run(self):
        self.fn()


# ---------------------------------------------------------------------- small drawing helpers
def glow_dots(plot, xs, ys, color, size: float, z: float) -> list:
    """Soft glow of a selected symbol: a few wide, semi-transparent dots of its color underneath."""
    out = []
    for extra, alpha in LAYOUT["selection_glow"]:
        c = QColor(color)
        c.setAlpha(alpha)
        g = pg.ScatterPlotItem(list(xs), list(ys), size=size + extra, symbol="o",
                               brush=pg.mkBrush(c), pen=pg.mkPen(None))
        g.setZValue(z)
        plot.addItem(g)
        out.append(g)
    return out


def mono_css() -> str:
    """Font family of the small coordinate boxes on the plot (for their HTML)."""
    return "'" + font("mono", FONT["plot_label_size_pt"] - 1).family() + "'"


def set_box_text(label: pg.TextItem, theme: dict, html: str, padding: str = "2px 4px"):
    """A small box on the plot (coordinates of a point): panel colors, monospaced text."""
    label.setHtml(f'<div style="color:{theme["text"]}; font-family:{mono_css()}; font-size:9pt; '
                  f'padding:{padding};">{html}</div>')
    label.fill = pg.mkBrush(theme["panel_bg"])
    label.border = pg.mkPen(theme["border"])


def drop_picture(item):
    """While animating, an item is kept as a picture (DeviceCoordinateCache). Qt's own invalidation on new
    data was not enough: after dragging an element in the Pulses view, parts of an older picture of the
    streamlines stayed on the screen. Switching the cache off and on again throws the picture away for sure."""
    from PySide6.QtWidgets import QGraphicsItem
    mode = item.cacheMode()
    if mode != QGraphicsItem.NoCache:
        item.setCacheMode(QGraphicsItem.NoCache)
        item.setCacheMode(mode)
