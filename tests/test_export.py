"""Export: figure as PNG (1×–4×) / SVG / PDF, animation as GIF / MP4, data as CSV tables; File menu + plot bar
Export button."""
import csv
import os

import numpy as np
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
    cv = win.canvas
    written = export_data(str(tmp_path / "scene.csv"), ["elements", "stagnation", "streamlines", "field"],
                          win.elements, cv.view(), cv.stagnation_points, cv.last_result.lines, grid_nx=21)
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
    (path,) = export_data(str(tmp_path / "st.csv"), ["stagnation"], win.elements, win.canvas.view(),
                          win.canvas.stagnation_points, separator=";")
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


def test_mirrored_axes_only_in_the_file(win, qapp, tmp_path):
    """Axes on all four sides in the figure, the plot area in the middle; the screen keeps two axes
    and the same visible region."""
    from app.export import mirrored_axes, render_figure
    pi, vb = win.canvas.plot.getPlotItem(), win.canvas.vb
    view = vb.viewRange()
    with mirrored_axes(win.canvas, numbers=True):
        r, area = pi.sceneBoundingRect(), vb.sceneBoundingRect()
        assert pi.getAxis("top").isVisible() and pi.getAxis("right").isVisible()
        assert abs((area.left() - r.left()) - (r.right() - area.right())) <= 2         # centered
        assert abs((area.top() - r.top()) - (r.bottom() - area.bottom())) <= 2
        x0, x1 = vb.viewRange()[0]
        assert x0 <= view[0][0] + 1e-6 and x1 >= view[0][1] - 1e-6                     # nothing cut off
    assert not pi.getAxis("top").isVisible() and not pi.getAxis("right").isVisible()
    (x0, x1), (y0, y1) = vb.viewRange()                          # the region on the screen is still shown
    assert x0 <= view[0][0] + 1e-6 and x1 >= view[0][1] - 1e-6
    assert (y0, y1) == pytest.approx(view[1], abs=1e-6) or (y0 <= view[1][0] and y1 >= view[1][1])
    render_figure(win.canvas, str(tmp_path / "m.png"), "png", 1, mirror=True, mirror_numbers=False)
    assert not pi.getAxis("right").isVisible()


# ---------------------------------------------------------------- animation (GIF / MP4)
needs_pillow = pytest.mark.skipif(__import__("importlib").util.find_spec("PIL") is None, reason="Pillow missing")
needs_ffmpeg = pytest.mark.skipif(__import__("importlib").util.find_spec("imageio_ffmpeg") is None,
                                  reason="imageio-ffmpeg missing")


@needs_pillow
def test_gif_of_the_particles(win, qapp, tmp_path):
    from PIL import Image, ImageSequence
    from app.export import render_animation
    from app.export.figure import figure_size
    cv = win.canvas
    cv.set_view_mode("particles")
    path = str(tmp_path / "p.gif")
    calls = []
    render_animation(cv, path, "gif", 1, 20, 1, progress=lambda d, n: calls.append((d, n)))
    im = Image.open(path)
    frames = [f.convert("RGB") for f in ImageSequence.Iterator(im)]
    s = figure_size(cv)
    assert len(frames) == 20 and calls[-1] == (20, 20) and im.info["duration"] == 50
    assert abs(im.size[0] - s.width()) <= 1 and abs(im.size[1] - s.height()) <= 1
    a, b = np.asarray(frames[0], int), np.asarray(frames[-1], int)
    assert (np.abs(a - b).sum(axis=2) > 30).mean() > 0.01                    # the particles moved
    assert cv.particles._timer.isActive() and cv.static_cache and cv.particles.export_scale is None


@needs_ffmpeg
def test_mp4_of_the_pulses_at_2x(win, qapp, tmp_path):
    import imageio_ffmpeg
    from app.export import render_animation
    cv = win.canvas
    cv.set_view_mode("pulses")
    path = str(tmp_path / "p.mp4")
    render_animation(cv, path, "mp4", 1, 24, 2)
    reader = imageio_ffmpeg.read_frames(path)
    meta = next(reader)
    n = sum(1 for _ in reader)
    w, h = meta["size"]
    assert n == 24 and w % 2 == 0 and h % 2 == 0 and w > 1.9 * cv.plot.getPlotItem().sceneBoundingRect().width()
    assert meta["fps"] == pytest.approx(24)
    assert cv.pulses._timer.isActive() and cv.pulses.export_scale is None


@needs_pillow
def test_animation_export_cancel_removes_the_file(win, qapp, tmp_path):
    from app.export import Cancelled, render_animation
    cv = win.canvas
    cv.set_view_mode("particles")
    path = str(tmp_path / "c.gif")
    with pytest.raises(Cancelled):
        render_animation(cv, path, "gif", 3, 20, 1, progress=lambda d, n: d < 5)
    assert not os.path.exists(path) and cv.particles._timer.isActive()


def test_animation_export_needs_an_animation_and_the_package(win, monkeypatch, tmp_path):
    from app.export import animation, render_animation
    with pytest.raises(ValueError):
        render_animation(win.canvas, str(tmp_path / "s.gif"), "gif")              # Static view
    monkeypatch.setitem(animation.PACKAGES, "gif", ("no_such_module_xyz", "pillow"))
    win.canvas.set_view_mode("particles")
    with pytest.raises(RuntimeError, match="pip install pillow"):
        render_animation(win.canvas, str(tmp_path / "s.gif"), "gif")
    from app.export import ExportAnimationDialog
    dlg = ExportAnimationDialog(win.canvas, {"format": "gif"}, win)
    assert not dlg.ok.isEnabled() and "pip install pillow" in dlg.info.text()


@needs_pillow
def test_animation_export_from_the_menu_remembers_the_options(win, qapp, tmp_path):
    from app.export import ExportAnimationDialog

    def answer(dlg):
        dlg.fmt_buttons["gif"].setChecked(True)
        dlg.view.setCurrentIndex(dlg.view.findData("pulses"))
        dlg.duration.setCurrentIndex(dlg.duration.findData(1))
        dlg.fps.setCurrentIndex(dlg.fps.findData(20))
        return True
    win._run_dialog = answer
    target = str(tmp_path / "menu_anim")
    win._ask_export_path = lambda suggested, filt: target
    assert win.canvas.view_mode == "static"
    assert win.export_animation() and os.path.exists(target + ".gif")
    assert win.canvas.view_mode == "pulses"                                    # switched to it
    dlg = ExportAnimationDialog(win.canvas, win._export_settings("animation"), win)
    assert dlg.fmt() == "gif" and dlg.duration.currentData() == 1 and dlg.fps.currentData() == 20
    dlg.fmt_buttons["mp4"].setChecked(True)
    assert dlg.fps.currentData() == 30 and [dlg.fps.itemData(i) for i in range(dlg.fps.count())] == [24, 30, 60]
    assert [dlg.duration.itemData(i) for i in range(dlg.duration.count())] == [1, 2, 3, 5, 10]
    assert win.act_export_anim.shortcut().toString() == "Ctrl+Shift+E"
    assert [a.text() for a in win.canvas.bar.export_menu.actions()][1].startswith("Animation")


def test_legend_grows_with_a_2x_figure(win, qapp, tmp_path):
    from app.export import render_figure
    from PySide6.QtWidgets import QGraphicsItem
    cv = win.canvas
    cv.set_view_mode("particles")
    qapp.processEvents()
    render_figure(cv, str(tmp_path / "l.png"), "png", 2)
    assert cv.particles.legend.flags() & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations     # restored


def test_compute_now_then_export_without_waiting(qapp, tmp_path):
    """A plot alone (no main window): the scene, all layers drawn synchronously, a figure written —
    what the command line export will do."""
    from PySide6.QtGui import QImage
    from app.canvas import PlotCanvas
    from app.export import render_figure
    from app.theme import LIGHT
    from physics import Source, Uniform
    cv = PlotCanvas(LIGHT, [Uniform(), Source(m=6.0, x0=-1.0), Source(m=-6.0, x0=1.0)])
    cv.resize(900, 640)
    cv.show()
    qapp.processEvents()
    cv.set_view((-4.0, 4.0), (-3.0, 3.0))
    for key in ("speed", "bodies"):
        cv.set_layer(key, True)
    cv.compute_now()
    assert cv.last_result is not None and len(cv.last_result.lines) > 20
    assert len(cv.stagnation_points) == 2 and cv.fields.legend.isVisible() and cv.bodies.mask is not None
    render_figure(cv, str(tmp_path / "cli.png"), "png", 1)
    assert QImage(str(tmp_path / "cli.png")).width() > 500
    cv.shutdown()
    cv.close()


def test_png_of_the_animation_is_sharp_at_3x(win, qapp, tmp_path):
    """The particle picture of a 3× PNG is drawn at 3× (not the screen picture enlarged): its trail
    lines keep their sharp edges (few half-transparent edge pixels per line pixel)."""
    from PySide6.QtGui import QImage
    from app.export import render_figure
    cv = win.canvas
    cv.set_view_mode("particles")
    from PySide6.QtTest import QTest
    QTest.qWait(300)
    seen = []
    orig = cv.particles.set_export_scale
    cv.particles.set_export_scale = lambda k: (seen.append(k), orig(k))[1]
    render_figure(cv, str(tmp_path / "p3.png"), "png", 3)
    assert seen == [3.0, None] and cv.particles.export_scale is None and cv.particles._timer.isActive()
    assert QImage(str(tmp_path / "p3.png")).width() > 3 * 600
    cv.set_paused(True)                                       # paused particles: the screen picture
    seen.clear()
    render_figure(cv, str(tmp_path / "p3b.png"), "png", 3)
    assert seen == []
    cv.set_view_mode("pulses")                                # paused pulses: drawn again as they are
    t = cv.pulses.t
    orig2 = cv.pulses.set_export_scale
    cv.pulses.set_export_scale = lambda k: (seen.append(k), orig2(k))[1]
    render_figure(cv, str(tmp_path / "p3c.png"), "png", 3)
    assert seen == [3.0, None] and cv.pulses.t == t
