"""
particle_layer.py — the animated view: tracer particles carried by the flow, with fading trails,
colored by speed (pastel blue = slow … red = fast) with a legend.

Trails: one picture of the visible region (device pixels). Every frame it fades a little (integer
arithmetic that rounds down, so old trails really disappear), then each particle's step since the last
frame is drawn on top as a short line. The trail length is how fast the picture fades. Zoom / pan start
the picture again (the old trails would be in the wrong place).

While animating, every other plot item is cached as a picture in device pixels (Qt's
DeviceCoordinateCache): a frame repaints the trails and copies the cached pictures, instead of drawing
all streamlines again. The frame timer stops when the window is hidden or the animation is paused.
"""
import math
import time

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QLineF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem

from physics import kernel
from physics.particles import Particles, nice_top

from .contours import ramp
from .layer import PlotLayer
from .legend import ColorLegend

FRAME_MS = 16                    # ~60 frames per second
BINS = 8                         # speed colors (also the legend bands)
LINE_PX = 1.7                    # width of a particle's trail line (screen pixels)
MAX_STEP_PX = 24                 # a longer step in one frame (next to a singular point) is not drawn:
                                 # as a straight line it would cut across the curved path
STATIC_CACHE = QGraphicsItem.DeviceCoordinateCache


def speed_factor(slider: int) -> float:
    """Speed slider 1 … 10 -> time scale × 0.25 … × 5.7 (5 = a typical particle crosses the view in 6 s)."""
    return 2.0 ** ((slider - 5) / 2.0)


def trail_seconds(slider: int) -> float:
    """Trail length slider 0 … 10 -> how long a trail takes to fade (0 = no trail: dots only)."""
    return 0.0 if slider <= 0 else 0.05 * 1.45 ** slider


class TrailItem(pg.GraphicsObject):
    """The trail picture, drawn over the visible region in data coordinates (row 0 = bottom: the plot's
    y axis points up)."""

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


class ParticleLayer(PlotLayer):

    def __init__(self, plot, vb):
        super().__init__(plot, vb)
        self.trail = self.add_item(TrailItem(), 1.5)          # over the streamlines, under the symbols
        self.trail.setVisible(False)
        self.legend = ColorLegend()
        self.legend.setParentItem(vb)
        self.legend.anchor(itemPos=(1, 0), parentPos=(1, 0), offset=(-12, 12))
        self.legend.setVisible(False)
        self.particles = Particles()
        self.animated = False
        self.paused = False
        self.speed_slider, self.trail_slider = 5, 4
        self._image = None
        self._view_key = None                 # (view, pixel size) the picture belongs to
        self._pens = []
        self._top = 1.0                        # speed of the top legend band (color scale)
        self._last = None
        self.frame_ms = []                     # duration of the last frames (measurements)
        self._timer = QTimer(plot)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self.frame)

    # ------------------------------------------------------------------ hooks
    def apply_theme(self, theme):
        super().apply_theme(theme)
        self.legend.theme = theme
        self._colors()
        self._clear()

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

    def visibility_changed(self):
        self.trail.setVisible(self.animated)
        self._update_legend()

    def shutdown(self):
        self._timer.stop()

    # ------------------------------------------------------------------ settings
    def set_animated(self, on: bool):
        self.animated = bool(on)
        self.canvas.set_static_cache(self.animated)
        if self.animated:
            self.particles.set_scene(self.canvas.shown_elements())
            self.particles.set_view(self._box(), restart=True)
            self._colors()
            self._clear()
            self._last = None
            self._timer.start()
        else:
            self._timer.stop()
        self.visibility_changed()

    def set_paused(self, on: bool):
        self.paused = bool(on)
        self._last = None

    def set_count(self, n: int):
        self.particles.set_count(n)

    # ------------------------------------------------------------------ one frame
    def frame(self):
        now = time.perf_counter()
        dt, self._last = (0.0 if self._last is None else min(now - self._last, 0.1)), now
        if self.paused or not self.animated or not self.canvas.isVisible():
            return
        image = self._picture()
        if image is None:
            return
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
        self.trail.set_image(image, self._rect)
        self._update_legend()
        self.frame_ms.append((time.perf_counter() - now) * 1000.0)
        del self.frame_ms[:-120]

    def _draw_steps(self, image, trails: bool):
        """Each particle's step since the last frame as a short line (a dot without trails), in its
        speed color."""
        p = self.particles
        (x0, x1), (y0, y1) = self._view
        sx, sy = image.width() / (x1 - x0), image.height() / (y1 - y0)
        a, b = (p.prev, p.pos) if trails else (p.pos, p.pos)
        ax, ay = (a.real - x0) * sx, (a.imag - y0) * sy
        bx, by = (b.real - x0) * sx, (b.imag - y0) * sy
        dpr = self.plot.devicePixelRatioF()
        draw = ~p.fresh if trails else np.ones(p.pos.size, bool)
        draw &= np.hypot(bx - ax, by - ay) <= MAX_STEP_PX * dpr
        band = np.clip((p.speed / self._top * BINS).astype(np.int64), 0, BINS - 1)
        if kernel.HAVE_NUMBA:
            rows = np.frombuffer(image.bits(), np.uint8).reshape(image.height(), image.bytesPerLine() // 4, 4)
            kernel.draw_segments(rows, ax, ay, bx, by, np.where(draw, band, -1), self._palette,
                                 0.5 * LINE_PX * dpr)
            return
        painter = QPainter(image)                         # without Numba: Qt draws them (slower)
        painter.setRenderHint(QPainter.Antialiasing, True)
        for k in range(BINS):
            idx = np.nonzero(draw & (band == k))[0]
            if idx.size:
                painter.setPen(self._pens[k])
                painter.drawLines([QLineF(ax[i], ay[i], bx[i], by[i]) for i in idx])
        painter.end()

    # ------------------------------------------------------------------ picture, colors, legend
    def _box(self):
        (x0, x1), (y0, y1) = self.canvas.view()
        return (x0, x1, y0, y1)

    def _picture(self):
        """The trail picture for the current view and widget size (a new, empty one if they changed)."""
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
        return self._image

    def _clear(self):
        self._view_key = None
        self.trail.set_image(None, self.trail.rect)

    def _colors(self):
        """Speed scale (0 … a round value ≈ 2 × the typical speed of the view) and its pens."""
        if self.theme is None:
            return
        self._top = nice_top(2.0 * self.particles.v_typ) if self.particles.v_typ > 0 else 1.0
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

    def _update_legend(self):
        """The particle legend unless a color map (|V| or Cp bands) shows its own legend there."""
        fields = self.canvas.fields.legend
        self.legend.setVisible(self.animated and not fields.isVisible())
