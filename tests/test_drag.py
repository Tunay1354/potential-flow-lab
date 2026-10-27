"""Phase 2c: mouse modes (Select · Move · Pan), dragging elements in Move mode (one undo step, Shift
snaps, Esc cancels, nothing computed while dragging), dropping palette elements on the plot, and the
keyboard shortcuts the user can change."""
import pytest


@pytest.fixture
def win(qapp):
    from app.main_window import MainWindow
    w = MainWindow()
    w._ask_save_changes = lambda: "discard"
    w.resize(1400, 860)
    w.show()
    qapp.processEvents()
    w.canvas.set_view((-4.0, 4.0), (-3.0, 3.0))
    w.canvas.recompute()
    qapp.processEvents()
    yield w
    w.close()


def _vp_pos(win, x, y):
    from PySide6.QtCore import QPointF
    plot = win.canvas.plot
    return plot.mapFromScene(win.canvas.vb.mapViewToScene(QPointF(x, y)))


def _mouse(win, kind, pos, buttons, modifiers=None):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    vp = win.canvas.plot.viewport()
    ev = QMouseEvent(kind, QPointF(pos), QPointF(vp.mapToGlobal(pos)), Qt.LeftButton, buttons,
                     modifiers if modifiers is not None else Qt.NoModifier)
    QApplication.sendEvent(vp, ev)


def _drag(qapp, win, start, end, shift=False, steps=6, before_release=None):
    """Press at data point `start`, move in steps to `end`, release (like a real mouse)."""
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtTest import QTest
    mod = Qt.ShiftModifier if shift else Qt.NoModifier
    QTest.qWait(400)
    a, b = _vp_pos(win, *start), _vp_pos(win, *end)
    _mouse(win, QEvent.MouseButtonPress, a, Qt.LeftButton, mod)
    for k in range(1, steps + 1):
        p = a + (b - a) * (k / steps)
        _mouse(win, QEvent.MouseMove, p, Qt.LeftButton, mod)
        qapp.processEvents()
    if before_release:
        before_release()
    _mouse(win, QEvent.MouseButtonRelease, b, Qt.NoButton, mod)
    for _ in range(3):
        qapp.processEvents()


def _vortex(win):
    return next(i for i, e in enumerate(win.elements) if e.TYPE == "vortex")


def test_three_modes_buttons_and_menu_in_sync(win):
    cv = win.canvas
    assert cv.mode == "select" and cv.bar.btn_select.isChecked()
    assert [b.text() for b in (cv.bar.btn_select, cv.bar.btn_move, cv.bar.btn_pan)] == ["Select", "Move", "Pan"]
    cv.bar.btn_move.click()
    assert cv.mode == "move" and win.mode_actions["move"].isChecked()
    win.mode_actions["pan"].trigger()
    assert cv.mode == "pan" and cv.bar.btn_pan.isChecked()
    assert "[H]" in cv.bar.btn_pan.toolTip()


def test_select_mode_does_not_move_elements(win, qapp):
    before = list(win.elements)
    view = win.canvas.vb.viewRange()
    _drag(qapp, win, (0.0, 0.0), (1.5, 1.0))
    assert win.elements == before                    # nothing moved ...
    assert win.canvas.vb.viewRange() != view         # ... the view panned instead


def test_move_mode_drags_one_element_one_undo_step(win, qapp):
    win.canvas.set_mode("move")
    win.select_element(-1)
    computed = []
    win.canvas.computed.connect(lambda n, ms: computed.append(ms))
    views = []
    _drag(qapp, win, (0.0, 0.0), (1.2, 0.7),
          before_release=lambda: views.append((list(win.elements), win.canvas.is_dragging(), len(computed))))
    _, dragging, n_computed = views[0]
    assert dragging and n_computed == 0                          # nothing computed while dragging
    moved = [e for e in win.elements if e.POSITION_KEYS and (e.x0, e.y0) != (0.0, 0.0)]
    assert len(moved) == 1
    assert moved[0].x0 == pytest.approx(1.2, abs=0.02) and moved[0].y0 == pytest.approx(0.7, abs=0.02)
    assert win.canvas.selected == win.elements.index(moved[0])
    assert win.act_undo.text().startswith("Undo move")
    win.model_undo()
    assert all((e.x0, e.y0) == (0.0, 0.0) for e in win.elements if e.POSITION_KEYS)


def test_shift_snaps_to_the_grid(win, qapp):
    win.canvas.set_mode("move")
    _drag(qapp, win, (0.0, 0.0), (1.04, 0.47), shift=True)
    moved = next(e for e in win.elements if e.POSITION_KEYS and (e.x0, e.y0) != (0.0, 0.0))
    assert (moved.x0, moved.y0) == (1.0, 0.5)


def test_escape_cancels_a_drag(win, qapp):
    win.canvas.set_mode("move")
    before = list(win.elements)
    _drag(qapp, win, (0.0, 0.0), (1.5, 1.0), before_release=win.canvas.cancel_drag)
    assert win.elements == before and not win.canvas.is_dragging()
    assert not win.model.can_undo


def test_uniform_flow_and_empty_place_pan_in_move_mode(win, qapp):
    win.canvas.set_mode("move")
    before = list(win.elements)
    view = win.canvas.vb.viewRange()
    _drag(qapp, win, (-3.0, 2.0), (-2.0, 1.0))        # empty place: the view moves
    assert win.elements == before and win.canvas.vb.viewRange() != view


def test_pan_mode_never_selects(win, qapp):
    from test_gui import _click
    win.canvas.set_mode("pan")
    _click(qapp, win, 0.0, 0.0)
    assert win.elements_panel.current_row() == -1


def test_wall_moves_parallel(win, qapp):
    from physics import SymmetryWall, Uniform
    win.load_scene([Uniform(), SymmetryWall(yw=-1.0)], ((-4, 4), (-3, 3)), title="wall")
    win.canvas.recompute()
    qapp.processEvents()
    win.canvas.set_mode("move")
    _drag(qapp, win, (1.0, -1.0), (1.0, -2.0), shift=True)
    wall = win.elements[1]
    assert wall.yw == pytest.approx(-2.0) and wall.theta_w == 0.0


def _drop(qapp, win, key, x, y, shift=False):
    from PySide6.QtCore import QEvent, QMimeData, QPointF, Qt
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
    from PySide6.QtWidgets import QApplication
    from app.canvas import ELEMENT_MIME
    vp = win.canvas.plot.viewport()
    pos = _vp_pos(win, x, y)
    mime = QMimeData()
    mime.setData(ELEMENT_MIME, key.encode())
    mod = Qt.ShiftModifier if shift else Qt.NoModifier
    QApplication.sendEvent(vp, QDragEnterEvent(QPointF(pos), Qt.CopyAction, mime, Qt.LeftButton, mod))
    QApplication.sendEvent(vp, QDragMoveEvent(QPointF(pos), Qt.CopyAction, mime, Qt.LeftButton, mod))
    ghost = win.canvas._ghost.isVisible()
    QApplication.sendEvent(vp, QDropEvent(QPointF(pos), Qt.CopyAction, mime, Qt.LeftButton, mod, QEvent.Drop))
    for _ in range(3):
        qapp.processEvents()
    return ghost


def test_drop_from_palette_opens_the_dialog_at_that_place(win, qapp):
    calls = []
    win.add_element_dialog = lambda key, at=None: calls.append((key, at))
    for mode in ("select", "pan"):                          # works in every mouse mode
        win.canvas.set_mode(mode)
        assert _drop(qapp, win, "vortex", 1.5, -1.0, shift=True)
    assert calls == [("vortex", (1.5, -1.0))] * 2
    calls.clear()
    _drop(qapp, win, "uniform", 0.0, 0.0)                  # no position: just the dialog
    assert calls == [("uniform", None)]
    assert not win.canvas._ghost.isVisible()


def test_dropped_position_fills_the_dialog(win, qapp, monkeypatch):
    import app.main_window as mw
    seen = {}

    class Dialog:
        def __init__(self, spec, theme, editing, parent, values=None, validator=None):
            seen.update(values)

        def exec(self):
            return False                                    # Cancel: nothing added

    monkeypatch.setattr(mw, "ElementDialog", Dialog)
    n = len(win.elements)
    win.add_element_dialog("source", at=(2.25, -0.5))
    assert (seen["x0"], seen["y0"]) == (2.25, -0.5) and len(win.elements) == n
    win.add_element_dialog("wall", at=(0.0, 1.5))
    assert (seen["xw"], seen["yw"]) == (0.0, 1.5)


def test_palette_button_starts_a_drag(win, qapp, monkeypatch):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QDrag, QMouseEvent
    from PySide6.QtWidgets import QApplication, QToolButton
    started = []
    monkeypatch.setattr(QDrag, "exec", lambda self, *a: started.append(self.mimeData()) or Qt.IgnoreAction)
    btn = next(b for b in win.element_toolbar.findChildren(QToolButton) if b.property("element_key") == "source")
    for kind, pos, buttons in ((QEvent.MouseButtonPress, QPointF(20, 20), Qt.LeftButton),
                               (QEvent.MouseMove, QPointF(60, 40), Qt.LeftButton),
                               (QEvent.MouseButtonRelease, QPointF(60, 40), Qt.NoButton)):
        QApplication.sendEvent(btn, QMouseEvent(kind, pos, btn.mapToGlobal(pos), Qt.LeftButton, buttons,
                                                Qt.NoModifier))
    from app.canvas import ELEMENT_MIME
    assert len(started) == 1 and bytes(started[0].data(ELEMENT_MIME)).decode() == "source"


# ---------------------------------------------------------------- keyboard shortcuts
def test_mode_keys(win, qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    win.canvas.plot.setFocus()
    for key, mode in ((Qt.Key_M, "move"), (Qt.Key_H, "pan"), (Qt.Key_V, "select")):
        QTest.keyClick(win.canvas.plot, key)
        qapp.processEvents()
        assert win.canvas.mode == mode


def test_shortcuts_can_be_changed_and_are_remembered(qapp, win):
    from PySide6.QtGui import QKeySequence
    from app.main_window import MainWindow
    from app.shortcuts import ShortcutsDialog
    sc = win.shortcuts
    assert sc.keys("mode.move") == ["M"] and sc.keys("view.fit") == ["F"]
    assert "add.vortex" in sc.entries and sc.keys("add.vortex") == []
    dlg = ShortcutsDialog(sc, win)
    dlg.edits["mode.move"].setKeySequence(QKeySequence("G"))
    dlg.edits["add.vortex"].setKeySequence(QKeySequence("Ctrl+Alt+V"))
    dlg._save()
    assert sc.keys("mode.move") == ["G"] and win.mode_actions["move"].shortcut().toString() == "G"
    assert "[G]" in win.canvas.bar.btn_move.toolTip()
    w2 = MainWindow()
    try:
        assert w2.shortcuts.keys("mode.move") == ["G"] and w2.shortcuts.keys("add.vortex") == ["Ctrl+Alt+V"]
        w2.shortcuts.reset_all()
        assert w2.shortcuts.keys("mode.move") == ["M"]
    finally:
        w2._ask_save_changes = lambda: "discard"
        w2.close()


def test_shortcut_conflicts_are_refused(win):
    from PySide6.QtGui import QKeySequence
    from app.shortcuts import ShortcutsDialog
    dlg = ShortcutsDialog(win.shortcuts, win)
    warnings = []
    dlg._warn = lambda title, text: warnings.append(text)
    dlg.edits["mode.pan"].setKeySequence(QKeySequence("F"))     # F is Fit view
    dlg._save()
    assert warnings and "Fit view" in warnings[0] and win.shortcuts.keys("mode.pan") == ["H"]
    dlg._reset()
    assert win.shortcuts.keys("edit.redo") == dlg.assignment()["edit.redo"]


def test_dividing_lines_come_back_after_a_drag(win, qapp):
    cv = win.canvas
    cv.set_mode("move")
    _drag(qapp, win, (0.0, 0.0), (0.4, 0.3))
    for _ in range(50):
        cv.wait_idle(50)
        qapp.processEvents()
    cv.set_mode("select")
    win.select_stagnation(0)
    qapp.processEvents()
    x, _ = cv._dividing_item.getData()
    assert cv._dividing_item.isVisible() and x is not None and len(x) > 0
    _drag(qapp, win, (0.4, 0.3), (0.4, 0.3), before_release=cv.cancel_drag)     # an Esc'd drag too
    assert cv._dividing_item.isVisible()


def test_sector_vertex_is_not_marked(win, qapp):
    from physics import SectorFlow, Source
    win.load_scene([SectorFlow(V=1.0)], ((-1, 3), (-1, 3)), title="corner")
    win.canvas.recompute()
    qapp.processEvents()
    assert win.canvas.stagnation_points == []                  # the corner itself is not marked
    win.load_scene([SectorFlow(V=1.0), Source(m=1.0, x0=1.0, y0=1.0)], ((-1, 3), (-1, 3)), title="corner+")
    win.canvas.recompute()
    qapp.processEvents()
    pts = win.canvas.stagnation_points
    assert pts and all(p.kind != "vertex" for p in pts)
    assert set(win.canvas._dividing_owner) <= set(range(len(pts)))
