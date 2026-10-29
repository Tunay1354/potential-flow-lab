"""
gl_viewport.py — the plot drawn by the graphics card, and the frame counter of the plot.

PlotGLViewport: the plot's viewport (the widget the plot paints on) as an OpenGL surface. The plot items
paint exactly as before (QPainter); Qt's OpenGL paint engine turns the lines into triangles that the
graphics card fills, smoothed by multisampling (MSAA_SAMPLES). PlotCanvas.set_gpu switches between this and
the normal viewport (a QWidget, drawn by the processor) at any time; exports never use it (they paint
into their own pictures, identical with and without the graphics card).

FrameMeter: frames shown per second and the time one frame of the plot takes to paint, for the Graphics card
panel (works for both viewports; PlotView.paintEvent feeds it).
"""
from __future__ import annotations

import logging
import time
from collections import deque

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtGui import QOpenGLContext, QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget

log = logging.getLogger("pflab")

GL_VENDOR, GL_RENDERER, GL_VERSION, GL_SAMPLES = 0x1F00, 0x1F01, 0x1F02, 0x80A9


class PlotGLViewport(QOpenGLWidget):
    """The OpenGL viewport. `ready` is emitted once the graphics context exists, with what the driver says
    ({"vendor", "renderer", "version", "samples"}); `failed` if no context could be made."""
    ready = Signal(dict)
    failed = Signal(str)

    def __init__(self, samples: int = 4, parent=None):
        super().__init__(parent)
        fmt = QSurfaceFormat()
        fmt.setSamples(int(samples))
        self.setFormat(fmt)
        self.info: dict | None = None           # (also kept: initializeGL may run before anyone listens)
        self.error: str | None = None
        self.requested_samples = int(samples)
        self.frameSwapped.connect(self._read_samples)
        self._animation = None                  # GLAnimation: the animations drawn on the card (gl_animation.py)

    def animation(self):
        """The animations' shaders and pictures in this context (made on first use; context current)."""
        if self._animation is None:
            from .gl_animation import GLAnimation
            self._animation = GLAnimation()
            ctx = self.context()
            if ctx is not None:
                ctx.aboutToBeDestroyed.connect(self._free_animation)
        return self._animation

    def _free_animation(self):
        """The context goes (the viewport is switched off / closed): its pictures and buffers with it."""
        if self._animation is not None:
            try:
                self.makeCurrent()
                self._animation.destroy()
                self.doneCurrent()
            except Exception as exc:                      # noqa: BLE001
                log.info("animation resources not freed: %s", exc)
            self._animation = None

    def initializeGL(self):
        """Called by Qt with the context current (also again if the context is made anew)."""
        try:
            ctx = self.context()
            if ctx is None or not ctx.isValid():
                self.error = "no OpenGL context"
                self.failed.emit(self.error)
                return
            f = ctx.functions()
            vendor, renderer, version = (str(f.glGetString(k) or "") for k in (GL_VENDOR, GL_RENDERER, GL_VERSION))
            # samples: known only once the widget's frame buffer exists (after the first frame, _read_samples);
            # format().samples() says 0 even when the frame buffer is multisampled
            self.info = {"vendor": vendor, "renderer": renderer, "version": version, "samples": None}
            log.info("plot drawn by OpenGL: %s | %s | %s", renderer, vendor, version)
            self.ready.emit(dict(self.info))
        except Exception as exc:                          # noqa: BLE001 - reported, never raised into Qt
            log.exception("OpenGL viewport could not start")
            self.error = f"{type(exc).__name__}: {exc}"
            self.failed.emit(self.error)

    def _read_samples(self):
        """After the first frame: how many samples per pixel the frame buffer really has (smoothing)."""
        try:
            self.frameSwapped.disconnect(self._read_samples)
        except (RuntimeError, TypeError):
            pass
        if self.info is None or not self.isValid():
            return
        try:
            self.makeCurrent()
            ctx = self.context()
            if ctx is None or QOpenGLContext.currentContext() is not ctx:      # never ask a context not current
                return
            n = int(ctx.functions().glGetIntegerv(GL_SAMPLES) or 0)
            self.doneCurrent()
        except Exception as exc:                          # noqa: BLE001
            log.info("smoothing samples not readable: %s", exc)
            return
        self.info["samples"] = n
        log.info("plot OpenGL smoothing: %d samples per pixel (asked %d)", n, self.requested_samples)
        self.ready.emit(dict(self.info))


class FrameMeter:
    """Frames per second (painted in the last second) and paint time per frame (median of the last ones)."""

    def __init__(self, window_s: float = 1.0):
        self.window_s = window_s
        self.stamps: deque = deque(maxlen=2000)
        self.paint_ms: deque = deque(maxlen=60)

    def add(self, start: float, end: float):
        self.stamps.append(end)
        self.paint_ms.append((end - start) * 1000.0)

    def fps(self, now: float | None = None) -> float:
        now = time.perf_counter() if now is None else now
        return sum(1 for t in self.stamps if 0.0 <= now - t <= self.window_s) / self.window_s

    def paint_median(self) -> float | None:
        if not self.paint_ms:
            return None
        v = sorted(self.paint_ms)
        return v[len(v) // 2]

    def clear(self):
        self.stamps.clear()
        self.paint_ms.clear()


class PlotView(pg.PlotWidget):
    """The plot widget, counting its frames (FrameMeter)."""

    def __init__(self, *args, **kwargs):
        self.meter = FrameMeter()
        super().__init__(*args, **kwargs)

    def paintEvent(self, ev):
        t = time.perf_counter()
        result = super().paintEvent(ev)
        self.meter.add(t, time.perf_counter())
        return result
