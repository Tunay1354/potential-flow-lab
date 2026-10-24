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


def make_element_icon(key: str, theme: dict, size: int = 96, sign: int = 1) -> QIcon:
    """Icon for an element type. sign=-1 draws a sink (inward arrows) for 'source'
    and a clockwise vortex for 'vortex'."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    color_key = "el_sink" if (key == "source" and sign < 0) else _color_key(key)
    _draw(key, p, float(size), QColor(theme[color_key]), sign)
    p.end()
    return QIcon(pm)


def _color_key(key: str) -> str:
    from .element_specs import SPEC_BY_KEY
    return SPEC_BY_KEY[key].color_key


def make_app_icon(theme: dict, size: int = 128) -> QIcon:
    """Program icon: a cylinder with two streamlines."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    p.setBrush(QColor(theme["accent"]))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.2, s * 0.2)
    white = QColor("#FFFFFF")
    p.setPen(QPen(white, s * 0.05, Qt.SolidLine, Qt.RoundCap))
    for sgn in (-1, 1):
        path = QPainterPath()
        path.moveTo(s * 0.1, s * (0.5 + sgn * 0.13))
        path.cubicTo(s * 0.35, s * (0.5 + sgn * 0.13), s * 0.33, s * (0.5 + sgn * 0.32),
                     s * 0.5, s * (0.5 + sgn * 0.32))
        path.cubicTo(s * 0.67, s * (0.5 + sgn * 0.32), s * 0.65, s * (0.5 + sgn * 0.13),
                     s * 0.9, s * (0.5 + sgn * 0.13))
        p.drawPath(path)
    p.setBrush(white)
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.17, s * 0.17)
    p.end()
    return QIcon(pm)
