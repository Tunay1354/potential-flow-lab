"""Package D: panels only left / right (no floating, no tabs), the element palette moves as a whole
to either side of the plot, Plot settings sections can be hidden, the layout is remembered."""
import pytest


def make_window(qapp):
    from app.main_window import MainWindow
    w = MainWindow()
    w._ask_save_changes = lambda: "discard"
    w.resize(1400, 860)
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
    for d in (win.dock_elements, win.dock_settings):
        assert d.allowedAreas() == Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
        assert not d.features() & QDockWidget.DockWidgetFloatable
        assert d.features() & QDockWidget.DockWidgetMovable
        assert win.dockWidgetArea(d) == Qt.RightDockWidgetArea
    assert not win.dockOptions() & QMainWindow.AllowTabbedDocks        # never stacked as tabs
    assert not win.dockOptions() & QMainWindow.AllowNestedDocks         # one column per side


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
        s = sp.s_density
        right = s.mapTo(sp.viewport(), s.rect().topRight()).x()
        assert right < sp.viewport().width()
    finally:
        w.close()
