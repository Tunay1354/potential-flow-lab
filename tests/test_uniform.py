"""Verification case 1: uniform flow at α = 0° and 45° (velocity direction and streamline orientation)."""
import numpy as np
import pytest

from physics import Uniform, complex_potential, velocity

RNG = np.random.default_rng(0)
X, Y = RNG.uniform(-5, 5, 50), RNG.uniform(-5, 5, 50)


@pytest.mark.parametrize("alpha", [0.0, 45.0, 90.0, -30.0])
def test_velocity_components(alpha):
    V = 2.0
    u, v = velocity([Uniform(V=V, alpha=alpha)], X, Y)
    a = np.radians(alpha)
    np.testing.assert_allclose(u, V * np.cos(a), atol=1e-14)
    np.testing.assert_allclose(v, V * np.sin(a), atol=1e-14)


def test_alpha_45_has_equal_components():
    u, v = velocity([Uniform(V=1.0, alpha=45.0)], X, Y)
    np.testing.assert_allclose(u, 1 / np.sqrt(2), atol=1e-14)
    np.testing.assert_allclose(v, 1 / np.sqrt(2), atol=1e-14)


@pytest.mark.parametrize("alpha", [0.0, 45.0])
def test_streamlines_are_straight_lines_along_alpha(alpha):
    """ψ is constant along the flow direction -> streamlines are lines with slope tan α."""
    el = [Uniform(V=1.5, alpha=alpha)]
    z0 = X + 1j * Y
    step = 3.0 * np.exp(1j * np.radians(alpha))
    psi_a = complex_potential(el, z0).imag
    psi_b = complex_potential(el, z0 + step).imag
    np.testing.assert_allclose(psi_a, psi_b, atol=1e-12)


def test_negative_speed_is_rejected():
    assert not Uniform(V=-1.0).is_valid()
