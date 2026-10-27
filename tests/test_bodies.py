"""'Solid bodies' layer: the inside of cylinders and Rankine bodies (physics/bodies.py) filled on the
plot, and no particles / pulses inside them."""
import numpy as np
import pytest

from physics import Doublet, Source, Uniform, Vortex, kernel
from physics.bodies import _label, body_mask, draw_barriers, find_bodies
from physics.stagnation import BODY, FAR, LOOP, find_stagnation_points, trace_origin
from physics.streamlines import StreamlineCache


def _dividing(els, box):
    return StreamlineCache(tuple(els), 1.0).update(((box[0], box[1]), (box[2], box[3])), force=True).dividing


def _mask(els, box, rows=300):
    res = StreamlineCache(tuple(els), 1.0).update(((box[0], box[1]), (box[2], box[3])), force=True)
    cols = int(rows * (box[1] - box[0]) / (box[3] - box[2]))
    return body_mask(els, box, (rows, cols), res.dividing)


def test_cylinder_and_rankine_oval_areas():
    box = (-3.2, 3.2, -2.0, 2.0)
    m = _mask([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)], box)
    assert m.mean() * 6.4 * 4.0 == pytest.approx(np.pi, rel=0.03)                 # R = 1
    rows, cols = m.shape
    assert m[rows // 2, cols // 2] and not m[rows // 2, 2] and not m[2, cols // 2]
    # Rankine oval: half-length L = a √(1 + m/(π a V)) = √3, crossing the x axis there
    m = _mask([Uniform(), Source(m=2 * np.pi, x0=-1.0), Source(m=-2 * np.pi, x0=1.0)], box)
    row = m[m.shape[0] // 2]
    x = -3.2 + (np.arange(row.size) + 0.5) * 6.4 / row.size
    assert x[row].min() == pytest.approx(-np.sqrt(3), abs=0.04) and x[row].max() == pytest.approx(np.sqrt(3), abs=0.04)


def test_half_body_is_open_to_the_edge_of_the_view():
    box = (-3.0, 5.0, -2.5, 2.5)
    m = _mask([Uniform(), Source(m=2 * np.pi)], box)
    rows, cols = m.shape
    assert m[rows // 2, -1] and m[rows // 2, cols // 2]                        # right edge: still body
    x = -3.0 + (np.arange(cols) + 0.5) * 8.0 / cols
    assert x[m[rows // 2]].min() == pytest.approx(-1.0, abs=0.04)              # nose at x = −m / (2πV)
    # surface: y = m (π − θ) / (2π V) = π − θ, x = y / tan θ (half-width → π far downstream)
    c = int(np.argmin(np.abs(x - 2.0)))
    lo, hi = 0.05, 1.5                                                         # (π − θ)/tan θ = x
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if (np.pi - mid) / np.tan(mid) > x[c] else (lo, mid)
    theta = 0.5 * (lo + hi)
    y = -2.5 + (np.arange(rows) + 0.5) * 5.0 / rows
    assert y[m[:, c]].max() == pytest.approx(np.pi - theta, abs=0.04)


def test_no_bodies_without_a_free_stream_or_around_a_free_vortex():
    assert _mask([Source(m=2.0)], (-3, 3, -2, 2)) is None
    m = _mask([Uniform(), Vortex(Gamma=-6.0)], (-3, 3, -2, 2))           # closed loops: real flow
    assert m is None or not m.any()


def test_where_fluid_comes_from():
    box = (-3.0, 3.0, -2.0, 2.0)
    cyl = [Uniform(), Doublet(mu=1.0)]
    assert trace_origin(cyl, np.array([-2.5 + 1.5j, 0.3 + 0.3j]), box).tolist() == [FAR, BODY]
    vortex = [Uniform(), Vortex(Gamma=-6.0)]            # closed loops round a free vortex: real flow
    assert trace_origin(vortex, np.array([0.2j, -2.5 + 1.5j]), box).tolist() == [LOOP, FAR]
    (p,) = find_stagnation_points(vortex, box)
    assert p.kind == "flow"                              # not "on the body surface"


def test_fast_spinning_cylinder_is_one_body_with_its_ring():
    """Γ > 4πV∞a: the ring of fluid turning with the cylinder belongs to the body (closed loops round
    the doublet); the one stagnation point lies on its border."""
    els = [Uniform(), Doublet(mu=1.0), Vortex(Gamma=-16.0)]
    box = (-3.2, 3.2, -3.0, 3.0)
    (p,) = find_stagnation_points(els, box)
    assert p.kind == "body"
    (body,) = find_bodies(els, _dividing(els, box), box)
    ring = body.surface[0][:, 0] + 1j * body.surface[0][:, 1]
    assert body.closed and np.min(np.abs(ring - p.z)) < 0.02 and np.max(np.abs(ring)) > 1.5


def test_body_surfaces_are_closed_counter_clockwise_rings():
    box = (-3.2, 3.2, -2.0, 2.0)
    els = [Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)]
    (body,) = find_bodies(els, _dividing(els, box), box)
    (ring,) = body.surface
    z = ring[:, 0] + 1j * ring[:, 1]
    assert body.closed and np.allclose(np.abs(z), 1.0, atol=2e-3)
    assert body.length == pytest.approx(2 * np.pi, rel=0.01)
    area = 0.5 * np.sum(z.real * np.roll(z.imag, -1) - np.roll(z.real, -1) * z.imag)
    assert area == pytest.approx(np.pi, rel=0.01)                              # > 0: counter-clockwise
    assert body.singular and all(abs(s) < 1e-12 for s in body.singular)
    # two cylinders: two bodies
    els = [Uniform(), Doublet(mu=0.5, x0=-1.5), Doublet(mu=0.5, x0=1.5)]
    box = (-4.0, 4.0, -2.5, 2.5)
    bodies = find_bodies(els, _dividing(els, box), box)
    assert len(bodies) == 2 and all(b.closed for b in bodies)
    assert sorted(b.singular[0].real for b in bodies) == [-1.5, 1.5]


def test_open_half_body_surface_ends_at_the_region_border():
    box = (-3.0, 5.0, -2.5, 2.5)
    els = [Uniform(), Source(m=2 * np.pi)]
    (body,) = find_bodies(els, _dividing(els, box), box)
    assert not body.closed
    z = np.concatenate([s[:, 0] + 1j * s[:, 1] for s in body.surface])
    assert z.real.min() == pytest.approx(-1.0, abs=0.01)                         # the nose
    assert z[0].imag > 0 > z[-1].imag                                            # top -> nose -> bottom
    assert find_bodies([Uniform(), Vortex(Gamma=-6.0)], _dividing([Uniform(), Vortex(Gamma=-6.0)], box), box) == []


def test_barrier_lines_separate_regions():
    box = (0.0, 1.0, 0.0, 1.0)
    diag = [np.array([[0.0, 0.0], [1.0, 1.0]]), np.array([[0.0, 0.77], [1.0, 0.13]])]
    b = draw_barriers(diag, box, (97, 101))
    labels, n = _label(~b)
    assert n == 4                                      # two crossing lines: four regions, no leaks


@pytest.mark.skipif(not kernel.HAVE_NUMBA, reason="Numba not installed")
def test_compiled_labels_match_python(monkeypatch):
    rng = np.random.default_rng(3)
    free = rng.random((60, 80)) > 0.45
    a, na = kernel.label_regions(free)
    monkeypatch.setattr(kernel, "HAVE_NUMBA", False)
    b, nb = _label(free)
    assert na == nb
    for k in range(1, na + 1):                         # the same regions (numbered alike: same scan order)
        assert np.array_equal(a == k, b == k)


# ---------------------------------------------------------------- the plot
@pytest.fixture
def win(qapp):
    from app.main_window import MainWindow
    w = MainWindow()
    w._ask_save_changes = lambda: "discard"
    w.resize(1300, 820)
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def _load(w, qapp, els, view):
    w.load_scene(els, view)
    w.canvas.wait_idle()
    from PySide6.QtTest import QTest
    for _ in range(100):
        QTest.qWait(20)
        if not w.canvas.streamlines.busy and w.canvas.last_result is not None:
            break
    qapp.processEvents()


def test_solid_bodies_switch(win, qapp):
    cv, sp = win.canvas, win.settings_panel
    _load(win, qapp, [Uniform(), Doublet(mu=1.0)], ((-3.0, 3.0), (-2.0, 2.0)))
    assert not cv.layers["bodies"] and cv.bodies.mask is None and cv.bodies.fill.path().isEmpty()
    sp.layer_boxes["bodies"].setChecked(True)
    assert cv.layers["bodies"] and cv.bodies.mask is not None
    assert not cv.bodies.fill.path().isEmpty() and cv.bodies.fill.isVisible()
    assert cv.bodies.contains(np.array([0.3 + 0.2j, 2.5 + 1.5j])).tolist() == [True, False]
    edge = cv.bodies.edge.getData()
    r = np.hypot(edge[0], edge[1])
    r = r[np.isfinite(r)]
    assert r.size > 50 and np.allclose(r, 1.0, atol=0.02)                    # the surface only
    win.layer_actions["bodies"].setChecked(False)                              # View → Layers
    assert cv.bodies.mask is None and not cv.bodies.fill.isVisible()


def test_no_particles_or_pulses_inside_a_body(win, qapp):
    cv, sp = win.canvas, win.settings_panel
    _load(win, qapp, [Uniform(), Doublet(mu=1.0)], ((-3.0, 3.0), (-2.0, 2.0)))
    cv.set_view_mode("particles")
    from PySide6.QtTest import QTest
    QTest.qWait(200)
    inside = np.abs(cv.particles.particles.pos) < 0.95
    assert inside.sum() > 10                                                   # without the layer
    sp.layer_boxes["bodies"].setChecked(True)
    for _ in range(30):
        QTest.qWait(17)
        assert (np.abs(cv.particles.particles.pos) < 0.97).sum() == 0
    cv.set_view_mode("pulses")
    QTest.qWait(200)
    ax, ay, bx, by, *_ = cv.pulses._px
    img = cv.pulses.trail.image
    (x0, x1), (y0, y1) = cv.view()
    mx = x0 + 0.5 * (ax + bx) / img.width() * (x1 - x0)
    my = y0 + 0.5 * (ay + by) / img.height() * (y1 - y0)
    assert (np.hypot(mx, my) < 0.97).sum() == 0
    sp.layer_boxes["bodies"].setChecked(False)
    QTest.qWait(100)
    ax, ay, bx, by, *_ = cv.pulses._px
    mx = x0 + 0.5 * (ax + bx) / img.width() * (x1 - x0)
    my = y0 + 0.5 * (ay + by) / img.height() * (y1 - y0)
    assert (np.hypot(mx, my) < 0.9).sum() > 50                                 # back inside


def test_bodies_follow_zoom_and_a_moved_element(win, qapp):
    cv, sp = win.canvas, win.settings_panel
    sp.layer_boxes["bodies"].setChecked(True)
    _load(win, qapp, [Uniform(), Doublet(mu=1.0)], ((-3.0, 3.0), (-2.0, 2.0)))
    cv.set_view((-1.5, 1.5), (-1.0, 1.0))
    from PySide6.QtTest import QTest
    QTest.qWait(300)
    cv.wait_idle()
    QTest.qWait(200)
    assert cv.bodies.mask_box == (-1.5, 1.5, -1.0, 1.0) or cv.bodies.mask_box[:2] == cv.view()[0]
    assert cv.bodies.mask.mean() > 0.4                                         # the zoomed cylinder
    _load(win, qapp, [Uniform(), Doublet(mu=1.0, x0=1.0)], ((-3.0, 3.0), (-2.0, 2.0)))
    assert cv.bodies.contains(np.array([1.5 + 0j, -0.5 + 0j])).tolist() == [True, False]
