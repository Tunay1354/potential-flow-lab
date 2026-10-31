"""Zoom (his report of 31 Oct): limits 10 000× in / out of the Fit size for the user's wheel / drag, views set by
the program never cut; lines kept when zoomed far out (each level its own stagnation-speed threshold); lines in
a local coordinate system (the graphics card's painter thickened them far in); the View range boxes for any
size; the beaver's zoom jokes; the name Flowy."""
import numpy as np
import pytest

from tests.test_beaver import DT, win  # noqa: F401  (the window fixture with the beaver stepped by hand)


def wheel(qapp, w, n, delta):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    vp = w.canvas.plot.viewport()
    c = QPointF(vp.width() / 2 + 60, vp.height() / 2 - 30)
    for _ in range(n):
        ev = QWheelEvent(c, QPointF(vp.mapToGlobal(c.toPoint())), QPoint(0, 0), QPoint(0, delta), Qt.NoButton,
                         Qt.NoModifier, Qt.NoScrollPhase, False)
        qapp.sendEvent(vp, ev)
        qapp.processEvents()


def widths(w):
    (x0, x1), (y0, y1) = w.canvas.view()
    return x1 - x0, y1 - y0


def test_wheel_stops_at_the_zoom_limits_and_says_so(win, qapp):  # noqa: F811
    from app.canvas.canvas import ZOOM_RANGE
    from physics.elements import Doublet, Uniform
    w = win
    w.model.reset([Uniform(), Doublet(mu=1.0)])
    w.canvas.fit_view()
    qapp.processEvents()
    (fx0, fx1), (fy0, fy1) = w.canvas.fit_range()
    size = max(fx1 - fx0, fy1 - fy0)
    first = widths(w)
    aspect = first[0] / first[1]
    hits, flashes = [], []
    w.canvas.zoom_limit.connect(hits.append)
    w.flash = flashes.append
    wheel(qapp, w, 150, 240)
    wx, wy = widths(w)
    assert min(wx, wy) == pytest.approx(size / ZOOM_RANGE, rel=0.05)          # stopped, not beyond
    assert wx / wy == pytest.approx(aspect, rel=0.02)          # (aspect lock; axis labels may widen)
    assert hits == ["in"]                                                      # once per arrival
    assert any("Zoom limit" in f for f in flashes)
    wheel(qapp, w, 300, -240)
    wx, wy = widths(w)
    assert max(wx, wy) == pytest.approx(size * ZOOM_RANGE, rel=0.05)
    assert hits == ["in", "out"]
    w.canvas.fit_view()
    qapp.processEvents()
    assert widths(w)[0] == pytest.approx(first[0], rel=0.02)


def test_views_set_by_the_program_are_never_cut(win, qapp):  # noqa: F811
    from physics.elements import Uniform
    w = win
    w.model.reset([Uniform()])
    for half in (1e7, 1e-6):
        w.canvas.set_view((-half, half), (-half, half))
        qapp.processEvents()
        (x0, x1), (y0, y1) = w.canvas.view()
        assert min(x1 - x0, y1 - y0) == pytest.approx(2 * half, rel=1e-6)
    # … and the limits follow the scene: a scene ten times larger may be seen ten times wider
    lo1, hi1 = w.canvas.zoom_limits()
    from physics.elements import Source
    w.model.reset([Uniform(), Source(m=1.0, x0=-40.0), Source(m=-1.0, x0=40.0)])
    w.canvas.fit_view()
    qapp.processEvents()
    lo2, hi2 = w.canvas.zoom_limits()
    assert hi2 > hi1 * 5


def test_far_zoom_out_keeps_every_streamline():
    """The cache used the 'too slow = stagnation point' speed of the first view at every level: zoomed out
    100 000×, every line ended at once (the far-away flow is slower than that)."""
    from physics.elements import Source, Vortex
    from physics.streamlines.cache import StreamlineCache
    els = [Vortex(Gamma=2.0), Source(m=1.0, x0=0.5)]
    cache = StreamlineCache(els)
    for half in (4.0, 4e5, 4e-4):
        res = cache.update(((-half, half), (-half, half)), force=True, margin=False)
        pts = np.concatenate(res.lines)
        inside = pts[(np.abs(pts[:, 0]) <= half) & (np.abs(pts[:, 1]) <= half)]
        span = inside[:, 0].max() - inside[:, 0].min()
        assert span > 1.8 * half, half                                     # lines across the whole view


def test_curves_keep_a_local_coordinate_system(win, qapp):  # noqa: F811
    from app.canvas.scaled_curve import ScaledCurve
    w = win
    w.canvas.set_view((1.0 - 1e-4, 1.0 + 1e-4), (-1e-4, 1e-4))
    qapp.processEvents()
    c = ScaledCurve()
    w.canvas.plot.addItem(c)
    x = np.linspace(1.0 - 1e-4, 1.0 + 1e-4, 11)
    c.setData(x, np.zeros_like(x))
    xl, yl = c.getData()
    assert np.allclose(c.xy()[0], x) and np.max(np.abs(xl)) < 2000               # data back; local ≈ px
    t = c.transform()
    assert t.m11() == pytest.approx(2e-4 * 1.8 / 1000, rel=0.5) and t.dx() == pytest.approx(1.0)
    br = c.mapRectToView(c.boundingRect())
    assert br.left() <= x[0] and br.right() >= x[-1]
    w.canvas.set_view((-4.0, 4.0), (-3.0, 3.0))                                  # zoomed out 40 000×: renewed
    qapp.processEvents()
    assert c.transform().m11() > 1e-3
    assert np.allclose(c.xy()[0], x)
    # the streamlines use it
    from app.canvas.scaled_curve import ScaledCurve as SC
    assert all(isinstance(it, SC) for it in w.canvas.streamlines.line_items)


def test_paper_grid_paints(win, qapp):  # noqa: F811
    from app.canvas.grid_item import PaperGridItem
    assert isinstance(win.canvas._grid, PaperGridItem)
    for half in (4.0, 1e-4, 5e4):
        win.canvas.set_view((-half, half), (-half, half))
        qapp.processEvents()
        img = win.canvas.plot.grab().toImage()
        assert not img.isNull()


def test_view_range_boxes_show_any_size(qapp):
    from app.panels import ViewSpinBox
    b = ViewSpinBox(-4.0)
    assert b.text() == "-4.00"
    b.set_resolution(2e-4)                                     # zoomed in: the two ends must differ
    b.setValue(1.0001)
    assert b.text() == "1.0001000"
    b.setValue(1.0 - 1e-4)
    assert b.text() == "0.9999000"
    b.set_resolution(1e-6)
    b.setValue(3.4e-7)
    assert "e-07" in b.text()
    b.set_resolution(4e7)
    b.setValue(-1.8e7)
    assert b.text() == "-1.8e+07" and b.value() == -1.8e7
    from PySide6.QtGui import QValidator
    assert b.validate("1.5e-4", 0)[0] == QValidator.Acceptable
    assert b.validate("1.5e", 0)[0] == QValidator.Intermediate
    assert b.validate("abc", 0)[0] == QValidator.Invalid
    assert b.valueFromText("2,5") == 2.5
    assert b.sizeHint().width() < 140                           # (the panel stays narrow)


def test_typed_tiny_view_reaches_the_plot(win, qapp):  # noqa: F811
    sp = win.settings_panel
    for box, val in ((sp.xmin, 1.0 - 1e-4), (sp.xmax, 1.0 + 1e-4), (sp.ymin, -1e-4), (sp.ymax, 1e-4)):
        box.setValue(val)
    sp._view_typed()
    qapp.processEvents()
    (x0, x1), (y0, y1) = win.canvas.view()
    assert y1 - y0 == pytest.approx(2e-4, rel=1e-3) or x1 - x0 == pytest.approx(2e-4, rel=1e-3)
    assert sp.xmin.text() != sp.xmax.text()


def test_beaver_jokes_at_the_zoom_limits(win, qapp, monkeypatch):  # noqa: F811
    from app.beaver.lines import LINES, PRIORITY, REMARK_CHANCE
    for key in ("zoom_limit_in", "zoom_limit_out"):
        assert len(LINES[key]) >= 8 and 0 < REMARK_CHANCE[key] < 1 and PRIORITY[key] == 0
    b = win.beaver
    from tests.test_beaver import run
    run(qapp, win, 0.5)
    b.bubble.clear()
    b.last_remark = -1e9
    monkeypatch.setattr(b.lines.rng, "random", lambda: 0.0)
    win._zoom_limit("in")
    assert b.bubble.text in LINES["zoom_limit_in"]
    b.bubble.clear()
    b.last_remark = -1e9
    win._zoom_limit("out")
    assert b.bubble.text in LINES["zoom_limit_out"]
    b.bubble.clear()
    b.last_remark = -1e9
    monkeypatch.setattr(b.lines.rng, "random", lambda: 0.99)      # (a chance not taken: quiet)
    win._zoom_limit("in")
    assert not b.bubble.active


def test_the_program_is_called_flowy(win):  # noqa: F811
    from app_info import APP_ID, APP_NAME
    assert APP_NAME == "Flowy" and APP_ID == "Potential Flow Lab"         # (settings kept under the old name)
    assert win.windowTitle().startswith("Flowy")
    assert win.header.plank.title.text() == "Flowy"
    assert win.header.plank.subtitle.text() == "POTENTIAL FLOW LAB"


GL_ZOOM_SCRIPT = r'''
import os, sys, time
sys.path.insert(0, %(root)r); os.chdir(%(root)r)
from PySide6.QtCore import QSettings, QStandardPaths
QStandardPaths.setTestModeEnabled(True)
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, %(out)r)
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
import numpy as np
app = QApplication([])
from app.startup import setup_application
setup_application(app); QSettings().setValue("beaver/tour_offered", True); QSettings().setValue("beaver/enabled", False)
from app import gpu
gpu.support = lambda p: (True, "test")
from app.main_window import MainWindow
from app.scene import starter_scene
MainWindow.START_SCENE = ("Lifting (rotating) cylinder", starter_scene)
w = MainWindow(); w._ask_save_changes = lambda: "discard"; w._notify_user = lambda *a: print("NOTE", a)
w.resize(1400, 800); w.move(0, 0); w.show()
def pump(s):
    t = time.perf_counter()
    while time.perf_counter() - t < s:
        app.processEvents(); time.sleep(0.005)
def plot_pixels():
    pump(0.6)
    vp = w.canvas.plot.viewport()
    r = vp.rect(); p = vp.mapToGlobal(r.topLeft())
    img = app.primaryScreen().grabWindow(0, p.x(), p.y(), r.width(), r.height()).toImage()
    img = img.convertToFormat(QImage.Format_RGB888)
    a = np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.bytesPerLine())[:, :img.width() * 3]
    return a.reshape(img.height(), img.width(), 3).astype(int)
def differ(a, b):
    return 100.0 * float((np.abs(a - b).max(axis=2) > 60).mean()) if a.shape == b.shape else 100.0
pump(2.0)
out = []
for half in (1e-3, 1e-5):
    w.canvas.set_view((2.0 - half, 2.0 + half), (1.0 - half, 1.0 + half))
    w.canvas.wait_idle(20000); pump(0.5)
    raster = plot_pixels()
    w.set_gpu(True, user=False); pump(1.5)
    on = plot_pixels()
    w.set_gpu(False, user=False); pump(0.8)
    out.append(round(differ(raster, on), 3))
print("RESULT", *out)
w.model.mark_clean(); w.close()
'''


def test_opengl_lines_stay_thin_far_zoomed_in(tmp_path):
    """His report of 31 Oct: zoomed far in with the graphics card, the lines grew thick (Qt's OpenGL painter
    limits the magnification of an item's own coordinates). The picture with the card = the normal one."""
    import os
    import subprocess
    import sys
    from tests.test_gpu import ROOT, _xvfb_display
    if _xvfb_display() is None:
        pytest.skip("needs an X server with OpenGL (Xvfb + Mesa)")
    script = tmp_path / "glzoom.py"
    script.write_text(GL_ZOOM_SCRIPT % {"root": ROOT, "out": str(tmp_path)})
    env = dict(os.environ, DISPLAY=_xvfb_display(), QT_QPA_PLATFORM="xcb", PFL_GPU_ALLOW_SOFTWARE="1")
    out = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True, timeout=300)
    assert "RESULT" in out.stdout, out.stdout[-2000:] + out.stderr[-2000:]
    line = next(ln for ln in out.stdout.splitlines() if ln.startswith("RESULT"))
    for d in line.split()[1:]:
        assert float(d) < 3.0, line
