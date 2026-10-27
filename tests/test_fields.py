"""Phase 4: field layers — equipotential lines φ, |V| and Cp color bands with a legend — and the
Computation settings (grid quality, Cp reference) that are saved with the scene."""
import numpy as np
import pytest


@pytest.fixture
def fl(qapp):
    import pyqtgraph as pg
    from app.field_layers import FieldLayers
    from app.theme import LIGHT
    pw = pg.PlotWidget()
    layers = FieldLayers(pw, pw.getPlotItem().getViewBox())
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
    from app.field_layers import nice_step
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


def test_custom_cp_reference_and_grid_quality_are_saved(win, qapp, tmp_path):
    sp, cv = win.settings_panel, win.canvas
    sp.c_cp_ref.setCurrentIndex(1)
    sp.s_vref.setValue(2.0)
    sp.s_vref.editingFinished.emit()
    sp.c_quality.setCurrentIndex(2)
    assert cv.v_ref_override == 2.0 and cv.field_quality == 3 and cv.cp_reference() == 2.0
    path = str(tmp_path / "s.pflow")
    win._ask_save_path = lambda suggested: path
    assert win.save_scene_as()
    sp.c_cp_ref.setCurrentIndex(0)
    sp.c_quality.setCurrentIndex(0)
    assert cv.v_ref_override is None and cv.field_quality == 1
    assert win.open_scene(path)
    assert cv.v_ref_override == 2.0 and cv.field_quality == 3
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
    cv.update_fields()
    lines = _lines(cv.fields.phi)
    assert lines and all(np.ptp(ln[:, 1]) < 1e-6 for ln in lines)   # flow upwards: φ = V y -> horizontal
    cv.set_view((40.0, 48.0), (-3.0, 3.0))
    assert cv.fields.needs_update(cv._view())


def test_legend_is_in_exported_figures(win, tmp_path):
    from app.export import render_figure
    from app.field_layers import ColorLegend
    win.settings_panel.layer_boxes["speed"].setChecked(True)
    scene_items = win.canvas.plot.scene().items()
    assert any(isinstance(i, ColorLegend) and i.isVisible() for i in scene_items)
    render_figure(win.canvas, str(tmp_path / "f.svg"), "svg")
    assert "|V|" in open(tmp_path / "f.svg", encoding="utf-8").read()
