"""Interactive streamlines (StreamlineCache / StreamlineField): lines stay where they are while
panning, keep their places across zoom levels, and the picture stays evenly spaced."""
import numpy as np
import pytest

from physics import Doublet, SectorFlow, Source, SymmetryWall, Uniform, Vortex, kernel
from physics.streamlines import STOP_RATIO, Cancelled, StreamlineCache, StreamlineField

CYL = [Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)]
VIEW = ((-4.0, 4.0), (-3.0, 3.0))


def shifted(view, dx, dy=0.0):
    (x0, x1), (y0, y1) = view
    return (x0 + dx, x1 + dx), (y0 + dy, y1 + dy)


def as_complex(xy):
    return xy[:, 0] + 1j * xy[:, 1]


def contains_block(big, small):
    """True if the points of `small` appear, unchanged and in order, inside `big`."""
    if small.size > big.size:
        return False
    hits = np.nonzero(big == small[0])[0]
    return any(np.array_equal(big[i:i + small.size], small) for i in hits)


def min_gap(lines):
    zs = [as_complex(ln) for ln in lines]
    best = np.inf
    for i in range(len(zs)):
        for j in range(i + 1, len(zs)):
            best = min(best, float(np.min(np.abs(zs[i][:, None] - zs[j][None, :]))))
    return best


def test_small_pan_inside_the_computed_margin_changes_nothing():
    c = StreamlineCache(CYL)
    first = c.update(VIEW)
    assert first is not None and len(first.lines) > 20
    assert c.update(shifted(VIEW, 0.8, 0.5)) is None              # already computed around the view
    assert c.covers(shifted(VIEW, 0.8, 0.5))


@pytest.mark.parametrize("els", [CYL, [Uniform(alpha=30.0)],
                                 [SymmetryWall(yw=0.0), Source(m=2.0, y0=1.0)],
                                 [Vortex(Gamma=1.0)]], ids=["cylinder", "uniform", "wall", "vortex"])
def test_lines_do_not_move_when_panning(els):
    c = StreamlineCache(els)
    c.update(VIEW)
    L = c.level
    before = {ln.id: ln.pts.copy() for ln in c.fields[L].lines}
    res = c.update(shifted(VIEW, 9.0, 3.0))                        # far beyond the margin
    assert res is not None and c.level == L
    after = {ln.id: ln.pts for ln in c.fields[L].lines}
    d = c.fields[L].d
    # lines never jump: every old line is kept (maybe lengthened)
    assert all(i in after and contains_block(after[i], pts) for i, pts in before.items())
    assert len(after) > len(before)                                # the new area got lines
    assert min_gap(res.lines) > (STOP_RATIO - 0.15) * d            # no line runs into another


def test_continued_lines_have_no_jumps():
    c = StreamlineCache([Uniform(alpha=20.0), Source(m=1.0, x0=3.0, y0=1.0)])
    c.update(VIEW)
    c.update(shifted(VIEW, 7.0))
    f = c.fields[c.level]
    for ln in f.lines:
        steps = np.abs(np.diff(ln.pts))
        assert steps.max() <= f.h * 1.0001
        assert steps.min() > 0


def test_uniform_flow_stays_evenly_spaced_after_panning():
    c = StreamlineCache([Uniform(alpha=0.0)])
    c.update(VIEW)
    res = c.update(shifted(VIEW, 0.0, 7.5))
    ys = np.sort([float(np.mean(ln[:, 1])) for ln in res.lines])
    gaps = np.diff(ys)
    np.testing.assert_allclose(gaps, res.separation, rtol=0.03)


def test_vortex_circles_close_after_the_view_grows():
    c = StreamlineCache([Vortex(Gamma=2.0)])
    small = ((-1.0, 1.0), (-0.75, 0.75))
    c.update(small)
    level = c.level
    c.level = level                                                # same level, bigger region:
    f = c.fields[level]
    f.extend((-4.0, 4.0, -3.0, 3.0))                               # circles cut by the old border run on
    closed = [ln for ln in f.lines if ln.start == "closed"]
    radii = [np.mean(np.abs(ln.pts)) for ln in closed]
    assert sum(r > 1.0 for r in radii) >= 3
    for ln in closed:
        assert ln.end == "closed" and abs(ln.pts[0] - ln.pts[-1]) < 1e-12
        r = np.abs(ln.pts)
        assert np.ptp(r) < 1e-3 * r.mean()                         # still a circle, one turn


def test_small_zoom_keeps_the_level_and_the_picture():
    c = StreamlineCache(CYL)
    c.update(VIEW)
    L = c.level
    (x0, x1), (y0, y1) = VIEW
    for s in (0.9, 1.1, 1.2, 0.85):
        assert c.update(((x0 * s, x1 * s), (y0 * s, y1 * s))) is None
        assert c.level == L


def test_force_gives_the_current_picture_and_density_is_respected():
    c1, c2 = StreamlineCache(CYL, density=1.0), StreamlineCache(CYL, density=2.0)
    a, b = c1.update(VIEW), c2.update(VIEW)
    assert len(b.lines) > 1.5 * len(a.lines)
    again = c1.update(VIEW, force=True)
    assert again is not None and len(again.lines) == len(a.lines)
    no_arrows = c1.update(VIEW, arrow_density=0, force=True)
    assert no_arrows.arrows == [] and a.arrows


def test_cancelled_extension_is_redone_later():
    c = StreamlineCache(CYL)
    c.update(VIEW)
    calls = {"n": 0}

    def cancel_soon():
        calls["n"] += 1
        return calls["n"] > 3

    with pytest.raises(Cancelled):
        c.update(shifted(VIEW, 10.0), cancelled=cancel_soon)
    assert not c.covers(shifted(VIEW, 10.0))
    res = c.update(shifted(VIEW, 10.0))
    assert res is not None and c.covers(shifted(VIEW, 10.0))
    assert min_gap(res.lines) > (STOP_RATIO - 0.15) * res.separation


def test_far_pan_starts_again_instead_of_growing_forever():
    c = StreamlineCache([Uniform()])
    c.update(VIEW)
    for k in range(1, 8):
        c.update(shifted(VIEW, 40.0 * k))
    f = c.fields[c.level]
    x0, x1, y0, y1 = f.domain
    assert (x1 - x0) * (y1 - y0) < StreamlineCache.MAX_DOMAIN_FACTOR * 48.0


@pytest.mark.skipif(not kernel.HAVE_NUMBA, reason="Numba not installed")
def test_numpy_and_kernel_fields_agree():
    els = [Uniform(), Source(m=1.0, x0=-1.0, y0=0.5), Vortex(Gamma=1.5, x0=1.0, y0=-0.5)]
    ka, na = StreamlineField(els, 0.3), StreamlineField(els, 0.3, use_kernel=False)
    assert ka.compiled is not None and na.compiled is None
    for f in (ka, na):
        f.extend((-4, 4, -3, 3))
        f.extend((0, 8, -3, 3))
    assert abs(len(ka.lines) - len(na.lines)) <= 2
    same = sum(any(p.size == q.size and np.allclose(p, q, atol=1e-9) for q in [m.pts for m in na.lines])
               for p in [m.pts for m in ka.lines])
    assert same >= 0.9 * len(ka.lines)


def test_sector_and_walls_work_in_the_cache():
    for els in ([SectorFlow(theta2=360.0)], [SymmetryWall(yw=-1.0), SymmetryWall(yw=1.0, side=1), Uniform()]):
        c = StreamlineCache(els)
        a = c.update(VIEW)
        b = c.update(shifted(VIEW, 6.0))
        def total(r):
            return sum(float(np.sum(np.hypot(*np.diff(ln, axis=0).T))) for ln in r.lines)
        assert a is not None and b is not None and total(b) > 1.2 * total(a)


def _view_with_ideal_level(ideal, aspect=0.75):
    """Uniform flow: d = sqrt(W·H)/26 -> a view whose ideal level −log2(d) is `ideal`."""
    W = 26.0 / (2.0 ** ideal) / np.sqrt(aspect)
    return (-W / 2, W / 2), (-W * aspect / 2, W * aspect / 2)


def test_level_changes_only_after_a_clear_zoom():
    c = StreamlineCache([Uniform()])
    c.update(_view_with_ideal_level(2.4))
    assert c.level == 2
    c.update(_view_with_ideal_level(2.6))          # past the rounding point, inside the hysteresis
    assert c.level == 2
    c.update(_view_with_ideal_level(2.7))          # clearly closer to level 3
    assert c.level == 3
    c.update(_view_with_ideal_level(2.4))          # and back: stays at 3 until clearly at 2
    assert c.level == 3
    c.update(_view_with_ideal_level(2.3))
    assert c.level == 2


def test_single_level_cache_gives_the_same_picture_as_one_view():
    """The visible part looks like a single computation at that spacing."""
    c = StreamlineCache(CYL)
    res = c.update(VIEW)
    assert len(c.fields) == 1
    d = res.separation
    assert d == 2.0 ** -c.level
    assert min_gap(res.lines) > (STOP_RATIO - 0.15) * d


def _dist_to_polyline(q, line):
    """Distance from the points q to the polyline `line` (complex arrays)."""
    a, b = line[:-1], line[1:]
    ab = b - a
    t = np.clip(((q[:, None] - a[None, :]) * np.conj(ab)[None, :]).real / np.maximum(np.abs(ab) ** 2, 1e-300),
                0.0, 1.0)
    return np.min(np.abs(q[:, None] - (a[None, :] + t * ab[None, :])), axis=1)


def test_regular_lines_start_from_the_dividing_streamlines():
    """The dividing streamlines seed the regular picture: one regular line runs exactly along the
    (slanted) upstream dividing streamline of the lifting cylinder."""
    res = StreamlineCache(CYL).update(VIEW, force=True)
    assert len(res.stagnation) == 2 and res.dividing
    upstream = max(res.dividing, key=lambda ln: -ln[:, 0].min())        # reaches furthest left
    up = as_complex(upstream)
    up = up[(up.real < -1.3) & (up.real > -4.0)]                        # the part in view
    best = min((as_complex(ln) for ln in res.lines), key=lambda w: np.median(_dist_to_polyline(up[::5], w)))
    assert np.max(_dist_to_polyline(up, best)) < 1e-3


def test_forced_redraw_keeps_the_stagnation_points():
    """Theme / arrow changes redraw without new lines; the stagnation points must stay."""
    c = StreamlineCache(CYL)
    assert len(c.update(VIEW).stagnation) == 2
    again = c.update(VIEW, arrow_density=2.0, force=True)
    assert len(again.stagnation) == 2 and len(again.dividing) == 6


def test_dividing_line_seeds_do_not_pile_up():
    """The features (stagnation points, dividing streamlines) are found again whenever the view leaves
    their region, mostly the same ones: their seeds are added to a field only once."""
    c = StreamlineCache(CYL)
    c.update(((-4.0, 4.0), (-3.0, 3.0)))
    for f in c.fields.values():
        f.special_seeds = np.array([5.0 + 5.0j])            # one pending seed outside the region
    for _ in range(5):
        c._update_features((-4.0, 4.0, -3.0, 3.0), None)
    for f in c.fields.values():
        z = f.special_seeds
        assert z.size == 1 + len(c._seeds)
        gaps = np.abs(z[:, None] - z[None, :]) + np.eye(z.size) * 1e9
        assert gaps.min() > 0.2 * f.d


@pytest.mark.parametrize("scene, zoom", [
    ([Uniform(), Source(m=0.02)], ((-0.02, 0.01), (-0.01, 0.01))),                 # point 0.003 from the source
    ([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-4 * np.pi + 0.3)], ((-0.3, 0.3), (-1.2, -0.8))),   # close pair
])
def test_stagnation_points_are_searched_again_after_a_big_zoom(scene, zoom):
    """Searched at the scale of the whole view, a point that only shows at a finer scale was missing
    after zooming in (the view stayed inside the searched region, so nothing was searched again)."""
    from physics.stagnation import find_stagnation_points
    c = StreamlineCache(scene)
    c.update(((-4.0, 4.0), (-3.0, 3.0)))
    res = c.update(zoom)
    (x0, x1), (y0, y1) = zoom
    shown = [p for p in res.stagnation if x0 <= p.x <= x1 and y0 <= p.y <= y1]
    true = find_stagnation_points(scene, (x0, x1, y0, y1), scale=max(x1 - x0, y1 - y0))
    assert len(shown) == len(true) >= 1
    assert c.update(zoom) is None                                      # (then nothing new until it changes)
