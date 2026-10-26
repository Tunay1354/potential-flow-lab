"""Package C: drafting-paper theme — header with the menus on the ruler, bundled fonts, framed panels,
title block under the plot, light / dark switch."""
import pytest


@pytest.fixture
def win(qapp):
    from app.main_window import MainWindow
    w = MainWindow()
    w._ask_save_changes = lambda: "discard"
    w.resize(1400, 860)
    w.show()
    qapp.processEvents()
    w.canvas.recompute()
    qapp.processEvents()
    yield w
    w.close()


def test_bundled_fonts_are_used(qapp):
    from PySide6.QtGui import QFontDatabase
    families = set(QFontDatabase.families())
    assert {"IBM Plex Mono", "Barlow", "Barlow Condensed"} <= families
    assert qapp.font().family() == "Barlow"


def test_css_colors_with_alpha():
    from app.chrome import color
    c = color("#3A332610")
    assert (c.red(), c.green(), c.blue(), c.alpha()) == (0x3A, 0x33, 0x26, 0x10)


def test_menus_sit_on_the_ruler_with_room_for_the_beaver(win):
    header = win.header
    assert win.menuWidget() is header and win.menuBar() is header.menu_bar
    assert header.ruler.isAncestorOf(win.menuBar())
    titles = [a.text() for a in win.menuBar().actions()]
    assert titles == ["&File", "&Edit", "E&lements", "&View", "&Presets", "&Help"]
    perch = header.ruler.beaver_perch
    help_rect = win.menuBar().actionGeometry(win.menuBar().actions()[-1])
    help_right = win.menuBar().mapTo(header.ruler, help_rect.topRight()).x()
    assert perch.width() >= 100 and 0 <= perch.x() - help_right <= 20     # right next to Help, still empty
    assert perch.findChildren(type(perch)) == []


def test_header_shows_version_and_file(win, tmp_path):
    from app_info import APP_VERSION
    assert win.header.plank.version.text() == f"REV {APP_VERSION}"
    assert win.header.plank.file.text().startswith("SHEET  not saved")
    path = str(tmp_path / "cyl.pflow")
    win._ask_save_path = lambda suggested: path
    assert win.save_scene_as()
    assert win.header.plank.file.text() == "SHEET  cyl.pflow"
    assert win.canvas.title_block.values["file"].text() == "cyl.pflow"


def test_title_block_follows_scene_and_view(win, qapp):
    tb = win.canvas.title_block.values
    assert tb["scene"].text() == win.scene_title
    assert tb["elements"].text() == f"{len(win.elements)}  ·  ⊗ {len(win.canvas.stagnation_points)}"
    win.canvas.set_view((-2.0, 2.0), (-1.0, 1.0))
    qapp.processEvents()
    assert tb["view"].text().startswith("x[−2.00, 2.00]")
    win.model.remove(0)
    qapp.processEvents()
    assert tb["elements"].text().startswith(f"{len(win.elements)}  ·")
    assert win.dock_elements.titleBarWidget().note.text() == f"{len(win.elements)} ITEMS"


def test_theme_switch_keeps_fonts_and_recolors(win, qapp):
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QToolButton
    from app.theme import DARK, LIGHT
    buttons = [b for b in win.element_toolbar.findChildren(QToolButton) if b.defaultAction() is not None]
    for theme in (DARK, LIGHT):
        win.apply_theme(theme)
        qapp.processEvents()
        assert all(b.font().family() == "IBM Plex Mono" and b.font().capitalization() == QFont.AllUppercase
                   for b in buttons)
        assert win.menuBar().font().capitalization() == QFont.AllUppercase
        assert win.header.plank.theme is theme and win.dock_settings.widget().theme is theme
        assert win.canvas.plot.backgroundBrush().color().name().upper() == theme["plot_bg"]


def test_dock_card_keeps_a_paper_margin_to_the_window_edge(win, qapp):
    from PySide6.QtCore import Qt
    from app.theme import LAYOUT
    g = LAYOUT["gap"]
    d = win.dock_settings
    assert d.widget().outer == (0, 0, g, g) and d.titleBarWidget().outer == (0, 0, g, 0)
    win.addDockWidget(Qt.LeftDockWidgetArea, d)
    qapp.processEvents()
    assert d.widget().outer == (g, 0, 0, g)


def test_plot_card_frame_on_all_four_sides(win):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QColor
    cv = win.canvas
    img = win.grab().toImage()
    d = cv.devicePixelRatioF()
    tl, br = cv.mapTo(win, QPoint(0, 0)), cv.mapTo(win, QPoint(cv.width(), cv.height()))
    x0, y0, x1, y1 = int(tl.x() * d), int(tl.y() * d), int(br.x() * d) - 1, int(br.y() * d) - 1
    xm, ym = (x0 + x1) // 2, (y0 + y1) // 2
    ink = QColor(win.theme["ink"]).name()
    for x, y in ((x0, ym), (x1, ym), (xm, y0), (xm, y1)):
        assert QColor(img.pixel(x, y)).name() == ink


def test_drop_down_lists_use_the_styled_delegate(win):
    from PySide6.QtWidgets import QComboBox, QStyledItemDelegate
    combos = win.settings_panel.findChildren(QComboBox)
    assert combos and all(type(c.itemDelegate()) is QStyledItemDelegate for c in combos)
