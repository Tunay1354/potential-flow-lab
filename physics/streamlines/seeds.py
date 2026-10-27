"""
seeds.py — where new streamlines start: d away from a line (neighbour seeds), on the inflow border,
around singular points and along walls (priority seeds), on a grid.
"""
from __future__ import annotations

import math

import numpy as np

from .. import kernel
from ..field import complex_velocity, fluid_mask
from .common import _c128


# ---------------------------------------------------------------------- seeds
def _neighbour_seeds(seg: np.ndarray, d: float) -> list[complex]:
    """Points at distance d on both sides of a line, every d along it (alternating sides)."""
    if kernel.HAVE_NUMBA:
        return kernel.neighbour_seeds(_c128(seg), float(d)).tolist()
    ds = np.abs(np.diff(seg))
    s = np.concatenate([[0.0], np.cumsum(ds)])
    if s[-1] <= 0:
        return []
    out = []
    for target in np.arange(0.5 * d, s[-1], d):
        k = int(np.clip(np.searchsorted(s, target), 1, seg.size - 1))
        t = seg[k] - seg[k - 1]
        if abs(t) == 0:
            continue
        nrm = 1j * t / abs(t)
        out.append(seg[k] + d * nrm)
        out.append(seg[k] - d * nrm)
    return out


def _priority_seeds(els, x0, x1, y0, y1, d, sing, r_sing) -> np.ndarray:
    """Seeds used when no neighbour seed is left, in this order:
    1. small rings around singular points (closed circles around a vortex, lines out of a source),
    2. points d away from walls and wedge sides (lines that follow the wall)."""
    ring = []
    inside = sing[(sing.real > x0) & (sing.real < x1) & (sing.imag > y0) & (sing.imag < y1)] if sing.size else sing
    for p in inside:
        ring.append(p + 1.5 * r_sing * np.exp(2j * np.pi * np.arange(8) / 8))

    wall_seeds = []
    for e in els:
        for origin, direc, normal, ray in _boundary_lines(e):
            t_lo, t_hi = _line_range(origin, direc, x0, x1, y0, y1, ray)
            if t_hi <= t_lo:
                continue
            t = np.arange(t_lo + d, t_hi, 2.0 * d)
            if t.size:
                wall_seeds.append(origin + t * direc + d * normal)

    parts = ring + wall_seeds
    return np.concatenate(parts) if parts else np.zeros(0, complex)


def _inflow_seeds(els, flows, x0, x1, y0, y1, d) -> np.ndarray:
    """Seeds along the part of the view border where the flow ENTERS the view, spaced so that the
    lines start exactly d apart (measured across the flow). Each inflow stretch is anchored at its
    middle, so symmetric scenes give symmetric pictures. Returned middle-first, strongest stretch
    first (earlier seeds win when lines of the same batch come too close)."""
    inset = 0.3 * d
    corners = [complex(x0 + inset, y0 + inset), complex(x1 - inset, y0 + inset),
               complex(x1 - inset, y1 - inset), complex(x0 + inset, y1 - inset)]
    step = d / 8.0
    pts, nrm = [], []
    for k in range(4):                                   # counter-clockwise around the view
        a, b = corners[k], corners[(k + 1) % 4]
        L = abs(b - a)
        if L <= 0:
            continue
        n = max(2, int(math.ceil(L / step)))
        pts.append(a + (np.arange(n) / n) * (b - a))
        nrm.append(np.full(n, 1j * (b - a) / L))         # left of the direction = into the view
    if not pts:
        return np.zeros(0, complex)
    P, N = np.concatenate(pts), np.concatenate(nrm)
    M = 0.5 * (P + np.roll(P, -1))                      # middle of the border piece P[i] -> P[i+1]
    with np.errstate(all="ignore"):
        vel = np.conj(complex_velocity(flows, P))
        cos_in = (vel * np.conj(N)).real / np.abs(vel)
        vel_m = np.conj(complex_velocity(flows, M))
        cos_m = (vel_m * np.conj(N)).real / np.abs(vel_m)  # N[i] is the normal of piece i (also at corners)
    cos_m = np.where(np.isfinite(cos_m), np.maximum(cos_m, 0.0), 0.0)
    ok = np.isfinite(cos_in) & (cos_in > 0.05) & fluid_mask(els, P)
    if not ok.any():
        return np.zeros(0, complex)
    if not ok.all():                                     # start the walk at a point without inflow
        r = int(np.argmax(~ok))
        P, cos_m, ok = np.roll(P, -r), np.roll(cos_m, -r), np.roll(ok, -r)
    edges = np.diff(np.concatenate([[0], ok.astype(int), [0]]))
    starts, ends = np.nonzero(edges == 1)[0], np.nonzero(edges == -1)[0]
    runs = []
    for i0, i1 in zip(starts, ends):
        seg, c = P[i0:i1], cos_m[i0:i1 - 1]
        if seg.size < 2:
            continue
        ds = np.abs(np.diff(seg))
        C = np.concatenate([[0.0], np.cumsum(c * ds)])   # distance across the flow (midpoint rule)
        total = C[-1]
        if total < 0.6 * d:
            continue
        mid = 0.5 * total
        k = np.arange(-math.floor(mid / d), math.floor(mid / d) + 1)
        levels = mid + k * d
        levels = levels[(levels >= 0.3 * d) & (levels <= total - 0.3 * d)]
        levels = levels[np.argsort(np.abs(levels - mid), kind="stable")]
        idx = np.arange(seg.size)
        f = np.interp(levels, C, idx)
        i = np.clip(np.floor(f).astype(int), 0, seg.size - 2)
        z = seg[i] + (f - i) * (seg[i + 1] - seg[i])
        runs.append((total, z))
    runs.sort(key=lambda r: -r[0])
    return np.concatenate([z for _, z in runs]) if runs else np.zeros(0, complex)


def _boundary_lines(e):
    """Straight boundaries of an element as (origin, unit direction, unit normal into the fluid, is_ray)."""
    if e.IS_BOUNDARY and hasattr(e, "normal"):
        return [(e.point, e.direction, e.normal, False)]
    if e.TYPE == "sector":
        a1, a2 = math.radians(e.theta1), math.radians(e.theta1 + e.beta_deg)
        d1, d2 = complex(math.cos(a1), math.sin(a1)), complex(math.cos(a2), math.sin(a2))
        return [(e.z0, d1, 1j * d1, True), (e.z0, d2, -1j * d2, True)]
    return []


def _line_range(origin, direc, x0, x1, y0, y1, ray):
    t0, t1 = (0.0 if ray else -np.inf), np.inf
    for pc, dc, lo, hi in ((origin.real, direc.real, x0, x1), (origin.imag, direc.imag, y0, y1)):
        if abs(dc) < 1e-15:
            if pc < lo or pc > hi:
                return 0.0, -1.0
            continue
        a, b = (lo - pc) / dc, (hi - pc) / dc
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
    return t0, t1


def _grid_seeds(x0, x1, y0, y1, d, center: complex | None = None) -> np.ndarray:
    """Regular grid (spacing d), ordered from `center` (default: the middle) outwards."""
    cx = np.arange(x0 + 0.5 * d, x1, d)
    cy = np.arange(y0 + 0.5 * d, y1, d)
    CX, CY = np.meshgrid(cx, cy)
    g = (CX + 1j * CY).ravel()
    c = complex(0.5 * (x0 + x1), 0.5 * (y0 + y1)) if center is None else center
    return g[np.argsort(np.abs(g - c), kind="stable")]
