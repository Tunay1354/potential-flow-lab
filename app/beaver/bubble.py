"""
bubble.py — the beaver's speech bubble, in the "drafting card" look: a thick ink frame with stepped
corners, a solid drop shadow and a staircase tail; a header line with the speaker's name (left) and a tag
such as "TOUR 3/18" (right); the text in the mono font, typed letter by letter with a block cursor; buttons
at the bottom right (a plain one with an ink frame, the main one filled in the header's wood colour). Long
lines wrap. The size is fixed by the whole text, so the bubble does not grow while it types.

Kinds:
  a remark      say(text): types, stays a while, goes away; never takes the mouse
  a dialog      say(text, choices=[...], sticky=True): stays until it is answered; the choices (numbered
                rows, shown when the text is typed) can be clicked or picked with the keys (the beaver
                handles the keys); a click elsewhere on it gives clicked(-1) ("next" in the tour)
  buttons       say(..., buttons=["End tour", "Next ›"], primary=1): a click on one gives
                button_clicked(k) — they work while it still types
  header        say(..., title="PSI", tag="TOUR 3/18")
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter
from PySide6.QtWidgets import QWidget

from ..theme import first_family

CPS = 38.0                       # characters per second
HOLD_S = 1.6                     # shown this long after the last character …
HOLD_PER_CHAR_S = 0.035          # … plus this per character
READ_S, READ_PER_CHAR_S = 0.7, 0.03   # never replaced by another line before this (time to read it)
TEXT_PX = 14                     # body text (mono)
HEAD_PX = 11                     # header: name and tag (mono, capitals)
BTN_PX = 12                      # button labels (mono)
HINT_PX = 11
PAD = 13                         # margin inside the frame (logical px)
HEAD_GAP = 7                     # header → text
TAIL = 10                        # tail length (logical px)
MAX_TEXT_W = 370                 # longer lines wrap
ROW_GAP = 4
BTN_PAD_X, BTN_PAD_Y = 11, 5     # text margin inside a button (logical px)
BTN_GAP = 10                     # between two buttons
BTN_TOP = 12                     # text / choices → buttons


def _font(px, weight=QFont.Medium, caps=False, spacing=100.0):
    f = QFont(first_family("mono"))
    f.setPixelSize(px)
    f.setWeight(weight)
    if caps:
        f.setCapitalization(QFont.AllUppercase)
        f.setLetterSpacing(QFont.PercentageSpacing, spacing)
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
    button_clicked = Signal(int)     # one of the buttons (0, 1 …)

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.hide()
        self.font_ = _font(TEXT_PX)
        self.head_font = _font(HEAD_PX, QFont.DemiBold, caps=True, spacing=108)
        self.btn_font = _font(BTN_PX, QFont.DemiBold)
        self.hint_font = _font(HINT_PX, QFont.Normal)
        self.text = ""
        self.title = ""
        self.tag = ""
        self.choices: list[str] = []
        self.hint = ""
        self.buttons: list[str] = []
        self.primary = None              # index of the main (filled) button, or None
        self.hover_btn = -1              # button under the mouse
        self.sticky = False
        self.sel = -1                    # highlighted choice (keys / mouse)
        self.shown = 0.0                 # characters typed so far
        self.after = 0.0                 # seconds since the last character
        self.tail = "down"               # where the tail points: down (bubble above), left / right, up
        self.colors = {}
        self.set_theme(None)
        self._lines = []
        self._rows = []                  # choice rows: (rect in box coordinates)
        self._btns = []                  # buttons: (rect in box coordinates)
        self._text_y = 0.0
        self._hint_y = 0.0
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

    def set_theme(self, theme: dict | None):
        t = theme or {"panel_bg": "#FBF7EC", "ink": "#211A12", "text_muted": "#4E4434", "accent_soft": "#EFE3CE",
                      "accent": "#6E5640", "accent_strong": "#A98B6D", "accent_hover": "#B99D80",
                      "accent_text": "#211A12", "name": "light"}
        dark = t.get("name") == "dark"
        self.colors = {"paper": QColor(t["panel_bg"]), "ink": QColor(t["ink"]),
                       "shadow": QColor(0, 0, 0, 120 if dark else 55), "muted": QColor(t["text_muted"]),
                       "sel": QColor(t["accent_soft"]), "name": QColor(t["accent"]),
                       "primary": QColor(t["accent_strong"]), "primary_hover": QColor(t["accent_hover"]),
                       "primary_text": QColor(t["accent_text"])}
        self.update()

    def say(self, text: str, typed: bool = True, choices=None, hint: str = "", sticky: bool = False,
            buttons=None, primary=None, title: str = "", tag: str = ""):
        self.text = text
        self.title, self.tag = title, tag
        self.choices = list(choices or [])
        self.hint = hint
        self.buttons = list(buttons or [])
        self.primary = primary
        self.hover_btn = -1
        self.sticky = bool(sticky)
        self.sel = 0 if self.choices else -1
        self.after = 0.0
        fm, hm = QFontMetricsF(self.font_), QFontMetricsF(self.head_font)
        bm, im = QFontMetricsF(self.btn_font), QFontMetricsF(self.hint_font)
        self._lines = wrap(text, fm, MAX_TEXT_W)
        self.shown = 0.0 if typed else float(len(self._typed()))
        w = max(fm.horizontalAdvance(line) for line in self._lines)
        y = PAD
        if self.title or self.tag:
            w = max(w, hm.horizontalAdvance(self.title) + hm.horizontalAdvance(self.tag) + 28)
            y += hm.height() + HEAD_GAP
        self._text_y = y
        y += fm.lineSpacing() * len(self._lines)
        self._rows = []
        if self.choices:
            y += 6
            for k, c in enumerate(self.choices):
                label = f"{(k + 1) % 10}  {c}"
                w = max(w, fm.horizontalAdvance(label) + 14)
                self._rows.append(QRectF(PAD - 5, y, 0, fm.lineSpacing() + ROW_GAP))
                y += fm.lineSpacing() + ROW_GAP
        if self.hint:
            y += 5
            self._hint_y = y
            y += im.lineSpacing()
            w = max(w, im.horizontalAdvance(self.hint))
        widths = [bm.horizontalAdvance(b) + 2 * BTN_PAD_X for b in self.buttons]
        bh = bm.height() + 2 * BTN_PAD_Y
        if self.buttons:
            y += BTN_TOP
            w = max(w, sum(widths) + BTN_GAP * (len(widths) - 1))
        w += 2 * PAD
        h = y + (bh if self.buttons else 0) + PAD
        a = self.px(1)
        self._box = QRectF(0, 0, math.ceil(w / a) * a, math.ceil(h / a) * a)
        for r in self._rows:
            r.setWidth(self._box.width() - 2 * (PAD - 5))
        self._btns = []                                    # right-aligned at the bottom
        x = self._box.width() - PAD
        for bw in reversed(widths):
            x -= bw
            self._btns.insert(0, QRectF(self._snap(x), self._snap(y), self._snap(bw), self._snap(bh)))
            x -= BTN_GAP
        self.setAttribute(Qt.WA_TransparentForMouseEvents, not self.dialog)
        self.update()

    def _typed(self) -> str:
        return "\n".join(self._lines)

    def finish_typing(self):
        self.shown = float(len(self._typed()))
        self.update()

    def clear(self):
        self.text = ""
        self.title = self.tag = ""
        self._lines = []                 # (otherwise `typing` would still see the old text)
        self.shown = 0.0
        self.choices = []
        self.buttons = []
        self._btns = []
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

    def px(self, n: float) -> float:
        """n device-independent pixels rounded to whole device pixels (crisp frame lines at 125 %)."""
        dpr = self.devicePixelRatioF() or 1.0
        return max(1, round(n * dpr)) / dpr

    def _snap(self, v: float) -> float:
        a = self.px(1)
        return round(v / a) * a

    def art(self) -> float:
        """Thickness of the frame (the tail's steps use it too)."""
        return self.px(3)

    # ------------------------------------------------------------------ mouse (dialogs)
    def _row_at(self, pos) -> int:
        if self.typing:
            return -1
        p = pos - self._offset
        for k, r in enumerate(self._rows):
            if r.contains(p):
                return k
        return -1

    def _button_at(self, pos) -> int:
        p = pos - self._offset
        for k, r in enumerate(self._btns):
            if r.contains(p):
                return k
        return -1

    def button_rect(self, k: int) -> QRectF:
        """Button k in this widget's coordinates (tests)."""
        return self._btns[k].translated(self._offset)

    def mouseMoveEvent(self, e):
        k = self._row_at(e.position())
        if k >= 0 and k != self.sel:
            self.sel = k
            self.update()
        b = self._button_at(e.position())
        if b != self.hover_btn:
            self.hover_btn = b
            self.update()
        self.setCursor(Qt.PointingHandCursor if k >= 0 or b >= 0 or self.sticky else Qt.ArrowCursor)

    def leaveEvent(self, _e):
        if self.hover_btn >= 0:
            self.hover_btn = -1
            self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.dialog:
            b = self._button_at(e.position())
            if b >= 0:
                self.button_clicked.emit(b)
            elif self.typing:
                self.finish_typing()
            else:
                self.clicked.emit(self._row_at(e.position()))
        e.accept()

    # ------------------------------------------------------------------ placement
    def box_at(self, anchor: QPointF, tail: str, bounds: QRectF) -> QRectF:
        """Where the box would be (parent coordinates) for place(anchor, tail, bounds)."""
        bw, bh = self._box.width(), self._box.height()
        if tail == "down":
            x, y = anchor.x() - 26, anchor.y() - bh - TAIL
        elif tail == "up":
            x, y = anchor.x() - 26, anchor.y() + TAIL
        elif tail == "left":
            x, y = anchor.x() + TAIL, anchor.y() - bh / 2
        else:
            x, y = anchor.x() - bw - TAIL, anchor.y() - bh / 2
        x = min(max(x, bounds.left() + 2), bounds.right() - bw - 10)
        y = min(max(y, bounds.top() + 2), bounds.bottom() - bh - 10)
        return QRectF(x, y, bw, bh)

    def place(self, anchor: QPointF, tail: str, bounds: QRectF):
        """Put the tail tip at `anchor` (parent coordinates), bubble on the other side of the tail, kept
        inside `bounds`."""
        if not self.text:
            return
        self.tail = tail
        box = self.box_at(anchor, tail, bounds)
        x, y, bw, bh = box.x(), box.y(), box.width(), box.height()
        m = TAIL + 8
        self._anchor = anchor - QPointF(x - m, y - m)                   # tail tip in widget coordinates
        self.setGeometry(int(x - m), int(y - m), int(bw + 2 * m), int(bh + 2 * m))
        self._offset = QPointF(m, m)
        if not self.isVisible():
            self.show()
        self.raise_()

    # ------------------------------------------------------------------ drawing
    def _card(self, p, r: QRectF, t: float, fill: QColor, ink: QColor, shadow: QColor | None, s: float = 0.0):
        """A card with stepped corners: its shadow (offset s), body, a frame of thickness t."""
        x0, y0, w, h = r.x(), r.y(), r.width(), r.height()
        if shadow is not None and s > 0:
            p.fillRect(QRectF(x0 + t + s, y0 + s, w - 2 * t, h), shadow)
            p.fillRect(QRectF(x0 + s, y0 + t + s, w, h - 2 * t), shadow)
        p.fillRect(QRectF(x0 + t, y0, w - 2 * t, h), fill)
        p.fillRect(QRectF(x0, y0 + t, w, h - 2 * t), fill)
        for rr in (QRectF(x0 + t, y0, w - 2 * t, t), QRectF(x0 + t, y0 + h - t, w - 2 * t, t),
                   QRectF(x0, y0 + t, t, h - 2 * t), QRectF(x0 + w - t, y0 + t, t, h - 2 * t)):
            p.fillRect(rr, ink)
        for cx, cy in ((x0 + t, y0 + t), (x0 + w - 2 * t, y0 + t), (x0 + t, y0 + h - 2 * t),
                       (x0 + w - 2 * t, y0 + h - 2 * t)):
            p.fillRect(QRectF(cx, cy, t, t), ink)                        # the inner step of each corner

    def paintEvent(self, _e):
        if not self.text:
            return
        t = self.art()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        c = self.colors
        ink, paper = c["ink"], c["paper"]
        o = self._offset
        r = self._box.translated(o)
        x0, y0, w, h = r.x(), r.y(), r.width(), r.height()
        self._card(p, r, t, paper, ink, c["shadow"], self.px(5))
        self._tail(p, t, x0, y0, w, h, ink, paper)
        # header: name left, tag right
        if self.title or self.tag:
            hm = QFontMetricsF(self.head_font)
            p.setFont(self.head_font)
            base = y0 + PAD + hm.ascent()
            if self.title:
                p.setPen(c["name"])
                p.drawText(QPointF(x0 + PAD, base), self.title)
            if self.tag:
                p.setPen(c["muted"])
                p.drawText(QPointF(x0 + w - PAD - hm.horizontalAdvance(self.tag), base), self.tag)
        # text typed so far + block cursor
        p.setFont(self.font_)
        p.setPen(ink)
        fm = QFontMetricsF(self.font_)
        n = int(self.shown)
        y = y0 + self._text_y + fm.ascent()
        for line in self._lines:
            part = line[:max(0, n)]
            p.drawText(QPointF(x0 + PAD, y), part)
            if self.typing and 0 <= n <= len(line):
                cx = x0 + PAD + fm.horizontalAdvance(part) + 1
                p.fillRect(QRectF(self._snap(cx), self._snap(y - fm.ascent() + 1), self.px(7), self._snap(fm.ascent())), ink)
            n -= len(line) + 1
            y += fm.lineSpacing()
        # choices: numbered rows, the selected one marked (clickable once the text is typed)
        for k, (ch, rr) in enumerate(zip(self.choices, self._rows)):
            row = rr.translated(o)
            if k == self.sel and not self.typing:
                p.fillRect(row.adjusted(0, 0, 0, -1), c["sel"])
                p.fillRect(QRectF(row.left(), row.top(), self.px(3), row.height() - 1), c["name"])
            p.setPen(ink)
            p.drawText(QPointF(row.left() + 9, row.top() + ROW_GAP / 2 + fm.ascent()), f"{(k + 1) % 10}  {ch}")
        if self.hint:
            im = QFontMetricsF(self.hint_font)
            p.setFont(self.hint_font)
            p.setPen(c["muted"])
            p.drawText(QPointF(x0 + PAD, y0 + self._hint_y + im.ascent()), self.hint)
        # buttons: an ink frame on paper; the main one filled in the header's wood colour
        bm = QFontMetricsF(self.btn_font)
        p.setFont(self.btn_font)
        bt = self.px(2)
        for k, (label, rr) in enumerate(zip(self.buttons, self._btns)):
            br = rr.translated(o)
            main = k == self.primary
            hover = k == self.hover_btn
            fill = (c["primary_hover"] if hover else c["primary"]) if main else (c["sel"] if hover else paper)
            self._card(p, br, bt, fill, ink, None)
            shade = QColor(fill).darker(118)                             # a little 3-D: darker bottom edge
            p.fillRect(QRectF(br.left() + bt, br.bottom() - 2 * bt, br.width() - 2 * bt, bt), shade)
            p.setPen(c["primary_text"] if main else ink)
            p.drawText(QPointF(br.left() + (br.width() - bm.horizontalAdvance(label)) / 2,
                               br.top() + BTN_PAD_Y + bm.ascent() - bt / 2), label)
        p.end()

    def _tail(self, p, a, x0, y0, w, h, ink, paper):
        tip = self._anchor
        steps = 4
        if self.tail in ("down", "up"):
            sgn = 1 if self.tail == "down" else -1
            base_y = y0 + h - a if sgn > 0 else y0
            bx = min(max(tip.x() - 3 * a, x0 + 3 * a), x0 + w - 7 * a)
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
            for k in range(0, steps):
                xx = ex + sgn * k * a
                half = (steps - k) * a
                p.fillRect(QRectF(xx, cy - half + a, a, 2 * half - 2 * a), paper)
                p.fillRect(QRectF(xx, cy - half, a, a), ink)
                p.fillRect(QRectF(xx, cy + half - a, a, a), ink)
            p.fillRect(QRectF(ex + sgn * steps * a, cy - a, a, a), ink)
