"""Superposition, masking and helper behaviour of field.py."""
import numpy as np

from physics import (Doublet, Source, Uniform, Vortex, coincident_singularities, compute_field,
                     reference_speed, velocity)

RNG = np.random.default_rng(3)
X, Y = RNG.uniform(-3, 3, 40), RNG.uniform(-3, 3, 40)


def test_superposition_is_sum_of_velocities():
    a, b, c = Uniform(V=1.0, alpha=10.0), Source(m=2.0, x0=1.0, y0=0.5), Vortex(Gamma=-1.0, x0=-1.0)
    u, v = velocity([a, b, c], X, Y)
    parts = [velocity([e], X, Y) for e in (a, b, c)]
    np.testing.assert_allclose(u, sum(p[0] for p in parts), rtol=1e-13)
    np.testing.assert_allclose(v, sum(p[1] for p in parts), rtol=1e-13)


def test_disabled_element_is_ignored():
    u1, v1 = velocity([Uniform(V=1.0), Source(m=5.0, enabled=False)], X, Y)
    np.testing.assert_allclose(u1, 1.0)
    np.testing.assert_allclose(v1, 0.0, atol=1e-15)


def test_no_elements_gives_zero_velocity():
    u, v = velocity([], X, Y)
    assert np.all(u == 0) and np.all(v == 0)


def test_singularities_are_masked_not_evaluated():
    res = compute_field([Uniform(), Source(m=1.0)], (-1, 1), (-1, 1), 41, 41, mask_radius=0.2)
    near = np.abs(res.grid.Z) < 0.2
    assert near.any()
    assert np.all(np.isnan(res.u[near])) and np.all(res.mask[near])
    assert np.all(np.isfinite(res.u[~near]))


def test_reference_speed_and_cp():
    assert reference_speed([Source(m=1.0)]) is None
    assert compute_field([Source(m=1.0)], (-1, 1), (-1, 1), 5, 5).cp is None
    assert reference_speed([Uniform(V=2.0), Uniform(V=2.0, alpha=90)]) == np.hypot(2, 2)


def test_coincident_singularities_are_reported():
    els = [Uniform(), Doublet(mu=1.0), Vortex(Gamma=1.0), Source(m=1.0, x0=2.0)]
    assert coincident_singularities(els) == [(1, 2)]
    els[2].enabled = False
    assert coincident_singularities(els) == []


def test_grid_shapes():
    res = compute_field([Uniform()], (-2, 2), (-1, 1), 30, 20)
    assert res.u.shape == (20, 30) and res.grid.X.shape == (20, 30)
