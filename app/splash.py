"""
splash.py — the loading screen shown while the program starts (main.py): the wooden header with the logo,
what is being done ("Compiling the flow kernels…"), what was found about the computer, a progress bar.

The first start (or after an update / on a new computer) takes ~15–25 s: the compiled kernels (Numba) are
made for this processor and the graphics card is checked once; later starts reuse both and the screen is
gone in about the time the program needs to load (1–2 s). Only on a first start (main.py asks
startup.is_first_start) a box right above the bar says so, with the seconds so far.

Work that takes long runs in a thread (run()); meanwhile the screen keeps painting, the bar creeping on.
Light module: PySide6 and the theme only (it is shown before pyqtgraph / Numba are imported).
"""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from app_info import APP_VERSION

from .chrome.header import draw_logo
from .chrome.style import color, font
from .theme import LIGHT

SIZE = (580, 400)
PLANK_H = 70
GRID = 24
SLOW_S = 1.5                     # a step longer than this: it is a first start after all, say so
FIRST_TITLE = "First start on this computer"
FIRST_NOTE = ("Preparing the fast engine for this processor (about 15–30 s).",
              "Only this once: later starts take a few seconds.")


class LoadingScreen(QWidget):
    def __init__(self, theme: dict = LIGHT, first_start: bool = False):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setFixedSize(*SIZE)
        self.t = theme
        self.step = "Starting…"
        self.fraction = 0.0                  # shown bar 0 … 1
        self.target = 0.0                    # where the bar is creeping to (a running step's end)
        self.lines: list[str] = []
        self.first = bool(first_start)       # the box above the bar: it takes a while, only this once
        self.t0 = time.perf_counter()
        self._title = font("mono", 15, caps=True, spacing_pct=112)
        self._ver = font("mono", 9)
        self._step = font("heading", 13)
        self._small = font("mono", 8.5)
        self._note_head = font("heading", 10.5, caps=True, spacing_pct=106)
        self._center()

    def _center(self):
        scr = QGuiApplication.primaryScreen()
        if scr is not None:
            g = scr.availableGeometry()
            self.move(g.center().x() - SIZE[0] // 2, g.center().y() - SIZE[1] // 2)

    # ------------------------------------------------------------------ progress
    def set_step(self, text: str, fraction: float | None = None):
        self.step = text
        if fraction is not None:
            self.fraction = max(self.fraction, min(1.0, fraction))
            self.target = self.fraction
        self.pump()

    def add_line(self, text: str):
        self.lines.append(text)
        self.pump()

    def pump(self):
        self.update()
        QApplication.processEvents()

    def run(self, fn, label: str, start: float, end: float):
        """fn() in a thread while the bar creeps from start towards end; returns fn's result (its exception
        is raised here)."""
        self.set_step(label, start)
        self.target = end
        box = {}

        def work():
            try:
                box["result"] = fn()
            except BaseException as exc:            # noqa: BLE001 - raised again in the GUI thread
                box["error"] = exc

        th = threading.Thread(target=work, name="loading", daemon=True)
        th.start()
        t_start = time.perf_counter()
        while th.is_alive():
            if not self.first and time.perf_counter() - t_start > SLOW_S:
                self.first = True                   # (compiling after all, e.g. a changed cache)
            # ease towards (not up to) the end: it never looks finished before it is
            self.fraction += (self.target - self.fraction) * 0.02
            self.pump()
            th.join(0.03)
        self.fraction = max(self.fraction, end)
        self.pump()
        if "error" in box:
            raise box["error"]
        return box.get("result")

    # ------------------------------------------------------------------ drawing
    def paintEvent(self, _e):
        t = self.t
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        W, H = self.width(), self.height()
        ink = color(t["ink"])
        # paper with the drafting grid
        p.fillRect(self.rect(), color(t["window_bg"]))
        p.setPen(QPen(color(t["paper_grid"]), 1))
        for x in range(0, W, GRID):
            p.drawLine(x, PLANK_H, x, H)
        for y in range(PLANK_H, H, GRID):
            p.drawLine(0, y, W, y)
        # the wooden header: logo, name, version
        p.fillRect(QRectF(0, 0, W, PLANK_H), color(t["plank"]))
        p.fillRect(QRectF(0, PLANK_H - 3, W, 3), color(t["plank_edge"]))
        draw_logo(p, QRectF(22, 15, 40, 40), t)
        p.setPen(color(t["plank_text"]))
        p.setFont(self._title)
        p.drawText(QPointF(78, 42), "Potential Flow Lab")
        p.setFont(self._ver)
        p.setPen(color(t["plank_text_muted"]))
        p.drawText(QRectF(0, 26, W - 22, 20), Qt.AlignRight | Qt.AlignVCenter, f"REV {APP_VERSION}")
        # what is being done
        dots = "." * (1 + int((time.perf_counter() - self.t0) * 2.5) % 3)
        p.setPen(ink)
        p.setFont(self._step)
        step = self.step[:-1] + dots if self.step.endswith("…") else self.step
        p.drawText(QPointF(30, PLANK_H + 44), step)
        # what was found about the computer
        p.setFont(self._small)
        p.setPen(color(t["text_muted"]))
        y = PLANK_H + 74
        for line in self.lines[-6:]:
            p.drawText(QRectF(30, y - 13, W - 60, 18), Qt.AlignLeft | Qt.AlignVCenter,
                       p.fontMetrics().elidedText(line, Qt.ElideRight, W - 60))
            y += 19
        # first start: a box right above the bar — this takes a while, only once
        if self.first:
            box = QRectF(30, H - 140, W - 60, 70)
            p.setRenderHint(QPainter.Antialiasing, False)
            p.fillRect(box, color(t["accent_soft"]))
            p.fillRect(QRectF(box.left(), box.top(), 5, box.height()), color(t["accent_strong"]))
            p.setPen(QPen(ink, 1))
            p.drawRect(box)
            p.setPen(ink)
            p.setFont(self._note_head)
            p.drawText(QRectF(box.left() + 16, box.top() + 6, box.width() - 90, 20), Qt.AlignLeft | Qt.AlignVCenter,
                       FIRST_TITLE)
            p.setFont(self._small)
            secs = int(time.perf_counter() - self.t0)
            p.drawText(QRectF(box.left(), box.top() + 6, box.width() - 12, 20), Qt.AlignRight | Qt.AlignVCenter,
                       f"{secs} s")
            p.setPen(color(t["text_muted"]))
            for k, line in enumerate(FIRST_NOTE):
                p.drawText(QRectF(box.left() + 16, box.top() + 27 + 18 * k, box.width() - 28, 18),
                           Qt.AlignLeft | Qt.AlignVCenter, p.fontMetrics().elidedText(line, Qt.ElideRight,
                                                                                      int(box.width() - 28)))
        # progress bar: an ink frame, filled with the wood colour
        bar = QRectF(30, H - 58, W - 60, 16)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.fillRect(bar, color(t["panel_bg"]))
        p.fillRect(QRectF(bar.left(), bar.top(), bar.width() * max(0.0, min(1.0, self.fraction)), bar.height()),
                   color(t["accent_strong"]))
        p.setPen(QPen(ink, 2))
        p.drawRect(bar)
        p.setPen(QPen(ink, 2))
        p.drawRect(QRectF(1, 1, W - 2, H - 2))                            # the card's frame
        p.end()
