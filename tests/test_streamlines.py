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
    s = trace_streamlines(els, XLIM, YLIM, arrows_per_line=2)
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
