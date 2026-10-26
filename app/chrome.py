"""
chrome.py — the "drafting paper" frame of the window: bundled fonts, the wooden header with the
logo, the ruler that carries the menus, framed panels (double line like a title block) and the
title block under the plot. Colors and sizes come from theme.py.
"""
import glob
import math
import os

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenuBar, QSizePolicy, QVBoxLayout, QWidget

from .theme import ASSETS_DIR, FONT, LAYOUT, first_family

_fonts_loaded = False


def load_fonts():
    """Register the bundled fonts (IBM Plex Mono, Barlow, Barlow Condensed) once per process."""
    global _fonts_loaded
    if _fonts_loaded:
        return
    for path in sorted(glob.glob(os.path.join(ASSETS_DIR, "fonts", "*", "*.ttf"))):
        QFontDatabase.addApplicationFont(path)
    _fonts_loaded = True


def color(value: str) -> QColor:
    """QColor from '#RRGGBB' or '#RRGGBBAA' (CSS order; Qt itself reads 8 digits as #AARRGGBB)."""
    if len(value) == 9:
        c = QColor(value[:7])
        c.setAlpha(int(value[7:9], 16))
        return c
    return QColor(value)


def font(kind: str, size_pt: float, weight=QFont.Normal, caps=False, spacing_pct=100.0) -> QFont:
    """Font of a family list in FONT ("families", "mono", "heading"); caps = shown in capitals,
    spacing_pct = letter spacing in percent of the normal spacing."""
    f = QFont(first_family(kind))
    f.setPointSizeF(size_pt)
    f.setWeight(weight)
    if caps:
        f.setCapitalization(QFont.AllUppercase)
    if spacing_pct != 100.0:
        f.setLetterSpacing(QFont.PercentageSpacing, spacing_pct)
    return f


def heading_font(size_pt=None) -> QFont:
    return font("heading", size_pt or FONT["heading_size_pt"], QFont.Bold, caps=True, spacing_pct=118)


def button_font() -> QFont:
    return font("heading", FONT["button_size_pt"], QFont.DemiBold, caps=True, spacing_pct=108)


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
    p.setBrush(QColor(theme["accent_strong"]))
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


# ---------------------------------------------------------------------------------------- panels
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


def _frame_lines(p: QPainter, r: QRectF, theme: dict, top: bool, bottom: bool):
    """Double frame of a panel (outer line + inner line 3 px inside) with optional open top / bottom,
    so the title bar and the body of a dock look like one card."""
    for inset, key in ((0.5, "border"), (4.5, "border_inner")):
        p.setPen(QPen(QColor(theme[key]), 1))
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
        _frame_lines(p, r, th, top=True, bottom=False)
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
        _frame_lines(p, r, self.theme, top=False, bottom=True)
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
