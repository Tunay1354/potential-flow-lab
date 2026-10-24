"""Sector (wedge) flow: course notes item 7, its fluid region, and how it interacts with other elements."""
import numpy as np
import pytest

from physics import (Doublet, SectorFlow, Source, SymmetryWall, Uniform, Vortex, build_image_system,
                     check_scene, complex_potential, compute_field, velocity)
from physics.diagnostics import polar_components
from physics.streamlines import trace_streamlines

S = SectorFlow
BETAS = [30.0, 45.0, 60.0, 90.0, 120.0, 180.0, 225.0, 270.0, 360.0]


def inside_points(sec, n=60, r_min=0.2, r_max=3.0, seed=0):
    """Random points strictly inside the wedge."""
    rng = np.random.default_rng(seed)
    r = rng.uniform(r_min, r_max, n)
    th = np.radians(sec.theta1) + rng.uniform(0.02, 0.98, n) * sec.beta
    return sec.z0 + r * np.exp(1j * th), r, th - np.radians(sec.theta1)


def wall_points(sec, which, r=np.linspace(0.05, 4.0, 200)):
    ang = sec.theta1 if which == 1 else sec.theta1 + sec.beta_deg
    return sec.z0 + r * np.exp(1j * np.radians(ang))


# ---------------------------------------------------------------- formulas from the notes
@pytest.mark.parametrize("beta", BETAS)
def test_polar_velocity_components_from_notes(beta):
    """V_r = n V r^{n−1} cos(nθ'),  V_θ = −n V r^{n−1} sin(nθ'),  n = π/β."""
    sec = S(V=1.3, theta1=0.0, theta2=beta)
    z, r, th = inside_points(sec)
    n = 180.0 / beta
    vr, vt = polar_components([sec], z)
    np.testing.assert_allclose(vr, n * 1.3 * r ** (n - 1) * np.cos(n * th), rtol=1e-11, atol=1e-12)
    np.testing.assert_allclose(vt, -n * 1.3 * r ** (n - 1) * np.sin(n * th), rtol=1e-11, atol=1e-12)


def test_corner_flow_example_from_notes():
    """β = 90° (n = 2):  F = V z²,  u = 2Vx,  v = −2Vy."""
    rng = np.random.default_rng(1)
    x, y = rng.uniform(0.01, 3, 50), rng.uniform(0.01, 3, 50)
    u, v = velocity([S(V=0.7)], x, y)
    np.testing.assert_allclose(u, 2 * 0.7 * x, rtol=1e-12)
    np.testing.assert_allclose(v, -2 * 0.7 * y, rtol=1e-12)


def test_n_from_notes_examples():
    """α = 30° -> n = 6,  α = π/2 -> n = 2,  α = 2π -> n = 1/2 (course notes)."""
    assert S(theta2=30.0).n == pytest.approx(6.0)
    assert S(theta2=90.0).n == pytest.approx(2.0)
    assert S(theta1=0.0, theta2=360.0).n == pytest.approx(0.5)


def test_beta_180_is_uniform_flow_along_the_wall():
    sec = S(V=1.5, theta1=0.0, theta2=180.0)
    z, _, _ = inside_points(sec)
    u, v = velocity([sec], z.real, z.imag)
    np.testing.assert_allclose(u, 1.5, rtol=1e-12)
    np.testing.assert_allclose(v, 0.0, atol=1e-12)


def test_plate_tip_speed():
    """β = 360°, n = 1/2: |w| = (V/2) r^{−1/2}  (flow around the tip of a semi-infinite plate)."""
    sec = S(V=2.0, theta1=0.0, theta2=360.0)
    z, r, _ = inside_points(sec)
    u, v = velocity([sec], z.real, z.imag)
    np.testing.assert_allclose(np.hypot(u, v), 1.0 * r ** -0.5, rtol=1e-12)


# ---------------------------------------------------------------- walls are streamlines
@pytest.mark.parametrize("beta", BETAS)
@pytest.mark.parametrize("theta1", [0.0, 37.0, -120.0])
def test_both_walls_are_streamlines(beta, theta1):
    """ψ = 0 and V·n = 0 on both walls, for any orientation."""
    sec = S(V=1.0, x0=0.4, y0=-0.3, theta1=theta1, theta2=theta1 + beta)
    for which in (1, 2):
        z = wall_points(sec, which)
        psi = complex_potential([sec], z).imag
        scale = np.abs(complex_potential([sec], z)).max()
        assert np.max(np.abs(psi)) < 1e-12 * max(scale, 1.0)
        u, v = velocity([sec], z.real, z.imag)
        d = np.exp(1j * np.radians(theta1 if which == 1 else theta1 + beta))
        vn = ((u + 1j * v) * np.conj(1j * d)).real
        assert np.max(np.abs(vn)) < 1e-11 * max(np.max(np.hypot(u, v)), 1.0)


def test_direction_convention():
    """V > 0: fluid comes in along the θ2 wall and leaves along the θ1 wall; V < 0 reverses it."""
    for V, sign in [(1.0, 1), (-1.0, -1)]:
        sec = S(V=V, theta1=0.0, theta2=90.0)
        vr1, _ = polar_components([sec], wall_points(sec, 1), sec.z0)
        vr2, _ = polar_components([sec], wall_points(sec, 2), sec.z0)
        assert np.all(np.sign(vr1) == sign) and np.all(np.sign(vr2) == -sign)


def test_rotation_and_translation():
    """A rotated, shifted sector equals the standard one in local coordinates."""
    t1, beta, z0 = 35.0, 60.0, 1.2 - 0.7j
    sec = S(V=0.9, x0=z0.real, y0=z0.imag, theta1=t1, theta2=t1 + beta)
    ref = S(V=0.9, theta1=0.0, theta2=beta)
    zl, _, _ = inside_points(ref)
    rot = np.exp(1j * np.radians(t1))
    z = z0 + zl * rot
    u, v = velocity([sec], z.real, z.imag)
    u0, v0 = velocity([ref], zl.real, zl.imag)
    np.testing.assert_allclose(u + 1j * v, (u0 + 1j * v0) * rot, rtol=1e-12, atol=1e-13)


def test_angle_wrapping():
    """θ2 − θ1 is wrapped into (0°, 360°]: (300°, 30°) is the same 90° wedge as (−60°, 30°)."""
    a, b = S(theta1=300.0, theta2=30.0), S(theta1=-60.0, theta2=30.0)
    assert a.beta_deg == pytest.approx(90.0) and b.beta_deg == pytest.approx(90.0)
    z, _, _ = inside_points(b)
    np.testing.assert_allclose(velocity([a], z.real, z.imag), velocity([b], z.real, z.imag), rtol=1e-12)
    assert S(theta1=40.0, theta2=40.0).beta_deg == pytest.approx(360.0)
    assert S(theta1=0.0, theta2=-90.0).beta_deg == pytest.approx(270.0)


# ---------------------------------------------------------------- fluid region
@pytest.mark.parametrize("beta", [60.0, 180.0, 270.0])
def test_fluid_region_is_the_wedge(beta):
    sec = S(theta1=20.0, theta2=20.0 + beta)
    z, _, _ = inside_points(sec)
    assert np.all(sec.fluid_region(z)) and np.all(sec.signed_distance(z) > 0)
    outside = sec.z0 + 2.0 * np.exp(1j * np.radians(20.0 + beta + 0.5 * (360.0 - beta)))
    assert not sec.fluid_region(np.array([outside]))[0]
    assert sec.signed_distance(np.array([outside]))[0] < 0
    for which in (1, 2):
        np.testing.assert_allclose(sec.signed_distance(wall_points(sec, which)), 0.0, atol=1e-12)


def test_field_is_masked_outside_the_wedge():
    res = compute_field([S(theta1=0.0, theta2=90.0)], (-2, 2), (-2, 2), 41, 41)
    outside = (res.grid.X < -0.01) | (res.grid.Y < -0.01)
    assert np.all(np.isnan(res.u[outside]))
    assert np.all(np.isfinite(res.u[(res.grid.X > 0.01) & (res.grid.Y > 0.01)]))


def test_vertex_is_singular_only_for_beta_over_180():
    assert S(theta2=90.0).singular_points() == []          # stagnation point (velocity 0)
    assert S(theta2=180.0).singular_points() == []         # uniform flow
    assert S(theta2=270.0).singular_points() == [0j]       # velocity ~ r^{n−1} -> ∞
    u, v = velocity([S(theta2=90.0)], 0.0, 0.0)
    assert np.hypot(u, v) == 0.0


# ---------------------------------------------------------------- other elements in a wedge
def max_vn_on_walls(els, sec):
    worst = 0.0
    for which in (1, 2):
        z = wall_points(sec, which, np.linspace(0.05, 6.0, 400))
        u, v = velocity(els, z.real, z.imag)
        d = np.exp(1j * np.radians(sec.theta1 if which == 1 else sec.theta1 + sec.beta_deg))
        worst = max(worst, float(np.max(np.abs(((u + 1j * v) * np.conj(1j * d)).real))))
    return worst


@pytest.mark.parametrize("beta, k", [(90.0, 2), (60.0, 3), (45.0, 4), (180.0, 1)])
def test_elements_inside_wedge_get_exact_images(beta, k):
    """β = 180°/k: source, vortex and doublet inside the wedge get 2k − 1 images each; V·n = 0 on both walls."""
    t1 = 15.0
    sec = S(V=0.8, x0=0.5, y0=0.2, theta1=t1, theta2=t1 + beta)
    mid = sec.z0 + np.exp(1j * np.radians(t1 + beta / 2))
    others = [Source(m=1.0, x0=(mid * 1.0).real, y0=(mid * 1.0).imag),
              Vortex(Gamma=-0.7, x0=(sec.z0 + 2.0 * (mid - sec.z0)).real, y0=(sec.z0 + 2.0 * (mid - sec.z0)).imag),
              Doublet(mu=0.3, x0=(sec.z0 + 3.0 * (mid - sec.z0)).real, y0=(sec.z0 + 3.0 * (mid - sec.z0)).imag,
                      delta=40.0)]
    els = [sec] + others
    assert not [s for s in check_scene(els) if s.is_error]
    system = build_image_system(els)
    assert system.exact and system.n_images == len(others) * (2 * k - 1)
    assert max_vn_on_walls(els, sec) < 1e-11


def test_uniform_flow_allowed_only_parallel_in_a_180_degree_sector():
    sec = S(V=1.0, theta1=0.0, theta2=180.0)
    assert not [s for s in check_scene([sec, Uniform(V=0.5, alpha=180.0)]) if s.is_error]
    assert [s for s in check_scene([sec, Uniform(V=0.5, alpha=30.0)]) if s.is_error]
    assert [s for s in check_scene([S(theta2=90.0), Uniform()]) if s.is_error]


@pytest.mark.parametrize("els, words", [
    ([S(theta2=70.0), Source(m=1.0, x0=1.0, y0=0.5)], "180°/k"),                  # β is not 180°/k
    ([S(theta2=270.0), Source(m=1.0, x0=-1.0, y0=1.0)], "β = 270° > 180°"),      # β > 180°
    ([S(), S(x0=3.0)], "Only one sector"),                                         # two sectors
    ([S(), SymmetryWall(yw=-1.0)], "cannot be combined"),                          # sector + wall
    ([S(), Source(m=1.0, x0=-1.0, y0=1.0)], "outside the wedge"),                  # outside the wedge
    ([S(), Vortex(Gamma=1.0, x0=2.0, y0=0.0)], "lies on a wall"),                  # on a wall
])
def test_invalid_combinations_are_errors(els, words):
    msgs = [s.message for s in check_scene(els) if s.is_error]
    assert any(words in m for m in msgs), msgs


def test_sector_alone_any_beta_is_valid():
    for beta in BETAS:
        assert not [s for s in check_scene([S(theta2=beta)]) if s.is_error]


# ---------------------------------------------------------------- streamlines
@pytest.mark.parametrize("beta", [45.0, 90.0, 270.0, 360.0])
def test_streamlines_stay_in_the_wedge_and_follow_psi(beta):
    sec = S(V=1.0, x0=0.3, y0=-0.2, theta1=10.0, theta2=10.0 + beta)
    s = trace_streamlines([sec], (-3, 3), (-3, 3))
    assert len(s.lines) > 5
    for ln in s.lines:
        z = ln[:, 0] + 1j * ln[:, 1]
        assert np.all(sec.signed_distance(z) > -1e-9)                     # never outside the wedge
        th = sec.local_angle(z)
        assert np.all(np.abs(np.diff(th)) < np.pi)                         # never jumps across a plate
        psi = complex_potential([sec], z).imag
        assert np.ptp(psi) < 3e-3 * (1.0 + np.abs(psi).max())             # ψ = const along each line


def test_corner_streamlines_are_hyperbolas():
    """β = 90°: ψ = 2Vxy, so every streamline is a hyperbola x·y = const."""
    s = trace_streamlines([S(V=1.0)], (-0.5, 3), (-0.5, 3))
    for ln in s.lines:
        xy = ln[:, 0] * ln[:, 1]
        assert np.ptp(xy) < 2e-3 * (1.0 + xy.max())


def test_sector_with_source_streamlines_stay_inside():
    sec = S(V=1.0)
    els = [sec, Source(m=1.0, x0=1.0, y0=1.0)]
    s = trace_streamlines(els, (-0.5, 4), (-0.5, 4))
    pts = np.vstack(s.lines)
    assert np.min(sec.signed_distance(pts[:, 0] + 1j * pts[:, 1])) > -1e-9


def test_plate_crossing_is_detected():
    """β = 360°: a step from just above to just below the plate crosses it; steps in the fluid do not.
    (The tracer also stops on the direction reversal at the plate; this is the second safeguard.)"""
    sec = S(theta1=0.0, theta2=360.0)
    za = np.array([1.0 + 0.01j, 1.0 + 0.5j, -1.0 + 0.01j, 1.0 + 0.3j])
    zb = np.array([1.0 - 0.01j, 1.2 + 0.6j, -1.0 - 0.01j, 0.9 + 0.2j])
    np.testing.assert_array_equal(sec.crosses_boundary(za, zb), [True, False, False, False])
    # crossing the ray x < 0 is not crossing the plate (the plate is only x > 0)


def test_sector_images_agree_with_two_walls():
    """Sector β = 90° + source  ==  (source in a 90° corner of two symmetry walls) + (sector flow alone):
    the wedge sides give exactly the same images as two real walls."""
    sec = S(V=0.8, theta1=0.0, theta2=90.0)
    src = Source(m=1.3, x0=1.0, y0=0.6)
    corner = [SymmetryWall(xw=0.0, yw=0.0, theta_w=0.0, side=0),
              SymmetryWall(xw=0.0, yw=0.0, theta_w=90.0, side=1), src]
    z, _, _ = inside_points(sec, seed=4)
    u1, v1 = velocity([sec, src], z.real, z.imag)
    u2, v2 = velocity(corner, z.real, z.imag)
    u3, v3 = velocity([sec], z.real, z.imag)
    np.testing.assert_allclose(u1 + 1j * v1, (u2 + u3) + 1j * (v2 + v3), rtol=1e-12, atol=1e-12)
