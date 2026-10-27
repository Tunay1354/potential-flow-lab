"""
cards.py — the drafting-paper look of the window: the paper grid, the framed side-panel cards (double
line like a title block), the title block under the plot, and the drop indicator of a dragged card.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..theme import LAYOUT
from .style import color, device_line_rect, heading_font


def paint_paper_grid(widget: QWidget, theme: dict):
    """Drafting paper: background color and a faint square grid."""
    p = QPainter(widget)
    p.fillRect(widget.rect(), QColor(theme["window_bg"]))
    p.setPen(QPen(color(theme["paper_grid"]), 1))
    step = LAYOUT["paper_grid_px"]
    w, h = widget.width(), widget.height()
    for x in range(0, w, step):
        p.drawLine(x, 0, x, h)
    for y in range(0, h, step):
        p.drawLine(0, y, w, y)
    p.end()


def frame_lines(p: QPainter, r: QRectF, theme: dict, top: bool, bottom: bool):
    """Double frame of a panel (outer line + inner line 3 px inside) with optional open top / bottom,
    so the title bar and the body of a dock look like one card."""
    for inset, key in ((0.5, "border"), (4.5, "border_inner")):
        pen = QPen(QColor(theme[key]), 0)
        pen.setCosmetic(True)          # exactly one screen pixel at any display scaling (125 %, 150 % ...)
        p.setPen(pen)
        x0, x1 = r.left() + inset, r.right() - inset
        y0 = r.top() + (inset if top else 0)
        y1 = r.bottom() - (inset if bottom else 0)
        p.drawLine(QPointF(x0, y0), QPointF(x0, y1))
        p.drawLine(QPointF(x1, y0), QPointF(x1, y1))
        if top:
            p.drawLine(QPointF(x0, y0), QPointF(x1, y0))
        if bottom:
            p.drawLine(QPointF(x0, y1), QPointF(x1, y1))


class _DockPart(QWidget):
    """Common part of the dock title and body: knows its margins to the window edge."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = None
        self.outer = (0, 0, 0, 0)      # paper left around the card: left, top, right, bottom

    def card_rect(self) -> QRectF:
        l, t, r, b = self.outer
        return QRectF(self.rect()).adjusted(l, t, -r, -b)


class PanelTitle(_DockPart):
    """Title bar of a dock: heading in capitals over a strong rule (title-block style); drag it to move
    the panel. `note` is a small text on the right (e.g. '3 ITEMS')."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setSpacing(8)
        self.heading = QLabel(text)
        self.heading.setObjectName("PanelHeading")
        self.heading.setFont(heading_font())
        self.note = QLabel("")
        self.note.setObjectName("PanelNote")
        lay.addWidget(self.heading)
        lay.addStretch(1)
        lay.addWidget(self.note)
        self.set_outer(self.outer)

    def set_outer(self, outer):
        self.outer = outer
        l, t, r, _b = outer
        self.layout().setContentsMargins(l + 16, t + 12, r + 16, 8)
        self.update()

    def paintEvent(self, _event):
        if self.theme is None:
            return
        th = self.theme
        p = QPainter(self)
        r = self.card_rect()
        p.fillRect(r, QColor(th["panel_bg"]))
        frame_lines(p, r, th, top=True, bottom=False)
        p.setPen(QPen(QColor(th["ink"]), 1.5))
        y = r.bottom() - 1
        p.drawLine(QPointF(r.left() + 14, y), QPointF(r.right() - 14, y))
        p.end()


class PanelBody(_DockPart):
    """Body of a dock: the panel widget inside the lower part of the double frame."""

    def __init__(self, inner: QWidget, parent=None):
        super().__init__(parent)
        self.inner = inner
        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.addWidget(inner)
        self.set_outer(self.outer)

    def set_outer(self, outer):
        self.outer = outer
        l, _t, r, b = outer
        self.layout().setContentsMargins(l + 6, 2, r + 6, b + 6)
        self.update()

    def paintEvent(self, _event):
        if self.theme is None:
            return
        p = QPainter(self)
        r = self.card_rect()
        p.fillRect(r, QColor(self.theme["panel_bg"]))
        frame_lines(p, r, self.theme, top=False, bottom=True)
        p.end()


# ---------------------------------------------------------------------------------------- title block
class TitleBlock(QWidget):
    """Strip under the plot like the title block of a technical drawing: SCENE | ELEMENTS | VIEW | FILE."""

    CELLS = (("scene", "SCENE", 14), ("elements", "ELEMENTS", 9), ("view", "VIEW", 13), ("file", "FILE", 11))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBlock")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.values = {}
        for i, (key, title, stretch) in enumerate(self.CELLS):
            cell = QWidget(self)
            cell.setObjectName("TitleCellLast" if i == len(self.CELLS) - 1 else "TitleCell")
            cell.setAttribute(Qt.WA_StyledBackground, True)
            v = QVBoxLayout(cell)
            v.setContentsMargins(10, 4, 10, 5)
            v.setSpacing(0)
            k = QLabel(title)
            k.setObjectName("TitleKey")
            val = QLabel("—")
            val.setObjectName("TitleValue")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            v.addWidget(k)
            v.addWidget(val)
            lay.addWidget(cell, stretch)
            self.values[key] = val

    def set(self, key: str, text: str):
        self.values[key].setText(text)


class DropIndicator(QWidget):
    """Where a dragged card will land: a translucent wood-colored band with a dashed outline
    (used for the element palette; Qt's own dock indicator gets the same color via the palette)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = None
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hide()

    def paintEvent(self, _event):
        if self.theme is None:
            return
        p = QPainter(self)
        fill = QColor(self.theme["accent_strong"])
        fill.setAlpha(80)
        p.fillRect(self.rect(), fill)
        pen = QPen(QColor(self.theme["accent"]), 0, Qt.DashLine)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.drawRect(device_line_rect(self))
        p.end()
