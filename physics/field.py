"""
field.py — superposition of elements and evaluation on a grid.

The professor's requirement "superpose velocity components, not streamline
images" is implemented here: the complex velocities w_k of all enabled
elements are added,  w = Σ w_k,  and only then u = Re(w), v = −Im(w).

Symmetry walls: before summing, the element list is "resolved" (images.py):
every flow element gets its images in the walls, so the walls become streamlines.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

from . import parallel
from .base import FlowElement, as_complex_array
from .images import resolve


PARALLEL_MIN_POINTS = 20_000            # smaller arrays: one core (a thread costs more than it saves)


# ---------------------------------------------------------------------------
# Superposition
# ---------------------------------------------------------------------------
def active(elements: Iterable[FlowElement]) -> list[FlowElement]:
    """Enabled elements only (unticked ones are ignored)."""
    return [e for e in elements if e.enabled]


def complex_velocity(elements: Iterable[FlowElement], z) -> np.ndarray:
    """w(z) = Σ w_k(z) = u − i v   (sum over flow elements and their wall images).
    A large array of points (a field-layer grid) is split over the processor's cores (parallel.py): every
    point is computed exactly as on one core."""
    z = as_complex_array(z)
    flows = resolve(elements)
    return _on_cores(lambda part: _velocity_sum(flows, part), z)


def _velocity_sum(flows, z) -> np.ndarray:
    w = np.zeros(z.shape, dtype=np.complex128)
    for cls, group in flows.groups.items():
        w += cls.batch_complex_velocity(group, z)
    return w


def _on_cores(fn, z) -> np.ndarray:
    """fn(z) for an array of points, in pieces on several cores when it is large (results in the original
    order and shape; each point's value does not depend on the piece it is in)."""
    if z.size < PARALLEL_MIN_POINTS or parallel.workers() <= 1:
        return fn(z)
    flat = z.reshape(-1)
    parts = parallel.run([lambda a=a, b=b: fn(flat[a:b]) for a, b in parallel.chunks(flat.size, PARALLEL_MIN_POINTS // 2)])
    return np.concatenate(parts).reshape(z.shape)


def velocity(elements: Iterable[FlowElement], x, y) -> tuple[np.ndarray, np.ndarray]:
    """(u, v) at points (x, y)."""
    w = complex_velocity(elements, np.asarray(x, dtype=float) + 1j * np.asarray(y, dtype=float))
    return w.real, -w.imag


def complex_potential(elements: Iterable[FlowElement], z) -> np.ndarray:
    """F(z) = Σ F_k(z) = φ + i ψ  (ψ of sources and φ of vortices contain branch cuts)."""
    z = as_complex_array(z)
    flows = resolve(elements)

    def potential(part):
        F = np.zeros(part.shape, dtype=np.complex128)
        for e in flows:
            F += e.complex_potential(part)
        return F
    return _on_cores(potential, z)


# ---------------------------------------------------------------------------
# Pressure
# ---------------------------------------------------------------------------
def reference_speed(elements: Iterable[FlowElement]) -> float | None:
    """|V∞| from the uniform flow(s); None if there is no freestream (Cp undefined)."""
    total = 0j
    found = False
    for e in active(elements):
        fv = e.freestream_velocity()
        if fv is not None:
            total += fv
            found = True
    if not found or abs(total) == 0:
        return None
    return float(abs(total))


def pressure_coefficient(u, v, v_ref: float) -> np.ndarray:
    """Cp = 1 − (V / V∞)²   (steady Bernoulli, incompressible)."""
    return 1.0 - (np.asarray(u) ** 2 + np.asarray(v) ** 2) / v_ref ** 2


# ---------------------------------------------------------------------------
# Fluid region
# ---------------------------------------------------------------------------
def fluid_mask(elements: Iterable[FlowElement], z) -> np.ndarray:
    """True where fluid exists (intersection of every element's fluid_region)."""
    z = as_complex_array(z)
    fluid = np.ones(z.shape, dtype=bool)
    for e in active(elements):
        region = e.fluid_region(z)
        if region is not None:
            fluid &= region
    return fluid


# ---------------------------------------------------------------------------
# Singularities
# ---------------------------------------------------------------------------
def singular_points(elements: Iterable[FlowElement]) -> list[complex]:
    pts = []
    for e in active(elements):
        pts.extend(e.singular_points())
    return pts


def singularity_mask(elements: Iterable[FlowElement], z, radius: float) -> np.ndarray:
    """True where a point is closer than `radius` to any singular point (velocity not evaluated there)."""
    z = as_complex_array(z)
    mask = np.zeros(z.shape, dtype=bool)
    for p in singular_points(elements):
        mask |= np.abs(z - p) < radius
    return mask


def coincident_singularities(elements: Sequence[FlowElement], tol: float = 1e-9) -> list[tuple[int, int]]:
    """Index pairs (i, j) of enabled elements whose singular points coincide.

    Coincident singularities are allowed (e.g. doublet + vortex at the cylinder center);
    the GUI shows them as a warning so the user knows two elements share a point."""
    pairs = []
    for i, a in enumerate(elements):
        if not a.enabled:
            continue
        for j in range(i + 1, len(elements)):
            b = elements[j]
            if not b.enabled:
                continue
            if any(abs(p - q) < tol for p in a.singular_points() for q in b.singular_points()):
                pairs.append((i, j))
    return pairs


# ---------------------------------------------------------------------------
# Grid evaluation
# ---------------------------------------------------------------------------
@dataclass
class Grid:
    x: np.ndarray       # 1-D, length nx
    y: np.ndarray       # 1-D, length ny
    X: np.ndarray       # 2-D, shape (ny, nx)
    Y: np.ndarray

    @property
    def Z(self) -> np.ndarray:
        return self.X + 1j * self.Y

    @property
    def spacing(self) -> float:
        dx = self.x[1] - self.x[0] if len(self.x) > 1 else 1.0
        dy = self.y[1] - self.y[0] if len(self.y) > 1 else 1.0
        return float(max(abs(dx), abs(dy)))


def make_grid(xlim: tuple[float, float], ylim: tuple[float, float], nx: int = 200, ny: int = 150) -> Grid:
    x = np.linspace(xlim[0], xlim[1], nx)
    y = np.linspace(ylim[0], ylim[1], ny)
    X, Y = np.meshgrid(x, y)
    return Grid(x, y, X, Y)


@dataclass
class FieldResult:
    grid: Grid
    u: np.ndarray            # NaN where masked
    v: np.ndarray
    speed: np.ndarray
    cp: np.ndarray | None    # None when there is no reference speed
    mask: np.ndarray         # True = not part of the plotted flow (near a singularity / not fluid)
    v_ref: float | None


def compute_field(elements: Sequence[FlowElement], xlim, ylim, nx: int = 200, ny: int = 150,
                  mask_radius: float | None = None) -> FieldResult:
    """Velocity, speed and Cp on a regular grid. Points near singularities are set to NaN."""
    grid = make_grid(xlim, ylim, nx, ny)
    Z = grid.Z
    if mask_radius is None:
        mask_radius = 1.5 * grid.spacing
    mask = singularity_mask(elements, Z, mask_radius) | ~fluid_mask(elements, Z)

    w = complex_velocity(resolve(elements), Z)
    u, v = w.real.copy(), -w.imag
    mask |= ~np.isfinite(u) | ~np.isfinite(v)
    u[mask] = np.nan
    v[mask] = np.nan
    speed = np.hypot(u, v)

    v_ref = reference_speed(elements)
    cp = pressure_coefficient(u, v, v_ref) if v_ref else None
    return FieldResult(grid, u, v, speed, cp, mask, v_ref)
