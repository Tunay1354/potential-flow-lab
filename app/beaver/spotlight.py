"""
spotlight.py — the tour's highlight: the rest of the window slightly dimmed, a blinking pixel frame round
the part being explained. Never takes the mouse (everything stays usable).
"""
from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

PAD = 6


class Spotlight(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.target = None              # QRectF in parent coordinates, or None (dim only)
        self.phase = 0.0
        self.color = QColor("#B03A2E")
        self.hide()

    def set_theme(self, theme):
        self.color = QColor(theme["danger"])
        self.update()

    def show_on(self, rect):
        self.target = None if rect is None else QRectF(rect).adjusted(-PAD, -PAD, PAD, PAD)
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.update()

    def advance(self, dt):
        self.phase += dt
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        dim = QPainterPath()
        dim.addRect(QRectF(self.rect()))
        if self.target is not None:
            hole = QPainterPath()
            hole.addRect(self.target)
            dim = dim.subtracted(hole)
        p.fillPath(dim, QColor(20, 14, 8, 55))
        if self.target is not None:
            r = self.target
            a = 3                                            # pixel frame, blinking
            c = QColor(self.color)
            c.setAlphaF(0.55 + 0.45 * (0.5 + 0.5 * math.sin(self.phase * 6.0)))
            for rr in (QRectF(r.left(), r.top() - a, r.width(), a), QRectF(r.left(), r.bottom(), r.width(), a),
                       QRectF(r.left() - a, r.top(), a, r.height()), QRectF(r.right(), r.top(), a, r.height())):
                p.fillRect(rr, c)
            k = 4 * a                                        # corner brackets
            for cx, cy, sx, sy in ((r.left(), r.top(), 1, 1), (r.right(), r.top(), -1, 1),
                                   (r.left(), r.bottom(), 1, -1), (r.right(), r.bottom(), -1, -1)):
                p.fillRect(QRectF(cx - (2 * a if sx > 0 else -a), cy - (2 * a if sy > 0 else -a),
                                  sx * k if sx > 0 else -k, 2 * a).normalized(), c)
                p.fillRect(QRectF(cx - (2 * a if sx > 0 else -a), cy - (2 * a if sy > 0 else -a),
                                  2 * a, sy * k if sy > 0 else -k).normalized(), c)
        p.end()
