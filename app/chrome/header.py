"""
header.py — the wooden header: the logo, the plank with the program name and the open file, and the
ruler that carries the menus (and, later, the beaver).
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenuBar, QSizePolicy, QVBoxLayout, QWidget

from ..theme import FONT, LAYOUT
from .style import color, font


# ---------------------------------------------------------------------------------------- logo
def draw_logo(p: QPainter, rect: QRectF, theme: dict):
    """Program mark: a square paper tile with streamlines passing a rust-colored cylinder."""
    s = rect.width()
    x0, y0 = rect.x(), rect.y()

    def P(x, y):                                   # coordinates of a 40 × 40 design
        return QPointF(x0 + x * s / 40.0, y0 + y * s / 40.0)

    ink = QColor(theme["ink"] if theme["name"] == "dark" else theme["text"])
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(ink, max(1.0, 1.5 * s / 40.0)))
    p.setBrush(QColor(theme["panel_bg"]))
    p.drawRect(QRectF(P(1.5, 1.5), P(38.5, 38.5)))
    path = QPainterPath()
    for sgn in (-1, 1):                            # upper and lower streamline around the cylinder
        y_far, y_near = 20 + sgn * 6.5, 20 + sgn * 12.5
        path.moveTo(P(5, y_far))
        path.cubicTo(P(12.5, y_far), P(14, y_near), P(20, y_near))
        path.cubicTo(P(26, y_near), P(27.5, y_far), P(35, y_far))
    path.moveTo(P(5, 20))
    path.lineTo(P(12.5, 20))
    path.moveTo(P(27.5, 20))
    path.lineTo(P(35, 20))
    p.setPen(QPen(ink, 2.0 * s / 40.0, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(theme["logo_dot"]))
    p.drawEllipse(P(20, 20), 6.6 * s / 40.0, 6.6 * s / 40.0)
    p.restore()


def logo_pixmap(theme: dict, size: int, dpr: float = 1.0) -> QPixmap:
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    draw_logo(p, QRectF(0, 0, size, size), theme)
    p.end()
    return pm


# ---------------------------------------------------------------------------------------- header
class Plank(QWidget):
    """Wooden band: logo, program name, version, current file."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(LAYOUT["plank_height"])
        self.theme = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(14)
        self.logo = QLabel()
        self.title = QLabel("Potential Flow Lab")
        self.title.setObjectName("PlankTitle")
        self.title.setFont(font("mono", FONT["title_size_pt"], QFont.DemiBold, caps=True, spacing_pct=114))
        self.version = QLabel("")
        self.version.setObjectName("PlankMuted")
        self.file = QLabel("")
        self.file.setObjectName("PlankMuted")
        for w in (self.logo, self.title, self.version):
            lay.addWidget(w)
        lay.addStretch(1)
        lay.addWidget(self.file)

    def apply_theme(self, theme):
        self.theme = theme
        self.logo.setPixmap(logo_pixmap(theme, LAYOUT["logo_px"], self.devicePixelRatioF()))
        self.update()

    def paintEvent(self, _event):
        if self.theme is None:
            return
        t = self.theme
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(t["plank"]))
        # wood grain: nearly horizontal stripes, slightly tilted (like the concept drawing)
        p.setRenderHint(QPainter.Antialiasing)
        tilt = w * math.tan(math.radians(1.5))
        light, dark = color(t["plank_grain_light"]), color(t["plank_grain_dark"])
        period = 17.0
        k = -int(tilt / period) - 2
        while k * period < h + 2:
            y = k * period
            for dy, c, width in ((1.0, light, 2.0), (9.5, dark, 1.0)):
                p.setPen(QPen(c, width))
                p.drawLine(QPointF(0, y + dy + tilt), QPointF(w, y + dy))
            k += 1
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setPen(QPen(QColor(t["plank_edge"]), 1))
        p.drawLine(0, h - 1, w, h - 1)
        p.end()


class Ruler(QWidget):
    """The rail under the plank: a ruler with mm / cm ticks that carries the menus.
    `beaver_perch` is the free space right of Help where the mascot will hang later."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(LAYOUT["ruler_height"])
        self.theme = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 1, 18, 0)
        lay.setSpacing(0)
        self.menu_bar = QMenuBar(self)
        self.menu_bar.setObjectName("RulerMenu")
        self.menu_bar.setNativeMenuBar(False)          # macOS: keep the menus on the ruler
        self.menu_bar.setFont(font("heading", FONT["menu_size_pt"], QFont.DemiBold, caps=True, spacing_pct=110))
        self.menu_bar.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        lay.addWidget(self.menu_bar, 0, Qt.AlignTop)
        self.beaver_perch = QWidget(self)
        self.beaver_perch.setObjectName("BeaverPerch")
        self.beaver_perch.setFixedWidth(LAYOUT["beaver_perch_px"])
        lay.addWidget(self.beaver_perch)
        lay.addStretch(1)
        self.scale = QLabel("0   1   2   3   4   5 cm")
        self.scale.setObjectName("RulerScale")
        self.scale.setFont(font("mono", 8.5))
        lay.addWidget(self.scale, 0, Qt.AlignTop)
        self.scale.setContentsMargins(0, 8, 0, 0)

    def apply_theme(self, theme):
        self.theme = theme
        self.update()

    def paintEvent(self, _event):
        if self.theme is None:
            return
        t = self.theme
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(t["ruler"]))
        p.setPen(QPen(QColor(t["ruler_tick"]), 1))
        for k, x in enumerate(range(0, w, 8)):        # 1 mm = 8 px, a long tick every 5 mm
            length = 10 if k % 5 == 0 else 5
            p.drawLine(x, h - 1 - length, x, h - 1)
        p.setPen(QPen(QColor(t["ruler_edge"]), 1))
        p.drawLine(0, h - 1, w, h - 1)
        p.end()


class HeaderBar(QWidget):
    """Plank + ruler + a strip of paper under them (gap to the panels)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, LAYOUT["gap"])
        lay.setSpacing(0)
        self.plank = Plank(self)
        self.ruler = Ruler(self)
        lay.addWidget(self.plank)
        lay.addWidget(self.ruler)

    @property
    def menu_bar(self) -> QMenuBar:
        return self.ruler.menu_bar

    def apply_theme(self, theme):
        self.plank.apply_theme(theme)
        self.ruler.apply_theme(theme)
