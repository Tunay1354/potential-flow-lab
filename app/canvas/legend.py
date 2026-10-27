"""
legend.py — the color legend of the field layers: a small card in the top-right corner of the plot
with the title and the color bands with their values, or a short note with a clickable action
(e.g. Cp without a reference speed). Part of the plot scene, so it is also in exported figures.
"""
import math

import pyqtgraph as pg
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from ..theme import FONT, first_family


class ColorLegend(pg.GraphicsWidgetAnchor, pg.GraphicsWidget):
    """Small card in the top-right corner of the plot: title and the color bands with values.
    Part of the plot scene, so it is also in exported figures."""

    W, H = 92, 214

    def __init__(self):
        pg.GraphicsWidget.__init__(self)
        pg.GraphicsWidgetAnchor.__init__(self)
        self.setFlag(self.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setFixedWidth(self.W)
        self.setFixedHeight(self.H)
        self.theme = None
        self.title = ""
        self.edges, self.colors = [], []
        self.note = None                  # (text, link): a message instead of the color bands
        self.clicked = None               # called when the note's link is clicked
        self.setZValue(20)

    def set_bands(self, title, edges, colors):
        self.title, self.edges, self.colors = title, list(edges), list(colors)
        self.note = None
        self._resize(self.W, self.H)
        self.unsetCursor()
        self.update()

    def set_note(self, title, text, link):
        """A small card with a message (e.g. Cp without reference speed) and a clickable action."""
        self.title, self.note = title, (text, link)
        self.edges, self.colors = [], []
        self._resize(206, 96)
        self.setCursor(Qt.PointingHandCursor)
        self.update()

    def _resize(self, w, h):
        self.prepareGeometryChange()
        self.setFixedWidth(w)
        self.setFixedHeight(h)

    def boundingRect(self):
        return QRectF(0, 0, self.width(), self.height())

    def mouseClickEvent(self, ev):                    # pyqtgraph's click event
        if self.note is not None and self.clicked is not None and ev.button() == Qt.LeftButton:
            ev.accept()
            self.clicked()

    def _paint_note(self, p):
        t = self.theme
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor(t["accent"]), 1))
        p.setBrush(QColor(t["panel_bg"]))
        p.drawRect(QRectF(0.5, 0.5, w - 1, h - 1))
        mono = QFont(first_family("mono"))
        mono.setPointSizeF(FONT["mono_size_pt"] - 1.5)
        body = QFont(first_family("families"))
        body.setPointSizeF(FONT["size_pt"] - 1.5)
        p.setFont(mono)
        p.setPen(QColor(t["text"]))
        p.drawText(QRectF(10, 6, w - 20, 16), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        p.setFont(body)
        text, link = self.note
        p.drawText(QRectF(10, 24, w - 20, h - 46), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, text)
        link_font = QFont(body)
        link_font.setUnderline(True)
        link_font.setWeight(QFont.DemiBold)
        p.setFont(link_font)
        p.setPen(QColor(t["accent"]))
        p.drawText(QRectF(10, h - 22, w - 20, 16), Qt.AlignLeft | Qt.AlignVCenter, link)

    def paint(self, p, *args):
        if self.theme is None:
            return
        if self.note is not None:
            p.setRenderHint(QPainter.Antialiasing, False)
            self._paint_note(p)
            return
        if len(self.edges) < 2:
            return
        t = self.theme
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setPen(QPen(QColor(t["border"]), 1))
        p.setBrush(QColor(t["panel_bg"]))
        p.drawRect(QRectF(0.5, 0.5, self.W - 1, self.H - 1))
        mono = QFont(first_family("mono"))
        mono.setPointSizeF(FONT["mono_size_pt"] - 1.5)
        p.setFont(mono)
        p.setPen(QColor(t["text"]))
        p.drawText(QRectF(8, 5, self.W - 12, 16), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        top, bottom, x0, bw = 26.0, self.H - 10.0, 10.0, 14.0
        n = len(self.colors)
        hb = (bottom - top) / n
        for k, c in enumerate(self.colors):             # highest value on top
            y = bottom - (k + 1) * hb
            p.fillRect(QRectF(x0, y, bw, hb + 0.5), QColor(*c))
        p.setPen(QPen(QColor(t["border"]), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(x0, top, bw, bottom - top))
        every = max(1, int(math.ceil((n + 1) / 7)))       # at most ~7 labels
        shown = list(range(0, len(self.edges), every))
        if shown[-1] != len(self.edges) - 1:
            shown[-1] = len(self.edges) - 1                  # always the top value, never two crowded
        p.setPen(QColor(t["text"]))
        for k in shown:
            e = self.edges[k]
            y = bottom - k * hb
            p.drawLine(QPointF(x0 + bw, y), QPointF(x0 + bw + 4, y))
            p.drawText(QRectF(x0 + bw + 7, y - 7, self.W - x0 - bw - 9, 14), Qt.AlignLeft | Qt.AlignVCenter,
                       _label(e))


def _label(v: float) -> str:
    if abs(v) < 1e-12:
        return "0"
    return (f"{v:.3g}" if abs(v) >= 1e-3 else f"{v:.1e}").replace("-", "−")
