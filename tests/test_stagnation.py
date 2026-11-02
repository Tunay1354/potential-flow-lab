"""Stagnation points and dividing streamlines against the analytic solutions of the course."""
import numpy as np
import pytest

from physics import (Doublet, SectorFlow, Source, SymmetryWall, Uniform, Vortex, complex_potential,
                     complex_velocity)
from physics.field import fluid_mask
from physics.stagnation import find_stagnation_points, flow_features

R = (-4.0, 4.0, -3.0, 3.0)


def zs(points):
    return np.array(sorted([p.z for p in points], key=lambda z: (z.real, z.imag)))


def test_uniform_flow_has_none():
    assert find_stagnation_points([Uniform(alpha=30.0)], R) == []


def test_non_lifting_cylinder_front_and_back():
    pts = find_stagnation_points([Uniform(V=2.0), Doublet(mu=2.0)], R)        # a = √(μ/V) = 1
    np.testing.assert_allclose(zs(pts), [-1.0, 1.0], atol=1e-9)
    assert {p.kind for p in pts} == {"body"}


@pytest.mark.parametrize("gamma", [-2.0, 3.0, -6.0])
def test_lifting_cylinder_points_on_the_surface(gamma):
    """|Γ| < 4πV∞a:  sin θ = Γ / (4π V∞ a)  (Γ > 0 counter-clockwise)."""
    V, a = 1.5, 1.2
    pts = find_stagnation_points([Uniform(V=V), Doublet(mu=V * a * a), Vortex(Gamma=gamma)], R)
    th = np.arcsin(gamma / (4 * np.pi * V * a))
    np.testing.assert_allclose(zs(pts), sorted([a * np.exp(1j * (np.pi - th)), a * np.exp(1j * th)],
                                               key=lambda z: z.real), atol=1e-8)


def test_fast_spinning_cylinder_point_leaves_the_surface():
    """|Γ| > 4πV∞a: one point in the flow on the y-axis; the second root (inside the cylinder) is
    not physical and is not reported."""
    V, a, G = 1.0, 1.0, -15.0
    pts = find_stagnation_points([Uniform(V=V), Doublet(mu=1.0), Vortex(Gamma=G)], R)
    c = G / (2 * np.pi)
    y_out = (c - np.sqrt(c * c - 4 * V * V * a * a)) / (2 * V)                 # |y| > a
    assert len(pts) == 1
    assert abs(pts[0].z - 1j * y_out) < 1e-8 and abs(y_out) > a


def test_critical_spin_gives_one_double_point():
    G = -4 * np.pi                                                             # Γ = −4πV∞a
    pts = find_stagnation_points([Uniform(), Doublet(mu=1.0), Vortex(Gamma=G)], R)
    assert len(pts) == 1 and abs(pts[0].z - (-1j)) < 1e-5


def test_rankine_half_body_and_oval():
    V, m = 1.0, 2.0
    pts = find_stagnation_points([Uniform(V=V), Source(m=m, x0=0.5)], R)
    np.testing.assert_allclose(zs(pts), [0.5 - m / (2 * np.pi * V)], atol=1e-9)
    b, m = 1.0, 3.0
    pts = find_stagnation_points([Uniform(V=V), Source(m=m, x0=-b), Source(m=-m, x0=b)], R)
    x = b * np.sqrt(1 + m / (np.pi * V * b))
    np.testing.assert_allclose(zs(pts), [-x, x], atol=1e-9)


def test_corner_flow_vertex_and_convex_corner():
    pts = find_stagnation_points([SectorFlow(V=1.0, x0=0.5, y0=0.25)], (-1, 3, -1, 3))
    assert [(p.z, p.kind) for p in pts] == [(0.5 + 0.25j, "vertex")]
    assert find_stagnation_points([SectorFlow(theta2=270.0)], R) == []          # n < 1: singular, not 0


def test_source_near_wall_point_is_on_the_wall():
    pts = find_stagnation_points([SymmetryWall(yw=0.0), Source(m=2.0, y0=1.0)], (-4, 4, -1, 5))
    assert len(pts) == 1 and abs(pts[0].z) < 1e-9 and pts[0].kind == "wall"


def test_zeros_behind_walls_are_not_reported():
    els = [SymmetryWall(), SymmetryWall(theta_w=90.0, side=1), Source(m=2.0, x0=1.0, y0=1.0),
           Vortex(Gamma=1.0, x0=2.0, y0=0.5)]
    pts = find_stagnation_points(els, (-3, 4, -3, 4))
    z = np.array([p.z for p in pts])
    assert z.size and (fluid_mask(els, z) | (np.abs(z.real) < 1e-7) | (np.abs(z.imag) < 1e-7)).all()


def test_mirror_zero_behind_the_wall_is_not_reported():
    """Uniform flow along a wall + source near it: the image system is symmetric about the wall, so
    every zero in the fluid has a mirror zero in the solid. Only the fluid one is a stagnation point:
    U(z² + 1) + (m/π) z = 0  ->  z = (−m/π ± √(m²/π² − 4U²)) / 2U."""
    U, m = 1.0, 2.0
    pts = find_stagnation_points([SymmetryWall(yw=0.0), Uniform(V=U), Source(m=m, y0=1.0)], R)
    root = (-m / np.pi + np.sqrt(complex(m * m / np.pi ** 2 - 4 * U * U))) / (2 * U)
    root = complex(root.real, abs(root.imag))
    assert len(pts) == 1 and abs(pts[0].z - root) < 1e-9


def test_point_on_a_wall_extension_inside_the_solid_is_not_reported():
    """Two walls meeting at (0, −1.5): zeros on the line x = 0 BELOW the corner are behind the
    other wall (solid), only the ones on the fluid side count."""
    els = [SymmetryWall(yw=-1.5), SymmetryWall(yw=-1.5, theta_w=90.0, side=1), Source(m=2.0, x0=1.0, y0=1.0)]
    pts = find_stagnation_points(els, (-5, 10, -5, 9))
    assert pts and all(p.y >= -1.5 - 1e-9 and p.x >= -1e-9 for p in pts)


def test_vortex_pairs():
    pts = find_stagnation_points([Vortex(Gamma=1.0, x0=-1.0), Vortex(Gamma=1.0, x0=1.0)], R)
    assert len(pts) == 1 and abs(pts[0].z) < 1e-9 and pts[0].kind == "flow"
    assert find_stagnation_points([Vortex(Gamma=1.0, x0=-1.0), Vortex(Gamma=-1.0, x0=1.0)], R) == []


@pytest.mark.parametrize("els, region", [
    ([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)], R),
    ([SymmetryWall(yw=-1.0), SymmetryWall(yw=1.0, side=1), Uniform(), Source(m=1.0, x0=-1.5, y0=0.3),
      Vortex(Gamma=1.0, x0=1.5, y0=-0.3)], (-5, 5, -1.6, 1.6)),
    ([Uniform(alpha=20.0), Source(m=1.0, x0=-1.0), Doublet(mu=0.5, x0=1.5, delta=40.0)], R),
])
def test_every_point_is_a_zero_of_the_velocity_in_the_fluid(els, region):
    pts = find_stagnation_points(els, region)
    assert pts
    z = np.array([p.z for p in pts])
    assert np.all(np.abs(complex_velocity(els, z)) < 1e-8)
    assert np.all(fluid_mask(els, z) | np.array([p.kind == "wall" for p in pts]))


# ---------------------------------------------------------------- dividing streamlines
def test_cylinder_dividing_streamline_is_psi_zero_and_the_surface():
    els = [Uniform(), Doublet(mu=1.0)]
    f = flow_features(els, R)
    pts = np.concatenate([ln[:, 0] + 1j * ln[:, 1] for ln in f.dividing])
    psi = complex_potential(els, pts).imag
    assert np.max(np.abs(psi)) < 1e-3                                   # ψ = 0 along all of them
    on_surface = np.abs(np.abs(pts) - 1.0) < 1e-3
    ang = np.angle(pts[on_surface])
    assert (ang > 2.5).any() and (ang < -2.5).any() and (np.abs(ang - 1.57) < 0.1).any() \
        and (np.abs(ang + 1.57) < 0.1).any()                           # the whole circle
    assert (pts.real < -3.5).any() and (pts.real > 3.5).any()           # the axis up- and downstream
    assert np.all(np.abs(pts) > 1.0 - 1e-3)                             # nothing drawn inside the body


def test_dividing_lines_follow_constant_psi_through_their_point():
    els = [Uniform(), Doublet(mu=1.0), Vortex(Gamma=-15.0)]           # ψ single-valued here
    f = flow_features(els, R)
    psi0 = complex_potential(els, np.array([f.points[0].z])).imag[0]
    for ln in f.dividing:
        z = ln[:, 0] + 1j * ln[:, 1]
        assert np.max(np.abs(complex_potential(els, z).imag - psi0)) < 5e-3
    loop = np.concatenate([ln[:, 0] + 1j * ln[:, 1] for ln in f.dividing])
    assert loop.imag.max() > 1.0 and np.abs(loop).min() > 1.0          # goes around the cylinder, outside it


def test_two_vortices_figure_eight():
    """ψ ∝ ln|z² − 1|: the dividing streamline through 0 is the lemniscate |z² − 1| = 1 (|x| ≤ √2)."""
    f = flow_features([Vortex(Gamma=1.0, x0=-1.0), Vortex(Gamma=1.0, x0=1.0)], R)
    assert len(f.dividing) == 4
    pts = np.concatenate([ln[:, 0] + 1j * ln[:, 1] for ln in f.dividing])
    np.testing.assert_allclose(np.abs(pts ** 2 - 1), 1.0, atol=2e-3)
    assert pts.real.min() == pytest.approx(-np.sqrt(2), abs=0.02)
    assert pts.real.max() == pytest.approx(np.sqrt(2), abs=0.02)


def test_source_near_wall_dividing_line_goes_up_to_the_source():
    f = flow_features([SymmetryWall(yw=0.0), Source(m=2.0, y0=1.0)], (-4, 4, -1, 5))
    assert len(f.dividing) == 1
    ln = f.dividing[0]
    np.testing.assert_allclose(ln[:, 0], 0.0, atol=1e-9)
    assert ln[:, 1].min() < 1e-6 and ln[:, 1].max() > 0.9


def test_no_features_without_flow():
    f = flow_features([Uniform(V=0.0)], R)
    assert f.points == [] and f.dividing == []


def test_description_has_no_negative_zero():
    from physics.stagnation import StagnationPoint
    assert StagnationPoint(complex(1.0, -1e-17), "body").describe() == \
        "Stagnation point (1.0000, 0.0000), on the body surface"


def test_every_dividing_streamline_starts_or_ends_at_its_own_point():
    f = flow_features([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)], R)
    assert len(f.owners) == len(f.dividing) and set(f.owners) == {0, 1}
    for ln, k in zip(f.dividing, f.owners):
        ends = [complex(*ln[0]), complex(*ln[-1])]
        assert min(abs(e - f.points[k].z) for e in ends) < 1e-12


def test_newton_seed_exactly_on_a_free_vortex_is_no_crash():
    """A Newton seed placed exactly on a singularity (a free vortex's centre in a view symmetric about it)
    divided by zero in the compiled kernel (31 Oct). Such a seed simply finds nothing."""
    from physics.stagnation import _newton, resolve
    for els in ([Vortex(Gamma=6.0)], [Uniform(), Doublet(mu=1.0)], [Uniform(), Source(m=1.0, x0=0.5)]):
        flows = resolve(els)
        seeds = np.array([0j, 0.5 + 0j, 1e-7 + 0j, 2.0 + 1.0j])          # (0 and 0.5: on the singular points)
        z = _newton(els, flows, seeds, 4.0, (-8.0, 8.0, -8.0, 8.0))
        on = 1 if els[-1].TYPE == "source" else 0
        assert z.shape == seeds.shape and np.isnan(z[on])
    assert find_stagnation_points([Vortex(Gamma=6.0)], (-3.4558823529411766, 3.4558823529411766, -2.0, 2.0)) == []


def test_closed_channel_far_zoomed_out_keeps_its_points_and_no_noise():
    """Found by scripts/random_test.py on his PC: far down a channel closed at one end the flow dies out like
    e^(−πx/H). Zoomed out 10× the view's median speed was ~0, so no point was found at all; 100× there were
    8 false points in the rounding noise of the dead flow. Now the same 4 points at every zoom."""
    W = SymmetryWall
    els = [W(xw=-0.910979, yw=-1.561937, theta_w=-30.252308, side=0),
           W(xw=0.910979, yw=1.561937, theta_w=-30.252308, side=1),
           W(xw=-2.547992, yw=1.486083, theta_w=59.747692, side=1),
           Doublet(mu=0.857930, x0=0.843207, y0=0.650283, delta=-30.252308)]
    found = []
    for half in (40.0, 400.0, 4000.0):
        pts = find_stagnation_points(els, (-half, half, -half, half), scale=2 * half)
        found.append(sorted((round(p.x, 4), round(p.y, 4)) for p in pts))
    assert len(found[0]) == 4 and found[0] == found[1] == found[2]


def test_dividing_lines_start_in_the_slow_corner_of_a_sector_flow():
    """Found by scripts/random_test.py: a source in a 45° sector flow makes a body in the corner; its branches
    start where the flow (∝ r³ there) is slower than the 3× region's "too slow" speed, so they stopped at
    once and the body was missing in the Fit view but there 4× closer. Now traced from where they start."""
    els = [SectorFlow(V=2.6034, theta1=-65.4987, theta2=-20.4987), Source(m=1.8196, x0=0.41019, y0=-0.38249)]
    for half in (2.0, 13.0):                                # about the view 4× closer, and 3× the Fit view
        feats = flow_features(els, (-half + 0.4, half + 0.4, -half - 0.3, half - 0.3), scale=half)
        assert len(feats.inner) == 2
