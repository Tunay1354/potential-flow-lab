"""
bubble.py — the beaver's speech bubble: a pixel-art frame (stepped corners, a staircase tail, a drop
shadow) with a pixel font, the text typed letter by letter with a blinking block cursor. Long lines wrap.
The size is fixed by the whole text, so the bubble does not grow while it types.

Two kinds:
  a remark      say(text): types, stays a while, goes away; never takes the mouse
  a dialog      say(text, choices=[...], hint=..., sticky=True): stays until it is answered; the choices
                (numbered rows, shown when the text is typed) can be clicked or picked with the keys (the
                beaver handles the keys); a click elsewhere on it gives clicked(-1) ("next" in the tour)
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter
from PySide6.QtWidgets import QWidget

CPS = 38.0                       # characters per second
HOLD_S = 1.6                     # shown this long after the last character …
HOLD_PER_CHAR_S = 0.035          # … plus this per character
READ_S, READ_PER_CHAR_S = 0.7, 0.03   # never replaced by another line before this (time to read it)
FONT_FAMILY = "Pixelify Sans"
FONT_PX = 15
HINT_PX = 12
PAD = 9                          # text margin inside the frame (logical px)
TAIL = 10                        # tail length (logical px)
MAX_TEXT_W = 340                 # longer lines wrap
ROW_GAP = 4


def _font(px):
    f = QFont(FONT_FAMILY)
    f.setPixelSize(px)
    f.setStyleStrategy(QFont.NoAntialias)
    f.setHintingPreference(QFont.PreferFullHinting)
    return f


def wrap(text: str, fm: QFontMetricsF, width: float) -> list[str]:
    """Lines of `text` (kept "\\n" breaks) no wider than `width`, broken between words."""
    out = []
    for para in text.split("\n"):
        words, line = para.split(" "), ""
        for w in words:
            trial = w if not line else line + " " + w
            if line and fm.horizontalAdvance(trial) > width:
                out.append(line)
                line = w
            else:
                line = trial
        out.append(line)
    return out


class SpeechBubble(QWidget):
    clicked = Signal(int)            # a choice (0, 1 …) or −1 (the text) of a dialog

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.hide()
        self.font_, self.hint_font = _font(FONT_PX), _font(HINT_PX)
        self.text = ""
        self.choices: list[str] = []
        self.hint = ""
        self.sticky = False
        self.sel = -1                    # highlighted choice (keys / mouse)
        self.shown = 0.0                 # characters typed so far
        self.after = 0.0                 # seconds since the last character
        self.tail = "down"               # where the tail points: down (bubble above), left / right, up
        self.colors = {"paper": QColor("#FBF7EC"), "ink": QColor("#211A12"), "shadow": QColor(33, 26, 18, 70),
                       "muted": QColor("#4E4434"), "sel": QColor("#EFE3CE")}
        self._lines = []
        self._rows = []                  # choice rows: (rect in box coordinates)
        self._box = QRectF()
        self._anchor = QPointF()
        self._offset = QPointF()

    # ------------------------------------------------------------------ text
    @property
    def active(self) -> bool:
        return bool(self.text)

    @property
    def typing(self) -> bool:
        return self.shown < len(self._typed())

    @property
    def dialog(self) -> bool:
        return bool(self.text) and (self.sticky or bool(self.choices))

    def busy(self) -> bool:
        """Still typing, or typed but not yet readable (a new line would cut it off); a dialog is always busy."""
        if not self.text:
            return False
        if self.dialog:
            return True
        return self.typing or self.after < READ_S + READ_PER_CHAR_S * len(self.text)

    def set_theme(self, theme: dict):
        self.colors = {"paper": QColor(theme["panel_bg"]), "ink": QColor(theme["ink"]),
                       "shadow": QColor(0, 0, 0, 70), "muted": QColor(theme["text_muted"]),
                       "sel": QColor(theme["accent_soft"])}
        self.update()

    def say(self, text: str, typed: bool = True, choices=None, hint: str = "", sticky: bool = False):
        self.text = text
        self.choices = list(choices or [])
        self.hint = hint
        self.sticky = bool(sticky)
        self.sel = 0 if self.choices else -1
        self.after = 0.0
        fm, hm = QFontMetricsF(self.font_), QFontMetricsF(self.hint_font)
        self._lines = wrap(text, fm, MAX_TEXT_W)
        self.shown = 0.0 if typed else float(len(self._typed()))
        a = self.art()
        w = max(fm.horizontalAdvance(l) for l in self._lines)
        h = fm.lineSpacing() * len(self._lines)
        self._rows = []
        if self.choices:
            h += 6
            for k, c in enumerate(self.choices):
                label = f"{(k + 1) % 10}  {c}"
                w = max(w, fm.horizontalAdvance(label) + 12)
                self._rows.append(QRectF(PAD - 4, PAD - 2 + h, 0, fm.lineSpacing() + ROW_GAP))
                h += fm.lineSpacing() + ROW_GAP
        if self.hint:
            h += 4 + hm.lineSpacing()
            w = max(w, hm.horizontalAdvance(self.hint))
        w += 2 * PAD + 6
        h += 2 * PAD - 2
        self._box = QRectF(0, 0, math.ceil(w / a) * a, math.ceil(h / a) * a)
        for r in self._rows:
            r.setWidth(self._box.width() - 2 * (PAD - 4))
        self.setAttribute(Qt.WA_TransparentForMouseEvents, not self.dialog)
        self.update()

    def _typed(self) -> str:
        return "\n".join(self._lines)

    def finish_typing(self):
        self.shown = float(len(self._typed()))
        self.update()

    def clear(self):
        self.text = ""
        self.choices = []
        self.sticky = False
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hide()

    def advance(self, dt: float):
        """Type on / count the time it stays; a remark hides itself when done (a dialog stays)."""
        if not self.text:
            return
        if self.typing:
            self.shown = min(len(self._typed()), self.shown + CPS * dt)
        else:
            self.after += dt
            if not self.dialog and self.after > HOLD_S + HOLD_PER_CHAR_S * len(self.text):
                self.clear()
                return
        self.update()

    def move_selection(self, step: int):
        if self.choices:
            self.sel = (self.sel + step) % len(self.choices)
            self.update()

    def art(self) -> float:
        """One art pixel in logical pixels (whole device pixels)."""
        dpr = self.devicePixelRatioF() or 1.0
        return max(2, round(2 * dpr)) / dpr

    # ------------------------------------------------------------------ mouse (dialogs)
    def _row_at(self, pos) -> int:
        if self.typing:
            return -1
        p = pos - self._offset
        for k, r in enumerate(self._rows):
            if r.contains(p):
                return k
        return -1

    def mouseMoveEvent(self, e):
        k = self._row_at(e.position())
        if k >= 0 and k != self.sel:
            self.sel = k
            self.update()
        self.setCursor(Qt.PointingHandCursor if k >= 0 or self.sticky else Qt.ArrowCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.dialog:
            if self.typing:
                self.finish_typing()
            else:
                self.clicked.emit(self._row_at(e.position()))
        e.accept()

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
        for line in self._lines:
            part = line[:max(0, n)]
            p.drawText(QPointF(x0 + PAD + 1, y), part)
            if self.typing and 0 <= n <= len(line):
                cx = x0 + PAD + 1 + fm.horizontalAdvance(part) + 1
                p.fillRect(QRectF(cx, y - fm.ascent() + 2, a * 2.5, fm.ascent() - 1), ink)
            n -= len(line) + 1
            y += fm.lineSpacing()
        # choices: numbered rows, the selected one marked (clickable once the text is typed)
        for k, (c, rr) in enumerate(zip(self.choices, self._rows)):
            row = rr.translated(o)
            if k == self.sel and not self.typing:
                p.fillRect(row.adjusted(0, 0, 0, -1), self.colors["sel"])
                p.fillRect(QRectF(row.left(), row.top(), a, row.height() - 1), ink)
            p.setPen(ink)
            p.drawText(QPointF(row.left() + 6, row.top() + ROW_GAP / 2 + fm.ascent()), f"{(k + 1) % 10}  {c}")
        if self.hint:
            hm = QFontMetricsF(self.hint_font)
            p.setFont(self.hint_font)
            p.setPen(self.colors["muted"])
            p.drawText(QPointF(x0 + PAD + 1, y0 + h - PAD + 2 - hm.descent()), self.hint)
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
