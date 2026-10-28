"""
surface_panel.py — the "Surface pressure" side panel (Paket S): Cp along one surface (a body surface
or a wall) as a graph, and for a closed body the force from the pressure integral with the
Kutta–Joukowski / d'Alembert values next to it.

The surfaces come from the plot's SurfaceLayer (physics.surface); the panel only shows them. The
graph's colors are the colors of the surface on the plot. Moving the mouse over the graph puts a ring
on the plot at that point of the surface. For a (lifting) cylinder the analytic curve
Cp = 1 − (2 sin θ − Γ/(2πaV∞))² is drawn too (dashed).
"""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QSettings, QSize, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QGraphicsView, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from physics.surface import cylinder_cp, free_stream_angle, pressure_force, rotate_to_theta0

from .chrome import button_font, font, themed_combo
from .theme import FONT

AXES = (("theta", "θ  round the center"),
        ("s", "s  along the surface"),
        ("x", "x  along the flow"))
GRAPH_BINS = 48
RHO_DEFAULT = 1.225              # kg/m³, air at sea level
GRAPH_PX = 210                   # graph height: graph and numbers fit a 1080-p screen at 125 % unscrolled


class SurfacePanel(QScrollArea):
    """Scrolls when the panel is short: so it also fits under the other panels on the right."""
    export_requested = Signal()              # "Export CSV…" (the window asks where and writes it)
    cp_reference_requested = Signal()        # "set V_ref…" link

    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.layer = None                    # the plot's SurfaceLayer (set_layer)
        self.elements = []
        self._shown = None                   # (surface as plotted, x values, Cp) for the hover ring
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("DockBody")
        body.setAttribute(Qt.WA_StyledBackground, True)
        self.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(10, 4, 10, 10)
        lay.setSpacing(6)

        row = QHBoxLayout()
        row.addWidget(QLabel("Surface"))
        self.c_surface = themed_combo(QComboBox())
        self.c_surface.currentIndexChanged.connect(self._draw)
        self._chosen = None                  # the surface the user picked (kept while it exists)
        self.c_surface.activated.connect(lambda _i: setattr(self, "_chosen", self.c_surface.currentText()))
        row.addWidget(self.c_surface, 1)
        lay.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Along"))
        self.c_axis = themed_combo(QComboBox())
        for key, text in AXES:
            self.c_axis.addItem(text, key)
        self._axis_pref = "theta"            # what the user chose; shown when the surface allows it
        self.c_axis.activated.connect(self._axis_chosen)
        row.addWidget(self.c_axis, 1)
        lay.addLayout(row)

        self.c_suction = QCheckBox("Suction up  (−Cp up)")
        self.c_suction.setToolTip("Cp axis reversed, as usual in aerodynamics: suction (Cp < 0) on top")
        self.c_suction.setChecked(True)
        self.c_suction.toggled.connect(self._draw)
        lay.addWidget(self.c_suction)
        self.graph = pg.PlotWidget()
        self.graph.setCacheMode(QGraphicsView.CacheNone)        # see PlotCanvas: no unpainted pixel column
        self.graph.setMenuEnabled(False)
        self.graph.hideButtons()
        self.graph.setMinimumHeight(GRAPH_PX)
        self.graph.setMaximumHeight(GRAPH_PX)
        self.graph.setMouseEnabled(x=False, y=False)
        self.graph.getPlotItem().getViewBox().disableAutoRange()   # ranges set in _draw: the hover dot never moves them
        self.curves = [pg.PlotCurveItem(connect="finite") for _ in range(GRAPH_BINS)]
        for c in self.curves:
            self.graph.addItem(c)
        self.exact = pg.PlotCurveItem()
        self.graph.addItem(self.exact, ignoreBounds=True)
        self.dot = pg.ScatterPlotItem(size=9)
        self.dot.setZValue(10)
        self.graph.addItem(self.dot, ignoreBounds=True)
        self.zero = pg.InfiniteLine(pos=0.0, angle=0)
        self.graph.addItem(self.zero, ignoreBounds=True)
        self.graph.scene().sigMouseMoved.connect(self._hover)
        lay.addWidget(self.graph)
        self.key = QLabel("")                # what the lines are (under the graph)
        self.key.setObjectName("LayerNote")
        self.key.setWordWrap(True)
        lay.addWidget(self.key)

        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.RichText)
        self.info.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.info.linkActivated.connect(lambda _l: self.cp_reference_requested.emit())
        lay.addWidget(self.info)

        row = QHBoxLayout()
        row.addWidget(QLabel("ρ"))
        self.s_rho = QDoubleSpinBox()
        self.s_rho.setRange(0.001, 20000.0)
        self.s_rho.setDecimals(3)
        self.s_rho.setSuffix("  kg/m³")
        self.s_rho.setToolTip("Density for the forces in N/m (the pressure integral gives F′/ρ)")
        self.s_rho.setValue(float(QSettings().value("surface/rho", RHO_DEFAULT) or RHO_DEFAULT))
        self.s_rho.valueChanged.connect(lambda v: (QSettings().setValue("surface/rho", v), self._update_info()))
        row.addWidget(self.s_rho)
        row.addStretch(1)
        self.s_rho.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)     # may shrink: a narrow panel
        self.btn_export = QPushButton("Export CSV…")
        self.btn_export.setFont(button_font())
        self.btn_export.setToolTip("Cp along all surfaces (x, y, s, θ, u, v, |V|, Cp) as a CSV table")
        self.btn_export.clicked.connect(self.export_requested)
        self.btn_export.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        row.addWidget(self.btn_export)
        lay.addLayout(row)
        lay.addStretch(1)
        self.apply_theme(theme)

    def minimumSizeHint(self) -> QSize:
        """As wide as the content plus the vertical scrollbar (as the Plot settings panel), and only a
        little high: the rest scrolls (the panel fits in a column under other panels)."""
        body = self.widget().minimumSizeHint().width()
        bar = self.verticalScrollBar().sizeHint().width()
        return QSize(body + bar + 2 * self.frameWidth(), 160)

    # ------------------------------------------------------------------ wiring
    def set_layer(self, layer):
        self.layer = layer
        layer.changed.append(self.refresh)

    def set_elements(self, elements):
        self.elements = elements

    def leaveEvent(self, event):
        self._hide_marker()
        super().leaveEvent(event)

    def _hide_marker(self):
        if self.layer is not None:
            self.layer.show_marker(None)
        self.dot.setData([], [])

    # ------------------------------------------------------------------ appearance
    def apply_theme(self, theme):
        self.theme = t = theme
        self.graph.setBackground(t["plot_bg"])
        _fill_viewport(self.graph, t["plot_bg"])
        pi = self.graph.getPlotItem()
        tick = font("mono", FONT["plot_label_size_pt"] - 1)
        style = {"color": t["plot_axis"], "font-size": f"{FONT['plot_label_size_pt'] - 1}pt",
                 "font-family": tick.family()}
        for name in ("left", "bottom"):
            ax = pi.getAxis(name)
            ax.setPen(pg.mkPen(t["plot_axis"]))
            ax.setTextPen(pg.mkPen(t["plot_axis"]))
            ax.setTickFont(tick)
        pi.setLabel("left", "Cp", **style)
        self._label_style = style
        pi.showGrid(x=True, y=True, alpha=0.18)
        dash = pg.mkPen(t["ink"], width=1.4)
        dash.setDashPattern([5.0, 4.0])
        dash.setCosmetic(True)
        self.exact.setPen(dash)
        self.zero.setPen(pg.mkPen(t["plot_axis"], width=1))
        self.dot.setPen(pg.mkPen(t["ink"], width=1.5))
        self.dot.setBrush(pg.mkBrush(t["panel_bg"]))
        self._draw()

    # ------------------------------------------------------------------ content
    def refresh(self):
        """New surfaces or colors (SurfaceLayer.changed): the list, the graph and the numbers."""
        surfaces = self.layer.surfaces() if self.layer is not None else []
        names = [s.name for s in surfaces]
        self.c_surface.blockSignals(True)
        self.c_surface.clear()
        self.c_surface.addItems(names)
        if self._chosen in names:                      # else the first one (a body before the walls)
            self.c_surface.setCurrentIndex(names.index(self._chosen))
        self.c_surface.blockSignals(False)
        self._draw()

    def current(self):
        if self.layer is None:
            return None
        surfaces = self.layer.surfaces()
        k = self.c_surface.currentIndex()
        return surfaces[k] if 0 <= k < len(surfaces) else None

    def _axis_chosen(self, _index):
        self._axis_pref = self.c_axis.currentData()
        self._draw()

    def _axis_for(self, surf) -> str:
        """The x axis used for `surf`: the user's choice if it fits (θ only for closed bodies, a wall
        only has s), else x along the flow (open body) or s (wall)."""
        key = self._axis_pref
        if surf is None:
            return key
        if surf.kind == "wall":
            return "s"
        if key == "theta" and not surf.closed:
            return "x"
        return key

    def _x_values(self, surf, alpha, key):
        if surf.kind == "wall":
            return surf.s, "s  [m]  along the wall"
        if key == "theta":
            return surf.theta(alpha), "θ  [°]"
        if key == "x":
            return surf.along_flow(alpha), "x  [m]  from the nose"
        return surf.s, "s  [m]  along the surface"

    def _draw(self, *_):
        if not hasattr(self, "_label_style"):
            return
        for c in self.curves:
            c.setData([], [])
        self.exact.setData([], [])
        self.dot.setData([], [])
        self._shown = None
        surf = self.current()
        layer = self.layer
        v_ref = layer._v_ref() if layer is not None else None
        model = self.c_axis.model()
        for i, (key, _text) in enumerate(AXES):        # θ only for closed bodies, nothing but s for walls
            ok = surf is None or (surf.kind == "body" and (key != "theta" or surf.closed)) or key == "s"
            model.item(i).setEnabled(bool(ok))
        axis = self._axis_for(surf)
        self.c_axis.blockSignals(True)
        self.c_axis.setCurrentIndex(self.c_axis.findData(axis))
        self.c_axis.blockSignals(False)
        if surf is not None and v_ref:
            alpha = free_stream_angle(self.elements)
            if axis == "theta":
                surf = rotate_to_theta0(surf, alpha)
            x, label = self._x_values(surf, alpha, axis)
            cp = surf.cp(v_ref)
            self._shown = (surf, x, cp)
            colors = layer.color_of(cp) if layer is not None else [(0, 0, 0)] * cp.size
            # one curve per color (segments of neighbouring points; θ wraps at 360°: no segment there)
            jump = np.abs(np.diff(x)) > 0.5 * (np.nanmax(x) - np.nanmin(x)) if x.size > 1 else np.zeros(0, bool)
            mid_colors = colors[:-1]
            order = {}
            for k, c in enumerate(mid_colors):
                if not jump[k]:
                    order.setdefault(c, []).append(k)
            for curve, (c, idx) in zip(self.curves, sorted(order.items(), key=lambda kv: -len(kv[1]))):
                idx = np.asarray(idx)
                xs = np.empty(3 * idx.size)
                ys = np.empty(3 * idx.size)
                xs[0::3], xs[1::3], xs[2::3] = x[idx], x[idx + 1], np.nan
                ys[0::3], ys[1::3], ys[2::3] = cp[idx], cp[idx + 1], np.nan
                pen = pg.mkPen(c, width=2.6)
                pen.setCosmetic(True)
                curve.setData(xs, ys, pen=pen)
            exact = cylinder_cp(self.elements, surf) if axis == "theta" else None
            if exact is not None and v_ref:
                ref = _scene_v_inf(self.elements)
                if ref:
                    exact = 1.0 - (1.0 - exact) * (ref / v_ref) ** 2          # the same reference speed
                    self.exact.setData(x, exact, connect=np.append(~jump, False))
            pi = self.graph.getPlotItem()
            pi.setLabel("bottom", label, **self._label_style)
            pi.invertY(self.c_suction.isChecked())
            if axis == "theta":
                pi.getAxis("bottom").setTicks([[(v, f"{v:g}") for v in range(0, 361, 90)]])
                x0, x1 = 0.0, 360.0
            else:
                pi.getAxis("bottom").setTicks(None)
                x0, x1 = float(np.nanmin(x)), float(np.nanmax(x))
            ys = cp[np.isfinite(cp)]
            if exact is not None:
                ys = np.concatenate([ys, exact[np.isfinite(exact)]])
            y0, y1 = (float(ys.min()), float(ys.max())) if ys.size else (-1.0, 1.0)
            y0, y1 = min(y0, 0.0), max(y1, 1.0)                     # Cp = 0 and 1 always in view
            # fixed ranges (not auto): the hover dot must never change them
            pi.getViewBox().setRange(xRange=(x0, x1), yRange=(y0, y1), padding=0.04)
            key = "Colored: Cp on the surface (colors as on the plot)."
            if exact is not None:
                key += "  Dashed: analytic Cp = 1 − (2 sin θ − Γ/2πaV∞)²."
            self.key.setText(key)
        else:
            self.key.setText("")
        self._update_info()

    def _update_info(self):
        """The numbers under the graph, in short sections (each line fits a narrow panel):
            CP ON THE SURFACE   lowest Cp and where
            FORCE (per unit span, from the pressure integral)
              Lift L′ … N/m      and below it, small: the theory's value and the difference
              Drag D′ … N/m
              Γ inside the body
            notes (why there is no comparison, …)"""
        t = self.theme
        layer = self.layer
        surf = self.current()
        v_ref = layer._v_ref() if layer is not None else None
        muted, good = t["text_muted"], t["el_sector"]
        link = f'<a href="vref" style="color:{t["accent"]}">set V_ref…</a>'
        if layer is None:
            self.info.setText("")
            return
        if not v_ref and layer.surfaces():
            self.info.setText(f"Cp needs a reference speed: this scene has no uniform flow (V∞).<br>{link}")
            return
        if surf is None:
            self.info.setText("Computing the body surfaces…" if layer.computing else
                              f'<span style="color:{muted}">No surfaces here. Solid bodies come with a uniform '
                              f"(or sector) flow and a source or doublet; walls are surfaces too.</span>")
            return
        alpha = free_stream_angle(self.elements)
        cp = surf.cp(v_ref)
        k = int(np.nanargmin(cp))
        if surf.closed:
            where = f"at θ = {surf.theta(alpha)[k]:.0f}°"
        else:
            where = f"at ({_num(surf.z[k].real, 3)}, {_num(surf.z[k].imag, 3)})"
        rows = [_head("Cp on the surface", t),
                _row("Lowest Cp", f"<b>{_num(cp[k], 4)}</b>&nbsp;&nbsp;{where}")]
        if surf.kind == "wall":                          # (a body: 1, at its stagnation point)
            rows.append(_row("Highest Cp", f"<b>{_num(np.nanmax(cp), 4)}</b>"))
        force = pressure_force(surf, self.elements, v_ref)
        notes = []
        if force is not None:
            rho = self.s_rho.value()
            rows.append(_head("Force per unit span", t, "from the pressure integral −∮ p n ds"))
            scale = max(abs(force.fx), abs(force.fy), abs(force.kj_lift or 0.0), 1e-12)
            if force.lift is not None:
                items = (("Lift L′", force.lift, force.kj_lift, "Kutta–Joukowski −ρV∞Γ"),
                         ("Drag D′", force.drag, 0.0 if surf.alone else None, "d'Alembert"))
            else:
                items = (("Force F′x", force.fx, None, ""), ("Force F′y", force.fy, None, ""))
            for name, value, theory, theory_name in items:
                value = 0.0 if abs(value) < 1e-5 * scale else value
                rows.append(_row(name, f"<b>{_num(value * rho, 4)}</b> N/m"))
                if theory is not None:
                    diff = abs(value - theory) / scale * 100.0
                    mark = f'<span style="color:{good}">✓</span> ' if diff < 1.0 else ""
                    rows.append(_row("", f'<span style="color:{muted}">{theory_name}: {_num(theory * rho, 4)} N/m'
                                         f"<br>{mark}difference {diff:.2g} %</span>", small=True))
            if surf.gamma:
                rows.append(_row("Γ inside", f"{_num(surf.gamma, 4)} m²/s"))
            a, b = (force.lift, force.drag) if force.lift is not None else (force.fx, force.fy)
            names = ("L′/ρ", "D′/ρ") if force.lift is not None else ("F′x/ρ", "F′y/ρ")
            a, b = (0.0 if abs(v) < 1e-5 * scale else v for v in (a, b))
            notes.append(f"With ρ = {_num(rho, 4)} kg/m³ (set below). Without ρ: {names[0]} = {_num(a)}, "
                         f"{names[1]} = {_num(b)} m³/s².")
        if surf.note:
            notes.append(surf.note)
        text = "<table cellspacing='0' cellpadding='0' width='100%'>" + "".join(rows) + "</table>"
        if notes:
            text += "".join(f'<p style="color:{muted}; margin-top:6px">{n}</p>' for n in notes)
        self.info.setText(text)

    # ------------------------------------------------------------------ hover
    def _hover(self, pos):
        if self._shown is None or self.layer is None:
            return
        vb = self.graph.getPlotItem().getViewBox()
        if not vb.sceneBoundingRect().contains(pos):
            self._hide_marker()
            return
        p = vb.mapSceneToView(pos)
        surf, x, cp = self._shown
        if not len(x):
            return
        # the point nearest to the mouse ON THE SCREEN (x and Cp in pixels): along x alone the upper and
        # lower surface (same x) took turns and the ring jumped between them
        pw, ph = vb.viewPixelSize()
        d = ((x - p.x()) / max(pw, 1e-300)) ** 2 + ((cp - p.y()) / max(ph, 1e-300)) ** 2
        k = int(np.nanargmin(d))
        self.dot.setData([x[k]], [cp[k]])
        self.layer.show_marker(complex(surf.z[k]))


def _fill_viewport(view, color):
    """The view's own pixels in the plot color, also the last device pixel column at a fractional
    display scale (125 %), which the view's background drawing can leave out."""
    from PySide6.QtGui import QColor, QPalette
    vp = view.viewport()
    pal = vp.palette()
    pal.setColor(QPalette.Window, QColor(color))
    pal.setColor(QPalette.Base, QColor(color))
    vp.setPalette(pal)
    vp.setAutoFillBackground(True)


def _scene_v_inf(elements):
    from physics.field import reference_speed
    return reference_speed(elements)


def _head(title, theme, sub="") -> str:
    """A section title row: small capitals in the accent color over a thin rule (as the panel titles)."""
    sub = f'<br><span style="color:{theme["text_muted"]}; font-size:8pt">{sub}</span>' if sub else ""
    return (f'<tr><td colspan="2" style="padding-top:8px; padding-bottom:3px; border-bottom:1px solid '
            f'{theme["border_soft"]}"><span style="color:{theme["accent"]}; font-weight:600; '
            f'letter-spacing:1px">{title.upper()}</span>{sub}</td></tr>')


def _row(name, value, small=False) -> str:
    size = "font-size:8.5pt; " if small else ""
    return (f'<tr><td style="padding:2px 10px 2px 0; white-space:nowrap; vertical-align:top">{name}</td>'
            f'<td style="padding:2px 0; {size}vertical-align:top">{value}</td></tr>')


def _num(v, digits: int = 5) -> str:
    """A number for the panel: `digits` significant digits, a real minus sign, no "−0"."""
    if abs(v) < 1e-12:
        return "0"
    text = f"{v:.{digits}g}" if digits != 3 else f"{v:.3f}"
    if "e" in text:
        text = f"{v:.2e}"
    return text.replace("-", "−")
