"""Verification case 3: uniform flow + doublet = flow over a circular cylinder (course notes),
optional vortex adds circulation (lifting cylinder). Also Kutta–Joukowski and d'Alembert."""
import numpy as np
import pytest

from physics import Doublet, Uniform, Vortex, complex_potential, compute_field, velocity
from physics.diagnostics import circle_points, polar_components, surface_forces

V, A = 1.3, 0.8
MU = V * A**2                          # a = √(μ / V∞)  ->  μ = V∞ a²
THETA = np.linspace(0, 2 * np.pi, 361)
SURF = A * np.exp(1j * THETA)


def cylinder(gamma_cw=0.0):
    els = [Uniform(V=V), Doublet(mu=MU)]
    if gamma_cw:
        els.append(Vortex(Gamma=-gamma_cw))     # clockwise circulation = negative Γ in the program
    return els


def test_surface_is_a_streamline():
    """ψ = 0 on r = a  and  V_r = 0 there (impermeable body)."""
    np.testing.assert_allclose(complex_potential(cylinder(), SURF).imag, 0.0, atol=1e-13)
    v_r, _ = polar_components(cylinder(), SURF)
    np.testing.assert_allclose(v_r, 0.0, atol=1e-13)


def test_surface_velocity_and_cp():
    """V_θ = −2 V∞ sin θ,  Cp = 1 − 4 sin² θ."""
    _, v_t = polar_components(cylinder(), SURF)
    np.testing.assert_allclose(v_t, -2 * V * np.sin(THETA), atol=1e-13)
    u, v = velocity(cylinder(), SURF.real, SURF.imag)
    cp = 1 - (u**2 + v**2) / V**2
    np.testing.assert_allclose(cp, 1 - 4 * np.sin(THETA) ** 2, atol=1e-12)


def test_stagnation_points_and_maximum_speed():
    u, v = velocity(cylinder(), [A, -A, 0.0, 0.0], [0.0, 0.0, A, -A])
    speed = np.hypot(u, v)
    np.testing.assert_allclose(speed[:2], 0.0, atol=1e-13)          # θ = 0, π
    np.testing.assert_allclose(speed[2:], 2 * V, rtol=1e-13)        # θ = ±90°: 2 V∞, Cp = −3


def test_far_field_returns_to_freestream():
    z, _ = circle_points(0j, 1000 * A, 64)
    u, v = velocity(cylinder(gamma_cw=1.0), z.real, z.imag)
    np.testing.assert_allclose(u, V, rtol=1e-3)
    np.testing.assert_allclose(v, 0.0, atol=1e-3)


def test_dalembert_no_lift_no_drag():
    lift, drag = surface_forces(cylinder(), 0j, A, rho=1.225)
    assert lift == pytest.approx(0.0, abs=1e-10)
    assert drag == pytest.approx(0.0, abs=1e-10)


@pytest.mark.parametrize("gamma_cw", [1.0, 2.5, 4 * np.pi * V * A])   # last one: single stagnation point
def test_lifting_cylinder_surface_velocity_and_stagnation(gamma_cw):
    """V_θ = −[2 V∞ sin θ + Γ/(2π a)],  stagnation at sin θ = −Γ / (4π V∞ a)."""
    els = cylinder(gamma_cw)
    _, v_t = polar_components(els, SURF)
    np.testing.assert_allclose(v_t, -(2 * V * np.sin(THETA) + gamma_cw / (2 * np.pi * A)), atol=1e-12)
    s = -gamma_cw / (4 * np.pi * V * A)
    for th in (np.arcsin(s), np.pi - np.arcsin(s)):
        u, v = velocity(els, A * np.cos(th), A * np.sin(th))
        assert np.hypot(u, v) == pytest.approx(0.0, abs=1e-12)
        assert A * np.sin(th) <= 1e-12                               # on the lower half


@pytest.mark.parametrize("gamma_cw", [1.0, 2.5])
def test_kutta_joukowski(gamma_cw):
    """Pressure integration gives L′ = ρ V∞ Γ_cw (clockwise circulation) and D′ = 0."""
    rho = 1.225
    lift, drag = surface_forces(cylinder(gamma_cw), 0j, A, rho=rho)
    assert lift == pytest.approx(rho * V * gamma_cw, rel=1e-10)
    assert drag == pytest.approx(0.0, abs=1e-10)


def test_rotated_freestream_cylinder():
    """Uniform flow at α with doublet δ = α still gives a cylinder of radius a."""
    alpha = 35.0
    els = [Uniform(V=V, alpha=alpha), Doublet(mu=MU, delta=alpha)]
    v_r, _ = polar_components(els, SURF)
    np.testing.assert_allclose(v_r, 0.0, atol=1e-13)


def test_grid_cp_matches_analytic_outside_body():
    res = compute_field(cylinder(), (-3, 3), (-2, 2), 61, 41)
    R = np.abs(res.grid.Z)
    th = np.angle(res.grid.Z)
    outside = (R > A) & ~res.mask
    with np.errstate(divide="ignore", invalid="ignore"):     # R = 0 at the grid center
        vr = V * np.cos(th) * (1 - A**2 / R**2)
        vt = -V * np.sin(th) * (1 + A**2 / R**2)
    cp_exact = 1 - (vr**2 + vt**2) / V**2
    np.testing.assert_allclose(res.cp[outside], cp_exact[outside], atol=1e-12)
