"""
gpu_panel.py — the "Graphics card" side panel, shown while the plot is drawn by the graphics card (the GPU
box in the header): which card draws, frames per second (live), the frame rate limit of the animations.
A laptop whose program runs on the power-saving card gets a note with a button to switch
(MainWindow.offer_strong_card, app/window/graphics.py).
"""
from __future__ import annotations

import html
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                               QWidget)

from . import gpu
from .chrome import button_font, font, themed_combo

REFRESH_MS = 500


class GpuPanel(QWidget):
    cap_changed = Signal(str)                 # gpu.FPS_CAPS key
    switch_requested = Signal()               # "Use <strong card>…"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DockBody")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 10)
        lay.setSpacing(2)

        self.card = QLabel("—")                   # which card draws
        self.card.setWordWrap(True)
        self.card.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.detail = QLabel("")
        self.detail.setObjectName("LayerNote")
        self.detail.setWordWrap(True)
        lay.addSpacing(6)
        lay.addWidget(self.card)
        lay.addWidget(self.detail)
        self.weak_note = QLabel("")                # a laptop on its power-saving card: the faster one
        self.weak_note.setObjectName("LayerNote")
        self.weak_note.setWordWrap(True)
        self.weak_note.setTextFormat(Qt.RichText)
        self.btn_switch = QPushButton("Use the faster card…")
        self.btn_switch.setFont(button_font())
        self.btn_switch.setCursor(Qt.PointingHandCursor)
        self.btn_switch.clicked.connect(self.switch_requested)
        for w in (self.weak_note, self.btn_switch):
            w.setVisible(False)
            lay.addWidget(w)
        lay.addSpacing(6)
        row = QHBoxLayout()                        # frames per second, live
        row.setSpacing(10)
        self.fps = QLabel("—")
        self.fps.setFont(font("mono", 17, QFont.DemiBold))
        self.fps_note = QLabel("")
        self.fps_note.setObjectName("LayerNote")
        self.fps_note.setWordWrap(True)
        row.addWidget(self.fps)
        row.addWidget(self.fps_note, 1)
        lay.addLayout(row)
        f = QFormLayout()                          # how often the animations draw
        self.cap = themed_combo(QComboBox())
        self.cap.setToolTip("How often the animations (Particles, Pulses) draw a new frame")
        for key, text in gpu.FPS_CAPS:
            self.cap.addItem(text, key)
        self.cap.currentIndexChanged.connect(lambda _i: self.cap_changed.emit(self.cap.currentData()))
        f.addRow("Frame rate", self.cap)
        lay.addLayout(f)
        self.cap_note = QLabel("")
        self.cap_note.setObjectName("LayerNote")
        self.cap_note.setWordWrap(True)
        self.cap_note.setVisible(False)
        lay.addWidget(self.cap_note)
        lay.addStretch(1)

        self.meter = None                     # FrameMeter of the plot (set by the window)
        self.screen_hz = 60.0
        self.timer = QTimer(self)
        self.timer.setInterval(REFRESH_MS)
        self.timer.timeout.connect(self.refresh)

    # ------------------------------------------------------------------ filled by the window
    def set_card(self, info: dict | None, weak: dict | None = None):
        """What draws (PlotGLViewport.info) and, on a laptop running on its power-saving card, the faster one."""
        if not info:
            self.card.setText("starting…")
            self.detail.setText("")
        else:
            self.card.setText(info.get("renderer") or "unknown graphics card")
            version = (info.get("version") or "").split(" ")[0]
            smooth = f" · {info['samples']}× smoothing" if info.get("samples") else " · no smoothing"
            self.detail.setText(f"OpenGL {version}{smooth}")
        self.weak_note.setVisible(weak is not None)
        self.btn_switch.setVisible(weak is not None)
        if weak is not None:
            self.weak_note.setText(f"This computer also has <b>{html.escape(weak['name'])}</b>, which is faster.")
            self.btn_switch.setText(f"Use {short_name(weak['name'])}…")

    def set_cap(self, cap: str):
        i = self.cap.findData(cap)
        if i >= 0 and i != self.cap.currentIndex():
            self.cap.blockSignals(True)
            self.cap.setCurrentIndex(i)
            self.cap.blockSignals(False)
        self._cap_texts()

    def set_screen_hz(self, hz: float):
        self.screen_hz = float(hz) if hz and hz > 1 else 60.0
        self._cap_texts()

    def _cap_texts(self):
        i = self.cap.findData("screen")
        self.cap.setItemText(i, f"Match screen ({self.screen_hz:.0f} Hz)")
        cap = self.cap.currentData()
        if cap != "screen" and float(cap) > self.screen_hz + 0.5:
            self.cap_note.setText(f"Your screen shows at most {self.screen_hz:.0f} frames per second; "
                                  "more are not visible.")
            self.cap_note.setVisible(True)
        else:
            self.cap_note.setVisible(False)

    # ------------------------------------------------------------------ live
    def showEvent(self, e):
        super().showEvent(e)
        self.timer.start()
        self.refresh()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    def refresh(self):
        m = self.meter
        if m is None:
            return
        fps = m.fps(time.perf_counter())
        paint = m.paint_median()
        if fps < 1.5:
            self.fps.setText("— fps")
            self.fps_note.setText("still: the plot is drawn only when something changes")
        else:
            self.fps.setText(f"{fps:.0f} fps")
            self.fps_note.setText(f"a frame takes {paint:.1f} ms to draw" if paint is not None else "")


def short_name(name: str) -> str:
    """"NVIDIA GeForce RTX 3050 Ti Laptop GPU" -> "NVIDIA"; the vendor is the short name on a button."""
    from .hardware import vendor_of
    v = vendor_of(name)
    return {"nvidia": "NVIDIA", "amd": "AMD", "intel": "Intel"}.get(v, name)
