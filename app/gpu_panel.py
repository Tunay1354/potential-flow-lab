"""
gpu_panel.py — the "Graphics card" panel: a drop-down card hanging from the small arrow beside the GPU box in
the header (a notch points at the arrow; the program's "drafting card" look: ink frame, hard shadow, like the
beaver's bubble), over whatever is below it; the same arrow closes it (app/window/graphics.py places it). No
side panel: the layout stays as the user left it.

It works with and without the graphics card:
  - which card draws (or "the processor"), frames per second (live) and how long a frame takes to draw
  - Frame rate of the animations (remembered for each mode)
  - WITH THE GRAPHICS CARD (greyed while the processor draws): Higher limits in Plot settings, and the
    limits themselves; on a laptop running on its power-saving card, the button for the faster one
"""
from __future__ import annotations

import html
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout)

from . import gpu
from .chrome import button_font, font, heading_font, themed_combo

REFRESH_MS = 500
WIDTH = 330                                  # px, with the shadow
NOTCH = 9                                    # px: the notch pointing up at the arrow
SHADOW = 5                                   # px: the hard shadow right and below
FRAME = 2                                    # px: the ink frame


class GpuPanel(QFrame):
    cap_changed = Signal(str)                 # gpu.FPS_CAPS key
    switch_requested = Signal()               # "Use <faster card>…"
    higher_changed = Signal(bool)             # Higher limits ticked / unticked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GpuOverlay")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.theme = None
        self.on_card = False
        self.notch_x = WIDTH - 40                # where the notch is (the window sets it under the arrow)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 12 + NOTCH, 18 + SHADOW, 14 + SHADOW)
        lay.setSpacing(4)

        head = self.head = QLabel("GRAPHICS CARD")
        head.setObjectName("GpuHead")
        head.setFont(heading_font(11))
        lay.addWidget(head)
        lay.addSpacing(10)                     # (the rule under the heading is painted)

        self.mode = QLabel("")                 # who draws: the card / the processor
        self.mode.setObjectName("GpuMode")
        self.mode.setFont(font("mono", 9, QFont.DemiBold, caps=True, spacing_pct=106))
        self.card = QLabel("—")
        self.card.setWordWrap(True)
        self.card.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.detail = QLabel("")
        self.detail.setObjectName("Muted")
        self.detail.setWordWrap(True)
        for w in (self.mode, self.card, self.detail):
            lay.addWidget(w)
        lay.addSpacing(8)

        row = QHBoxLayout()                    # frames per second, live
        row.setSpacing(10)
        self.fps = QLabel("—")
        self.fps.setFont(font("mono", 17, QFont.DemiBold))
        self.fps_note = QLabel("")
        self.fps_note.setObjectName("Muted")
        self.fps_note.setWordWrap(True)
        row.addWidget(self.fps)
        row.addWidget(self.fps_note, 1)
        lay.addLayout(row)
        f = QFormLayout()
        f.setContentsMargins(0, 6, 0, 0)
        self.cap = themed_combo(QComboBox())
        self.cap.setToolTip("How often the animations (Particles, Pulses) draw a new frame")
        for key, text in gpu.FPS_CAPS:
            self.cap.addItem(text, key)
        self.cap.currentIndexChanged.connect(lambda _i: self.cap_changed.emit(self.cap.currentData()))
        f.addRow("Frame rate", self.cap)
        lay.addLayout(f)
        self.cap_note = QLabel("")
        self.cap_note.setObjectName("Muted")
        self.cap_note.setWordWrap(True)
        self.cap_note.setVisible(False)
        lay.addWidget(self.cap_note)

        lay.addSpacing(12)
        self.gpu_only = QFrame()               # greyed while the processor draws
        self.gpu_only.setObjectName("GpuOnly")
        g = QVBoxLayout(self.gpu_only)
        g.setContentsMargins(10, 8, 10, 10)
        g.setSpacing(4)
        sub = QLabel("WITH THE GRAPHICS CARD")
        sub.setObjectName("GpuSub")
        sub.setFont(heading_font(9.5))
        g.addWidget(sub)
        self.higher = QCheckBox("Higher limits in Plot settings")
        self.higher.setToolTip("The sliders reach further (more lines, particles, longer trails …).\n"
                               "A small mark on a slider shows the processor's limit.")
        self.higher.setChecked(gpu.higher_limits())
        self.higher.toggled.connect(self.higher_changed)
        g.addWidget(self.higher)
        self.limits = QLabel("")               # what the sliders reach with the card
        self.limits.setObjectName("Muted")
        self.limits.setTextFormat(Qt.RichText)
        self.limits.setWordWrap(True)
        g.addWidget(self.limits)
        self.weak_note = QLabel("")            # a laptop on its power-saving card: the faster one
        self.weak_note.setObjectName("Muted")
        self.weak_note.setWordWrap(True)
        self.weak_note.setTextFormat(Qt.RichText)
        self.btn_switch = QPushButton("Use the faster card…")
        self.btn_switch.setFont(button_font())
        self.btn_switch.setCursor(Qt.PointingHandCursor)
        self.btn_switch.clicked.connect(self.switch_requested)
        for w in (self.weak_note, self.btn_switch):
            w.setVisible(False)
            g.addWidget(w)
        lay.addWidget(self.gpu_only)
        self.off_note = QLabel("Tick GPU in the header to draw with the graphics card: the program restarts "
                               "in a few seconds, your scene stays as it is.")
        self.off_note.setObjectName("Muted")
        self.off_note.setWordWrap(True)
        lay.addSpacing(6)
        lay.addWidget(self.off_note)

        self.meter = None                     # FrameMeter of the plot (set by the window)
        self.screen_hz = 60.0
        self.timer = QTimer(self)
        self.timer.setInterval(REFRESH_MS)
        self.timer.timeout.connect(self.refresh)
        self.setFixedWidth(WIDTH)
        self.hide()

    # ------------------------------------------------------------------ look
    def apply_theme(self, theme: dict):
        self.theme = t = theme
        self.setStyleSheet(f"""
            QFrame#GpuOverlay {{ background: transparent; border: none; }}
            QFrame#GpuOverlay QLabel {{ background: transparent; }}
            QLabel#GpuMode {{ color: {t['accent']}; }}
            QFrame#GpuOnly {{ background: {t['window_bg']}; border: 1px solid {t['border_soft']}; }}
            QFrame#GpuOnly:disabled QLabel, QFrame#GpuOnly QLabel:disabled {{ color: {t['text_disabled']}; }}
        """)
        self.update()

    def card_rect(self):
        from PySide6.QtCore import QRectF
        return QRectF(FRAME / 2, NOTCH + FRAME / 2, self.width() - SHADOW - FRAME, self.height() - NOTCH - SHADOW - FRAME)

    def paintEvent(self, e):
        if self.theme is None:
            return
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPainterPath
        t = self.theme
        ink, paper = QColor(t["ink"]), QColor(t["panel_bg"])
        shadow = QColor(t["ink"])
        shadow.setAlpha(46)
        r = self.card_rect()
        nx = min(max(self.notch_x, r.left() + 18), r.right() - 18)
        p = QPainter(self)
        p.fillRect(r.translated(SHADOW, SHADOW), shadow)                  # the hard shadow
        path = QPainterPath()                                             # the card with its notch
        path.moveTo(r.topLeft())
        path.lineTo(QPointF(nx - NOTCH, r.top()))
        path.lineTo(QPointF(nx, r.top() - NOTCH + 1))
        path.lineTo(QPointF(nx + NOTCH, r.top()))
        path.lineTo(r.topRight())
        path.lineTo(r.bottomRight())
        path.lineTo(r.bottomLeft())
        path.closeSubpath()
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(ink, FRAME, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
        p.setBrush(paper)
        p.drawPath(path)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setPen(QPen(ink, 1.5))                                          # the rule under the heading
        y = self.head.geometry().bottom() + 5.5
        p.drawLine(QPointF(18, y), QPointF(r.right() - 14, y))
        p.end()


    # ------------------------------------------------------------------ filled by the window
    def set_mode(self, on_card: bool, possible: bool = True, why: str = ""):
        """Who draws now; the GPU-only part usable only with the card."""
        self.on_card = bool(on_card)
        self.mode.setText("The graphics card draws" if on_card else "The processor draws")
        if not on_card:
            self.card.setText("No graphics card is used now.")
            self.detail.setText("" if possible else f"The graphics card cannot be used here: {why}")
        self.gpu_only.setEnabled(on_card)
        self.off_note.setVisible(not on_card and possible)
        self.adjustSize()

    def set_card(self, info: dict | None, weak: dict | None = None):
        """What draws (PlotGLViewport.info) and, on a laptop running on its power-saving card, the faster one."""
        if not info:
            self.card.setText("starting…")
            self.detail.setText("")
        else:
            self.card.setText(info.get("renderer") or "unknown graphics card")
            version = (info.get("version") or "").split(" ")[0]
            n = info.get("samples")
            smooth = "" if n is None else f" · {n}× smoothing" if n > 1 else " · no smoothing"
            self.detail.setText(f"OpenGL {version}{smooth}")
        self.weak_note.setVisible(weak is not None)
        self.btn_switch.setVisible(weak is not None)
        if weak is not None:
            self.weak_note.setText(f"This computer also has <b>{html.escape(weak['name'])}</b>, which is faster.")
            self.btn_switch.setText(f"Use {short_name(weak['name'])}…")
        self.adjustSize()

    def set_limits(self, rows: list[tuple[str, str, str]]):
        """[(setting, processor's limit, with the card)]: what Higher limits gives."""
        cells = "".join(f"<tr><td>{html.escape(a)}</td><td align='right'>&nbsp;{html.escape(b)}</td>"
                        f"<td>&nbsp;→&nbsp;</td><td><b>{html.escape(c)}</b></td></tr>" for a, b, c in rows)
        self.limits.setText(f"<table cellspacing='0' cellpadding='1'>{cells}</table>")

    def set_particles_max(self, n: int):
        self.particles_max = n

    def set_higher(self, on: bool):
        self.higher.blockSignals(True)
        self.higher.setChecked(bool(on))
        self.higher.blockSignals(False)

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
