"""
streamline_layer.py — the streamlines with their direction arrows, computed in the background.

Streamlines come from a StreamlineCache (physics/streamlines.py): lines already computed never move,
a margin around the view is computed in advance (panning shows lines that are already there), and
zooming changes the line spacing in steps of 2.

The computation runs in a background thread, so the window never freezes. While it runs, new view
requests are collected and only the newest is computed next. A change of the scene or the density
starts a new cache and cancels the running computation (generation number); results of old
generations are thrown away. `recompute()` is the synchronous version (tests and scripts).

Live update while dragging (canvas.live_drag): every move of a dragged element asks for a preview —
the lines of the visible region only, at the current spacing level, without stagnation points — in the
same thread; while one runs, only the newest position is kept for the next. On release the scene
changes and everything is computed as usual (on Esc the lines of the old scene come back).

Every result also carries the stagnation points and dividing streamlines; the canvas hands them on
(PlotCanvas.streamlines_drawn).
"""
import time

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor

from physics.streamlines import FADE_LEVELS, Cancelled, StreamlineCache, fade_piece_boxes

from ..theme import LAYOUT
from .arrows_item import ArrowsItem
from .layer import PlotLayer
from .scaled_curve import ScaledCurve


class _ResultSignal(QObject):
    """Carries background results to the GUI thread (queued connection)."""
    done = Signal(int, object, float)        # generation, (StreamlineSet, level) / None / exception, ms
    partial = Signal(int, object)            # generation, (StreamlineSet, level) of the visible part
    preview = Signal(int, object, float)     # generation, StreamlineSet of a dragged scene / None / exc., ms


class _Job(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.setAutoDelete(True)

    def run(self):
        self.fn()


ANIMATED_ALPHA = (0.35, 0.45)                 # streamline opacity under the animation (particles, pulses)


class StreamlineLayer(PlotLayer):
    FADES_WHILE_DRAGGING = True
    CULL_MARGIN = 0.3                         # lines handed to the plot: the view + 30 % on every side

    def __init__(self, plot, vb):
        super().__init__(plot, vb)
        # one curve item per opacity level (0 = full opacity, then the steps of the fading line ends);
        # lines are separated by NaN inside each item, drawn as separate segments (~7× faster)
        self.line_items = []
        for _ in range(FADE_LEVELS + 1):
            item = ScaledCurve(connect="finite")
            item.setSegmentedLineMode("on")
            self.line_items.append(self.add_item(item, 1))
        self.arrow_item = self.add_item(ArrowsItem(LAYOUT["arrow_size_px"]), 2)

        self.background = True                    # False: compute synchronously (tests, scripts)
        self.generation = 0
        self.cache = None                         # StreamlineCache of the current scene and density
        self.busy = False                         # a job is running
        self.pending = False                      # a newer view was requested meanwhile
        self._force = True                        # the next result is drawn even if the lines are the same
        self.drawn_domain = None                  # region filled by the drawn lines (x0, x1, y0, y1)
        self.drawn_level = None
        self._pieces = None                       # per opacity level: (pieces, bounding boxes)
        self._arrows = np.zeros((0, 3))
        self.cull_rect = None                     # lines / arrows handed to the plot meet this rect
        self._first_job = True                    # the very first job may compile the kernel
        self._preview_wanted = False              # live drag: a newer element position waits
        self._preview_shown = False               # live drag: the drawn lines belong to the dragged scene
        self._job_level = None                    # spacing level of the running job (None: no job)
        self._wanted_level = None                 # spacing level the newest view needs
        self.preview_ms = []                      # computation time of every preview drawn (measurements)
        self._pool = QThreadPool(plot)            # Qt objects owned by the plot widget (deleted with it)
        self._pool.setMaxThreadCount(1)
        self._results = _ResultSignal(plot)
        self._results.done.connect(self._on_result)
        self._results.partial.connect(self._on_partial)
        self._results.preview.connect(self._on_preview)

    def items(self):
        return self.line_items + [self.arrow_item]

    # ------------------------------------------------------------------ hooks
    def apply_theme(self, theme):
        super().apply_theme(theme)
        self.set_line_pens()
        self.arrow_item.setColor(theme["streamline"])
        self.redraw()

    def scene_changed(self):
        self.restart()

    def view_changed(self):
        if self._needs_cull():
            self._cull()
        self.request()

    def fades_while_dragging(self) -> bool:
        return not self.canvas.live_drag

    def drag_moved(self):
        if not self.canvas.live_drag:
            return
        self._preview_wanted = True
        if not self.busy:
            self._start_preview()

    def drag_finished(self):
        self._preview_wanted = False
        if self._preview_shown:                       # back to the lines of the scene (Esc), or the
            self._preview_shown = False               # new scene follows at once (released)
            self.redraw()

    def visibility_changed(self):
        on = self.canvas.layers["streamlines"]
        for item in self.line_items:
            item.setVisible(on)
        self.arrow_item.setVisible(on and not self.canvas.animated)      # particles show the direction

    def shutdown(self):
        """Cancel and wait for the background computation."""
        self.generation += 1
        self._pool.waitForDone(10000)

    # ------------------------------------------------------------------ settings
    def set_line_pens(self):
        """Pens of the opacity levels; faint while animating (the particles are the main thing then)."""
        n = len(self.line_items)
        faint = ANIMATED_ALPHA[self.canvas.view_mode == "pulses"] if self.canvas.animated else 1.0
        for k, item in enumerate(self.line_items):
            color = QColor(self.theme["streamline"])
            color.setAlphaF(color.alphaF() * faint * (n - k) / n)
            item.setPen(pg.mkPen(color, width=self.canvas.settings.line_width))

    def restart(self):
        """Scene or density changed: a new cache, the running computation is cancelled."""
        self.generation += 1
        self.cache = StreamlineCache(tuple(self.canvas.elements), self.canvas.settings.density)
        self._force = True
        self.request()

    def redraw(self):
        """Same lines, drawn again (arrows or colors changed)."""
        self._force = True
        self.request()

    # ------------------------------------------------------------------ computation
    def _arrow_density(self) -> float:
        s = self.canvas.settings
        return s.arrow_density if s.show_arrows else 0.0

    def request(self):
        """Bring the streamlines up to date: in the background thread (normal use) or synchronously."""
        if self.cache is None:
            self.restart()
            return
        if not self.background:
            self.recompute()
            return
        if self.busy:
            self.pending = True                   # computed when the running job is finished
            if self._job_level is not None:       # (zoomed on to another spacing level: the running job
                self._wanted_level = self.cache._choose_level(self.canvas.view(), self._job_level)
            return                                #  is given up, see _start_job)
        self._start_job()

    def _start_job(self):
        if self._first_job:
            self._first_job = False
            QTimer.singleShot(2500, self.plot, self._first_job_slow)    # cached engine + first picture: < 1 s
        self.busy, self.pending = True, False
        gen, cache, view = self.generation, self.cache, self.canvas.view()
        arrows = self._arrow_density()
        force, self._force = self._force, False
        level = self._job_level = self._wanted_level = cache._choose_level(view, cache.level)

        def cancelled():
            # a newer scene, or the view has gone on to another spacing level meanwhile (a fast wheel
            # zoom): lines of a level nobody looks at any more would only delay the ones of the newest view
            return gen != self.generation or (self.pending and self._wanted_level != level)

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
        if self.busy and self.drawn_domain is None:
            self.canvas.message.emit("Preparing the fast streamline engine (only after installing / updating)…")

    def _on_partial(self, gen, payload):
        if gen == self.generation:
            self._draw(*payload, None)

    def _on_result(self, gen, payload, ms):
        self.busy = False
        self._job_level = None
        current = gen == self.generation
        if current and isinstance(payload, tuple) and payload[0] is not None:
            self._draw(*payload, ms)
        self._next_job(not current)
        if isinstance(payload, BaseException):
            raise payload

    def _next_job(self, stale: bool):
        if self._preview_wanted and self.canvas.is_dragging():
            self._start_preview()                        # the newest position of a dragged element
        elif self.pending or stale:
            self._start_job()                            # newer view or newer scene

    # ------------------------------------------------------------------ live drag (preview)
    def _start_preview(self):
        self.busy, self._preview_wanted = True, False
        gen, view, level = self.generation, self.canvas.view(), self.drawn_level
        elements, density = tuple(self.canvas.shown_elements()), self.canvas.settings.density
        arrows = self._arrow_density()

        def work():
            t0 = time.perf_counter()
            try:
                cache = StreamlineCache(elements, density)
                cache.level, cache.with_features = level, False     # same spacing as the drawn lines
                result = cache.update(view, arrows, force=True, margin=False,
                                      cancelled=lambda: gen != self.generation)
            except Cancelled:
                result = None
            except Exception as exc:                     # report bugs in the GUI thread
                result = exc
            self._results.preview.emit(gen, result, (time.perf_counter() - t0) * 1000.0)

        if self.background:
            self._pool.start(_Job(work))
        else:
            work()

    def _on_preview(self, gen, result, ms):
        self.busy = False
        if gen == self.generation and self.canvas.is_dragging() and result is not None \
                and not isinstance(result, BaseException):
            self._show(result)
            self._preview_shown = True
            self.preview_ms.append(ms)
        self._next_job(gen != self.generation)
        if isinstance(result, BaseException):
            raise result

    def recompute(self):
        """Synchronous computation (cancels a running background one)."""
        self.generation += 1                             # results of running jobs are not drawn
        self._pool.waitForDone(10000)
        self.busy = self.pending = False
        self.cache = StreamlineCache(tuple(self.canvas.elements), self.canvas.settings.density)
        t0 = time.perf_counter()
        result = self.cache.update(self.canvas.view(), self._arrow_density(), force=True)
        self._force = False
        self._draw(result, self.cache.level, (time.perf_counter() - t0) * 1000.0)

    def wait_idle(self, msecs: int = 10000) -> bool:
        """Wait until the background thread is idle (results still arrive via the event loop)."""
        return self._pool.waitForDone(msecs)

    def covers_view(self) -> bool:
        """True if the drawn streamlines fill the visible region at the right spacing level."""
        if self.drawn_domain is None or self.cache is None:
            return False
        view = self.canvas.view()
        (x0, x1), (y0, y1) = view
        a0, a1, b0, b1 = self.drawn_domain
        inside = a0 <= x0 and x1 <= a1 and b0 <= y0 and y1 <= b1
        return inside and self.cache._choose_level(view, self.drawn_level) == self.drawn_level

    # ------------------------------------------------------------------ drawing
    def _draw(self, result, level, ms):
        """Draw a StreamlineSet. ms = None for a partial result (the visible part; more follows)."""
        self.drawn_domain, self.drawn_level = result.domain, level
        self._preview_shown = False
        self._show(result)
        self.canvas.streamlines_drawn(result, ms)

    def _show(self, result):
        """Hand the lines and arrows of a result to the plot."""
        self._pieces = fade_piece_boxes(result.lines, result.tapers, result.separation)
        self._arrows = np.asarray(result.arrows, dtype=float).reshape(-1, 3)
        self._cull()
        self.arrow_item.setColor(self.theme["streamline"])
        self.canvas.lines_shown(result)

    def _cull(self):
        """Hand to the plot only the line pieces and arrows near the view (the computed region is
        about 4× the view; drawing everything would cost 4× the time). Redone when the view leaves
        the rectangle or the zoom changes."""
        if self._pieces is None:
            return
        (x0, x1), (y0, y1) = self.canvas.view()
        W, H = x1 - x0, y1 - y0
        m = self.CULL_MARGIN
        r = (x0 - m * W, x1 + m * W, y0 - m * H, y1 + m * H)
        self.cull_rect = (*r, W)
        gap = np.array([[np.nan, np.nan]])
        for item, (parts, boxes) in zip(self.line_items, self._pieces):
            keep = np.nonzero((boxes[:, 1] >= r[0]) & (boxes[:, 0] <= r[1]) &
                              (boxes[:, 3] >= r[2]) & (boxes[:, 2] <= r[3]))[0] if boxes.size else []
            if len(keep):
                xy = np.vstack([x for i in keep for x in (parts[i], gap)])
                item.setData(xy[:, 0], xy[:, 1])
            else:
                item.setData([], [])
        a = self._arrows
        inside = (a[:, 0] >= r[0]) & (a[:, 0] <= r[1]) & (a[:, 1] >= r[2]) & (a[:, 1] <= r[3])
        self.arrow_item.setData(a[inside])

    def _needs_cull(self) -> bool:
        if self.cull_rect is None:
            return self._pieces is not None
        (x0, x1), (y0, y1) = self.canvas.view()
        a0, a1, b0, b1, w = self.cull_rect
        return not (a0 <= x0 and x1 <= a1 and b0 <= y0 and y1 <= b1) or not 0.8 < (x1 - x0) / w < 1.25
