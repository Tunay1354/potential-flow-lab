"""GUI tests (offscreen): dialogs agree with the physics classes, and every user action goes through
the scene model so that it can be undone."""
import numpy as np
import pytest

from physics import (ELEMENT_TYPES, Doublet, FlowElement, ParamSpec, SectorFlow, Source, SymmetryWall, Uniform,
                     Vortex)


# ---------------------------------------------------------------- dialog <-> physics consistency
@pytest.mark.parametrize("key", sorted(ELEMENT_TYPES))
def test_ui_spec_keys_and_defaults_match_physics(qapp, key):
    from app.dialogs import ElementDialog
    from app.element_specs import spec_for
    from app.theme import LIGHT
    cls = ELEMENT_TYPES[key]
    spec = spec_for(key)
    assert [p.key for p in spec.params] == [p.key for p in cls.PARAMS]
    dlg = ElementDialog(spec, LIGHT)
    assert dlg.values() == {p.key: p.default for p in cls.PARAMS}      # same defaults, signs included


NONTRIVIAL = [
    Uniform(V=2.5, alpha=-135.0),
    Source(m=-3.25, x0=1.5, y0=-0.75),                 # sink
    Vortex(Gamma=-2.0, x0=-1.0, y0=0.5),               # clockwise
    Doublet(mu=0.6, x0=0.25, y0=1.0, delta=30.0),
    SectorFlow(V=-1.5, x0=0.5, y0=-0.5, theta1=300.0, theta2=30.0),
    SymmetryWall(xw=1.0, yw=-2.0, theta_w=270.0, side=1),
    Source(m=1.23456789, x0=-0.0001234, y0=9.87654321),  # more decimals than the dialog shows
]


@pytest.mark.parametrize("el", NONTRIVIAL, ids=lambda e: e.TYPE)
def test_dialog_round_trip_is_exact(qapp, el):
    """Opening an element in the dialog and pressing Apply without changes gives the same element."""
    from app.dialogs import ElementDialog
    from app.element_specs import spec_for
    from app.theme import LIGHT
    spec = spec_for(el.TYPE)
    dlg = ElementDialog(spec, LIGHT, editing=True, values={p.key: getattr(el, p.key) for p in spec.params})
    assert el.copy(**dlg.values()) == el


def test_sign_radio_buttons(qapp):
    from app.dialogs import ElementDialog
    from app.element_specs import spec_for
    from app.theme import LIGHT
    dlg = ElementDialog(spec_for("source"), LIGHT)
    assert dlg.signs["m"].index() == 0 and dlg.values()["m"] == 1.0          # Source selected by default
    dlg.signs["m"].set_index(1)
    assert dlg.values()["m"] == -1.0                                          # Sink -> negative m
    dlg.signs["m"].group.button(1).setChecked(False)                          # cannot leave both empty
    assert dlg.signs["m"].index() == 1


def test_new_physics_type_gets_an_automatic_dialog(qapp, monkeypatch):
    """A physics element with no UI entry still gets a working dialog (extensibility)."""
    from dataclasses import dataclass

    from app.dialogs import ElementDialog
    from app.element_specs import spec_for, toolbar_types
    from app.theme import LIGHT

    @dataclass(kw_only=True)
    class Dummy(FlowElement):
        TYPE = "dummy_test"
        NAME = "Dummy"
        PARAMS = (ParamSpec("a", "a", "Strength", default=2.0),
                  ParamSpec("kind", "", "Kind", default=1, minimum=0, maximum=1, choices=("one", "two")))
        a: float = 2.0
        kind: int = 1

    monkeypatch.setitem(ELEMENT_TYPES, "dummy_test", Dummy)
    assert "dummy_test" in toolbar_types()
    dlg = ElementDialog(spec_for("dummy_test"), LIGHT)
    assert dlg.values() == {"a": 2.0, "kind": 1}


def test_validator_switches_apply_button(qapp):
    from app.dialogs import ElementDialog
    from app.element_specs import spec_for
    from app.theme import LIGHT
    bad = {"value": True}
    dlg = ElementDialog(spec_for("vortex"), LIGHT,
                        validator=lambda v: [("error", "behind the wall")] if v["y0"] < 0 else [])
    dlg.widgets["y0"].setValue(-1.0)
    assert dlg.has_errors and dlg.apply_button.text() == "Apply anyway"
    dlg.widgets["y0"].setValue(1.0)
    assert not dlg.has_errors and dlg.apply_button.text() == "Apply"
    assert bad


# ---------------------------------------------------------------- main window wired to the model
@pytest.fixture
def window(qapp):
    from app.main_window import MainWindow
    FakeDialog.result_values = None
    w = MainWindow()
    w.recent.clear()
    w._ask_save_changes = lambda: "discard"          # never block on the "unsaved changes" box
    w.messages = []                                  # message boxes are recorded instead of shown
    w._notify_user = lambda kind, title, text: w.messages.append((kind, title, text))
    yield w
    w.close()
    w.deleteLater()


def preset(title):
    from app.scene import list_presets
    return next(p for _, items in list_presets() for p in items if p.title == title)


def types(w):
    return [e.TYPE for e in w.elements]


class FakeDialog:
    """Replaces ElementDialog: 'the user presses Apply' with given values (no blocking exec)."""
    result_values = None

    def __init__(self, spec, theme, editing=False, parent=None, values=None, validator=None):
        self.start = dict(values or {})
        self.validator = validator

    def exec(self):
        return True

    def values(self):
        out = dict(self.start)
        out.update(type(self).result_values or {})
        return out


def test_add_from_toolbar_and_undo(window, monkeypatch):
    import app.main_window as mw
    monkeypatch.setattr(mw, "ElementDialog", FakeDialog)
    FakeDialog.result_values = {"m": -2.0, "x0": 2.0, "y0": 1.0}
    window.element_actions["source"].trigger()
    assert types(window) == ["uniform", "doublet", "vortex", "source"]
    assert window.elements[3] == Source(m=-2.0, x0=2.0, y0=1.0)
    assert window.elements_panel.current_row() == 3                     # new element selected
    assert window.act_undo.text() == "Undo add source / sink"
    assert window.windowTitle().endswith("*")
    window.act_undo.trigger()
    assert types(window) == ["uniform", "doublet", "vortex"]
    assert not window.windowTitle().endswith("*")
    window.act_redo.trigger()
    assert types(window) == ["uniform", "doublet", "vortex", "source"]


def test_add_dialog_starts_at_view_center(window, monkeypatch):
    import app.main_window as mw
    seen = {}

    class Spy(FakeDialog):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            seen.update(self.start)

    monkeypatch.setattr(mw, "ElementDialog", Spy)
    Spy.result_values = None
    window.canvas.set_view((2.0, 6.0), (-1.0, 1.0))
    window.add_element_dialog("vortex")
    assert seen["x0"] == pytest.approx(4.0, abs=0.06) and seen["y0"] == pytest.approx(0.0, abs=0.06)


def test_edit_from_list_and_undo(window, monkeypatch):
    import app.main_window as mw
    monkeypatch.setattr(mw, "ElementDialog", FakeDialog)
    FakeDialog.result_values = {"Gamma": 3.0}
    old = window.elements[2]
    window.elements_panel.edit_requested.emit(2)
    assert window.elements[2].Gamma == 3.0 and old.Gamma == -2.0
    window.model_undo()
    assert window.elements[2] is old


def test_edit_without_change_adds_no_undo_step(window, monkeypatch):
    import app.main_window as mw
    monkeypatch.setattr(mw, "ElementDialog", FakeDialog)
    FakeDialog.result_values = None
    window.edit_element(1)
    assert not window.model.can_undo


def test_validator_given_to_dialog_reports_wall_problems(window, monkeypatch):
    import app.main_window as mw
    captured = {}

    class Spy(FakeDialog):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            captured["validator"] = self.validator

        def exec(self):
            return False                                        # the user presses Cancel

    monkeypatch.setattr(mw, "ElementDialog", Spy)
    Spy.result_values = None
    window.add_element_dialog("wall")                          # default wall y = −1.5 below the cylinder
    v = captured["validator"]
    ok = {"xw": 0.0, "yw": -1.5, "theta_w": 0.0, "side": 0}
    assert not [m for sev, m in v(ok) if sev == "error"]
    above = dict(ok, yw=0.5)                                    # wall above the doublet / vortex
    msgs = [m for sev, m in v(above) if sev == "error"]
    assert any("[2] Doublet is behind the wall" in m for m in msgs)


def test_hide_delete_duplicate_from_panel(window, qapp):
    """Through the real panel widgets: tick box, Duplicate and Delete buttons (requests are delivered
    on the next event-loop turn, so the list can be rebuilt safely)."""
    from PySide6.QtCore import Qt
    panel = window.elements_panel
    panel.tree.topLevelItem(2).setCheckState(0, Qt.Unchecked)
    qapp.processEvents()
    assert not window.elements[2].enabled and window.act_undo.text() == "Undo hide vortex"
    panel.tree.setCurrentItem(panel.tree.topLevelItem(1))
    panel.btn_dup.click()
    qapp.processEvents()
    assert types(window) == ["uniform", "doublet", "doublet", "vortex"]
    assert (window.elements[2].x0, window.elements[2].y0) == (0.5, 0.5)
    panel.tree.setCurrentItem(panel.tree.topLevelItem(0))
    panel.btn_del.click()
    qapp.processEvents()
    assert types(window) == ["doublet", "doublet", "vortex"]
    for _ in range(3):
        window.model_undo()
    assert types(window) == ["uniform", "doublet", "vortex"] and window.elements[2].enabled


def test_preset_and_clear_are_undoable(window):
    window.load_preset(preset("Symmetry wall: source near a wall"))
    assert types(window) == ["wall", "source"]
    assert "Symmetry wall: source near a wall" in window.windowTitle()
    window.clear_all()
    assert window.elements == [] and window.issue_label.text() == "✓ scene OK"
    window.model_undo()
    window.model_undo()
    assert types(window) == ["uniform", "doublet", "vortex"]


def test_loading_a_preset_selects_nothing(window):
    window.select_element(1)
    window.load_preset(preset("Symmetry wall: source near a wall"))
    assert window.elements_panel.current_row() == -1 and window.canvas.selected == -1
    window.model_undo()
    assert window.canvas.selected == -1


def test_error_banner_follows_the_scene(window):
    window.model.add(SymmetryWall(yw=0.5))
    assert not window.canvas.banner.isHidden() and "behind the wall" in window.canvas.banner.text()
    assert window.issue_label.text().startswith("✖")
    window.model_undo()
    assert window.canvas.banner.isHidden()


def test_elements_menu_lists_every_element(window):
    titles = [a.text() for a in window.elements_menu.actions()]
    assert any(t.startswith("1. Uniform flow") for t in titles)
    assert any(t.startswith("3. Vortex") for t in titles)
    window.model.add(Source())
    assert any(t.startswith("4. Source") for t in (a.text() for a in window.elements_menu.actions()))


def test_canvas_highlights_selection(window):
    window.elements_panel.tree.setCurrentItem(window.elements_panel.tree.topLevelItem(2))
    assert window.canvas.selected == 2


def test_double_click_edit_and_tick_box_do_not_crash(window, qapp, monkeypatch):
    """Regression: the list is rebuilt by the model while the item's own signal is running."""
    import app.main_window as mw
    from PySide6.QtCore import Qt
    monkeypatch.setattr(mw, "ElementDialog", FakeDialog)
    FakeDialog.result_values = {"mu": 2.0}
    tree = window.elements_panel.tree
    tree.itemDoubleClicked.emit(tree.topLevelItem(1), 0)
    qapp.processEvents()
    assert window.elements[1].mu == 2.0
    for _ in range(3):
        tree.topLevelItem(0).setCheckState(0, Qt.Unchecked if window.elements[0].enabled else Qt.Checked)
        qapp.processEvents()
    assert not window.elements[0].enabled


def test_coincident_points_are_a_note_not_a_warning(window):
    """Doublet + vortex at the cylinder center: allowed, shown as an info note (status stays 'OK')."""
    from physics import check_scene
    issues = check_scene(window.elements)
    assert [s.severity for s in issues] == ["info"]
    assert window.issue_label.text().startswith("✓ scene OK") and "1 note" in window.issue_label.text()
    window.model.set_enabled(2, False)
    assert window.issue_label.text() == "✓ scene OK"


# ---------------------------------------------------------------- selecting on the plot / clearing the selection
def _click(qapp, window, x, y, double=False):
    """Mouse click at data coordinates (x, y) on the plot, with the same event sequence as a real mouse
    (a double click is press, release, double-click press, release)."""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    plot = window.canvas.plot
    vp = plot.viewport()
    pos = plot.mapFromScene(window.canvas.vb.mapViewToScene(QPointF(x, y)))
    QTest.qWait(QApplication.doubleClickInterval() + 50)     # never merge with a previous click
    kinds = [QEvent.MouseButtonPress, QEvent.MouseButtonRelease]
    if double:
        kinds += [QEvent.MouseButtonDblClick, QEvent.MouseButtonRelease]
    for kind in kinds:
        pressed = Qt.NoButton if kind == QEvent.MouseButtonRelease else Qt.LeftButton
        ev = QMouseEvent(kind, QPointF(pos), QPointF(vp.mapToGlobal(pos)), Qt.LeftButton, pressed,
                         Qt.NoModifier)
        QApplication.sendEvent(vp, ev)
    for _ in range(3):
        qapp.processEvents()


@pytest.fixture
def shown(window, qapp):
    window.resize(1400, 860)
    window.show()
    qapp.processEvents()
    window.canvas.set_view((-4.0, 4.0), (-3.0, 3.0))
    window.canvas.recompute()
    qapp.processEvents()
    return window


def test_start_without_selection(shown):
    assert shown.elements_panel.current_row() == -1 and shown.canvas.selected == -1
    assert not shown.act_del.isEnabled()


def test_click_symbol_selects_and_cycles_overlapping(shown, qapp):
    _click(qapp, shown, 0.0, 0.0)                      # doublet and vortex are both at (0, 0)
    first = shown.elements_panel.current_row()
    assert first in (1, 2) and shown.canvas.selected == first and shown.act_del.isEnabled()
    _click(qapp, shown, 0.0, 0.0)                      # same place again -> the other one
    assert shown.elements_panel.current_row() == ({1, 2} - {first}).pop()


def test_click_on_flow_clears_selection(shown, qapp):
    shown.select_element(2)
    _click(qapp, shown, -3.0, 2.0)                     # empty flow area (uniform flow is not pickable)
    assert shown.elements_panel.current_row() == -1 and shown.canvas.selected == -1


def test_click_on_wall_and_sector_side(shown, qapp):
    shown.load_preset(preset("Symmetry wall: source near a wall"))
    qapp.processEvents()
    _click(qapp, shown, 2.0, 0.0)                      # on the wall y = 0
    assert shown.elements_panel.current_row() == 0
    shown.load_preset(preset("Corner flow (90° sector, n = 2)"))
    qapp.processEvents()
    shown.select_element(-1)
    _click(qapp, shown, 0.0, 2.0)                      # on the vertical side of the wedge
    assert shown.elements_panel.current_row() == 0


def test_click_elsewhere_clears_but_delete_button_keeps(shown, qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    shown.select_element(1)
    QTest.mouseClick(shown.settings_panel.sliders["density"], Qt.LeftButton)       # any other widget
    qapp.processEvents()
    assert shown.elements_panel.current_row() == -1
    shown.select_element(1)
    QTest.mouseClick(shown.elements_panel.btn_del, Qt.LeftButton)        # acts on the selection
    qapp.processEvents()
    assert types(shown) == ["uniform", "vortex"]


def test_click_empty_list_area_and_escape_clear(shown, qapp):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    tree = shown.elements_panel.tree
    shown.select_element(0)
    vp = tree.viewport()
    QTest.mouseClick(vp, Qt.LeftButton, pos=QPoint(20, vp.height() - 5))  # below the last row
    qapp.processEvents()
    assert shown.elements_panel.current_row() == -1
    shown.select_element(0)
    shown.canvas.plot.setFocus()
    QTest.keyClick(shown.canvas.plot, Qt.Key_Escape)
    qapp.processEvents()
    assert shown.elements_panel.current_row() == -1


def test_double_click_symbol_opens_edit(shown, qapp, monkeypatch):
    import app.main_window as mw
    monkeypatch.setattr(mw, "ElementDialog", FakeDialog)
    shown.load_preset(preset("Rankine half-body"))
    qapp.processEvents()
    FakeDialog.result_values = {"m": 3.0}
    _click(qapp, shown, 0.0, 0.0, double=True)         # the source of the half-body
    qapp.processEvents()
    assert shown.elements[1].m == 3.0


def test_pick_ignores_hidden_elements(shown):
    from PySide6.QtCore import QPointF
    shown.model.set_enabled(1, False)
    shown.model.set_enabled(2, False)
    pt = shown.canvas.vb.mapViewToScene(QPointF(0.0, 0.0))
    assert shown.canvas.pick(pt) == []


# ---------------------------------------------------------------- background streamline computation
def _wait_for(qapp, canvas, cond, timeout_s=20.0):
    import time
    end = time.time() + timeout_s
    while time.time() < end:
        canvas.wait_idle(100)
        qapp.processEvents()
        if cond():
            return True
    return False


def test_scene_change_computes_streamlines_in_the_background(shown, qapp):
    cv = shown.canvas
    assert cv.streamlines.background
    done = []
    cv.computed.connect(lambda n, ms: done.append(n))
    shown.load_scene([Uniform(), Doublet(mu=1.0)], title="cylinder")
    assert _wait_for(qapp, cv, lambda: bool(done))
    assert done[-1] > 10 and cv.streamlines.line_items[0].getData()[0].size > 0


def test_only_the_newest_request_is_drawn(shown, qapp):
    from physics.streamlines import StreamlineCache
    cv = shown.canvas
    cv.wait_idle()
    qapp.processEvents()
    done = []
    cv.computed.connect(lambda n, ms: done.append(n))
    for density in (0.4, 0.7, 1.6):                  # three quick changes: only the last one counts
        cv.set_density(density)
    assert _wait_for(qapp, cv, lambda: bool(done))
    for _ in range(5):
        cv.wait_idle(100)
        qapp.processEvents()
    assert len(done) == 1
    assert cv.streamlines.cache.density == 1.6
    assert cv.streamlines.drawn_level == StreamlineCache(tuple(cv.elements), 1.6).level_for(cv.view())
    assert cv.streamlines.covers_view()


def test_panning_inside_the_margin_needs_no_new_computation(shown, qapp):
    cv = shown.canvas
    assert _wait_for(qapp, cv, cv.streamlines.covers_view)
    done = []
    cv.computed.connect(lambda n, ms: done.append(n))
    (x0, x1), (y0, y1) = cv.view()
    lines_before = cv.streamlines.line_items[0].getData()[0].copy()
    cv.set_view((x0 + 0.5, x1 + 0.5), (y0 + 0.3, y1 + 0.3))
    for _ in range(10):
        cv.wait_idle(50)
        qapp.processEvents()
    assert done == [] and cv.streamlines.covers_view()                          # lines were already there
    np.testing.assert_array_equal(cv.streamlines.line_items[0].getData()[0], lines_before)
    cv.set_view((x0 + 12, x1 + 12), (y0, y1))                         # far: new area is computed
    assert _wait_for(qapp, cv, lambda: bool(done) and cv.streamlines.covers_view())


def test_quick_view_changes_are_collected_into_one_computation(shown, qapp):
    cv = shown.canvas
    assert _wait_for(qapp, cv, cv.streamlines.covers_view)
    started = []
    original = cv.streamlines._start_job
    cv.streamlines._start_job = lambda: (started.append(1), original())[1]
    (x0, x1), (y0, y1) = cv.view()
    for k in range(1, 9):                            # 8 jumps to areas that are not computed yet
        cv.set_view((x0 + 20 * k, x1 + 20 * k), (y0, y1))
    assert _wait_for(qapp, cv, lambda: cv.streamlines.covers_view() and not cv.streamlines.busy)
    assert len(started) <= 3                         # first jump + one for the newest view (+ margin)
    cv.streamlines._start_job = original


def test_panning_updates_the_drawn_part_without_a_computation(shown, qapp):
    cv = shown.canvas
    assert _wait_for(qapp, cv, lambda: cv.streamlines.covers_view() and not cv.streamlines.busy)
    (x0, x1), (y0, y1) = cv.view()
    W = x1 - x0
    cv.set_view((x0 + 0.33 * W, x1 + 0.33 * W), (y0, y1))     # inside the computed margin
    qapp.processEvents()
    a0, a1, b0, b1, _ = cv.streamlines.cull_rect
    (v0, v1), (w0, w1) = cv.view()
    assert a0 <= v0 and v1 <= a1 and b0 <= w0 and w1 <= b1      # lines / arrows handed for the new view


def test_closing_during_a_computation_waits_and_does_not_hang(window, qapp):
    import time
    window.show()
    window.load_scene([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)], title="lifting")
    window.canvas.set_density(2.0)
    t0 = time.time()
    window.close()
    assert window.canvas.wait_idle(0)                # nothing running any more
    assert time.time() - t0 < 10.0


# ---------------------------------------------------------------- stagnation points / dividing streamlines
def test_stagnation_points_are_drawn_and_their_lines_appear_only_when_selected(shown, qapp):
    cv = shown.canvas
    shown.load_preset(preset("Single vortex, clockwise (Γ = −2)"))       # no stagnation points
    assert _wait_for(qapp, cv, lambda: not cv.stagnation_points and not cv.streamlines.busy)
    shown.load_preset(preset("Lifting (rotating) cylinder"))
    assert _wait_for(qapp, cv, lambda: len(cv.stagnation_points) == 2)
    th = np.arcsin(-2.0 / (4 * np.pi))
    xs = sorted(p.x for p in cv.stagnation_points)
    np.testing.assert_allclose(xs, [-np.cos(th), np.cos(th)], atol=1e-8)
    x, y = cv.stagnation.symbol_item.getData()
    assert len(x) == 2                                               # ⊗ symbols always shown
    assert cv.stagnation.dividing_item.getData()[0].size == 0                  # no black lines by default
    assert not cv.stagnation.label.isVisible()


def _dividing_points(cv):
    x, y = cv.stagnation.dividing_item.getData()
    ok = np.isfinite(x)
    return x[ok] + 1j * y[ok]


def test_clicking_a_stagnation_point_shows_its_lines_and_coordinates(shown, qapp):
    cv = shown.canvas
    shown.load_preset(preset("Non-lifting cylinder (uniform + doublet)"))
    assert _wait_for(qapp, cv, lambda: sorted(round(p.x, 6) for p in cv.stagnation_points) == [-1.0, 1.0]
                     and all(abs(p.y) < 1e-9 for p in cv.stagnation_points))
    shown.select_element(1)                                          # the doublet is selected ...
    _click(qapp, shown, -1.0, 0.0)                                   # ... click the front stagnation point
    k = cv.selected_stagnation
    assert k is not None and cv.stagnation_points[k].x == pytest.approx(-1.0)
    assert shown.elements_panel.current_row() == -1 and cv.selected == -1   # element selection gone
    assert len(cv.stagnation.glow) == len(LAYOUT_GLOW())                   # it glows
    assert cv.stagnation.label.isVisible()
    html = cv.stagnation.label.textItem.toHtml()
    assert "x = -1.0000" in html and "y = 0.0000" in html and "on the body surface" in html
    pts = _dividing_points(cv)
    assert pts.size > 50
    assert (pts.real < -3.0).any()                                   # the line coming from upstream
    surface = pts[(np.abs(pts.imag) > 1e-6) | (pts.real > -1.0 + 1e-9)]
    assert surface.size > 20 and np.abs(np.abs(surface) - 1.0).max() < 2e-3   # and the cylinder surface
    assert not (pts.real > 3.0).any()                                # not the back point's line

    _click(qapp, shown, 1.0, 0.0)                                    # the other point
    assert cv.stagnation_points[cv.selected_stagnation].x == pytest.approx(1.0)
    assert (_dividing_points(cv).real > 3.0).any()

    _click(qapp, shown, -3.0, 2.0)                                   # empty place: everything goes
    assert cv.selected_stagnation is None and not cv.stagnation.glow
    assert not cv.stagnation.label.isVisible() and _dividing_points(cv).size == 0
    assert len(cv.stagnation.symbol_item.getData()[0]) == 2                      # the symbols stay


def test_stagnation_selection_clears_with_escape_and_element_selection(shown, qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    cv = shown.canvas
    shown.load_preset(preset("Non-lifting cylinder (uniform + doublet)"))
    assert _wait_for(qapp, cv, lambda: len(cv.stagnation_points) == 2
                     and sorted(round(p.x, 6) for p in cv.stagnation_points) == [-1.0, 1.0])
    shown.select_stagnation(0)
    assert cv.selected_stagnation == 0
    tree = shown.elements_panel.tree                                 # a click on an element in the list
    tree.setCurrentItem(tree.topLevelItem(0))
    tree.topLevelItem(0).setSelected(True)
    for _ in range(3):
        qapp.processEvents()
    assert shown.elements_panel.current_row() == 0
    assert cv.selected_stagnation is None
    shown.select_stagnation(1)
    QTest.keyClick(shown.canvas.plot, Qt.Key_Escape)
    for _ in range(3):
        qapp.processEvents()
    assert cv.selected_stagnation is None


def test_all_dividing_streamlines_layer(shown, qapp):
    cv = shown.canvas
    assert _wait_for(qapp, cv, lambda: len(cv.stagnation_points) == 2)
    assert not shown.settings_panel.layer_boxes["dividing"].isChecked()
    shown.settings_panel.layer_boxes["dividing"].setChecked(True)
    assert _dividing_points(cv).size > 100 and shown.layer_actions["dividing"].isChecked()
    shown.layer_actions["dividing"].setChecked(False)
    assert _dividing_points(cv).size == 0


def LAYOUT_GLOW():
    from app.theme import LAYOUT
    return LAYOUT["selection_glow"]


def test_hover_over_a_stagnation_point_shows_it(shown, qapp):
    cv = shown.canvas
    shown.load_preset(preset("Non-lifting cylinder (uniform + doublet)"))
    assert _wait_for(qapp, cv, lambda: sorted(round(p.x, 6) for p in cv.stagnation_points) == [-1.0, 1.0]
                     and all(abs(p.y) < 1e-9 for p in cv.stagnation_points))
    shown._update_probe((1.0 + 0.004, 0.003))
    assert "Stagnation point (1.0000, 0.0000), on the body surface" in shown.probe_label.text()
    shown._update_probe((2.0, 2.0))
    assert "u =" in shown.probe_label.text()


def test_layer_switches_in_panel_and_view_menu_agree(shown, qapp):
    cv = shown.canvas
    box = shown.settings_panel.layer_boxes["stagnation"]
    act = shown.layer_actions["stagnation"]
    assert _wait_for(qapp, cv, lambda: len(cv.stagnation_points) == 2)
    p = cv.stagnation_points[0]
    assert cv.stagnation_near(p.x, p.y) is p
    box.setChecked(False)
    assert not cv.stagnation.symbol_item.isVisible() and not act.isChecked()
    assert cv.stagnation_near(p.x, p.y) is None                       # hidden points are not reported
    act.setChecked(True)
    assert box.isChecked() and cv.stagnation.symbol_item.isVisible()
    shown.settings_panel.layer_boxes["streamlines"].setChecked(False)
    assert not any(i.isVisible() for i in cv.streamlines.line_items) and not cv.streamlines.arrow_item.isVisible()
    shown.settings_panel.layer_boxes["walls"].setChecked(False)
    shown.load_preset(preset("Symmetry wall: source near a wall"))
    assert cv.element_layer.walls and not any(w.isVisible() for w in cv.element_layer.walls)  # newly drawn walls stay hidden
    assert shown.layer_actions["cp"].isEnabled()                      # Phase 4 layers are available


# ---------------------------------------------------------------- real dialogs (not replaced by fakes)
def _accept_modal_soon(qapp, before_accept=None):
    """Press OK / Apply in the dialog that opens next (exec() runs its own event loop)."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    def press():
        dlg = QApplication.activeModalWidget()
        if dlg is None:
            QTimer.singleShot(20, press)
            return
        if before_accept:
            before_accept(dlg)
        dlg.accept()
    QTimer.singleShot(50, press)


def test_real_add_and_edit_dialogs_return_their_values(window, qapp):
    """Regression: a dialog that deleted itself on close lost its values before they were read."""
    window.show()
    n = len(window.elements)
    _accept_modal_soon(qapp)
    window.add_element_dialog("source", at=(1.5, -0.5))
    assert len(window.elements) == n + 1
    src = window.elements[-1]
    assert src.TYPE == "source" and (src.x0, src.y0) == (1.5, -0.5)

    def change_strength(dlg):
        dlg.widgets["m"].setValue(3.0)
    _accept_modal_soon(qapp, change_strength)
    window.edit_element(n)
    assert window.elements[n].m == 3.0


def test_real_export_dialog_returns_its_options(window, qapp, tmp_path):
    window.show()
    window._ask_export_path = lambda suggested, flt: str(tmp_path / "fig.png")
    _accept_modal_soon(qapp)
    assert window.export_figure() and (tmp_path / "fig.png").exists()


def test_scene_check_in_the_status_bar_can_be_opened(window, qapp):
    """The status bar's '⚠ 2 warnings · 1 note' is a button: it lists every issue; a click on one selects
    its element."""
    from physics.elements import Doublet, Source, Uniform, Vortex
    window.load_scene([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0), Source(m=0.0, x0=2.0)])
    qapp.processEvents()
    assert window.issue_label.text().startswith("⚠ 1 warning") and "1 note" in window.issue_label.text()
    window.issue_label.click()
    qapp.processEvents()
    popup = window._issues_popup
    assert popup.isVisible()
    from app.window.issues_popup import _Row
    rows = popup.findChildren(_Row)
    assert len(rows) == 2
    texts = [" ".join(l.text() for l in r.findChildren(type(window.probe_label))) for r in rows]
    assert "Warning" in texts[0] and "m = 0" in texts[0] and "Note" in texts[1]       # warnings first
    rows[0].clicked.emit()
    qapp.processEvents()
    import shiboken6
    assert window.elements_panel.current_row() == 3
    assert not shiboken6.isValid(popup) or not popup.isVisible()                    # closed


def test_elements_list_shows_full_names_and_wraps_parameters(shown, qapp):
    """Elements panel: each row has the full element name on top and ALL its parameters below, wrapped to
    the list's width between parameters (never cut off), also after the panel gets narrower."""
    from PySide6.QtGui import QFontMetrics
    from app.panels import SUMMARY_ROLE, SUMMARY_SEP, wrap_summary
    shown.load_scene([Uniform(), SectorFlow(V=1.0, theta1=-30.0, theta2=240.0), SymmetryWall(yw=-1.5),
                      Doublet(mu=1.5, x0=-1.0, y0=0.5, delta=30.0)])
    qapp.processEvents()
    panel = shown.elements_panel
    tree = panel.tree
    assert tree.isColumnHidden(1)                                   # one visible column
    for i, e in enumerate(shown.elements):
        item = tree.topLevelItem(i)
        assert item.text(1) == e.summary() and item.data(0, SUMMARY_ROLE) == e.summary()
    fm = QFontMetrics(tree.font())
    for width in (300, 180, 120):
        lines = wrap_summary(shown.elements[1].summary(), fm, width)
        assert all(fm.horizontalAdvance(ln) <= width for ln in lines)
        # nothing lost: the lines together are the whole summary (as long as no single part is too wide)
        if all(fm.horizontalAdvance(p) <= width for p in shown.elements[1].summary().split(SUMMARY_SEP)):
            assert SUMMARY_SEP.join(lines) == shown.elements[1].summary()
    # the sector row (5 parameters) is taller than the uniform row (2 parameters) and grows when narrower
    h = lambda k: tree.visualItemRect(tree.topLevelItem(k)).height()        # noqa: E731
    assert h(1) > h(0)
    tall = h(1)
    tree.setFixedWidth(max(140, tree.width() // 2))
    for _ in range(5):
        qapp.processEvents()
    assert h(1) > tall


def test_the_program_starts_on_an_empty_sheet(qapp, monkeypatch):
    """His list (30 Oct): no scene at the start; Elements ~260 px over Plot settings on the right."""
    from app.main_window import MainWindow
    from app.window.layout import DEFAULT_ELEMENTS_HEIGHT
    monkeypatch.setattr(MainWindow, "START_SCENE", None)
    w = MainWindow()
    w.resize(1536, 830)
    w.show()
    for _ in range(20):
        qapp.processEvents()
    try:
        assert w.elements == [] and w.scene_title == "untitled" and not w.model.is_modified
        assert abs(w.dock_elements.height() - DEFAULT_ELEMENTS_HEIGHT) <= 3
        assert w.dockWidgetArea(w.dock_settings) == w.dockWidgetArea(w.dock_elements)
        assert w.dock_settings.y() > w.dock_elements.y()
    finally:
        w.close()


def test_user_guide_opens_with_f1_and_finds_words(window, qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.user_guide_text import CHAPTERS
    window.show()
    qapp.processEvents()
    window.activateWindow()
    QTest.keyClick(window, Qt.Key_F1)
    qapp.processEvents()
    g = window._guide
    assert g.isVisible() and g.toc.count() == len(CHAPTERS) and "Getting started" in g.text.toPlainText()
    g.show_key("keys")
    assert "Ctrl+S" in g.text.toPlainText()                          # the live shortcut table
    g.find.setText("Kutta")
    g.find_next()
    assert "Kutta" in g.text.toPlainText()
    g.find.setText("no such word xyz")
    g.find_next()
    assert "not in the guide" in g.note.text()
    from app.user_guide import full_html
    page = full_html(window.theme, window.shortcuts)
    assert all(t in page for _k, t, _x in CHAPTERS[:1]) and "{keys}" not in page
    g.close()


def test_sign_conventions_dialog_has_a_card_per_element(window, qapp):
    from app.conventions_dialog import CARDS, ConventionFigure, ConventionsDialog
    from app.element_specs import ELEMENT_SPECS
    d = ConventionsDialog(window.theme, window)
    d.show()
    qapp.processEvents()
    figs = d.findChildren(ConventionFigure)
    assert {k for k, *_ in CARDS} == {s.key for s in ELEMENT_SPECS} and len(figs) == len(CARDS)
    for f in figs:
        f.grab()                                                     # every figure paints
    d.close()


def test_first_start_is_known_before_the_loading_screen(qapp):
    from PySide6.QtCore import QSettings

    from app.splash import LoadingScreen
    from app.startup import PREPARED_KEY, is_first_start, mark_prepared
    s = QSettings()
    s.remove(PREPARED_KEY)
    assert is_first_start()
    mark_prepared()
    s.setValue("hardware/profile", s.value("hardware/profile") or "{}")
    assert not is_first_start()
    screen = LoadingScreen(first_start=True)
    screen.grab()
    assert screen.first
    screen.close()
