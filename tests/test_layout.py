"""Package D: panels only left / right (no floating, no tabs), the element palette moves as a whole
to either side of the plot, Plot settings sections can be hidden, the layout is remembered."""
import pytest


def make_window(qapp, size=(1400, 860)):
    from app.main_window import MainWindow
    w = MainWindow()
    w._ask_save_changes = lambda: "discard"
    w.resize(*size)
    w.show()
    qapp.processEvents()
    return w


@pytest.fixture
def win(qapp):
    w = make_window(qapp)
    yield w
    w.close()


def test_panels_only_beside_the_plot(win):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDockWidget, QMainWindow
    for d in (win.dock_elements, win.dock_settings, win.dock_surface):
        assert d.allowedAreas() == Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
        assert not d.features() & QDockWidget.DockWidgetFloatable
        assert d.features() & QDockWidget.DockWidgetMovable
    assert win.dockWidgetArea(win.dock_elements) == win.dockWidgetArea(win.dock_settings) == Qt.RightDockWidgetArea
    assert win.dockWidgetArea(win.dock_surface) == Qt.LeftDockWidgetArea           # opens left of the plot
    assert not win.dockOptions() & QMainWindow.AllowTabbedDocks        # never stacked as tabs
    assert win.dockOptions() & QMainWindow.AllowNestedDocks             # 28 Oct: a second column is allowed


def test_drop_indicator_in_wood_color(win, qapp):
    from PySide6.QtGui import QColor, QPalette
    from app.theme import DARK
    assert qapp.palette().color(QPalette.Highlight) == QColor(win.theme["accent_strong"])
    win.apply_theme(DARK)
    assert qapp.palette().color(QPalette.Highlight) == QColor(DARK["accent_strong"])


def test_palette_moves_as_a_whole_to_the_other_side(win, qapp):
    from PySide6.QtCore import QPoint
    pal, lay = win.element_toolbar, win._desk_layout
    width = pal.width()
    assert lay.indexOf(pal) == 0 and win.palette_side == "left"
    right = win.desk.mapToGlobal(QPoint(win.desk.width() - 30, 200))
    pal.drag_moved.emit(right)
    qapp.processEvents()
    ind = win._drop_indicator
    assert ind.isVisible() and ind.geometry() == win._palette_slot("right")
    pal.drag_finished.emit(right)
    qapp.processEvents()
    assert not ind.isVisible()
    assert win.palette_side == "right" and lay.indexOf(pal) > lay.indexOf(win.canvas)
    assert pal.width() == width and pal.x() > win.canvas.x()
    pal.drag_finished.emit(win.desk.mapToGlobal(QPoint(30, 200)))
    qapp.processEvents()
    assert win.palette_side == "left" and pal.x() < win.canvas.x()


def test_palette_drag_with_the_mouse(win, qapp):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    pal = win.element_toolbar
    start = QPoint(pal.width() // 2, 12)                      # on the ADD heading
    QTest.mousePress(pal, Qt.LeftButton, Qt.NoModifier, start)
    target = pal.mapFromGlobal(win.desk.mapToGlobal(QPoint(win.desk.width() - 40, 300)))
    QTest.mouseMove(pal, start + QPoint(20, 0))
    QTest.mouseMove(pal, target)
    QTest.mouseRelease(pal, Qt.LeftButton, Qt.NoModifier, target)
    qapp.processEvents()
    assert win.palette_side == "right"


def test_plot_settings_sections_can_be_hidden(win, qapp):
    sp = win.settings_panel
    assert list(sp.sections) == ["view", "streamlines", "layers", "particles", "pulses", "computation"]
    win.section_actions["pulses"].setChecked(False)
    qapp.processEvents()
    assert not sp.section_visible("pulses") and sp.hidden_sections() == ["pulses"]
    assert win.dock_settings.titleBarWidget().note.text() == "1 HIDDEN"
    sp.set_section_visible("pulses", True)
    assert win.section_actions["pulses"].isChecked()
    assert win.dock_settings.titleBarWidget().note.text() == ""
    title = win.dock_settings.titleBarWidget()
    from PySide6.QtCore import Qt
    assert title.contextMenuPolicy() == Qt.CustomContextMenu


def test_layout_is_remembered_and_can_be_reset(qapp):
    from PySide6.QtCore import Qt
    w = make_window(qapp)
    w.addDockWidget(Qt.LeftDockWidgetArea, w.dock_settings)
    w.set_palette_side("right")
    w.settings_panel.set_section_visible("computation", False)
    qapp.processEvents()
    w.close()

    w2 = make_window(qapp)
    try:
        assert w2.dockWidgetArea(w2.dock_settings) == Qt.LeftDockWidgetArea
        assert w2.dockWidgetArea(w2.dock_elements) == Qt.RightDockWidgetArea
        assert w2.dock_settings.widget().outer[0] > 0                    # paper margin on the left side
        assert w2.palette_side == "right"
        assert w2.settings_panel.hidden_sections() == ["computation"]
        w2.reset_layout()
        qapp.processEvents()
        assert w2.dockWidgetArea(w2.dock_settings) == Qt.RightDockWidgetArea
        assert w2.palette_side == "left" and w2.settings_panel.hidden_sections() == []
        assert w2.dock_settings.isVisible() and w2.dock_elements.isVisible()
    finally:
        w2.close()


def test_saved_layout_of_another_version_is_ignored(qapp):
    from PySide6.QtCore import QSettings, Qt
    s = QSettings()
    s.setValue("layout/version", 0)
    s.setValue("layout/palette_side", "right")
    w = make_window(qapp)
    try:
        assert w.palette_side == "left"
        assert w.dockWidgetArea(w.dock_settings) == Qt.RightDockWidgetArea
    finally:
        w.close()


def test_plot_settings_never_hide_under_their_scrollbar(qapp):
    """Regression: with the vertical scrollbar shown, the right edge of the panel (e.g. a slider's
    handle at its maximum) was covered: the content was wider than the visible area."""
    from app.main_window import MainWindow
    w = MainWindow()
    w._ask_save_changes = lambda: "discard"
    w.resize(1300, 640)                                         # short: Plot settings needs its scrollbar
    w.show()
    for _ in range(5):
        qapp.processEvents()
    sp = w.settings_panel
    try:
        assert sp.verticalScrollBar().isVisible()
        assert sp.widget().width() <= sp.viewport().width()
        s = sp.sliders["density"]
        right = s.mapTo(sp.viewport(), s.rect().topRight()).x()
        assert right < sp.viewport().width()
    finally:
        w.close()


def test_view_does_not_jump_back_and_forth(qapp):
    """1200 × 760 used to make the left axis switch between two widths ("-2.5" / "-2" labels): with
    the aspect lock the y range changed with it, ~40 times a second, for ever."""
    import time
    w = make_window(qapp)
    w.resize(1200, 760)
    w.show()
    changes = []
    w.canvas.vb.sigRangeChanged.connect(lambda *a: changes.append(1))
    t0 = time.time()
    while time.time() - t0 < 0.6:
        qapp.processEvents()
    changes.clear()
    t0 = time.time()
    while time.time() - t0 < 0.8:
        qapp.processEvents()
    w.close()
    assert len(changes) <= 1


def test_paths_point_at_the_bundled_files():
    import os
    from app.paths import ASSETS_DIR, PRESETS_DIR
    assert os.path.isdir(os.path.join(ASSETS_DIR, "fonts")) and os.path.isdir(PRESETS_DIR)


def _settle(qapp, n=20):
    for _ in range(n):
        qapp.processEvents()


def test_surface_pressure_panel_width_is_remembered_and_reset(qapp):
    """His list (30 Oct): it opens on the left at ~330 px, as wide as he left it next time; an odd width or
    Reset layout gives the default again (also while it is closed); unticking the layer closes it."""
    from PySide6.QtCore import QSettings, Qt

    from app.theme import LAYOUT
    from app.window.layout import SURFACE_WIDTH_KEY
    his = (1800, 900)                                                # (room to widen it: the plot needs ~840 px)
    w = make_window(qapp, his)
    try:
        sp, du = w.settings_panel, w.dock_surface
        sp.layer_boxes["surface"].setChecked(True)
        _settle(qapp)
        assert du.isVisible() and w.dockWidgetArea(du) == Qt.LeftDockWidgetArea
        assert abs(du.width() - LAYOUT["surface_panel_width"]) <= 3
        w.resizeDocks([du], [400], Qt.Horizontal)
        _settle(qapp)
        wide = du.width()
        assert wide > LAYOUT["surface_panel_width"] + 20
        sp.layer_boxes["surface"].setChecked(False)                  # unticked: the panel closes …
        _settle(qapp)
        assert not du.isVisible() and abs(int(QSettings().value(SURFACE_WIDTH_KEY)) - wide) <= 1
        sp.layer_boxes["surface"].setChecked(True)                   # … and opens as wide as it was
        _settle(qapp)
        assert abs(du.width() - wide) <= 3
        w.save_layout()
    finally:
        w.close()
    w = make_window(qapp, his)                                       # the next start
    try:
        w.settings_panel.layer_boxes["surface"].setChecked(True)
        _settle(qapp)
        assert abs(w.dock_surface.width() - wide) <= 3
        w.settings_panel.layer_boxes["surface"].setChecked(False)
        _settle(qapp)
        w.reset_layout()                                             # closed: the default next time
        w.settings_panel.layer_boxes["surface"].setChecked(True)
        _settle(qapp)
        assert abs(w.dock_surface.width() - LAYOUT["surface_panel_width"]) <= 3
        QSettings().setValue(SURFACE_WIDTH_KEY, 5000)                # nonsense saved: the default
        assert w.surface_width() == LAYOUT["surface_panel_width"]
    finally:
        w.close()


def test_reset_layout_keeps_the_scene(win, qapp):
    n = len(win.elements)
    win.dock_elements.hide()
    win.reset_layout()
    _settle(qapp)
    assert len(win.elements) == n and win.dock_elements.isVisible()


def test_background_grid_can_be_switched_off_and_is_remembered(qapp):
    from app.main_window import GRID_KEY
    w = make_window(qapp)
    try:
        assert w.canvas._grid.isVisible()
        w.layer_actions["grid"].setChecked(False)                     # View → Layers (= Plot settings → Layers)
        assert not w.canvas._grid.isVisible() and not w.settings_panel.layer_boxes["grid"].isChecked()
    finally:
        w.close()
    from PySide6.QtCore import QSettings
    assert QSettings().value(GRID_KEY, True, type=bool) is False
    w = make_window(qapp)
    try:
        assert not w.canvas._grid.isVisible()
    finally:
        w.close()


def test_surface_pressure_panel_can_be_dragged_to_the_right_and_stays_there(qapp):
    """His report (30 Oct): after 20.7B the panel could not be moved any more (opening it put it back on the
    left while Qt was dragging it). Dragged to the right it stays there, also closed and opened again and at
    the next start."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from physics.elements import Doublet, Uniform
    w = make_window(qapp, (1536, 830))
    try:
        w.model.add(Uniform())
        w.model.add(Doublet(mu=1.0))
        box = w.settings_panel.layer_boxes["surface"]
        box.setChecked(True)
        _settle(qapp)
        du, title = w.dock_surface, w.dock_surface.titleBarWidget()
        assert w.dockWidgetArea(du) == Qt.LeftDockWidgetArea
        start = QPoint(60, 10)
        QTest.mousePress(title, Qt.LeftButton, Qt.NoModifier, start)
        target = w.mapToGlobal(QPoint(1300, 300))
        for k in range(1, 30):
            g = title.mapToGlobal(start) + (target - title.mapToGlobal(start)) * k / 29
            QTest.mouseMove(title, title.mapFromGlobal(g))
            QTest.qWait(20)
        QTest.mouseRelease(title, Qt.LeftButton, Qt.NoModifier, title.mapFromGlobal(target))
        QTest.qWait(800)                                             # (the docks' animation)
        assert w.dockWidgetArea(du) == Qt.RightDockWidgetArea and not du.isFloating()
        box.setChecked(False)
        _settle(qapp)
        box.setChecked(True)
        _settle(qapp)
        assert w.dockWidgetArea(du) == Qt.RightDockWidgetArea
        w.save_layout()
    finally:
        w.close()
    w = make_window(qapp, (1536, 830))
    try:
        w.settings_panel.layer_boxes["surface"].setChecked(True)
        _settle(qapp)
        assert w.dockWidgetArea(w.dock_surface) == Qt.RightDockWidgetArea
    finally:
        w.close()
