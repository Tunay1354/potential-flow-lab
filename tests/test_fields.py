"""Phase 4: field layers — equipotential lines φ, |V| and Cp color bands with a legend — and the
Computation settings (grid quality, Cp reference) that are saved with the scene."""
import numpy as np
import pytest


@pytest.fixture
def fl(qapp):
    import pyqtgraph as pg
    from app.canvas.field_layer import FieldLayer
    from app.theme import LIGHT
    pw = pg.PlotWidget()
    layers = FieldLayer(pw, pw.getPlotItem().getViewBox())
    layers.apply_theme(LIGHT)
    yield layers
    pw.close()
    pw.deleteLater()                       # deleted now, not by a later garbage collection
    qapp.processEvents()


VIEW = ((-4.0, 4.0), (-3.0, 3.0))


def _lines(item):
    x, y = item.getData()
    xy = np.column_stack([x, y])
    cuts = np.where(~np.isfinite(xy[:, 0]))[0]
    out, start = [], 0
    for c in list(cuts) + [len(xy)]:
        if c - start > 1:
            out.append(xy[start:c])
        start = c + 1
    return out


def test_nice_step():
    from app.canvas.contours import nice_step
    assert nice_step(2.2, 12) == pytest.approx(0.2)
    assert nice_step(4.5, 12) == pytest.approx(0.5)
    assert nice_step(30, 12) == pytest.approx(2.5)


def test_uniform_flow_equipotentials_are_straight_and_evenly_spaced(fl):
    from physics import Uniform
    fl.update([Uniform(V=1.0)], VIEW, {"equipotential": True})
    lines = _lines(fl.phi)
    assert len(lines) > 10
    xs = sorted(np.mean(ln[:, 0]) for ln in lines)
    assert all(np.ptp(ln[:, 0]) < 1e-6 for ln in lines)              # x = const (φ = V x)
    gaps = np.diff(xs)
    assert np.ptp(gaps) < 1e-6                                       # same spacing everywhere


def test_equipotentials_cross_streamlines_at_right_angles(fl):
    from physics import Doublet, Uniform, velocity
    els = [Uniform(), Doublet(mu=1.0)]
    fl.update(els, VIEW, {"equipotential": True})
    cosines = []
    for ln in _lines(fl.phi):
        t = np.diff(ln, axis=0)
        mid = 0.5 * (ln[1:] + ln[:-1])
        u, v = velocity(els, mid[:, 0], mid[:, 1])
        sp, tl = np.hypot(u, v), np.hypot(t[:, 0], t[:, 1])
        ok = (sp > 1e-6) & (tl > 1e-9)
        cosines.append(np.abs(t[ok, 0] * u[ok] + t[ok, 1] * v[ok]) / (tl[ok] * sp[ok]))
    cos = np.concatenate(cosines)
    assert np.median(cos) < 0.01 and np.percentile(cos, 95) < 0.05   # tangent ⟂ velocity (grid accuracy)


def test_no_false_lines_along_a_vortex_branch_cut(fl):
    from physics import Uniform, Vortex
    fl.update([Uniform(), Vortex(Gamma=3.0)], VIEW, {"equipotential": True})
    lines = _lines(fl.phi)
    assert lines
    step = max(np.max(np.hypot(*np.diff(ln, axis=0).T)) for ln in lines)
    assert step < 0.2                                                # no long jumps across the cut
    # near the negative x-axis (the cut of log z) there is no crowd of short lines
    near_cut = [ln for ln in lines if np.all(np.abs(ln[:, 1]) < 0.05) and np.all(ln[:, 0] < -0.5)]
    assert len(near_cut) <= 2


def test_speed_bands_and_legend(fl):
    from PySide6.QtCore import QPointF
    from physics import Doublet, Uniform, velocity
    els = [Uniform(), Doublet(mu=1.0)]
    fl.update(els, VIEW, {"speed": True})
    edges = fl.legend.edges
    assert edges[0] == 0.0 and len(fl.legend.colors) == len(edges) - 1 and fl.legend.isVisible()
    assert fl.bands and fl.legend.title.startswith("|V|")
    # a point far upstream (|V| ≈ 1) lies in the band whose edges contain 1
    u, v = velocity(els, -3.5, 2.5)
    s = float(np.hypot(u, v))
    k = int(np.searchsorted(edges, s, side="right") - 1)
    hits = [i for i, item in enumerate(fl.bands) if item.path().contains(QPointF(-3.5, 2.5))]
    assert hits and fl.bands[hits[0]].brush().color().rgb() & 0xFFFFFF == \
        (fl.legend.colors[k][0] << 16 | fl.legend.colors[k][1] << 8 | fl.legend.colors[k][2])


def test_cp_needs_a_reference_speed(fl):
    from physics import Source
    fl.update([Source(m=1.0)], VIEW, {"cp": True})
    assert not fl.bands and "reference" in fl.message
    fl.update([Source(m=1.0)], VIEW, {"cp": True}, v_ref=0.5)
    assert fl.bands and fl.legend.title == "Cp" and fl.legend.edges[-1] >= 1.0 - 1e-9


def test_cp_without_reference_shows_a_note_instead_of_the_legend(fl):
    from physics import Source
    fl.update([Source(m=-2.0)], VIEW, {"cp": True})
    assert fl.legend.isVisible() and fl.legend.note is not None and not fl.legend.edges
    assert "V_ref" in fl.legend.note[1]
    called = []
    fl.legend.clicked = lambda: called.append(1)

    class Click:                                   # stand-in for pyqtgraph's MouseClickEvent
        def button(self):
            from PySide6.QtCore import Qt
            return Qt.LeftButton

        def accept(self):
            pass
    fl.legend.mouseClickEvent(Click())
    assert called
    fl.update([Source(m=-2.0)], VIEW, {"cp": True}, v_ref=1.0)
    assert fl.legend.note is None and fl.bands


@pytest.mark.parametrize("m", [2.0, -2.0])
def test_bands_are_filled_up_to_a_singular_point(fl, m):
    """No hole (whose shape depends on the grid) around a source or sink: the fastest band reaches
    the point itself."""
    from PySide6.QtCore import QPointF
    from physics import Source
    fl.update([Source(m=m)], VIEW, {"speed": True})
    for r in (0.02, 0.05, 0.1):
        assert any(b.path().contains(QPointF(r, 0.3 * r)) for b in fl.bands), r
    last = fl.bands[-1].path()
    assert last.contains(QPointF(0.03, 0.01))      # in the last (fastest) band


@pytest.mark.parametrize("view", [((-0.5, 0.5), (-0.3, 0.3)), ((-0.05, 0.05), (-0.03, 0.03))])
def test_legend_range_stays_sensible_when_zoomed_near_a_singular_point(fl, view):
    from physics import Doublet, Source, Uniform
    fl.update([Source(m=2.0)], view, {"speed": True})
    edges = fl.legend.edges
    w = view[0][1] - view[0][0]
    typical = 2.0 / (2 * np.pi * 0.25 * w)                            # |V| a quarter view away
    assert edges[-1] <= 6 * typical and len(edges) - 1 <= 20
    fl.update([Uniform(), Doublet(mu=1.0)], view, {"cp": True})
    edges = fl.legend.edges
    assert edges[-1] == 1.0 and len(edges) - 1 <= 20


def test_cp_legend_ends_at_one(fl):
    from physics import Doublet, Uniform
    for view in (VIEW, ((-0.5, 0.5), (-0.3, 0.3))):
        fl.update([Uniform(), Doublet(mu=1.0)], view, {"cp": True})
        assert fl.legend.edges[-1] == 1.0 and fl.legend.edges[-2] < 1.0


def test_layers_off_hide_everything(fl):
    from physics import Uniform
    fl.update([Uniform()], VIEW, {"equipotential": True, "speed": True})
    fl.update([Uniform()], VIEW, {})
    assert not fl.phi.isVisible() and not fl.bands and not fl.legend.isVisible()


# ---------------------------------------------------------------- in the window
@pytest.fixture
def win(qapp):
    from app.main_window import MainWindow
    w = MainWindow()
    w._ask_save_changes = lambda: "discard"
    w.resize(1400, 860)
    w.show()
    qapp.processEvents()
    w.canvas.set_view(*VIEW)
    w.canvas.recompute()
    qapp.processEvents()
    yield w
    w.close()


def test_one_color_map_at_a_time(win, qapp):
    boxes = win.settings_panel.layer_boxes
    boxes["speed"].setChecked(True)
    boxes["cp"].setChecked(True)
    assert not boxes["speed"].isChecked() and win.canvas.layers["cp"] and not win.canvas.layers["speed"]
    assert win.layer_actions["cp"].isChecked() and not win.layer_actions["speed"].isChecked()
    assert win.canvas.fields.legend.title == "Cp"


def test_cp_checkbox_says_when_a_reference_is_needed(win, qapp):
    from physics import Source, Uniform
    box = win.settings_panel.layer_boxes["cp"]
    win.load_scene([Source(m=-2.0)], VIEW, title="sink")
    assert "needs V_ref" in box.text()
    win.load_scene([Uniform(), Source(m=1.0)], VIEW, title="half body")
    assert "needs V_ref" not in box.text()
    win.load_scene([Source(m=-2.0)], VIEW, title="sink")
    win.settings_panel.c_cp_ref.setCurrentIndex(1)                   # a custom V_ref is enough
    assert "needs V_ref" not in box.text()


def test_clicking_the_cp_note_opens_the_reference_setting(win, qapp):
    from physics import Source
    sp, cv = win.settings_panel, win.canvas
    win.load_scene([Source(m=-2.0)], VIEW, title="sink")
    sp.set_section_visible("computation", False)
    sp.layer_boxes["cp"].setChecked(True)
    cv.fields.refresh()
    assert cv.fields.legend.note is not None
    cv.fields.legend.clicked()
    assert sp.section_visible("computation") and sp.c_cp_ref.currentIndex() == 1
    assert cv.settings.cp_reference == sp.s_vref.value()
    cv.fields.refresh()
    assert cv.fields.legend.note is None and cv.fields.bands


def test_status_message_hides_the_probe_readout(win, qapp):
    win._update_probe((-3.0, 2.0))
    win.flash("hello")
    assert not win.probe_label.isVisibleTo(win)
    win.statusBar().clearMessage()
    assert win.probe_label.isVisibleTo(win)


def test_custom_cp_reference_and_grid_quality_are_saved(win, qapp, tmp_path):
    sp, cv = win.settings_panel, win.canvas
    sp.c_cp_ref.setCurrentIndex(1)
    sp.s_vref.setValue(2.0)
    sp.s_vref.editingFinished.emit()
    sp.c_quality.setCurrentIndex(2)
    assert cv.settings.cp_reference == 2.0 and cv.settings.field_quality == 3 and cv.cp_reference() == 2.0
    path = str(tmp_path / "s.pflow")
    win._ask_save_path = lambda suggested: path
    assert win.save_scene_as()
    sp.c_cp_ref.setCurrentIndex(0)
    sp.c_quality.setCurrentIndex(0)
    assert cv.settings.cp_reference is None and cv.settings.field_quality == 1
    assert win.open_scene(path)
    assert cv.settings.cp_reference == 2.0 and cv.settings.field_quality == 3
    assert sp.c_cp_ref.currentIndex() == 1 and sp.s_vref.value() == 2.0 and sp.c_quality.currentIndex() == 2


def test_probe_shows_phi_psi_and_uses_the_cp_reference(win):
    win._update_probe((-3.0, 2.0))
    text = win.probe_label.text()
    assert "φ =" in text and "ψ =" in text and "Cp =" in text
    win.canvas.set_cp_reference(4.0)
    win._update_probe((-3.0, 2.0))
    cp = float(win.probe_label.text().split("Cp =")[1].split()[0])
    assert cp > 0.8                                                  # V ≈ 1, V_ref = 4 -> Cp ≈ 0.94


def test_field_layers_follow_the_scene_and_the_view(win, qapp):
    from physics import Uniform
    cv = win.canvas
    win.settings_panel.layer_boxes["equipotential"].setChecked(True)
    assert cv.fields.phi.isVisible() and cv.fields.covered is not None
    win.load_scene([Uniform(alpha=90.0)], VIEW, title="up")
    cv.fields.refresh()
    lines = _lines(cv.fields.phi)
    assert lines and all(np.ptp(ln[:, 1]) < 1e-6 for ln in lines)   # flow upwards: φ = V y -> horizontal
    cv.set_view((40.0, 48.0), (-3.0, 3.0))
    assert cv.fields.needs_update(cv.view())


def test_legend_is_in_exported_figures(win, tmp_path):
    from app.export import render_figure
    from app.canvas.legend import ColorLegend
    win.settings_panel.layer_boxes["speed"].setChecked(True)
    scene_items = win.canvas.plot.scene().items()
    assert any(isinstance(i, ColorLegend) and i.isVisible() for i in scene_items)
    render_figure(win.canvas, str(tmp_path / "f.svg"), "svg")
    assert "|V|" in open(tmp_path / "f.svg", encoding="utf-8").read()


def test_works_without_contourpy(fl, monkeypatch):
    """Without the optional contourpy package: φ lines from a NumPy marching-squares fallback and the
    bands as one pixel image — nothing fails."""
    import app.canvas.contours as mod
    from physics import Doublet, Uniform
    xs = np.linspace(-2, 2, 41)
    X, Y = np.meshgrid(xs, xs)
    ref = mod.contour_xy(xs, xs, X, [0.5])
    monkeypatch.setattr(mod, "HAVE_CONTOURPY", False)
    pieces = mod.contour_xy(xs, xs, X, [0.5])
    pts = pieces[np.isfinite(pieces[:, 0])]
    assert len(pts) and np.allclose(pts[:, 0], 0.5)                  # the line x = 0.5
    assert np.ptp(pts[:, 1]) == pytest.approx(np.ptp(ref[np.isfinite(ref[:, 0]), 1]))
    fl.update([Uniform(), Doublet(mu=1.0)], VIEW, {"equipotential": True, "speed": True})
    assert fl.phi.isVisible() and len(fl.bands) == 1 and fl.legend.isVisible()


def test_phi_lines_keep_a_clean_circle_round_a_singular_point(fl):
    """No φ lines inside a circle round the doublet (φ → ∞: they would crowd into a blot), lines right
    outside it; the pen is exactly 1 px (Qt's fast path: 1.1 px was ~30× slower to draw)."""
    from app.canvas.field_layer import crowd_circles
    from physics import Doublet, Uniform
    els = [Uniform(), Doublet(mu=1.0)]
    view = ((-2.2, 2.2), (-1.6, 1.6))
    fl.update(els, view, {"equipotential": True}, 3)
    pen = fl.phi.opts["pen"]
    assert pen.widthF() == 1.0 and pen.isCosmetic() and list(pen.dashPattern()) == [3.0, 3.0]
    x, y = fl.phi.getData()
    r = np.hypot(x, y)[np.isfinite(x)]
    (s, radius), = crowd_circles(els, 5.0, 0.01, 1.0)        # max |V| on the circle 1 + 1/r² = 5 -> r = 0.5
    assert abs(s) < 1e-12 and 0.5 <= radius < 0.6
    hole = r.min()                                              # (the layer's limit: 5 × the median |V|)
    assert 0.35 < hole < 0.75
    angles = np.angle((x + 1j * y)[np.isfinite(x)][r < hole * 1.3])
    assert np.ptp(angles) > 5.0                                  # all round: a circle, not a few spikes


def test_no_phi_lines_inside_solid_bodies(qapp):
    from app.main_window import MainWindow
    from physics import Doublet, Uniform
    w = MainWindow()
    w._ask_save_changes = lambda: "discard"
    w.resize(1300, 820)
    w.show()
    w.load_scene([Uniform(), Doublet(mu=1.0)], ((-3.0, 3.0), (-2.0, 2.0)))
    cv = w.canvas
    cv.set_layer("equipotential", True)
    cv.set_layer("bodies", True)
    cv.compute_now()
    from PySide6.QtTest import QTest
    QTest.qWait(300)
    qapp.processEvents()
    x, y = cv.fields.phi.getData()
    r = np.hypot(x, y)[np.isfinite(x)]
    assert r.size > 100 and r.min() > 0.97                         # nothing inside the cylinder r = 1
    w.close()
