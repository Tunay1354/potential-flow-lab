"""
bubble.py — the beaver's speech bubble: a pixel-art frame (stepped corners, a staircase tail, a drop
shadow) with a pixel font, the text typed letter by letter with a blinking block cursor. Never takes the
mouse. The size is fixed by the whole text, so the bubble does not grow while it types.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter
from PySide6.QtWidgets import QWidget

CPS = 38.0                       # characters per second
HOLD_S = 1.6                     # shown this long after the last character …
HOLD_PER_CHAR_S = 0.035          # … plus this per character
READ_S, READ_PER_CHAR_S = 0.7, 0.03   # never replaced by another line before this (time to read it)
FONT_FAMILY = "Pixelify Sans"
FONT_PX = 15
PAD = 9                          # text margin inside the frame (logical px)
TAIL = 10                        # tail length (logical px)


class SpeechBubble(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.hide()
        f = QFont(FONT_FAMILY)
        f.setPixelSize(FONT_PX)
        f.setStyleStrategy(QFont.NoAntialias)
        f.setHintingPreference(QFont.PreferFullHinting)
        self.font_ = f
        self.text = ""
        self.shown = 0.0                 # characters typed so far
        self.after = 0.0                 # seconds since the last character
        self.tail = "down"               # where the tail points: down (bubble above), left / right, up
        self.colors = {"paper": QColor("#FBF7EC"), "ink": QColor("#211A12"), "shadow": QColor(33, 26, 18, 70)}
        self._lines = []
        self._box = QRectF()
        self._anchor = QPointF()
        self._offset = QPointF()

    # ------------------------------------------------------------------ text
    @property
    def active(self) -> bool:
        return bool(self.text)

    @property
    def typing(self) -> bool:
        return self.shown < len(self.text)

    def busy(self) -> bool:
        """Still typing, or typed but not yet readable (a new line would cut it off)."""
        return bool(self.text) and (self.typing or self.after < READ_S + READ_PER_CHAR_S * len(self.text))

    def set_theme(self, theme: dict):
        self.colors = {"paper": QColor(theme["panel_bg"]), "ink": QColor(theme["ink"]),
                       "shadow": QColor(0, 0, 0, 70)}
        self.update()

    def say(self, text: str, typed: bool = True):
        self.text = text
        self.shown = 0.0 if typed else float(len(text))
        self.after = 0.0
        self._lines = text.split("\n")
        fm = QFontMetricsF(self.font_)
        a = self.art()
        w = max(fm.horizontalAdvance(l) for l in self._lines) + 2 * PAD + 6
        h = fm.lineSpacing() * len(self._lines) + 2 * PAD - 2
        self._box = QRectF(0, 0, math.ceil(w / a) * a, math.ceil(h / a) * a)
        self.update()

    def clear(self):
        self.text = ""
        self.hide()

    def advance(self, dt: float):
        """Type on / count the time it stays; hides itself when done."""
        if not self.text:
            return
        if self.typing:
            self.shown = min(len(self.text), self.shown + CPS * dt)
        else:
            self.after += dt
            if self.after > HOLD_S + HOLD_PER_CHAR_S * len(self.text):
                self.clear()
                return
        self.update()

    def art(self) -> float:
        """One art pixel in logical pixels (whole device pixels)."""
        dpr = self.devicePixelRatioF() or 1.0
        return max(2, round(2 * dpr)) / dpr

    # ------------------------------------------------------------------ placement
    def place(self, anchor: QPointF, tail: str, bounds: QRectF):
        """Put the tail tip at `anchor` (parent coordinates), bubble on the other side of the tail, kept
        inside `bounds`."""
        if not self.text:
            return
        self.tail = tail
        bw, bh = self._box.width(), self._box.height()
        if tail == "down":
            x, y = anchor.x() - 22, anchor.y() - bh - TAIL
        elif tail == "up":
            x, y = anchor.x() - 22, anchor.y() + TAIL
        elif tail == "left":
            x, y = anchor.x() + TAIL, anchor.y() - bh / 2
        else:
            x, y = anchor.x() - bw - TAIL, anchor.y() - bh / 2
        x = min(max(x, bounds.left() + 2), bounds.right() - bw - 6)
        y = min(max(y, bounds.top() + 2), bounds.bottom() - bh - 6)
        m = TAIL + 6
        self._anchor = anchor - QPointF(x - m, y - m)                   # tail tip in widget coordinates
        self.setGeometry(int(x - m), int(y - m), int(bw + 2 * m), int(bh + 2 * m))
        self._offset = QPointF(m, m)
        if not self.isVisible():
            self.show()
        self.raise_()

    # ------------------------------------------------------------------ drawing
    def paintEvent(self, _e):
        if not self.text:
            return
        a = self.art()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        ink, paper, shadow = self.colors["ink"], self.colors["paper"], self.colors["shadow"]
        o = self._offset
        r = self._box.translated(o)
        x0, y0, w, h = r.x(), r.y(), r.width(), r.height()
        # drop shadow, body with stepped corners, frame
        p.fillRect(QRectF(x0 + a + a, y0 + a + a, w - a, h - a), shadow)
        p.fillRect(QRectF(x0 + a, y0, w - 2 * a, h), paper)
        p.fillRect(QRectF(x0, y0 + a, w, h - 2 * a), paper)
        for rr in (QRectF(x0 + a, y0, w - 2 * a, a), QRectF(x0 + a, y0 + h - a, w - 2 * a, a),
                   QRectF(x0, y0 + a, a, h - 2 * a), QRectF(x0 + w - a, y0 + a, a, h - 2 * a)):
            p.fillRect(rr, ink)
        self._tail(p, a, x0, y0, w, h, ink, paper)
        # text typed so far + block cursor
        p.setFont(self.font_)
        p.setPen(ink)
        fm = QFontMetricsF(self.font_)
        n = int(self.shown)
        y = y0 + PAD - 2 + fm.ascent()
        for k, line in enumerate(self._lines):
            part = line[:max(0, n)]
            p.drawText(QPointF(x0 + PAD + 1, y), part)
            if self.typing and 0 <= n <= len(line):
                cx = x0 + PAD + 1 + fm.horizontalAdvance(part) + 1
                p.fillRect(QRectF(cx, y - fm.ascent() + 2, a * 2.5, fm.ascent() - 1), ink)
            n -= len(line) + 1
            y += fm.lineSpacing()
        p.end()

    def _tail(self, p, a, x0, y0, w, h, ink, paper):
        tip = self._anchor
        steps = 4
        if self.tail in ("down", "up"):
            sgn = 1 if self.tail == "down" else -1
            base_y = y0 + h - a if sgn > 0 else y0
            bx = min(max(tip.x() - 3 * a, x0 + 2 * a), x0 + w - 6 * a)
            for k in range(steps):
                yy = base_y + sgn * k * a
                xl = bx + k * a * 0.5
                width = max(a, 3 * a - k * a * 0.5)
                p.fillRect(QRectF(round(xl / a) * a, yy, round(width / a) * a, a), paper)
                p.fillRect(QRectF(round(xl / a) * a - a, yy, a, a), ink)
                p.fillRect(QRectF(round((xl + width) / a) * a, yy, a, a), ink)
            p.fillRect(QRectF(round((bx + steps * a * 0.5) / a) * a - a, base_y + sgn * steps * a, 2 * a, a), ink)
        else:
            sgn = -1 if self.tail == "left" else 1
            ex = x0 if sgn < 0 else x0 + w - a
            cy = round((y0 + h / 2) / a) * a
            for k in range(1, steps):
                xx = ex + sgn * k * a
                half = (steps - k) * a
                p.fillRect(QRectF(xx, cy - half + a, a, 2 * half - 2 * a), paper)
                p.fillRect(QRectF(xx, cy - half, a, a), ink)
                p.fillRect(QRectF(xx, cy + half - a, a, a), ink)
            p.fillRect(QRectF(ex + sgn * steps * a, cy - a, a, a), ink)
