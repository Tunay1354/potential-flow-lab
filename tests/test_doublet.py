"""Doublet: F = μ e^{iδ} / (z − z0), with μ = m ε / π (course notes)."""
import numpy as np
import pytest

from physics import Doublet, Source, complex_potential, velocity

RNG = np.random.default_rng(1)
R = RNG.uniform(1.0, 4.0, 40)
TH = RNG.uniform(0, 2 * np.pi, 40)
X, Y = R * np.cos(TH), R * np.sin(TH)


def test_limit_of_source_sink_pair():
    """Source m at −ε and sink −m at +ε approaches the doublet μ = m ε / π as ε -> 0."""
    mu = 1.3
    for eps, tol in [(1e-2, 1e-3), (1e-3, 1e-5)]:
        m = np.pi * mu / eps
        pair = [Source(m=m, x0=-eps), Source(m=-m, x0=+eps)]
        u1, v1 = velocity(pair, X, Y)
        u2, v2 = velocity([Doublet(mu=mu)], X, Y)
        np.testing.assert_allclose(u1, u2, rtol=tol, atol=tol)
        np.testing.assert_allclose(v1, v2, rtol=tol, atol=tol)


def test_polar_velocity_components_from_notes():
    """V_r = −(μ / r²) cos θ,  V_θ = −(μ / r²) sin θ."""
    from physics.diagnostics import polar_components
    mu = 0.9
    vr, vt = polar_components([Doublet(mu=mu)], X + 1j * Y)
    np.testing.assert_allclose(vr, -mu / R**2 * np.cos(TH), rtol=1e-12, atol=1e-14)
    np.testing.assert_allclose(vt, -mu / R**2 * np.sin(TH), rtol=1e-12, atol=1e-14)


def test_streamlines_are_circles_tangent_to_x_axis():
    """ψ = ψ0 is a circle with center (0, −μ/(2ψ0)) and radius |μ/(2ψ0)|."""
    mu, psi0 = 1.0, -0.4
    c, rad = -mu / (2 * psi0), abs(mu / (2 * psi0))
    t = np.linspace(0.1, 2 * np.pi - 0.1, 50)          # avoid the origin itself
    z = 1j * c + rad * np.exp(1j * t)
    np.testing.assert_allclose(complex_potential([Doublet(mu=mu)], z).imag, psi0, rtol=1e-12)


@pytest.mark.parametrize("delta", [30.0, 90.0, -135.0])
def test_orientation_rotates_the_field(delta):
    """(u + iv)_δ(z) = e^{iδ} (u + iv)_0(z e^{−iδ})."""
    d = np.radians(delta)
    z = X + 1j * Y
    u1, v1 = velocity([Doublet(mu=1.0, delta=delta)], X, Y)
    zr = z * np.exp(-1j * d)
    u0, v0 = velocity([Doublet(mu=1.0)], zr.real, zr.imag)
    rot = (u0 + 1j * v0) * np.exp(1j * d)
    np.testing.assert_allclose(u1, rot.real, atol=1e-12)
    np.testing.assert_allclose(v1, rot.imag, atol=1e-12)
