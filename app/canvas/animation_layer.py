"""
animation_layer.py — what the animated views share (AnimatedLayer): one picture of the visible region
(device pixels) that the plot shows over the streamlines, the frame timer, pause, speed colors (pastel
blue = slow … red = fast) and their legend. The views themselves:

    particle_layer.py  "Particles": tracer particles carried by the flow, with fading trails
    pulse_layer.py     "Pulses along streamlines": bright dashes that run along the drawn streamlines
                       at the local speed (like puffs of dye released at the same moment, again and again)

While animating, every other plot item is cached as a picture in device pixels (Qt's
DeviceCoordinateCache, PlotCanvas.set_static_cache): a frame repaints the animation picture and copies
the cached pictures, instead of drawing all streamlines again. While paused a frame draws nothing (the
pulses only after a zoom / pan); while the window is minimized or hidden the timer slows down to a
look every HIDDEN_MS. Exports draw the picture again at their own resolution (set_export_scale,
advance).
"""
import math
import time

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QGraphicsItem

from physics import kernel
from physics.particles import nice_top

from .contours import ramp
from .layer import PlotLayer
from .legend import ColorLegend

FRAME_MS = 16                    # ~60 frames per second
HIDDEN_MS = 250                  # window minimized / hidden: only look now and then whether it is back
BINS = 8                         # speed colors (also the legend bands)
LINE_PX = 1.7                    # width of a particle's trail line (screen pixels)
MAX_STEP_PX = 24                 # a longer step in one frame (next to a singular point) is not drawn:
                                 # as a straight line it would cut across the curved path
STATIC_CACHE = QGraphicsItem.DeviceCoordinateCache
MAX_WAIT_TICKS = 6               # a frame not shown after this many ticks: draw the next anyway (never stuck)


class GLFrame:
    """One frame for the graphics card: the picture's size (like a QImage: width(), height()) and the
    drawing steps the layer records into it (done by AnimatedLayer.paint_gl)."""

    def __init__(self, w: int, h: int, ops: list):
        self._w, self._h, self.ops = w, h, ops

    def width(self) -> int:
        return self._w

    def height(self) -> int:
        return self._h


def speed_factor(slider: int) -> float:
    """Speed slider 1 … 10 -> time scale × 0.25 … × 5.7 (5 = a typical particle crosses the view in 6 s)."""
    return 2.0 ** ((slider - 5) / 2.0)


class TrailItem(pg.GraphicsObject):
    """The animation picture, drawn over the visible region in data coordinates (row 0 = bottom: the
    plot's y axis points up)."""

    def __init__(self, layer=None):
        super().__init__()
        self.layer = layer                    # the AnimatedLayer (its picture on the graphics card)
        self.image = None
        self.rect = QRectF()
        self.shown = True                     # the last picture has been painted on the screen
        self.on_gpu = False                   # the picture is on the graphics card (layer.paint_gl)

    def set_image(self, image, rect):
        if rect != self.rect:
            self.prepareGeometryChange()
            self.rect = QRectF(rect)
        self.image = image
        self.on_gpu = False
        self.shown = image is None
        self.update()

    def set_gpu_picture(self, rect):
        """A new frame of the picture on the graphics card, over rect."""
        if rect != self.rect:
            self.prepareGeometryChange()
            self.rect = QRectF(rect)
        self.image = None
        self.on_gpu = True
        self.shown = False
        self.update()

    def boundingRect(self):
        return self.rect

    def paint(self, p, *args):
        self.shown = True
        if self.rect.isEmpty():
            return
        if self.on_gpu:
            device = p.device()
            if isinstance(device, QOpenGLWidget) and self.layer is not None:
                self.layer.paint_gl(p, device)
            return
        if self.image is not None:
            p.drawImage(self.rect, self.image)              # the picture has the view's pixel size


class AnimatedLayer(PlotLayer):
    """What both animation styles share: the picture, the frame timer, pause, speed colors and legend.
    A style implements start() (animation switched on), typical() (the typical speed of the view) and
    render(image, dt) (one frame); `animated` = this style is running."""
    DRAW_WHILE_PAUSED = False            # draw a new picture (zoom / pan) while paused
    KEEP_PICTURE = False                 # zoom / pan: the old picture is carried over into the new one

    def __init__(self, plot, vb):
        super().__init__(plot, vb)
        self.trail = self.add_item(TrailItem(self), 1.5)      # over the streamlines, under the symbols
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
        self.frame_interval = FRAME_MS        # ms between frames (the graphics card mode may set it lower)
        self._timer.setInterval(self.frame_interval)
        self._timer.timeout.connect(self.frame)
        self.export_scale = None              # recording a GIF / MP4: picture pixels per screen pixel
        self._waited = 0                      # timer ticks skipped while the last frame was not shown
        self.gpu_broken = False               # the graphics card could not draw it: the processor does
        self._gl_ops = []                     # drawing steps for the card, done at the next paint (GLFrame)
        self.gl_name = type(self).__name__

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

    def set_frame_interval(self, ms: int):
        """Frames every ms milliseconds (16 = ~60 fps; PlotCanvas.set_frame_interval)."""
        self.frame_interval = max(1, int(ms))
        if self._timer.interval() != HIDDEN_MS:
            self._timer.setInterval(self.frame_interval)

    def set_paused(self, on: bool):
        self.paused = bool(on)
        self._last = None

    def pixel_scale(self) -> float:
        """Picture pixels per screen pixel: the screen's device pixel ratio, or the resolution of a
        GIF / MP4 being recorded (app.export.animation)."""
        return self.export_scale or self.plot.devicePixelRatioF()

    def set_export_scale(self, scale):
        """Recording (scale = picture pixels per screen pixel) or back to the screen (None): the timer
        stops while recording; frames are made with advance()."""
        self.export_scale = scale
        self._clear()
        self._colors()
        if scale is not None:
            self._timer.stop()
        elif self.animated:
            self._last = None
            self._timer.start()

    def advance(self, dt: float):
        """One frame of dt seconds (recording): the picture is drawn even while the window is hidden."""
        image = self._picture()
        if image is None:
            return
        self._fresh = False
        self.render(image, dt)
        self.trail.set_image(image, self._rect)

    # ------------------------------------------------------------------ one frame
    def frame(self):
        now = time.perf_counter()
        if not self.trail.shown and self._waited < MAX_WAIT_TICKS and self.animated:
            # the last frame is not on the screen yet (the window is busy painting, or waits for the
            # screen's refresh): drawing another one now would only be thrown away and leave the window
            # less time to paint — frames shown dropped to ~27 per second at a 144 fps limit. The time
            # goes on (dt from the last frame drawn), so the speed of the flow stays right.
            self._waited += 1
            return
        self._waited = 0
        dt, self._last = (0.0 if self._last is None else min(now - self._last, 0.1)), now
        if not self.animated:
            return
        if not self.canvas.isVisible() or self.canvas.window().isMinimized():
            self._timer.setInterval(HIDDEN_MS)          # nothing to draw: no work 60 times a second
            self._last = None
            return
        if self._timer.interval() != self.frame_interval:
            self._timer.setInterval(self.frame_interval)
            self._last = now
        gpu = self.use_gpu()
        image = self._gl_frame() if gpu else self._picture()
        if image is None or (self.paused and not (self.DRAW_WHILE_PAUSED and self._fresh)):
            return
        self._fresh = False
        self.render(image, 0.0 if self.paused else dt)
        if gpu:
            self.trail.set_gpu_picture(self._rect)
        else:
            self.trail.set_image(image, self._rect)
        self._update_legend()
        self.frame_ms.append((time.perf_counter() - now) * 1000.0)
        del self.frame_ms[:-120]

    def _draw(self, image, ax, ay, bx, by, band, alpha, width_px, keep_max):
        """Lines (ax, ay) -> (bx, by) in picture pixels in their speed band's color (band < 0: not
        drawn) with opacity × alpha."""
        dpr = self.pixel_scale()
        if isinstance(image, GLFrame):
            image.ops.append(("segs", np.column_stack([ax, ay, bx, by, band, alpha]), 0.5 * width_px * dpr,
                              keep_max))
            return
        if kernel.HAVE_NUMBA:
            rows = np.frombuffer(image.bits(), np.uint8).reshape(image.height(), image.bytesPerLine() // 4, 4)
            kernel.draw_segments_parallel(rows, ax, ay, bx, by, band, self._palette, 0.5 * width_px * dpr,
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
        dpr = self.pixel_scale()
        size = self.vb.size()
        w, h = int(math.ceil(size.width() * dpr)), int(math.ceil(size.height() * dpr))
        if w < 2 or h < 2:
            return None
        view = self.canvas.view()
        key = (view, w, h)
        if key != self._view_key or self._image is None:
            old, old_view = (self._image, self._view) if self._view_key is not None else (None, None)
            self._view_key, self._view = key, view
            (x0, x1), (y0, y1) = view
            self._rect = QRectF(x0, y0, x1 - x0, y1 - y0)
            self._image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
            self._image.fill(Qt.transparent)
            self._fresh = True
            if self.KEEP_PICTURE and old is not None:
                self._carry_over(old, old_view)
        return self._image

    def _carry_over(self, old, old_view):
        """The old picture drawn into the new one where its region now is (a pan shifts it by whole
        pixels; a zoom scales it), so trails go on while the view moves. Not after a big zoom."""
        (a0, a1), (b0, b1) = old_view
        (x0, x1), (y0, y1) = self._view
        sx, sy = self._image.width() / (x1 - x0), self._image.height() / (y1 - y0)
        target = QRectF((a0 - x0) * sx, (b0 - y0) * sy, (a1 - a0) * sx, (b1 - b0) * sy)
        ratio = target.width() / max(old.width(), 1)
        if not 0.5 < ratio < 2.0:
            return
        painter = QPainter(self._image)
        if abs(ratio - 1.0) < 1e-6:                              # pan: whole pixels, no blur
            painter.drawImage(round(target.x()), round(target.y()), old)
        else:
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawImage(target, old)
        painter.end()
        self._fresh = False

    def _to_pixels(self, image, z):
        """Data points (complex) -> picture pixels (x, y; row 0 = bottom)."""
        (x0, x1), (y0, y1) = self._view
        sx, sy = image.width() / (x1 - x0), image.height() / (y1 - y0)
        return (z.real - x0) * sx, (z.imag - y0) * sy

    def _clear(self):
        self._view_key = None
        self._gl_ops = [("clear",)]
        self.trail.set_image(None, self.trail.rect)

    # ------------------------------------------------------------------ on the graphics card
    def use_gpu(self) -> bool:
        """Draw this animation with the graphics card: the plot is drawn by it (GPU box), not recording,
        and it worked so far."""
        return bool(self.canvas is not None and self.canvas.gpu and self.export_scale is None
                    and not self.gpu_broken)

    def gl_resend(self):
        """The card lacks this layer's lasting data (pulses: the line pieces): send it with the next frame."""

    def gpu_changed(self):
        """The plot's viewport changed (GPU box): pictures start again, the card may be tried again."""
        self.gpu_broken = False
        self._clear()

    def _gl_frame(self):
        """GLFrame for the current view and size (like _picture, without a picture in memory)."""
        dpr = self.pixel_scale()
        size = self.vb.size()
        w, h = int(math.ceil(size.width() * dpr)), int(math.ceil(size.height() * dpr))
        if w < 2 or h < 2:
            return None
        view = self.canvas.view()
        key = (view, w, h)
        if key != self._view_key:
            self._view_key, self._view = key, view
            (x0, x1), (y0, y1) = view
            self._rect = QRectF(x0, y0, x1 - x0, y1 - y0)
            self._fresh = True
        if len(self._gl_ops) > 60:                       # never painted meanwhile: start again
            self._gl_ops[:] = [("clear",)]
        return GLFrame(w, h, self._gl_ops)

    def _corners_on_viewport(self):
        """The picture's corners (x0, y0), (x1, y0), (x0, y1), (x1, y1) in the viewport's logical pixels:
        data → scene (the item's own mapping) → viewport (the view's transform), independent of the screen
        scale."""
        r = self._rect
        to_view = self.plot.viewportTransform()
        out = []
        for x, y in ((r.left(), r.top()), (r.right(), r.top()), (r.left(), r.bottom()), (r.right(), r.bottom())):
            p = to_view.map(self.trail.mapToScene(QPointF(x, y)))
            out.append((p.x(), p.y()))
        return out

    def paint_gl(self, painter, viewport):
        """The picture on the graphics card: the recorded steps, then onto the plot (inside the plot's paint,
        the context current). If the card cannot do it, the processor draws from the next frame on."""
        ops, self._gl_ops = self._gl_ops, []
        if self._view_key is None:
            return
        _view, w, h = self._view_key
        painter.beginNativePainting()
        try:
            anim = viewport.animation()
            if not anim.ensure():
                raise RuntimeError(anim.error)
            t = anim.target(self.gl_name, (w, h), self._view, self.KEEP_PICTURE)
            for op in ops:
                if op[0] == "clear":
                    anim.clear(self.gl_name)
                elif op[0] == "fade":
                    anim.fade(t, op[1])
                elif op[0] == "segs":
                    anim.segments(t, self._palette, op[2], segs=op[1], keep_max=op[3])
                elif op[0] == "pulses":
                    _k, segs, serial, phase, length, radius = op
                    if getattr(t, "serial", None) != serial:
                        if segs is None:                  # (a new context: the pieces again next frame)
                            self.gl_resend()
                            continue
                        anim.upload(t, segs)
                        t.serial = serial
                    anim.segments(t, self._palette, radius, pulse=(phase, length), keep_max=True)
            anim.present(t, self._corners_on_viewport(), viewport)
        except Exception:                                 # noqa: BLE001 - the processor takes over
            import logging
            logging.getLogger("pflab").exception("animation on the graphics card failed: the processor draws it")
            self.gpu_broken = True
            self._view_key = None
        finally:
            painter.endNativePainting()

    def _colors(self):
        """Speed scale (0 … a round value ≈ 2 × the typical speed of the view) and its pens."""
        if self.theme is None:
            return
        v_typ = self.typical()
        self._top = nice_top(2.0 * v_typ) if v_typ > 0 else 1.0
        stops = self.theme["particles"]
        dpr = self.pixel_scale()
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
