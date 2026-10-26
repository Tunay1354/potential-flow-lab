"""
icons.py — element icons drawn in code (no image files, no copyright issues).
Colors come from the theme, so icons follow the light/dark palette.
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


def _arrow_head(p: QPainter, tip: QPointF, angle_rad: float, size: float, color: QColor, half: float = 0.45):
    """Filled triangular arrow head pointing in direction angle_rad (screen coords); `half` = half opening angle."""
    left = QPointF(tip.x() - size * math.cos(angle_rad - half), tip.y() - size * math.sin(angle_rad - half))
    right = QPointF(tip.x() - size * math.cos(angle_rad + half), tip.y() - size * math.sin(angle_rad + half))
    p.setBrush(color)
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([tip, left, right]))


def _draw(key: str, p: QPainter, s: float, c: QColor, sign: int = 1):
    pen = QPen(c, s * 0.06, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    head = s * 0.16

    if key == "uniform":
        for y in (0.28, 0.5, 0.72):
            p.setPen(pen)
            p.drawLine(QPointF(s * 0.12, s * y), QPointF(s * 0.78, s * y))
            _arrow_head(p, QPointF(s * 0.9, s * y), 0.0, head, c)

    elif key == "source":
        cx = cy = s * 0.5
        for k in range(8):
            a = k * math.pi / 4
            p.setPen(pen)
            if sign > 0:    # source: arrows point outwards
                p.drawLine(QPointF(cx + s * 0.12 * math.cos(a), cy + s * 0.12 * math.sin(a)),
                           QPointF(cx + s * 0.33 * math.cos(a), cy + s * 0.33 * math.sin(a)))
                _arrow_head(p, QPointF(cx + s * 0.44 * math.cos(a), cy + s * 0.44 * math.sin(a)), a, head * 0.8, c)
            else:           # sink: arrows point inwards
                p.drawLine(QPointF(cx + s * 0.27 * math.cos(a), cy + s * 0.27 * math.sin(a)),
                           QPointF(cx + s * 0.46 * math.cos(a), cy + s * 0.46 * math.sin(a)))
                _arrow_head(p, QPointF(cx + s * 0.15 * math.cos(a), cy + s * 0.15 * math.sin(a)),
                            a + math.pi, head * 0.8, c)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), s * 0.07, s * 0.07)

    elif key == "vortex":
        if sign < 0:                                  # clockwise: mirror the counter-clockwise drawing
            p.translate(s, 0)
            p.scale(-1, 1)
        rect = QRectF(s * 0.16, s * 0.16, s * 0.68, s * 0.68)
        start, span = 120.0, 250.0                   # arc from 120° counter-clockwise to 10° (math angles)
        p.drawArc(rect, int(start * 16), int(span * 16))   # Qt angles: 1/16 degree, ccw
        r = s * 0.34
        a_end = math.radians(start + span)           # arc end
        a_tip = a_end + 0.62                         # head extends the arc in the ccw direction
        tip = QPointF(s * 0.5 + r * math.cos(a_tip), s * 0.5 - r * math.sin(a_tip))
        base = QPointF(s * 0.5 + r * math.cos(a_end), s * 0.5 - r * math.sin(a_end))
        # direction from the arc end to the tip (chord), screen coordinates
        _arrow_head(p, tip, math.atan2(tip.y() - base.y(), tip.x() - base.x()), s * 0.26, c, half=0.42)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.06, s * 0.06)

    elif key == "doublet":
        r = s * 0.2
        p.drawEllipse(QPointF(s * 0.5, s * 0.5 - r), r, r)
        p.drawEllipse(QPointF(s * 0.5, s * 0.5 + r), r, r)
        p.drawLine(QPointF(s * 0.1, s * 0.5), QPointF(s * 0.9, s * 0.5))
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.06, s * 0.06)

    elif key == "sector":
        v = QPointF(s * 0.16, s * 0.84)
        p.drawLine(v, QPointF(s * 0.92, s * 0.84))
        p.drawLine(v, QPointF(s * 0.16, s * 0.08))
        thin = QPen(c, s * 0.045, Qt.SolidLine, Qt.RoundCap)
        p.setPen(thin)
        # hyperbola (x - x_v)(y_v - y) = const  -> corner flow, n = 2
        path = QPainterPath()
        xs = [0.22 + 0.66 * i / 30 for i in range(31)]
        for i, x in enumerate(xs):
            pt = QPointF(s * x, s * (0.84 - 0.045 / (x - 0.16)))
            path.moveTo(pt) if i == 0 else path.lineTo(pt)
        p.drawPath(path)
        _arrow_head(p, QPointF(s * 0.88, s * (0.84 - 0.045 / 0.72)), 0.0, head * 0.85, c)

    elif key == "wall":
        thick = QPen(c, s * 0.09, Qt.SolidLine, Qt.FlatCap)
        p.setPen(thick)
        p.drawLine(QPointF(s * 0.1, s * 0.42), QPointF(s * 0.9, s * 0.42))
        hatch = QPen(c, s * 0.04, Qt.SolidLine, Qt.RoundCap)
        p.setPen(hatch)
        for k in range(6):
            x = 0.14 + k * 0.14
            p.drawLine(QPointF(s * x, s * 0.47), QPointF(s * (x - 0.1), s * 0.66))
        p.setPen(pen)
        p.drawLine(QPointF(s * 0.18, s * 0.24), QPointF(s * 0.66, s * 0.24))
        _arrow_head(p, QPointF(s * 0.8, s * 0.24), 0.0, head * 0.85, c)


    else:                                            # element type without its own drawing
        p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.32, s * 0.32)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.09, s * 0.09)

def make_element_icon(key: str, theme: dict, size: int = 96, sign: int = 1) -> QIcon:
    """Icon for an element type. sign=-1 draws a sink (inward arrows) for 'source'
    and a clockwise vortex for 'vortex'."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    color_key = "el_sink" if (key == "source" and sign < 0) else _color_key(key)
    _draw(key, p, float(size), QColor(theme.get(color_key, theme["plot_axis"])), sign)
    p.end()
    return QIcon(pm)


def _color_key(key: str) -> str:
    from .element_specs import SPEC_BY_KEY
    return SPEC_BY_KEY[key].color_key if key in SPEC_BY_KEY else f"el_{key}"


def make_app_icon(theme: dict, size: int = 128) -> QIcon:
    """Program icon: the logo of the header (paper tile, streamlines around a cylinder)."""
    from .chrome import logo_pixmap
    icon = QIcon()
    for s in (16, 32, 48, size, 256):
        icon.addPixmap(logo_pixmap(theme, s))
    return icon


# tool icons of the bar above the plot: polylines in a 24 × 24 design (like the concept drawing)
_TOOL_PATHS = {
    "select": [[(5, 3), (19, 11), (12.8, 12.8), (10.8, 19), (5, 3)]],
    "pan": [[(12, 3), (12, 21)], [(3, 12), (21, 12)], [(9.5, 5.5), (12, 3), (14.5, 5.5)],
            [(9.5, 18.5), (12, 21), (14.5, 18.5)], [(5.5, 9.5), (3, 12), (5.5, 14.5)],
            [(18.5, 9.5), (21, 12), (18.5, 14.5)]],
    "fit": [[(4, 9), (4, 4), (9, 4)], [(20, 9), (20, 4), (15, 4)], [(4, 15), (4, 20), (9, 20)],
            [(20, 15), (20, 20), (15, 20)]],
    "export": [[(12, 3), (12, 15)], [(7, 10), (12, 15), (17, 10)], [(5, 21), (19, 21)]],
}


def make_tool_icon(name: str, color: str, size: int = 32) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    k = size / 24.0
    p.setPen(QPen(QColor(color), 1.9 * k, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
    for line in _TOOL_PATHS[name]:
        path = QPainterPath(QPointF(line[0][0] * k, line[0][1] * k))
        for x, y in line[1:]:
            path.lineTo(x * k, y * k)
        p.drawPath(path)
    p.end()
    return QIcon(pm)


def _palette_path(key: str) -> QPainterPath:
    """Line drawing of an element for the palette, in a 24 × 24 design (as in the theme concept)."""
    path = QPainterPath()

    def poly(*pts):
        path.moveTo(*pts[0])
        for pt in pts[1:]:
            path.lineTo(*pt)

    if key == "uniform":
        for y in (7, 12, 17):
            poly((3, y), (18, y))
            poly((15, y - 2.5), (18, y), (15, y + 2.5))
    elif key == "source":
        path.addEllipse(QPointF(12, 12), 2.6, 2.6)
        for k in range(8):
            a = k * math.pi / 4
            poly((12 + 4.5 * math.cos(a), 12 + 4.5 * math.sin(a)), (12 + 9.5 * math.cos(a), 12 + 9.5 * math.sin(a)))
    elif key == "vortex":
        path.arcMoveTo(QRectF(5, 5, 14, 14), 0)
        path.arcTo(QRectF(5, 5, 14, 14), 0, -270)       # clockwise on the screen = counter-clockwise flow
        poly((11, 2.2), (13.8, 5), (11, 7.8))
        path.addEllipse(QPointF(12, 12), 1.6, 1.6)
    elif key == "doublet":
        path.moveTo(12, 12)
        path.cubicTo(9.4, 8.4, 3.5, 8.4, 3.5, 12)
        path.cubicTo(3.5, 15.6, 9.4, 15.6, 12, 12)
        path.cubicTo(14.6, 8.4, 20.5, 8.4, 20.5, 12)
        path.cubicTo(20.5, 15.6, 14.6, 15.6, 12, 12)
    elif key == "wall":
        path.moveTo(3, 9.5)
        path.cubicTo(9, 6.5, 15, 6.5, 21, 9.5)
        poly((3, 15), (21, 15))
        for x in (6, 10.5, 15, 19.5):
            poly((x, 15), (x - 2.5, 19.5))
    elif key == "sector":
        poly((4, 4), (4, 20), (20, 20))
        path.moveTo(8.5, 4)
        path.cubicTo(8.5, 11, 13, 15.5, 20, 15.5)
    else:
        path.addEllipse(QPointF(12, 12), 7, 7)
        path.addEllipse(QPointF(12, 12), 1.6, 1.6)
    return path


def make_palette_icon(key: str, color: str, size: int = 52) -> QIcon:
    """Single-color line icon of an element type (element palette left of the plot)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    k = size / 24.0
    p.scale(k, k)
    p.setPen(QPen(QColor(color), 1.5, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPath(_palette_path(key))
    p.end()
    return QIcon(pm)
