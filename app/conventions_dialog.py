"""
conventions_dialog.py — Help → Sign conventions: how the program reads every sign and angle, one card per
element (a small figure drawn in code, the complex potential, what + and − mean), with the general
definitions above and pressure / forces below. Colours from the theme (the element colours of the plot).
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from .chrome import heading_font

FIG = 112                          # px: the square figure of a card
COLUMNS = 3                        # cards side by side (two rows: everything visible on a 1536 × 864 screen)
DEMO_ALPHA = 30.0                  # the angles the figures show (degrees)
DEMO_WALL = 20.0

# (key, name, formula (rich text), rules (rich text lines)); {pos} / {neg} / {el} are filled with theme colours
CARDS = [
    ("uniform", "Uniform flow", "F(z) = V<sub>∞</sub> e<sup>−iα</sup> z",
     ["<b>α</b> — the direction the flow goes, counter-clockwise from +x (α = 90°: upwards)",
      "<b>V<sub>∞</sub></b> — the speed (V<sub>∞</sub> &gt; 0)"]),
    ("source", "Source / sink", "F(z) = (m / 2π) log(z − z<sub>0</sub>)",
     ["<b style='color:{pos}'>m &gt; 0</b> — source: the fluid flows out",
      "<b style='color:{neg}'>m &lt; 0</b> — sink: the fluid flows in",
      "|m| — volume flow rate per unit depth (m²/s)"]),
    ("vortex", "Vortex", "F(z) = −i (Γ / 2π) log(z − z<sub>0</sub>)",
     ["<b style='color:{el}'>Γ &gt; 0</b> — counter-clockwise",
      "<b>Γ &lt; 0</b> — clockwise",
      "speed round it: u<sub>θ</sub> = Γ / (2π r)"]),
    ("doublet", "Doublet", "F(z) = μ e<sup>iδ</sup> / (z − z<sub>0</sub>)",
     ["<b>δ</b> — turns the doublet counter-clockwise; δ = 0 as in the course notes",
      "with a uniform flow: a cylinder of radius a = √(μ / V<sub>∞</sub>) when <b>δ = α</b> "
      "(μ &lt; 0: δ = α + 180°)"]),
    ("sector", "Sector (wedge) flow", "F(z) = V [(z − z<sub>0</sub>) e<sup>−iθ₁</sup>]<sup>n</sup>",
     ["<b>β = θ₂ − θ₁</b> — the opening, counter-clockwise (0° &lt; β ≤ 360°); n = π / β",
      "<b style='color:{el}'>V &gt; 0</b> — in along the θ₂ wall, out along the θ₁ wall; "
      "<b>V &lt; 0</b> — the other way"]),
    ("wall", "Symmetry wall", "F<sub>total</sub>(z) = F(z) + conj F(z*)  (mirror images)",
     ["<b>θ<sub>w</sub></b> — the wall's direction, counter-clockwise from +x",
      "<b>fluid side</b> — left or right of that direction, looking along θ<sub>w</sub>",
      "V·n = 0 on the wall (method of images)"]),
]

BASICS = [   # (what, formula, note)
    ("Complex potential", "F(z) = φ + iψ,   w = dF/dz = u − iv", "z = x + iy;  V = |w|"),
    ("Angles", "", "in degrees, counter-clockwise from the +x axis"),
    ("Streamlines", "ψ = const", "the φ lines (equipotentials) cross them at right angles"),
]

PRESSURE = [
    ("Pressure coefficient", "C<sub>p</sub> = 1 − (V / V<sub>ref</sub>)²",
     "V<sub>ref</sub> = V<sub>∞</sub> of the uniform flow (or Plot settings → Computation → Cp reference); "
     "C<sub>p</sub> = 1 at a stagnation point, C<sub>p</sub> &lt; 0 is suction"),
    ("Forces per unit depth", "L′ = −ρ V<sub>∞</sub> Γ",
     "lift across the free stream (90° counter-clockwise from it), drag along it; a clockwise "
     "Γ &lt; 0 lifts upwards; no drag (d'Alembert)"),
]


class ConventionFigure(QWidget):
    """The small figure of one card, drawn in a [−1, 1]² frame with y upwards."""

    def __init__(self, key: str, theme: dict, parent=None):
        super().__init__(parent)
        self.key, self.t = key, theme
        self.setFixedSize(FIG, FIG)

    def sizeHint(self) -> QSize:
        return QSize(FIG, FIG)

    # ------------------------------------------------------------------ helpers (math coordinates)
    def _pt(self, x: float, y: float) -> QPointF:
        h = FIG / 2.0
        return QPointF(h + x * (h - 8), h - y * (h - 8))

    def _c(self, key: str) -> QColor:
        return QColor(self.t[key])

    def _line(self, p, a, b, color: QColor, w=1.6, dash=False):
        pen = QPen(color, w, Qt.DashLine if dash else Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(self._pt(*a), self._pt(*b))

    def _head(self, p, tip, ang: float, color: QColor, size=7.0):
        """Arrow head at `tip` (math coords) pointing at `ang` (radians, math)."""
        t = self._pt(*tip)
        pts = [t]
        for s in (+0.45, -0.45):
            pts.append(QPointF(t.x() - size * math.cos(ang + s), t.y() + size * math.sin(ang + s)))
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawPolygon(QPolygonF(pts))
        p.setBrush(Qt.NoBrush)

    def _arrow(self, p, a, b, color: QColor, w=1.6):
        self._line(p, a, b, color, w)
        self._head(p, b, math.atan2(b[1] - a[1], b[0] - a[0]), color)

    def _arc(self, p, r: float, a0: float, a1: float, color: QColor, center=(0.0, 0.0), arrow=False, w=1.2):
        """Arc of radius r (math units) from angle a0 to a1 (degrees, counter-clockwise if a1 > a0)."""
        path = QPainterPath()
        n = 32
        for k in range(n + 1):
            a = math.radians(a0 + (a1 - a0) * k / n)
            q = self._pt(center[0] + r * math.cos(a), center[1] + r * math.sin(a))
            path.moveTo(q) if k == 0 else path.lineTo(q)
        p.setPen(QPen(color, w))
        p.drawPath(path)
        if arrow:
            a = math.radians(a1)
            tang = a + (math.pi / 2 if a1 > a0 else -math.pi / 2)
            self._head(p, (center[0] + r * math.cos(a), center[1] + r * math.sin(a)), tang, color, 6.0)

    def _text(self, p, x, y, text, color: QColor, size=8.5, italic=True, align=Qt.AlignCenter):
        f = QFont("Cambria Math")
        f.setFamilies(["Cambria Math", "STIX Two Math", "Times New Roman", "serif"])
        f.setPointSizeF(size)
        f.setItalic(italic)
        p.setFont(f)
        p.setPen(color)
        c = self._pt(x, y)
        p.drawText(QRectF(c.x() - 40, c.y() - 9, 80, 18), align, text)

    def _hatch(self, p, a, b, side: float, color: QColor, n=7):
        """Short hatch marks on one side of the segment a-b (side +1: left of a→b, −1: right)."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        nx, ny = -dy / L * side, dx / L * side
        p.setPen(QPen(color, 1.0))
        for k in range(1, n + 1):
            s = k / (n + 1)
            x, y = a[0] + dx * s, a[1] + dy * s
            p.drawLine(self._pt(x, y), self._pt(x + 0.12 * nx - 0.08 * dx / L, y + 0.12 * ny - 0.08 * dy / L))

    # ------------------------------------------------------------------ the figures
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), self._c("plot_bg"))
        p.setPen(QPen(self._c("border_soft"), 1))
        p.drawRect(QRectF(0.5, 0.5, FIG - 1, FIG - 1))
        getattr(self, f"_fig_{self.key}")(p)
        p.end()

    def _axes(self, p, origin=(0.0, 0.0), length=0.8):
        muted = self._c("text_muted")
        self._line(p, origin, (origin[0] + length, origin[1]), muted, 1.0, dash=True)
        self._text(p, origin[0] + length + 0.08, origin[1] - 0.12, "+x", muted, 7.5, italic=False)

    def _fig_uniform(self, p):
        c, ink = self._c("el_uniform"), self._c("ink")
        a = math.radians(DEMO_ALPHA)
        d = (math.cos(a), math.sin(a))
        n = (-d[1], d[0])
        for k in (0, 1, 2):                                         # the flow, upper right
            o = (-0.45 + 0.30 * k * n[0] + 0.1 * k, -0.05 + 0.30 * k * n[1])
            self._arrow(p, o, (o[0] + 1.05 * d[0], o[1] + 1.05 * d[1]), c)
        o = (-0.8, -0.72)                                           # the angle, lower left
        self._axes(p, o, 1.25)
        self._line(p, o, (o[0] + 0.95 * d[0], o[1] + 0.95 * d[1]), ink, 1.0)
        self._arc(p, 0.62, 0.0, DEMO_ALPHA, ink, center=o)
        self._text(p, o[0] + 0.82 * math.cos(a / 2), o[1] + 0.82 * math.sin(a / 2), "α", ink, 10)

    def _fig_source(self, p):
        for cx, sign, key, label in ((-0.45, 1, "el_source", "m > 0"), (0.45, -1, "el_sink", "m < 0")):
            c = self._c(key)
            for k in range(6):
                a = k * math.pi / 3 + math.pi / 6
                u = (math.cos(a), math.sin(a))
                if sign > 0:
                    self._arrow(p, (cx + 0.12 * u[0], 0.1 + 0.12 * u[1]), (cx + 0.38 * u[0], 0.1 + 0.38 * u[1]), c, 1.4)
                else:
                    self._arrow(p, (cx + 0.40 * u[0], 0.1 + 0.40 * u[1]), (cx + 0.15 * u[0], 0.1 + 0.15 * u[1]), c, 1.4)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(self._pt(cx, 0.1), 3.2, 3.2)
            p.setBrush(Qt.NoBrush)
            self._text(p, cx, -0.62, label, c, 8.5)

    def _fig_vortex(self, p):
        c, muted = self._c("el_vortex"), self._c("text_muted")
        for r in (0.35, 0.62):
            self._arc(p, r, -60.0, 230.0, c if r > 0.5 else muted, arrow=True, w=1.6 if r > 0.5 else 1.0)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(self._pt(0, 0), 3.2, 3.2)
        p.setBrush(Qt.NoBrush)
        self._text(p, 0.0, -0.82, "Γ > 0", c, 8.5)

    def _fig_doublet(self, p):
        c, ink, flow = self._c("el_doublet"), self._c("ink"), self._c("el_uniform")
        a = math.radians(DEMO_ALPHA)
        d = (math.cos(a), math.sin(a))
        z = (0.12, 0.12)                                            # the doublet (and the cylinder) here
        p.setPen(QPen(self._c("body_edge"), 1.2, Qt.DashLine))
        r = 0.4 * (FIG / 2 - 8)
        p.drawEllipse(self._pt(*z), r, r)
        o = (-0.95, -0.55)                                          # the free stream at α, coming in
        self._arrow(p, o, (o[0] + 0.55 * d[0], o[1] + 0.55 * d[1]), flow, 1.4)
        self._text(p, o[0] + 0.32, o[1] - 0.2, "α", flow, 9)
        self._line(p, (z[0] - 0.6 * d[0], z[1] - 0.6 * d[1]), (z[0] + 0.6 * d[0], z[1] + 0.6 * d[1]), c, 1.6)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(self._pt(*z), 3.2, 3.2)
        p.setBrush(Qt.NoBrush)
        self._line(p, z, (z[0] + 0.8, z[1]), self._c("text_muted"), 1.0, dash=True)
        self._arc(p, 0.62, 0.0, DEMO_ALPHA, ink, center=z)
        self._text(p, z[0] + 0.76 * math.cos(a / 2) + 0.05, z[1] + 0.76 * math.sin(a / 2), "δ", ink, 10)
        self._text(p, 0.35, -0.82, "δ = α", ink, 8.5)

    def _fig_sector(self, p):
        c, ink, wall = self._c("el_sector"), self._c("ink"), self._c("el_wall")
        o = (-0.72, -0.72)
        e1 = (0.9, -0.72)                                           # θ₁ wall along +x
        e2 = (-0.72, 0.9)                                           # θ₂ wall at 90°
        self._line(p, o, e1, wall, 2.2)
        self._line(p, o, e2, wall, 2.2)
        self._hatch(p, o, e1, -1, wall)
        self._hatch(p, o, e2, +1, wall)
        path = QPainterPath()                                       # a streamline: xy = const (β = 90°)
        pts = []
        for k in range(40):
            s = 0.18 + 1.4 * k / 39
            x, y = s, 0.36 / s
            pts.append((o[0] + x, o[1] + y))
        pts = [q for q in pts if q[0] <= 0.85 and q[1] <= 0.85]
        for k, q in enumerate(reversed([q for q in pts])):
            path.moveTo(self._pt(*q)) if k == 0 else path.lineTo(self._pt(*q))
        p.setPen(QPen(c, 1.6))
        p.drawPath(path)
        q0, q1 = pts[-2], pts[-1]                                   # flows out along θ₁ (to +x)
        self._head(p, q1, math.atan2(q1[1] - q0[1], q1[0] - q0[0]), c)
        self._arc(p, 0.38, 0.0, 90.0, ink, center=o)
        self._text(p, o[0] + 0.42, o[1] + 0.42, "β", ink, 10)
        self._text(p, 0.62, -0.88, "θ₁", ink, 8.5)
        self._text(p, -0.48, 0.8, "θ₂", ink, 8.5)

    def _fig_wall(self, p):
        wall, ink, muted = self._c("el_wall"), self._c("ink"), self._c("text_muted")
        a = math.radians(DEMO_WALL)
        d = (math.cos(a), math.sin(a))
        o = (-0.85, -0.45)
        e = (o[0] + 1.7 * d[0], o[1] + 1.7 * d[1])
        self._line(p, o, e, wall, 2.4)
        k0 = 0.42                                                   # (the angle's room near the start)
        self._hatch(p, (o[0] + k0 * (e[0] - o[0]), o[1] + k0 * (e[1] - o[1])), e, -1, wall, n=6)   # solid side
        self._arrow(p, (o[0] + 0.55 * d[0] - 0.22 * d[1], o[1] + 0.55 * d[1] + 0.22 * d[0]),
                    (o[0] + 1.25 * d[0] - 0.22 * d[1], o[1] + 1.25 * d[1] + 0.22 * d[0]), ink, 1.2)
        self._line(p, o, (o[0] + 0.7, o[1]), muted, 1.0, dash=True)
        self._arc(p, 0.5, 0.0, DEMO_WALL, ink, center=o)
        self._text(p, o[0] + 0.72, o[1] + 0.1, "θ", ink, 9)
        self._text(p, 0.05, 0.55, "fluid (left)", self._c("el_uniform"), 8.0, italic=False)


class ConventionsDialog(QDialog):
    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self.t = theme
        self.setWindowTitle("Sign conventions")
        self.setObjectName("Conventions")
        t = theme
        self.setStyleSheet(f"""
            QFrame#ConvCard {{ background: {t['panel_bg']}; border: 1px solid {t['border']}; }}
            QFrame#ConvCard QLabel {{ background: transparent; border: none; }}
            QLabel#ConvName {{ color: {t['text']}; }}
            QLabel#ConvFormula {{ font-family: "Cambria Math", "STIX Two Math", "Times New Roman", serif;
                font-size: 12pt; color: {t['text']}; }}
            QLabel#ConvRule {{ color: {t['text_muted']}; }}
            QLabel#ConvKey {{ color: {t['text']}; font-weight: 600; }}
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 12)
        outer.setSpacing(8)
        head = QLabel("Sign conventions")
        head.setObjectName("DialogTitle")
        sub = QLabel("How the program reads every sign and angle — the conventions of the course notes.")
        sub.setObjectName("Muted")
        outer.addWidget(head)
        outer.addWidget(sub)

        body = QWidget()
        body.setObjectName("ConvBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(8)
        lay.addWidget(self._table_card("BASICS", BASICS))
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        for k, (key, name, formula, rules) in enumerate(CARDS):
            grid.addWidget(self._element_card(key, name, formula, rules), k // COLUMNS, k % COLUMNS)
        lay.addLayout(grid)
        lay.addWidget(self._table_card("PRESSURE AND FORCES", PRESSURE))
        lay.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(body)
        body.setStyleSheet("QWidget#ConvBody { background: transparent; }")
        outer.addWidget(scroll, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        close = QPushButton("Close")
        close.setObjectName("Primary")
        close.setDefault(True)
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(self.accept)
        row.addWidget(close)
        outer.addLayout(row)
        self.resize(1180, 720)

    def _colors(self, key: str) -> dict:
        t = self.t
        el = {"uniform": "el_uniform", "source": "el_source", "vortex": "el_vortex", "doublet": "el_doublet",
              "sector": "el_sector", "wall": "el_wall"}[key]
        return {"pos": t["el_source"], "neg": t["el_sink"], "el": t[el]}

    def _card(self) -> QFrame:
        f = QFrame()
        f.setObjectName("ConvCard")
        return f

    def _element_card(self, key, name, formula, rules) -> QFrame:
        card = self._card()
        h = QHBoxLayout(card)
        h.setContentsMargins(10, 10, 12, 10)
        h.setSpacing(12)
        h.addWidget(ConventionFigure(key, self.t), 0, Qt.AlignTop)
        v = QVBoxLayout()
        v.setSpacing(4)
        title = QLabel(name.upper())
        title.setObjectName("ConvName")
        title.setFont(heading_font(11))
        bar = QFrame()
        bar.setFixedHeight(2)
        bar.setStyleSheet(f"background: {self._colors(key)['el']}; border: none;")
        f = QLabel(formula)
        f.setObjectName("ConvFormula")
        f.setTextFormat(Qt.RichText)
        f.setWordWrap(True)
        v.addWidget(title)
        v.addWidget(bar)
        v.addWidget(f)
        col = self._colors(key)
        for r in rules:
            lab = QLabel("•&nbsp; " + r.format(**col))
            lab.setObjectName("ConvRule")
            lab.setTextFormat(Qt.RichText)
            lab.setWordWrap(True)
            v.addWidget(lab)
        v.addStretch(1)
        h.addLayout(v, 1)
        return card

    def _table_card(self, title: str, rows) -> QFrame:
        """A full-width card: what | formula | note, one row each."""
        card = self._card()
        g = QGridLayout(card)
        g.setContentsMargins(14, 8, 14, 8)
        g.setHorizontalSpacing(18)
        g.setVerticalSpacing(2)
        head = QLabel(title)
        head.setObjectName("ConvName")
        head.setFont(heading_font(11))
        g.addWidget(head, 0, 0, 1, 3)
        for k, (key, formula, note) in enumerate(rows, start=1):
            a = QLabel(key)
            a.setObjectName("ConvKey")
            b = QLabel(formula)
            b.setObjectName("ConvFormula")
            b.setTextFormat(Qt.RichText)
            c = QLabel(note)
            c.setObjectName("ConvRule")
            c.setTextFormat(Qt.RichText)
            c.setWordWrap(True)
            g.addWidget(a, k, 0, Qt.AlignVCenter)
            g.addWidget(b, k, 1, Qt.AlignVCenter)
            g.addWidget(c, k, 2, Qt.AlignVCenter)
        g.setColumnStretch(2, 1)
        return card
