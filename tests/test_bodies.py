"""'Solid bodies' layer: the inside of cylinders and Rankine bodies (physics/bodies.py) filled on the
plot, and no particles / pulses inside them."""
import numpy as np
import pytest

from physics import Doublet, Source, Uniform, Vortex, kernel
from physics.bodies import _label, body_map, body_mask, draw_barriers, find_bodies
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


def test_doublet_across_the_flow_is_no_body_and_gets_a_warning():
    """α = 30°, δ = 0°: part of the free stream goes through the doublet (in, and out again downstream)
    — the drawn lines are right (stagnation points = roots of w), but there is no solid body; δ = α
    gives the cylinder again. A tilted source–sink pair alike; a half-body (net outflow) stays."""
    from physics.validation import check_scene
    box = (-4.0, 4.0, -3.0, 3.0)
    tilted = [Uniform(alpha=30.0), Doublet(mu=1.0), Vortex(Gamma=-2.0)]
    m = body_map(tilted, box, (300, 400), _dividing(tilted, box))
    assert m is None or not m.mask.any()
    (w,) = [s for s in check_scene(tilted) if s.severity == "warning"]
    assert w.index == 1 and "δ = 30°" in w.message
    aligned = [Uniform(alpha=30.0), Doublet(mu=1.0, delta=30.0), Vortex(Gamma=-2.0)]
    m = body_map(aligned, box, (300, 400), _dividing(aligned, box))
    assert m.mask.mean() * 48.0 == pytest.approx(np.pi, rel=0.03)
    assert not [s for s in check_scene(aligned) if s.severity == "warning"]
    pair = [Uniform(alpha=30.0), Source(m=6.0, x0=-1.0), Source(m=-6.0, x0=1.0)]
    m = body_map(pair, box, (300, 400), _dividing(pair, box))
    assert m is None or not m.mask.any()
    half = [Uniform(), Source(m=6.0), Source(m=-2.0, x0=1.0)]
    assert body_map(half, box, (300, 400), _dividing(half, box)).mask.any()


@pytest.mark.parametrize("view", [((-0.8, 0.8), (-0.6, 0.6)), ((-0.1, 0.1), (0.9, 1.05)),
                                  ((-1.05, -0.9), (-0.08, 0.08)), ((0.69, 0.73), (0.69, 0.73))])
def test_body_is_right_when_zoomed_into_it(view):
    """Zoomed into (part of) the cylinder, the stagnation points of its surface are far outside the
    view: the surface comes from the scene-wide search, traced again at the view's scale; where no line
    tells anything (next to a stagnation point), the coarse scene map does."""
    from physics.bodies import scene_map
    els = [Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)]
    c = StreamlineCache(tuple(els))
    c.update(((-4.0, 4.0), (-3.0, 3.0)))
    res = c.update(view, force=True)
    (x0, x1), (y0, y1) = view
    m = body_map(els, (x0, x1, y0, y1), (240, 320), res.dividing, hint=scene_map(els, res))
    gx, gy = np.meshgrid(np.linspace(x0, x1, 9)[1:-1], np.linspace(y0, y1, 9)[1:-1])
    z = (gx + 1j * gy).ravel()
    far = np.abs(np.abs(z) - 1.0) > 0.01 * (x1 - x0) + 0.002
    assert np.array_equal(m.contains(z)[far], (np.abs(z) < 1.0)[far])


# a lifting-cylinder scene with the doublet and the vortex moved apart (user's screenshot, 27 Oct)
OFF_CENTER = [Uniform(), Doublet(mu=1.0, x0=0.3672, y0=-0.268), Vortex(Gamma=-2.0, x0=-0.7522, y0=0.113)]


@pytest.mark.parametrize("els, opened", [
    ([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)], set()),                    # lifting cylinder
    ([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-15.0)], set()),                   # spinning fast
    (OFF_CENTER, {1}),                                                            # the vortex turns the flow
    ([Uniform(alpha=30.0), Doublet(mu=1.0)], {1}),                                # δ ≠ α
    ([Uniform(), Source(m=2.0, x0=-1), Source(m=-2.0, x0=1)], set()),             # Rankine oval
    ([Uniform(), Source(m=2.0, x0=-1, y0=-0.5), Source(m=-2.0, x0=1, y0=0.5)], {1, 2}),   # pair across
    ([Uniform(), Source(m=2.0, x0=-1), Source(m=-1.0, x0=1)], set()),             # more out than in
    ([Uniform(), Source(m=-2.0)], {1}),                                           # a sink swallows the stream
])
def test_elements_the_free_stream_passes_through(els, opened):
    from physics.stagnation import open_elements
    assert set(open_elements(els)) == opened


@pytest.mark.parametrize("view", [((-4.0, 4.0), (-3.0, 3.0)), ((-1.83, 1.72), (-1.02, 0.81)),
                                  ((-1.25, 1.39), (-0.86, 0.50)), ((0.0, 0.7), (-0.6, -0.1))])
def test_off_center_vortex_makes_no_body_at_any_zoom(view):
    """Zoomed in, this scene was filled (most of the view's region was closed loops round the doublet)
    and zoomed out it was not: free-stream fluid goes through the doublet, so no zoom shows a body."""
    c = StreamlineCache(tuple(OFF_CENTER))
    c.update(((-4.0, 4.0), (-3.0, 3.0)))
    res = c.update(view, force=True)
    (x0, x1), (y0, y1) = view
    m = body_map(OFF_CENTER, (x0, x1, y0, y1), (200, 300), res.dividing)
    assert m is None or not m.mask.any()


def test_off_center_vortex_warning_names_the_flow_at_the_doublet():
    from physics.validation import check_scene
    (w,) = [s for s in check_scene(OFF_CENTER) if s.severity == "warning"]
    assert w.index == 1 and "-15.59°" in w.message and "vortex at the doublet's center" in w.message
    assert "set δ = -15.59°" in w.message
    ground = [__import__("physics").SymmetryWall(xw=0.0, yw=0.0, theta_w=0.0, side=0), Uniform(),
              Doublet(mu=1.0, x0=0.0, y0=1.5)]                       # the wall's image keeps it along
    assert not [s for s in check_scene(ground) if s.severity == "warning"]


def test_source_in_a_corner_flow_is_a_half_body():
    """A sector flow is a free stream too: the source's fluid is a half-body, as in a uniform flow."""
    from physics import SectorFlow
    els = [SectorFlow(V=1.0, x0=0.0, y0=0.0, theta1=0.0, theta2=90.0), Source(m=2.0, x0=1.0, y0=1.0)]
    box = (-0.6, 3.4, -0.6, 3.0)
    m = body_map(els, box, (240, 270), _dividing(els, box))
    z = np.array([1.05 + 1.0j, 3.0 + 0.3j, 2.0 + 2.0j, 0.3 + 1.0j, 3.0 + 0.05j])
    assert m.contains(z).tolist() == [True, True, False, False, False]


def test_zoom_into_a_source_in_a_wall_corner_does_not_crash():
    """A traced line stepping exactly onto the corner of two walls (velocity 0) raised
    ZeroDivisionError in the compiled tracer: no stagnation points / streamlines for that view."""
    from physics import SymmetryWall
    from physics.stagnation import flow_features
    els = [SymmetryWall(xw=0.0, yw=0.0, theta_w=0.0, side=0), SymmetryWall(xw=0.0, yw=0.0, theta_w=90.0, side=1),
           Source(m=2.0, x0=1.0, y0=1.0)]
    for x0, x1, y0, y1 in ((0.645, 1.895, -0.181, 0.944), (-0.276, 0.974, 0.258, 1.383), (0.9, 2.15, 0.013, 1.138)):
        W, H = x1 - x0, y1 - y0
        flow_features(els, (x0 - W, x1 + W, y0 - H, y1 + H), scale=max(W, H))


# user's screenshot (27 Oct): lifting cylinder with a source upstream-above it
WITH_SOURCE = [Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0), Source(m=1.0, x0=-1.729, y0=1.079)]


@pytest.mark.parametrize("region", [(-4.41, 4.24, -2.03, 2.43), (-20.0, 20.0, -15.0, 15.0)])
def test_stagnation_point_next_to_a_weak_source_is_found(region):
    """m/(2πU) ≈ 0.15 from the source: Newton started 0.05 × view away ran to other roots (and at
    large views the point was then dropped as 'inside a body', traced at the view's coarse scale)."""
    pts = find_stagnation_points(WITH_SOURCE, region)
    assert min(abs(p.z - (-1.8795 + 1.0295j)) for p in pts) < 1e-3


def test_warning_and_fill_agree_for_a_doublet():
    """The status bar warning (doublet not along the flow at it) and the Solid bodies layer use one
    test: misaligned (the source turns the flow at the doublet by −2.2°) = no body; δ set as the
    warning says = a closed body (the source's half-body is there in both)."""
    from physics.stagnation import open_elements
    from physics.validation import check_scene
    assert open_elements(WITH_SOURCE) == {1}
    (w,) = [s for s in check_scene(WITH_SOURCE) if s.severity == "warning"]
    assert "set δ = -2.221°" in w.message
    aligned = [Uniform(), Doublet(mu=1.0, delta=-2.221), Vortex(Gamma=-2.0), Source(m=1.0, x0=-1.729, y0=1.079)]
    assert open_elements(aligned) == set()
    assert not [s for s in check_scene(aligned) if s.severity == "warning"]
    box = (-4.41, 4.24, -2.03, 2.43)
    for els, cylinder in ((WITH_SOURCE, False), (aligned, True)):
        m = body_map(els, box, (240, 470), _dividing(els, box))
        assert m.contains(np.array([0.0 + 0.5j, 0.0 - 0.5j])).tolist() == [cylinder, cylinder]
        assert m.contains(np.array([-1.0 + 1.25j]))[0]                     # the half-body
        assert not m.contains(np.array([1.6 - 0.3j, 2.5 - 0.35j])).any()   # no tail behind the cylinder
