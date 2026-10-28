"""Paket S: pressure on surfaces — Cp along body surfaces and walls (physics/surface.py), the force
from the pressure integral against Kutta–Joukowski / d'Alembert, the Surface pressure layer and panel,
and the CSV table."""
import csv

import numpy as np
import pytest

from physics import Doublet, SectorFlow, Source, SymmetryWall, Uniform, Vortex
from physics.surface import (body_surfaces, cylinder_cp, pressure_force, rotate_to_theta0,
                             wall_surfaces)


def _one(els):
    (s,) = body_surfaces(els)
    return s


# ---------------------------------------------------------------- physics
@pytest.mark.parametrize("gamma, alpha", [(0.0, 0.0), (-2.0, 0.0), (3.0, 30.0), (-15.0, 0.0)])
def test_kutta_joukowski_and_dalembert_from_the_pressure_integral(gamma, alpha):
    """Lifting cylinder (also Γ > 4πV∞a: the body is the cylinder with the ring of fluid turning with
    it): the pressure integral over the traced surface gives L′ = −ρV∞Γ and D′ = 0."""
    els = [Uniform(alpha=alpha), Doublet(mu=1.0, delta=alpha)] + ([Vortex(Gamma=gamma)] if gamma else [])
    s = _one(els)
    assert s.closed and s.alone and s.gamma == pytest.approx(gamma)
    f = pressure_force(s, els, 1.0)
    assert f.kj_lift == pytest.approx(-gamma)
    assert f.lift == pytest.approx(-gamma, abs=2e-3 * max(1.0, abs(gamma)))
    assert abs(f.drag) < 1e-3
    # the force is along the lift direction, 90° counter-clockwise from the free stream
    if gamma:
        el = 1j * np.exp(1j * np.radians(alpha))
        assert complex(f.fx, f.fy) == pytest.approx(f.lift * el, abs=2e-3 * abs(gamma))


def test_cylinder_cp_matches_the_analytic_curve():
    els = [Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)]
    s = rotate_to_theta0(_one(els))
    exact = cylinder_cp(els, s)
    assert np.max(np.abs(exact - s.cp(1.0))) < 5e-3
    th = s.theta()
    assert th[0] < 1.0 and np.all(np.diff(th) > 0)                 # 0 … 360°, counter-clockwise
    assert s.cp(1.0).min() == pytest.approx(1.0 - (2.0 + 1.0 / np.pi) ** 2, abs=5e-3)   # θ = 90°
    assert cylinder_cp([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0, x0=0.5)], s) is None    # not a cylinder


def test_closed_bodies_without_lift_and_interaction_forces():
    """Rankine oval: no force. Two cylinders one behind the other: equal and opposite forces (they
    push each other apart along the flow), sum zero — no single Kutta–Joukowski value to compare.
    Cylinder above the ground: pulled down towards the wall (ground effect)."""
    oval = [Uniform(), Source(m=2 * np.pi, x0=-1.0), Source(m=-2 * np.pi, x0=1.0)]
    f = pressure_force(_one(oval), oval, 1.0)
    assert abs(f.lift) < 1e-3 and abs(f.drag) < 1e-3
    two = [Uniform(), Doublet(mu=0.5, x0=-1.5), Doublet(mu=0.5, x0=1.5)]
    a, b = body_surfaces(two)
    fa, fb = pressure_force(a, two, 1.0), pressure_force(b, two, 1.0)
    assert fa.drag == pytest.approx(-fb.drag, abs=1e-3) and abs(fa.drag) > 0.05
    assert fa.kj_lift is None and "Other elements" in a.note
    ground = [SymmetryWall(xw=0.0, yw=0.0, theta_w=0.0, side=0), Uniform(), Doublet(mu=1.0, x0=0.0, y0=1.5)]
    g = _one(ground)
    fg = pressure_force(g, ground, 1.0)
    assert fg.lift < -0.3 and abs(fg.drag) < 1e-3 and "Walls" in g.note


def test_half_body_is_open_and_has_no_force():
    els = [Uniform(), Source(m=2.0)]
    s = _one(els)
    assert not s.closed and pressure_force(s, els, 1.0) is None and "Open body" in s.note
    nose = s.z[np.argmin(s.z.real)]
    assert nose.real == pytest.approx(-2.0 / (2 * np.pi), abs=5e-3)           # stagnation point −m/2πV∞
    assert s.cp(1.0)[np.argmin(s.z.real)] == pytest.approx(1.0, abs=0.02)


def test_wall_cp_of_a_source_near_the_ground():
    """Source m at height h above a wall: on the wall u = (m/π) x / (x² + h²) (source + its image)."""
    els = [SymmetryWall(xw=0.0, yw=0.0, theta_w=0.0, side=0), Source(m=2.0, x0=0.0, y0=1.0)]
    (w,) = wall_surfaces(els, ((-4.0, 4.0), (-1.0, 4.0)))
    assert np.allclose(w.z.imag, 0.0)
    u = (2.0 / np.pi) * w.z.real / (w.z.real ** 2 + 1.0)
    assert np.allclose(w.vel.real, u, atol=1e-9) and np.allclose(w.vel.imag, 0.0, atol=1e-9)
    assert body_surfaces(els) == []                             # no free stream: no body


def test_sector_flow_walls_and_half_body_in_a_corner():
    els = [SectorFlow(V=1.0, x0=0.0, y0=0.0, theta1=0.0, theta2=90.0), Source(m=2.0, x0=1.0, y0=1.0)]
    walls = wall_surfaces(els, ((-0.6, 3.4), (-0.6, 3.0)))
    assert len(walls) == 2 and all(np.allclose(np.abs(np.angle(w.z[w.s > 0.1])) % (np.pi / 2), 0) for w in walls)
    (body,) = body_surfaces(els)
    assert not body.closed


def test_walls_where_fluid_touches_them_only():
    """Two walls make a corner: only the parts at the fluid are surfaces."""
    els = [SymmetryWall(xw=0.0, yw=0.0, theta_w=0.0, side=0), SymmetryWall(xw=0.0, yw=0.0, theta_w=90.0, side=1),
           Source(m=2.0, x0=1.0, y0=1.0)]
    walls = wall_surfaces(els, ((-1.0, 4.0), (-1.0, 3.0)))
    assert len(walls) == 2
    assert walls[0].z.real.min() > -0.05 and walls[1].z.imag.min() > -0.05


# ---------------------------------------------------------------- the window
@pytest.fixture
def win(qapp):
    from app.main_window import MainWindow
    w = MainWindow()
    w._ask_save_changes = lambda: "discard"
    w.resize(1300, 820)
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def _points(curves) -> int:
    return sum(0 if c.getData()[0] is None else len(c.getData()[0]) for c in curves)


def _settle(w, qapp, ms=6000):
    from PySide6.QtTest import QTest
    w.canvas.wait_idle()
    for _ in range(ms // 20):
        QTest.qWait(20)
        lay = w.canvas.surfaces
        if not w.canvas.streamlines.busy and not lay.computing:
            break
    qapp.processEvents()


def test_layer_opens_the_panel_with_forces(win, qapp):
    w = win
    assert not w.dock_surface.isVisible()                       # hidden at first
    w.load_scene([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)], ((-3.0, 3.0), (-2.0, 2.0)))
    w.settings_panel.layer_boxes["surface"].setChecked(True)
    _settle(w, qapp)
    assert w.dock_surface.isVisible() and w.layer_actions["surface"].isChecked()
    lay, sp = w.canvas.surfaces, w.surface_panel
    assert [s.name for s in lay.surfaces()] == ["Body 1"]
    text = sp.info.text()
    assert "Kutta–Joukowski" in text and "2.000" in text and "d'Alembert" in text
    assert _points(lay.curves) > 500        # the colored surface on the plot
    assert _points(sp.curves) > 500         # … and the graph
    assert sp.exact.xData is not None and len(sp.exact.xData) > 100        # analytic cylinder curve
    w.settings_panel.layer_boxes["surface"].setChecked(False)
    assert not any(c.isVisible() for c in lay.curves) and w.dock_surface.isVisible()


def test_panel_axis_follows_the_surface_and_hover_marks_the_plot(win, qapp):
    from PySide6.QtCore import QPointF
    w = win
    w.dock_surface.show()
    w.load_scene([Uniform(), Source(m=2.0)], ((-2.0, 6.0), (-2.5, 2.5)))
    _settle(w, qapp)
    sp, lay = w.surface_panel, w.canvas.surfaces
    assert sp.c_surface.currentText() == "Body 1 (open)"
    assert sp.c_axis.currentData() == "x"                     # θ does not fit an open body
    vb = sp.graph.getPlotItem().getViewBox()
    sp._hover(vb.mapViewToScene(QPointF(0.0, 1.0)))
    x, y = lay.marker.getData()
    assert lay.marker.isVisible() and x[0] == pytest.approx(-1 / np.pi, abs=0.05)   # the nose
    w.load_scene([Uniform(), Doublet(mu=1.0)], ((-3.0, 3.0), (-2.0, 2.0)))
    _settle(w, qapp)
    assert sp.c_axis.currentData() == "theta"                 # the user's choice again


def test_no_reference_speed_and_the_link(win, qapp):
    w = win
    w.dock_surface.show()
    w.load_scene([SymmetryWall(xw=0.0, yw=0.0, theta_w=0.0, side=0), Source(m=2.0, x0=0.0, y0=1.0)],
                 ((-4.0, 4.0), (-1.0, 5.0)))
    _settle(w, qapp)
    sp = w.surface_panel
    assert "needs a reference speed" in sp.info.text()
    sp.info.linkActivated.emit("vref")
    assert w.settings_panel.c_cp_ref.currentIndex() == 1
    qapp.processEvents()
    assert "Lowest Cp" in sp.info.text()


def test_surface_csv(win, qapp, tmp_path):
    w = win
    w.load_scene([SymmetryWall(xw=0.0, yw=0.0, theta_w=0.0, side=0), Uniform(), Doublet(mu=1.0, x0=0.0, y0=1.5)],
                 ((-4.0, 4.0), (-0.5, 4.0)))
    _settle(w, qapp)
    path = str(tmp_path / "s.csv")
    w._ask_export_path = lambda *a, **k: path
    assert w.export_surface()                                 # computed for the export (panel closed)
    rows = list(csv.reader(open(path, encoding="utf-8-sig")))
    assert rows[0][:2] == ["surface", "kind"] and rows[0][-1] == "Cp"
    kinds = {r[0] for r in rows[1:]}
    assert {"Body 1", "Wall 1"} <= kinds
    body = [r for r in rows[1:] if r[0] == "Body 1"]
    th = [float(r[7]) for r in body]
    assert th[0] < 1.0 and th[-1] > 359.0                      # θ from 0 round to 360°


def test_export_data_dialog_offers_surface_pressure(qapp):
    from app.export import ExportDataDialog
    dlg = ExportDataDialog({})
    assert "surface" in dlg.boxes
    dlg.deleteLater()


def test_panel_does_not_make_the_window_too_wide(win, qapp):
    """1536 × 864 (a 1920 × 1080 screen at 125 %): with the panel open the window still fits."""
    w = win
    w.dock_surface.show()
    qapp.processEvents()
    assert w.minimumSizeHint().width() <= 1536 / 1.0


def test_hover_keeps_the_graph_still_and_follows_the_curve_under_the_mouse(win, qapp):
    """The hover dot used to stretch the auto range (the graph jumped at the peaks); along x the
    upper and lower surface have the same x and the ring jumped between them."""
    from PySide6.QtCore import QPointF
    w = win
    w.settings_panel.layer_boxes["surface"].setChecked(True)
    w.load_scene([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)], ((-3.0, 3.0), (-2.0, 2.0)))
    _settle(w, qapp)
    sp, lay = w.surface_panel, w.canvas.surfaces
    sp.c_axis.setCurrentIndex(sp.c_axis.findData("x"))
    sp._axis_chosen(0)
    vb = sp.graph.getPlotItem().getViewBox()
    before = vb.viewRange()
    surf, x, cp = sp._shown
    upper = surf.z.imag > 0
    for xm in np.linspace(0.2, 1.8, 40):
        k = np.nanargmin(np.where(upper, np.abs(x - xm), np.inf))
        sp._hover(vb.mapViewToScene(QPointF(xm, cp[k] + 0.05)))
        assert lay.marker.getData()[1][0] > 0                    # still on the upper surface
    assert np.allclose(vb.viewRange(), before)


def test_panel_fits_under_other_panels_and_starts_hidden(win, qapp):
    """It scrolls when short (so it can stand under / beside the other panels on the right), docks
    may nest (a second column), and it never opens by itself at the start — only with its layer."""
    from PySide6.QtWidgets import QMainWindow
    w = win
    assert w.surface_panel.minimumSizeHint().height() <= 200
    assert w.dockOptions() & QMainWindow.AllowNestedDocks
    w.dock_surface.show()
    w.save_layout()
    w.restore_layout()
    assert not w.dock_surface.isVisible()


def test_plot_background_is_not_cached(win):
    """A cached background left the last device pixel column unpainted at 125 % (a second dark line
    beside the plot card's right frame, depending on the plot width)."""
    from PySide6.QtWidgets import QGraphicsView
    assert win.canvas.plot.cacheMode() == QGraphicsView.CacheNone
    assert win.surface_panel.graph.cacheMode() == QGraphicsView.CacheNone
