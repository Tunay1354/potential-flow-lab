"""
Checks that run automatically for EVERY registered element type (also future ones):
  * w = dF/dz                         (velocity and potential formulas agree)
  * ∇·V = 0 and ∇×V = 0               (incompressible and irrotational = potential flow)
  * save/load round trip
"""
import numpy as np
import pytest

from physics import ELEMENT_TYPES, element_from_dict, velocity

TYPES = sorted(ELEMENT_TYPES)


def make(type_key):
    """An element with non-trivial parameters, placed off the origin."""
    cls = ELEMENT_TYPES[type_key]
    el = cls.with_defaults()
    for p in cls.PARAMS:
        if p.key == "x0":
            setattr(el, p.key, 0.3)
        elif p.key == "y0":
            setattr(el, p.key, -0.2)
        elif p.is_angle:
            setattr(el, p.key, 25.0)
        elif p.default != 0:
            setattr(el, p.key, 1.7 * p.default)
    return el


# test points above the element (away from the singular point and the log branch cut)
RNG = np.random.default_rng(2)
PX, PY = RNG.uniform(-2, 2, 30), RNG.uniform(0.8, 3.0, 30)


@pytest.mark.parametrize("type_key", TYPES)
def test_velocity_is_derivative_of_potential(type_key):
    el = make(type_key)
    z = PX + 1j * PY
    h = 1e-6
    dF = (el.complex_potential(z + h) - el.complex_potential(z - h)) / (2 * h)
    np.testing.assert_allclose(dF, el.complex_velocity(z), rtol=1e-6, atol=1e-8)


@pytest.mark.parametrize("type_key", TYPES)
def test_divergence_and_curl_are_zero(type_key):
    el = [make(type_key)]
    h = 1e-5
    u_xp, v_xp = velocity(el, PX + h, PY)
    u_xm, v_xm = velocity(el, PX - h, PY)
    u_yp, v_yp = velocity(el, PX, PY + h)
    u_ym, v_ym = velocity(el, PX, PY - h)
    div = (u_xp - u_xm) / (2 * h) + (v_yp - v_ym) / (2 * h)
    curl = (v_xp - v_xm) / (2 * h) - (u_yp - u_ym) / (2 * h)
    np.testing.assert_allclose(div, 0.0, atol=1e-6)
    np.testing.assert_allclose(curl, 0.0, atol=1e-6)


@pytest.mark.parametrize("type_key", TYPES)
def test_save_load_round_trip(type_key):
    el = make(type_key)
    el.enabled = False
    copy = element_from_dict(el.to_dict())
    assert copy == el
    assert copy is not el


@pytest.mark.parametrize("type_key", TYPES)
def test_defaults_are_valid(type_key):
    assert ELEMENT_TYPES[type_key].with_defaults().is_valid()


@pytest.mark.parametrize("type_key", TYPES)
def test_non_finite_parameter_is_rejected(type_key):
    el = make(type_key)
    setattr(el, ELEMENT_TYPES[type_key].PARAMS[0].key, float("nan"))
    assert not el.is_valid()


def test_unknown_type_raises():
    with pytest.raises(ValueError):
        element_from_dict({"type": "black_hole"})
