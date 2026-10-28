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
from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from physics.surface import cylinder_cp, free_stream_angle, pressure_force, rotate_to_theta0

from .chrome import button_font, font, themed_combo
from .theme import FONT

AXES = (("theta", "θ  round the center"),
        ("s", "s  along the surface"),
        ("x", "x  along the flow"))
GRAPH_BINS = 48
RHO_DEFAULT = 1.225              # kg/m³, air at sea level


class SurfacePanel(QWidget):
    export_requested = Signal()              # "Export CSV…" (the window asks where and writes it)
    cp_reference_requested = Signal()        # "set V_ref…" link

    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.layer = None                    # the plot's SurfaceLayer (set_layer)
        self.elements = []
        self._shown = None                   # (surface as plotted, x values) for the hover ring
        lay = QVBoxLayout(self)
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

        self.graph = pg.PlotWidget()
        self.graph.setMenuEnabled(False)
        self.graph.hideButtons()
        self.graph.setMinimumHeight(240)
        self.graph.setMouseEnabled(x=False, y=False)
        self.curves = [pg.PlotCurveItem(connect="finite") for _ in range(GRAPH_BINS)]
        for c in self.curves:
            self.graph.addItem(c)
        self.exact = pg.PlotCurveItem()
        self.graph.addItem(self.exact)
        self.dot = pg.ScatterPlotItem(size=8)
        self.graph.addItem(self.dot)
        self.zero = pg.InfiniteLine(pos=0.0, angle=0)
        self.graph.addItem(self.zero)
        self.graph.scene().sigMouseMoved.connect(self._hover)
        lay.addWidget(self.graph, 1)
        self.c_suction = QCheckBox("Suction up  (−Cp up)")
        self.c_suction.setToolTip("Cp axis reversed, as usual in aerodynamics: suction (Cp < 0) on top")
        self.c_suction.setChecked(True)
        self.c_suction.toggled.connect(self._draw)
        lay.addWidget(self.c_suction)

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
        self.apply_theme(theme)

    # ------------------------------------------------------------------ wiring
    def set_layer(self, layer):
        self.layer = layer
        layer.changed.append(self.refresh)

    def set_elements(self, elements):
        self.elements = elements

    def leaveEvent(self, event):
        if self.layer is not None:
            self.layer.show_marker(None)
        self.dot.setData([], [])
        super().leaveEvent(event)

    # ------------------------------------------------------------------ appearance
    def apply_theme(self, theme):
        self.theme = t = theme
        self.graph.setBackground(t["plot_bg"])
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
                pi.setXRange(0, 360, padding=0.02)
            else:
                pi.getAxis("bottom").setTicks(None)
                pi.enableAutoRange(axis="x")
            pi.enableAutoRange(axis="y")
        self._update_info()

    def _update_info(self):
        t = self.theme
        layer = self.layer
        surf = self.current()
        v_ref = layer._v_ref() if layer is not None else None
        muted = t["text_muted"]
        link = f'<a href="vref" style="color:{t["accent"]}">set V_ref…</a>'
        if layer is None:
            text = ""
        elif not v_ref and layer.surfaces():
            text = f"Cp needs a reference speed: this scene has no uniform flow (V∞). {link}"
        elif surf is None:
            text = ("Computing the body surfaces…" if layer.computing else
                    f'<span style="color:{muted}">No surfaces here. Solid bodies appear with a uniform '
                    f"(or sector) flow and a source or doublet; symmetry walls and sector flows have walls.</span>")
        else:
            cp = surf.cp(v_ref)
            k = int(np.nanargmin(cp))
            rows = [("Cp min", f"<b>{_num(cp[k])}</b>  at ({_num(surf.z[k].real, 3)}, {_num(surf.z[k].imag, 3)})")]
            force = pressure_force(surf, self.elements, v_ref)
            rho = self.s_rho.value()
            if force is not None:
                if surf.gamma:
                    rows.append(("Γ inside", f"{_num(surf.gamma)} m²/s"))
                pairs = ((("Lift  L′/ρ", force.lift, force.kj_lift, "Kutta–Joukowski  −V∞Γ"),
                          ("Drag  D′/ρ", force.drag, 0.0 if surf.alone else None, "d'Alembert"))
                         if force.lift is not None else
                         (("F′x/ρ", force.fx, None, ""), ("F′y/ρ", force.fy, None, "")))
                scale = max(abs(force.fx), abs(force.fy), abs(force.kj_lift or 0.0), 1e-12)
                for name, value, theory, theory_name in pairs:
                    shown = 0.0 if abs(value) < 1e-5 * scale else value
                    rows.append((name, f"<b>{_num(shown)}</b> m³/s²   ({_num(shown * rho)} N/m)"))
                    if theory is not None:
                        diff = abs(value - theory) / scale * 100.0
                        rows.append((f'<span style="color:{muted}">{theory_name}</span>',
                                     f'<span style="color:{muted}">{_num(theory)}   (difference {diff:.2g} %)</span>'))
            cells = "".join(f'<tr><td style="padding-right:8px">{a}</td><td>{b}</td></tr>' for a, b in rows)
            text = f"<table cellspacing='0' cellpadding='1'>{cells}</table>"
            notes = []
            if force is not None:
                notes.append("Force = pressure integral −∮ p n ds, per unit span.")
            if surf.note:
                notes.append(surf.note)
            if self.exact.xData is not None and len(self.exact.xData):
                notes.append("Dashed: analytic Cp = 1 − (2 sin θ − Γ/(2πaV∞))² of the cylinder.")
            if notes:
                text += f'<div style="color:{muted}">{" ".join(notes)}</div>'
        self.info.setText(text)

    # ------------------------------------------------------------------ hover
    def _hover(self, pos):
        if self._shown is None or self.layer is None:
            return
        vb = self.graph.getPlotItem().getViewBox()
        if not self.graph.sceneBoundingRect().contains(pos):
            return
        p = vb.mapSceneToView(pos)
        surf, x, cp = self._shown
        if not len(x):
            return
        k = int(np.nanargmin(np.abs(x - p.x())))
        self.dot.setData([x[k]], [cp[k]])
        self.layer.show_marker(complex(surf.z[k]))


def _scene_v_inf(elements):
    from physics.field import reference_speed
    return reference_speed(elements)


def _num(v, digits: int = 5) -> str:
    """A number for the panel: `digits` significant digits, a real minus sign, no "−0"."""
    if abs(v) < 1e-12:
        return "0"
    text = f"{v:.{digits}g}" if digits != 3 else f"{v:.3f}"
    return text.replace("-", "−")
