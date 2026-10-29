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
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QGraphicsItem, QGraphicsView, QLabel, QVBoxLayout, QWidget

from physics.field import reference_speed

from ..chrome import TitleBlock, device_line_rect, font
from ..theme import FONT, LAYOUT
from .animation_layer import STATIC_CACHE
from .bar import CanvasBar
from .body_layer import BodyLayer
from .element_layer import ElementLayer
from .field_layer import KEYS as FIELD_KEYS
from .field_layer import FieldLayer
from .gl_viewport import PlotGLViewport, PlotView
from .interaction import DRAG_OPACITY, MOUSE_MODES, PlotInteraction, PlotViewBox
from .particle_layer import ParticleLayer
from .surface_layer import SurfaceLayer
from .pulse_layer import PulseLayer
from .settings import PlotSettings
from .stagnation_layer import StagnationLayer
from .streamline_layer import StreamlineLayer

LIVE_DRAG_DEFAULT = True          # "Live update while dragging" until the user changes it
VIEW_MODES = ("static", "particles", "pulses")      # the buttons at the left of the bar

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
    ("bodies", "Solid bodies (filled)", False),
    ("surface", "Surface pressure (Cp on surfaces)", False),
)


# Qt keeps the item pictures of set_static_cache in its pixmap cache, 10 MB by default. One picture of a
# plot-sized item is ~4–12 MB (125 % screen: 1250 × 640 device px × 4 bytes); with a few layers on, the
# pictures did not fit, Qt threw them away and drew every item again in EVERY animation frame (measured: plot
# frame 21–29 ms instead of 4–5 ms, the owner's 23 fps with φ lines + |V| bands). The limit is only a ceiling:
# memory is used by the pictures that exist.
PIXMAP_CACHE_PICTURES = 40                     # plot-sized pictures that fit (layers × a margin)
PIXMAP_CACHE_MIN_KB, PIXMAP_CACHE_MAX_KB = 128 * 1024, 1024 * 1024


def pixmap_cache_kb() -> int:
    """The pixmap cache needed for PIXMAP_CACHE_PICTURES pictures of the largest screen (device pixels)."""
    from PySide6.QtGui import QGuiApplication
    area = 0
    for s in QGuiApplication.screens():
        g, r = s.geometry(), s.devicePixelRatio()
        area = max(area, g.width() * r * g.height() * r)
    kb = int(PIXMAP_CACHE_PICTURES * area * 4 / 1024)
    return max(PIXMAP_CACHE_MIN_KB, min(PIXMAP_CACHE_MAX_KB, kb))


def ensure_pixmap_cache():
    from PySide6.QtGui import QPixmapCache
    kb = pixmap_cache_kb()
    if QPixmapCache.cacheLimit() < kb:
        QPixmapCache.setCacheLimit(kb)


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
    view_mode_changed = Signal(str)     # "static", "particles", "pulses" (VIEW_MODES)
    paused_changed = Signal(bool)
    message = Signal(str)               # a short note for the status bar

    def __init__(self, theme: dict, elements: list, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.elements = elements
        self.settings = PlotSettings()
        self.layers = {key: on for key, _label, on in LAYERS}
        self.selected = -1                       # index of the selected element (highlighted)
        self.live_drag = LIVE_DRAG_DEFAULT       # streamlines follow a dragged element (program setting)
        self.view_mode = "static"                # static streamlines, or an animation (VIEW_MODES)
        self.static_cache = False                # plot items cached as pictures (while animating)
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
        self.plot = PlotView(viewBox=PlotViewBox())            # (counts its frames: the Graphics card panel)
        # no cached background: at a fractional display scale (125 %) the cached picture (logical
        # pixels) left the last device pixel column unpainted — a dark line beside the right frame,
        # depending on the plot's width (e.g. with a side panel open). The viewport fills itself too.
        self.plot.setCacheMode(QGraphicsView.CacheNone)
        self.plot.viewport().setAutoFillBackground(True)
        self.gpu_info = None                     # what the graphics card said (PlotGLViewport.ready), or None
        self.plot.setAspectLocked(True)          # circles must look like circles
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()
        lay.addWidget(self.plot, 1)
        self.title_block = TitleBlock(self)      # SCENE | ELEMENTS | VIEW | FILE (filled by the window)
        lay.addWidget(self.title_block)
        self.vb = self.plot.getPlotItem().getViewBox()
        # axis label space only grows: with the aspect lock, a shrinking axis (e.g. "-2.5" -> "-2")
        # widens the plot area, which changes the y range and its labels again -> the view would jump
        # back and forth without end at some window sizes
        for name in ("left", "bottom"):
            self.plot.getPlotItem().getAxis(name).setStyle(autoReduceTextSpace=False)
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
        self.bodies = self.add_layer(BodyLayer(self.plot, self.vb))
        self.surfaces = self.add_layer(SurfaceLayer(self.plot, self.vb))           # Cp on body surfaces, walls
        self.surfaces.legend.clicked = self.cp_reference_requested.emit
        self.particles = self.add_layer(ParticleLayer(self.plot, self.vb))      # animation styles
        self.pulses = self.add_layer(PulseLayer(self.plot, self.vb))
        self.bodies.changed += [self.particles.bodies_changed, self.pulses.bodies_changed,
                                lambda: self.layers["equipotential"] and self.fields.schedule(force=True)]
        self.interaction = PlotInteraction(self)

        self.bar.message.connect(self.message)
        self.bar.btn_fit.clicked.connect(self.fit_view)
        self.bar.mode_selected.connect(self.set_mode)
        self.bar.view_mode_selected.connect(self.set_view_mode)
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
        elif key == "bodies":
            self.bodies.refresh()
        elif key == "surface":
            self.surfaces.refresh()
        elif key == "stagnation" and not on:
            self.stagnation.select(None)
        else:
            self.stagnation.draw()                   # (the dividing lines depend on the switches too)

    def apply_visibility(self):
        for layer in self._layers:
            layer.visibility_changed()

    # ------------------------------------------------------------------ view mode, animation
    @property
    def animated(self) -> bool:
        """An animation runs (particles or pulses over faint streamlines, no arrows)."""
        return self.view_mode != "static"

    @property
    def animation(self):
        """The layer of the running animation (particles also in Static mode: nothing runs then)."""
        return self.pulses if self.view_mode == "pulses" else self.particles

    def _animation_layers(self):
        return (self.particles, self.pulses)

    def set_view_mode(self, mode: str):
        """Static: streamlines + arrows; Particles / Pulses: that animation over faint streamlines."""
        if mode not in VIEW_MODES or mode == self.view_mode:
            return
        was = self.animated
        self.view_mode = mode
        self.bar.set_view_mode(mode)
        if self.animated != was:
            self.set_static_cache(self.animated)
        chosen = self.animation if self.animated else None
        for layer in self._animation_layers():
            if layer is not chosen:
                layer.set_animated(False)
        if chosen is not None:
            chosen.set_animated(True)
        self.streamlines.set_line_pens()
        self.apply_visibility()
        if self.paused and not self.animated:
            self.set_paused(False)
        self.view_mode_changed.emit(mode)

    def set_animated(self, on: bool):
        """Static, or the particle animation (if no animation runs yet)."""
        if bool(on) != self.animated:
            self.set_view_mode("particles" if on else "static")

    @property
    def paused(self) -> bool:
        return self.particles.paused

    def set_paused(self, on: bool):
        for layer in self._animation_layers():
            layer.set_paused(on)
        self.paused_changed.emit(bool(on))

    def toggle_pause(self) -> bool:
        """Space: pause / continue the animation (nothing in Static mode). Returns the new state."""
        if not self.animated:
            return False
        self.set_paused(not self.paused)
        return self.paused

    def set_static_cache(self, on: bool):
        """Keep every plot item (except the animation pictures) as a picture: a frame of the animation
        then only repaints the animation picture."""
        self.static_cache = bool(on)
        if on:
            ensure_pixmap_cache()
        mode = STATIC_CACHE if on else QGraphicsItem.NoCache
        own = {layer.trail for layer in self._animation_layers()}
        for item in self.vb.addedItems:
            if item not in own:
                item.setCacheMode(mode)

    # ------------------------------------------------------------------ graphics card (OpenGL)
    @property
    def gpu(self) -> bool:
        """The plot is drawn by the graphics card (an OpenGL viewport)."""
        return isinstance(self.plot.viewport(), QOpenGLWidget)

    def set_gpu(self, on: bool, samples: int = 4, factory=None):
        """Draw the plot with the graphics card (OpenGL) or with the processor (as before). Everything else
        stays: items, view, selection, animation. Returns the new viewport (a PlotGLViewport: listen to
        its ready / failed / frameSwapped signals). factory: makes the OpenGL viewport (tests)."""
        on = bool(on)
        if on == self.gpu:
            return self.plot.viewport()
        new = (factory or (lambda: PlotGLViewport(samples)))() if on else QWidget()
        self.gpu_info = None
        self.plot.setViewport(new)                       # (Qt deletes the old viewport)
        self._setup_viewport()
        for layer in self._animation_layers():           # their pictures: on the card / in memory now
            layer.gpu_changed()
        self.plot.meter.clear()
        self.plot.viewport().update()
        return new

    def _setup_viewport(self):
        """What the plot's viewport needs (also after a switch): background, update mode, the mouse and
        drop handling of PlotInteraction."""
        vp = self.plot.viewport()
        gl = isinstance(vp, QOpenGLWidget)
        # an OpenGL frame is drawn whole each time (its old content is not kept): repaint the whole plot,
        # never only the changed part (that would leave the rest of the frame empty)
        self.plot.setViewportUpdateMode(QGraphicsView.FullViewportUpdate if gl
                                        else QGraphicsView.MinimalViewportUpdate)
        if not gl:
            vp.setAutoFillBackground(True)
        self._viewport_palette()
        self.interaction.viewport_changed()

    def _viewport_palette(self):
        pal = self.plot.viewport().palette()
        pal.setColor(QPalette.Window, QColor(self.theme["plot_bg"]))
        pal.setColor(QPalette.Base, QColor(self.theme["plot_bg"]))
        self.plot.viewport().setPalette(pal)

    def set_frame_interval(self, ms: int):
        """Animation frames every ms milliseconds (the fps limit of the Graphics card panel)."""
        for layer in self._animation_layers():
            layer.set_frame_interval(ms)

    def set_setting(self, key: str, value):
        """A setting of the Plot settings panel (settings.SLIDERS): PlotCanvas.set_<key>(value)."""
        getattr(self, f"set_{key}")(value)

    def set_particles(self, count: int):
        self.settings.particles = int(count)
        self.particles.set_count(count)

    def set_anim_speed(self, slider: int):
        """Particles: speed slider 1 … 10."""
        self.settings.anim_speed = self.particles.speed_slider = int(slider)

    def set_trail(self, slider: int):
        """Particles: trail length slider 0 … 10."""
        self.settings.trail = self.particles.trail_slider = int(slider)

    def set_pulse_speed(self, slider: int):
        self.settings.pulse_speed = self.pulses.speed_slider = int(slider)

    def set_pulse_length(self, slider: int):
        self.settings.pulse_length = self.pulses.trail_slider = int(slider)

    def set_pulse_spacing(self, slider: int):
        self.settings.pulse_spacing = int(slider)
        self.pulses.set_spacing(slider)

    def lines_shown(self, result):
        """StreamlineLayer drew new lines (also a preview of a dragged element): pulses run along them."""
        self.pulses.set_lines(result)

    # ------------------------------------------------------------------ plot settings
    def apply_settings(self, settings: PlotSettings):
        """Settings of an opened scene (the scene itself follows, which computes everything)."""
        self.settings = settings
        self.streamlines.set_line_pens()
        self.particles.set_count(settings.particles)
        self.particles.speed_slider, self.particles.trail_slider = settings.anim_speed, settings.trail
        self.pulses.speed_slider, self.pulses.trail_slider = settings.pulse_speed, settings.pulse_length
        self.pulses.set_spacing(settings.pulse_spacing)

    def set_density(self, density: float):
        self.settings.density = density
        self.streamlines.restart()
        self.fields.schedule(force=True)            # φ line spacing follows the streamline spacing

    def set_arrows(self, show: bool):
        self.settings.show_arrows = bool(show)
        self.streamlines.redraw()

    def set_arrow_density(self, density: float):
        self.settings.arrow_density = density
        self.streamlines.redraw()

    def set_live_drag(self, on: bool):
        """Live update while dragging: the streamlines of the visible region follow a dragged element
        (computed in the background, newest position first); otherwise they fade until release."""
        self.live_drag = bool(on)

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
        self.surfaces.redraw()

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

    def compute_now(self):
        """Everything of the current scene and view drawn now, synchronously — streamlines, stagnation
        points, dividing streamlines, field layers, bodies — e.g. before a figure is exported without
        a window (command line). The background computation that was running is cancelled."""
        self.streamlines.recompute()
        self.fields.schedule(force=True, now=True)
        self.bodies.update()
        if self.surfaces.wanted:
            background, self.surfaces.background = self.surfaces.background, False
            self.surfaces.refresh()
            self.surfaces.background = background

    def wait_idle(self, msecs: int = 10000) -> bool:
        """Wait until the background computation is idle (results still arrive via the event loop)."""
        return self.streamlines.wait_idle(msecs) and self.surfaces.wait(msecs)

    def shutdown(self):
        """Stop background work (call before the window closes)."""
        for layer in self._layers:
            layer.shutdown()

    def streamlines_drawn(self, result, ms):
        """A streamline result was drawn (ms = None: a partial result, more follows)."""
        self.last_result = result
        self.stagnation.set_result(result)
        if ms is not None or result.dividing:
            self.bodies.set_result(result)
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
            for item in layer.items() if layer.fades_while_dragging() else ():
                item.setOpacity(DRAG_OPACITY)
            layer.drag_started()
        self.apply_visibility()

    def drag_moved(self):
        for layer in self._layers:
            layer.drag_moved()

    def drag_finished(self):
        for layer in self._layers:
            for item in layer.items():
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
        self._viewport_palette()
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
