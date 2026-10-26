"""Streamline tracer: lines must be tangent to the velocity, follow ψ = const, respect
singularities and view limits, and be ordered / arrowed in the flow direction."""
import numpy as np
import pytest

from physics import Doublet, Source, Uniform, Vortex, complex_potential, velocity
from physics.streamlines import trace_streamlines

XLIM, YLIM = (-4.0, 4.0), (-3.0, 3.0)


def tangents(line):
    t = np.diff(line, axis=0)
    return t / np.linalg.norm(t, axis=1)[:, None], 0.5 * (line[1:] + line[:-1])


@pytest.mark.parametrize("alpha", [0.0, 30.0, -60.0])
def test_uniform_flow_gives_straight_lines_along_alpha(alpha):
    s = trace_streamlines([Uniform(V=1.0, alpha=alpha)], XLIM, YLIM)
    assert len(s.lines) > 5
    a = np.radians(alpha)
    for ln in s.lines:
        t, _ = tangents(ln)
        np.testing.assert_allclose(t[:, 0], np.cos(a), atol=1e-9)
        np.testing.assert_allclose(t[:, 1], np.sin(a), atol=1e-9)


SCENES = {
    "cylinder": [Uniform(V=1.0), Doublet(mu=1.0)],
    "lifting cylinder": [Uniform(V=1.0), Doublet(mu=1.0), Vortex(Gamma=-2.0)],
    "source + sink + vortex": [Uniform(), Source(m=3, x0=-1.5), Source(m=-3, x0=1.5), Vortex(Gamma=4, y0=1.8)],
}


@pytest.mark.parametrize("name", SCENES)
def test_lines_are_tangent_to_velocity_and_in_flow_direction(name):
    els = SCENES[name]
    s = trace_streamlines(els, XLIM, YLIM)
    assert s.lines
    for ln in s.lines:
        t, mid = tangents(ln)
        u, v = velocity(els, mid[:, 0], mid[:, 1])
        sp = np.hypot(u, v)
        cos = (t[:, 0] * u + t[:, 1] * v) / sp
        assert np.all(cos > 0.98)          # same direction as the flow (small chord error allowed)


def test_streamlines_follow_constant_psi():
    """For uniform flow + doublet ψ is single-valued, so ψ must stay constant along every line."""
    els = SCENES["cylinder"]
    s = trace_streamlines(els, XLIM, YLIM)
    for ln in s.lines:
        psi = complex_potential(els, ln[:, 0] + 1j * ln[:, 1]).imag
        assert np.ptp(psi) < 2e-3 * (1 + np.abs(psi).max())


def test_vortex_lines_are_closed_circles():
    s = trace_streamlines([Vortex(Gamma=1.0)], XLIM, YLIM)
    closed = [ln for ln in s.lines if np.allclose(ln[0], ln[-1])]
    assert len(closed) >= 3
    for ln in closed:
        r = np.hypot(ln[:, 0], ln[:, 1])
        assert np.ptp(r) < 1e-3 * r.mean()                          # a circle
        length = np.sum(np.linalg.norm(np.diff(ln, axis=0), axis=1))
        assert length == pytest.approx(2 * np.pi * r.mean(), rel=0.01)   # exactly one turn


def test_vortex_lines_turn_counter_clockwise_for_positive_gamma():
    for gamma, sign in [(1.0, 1), (-1.0, -1)]:
        s = trace_streamlines([Vortex(Gamma=gamma)], XLIM, YLIM)
        ln = max(s.lines, key=len)
        cross = ln[:-1, 0] * ln[1:, 1] - ln[:-1, 1] * ln[1:, 0]     # z × dz
        assert np.sign(cross.sum()) == sign


@pytest.mark.parametrize("name", SCENES)
def test_lines_stay_away_from_singular_points_and_inside_view(name):
    els = SCENES[name]
    s = trace_streamlines(els, XLIM, YLIM)
    pts = np.vstack(s.lines)
    z = pts[:, 0] + 1j * pts[:, 1]
    for e in els:
        for p in e.singular_points():
            assert np.min(np.abs(z - p)) > 0.4 * s.separation
    m = 0.05 * 8.0
    assert pts[:, 0].min() > XLIM[0] - m and pts[:, 0].max() < XLIM[1] + m
    assert pts[:, 1].min() > YLIM[0] - m and pts[:, 1].max() < YLIM[1] + m


def test_source_lines_point_outward_sink_lines_inward():
    for m in (1.0, -1.0):
        s = trace_streamlines([Source(m=m)], XLIM, YLIM)
        for ln in s.lines:
            r = np.hypot(ln[:, 0], ln[:, 1])
            assert np.all(np.sign(np.diff(r)) == np.sign(m))


@pytest.mark.parametrize("name", SCENES)
def test_arrows_point_in_flow_direction(name):
    els = SCENES[name]
    s = trace_streamlines(els, XLIM, YLIM, arrow_density=2)
    assert s.arrows
    for x, y, ang in s.arrows:
        u, v = velocity(els, x, y)
        assert np.cos(ang) * u + np.sin(ang) * v > 0


def test_density_controls_number_of_lines():
    els = [Uniform()]
    n1 = len(trace_streamlines(els, XLIM, YLIM, density=0.5).lines)
    n2 = len(trace_streamlines(els, XLIM, YLIM, density=2.0).lines)
    assert n2 > 2.5 * n1


def test_lines_fill_the_view_after_zoom_out():
    """Recomputed for a larger view, lines must reach the new edges (not only the old region)."""
    s = trace_streamlines([Uniform()], (-40, 40), (-30, 30))
    ys = np.concatenate([ln[:, 1] for ln in s.lines])
    assert ys.min() < -25 and ys.max() > 25


def test_result_is_repeatable_and_empty_cases():
    els = SCENES["lifting cylinder"]
    a = trace_streamlines(els, XLIM, YLIM)
    b = trace_streamlines(els, XLIM, YLIM)
    assert len(a.lines) == len(b.lines)
    assert all(np.array_equal(p, q) for p, q in zip(a.lines, b.lines))
    assert trace_streamlines([], XLIM, YLIM).lines == []
    assert trace_streamlines([Uniform(enabled=False)], XLIM, YLIM).lines == []
    assert trace_streamlines([Uniform(V=0.0)], XLIM, YLIM).lines == []


# ---------------------------------------------------------------- picture quality (Package B)
from physics import SectorFlow, SymmetryWall  # noqa: E402
from physics.streamlines import (STOP_RATIO, TAPER_RATIO, Cancelled, fade_pieces,  # noqa: E402
                                 trace_streamlines as _trace)


def _offsets_across(lines, alpha):
    a = np.radians(alpha)
    nrm = np.array([-np.sin(a), np.cos(a)])
    return np.sort([float(np.mean(ln @ nrm)) for ln in lines])


@pytest.mark.parametrize("alpha", [0.0, 30.0, -60.0, 180.0])
def test_uniform_flow_lines_are_exactly_d_apart(alpha):
    s = _trace([Uniform(alpha=alpha)], XLIM, YLIM)
    gaps = np.diff(_offsets_across(s.lines, alpha))
    np.testing.assert_allclose(gaps, s.separation, rtol=0.02)


def _min_distance_between_lines(s, skip_ends=0.0):
    """Smallest distance between points of two DIFFERENT lines."""
    zs = [ln[:, 0] + 1j * ln[:, 1] for ln in s.lines]
    best = np.inf
    for i in range(len(zs)):
        for j in range(i + 1, len(zs)):
            best = min(best, float(np.min(np.abs(zs[i][:, None] - zs[j][None, :]))))
    return best


@pytest.mark.parametrize("name", SCENES)
def test_lines_never_come_closer_than_the_stop_distance(name):
    s = _trace(SCENES[name], XLIM, YLIM)
    # raster cells are d/4, so allow a quarter cell of quantisation
    assert _min_distance_between_lines(s) > (STOP_RATIO - 0.1) * s.separation


@pytest.mark.parametrize("els, view", [
    ([SymmetryWall(yw=0.0), Source(m=2.0, y0=1.0)], ((-4, 4), (-1, 5))),
    ([SectorFlow(V=1.0)], ((-0.6, 3.4), (-0.6, 3.0))),
    ([SectorFlow(theta2=360.0)], ((-3, 3), (-2.4, 2.4))),
])
def test_walls_count_as_streamlines(els, view):
    """No line runs on top of a wall: walls and wedge sides keep the line spacing."""
    s = _trace(els, *view)
    pts = np.vstack(s.lines)
    z = pts[:, 0] + 1j * pts[:, 1]
    for e in els:
        if e.IS_BOUNDARY:
            dist = np.abs(e.signed_distance(z))
        elif e.TYPE == "sector":                                # distance to both sides
            th1, th2 = np.radians(e.theta1), np.radians(e.theta1 + e.beta_deg)
            dist = np.minimum(_ray_distance(z, e.z0, th1), _ray_distance(z, e.z0, th2))
        else:
            continue
        assert dist.min() > (STOP_RATIO - 0.1) * s.separation


def _ray_distance(z, z0, theta):
    u = np.exp(1j * theta)
    t = np.maximum(((z - z0) * np.conj(u)).real, 0.0)
    return np.abs(z - (z0 + t * u))


@pytest.mark.parametrize("name", ["cylinder", "lifting cylinder"])
def test_lines_do_not_cross_the_cylinder_surface(name):
    """The body surface r = a is a streamline: no line may run from outside to inside (this
    happens if the tracer runs through a stagnation point on the surface)."""
    s = _trace(SCENES[name], XLIM, YLIM)
    for ln in s.lines:
        r = np.hypot(ln[:, 0], ln[:, 1])
        assert r.min() > 1.0 - 1e-3 or r.max() < 1.0 + 1e-3


def test_cancel_callback_stops_the_computation():
    with pytest.raises(Cancelled):
        _trace(SCENES["cylinder"], XLIM, YLIM, cancelled=lambda: True)


def test_arrows_are_spread_evenly_and_inside_the_view():
    s = _trace([Uniform()], XLIM, YLIM)
    a = np.array([(x, y) for x, y, _ in s.arrows])
    assert len(a) >= 8
    assert a[:, 0].min() > XLIM[0] and a[:, 0].max() < XLIM[1]
    assert a[:, 1].min() > YLIM[0] and a[:, 1].max() < YLIM[1]
    z = a[:, 0] + 1j * a[:, 1]
    dist = np.abs(z[:, None] - z[None, :]) + np.eye(len(z)) * 1e9
    nearest = dist.min(axis=1)
    assert nearest.min() > 0.5 * np.median(nearest)            # no clumps
    assert len(set(np.round(a[:, 0], 6))) > len(a) / 3          # staggered, not one column
    assert _trace([Uniform()], XLIM, YLIM, arrow_density=0).arrows == []
    assert len(_trace([Uniform()], XLIM, YLIM, arrow_density=2).arrows) > 2.5 * len(a)


def test_fade_pieces_keep_the_whole_line():
    s = _trace(SCENES["lifting cylinder"], XLIM, YLIM)
    d = s.separation
    assert any(t[0] or t[1] for t in s.tapers)                  # this scene has cut lines
    levels = fade_pieces(s.lines, s.tapers, d, levels=4)
    assert len(levels) == 5

    def length(xy):
        seg = np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1]))
        return float(np.nansum(seg))

    total = sum(length(ln) for ln in s.lines)
    assert sum(length(xy) for xy in levels) == pytest.approx(total, rel=1e-9)
    # every fading step of a cut end is TAPER_RATIO·d / levels long (or shorter for short lines)
    n_cut_ends = sum(int(a) + int(b) for a, b in s.tapers)
    assert length(levels[4]) <= n_cut_ends * TAPER_RATIO * d / 4 * (1 + 1e-9)


def test_lines_without_cut_ends_are_drawn_fully_opaque():
    s = _trace([Uniform()], XLIM, YLIM)
    assert not any(a or b for a, b in s.tapers)
    levels = fade_pieces(s.lines, s.tapers, s.separation)
    assert all(xy.size == 0 for xy in levels[1:])


def test_lines_stop_at_a_stagnation_point_instead_of_turning_a_corner():
    """Seeds right next to the rear stagnation point of the lifting cylinder: the tracer must
    stop at the saddle, never make a sharp corner there (that would leave the streamline)."""
    els = SCENES["lifting cylinder"]
    z_stag = np.exp(1j * np.arcsin(-2.0 / (4 * np.pi)))          # sin θ = Γ / (4π V a)
    for rho in (0.03, 0.06):
        for ang in range(0, 360, 15):
            z = z_stag + rho * np.exp(1j * np.radians(ang))
            s = _trace(els, XLIM, YLIM, seeds=[z])
            ln = s.lines[0]
            t, mid = tangents(ln)
            u, v = velocity(els, mid[:, 0], mid[:, 1])
            cos = (t[:, 0] * u + t[:, 1] * v) / np.hypot(u, v)
            assert cos.min() > 0.98, (rho, ang)


def test_given_seeds_are_drawn_first():
    s = _trace([Uniform()], XLIM, YLIM, seeds=[0.123 + 0.456j])
    np.testing.assert_allclose(s.lines[0][:, 1], 0.456)
