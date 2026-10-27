"""
animation_layer.py — the animated views (buttons Particles / Pulses at the left of the plot bar):

    ParticleLayer  "Particles": tracer particles carried by the flow, with fading trails
    PulseLayer     "Pulses along streamlines": bright dashes that run along the drawn streamlines at
                   the local speed (like puffs of dye released at the same moment, again and again)

Both are colored by speed (pastel blue = slow … red = fast) with a legend, and draw into one picture
of the visible region (device pixels) that the plot shows over the streamlines (AnimatedLayer).

Particle trails: every frame the picture fades a little (integer arithmetic that rounds down, so old
trails really disappear), then each particle's step since the last frame is drawn on top as a short
line. The trail length is how fast the picture fades. Zoom / pan start the picture again (the old trails
would be in the wrong place).

Pulses: every streamline is cut into ~2 pixel pieces with the travel time τ from the start of its line
(physics.particles.travel_times). With the animation time t and the pulse period T, a piece is lit
when s = frac((t − τ) / T) < L (L = the lit part of a period, Pulse length slider), brightest at the
head (s = 0); T follows from the Spacing slider. Equal spacing in TIME: pulses stretch where the flow is fast and crowd where it is slow.
The picture is drawn anew every frame.

While animating, every other plot item is cached as a picture in device pixels (Qt's
DeviceCoordinateCache, PlotCanvas.set_static_cache): a frame repaints the animation picture and copies
the cached pictures, instead of drawing all streamlines again. The frame timer stops when the animation
is paused (and does nothing while the window is hidden).
"""
import math
import time

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QLineF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem

from physics import kernel
from physics.field import active
from physics.images import resolve
from physics.particles import Particles, nice_top, time_scale, travel_times, typical_speed

from .contours import ramp
from .layer import PlotLayer
from .legend import ColorLegend

FRAME_MS = 16                    # ~60 frames per second
BINS = 8                         # speed colors (also the legend bands)
LINE_PX = 1.7                    # width of a particle's trail line (screen pixels)
MAX_STEP_PX = 24                 # a longer step in one frame (next to a singular point) is not drawn:
                                 # as a straight line it would cut across the curved path
PULSE_PX = 3.0                   # width of a pulse (screen pixels)
PULSE_STEP_PX = 2.0              # pulses: streamlines cut into pieces of about this length
STATIC_CACHE = QGraphicsItem.DeviceCoordinateCache


def speed_factor(slider: int) -> float:
    """Speed slider 1 … 10 -> time scale × 0.25 … × 5.7 (5 = a typical particle crosses the view in 6 s)."""
    return 2.0 ** ((slider - 5) / 2.0)


def trail_seconds(slider: int) -> float:
    """Trail length slider 0 … 10 -> how long a trail takes to fade (0 = no trail: dots only)."""
    return 0.0 if slider <= 0 else 0.05 * 1.45 ** slider


def pulse_length(slider: int) -> float:
    """Pulse length slider 0 … 10 -> lit part of a pulse period (0: short dashes … 10: long comets)."""
    return 0.06 + 0.064 * min(max(slider, 0), 10)


def pulse_spacing(slider: int) -> float:
    """Spacing slider 1 … 10 -> distance between pulses at the typical speed, in streamline spacings
    (4 -> 4)."""
    return 1.0 + 0.75 * min(max(slider, 1), 10)


class TrailItem(pg.GraphicsObject):
    """The animation picture, drawn over the visible region in data coordinates (row 0 = bottom: the
    plot's y axis points up)."""

    def __init__(self):
        super().__init__()
        self.image = None
        self.rect = QRectF()

    def set_image(self, image, rect):
        if rect != self.rect:
            self.prepareGeometryChange()
            self.rect = QRectF(rect)
        self.image = image
        self.update()

    def boundingRect(self):
        return self.rect

    def paint(self, p, *args):
        if self.image is not None and not self.rect.isEmpty():
            p.drawImage(self.rect, self.image)              # the picture has the view's pixel size


class AnimatedLayer(PlotLayer):
    """What both animation styles share: the picture, the frame timer, pause, speed colors and legend.
    A style implements start() (animation switched on), typical() (the typical speed of the view) and
    render(image, dt) (one frame); `animated` = this style is running."""
    DRAW_WHILE_PAUSED = False            # draw a new picture (zoom / pan) while paused

    def __init__(self, plot, vb):
        super().__init__(plot, vb)
        self.trail = self.add_item(TrailItem(), 1.5)          # over the streamlines, under the symbols
        self.trail.setVisible(False)
        self.legend = ColorLegend()
        self.legend.setParentItem(vb)
        self.legend.anchor(itemPos=(1, 0), parentPos=(1, 0), offset=(-12, 12))
        self.legend.setVisible(False)
        self.animated = False
        self.paused = False
        self.speed_slider, self.trail_slider = 5, 4
        self._image = None
        self._view_key = None                 # (view, pixel size) the picture belongs to
        self._fresh = False                   # the picture is new (empty)
        self._pens = []
        self._top = 1.0                        # speed of the top legend band (color scale)
        self._last = None
        self.frame_ms = []                     # duration of the last frames (measurements)
        self._timer = QTimer(plot)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self.frame)

    # ------------------------------------------------------------------ to implement
    def start(self):
        """The animation was switched on (or this style chosen)."""

    def typical(self) -> float:
        return 0.0

    def render(self, image, dt: float):
        """Draw one frame into the picture; dt = real seconds since the last frame."""

    # ------------------------------------------------------------------ hooks
    def apply_theme(self, theme):
        super().apply_theme(theme)
        self.legend.theme = theme
        self._colors()
        self._clear()

    def visibility_changed(self):
        self.trail.setVisible(self.animated)
        self._update_legend()

    def shutdown(self):
        self._timer.stop()

    # ------------------------------------------------------------------ settings
    def set_animated(self, on: bool):
        on = bool(on)
        if on == self.animated:
            return
        self.animated = on
        if self.animated:
            self.start()
            self._colors()
            self._clear()
            self._last = None
            self._timer.start()
        else:
            self._timer.stop()
            self._clear()
        self.visibility_changed()

    def set_paused(self, on: bool):
        self.paused = bool(on)
        self._last = None

    # ------------------------------------------------------------------ one frame
    def frame(self):
        now = time.perf_counter()
        dt, self._last = (0.0 if self._last is None else min(now - self._last, 0.1)), now
        if not self.animated or not self.canvas.isVisible():
            return
        image = self._picture()
        if image is None or (self.paused and not (self.DRAW_WHILE_PAUSED and self._fresh)):
            return
        self._fresh = False
        self.render(image, 0.0 if self.paused else dt)
        self.trail.set_image(image, self._rect)
        self._update_legend()
        self.frame_ms.append((time.perf_counter() - now) * 1000.0)
        del self.frame_ms[:-120]

    def _draw(self, image, ax, ay, bx, by, band, alpha, width_px, keep_max):
        """Lines (ax, ay) -> (bx, by) in picture pixels in their speed band's color (band < 0: not
        drawn) with opacity × alpha."""
        dpr = self.plot.devicePixelRatioF()
        if kernel.HAVE_NUMBA:
            rows = np.frombuffer(image.bits(), np.uint8).reshape(image.height(), image.bytesPerLine() // 4, 4)
            kernel.draw_segments(rows, ax, ay, bx, by, band, self._palette, 0.5 * width_px * dpr,
                                 alpha, keep_max)
            return
        painter = QPainter(image)                         # without Numba: Qt draws them (slower)
        painter.setRenderHint(QPainter.Antialiasing, True)
        level = np.clip(np.ceil(alpha * 4), 0, 4).astype(int)          # 4 opacity steps
        for k in range(BINS):
            for q in range(1, 5):
                idx = np.nonzero((band == k) & (level == q))[0]
                if idx.size:
                    pen = QPen(self._pens[k])
                    pen.setWidthF(width_px * dpr)
                    color = pen.color()
                    color.setAlphaF(color.alphaF() * q / 4)
                    pen.setColor(color)
                    painter.setPen(pen)
                    painter.drawLines([QLineF(ax[i], ay[i], bx[i], by[i]) for i in idx])
        painter.end()

    # ------------------------------------------------------------------ picture, colors, legend
    def _box(self):
        (x0, x1), (y0, y1) = self.canvas.view()
        return (x0, x1, y0, y1)

    def _picture(self):
        """The picture for the current view and widget size (a new, empty one if they changed)."""
        dpr = self.plot.devicePixelRatioF()
        size = self.vb.size()
        w, h = int(math.ceil(size.width() * dpr)), int(math.ceil(size.height() * dpr))
        if w < 2 or h < 2:
            return None
        view = self.canvas.view()
        key = (view, w, h)
        if key != self._view_key or self._image is None:
            self._view_key, self._view = key, view
            (x0, x1), (y0, y1) = view
            self._rect = QRectF(x0, y0, x1 - x0, y1 - y0)
            self._image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
            self._image.fill(Qt.transparent)
            self._fresh = True
        return self._image

    def _to_pixels(self, image, z):
        """Data points (complex) -> picture pixels (x, y; row 0 = bottom)."""
        (x0, x1), (y0, y1) = self._view
        sx, sy = image.width() / (x1 - x0), image.height() / (y1 - y0)
        return (z.real - x0) * sx, (z.imag - y0) * sy

    def _clear(self):
        self._view_key = None
        self.trail.set_image(None, self.trail.rect)

    def _colors(self):
        """Speed scale (0 … a round value ≈ 2 × the typical speed of the view) and its pens."""
        if self.theme is None:
            return
        v_typ = self.typical()
        self._top = nice_top(2.0 * v_typ) if v_typ > 0 else 1.0
        stops = self.theme["particles"]
        dpr = self.plot.devicePixelRatioF()
        self._band_colors = [ramp(stops, (k + 0.5) / BINS) for k in range(BINS)]
        self._palette = np.array([(*c, 235 / 255) for c in self._band_colors], dtype=float)
        self._pens = []
        for c in self._band_colors:
            pen = QPen(QColor(*c, 235), LINE_PX * dpr)
            pen.setCapStyle(Qt.RoundCap)
            self._pens.append(pen)
        self.legend.set_bands("|V|  [m/s]", np.linspace(0.0, self._top, BINS + 1), self._band_colors)

    def _band(self, speed):
        return np.clip((speed / self._top * BINS).astype(np.int64), 0, BINS - 1)

    def _update_legend(self):
        """The speed legend unless a color map (|V| or Cp bands) shows its own legend there."""
        fields = self.canvas.fields.legend
        self.legend.setVisible(self.animated and not fields.isVisible())


class ParticleLayer(AnimatedLayer):
    """Style "Particles": tracer particles with fading trails."""

    def __init__(self, plot, vb):
        super().__init__(plot, vb)
        self.particles = Particles()

    def start(self):
        self.particles.set_scene(self.canvas.shown_elements())
        self.particles.set_view(self._box(), restart=True)

    def typical(self) -> float:
        return self.particles.v_typ

    # ------------------------------------------------------------------ hooks
    def scene_changed(self):
        if self.animated:
            self.particles.set_scene(self.canvas.elements)
            self._colors()

    def view_changed(self):
        if self.animated:
            self.particles.set_view(self._box())
            self._colors()
            self._clear()

    def drag_moved(self):
        if self.animated:                                     # the particles flow around the moved element
            self.particles.set_scene(self.canvas.shown_elements())

    def drag_finished(self):
        self.scene_changed()

    def set_count(self, n: int):
        self.particles.set_count(n)

    def bodies_changed(self):
        """The solid bodies changed (BodyLayer): no particles inside them."""
        bodies = self.canvas.bodies
        self.particles.set_excluded(bodies.contains if bodies.mask is not None else None)

    # ------------------------------------------------------------------ one frame
    def render(self, image, dt):
        p = self.particles
        p.step(dt, speed_factor(self.speed_slider))
        tau = trail_seconds(self.trail_slider)
        bits = np.frombuffer(image.bits(), np.uint8)
        if tau > 0:
            keep = int(256 * math.exp(-dt / tau))
            if kernel.HAVE_NUMBA:
                kernel.fade_bytes(bits, keep)
            else:
                bits[:] = (bits.astype(np.uint16) * keep >> 8).astype(np.uint8)
        else:
            bits[:] = 0
        self._draw_steps(image, tau > 0)

    def _draw_steps(self, image, trails: bool):
        """Each particle's step since the last frame as a short line (a dot without trails), in its
        speed color."""
        p = self.particles
        a, b = (p.prev, p.pos) if trails else (p.pos, p.pos)
        ax, ay = self._to_pixels(image, a)
        bx, by = self._to_pixels(image, b)
        dpr = self.plot.devicePixelRatioF()
        draw = ~p.fresh if trails else np.ones(p.pos.size, bool)
        draw &= np.hypot(bx - ax, by - ay) <= MAX_STEP_PX * dpr
        band = np.where(draw, self._band(p.speed), -1)
        self._draw(image, ax, ay, bx, by, band, np.ones(band.size), LINE_PX, False)


class PulseLayer(AnimatedLayer):
    """Style "Pulses along streamlines" (see the module docstring)."""
    DRAW_WHILE_PAUSED = True

    def __init__(self, plot, vb):
        super().__init__(plot, vb)
        self.result = None                    # the StreamlineSet drawn (StreamlineLayer)
        self.t = 0.0                          # animation time
        self.period = 1.0                     # T
        self.v_typ = 0.0
        self._pieces = None                   # (a, b, tau, speed) of the drawn lines (data coordinates)
        self._piece_step = None               # piece length they were cut with
        self._px = None                       # the pieces near the view, in picture pixels
        self._px_key = None
        self.spacing_slider = 4

    def set_spacing(self, slider: int):
        self.spacing_slider = int(slider)
        self._pieces = None                   # a new period

    # ------------------------------------------------------------------ the lines
    def set_lines(self, result):
        """New streamlines are drawn (also the previews while an element is dragged)."""
        self.result = result
        self._pieces = None
        self._px_key = None

    def start(self):
        self.t = 0.0
        self._pieces = None
        self._px_key = None
        self._update_speed()

    def typical(self) -> float:
        return self.v_typ

    def _update_speed(self):
        els = active(self.canvas.shown_elements())
        self.v_typ = typical_speed(els, resolve(els), self._box())

    def _prepare(self, image):
        """Travel times along the lines (again when they or the zoom changed), and the pieces near the
        view in picture pixels (again when the view changed)."""
        res = self.result
        if res is None or not res.lines or not self.v_typ > 0:
            self._px = None
            return
        (x0, x1), _ = self._view
        step = PULSE_STEP_PX * (x1 - x0) / image.width()
        if self._pieces is None or not 0.6 < step / self._piece_step < 1.6:
            self._piece_step = step
            self._pieces = travel_times(res.lines, self.canvas.shown_elements(), step, 1e-3 * self.v_typ)
            sep = res.separation if res.separation > 0 else 0.05 * (x1 - x0)
            self.period = pulse_spacing(self.spacing_slider) * sep / self.v_typ
            self._px_key = None
        if self._px_key == self._view_key:
            return
        self._px_key = self._view_key
        a, b, tau, speed = self._pieces
        ax, ay = self._to_pixels(image, a)
        bx, by = self._to_pixels(image, b)
        m = PULSE_PX * 2
        w, h = image.width(), image.height()
        near = (np.maximum(ax, bx) > -m) & (np.minimum(ax, bx) < w + m) & \
               (np.maximum(ay, by) > -m) & (np.minimum(ay, by) < h + m)
        near &= np.hypot(bx - ax, by - ay) <= MAX_STEP_PX * self.plot.devicePixelRatioF()
        near[near] &= ~self.canvas.bodies.contains(0.5 * (a[near] + b[near]))
        idx = np.nonzero(near)[0]
        self._px = (ax[idx], ay[idx], bx[idx], by[idx], tau[idx] / self.period, self._band(speed[idx]))

    # ------------------------------------------------------------------ hooks
    def scene_changed(self):
        if self.animated:
            self._update_speed()
            self._colors()
            self._px_key = None

    def bodies_changed(self):
        self._px_key = None                   # (pieces inside a body are not drawn)

    def view_changed(self):
        if self.animated:
            self._update_speed()
            self._colors()
            self._px_key = None

    def drag_finished(self):
        self.scene_changed()

    # ------------------------------------------------------------------ one frame
    def render(self, image, dt):
        self.t += dt * time_scale(self._box(), self.v_typ, speed_factor(self.speed_slider))
        bits = np.frombuffer(image.bits(), np.uint8)
        bits[:] = 0
        self._prepare(image)
        if self._px is None:
            return
        ax, ay, bx, by, phase, band = self._px
        s = np.mod(self.t / self.period - phase, 1.0)
        L = pulse_length(self.trail_slider)
        lit = np.nonzero(s < L)[0]
        if lit.size:
            alpha = 1.0 - s[lit] / L                             # bright head, fading tail
            self._draw(image, ax[lit], ay[lit], bx[lit], by[lit], band[lit], alpha, PULSE_PX, True)
