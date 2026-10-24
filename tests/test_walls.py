"""Verification case 4: symmetry walls (method of images).

* wall-normal velocity V·n = 0 at many points on the wall (the professor's check)
* image rules agree with the Milne-Thomson plane theorem  F_total = F(z) + conj F(z*)
* analytic wall velocities for a vortex and a source near a wall
* corners (π/k), parallel walls (channel), invalid arrangements and invalid inputs
"""
import numpy as np
import pytest

from physics import (Doublet, Source, SymmetryWall, Uniform, Vortex, build_image_system, check_scene,
                     complex_potential, compute_field, complex_velocity, velocity)
from physics.streamlines import trace_streamlines

W = SymmetryWall


def wall_points(wall, half_length=8.0, n=801):
    t = np.linspace(-half_length, half_length, n)
    return wall.point + t * wall.direction


def normal_velocity(els, wall, **kw):
    z = wall_points(wall, **kw)
    u, v = velocity(els, z.real, z.imag)
    return ((u + 1j * v) * np.conj(wall.normal)).real


def scale(els, wall):
    """Typical speed near the wall, for relative tolerances."""
    z = wall_points(wall, n=101)
    u, v = velocity(els, z.real, z.imag)
    return max(1.0, float(np.max(np.hypot(u, v))))


# ---------------------------------------------------------------- geometry
def test_reflection_geometry():
    w = W(xw=0.0, yw=-1.0, theta_w=0.0)
    assert complex(w.reflect(2 + 3j)) == pytest.approx(2 - 5j)                 # y -> −2 − y
    w = W(xw=1.0, yw=1.0, theta_w=45.0)
    assert complex(w.reflect(3 + 1j)) == pytest.approx(1 + 3j)                 # mirror in y = x
    z = np.array([0.3 + 2j, -4 - 1j, 7 + 0.5j])
    w = W(xw=0.4, yw=-0.2, theta_w=-27.0)
    np.testing.assert_allclose(w.reflect(w.reflect(z)), z, atol=1e-14)          # involution
    on = wall_points(w, n=11)
    np.testing.assert_allclose(w.reflect(on), on, atol=1e-13)                   # wall points are fixed


def test_fluid_side_and_normal():
    w = W(yw=0.0, theta_w=0.0, side=0)
    assert w.normal == pytest.approx(1j)                    # left of +x direction = above
    assert w.fluid_region(np.array([1j]))[0] and not w.fluid_region(np.array([-1j]))[0]
    w = W(yw=0.0, theta_w=0.0, side=1)
    assert w.normal == pytest.approx(-1j)
    assert w.fluid_region(np.array([-1j]))[0] and not w.fluid_region(np.array([1j]))[0]


# ---------------------------------------------------------------- image rules
def test_image_rules():
    w = W(xw=0.0, yw=-1.0, theta_w=30.0)
    s = Source(m=2.0, x0=0.0, y0=0.0).mirrored(w)
    zs = complex(w.reflect(0j))
    assert (s.m, s.x0, s.y0) == pytest.approx((2.0, zs.real, zs.imag))           # same sign
    v = Vortex(Gamma=1.5).mirrored(w)
    assert v.Gamma == -1.5                                                       # opposite sign
    d = Doublet(mu=0.8, delta=10.0).mirrored(w)
    assert (d.mu, d.delta) == pytest.approx((0.8, 50.0))                         # δ* = 2θ_w − δ
    assert Uniform().mirrored(w) is None                                         # freestream not imaged


WALLS = [W(yw=-1.0), W(xw=0.5, yw=-0.5, theta_w=35.0), W(xw=2.0, yw=0.0, theta_w=90.0, side=0),
         W(xw=0.0, yw=-2.0, theta_w=-150.0, side=1)]
FLOWS = [Source(m=2.0, x0=0.2, y0=0.4), Source(m=-1.0, x0=-1.0, y0=1.0), Vortex(Gamma=1.5, x0=0.7, y0=0.9),
         Doublet(mu=0.6, x0=-0.4, y0=0.6, delta=25.0)]


@pytest.mark.parametrize("wall", WALLS, ids=lambda w: f"theta{w.theta_w:g}")
@pytest.mark.parametrize("flow", FLOWS, ids=lambda e: e.TYPE)
def test_plane_theorem(wall, flow):
    """w_total(z) = w(z) + e^{−2iθ_w} conj(w(z*))  (derivative of F(z) + conj F(z*))."""
    if wall.signed_distance(flow.z0) <= 0:
        pytest.skip("element not on the fluid side of this wall")
    rng = np.random.default_rng(5)
    z = flow.z0 + rng.uniform(-3, 3, 40) + 1j * rng.uniform(-3, 3, 40)
    z = z[wall.signed_distance(z) > 0.05]
    expected = flow.complex_velocity(z) + np.exp(-2j * np.radians(wall.theta_w)) * \
        np.conj(flow.complex_velocity(wall.reflect(z)))
    np.testing.assert_allclose(complex_velocity([wall, flow], z), expected, rtol=1e-12, atol=1e-12)


@pytest.mark.parametrize("wall", WALLS, ids=lambda w: f"theta{w.theta_w:g}")
def test_no_flow_through_wall_mixed_scene(wall):
    """V·n = 0 on the wall for a scene with every element type (uniform flow parallel to the wall)."""
    els = [wall, Uniform(V=1.0, alpha=wall.theta_w)]
    els += [f for f in FLOWS if wall.signed_distance(f.z0) > 0]
    assert len(els) >= 4
    vn = normal_velocity(els, wall)
    assert np.max(np.abs(vn)) < 1e-12 * scale(els, wall)


def test_wall_is_a_streamline():
    """ψ = const along the wall (vortex, doublet and freestream have a single-valued ψ here)."""
    wall = W(xw=0.0, yw=-1.0, theta_w=20.0)
    els = [wall, Uniform(V=1.0, alpha=20.0), Vortex(Gamma=1.0, x0=0.5, y0=0.8), Doublet(mu=0.5, x0=-1, y0=1)]
    psi = complex_potential(els, wall_points(wall)).imag
    assert np.ptp(psi) < 1e-10


def test_vortex_near_wall_analytic():
    """Vortex Γ at height h above the wall y = 0:  u(x, 0) = Γ h / (π (x² + h²)),  v(x, 0) = 0."""
    G, h = 1.7, 0.8
    x = np.linspace(-5, 5, 201)
    u, v = velocity([W(yw=0.0), Vortex(Gamma=G, y0=h)], x, 0 * x)
    np.testing.assert_allclose(u, G * h / (np.pi * (x**2 + h**2)), rtol=1e-12)
    np.testing.assert_allclose(v, 0.0, atol=1e-14)


def test_source_near_wall_analytic():
    """Source m at height h above y = 0:  u(x, 0) = m x / (π (x² + h²)),  v(x, 0) = 0."""
    m, h = 2.3, 1.1
    x = np.linspace(-5, 5, 201)
    u, v = velocity([W(yw=0.0), Source(m=m, y0=h)], x, 0 * x)
    np.testing.assert_allclose(u, m * x / (np.pi * (x**2 + h**2)), rtol=1e-12, atol=1e-15)
    np.testing.assert_allclose(v, 0.0, atol=1e-14)


def test_disabled_wall_has_no_effect():
    els = [W(yw=-1.0, enabled=False), Source(m=1.0)]
    z = np.array([1 + 1j, -2 - 0.5j])
    np.testing.assert_allclose(complex_velocity(els, z), Source(m=1.0).complex_velocity(z))


# ---------------------------------------------------------------- several walls
@pytest.mark.parametrize("angle, n_images", [(90.0, 3), (60.0, 5), (45.0, 7)])
def test_corner_with_angle_pi_over_k_is_exact(angle, n_images):
    a = W(theta_w=0.0, yw=0.0, side=0)            # fluid above y = 0
    b = W(theta_w=angle, yw=0.0, side=1)          # fluid to the right of the line at `angle`
    mid = np.exp(1j * np.radians(angle / 2))
    els = [a, b, Source(m=1.0, x0=(1.2 * mid).real, y0=(1.2 * mid).imag),
           Vortex(Gamma=0.7, x0=(2.0 * mid * np.exp(0.1j)).real, y0=(2.0 * mid * np.exp(0.1j)).imag)]
    system = build_image_system(els)
    assert system.closed and system.exact and not system.issues
    assert system.n_images == 2 * n_images        # each of the 2 flow elements gets 2k − 1 images
    for w in (a, b):
        z = w.point + np.linspace(0.01, 8, 400) * (w.direction if w is a else np.exp(1j * np.radians(angle)))
        u, v = velocity(els, z.real, z.imag)
        assert np.max(np.abs(((u + 1j * v) * np.conj(w.normal)).real)) < 1e-12


def test_corner_with_other_angle_is_reported():
    els = [W(theta_w=0.0, yw=0.0, side=0), W(theta_w=70.0, yw=0.0, side=1), Source(m=1.0, x0=1.0, y0=0.5)]
    system = build_image_system(els)
    assert not system.exact
    assert any(i.is_error and "180°/k" in i.message for i in system.issues)


def test_channel_is_exact():
    """Two parallel walls: infinite image rows summed in closed form."""
    a, b = W(yw=0.0, side=0), W(yw=2.0, side=1)
    els = [a, b, Uniform(V=1.0), Source(m=1.0, x0=0.0, y0=0.7), Vortex(Gamma=0.8, x0=1.0, y0=1.3),
           Doublet(mu=0.3, x0=-2.0, y0=1.0, delta=40.0)]
    system = build_image_system(els)
    assert system.periodic and system.exact and not system.issues
    for w in (a, b):
        assert np.max(np.abs(normal_velocity(els, w, half_length=30.0))) < 1e-12


def test_channel_tilted_walls():
    a = W(xw=0.0, yw=0.0, theta_w=30.0, side=0)
    b = W(xw=-1.0, yw=2.0, theta_w=210.0, side=0)       # parallel, opposite direction, facing a
    els = [a, b, Source(m=1.0, x0=-0.5, y0=0.8), Vortex(Gamma=-1.0, x0=0.3, y0=1.0)]
    assert not [s for s in check_scene(els) if s.is_error]
    for w in (a, b):
        assert np.max(np.abs(normal_velocity(els, w))) < 1e-12


def test_source_in_channel_far_field():
    """Mass conservation: the flux m splits equally, u -> ±m / (2H) far up- and downstream."""
    H, m = 2.0, 1.0
    els = [W(yw=0.0), W(yw=H, side=1), Source(m=m, y0=0.7)]
    u, v = velocity(els, np.array([80.0, -80.0, 80.0]), np.array([0.3, 1.0, 1.9]))
    np.testing.assert_allclose(u, [m / (2 * H), -m / (2 * H), m / (2 * H)], rtol=1e-10)
    np.testing.assert_allclose(v, 0.0, atol=1e-12)


@pytest.mark.parametrize("flow", FLOWS[:1] + FLOWS[2:], ids=lambda e: e.TYPE)
def test_periodic_sum_matches_brute_force(flow):
    P = 3.0 + 4.0j
    z = np.array([1.1 + 0.4j, -0.7 + 1.9j, 2.0 - 1.0j])
    n = np.arange(-4000, 4001)
    brute = sum(flow.complex_velocity(z - k * P) for k in n)
    np.testing.assert_allclose(flow.periodic_complex_velocity(z, P), brute, rtol=2e-3, atol=2e-4)


def test_periodic_sum_is_stable_far_away():
    w = Source(m=1.0).periodic_complex_velocity(np.array([5000.0 + 0.3j, -5000.0 + 0.3j]), 4.0j)
    assert np.all(np.isfinite(w))


# ---------------------------------------------------------------- validation
def errors(els):
    return [s for s in check_scene(els) if s.is_error]


def test_valid_scene_has_no_errors():
    assert errors([W(yw=-1.0), Uniform(), Source(m=1.0), Vortex(Gamma=1.0, x0=1.0)]) == []


def test_element_behind_or_on_wall_is_an_error():
    e = errors([W(yw=-1.0), Source(m=1.0, y0=-2.0), Vortex(Gamma=1.0, y0=-1.0)])
    assert {s.index for s in e} == {1, 2}
    assert any("behind" in s.message for s in e) and any("on the wall" in s.message for s in e)


def test_uniform_flow_must_be_parallel_to_wall():
    assert errors([W(yw=-1.0, theta_w=0.0), Uniform(alpha=180.0)]) == []       # anti-parallel is fine
    assert errors([W(yw=-1.0, theta_w=0.0), Uniform(alpha=10.0)])
    assert errors([W(yw=0.0), W(theta_w=90.0, side=1), Uniform(alpha=0.0)])    # corner: no freestream


def test_walls_without_fluid_are_an_error():
    assert errors([W(yw=0.0, side=1), W(yw=2.0, side=0)])                       # facing away
    assert errors([W(yw=0.0, side=0), W(yw=2.0, side=0)])                       # parallel, not facing


def test_invalid_side_choice():
    assert not W(side=2).is_valid()
    assert W(side=1).is_valid()


# ---------------------------------------------------------------- field and streamlines
def test_field_is_masked_behind_wall():
    res = compute_field([W(yw=-0.5), Uniform(), Source(m=1.0, y0=0.5)], (-2, 2), (-2, 2), 41, 41)
    behind = res.grid.Y < -0.5
    assert np.all(np.isnan(res.u[behind]))
    assert np.all(np.isfinite(res.u[(res.grid.Y > -0.4) & ~res.mask]))


def test_streamlines_do_not_cross_the_wall():
    wall = W(xw=0.0, yw=-1.0, theta_w=15.0)
    els = [wall, Uniform(alpha=15.0), Vortex(Gamma=2.0, x0=0.0, y0=0.2), Source(m=1.0, x0=-1.5, y0=1.0)]
    s = trace_streamlines(els, (-4, 4), (-3, 3))
    assert s.lines
    pts = np.vstack(s.lines)
    assert np.min(wall.signed_distance(pts[:, 0] + 1j * pts[:, 1])) > -1e-9
