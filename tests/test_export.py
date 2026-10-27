"""Export: figure as PNG (1×–4×) / SVG / PDF, data as CSV tables; File menu + plot bar Export button."""
import csv
import os

import pytest


@pytest.fixture
def win(qapp):
    from app.main_window import MainWindow
    w = MainWindow()
    w._ask_save_changes = lambda: "discard"
    w.messages = []
    w._notify_user = lambda kind, title, text: w.messages.append((kind, title, text))
    w.resize(1400, 860)
    w.show()
    qapp.processEvents()
    w.canvas.set_view((-4.0, 4.0), (-3.0, 3.0))
    w.canvas.recompute()
    qapp.processEvents()
    yield w
    w.close()


def test_png_size_follows_the_scale(win, tmp_path):
    from PySide6.QtGui import QImage
    from app.export import figure_size, render_figure
    s = figure_size(win.canvas)
    for k in (1, 3):
        path = str(tmp_path / f"f{k}.png")
        render_figure(win.canvas, path, "png", k)
        img = QImage(path)
        assert abs(img.width() - k * s.width()) <= k and abs(img.height() - k * s.height()) <= k


def test_png_lines_grow_with_the_scale(win, tmp_path):
    """A 3× PNG looks like the screen, only sharper: the streamlines are about 3× wider in pixels."""
    import numpy as np
    from PySide6.QtGui import QColor, QImage
    from app.export import render_figure
    from physics import Uniform
    win.load_scene([Uniform()], ((-4, 4), (-3, 3)), title="uniform")
    win.canvas.recompute()
    widths = []
    for k in (1, 3):
        path = str(tmp_path / f"u{k}.png")
        render_figure(win.canvas, path, "png", k, background="white")
        img = QImage(path)
        x = img.width() // 3
        line = QColor(win.theme["streamline"])
        dark = [abs(QColor(img.pixel(x, y)).lightness() - line.lightness()) < 60 for y in range(img.height())]
        runs, n = [], 0
        for d in dark:
            if d:
                n += 1
            elif n:
                runs.append(n)
                n = 0
        widths.append(np.median(runs))
    assert widths[1] >= 2.2 * widths[0]


def test_png_background_options(win, tmp_path):
    from PySide6.QtGui import QColor, QImage
    from app.export import render_figure
    for bg, check in (("white", lambda c: c.name() == "#ffffff"),
                      ("paper", lambda c: c.name() == win.theme["plot_bg"].lower()),
                      ("transparent", lambda c: c.alpha() == 0)):
        path = str(tmp_path / f"{bg}.png")
        render_figure(win.canvas, path, "png", 1, background=bg)
        img = QImage(path)
        assert check(QColor.fromRgba(img.pixel(2, 2)))           # a corner outside the plot area


def test_svg_is_clipped_to_the_plot_area(win, tmp_path):
    from app.export import render_figure
    path = str(tmp_path / "f.svg")
    render_figure(win.canvas, path, "svg")
    text = open(path, encoding="utf-8").read()
    assert text.startswith("<?xml") and '<clipPath id="plot-area">' in text
    assert 'clip-path="url(#plot-area)"' in text and "<path" in text
    assert "IBM Plex Mono, Consolas" in text                     # font fallback on other computers
    from xml.dom import minidom
    minidom.parseString(text.encode())                           # well-formed XML


def test_pdf_is_written(win, tmp_path):
    from app.export import render_figure
    path = str(tmp_path / "f.pdf")
    render_figure(win.canvas, path, "pdf")
    with open(path, "rb") as f:
        assert f.read(5) == b"%PDF-"
    assert os.path.getsize(path) > 10_000


def test_light_colors_from_the_dark_theme(win, tmp_path):
    from PySide6.QtGui import QColor, QImage
    from app.export import render_figure
    from app.theme import DARK, LIGHT
    win.apply_theme(DARK)
    path = str(tmp_path / "light.png")
    render_figure(win.canvas, path, "png", 1, background="paper", light=True)
    assert QColor(QImage(path).pixel(2, 2)).name() == LIGHT["plot_bg"].lower()
    assert win.canvas.theme is DARK                              # the screen stays dark


def _read(path, sep=","):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.reader(f, delimiter=sep))


def test_csv_tables(win, tmp_path):
    from app.export import export_data
    written = export_data(str(tmp_path / "scene.csv"), ["elements", "stagnation", "streamlines", "field"],
                          win.elements, win.canvas, grid_nx=21)
    names = sorted(os.path.basename(p) for p in written)
    assert names == ["scene_elements.csv", "scene_field.csv", "scene_stagnation.csv", "scene_streamlines.csv"]
    el = _read(str(tmp_path / "scene_elements.csv"))
    assert el[0][:3] == ["index", "type", "enabled"] and len(el) == 1 + len(win.elements)
    st = _read(str(tmp_path / "scene_stagnation.csv"))
    assert len(st) == 1 + len(win.canvas.stagnation_points)
    xs = sorted(float(r[1]) for r in st[1:])
    assert xs == pytest.approx([-0.98725, 0.98725], abs=1e-4)          # lifting cylinder, Γ = −2
    fl = _read(str(tmp_path / "scene_field.csv"))
    assert fl[0][:4] == ["x [m]", "y [m]", "u [m/s]", "v [m/s]"]
    rows = [r for r in fl[1:] if r[2]]
    inside = [r for r in fl[1:] if (float(r[0]) ** 2 + float(r[1]) ** 2) < 0.9 and r[2]]
    assert rows and len(fl) - 1 == 21 * len({r[1] for r in fl[1:]})
    far = min(rows, key=lambda r: abs(float(r[0]) + 4) + abs(float(r[1])))
    assert float(far[2]) == pytest.approx(1.0, abs=0.1)              # far upstream u ≈ V∞
    assert inside                                                    # (inside the cylinder: still a flow field)
    sl = _read(str(tmp_path / "scene_streamlines.csv"))
    assert sl[0] == ["line", "point", "x [m]", "y [m]"] and len(sl) > 100


def test_csv_semicolon_uses_decimal_comma(win, tmp_path):
    from app.export import export_data
    (path,) = export_data(str(tmp_path / "st.csv"), ["stagnation"], win.elements, win.canvas, separator=";")
    rows = _read(path, ";")
    assert path.endswith("st.csv") and "," in rows[1][1] and "." not in rows[1][1]


def test_export_from_the_menu(win, qapp, tmp_path):
    win._run_dialog = lambda dlg: True                           # dialogs answered with their defaults
    target = str(tmp_path / "menu_fig")
    win._ask_export_path = lambda suggested, filt: target
    assert win.export_figure() and os.path.exists(target + ".png")
    target = str(tmp_path / "menu_data.csv")
    win._ask_export_path = lambda suggested, filt: target
    assert win.export_data() and os.path.exists(str(tmp_path / "menu_data_elements.csv"))
    assert win.act_export_fig.shortcut().toString() == "Ctrl+E"


def test_export_options_are_remembered(win, qapp, tmp_path):
    from app.export import ExportFigureDialog
    win._run_dialog = lambda dlg: (dlg.fmt_buttons["svg"].setChecked(True), True)[1]
    win._ask_export_path = lambda suggested, filt: str(tmp_path / "x.svg")
    assert win.export_figure()
    dlg = ExportFigureDialog(win.canvas, win._export_settings("figure"), win)
    assert dlg.fmt() == "svg" and not dlg.res_row.isEnabled()


def test_export_cancelled(win):
    win._run_dialog = lambda dlg: False
    assert not win.export_figure() and not win.export_data()
