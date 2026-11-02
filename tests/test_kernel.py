"""Compiled kernel (Numba): same velocity, fluid region and streamlines as the NumPy code."""
import os
import sys

import numpy as np
import pytest

from physics import (Doublet, FlowElement, SectorFlow, Source, SymmetryWall, Uniform, Vortex, complex_velocity,
                     kernel, resolve)
from physics.field import active, fluid_mask
from physics.streamlines import trace_streamlines

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
from streamline_quality import SCENES  # noqa: E402

pytestmark = pytest.mark.skipif(not kernel.HAVE_NUMBA, reason="Numba not installed")

EXTRA = {
    "sector 270°": ([SectorFlow(V=1.0, theta2=270.0)], ((-3, 3), (-3, 3))),
    "rotated wedge + source": ([SectorFlow(V=0.5, x0=1.0, y0=-0.5, theta1=20.0, theta2=110.0),
                                Source(m=1.0, x0=1.2, y0=0.8)], ((-2, 4), (-2, 3))),
    "doublet δ between walls": ([SymmetryWall(yw=-1.0), SymmetryWall(yw=1.5, side=1), Uniform(V=0.7),
                                 Doublet(mu=0.3, x0=0.5, y0=0.2, delta=35.0)], ((-4, 4), (-1.2, 1.7))),
    "60° corner, two walls": ([SymmetryWall(), SymmetryWall(theta_w=60.0, side=1),
                               Vortex(Gamma=2.0, x0=1.6, y0=0.6)], ((-1, 4), (-0.8, 3.2))),
}
ALL = {**SCENES, **EXTRA}


@pytest.mark.parametrize("name", ALL)
def test_velocity_and_fluid_region_match_numpy(name):
    els, ((x0, x1), (y0, y1)) = ALL[name]
    els = active(els)
    flows = resolve(els)
    F, R, _ = kernel.compile_scene(els, flows)
    rng = np.random.default_rng(1)
    z = rng.uniform(x0, x1, 3000) + 1j * rng.uniform(y0, y1, 3000)
    w_np, w_k = complex_velocity(flows, z), kernel.velocity_many(z, F)
    fin = np.isfinite(w_np)
    assert np.array_equal(fin, np.isfinite(w_k))
    np.testing.assert_allclose(w_k[fin], w_np[fin], rtol=1e-12, atol=1e-13 * np.abs(w_np[fin]).max())
    assert np.array_equal(kernel.fluid_many(z, R), fluid_mask(els, z))


@pytest.mark.parametrize("name", ALL)
def test_kernel_and_numpy_streamlines_agree(name):
    els, view = ALL[name]
    a = trace_streamlines(els, *view, use_kernel=False)
    b = trace_streamlines(els, *view)
    assert abs(len(a.lines) - len(b.lines)) <= 1
    same = sum(any(p.shape == q.shape and np.allclose(p, q, atol=1e-9) for q in a.lines) for p in b.lines)
    assert same >= 0.9 * len(b.lines)          # a line may stop one step earlier at a raster border


def test_element_without_kernel_form_uses_numpy():
    """A new element type without kernel_terms() still works (slower NumPy path)."""
    from dataclasses import dataclass

    @dataclass(kw_only=True)
    class Spiral(FlowElement):           # source + vortex in one element, no kernel description
        TYPE = "test_spiral"
        NAME = "Spiral"
        m: float = 1.0
        G: float = 1.0

        def complex_velocity(self, z):
            with np.errstate(divide="ignore", invalid="ignore"):
                return (self.m - 1j * self.G) / (2 * np.pi * np.asarray(z, complex))

        def complex_potential(self, z):
            with np.errstate(divide="ignore", invalid="ignore"):
                return (self.m - 1j * self.G) / (2 * np.pi) * np.log(np.asarray(z, complex))

        def singular_points(self):
            return [0j]

    els = [Spiral()]
    assert kernel.compile_scene(els, resolve(els)) is None
    s = trace_streamlines(els, (-3, 3), (-2, 2))
    assert len(s.lines) > 5


def test_kernel_releases_the_interpreter_lock():
    """nogil: the window thread keeps running while streamlines are computed."""
    assert kernel.trace_batch.targetoptions.get("nogil") is True
    assert kernel.velocity_many.targetoptions.get("nogil") is True


# ---------------------------------------------------------------- R2: compiled Jobard–Lefer bookkeeping
def _numpy_path(monkeypatch):
    """The same functions without Numba (the fallback of an installation without it)."""
    monkeypatch.setattr(kernel, "HAVE_NUMBA", False)


def test_compiled_rasters_equal_the_numpy_ones(monkeypatch):
    from physics.streamlines.rasters import _OwnerRaster, _Raster
    rng = np.random.default_rng(3)
    pts = rng.uniform(-1, 5, 400) + 1j * rng.uniform(-1, 4, 400)
    rasters = []
    for compiled in (True, False):
        monkeypatch.setattr(kernel, "HAVE_NUMBA", compiled)
        b, o = _Raster(0.0, 0.0, 4.0, 3.0, 0.07), _OwnerRaster(0.0, 0.0, 4.0, 3.0, 0.07)
        for k in range(0, 400, 40):                            # several lines, some overlapping
            b.stamp(pts[k:k + 40], 0.2)
            o.stamp(pts[k:k + 40], 0.12, k % 3)
        rasters.append((b.a.copy(), o.a.copy(), b.test(pts), o.test(pts, 1), o.test(pts)))
    for a, b in zip(*rasters):
        assert np.array_equal(a, b)


def test_compiled_neighbour_seeds_and_arrows_equal_the_numpy_ones(monkeypatch):
    from physics.streamlines.arrows import _place_arrows
    from physics.streamlines.seeds import _neighbour_seeds
    els, view = SCENES["lifting cylinder"]
    s = trace_streamlines(els, *view)
    seg = s.lines[3][:, 0] + 1j * s.lines[3][:, 1]
    a = _neighbour_seeds(seg, s.separation)
    arrows = _place_arrows(s.lines, s.tapers, s.separation, 1.0, (-3.5, -2.5, 7.0, 5.0))
    _numpy_path(monkeypatch)
    b = _neighbour_seeds(seg, s.separation)
    assert len(a) == len(b) > 10 and np.allclose(a, b, rtol=0, atol=1e-12)
    # arrows are (x, y, angle) tuples: compared as an array (pytest >= 9's approx() refuses nested lists)
    arrows_np = _place_arrows(s.lines, s.tapers, s.separation, 1.0, (-3.5, -2.5, 7.0, 5.0))
    assert len(arrows) == len(arrows_np) > 0
    assert np.allclose(np.asarray(arrows), np.asarray(arrows_np), rtol=1e-6, atol=1e-12)


def test_compiled_newton_finds_the_same_stagnation_points(monkeypatch):
    from physics.stagnation import find_stagnation_points
    els = [Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)]
    a = find_stagnation_points(els, (-4, 4, -3, 3))
    _numpy_path(monkeypatch)
    b = find_stagnation_points(els, (-4, 4, -3, 3))
    assert [p.kind for p in a] == [p.kind for p in b] and len(a) == 2
    assert all(abs(p.z - q.z) < 1e-9 for p, q in zip(a, b))


def test_compiled_and_numpy_streamlines_have_the_same_quality(monkeypatch):
    """Last-bit differences (e.g. how |z| is rounded) may tip a near tie, so the pictures need not be
    identical bit for bit; the number of lines and their spacing are the same."""
    els, view = SCENES["Rankine oval"]
    a = trace_streamlines(els, *view)
    _numpy_path(monkeypatch)
    b = trace_streamlines(els, *view)
    assert abs(len(a.lines) - len(b.lines)) <= 2 and a.separation == b.separation


def test_row_sums_match_numpy_cot():
    """kernel._cot_sums (copies of an image row, one exponential for all) = the sum of base.stable_cot."""
    from physics.base import stable_cot
    rng = np.random.default_rng(0)
    for _ in range(2000):
        u = complex(rng.uniform(-10, 10), rng.uniform(-30, 30) * rng.choice([1.0, 0.01]))
        s, count = float(rng.choice([0.0, rng.uniform(0.1, 8.0)])), int(rng.integers(0, 6))
        ct = stable_cot(u - 1j * np.arange(-count, count + 1) * s)
        s1, s2 = kernel._cot_sums(u, s, count)
        assert abs(s1 - ct.sum()) <= 1e-12 * max(1.0, abs(ct.sum()))
        assert abs(s2 - (1 + ct ** 2).sum()) <= 1e-12 * max(1.0, abs((1 + ct ** 2).sum()))


@pytest.mark.parametrize("name", ALL)
def test_potential_matches_numpy(name):
    """Field grids (φ lines, ψ) are summed by the kernel: the same F = φ + iψ, the same branches."""
    from physics.field import _group_sum
    els, ((x0, x1), (y0, y1)) = ALL[name]
    flows = resolve(active(els))
    rng = np.random.default_rng(2)
    z = rng.uniform(x0, x1, 2000) + 1j * rng.uniform(y0, y1, 2000)
    with np.errstate(all="ignore"):
        f_np = _group_sum(flows, z, "batch_complex_potential")
    f_k = kernel.potential_many(z, kernel.velocity_table(flows))
    fin = np.isfinite(f_np)
    assert np.array_equal(fin, np.isfinite(f_k))
    np.testing.assert_allclose(f_k[fin], f_np[fin], rtol=1e-12, atol=1e-12 * np.abs(f_np[fin]).max())
