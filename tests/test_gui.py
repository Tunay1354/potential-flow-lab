"""GUI tests (offscreen): dialogs agree with the physics classes, and every user action goes through
the scene model so that it can be undone."""
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
    yield w
    w.close()
    w.deleteLater()


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
    from app.scene import PRESETS
    window.load_scene(*PRESETS["Source near a wall"](), title="Source near a wall")
    assert types(window) == ["wall", "source"]
    assert "Source near a wall" in window.windowTitle()
    window.clear_all()
    assert window.elements == [] and window.issue_label.text() == "✓ scene OK"
    window.model_undo()
    window.model_undo()
    assert types(window) == ["uniform", "doublet", "vortex"]


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
    from app.scene import PRESETS
    shown.load_scene(*PRESETS["Source near a wall"](), title="t")
    qapp.processEvents()
    _click(qapp, shown, 2.0, 0.0)                      # on the wall y = 0
    assert shown.elements_panel.current_row() == 0
    shown.load_scene(*PRESETS["Corner flow (90° sector, n = 2)"](), title="t")
    qapp.processEvents()
    shown.select_element(-1)
    _click(qapp, shown, 0.0, 2.0)                      # on the vertical side of the wedge
    assert shown.elements_panel.current_row() == 0


def test_click_elsewhere_clears_but_delete_button_keeps(shown, qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    shown.select_element(1)
    QTest.mouseClick(shown.settings_panel.s_density, Qt.LeftButton)       # any other widget
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
    from app.scene import PRESETS
    monkeypatch.setattr(mw, "ElementDialog", FakeDialog)
    shown.load_scene(*PRESETS["Rankine half-body"](), title="t")
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
    assert cv.background
    done = []
    cv.computed.connect(lambda n, ms: done.append(n))
    shown.load_scene([Uniform(), Doublet(mu=1.0)], title="cylinder")
    assert _wait_for(qapp, cv, lambda: bool(done))
    assert done[-1] > 10 and cv._lines.getData()[0].size > 0


def test_only_the_newest_request_is_drawn(shown, qapp):
    cv = shown.canvas
    cv.wait_idle()
    qapp.processEvents()
    done = []
    cv.computed.connect(lambda n, ms: done.append(n))
    for density in (0.4, 0.7, 1.6):                  # three quick changes: only the last one counts
        cv.density = density
        cv.request()
    elements, xr, yr, kw = cv._job_args()             # what the last request computes
    assert _wait_for(qapp, cv, lambda: bool(done))
    for _ in range(5):
        cv.wait_idle(100)
        qapp.processEvents()
    assert len(done) == 1
    from physics.streamlines import trace_streamlines
    assert kw["density"] == 1.6
    assert done[0] == len(trace_streamlines(elements, xr, yr, **kw).lines)


def test_closing_during_a_computation_waits_and_does_not_hang(window, qapp):
    import time
    window.show()
    window.load_scene([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)], title="lifting")
    window.canvas.density = 2.0
    window.canvas.request()
    t0 = time.time()
    window.close()
    assert window.canvas.wait_idle(0)                # nothing running any more
    assert time.time() - t0 < 10.0
