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


def test_wheel_at_a_limit_does_not_move_the_view(win, qapp):  # noqa: F811
    """His report of 1 Nov: turning the wheel on at a limit slid the view sideways (pyqtgraph cut the range round
    the middle of the asked one, which lies towards the mouse) and every notch started a new computation."""
    from physics.elements import Doublet, Uniform
    w = win
    w.model.reset([Uniform(), Doublet(mu=1.0)])
    w.canvas.fit_view()
    qapp.processEvents()
    for delta in (240, -240):
        wheel(qapp, w, 200, delta)                                    # to the limit (and well past it)
        before = w.canvas.view()
        changes = []
        w.canvas.view_changed.connect(lambda *a: changes.append(a))
        wheel(qapp, w, 40, delta)
        w.canvas.view_changed.disconnect()
        after = w.canvas.view()
        assert after == before                                        # not a hair: no new view, no computation
        assert changes == []
        wheel(qapp, w, 1, -delta)                                     # the other way it zooms as usual
        assert widths(w)[0] != pytest.approx(after[0][1] - after[0][0], rel=1e-3)


def test_zoom_reaches_the_limit_exactly_about_the_mouse(win, qapp):  # noqa: F811
    """A notch that would pass the limit is cut so the view ends exactly at the limit, zoomed about the mouse."""
    from physics.elements import Uniform
    w = win
    w.model.reset([Uniform()])
    w.canvas.fit_view()
    qapp.processEvents()
    vb = w.canvas.vb
    lo = w.canvas._limits[0]
    (x0, x1), (y0, y1) = w.canvas.view()
    centre = (x0 + 0.3 * (x1 - x0), y0 + 0.6 * (y1 - y0))
    vb.scaleBy((1e-9, 1e-9), centre)                                  # far past the limit in one step
    (a0, a1), (b0, b1) = w.canvas.view()
    assert min(a1 - a0, b1 - b0) == pytest.approx(lo, rel=1e-6)
    # the point under the mouse stayed where it was (same place in the view, as a fraction)
    assert (centre[0] - a0) / (a1 - a0) == pytest.approx(0.3, abs=0.02)
    assert (centre[1] - b0) / (b1 - b0) == pytest.approx(0.6, abs=0.02)


def test_far_views_find_stagnation_points_quickly():
    """Zoomed far out, the probes round the stagnation points were traced across a box 3× the view with their own
    small step: 18–66 s for one view of the lifting cylinder (his fans at full speed). Now a region at most
    PROBE_REGION_SCENES × the scene; the same points as in a normal view."""
    import time

    from physics.elements import Doublet, Uniform, Vortex
    from physics.stagnation import find_stagnation_points
    els = [Uniform(V=1.0), Doublet(mu=2 * np.pi), Vortex(Gamma=-6.0)]           # lifting cylinder, a = √(2π)
    near = find_stagnation_points(els, (-3, 3, -2, 2))
    t = time.perf_counter()
    far = find_stagnation_points(els, (-12000, 12000, -8000, 8000))
    assert time.perf_counter() - t < 8.0                                         # (was 18 s on this server)
    assert sorted((round(p.x, 6), round(p.y, 6), p.kind) for p in far) == \
        sorted((round(p.x, 6), round(p.y, 6), p.kind) for p in near)


def test_probe_region_only_for_views_far_larger_than_the_scene():
    from physics.elements import Doublet, Uniform
    from physics.stagnation import PROBE_REGION_SCENES, _probe_region
    els = [Uniform(), Doublet(mu=1.0, x0=2.0, y0=1.0)]
    normal = (-5.0, 5.0, -3.0, 3.0)
    assert _probe_region(els, [], normal) == normal
    far = _probe_region(els, [], (-1e5, 1e5, -7e4, 7e4))
    assert far[1] - far[0] < 1e5 and far[0] < 2.0 < far[1] and far[2] < 1.0 < far[3]
    assert far[1] - far[0] <= PROBE_REGION_SCENES * 20.0


def test_staged_tracing_gives_the_same_origins_zoomed_in():
    """Zoomed far in, lines are traced in growing stages (each 8× the box and the step) instead of across the
    whole far-field box with the view's tiny step: the same answers, far faster."""
    import time

    from physics import origin
    from physics.elements import Doublet, Source, Uniform, Vortex
    from physics.origin import trace_ends
    rng = np.random.default_rng(3)
    unknown = total = 0
    for els in ([Uniform(V=1.0), Doublet(mu=2 * np.pi), Vortex(Gamma=-6.0)],
                [Uniform(V=1.0), Source(m=3.0, x0=-1.0), Source(m=-3.0, x0=1.0)],
                [Uniform(V=1.0, alpha=10.0), Source(m=2.0)]):
        for c in (1.02 + 0.1j, -1.3 + 0.05j, 0.2 + 1.05j, 1.6 + 0.0j):
            w = 2e-3
            region = (c.real - w, c.real + w, c.imag - w, c.imag + w)
            seeds = c + w * (rng.random(12) - 0.5 + 1j * (rng.random(12) - 0.5))
            got = {}
            for name, growth in (("single", 1e300), ("staged", 8.0)):
                old = origin.STAGE_GROWTH
                origin.STAGE_GROWTH = growth
                try:
                    t = time.perf_counter()
                    got[name] = trace_ends(els, seeds, region, w, -1.0)
                    got[name + "_s"] = time.perf_counter() - t
                finally:
                    origin.STAGE_GROWTH = old
            # where both know the answer it is the same; a line passing a stagnation point closer than the
            # coarser stages resolve may end there ("stopped" = unknown: it does not vote in body_map)
            a, b = got["single"][0], got["staged"][0]
            known = (a != origin.STOPPED) & (b != origin.STOPPED)
            assert np.array_equal(a[known], b[known])
            assert np.array_equal(got["single"][1][known], got["staged"][1][known])
            unknown += int(np.count_nonzero(b == origin.STOPPED) - np.count_nonzero(a == origin.STOPPED))
            total += a.size
    assert unknown <= 0.05 * total


def test_body_barriers_sample_only_inside_the_grid():
    """Lines of the whole scene seen far zoomed in: segments thousands of cells long, sampled cell by cell —
    11 million samples froze the window. Only the part inside the grid is sampled now; the same cells."""
    import time

    from physics.bodies import draw_barriers

    def reference(lines, box, shape):            # the old way: every sample of every segment
        x0, x1, y0, y1 = box
        rows, cols = shape
        out = np.zeros(shape, bool)
        for xy in lines:
            px, py = (xy[:, 0] - x0) * cols / (x1 - x0), (xy[:, 1] - y0) * rows / (y1 - y0)
            seg = np.hypot(np.diff(px), np.diff(py))
            n = np.where(np.isfinite(seg), np.ceil(seg / 0.35), 0).astype(np.int64)
            t = np.concatenate([np.arange(k) / k for k in n if k > 0])
            idx = np.repeat(np.arange(seg.size), n)
            qx = np.concatenate([px[idx] + t * (px[idx + 1] - px[idx]), px[-1:]])
            qy = np.concatenate([py[idx] + t * (py[idx + 1] - py[idx]), py[-1:]])
            ok = np.isfinite(qx) & np.isfinite(qy)
            i, j = np.floor(qx[ok]).astype(np.int64), np.floor(qy[ok]).astype(np.int64)
            inside = (i >= 0) & (i < cols) & (j >= 0) & (j < rows)
            out[j[inside], i[inside]] = True
        return out

    rng = np.random.default_rng(5)
    for _ in range(300):
        shape = (int(rng.integers(5, 80)), int(rng.integers(5, 100)))
        lines = [rng.normal(0.5, 10 ** rng.uniform(-1, 1.3), size=(int(rng.integers(2, 25)), 2)) for _ in range(3)]
        assert np.array_equal(draw_barriers(lines, (-1.0, 2.0, -0.5, 1.5), shape),
                              reference(lines, (-1.0, 2.0, -0.5, 1.5), shape))
    huge = [np.array([[-1e4, -6.9e3 + 0.3], [1e4, 7e3], [0.5, 0.35], [3e4, -2e4]])]
    t = time.perf_counter()
    cells = draw_barriers(huge, (0, 1, 0, 0.7), (280, 400))
    assert time.perf_counter() - t < 0.5                                         # (was 8.7 s)
    assert cells.sum() > 100


def test_fast_zoom_gives_up_the_job_of_a_level_left_behind(win, qapp):  # noqa: F811
    """While a job computes the lines of one spacing level, a view that needs another level cancels it (the newest
    view is computed next instead of after the old one)."""
    w = win
    layer = w.canvas.streamlines
    layer._job_level, layer._wanted_level, layer.busy = 3, None, True
    try:
        (x0, x1), (y0, y1) = w.canvas.view()
        layer.request()
        assert layer.pending and layer._wanted_level == layer.cache._choose_level(w.canvas.view(), 3)
    finally:
        layer.busy, layer.pending, layer._job_level = False, False, None


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
    from app_info import APP_NAME, APP_SUBTITLE
    assert APP_NAME == "Flowy"
    assert win.windowTitle().startswith(APP_NAME)
    assert win.header.plank.title.text() == APP_NAME
    assert win.header.plank.subtitle.text() == APP_SUBTITLE.upper()


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
