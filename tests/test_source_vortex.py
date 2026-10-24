"""Verification case 2: single source, sink and vortex (sign conventions, radial / circular streamlines)."""
import numpy as np
import pytest

from physics import Source, Vortex
from physics.diagnostics import circle_points, circulation_around_circle, flux_through_circle, polar_components

CENTER = 0.7 - 0.4j


@pytest.mark.parametrize("m", [2.0, -3.0])           # source and sink
@pytest.mark.parametrize("r", [0.1, 1.0, 5.0])
def test_source_sink_is_purely_radial(m, r):
    el = [Source(m=m, x0=CENTER.real, y0=CENTER.imag)]
    z, _ = circle_points(CENTER, r, 64)
    v_r, v_t = polar_components(el, z, CENTER)
    np.testing.assert_allclose(v_r, m / (2 * np.pi * r), rtol=1e-12)    # V_r = m / (2π r)
    np.testing.assert_allclose(v_t, 0.0, atol=1e-12)                    # V_θ = 0


def test_source_points_outward_sink_inward():
    z, _ = circle_points(CENTER, 1.0, 16)
    assert np.all(polar_components([Source(m=1.0, x0=0.7, y0=-0.4)], z, CENTER)[0] > 0)
    assert np.all(polar_components([Source(m=-1.0, x0=0.7, y0=-0.4)], z, CENTER)[0] < 0)


@pytest.mark.parametrize("m", [2.0, -3.0])
def test_source_flux_equals_m(m):
    el = [Source(m=m, x0=CENTER.real, y0=CENTER.imag)]
    assert flux_through_circle(el, CENTER, 1.3) == pytest.approx(m, rel=1e-12)
    # any circle that contains the source gives the same flux (mass conservation)
    assert flux_through_circle(el, CENTER + 0.5, 2.0) == pytest.approx(m, rel=1e-10)
    # a circle that does not contain it gives zero
    assert flux_through_circle(el, CENTER + 5.0, 1.0) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("gamma", [2.5, -1.5])
@pytest.mark.parametrize("r", [0.1, 1.0, 5.0])
def test_vortex_is_purely_circular(gamma, r):
    el = [Vortex(Gamma=gamma, x0=CENTER.real, y0=CENTER.imag)]
    z, _ = circle_points(CENTER, r, 64)
    v_r, v_t = polar_components(el, z, CENTER)
    np.testing.assert_allclose(v_r, 0.0, atol=1e-12)                        # V_r = 0
    np.testing.assert_allclose(v_t, gamma / (2 * np.pi * r), rtol=1e-12)    # V_θ = Γ / (2π r)


def test_vortex_sign_convention_ccw_positive():
    """Γ > 0 counter-clockwise: at a point to the right of the center the velocity points up (+y)."""
    from physics import velocity
    _, v = velocity([Vortex(Gamma=1.0)], 1.0, 0.0)
    assert v > 0
    _, v = velocity([Vortex(Gamma=-1.0)], 1.0, 0.0)
    assert v < 0


@pytest.mark.parametrize("gamma", [2.5, -1.5])
def test_vortex_circulation_equals_gamma(gamma):
    el = [Vortex(Gamma=gamma, x0=CENTER.real, y0=CENTER.imag)]
    assert circulation_around_circle(el, CENTER, 0.8) == pytest.approx(gamma, rel=1e-12)
    assert circulation_around_circle(el, CENTER - 0.3j, 2.0) == pytest.approx(gamma, rel=1e-10)
    # irrotational everywhere else: zero circulation around a contour not enclosing the vortex
    assert circulation_around_circle(el, CENTER + 4.0, 1.0) == pytest.approx(0.0, abs=1e-12)


def test_zero_strength_gives_warning_not_error():
    for el in (Source(m=0.0), Vortex(Gamma=0.0)):
        issues = el.check()
        assert el.is_valid()
        assert any(i.severity == "warning" for i in issues)
