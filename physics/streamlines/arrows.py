"""
arrows.py — direction arrows along the streamlines, evenly spread.
"""
from __future__ import annotations

import math

import numpy as np

from .. import kernel
from .common import ARROW_SPACING_RATIO, TAPER_RATIO


# ---------------------------------------------------------------------- arrows
def _place_arrows(lines: list[np.ndarray], tapers: list[tuple[bool, bool]], d: float,
                  arrow_density: float, box) -> list[tuple[float, float, float]]:
    """Direction arrows spread evenly over the PICTURE (not a fixed number per line).
    A hexagonal lattice of spacing ARROW_SPACING_RATIO·d / arrow_density is fixed to the plot
    coordinates; every lattice point is moved to the nearest point of a streamline and becomes an
    arrow (pointing in the flow direction). Rows of the lattice are shifted by half a spacing, so
    the arrows are staggered, and because the lattice does not move with the view, arrows stay in
    place while panning. Fading ends and the first / last half d of a line get no arrow."""
    if arrow_density <= 0 or not lines:
        return []
    R = ARROW_SPACING_RATIO * d / arrow_density
    pts, tan = [], []
    for xy, (cut0, cut1) in zip(lines, tapers):
        seg = xy[:, 0] + 1j * xy[:, 1]
        s = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(seg)))])
        lo = TAPER_RATIO * d if cut0 else 0.5 * d
        hi = s[-1] - (TAPER_RATIO * d if cut1 else 0.5 * d)
        if hi <= lo:
            continue
        targets = np.arange(lo, hi, d / 4.0)
        k = np.clip(np.searchsorted(s, targets), 1, seg.size - 1)
        ds = np.maximum(s[k] - s[k - 1], 1e-300)
        f = np.clip((targets - s[k - 1]) / ds, 0.0, 1.0)
        pts.append(seg[k - 1] + f * (seg[k] - seg[k - 1]))
        tan.append(seg[k] - seg[k - 1])
    if not pts:
        return []
    P, T = np.concatenate(pts), np.concatenate(tan)

    bx, by, bw, bh = box
    ry = R * math.sqrt(3.0) / 2.0
    lattice = []
    for j in range(math.floor(by / ry), math.ceil((by + bh) / ry) + 1):
        shift = 0.5 * R if j % 2 else 0.0
        i = np.arange(math.floor((bx - shift) / R), math.ceil((bx + bw - shift) / R) + 1)
        lattice.append(i * R + shift + 1j * j * ry)
    L = np.concatenate(lattice)
    L = L[(L.real >= bx) & (L.real <= bx + bw) & (L.imag >= by) & (L.imag <= by + bh)]

    # nearest line point of every lattice point: look only in the 3 × 3 cells (size d) around it
    near = (P.real > bx - d) & (P.real < bx + bw + d) & (P.imag > by - d) & (P.imag < by + bh + d)
    P, T = P[near], T[near]
    if P.size == 0 or L.size == 0:
        return []
    kx = np.floor((P.real - bx) / d).astype(np.int64) + 2
    ky = np.floor((P.imag - by) / d).astype(np.int64) + 2
    ny_cells = int(ky.max()) + 3
    key = kx * ny_cells + ky
    order = np.argsort(key, kind="stable")
    skey = key[order]
    lx = np.floor((L.real - bx) / d).astype(np.int64) + 2
    ly = np.floor((L.imag - by) / d).astype(np.int64) + 2
    if kernel.HAVE_NUMBA:
        hit = kernel.nearest_line_points(P, L, skey, order, lx, ly, ny_cells, 0.75 * d)
        return [(float(P[j].real), float(P[j].imag), float(np.angle(T[j]))) for j in hit if j >= 0]
    ranges = []
    for ox in (-1, 0, 1):
        for oy in (-1, 0, 1):
            k = (lx + ox) * ny_cells + (ly + oy)
            ranges.append((np.searchsorted(skey, k, "left"), np.searchsorted(skey, k, "right")))
    arrows = []
    for i in range(L.size):
        cand = [order[lo[i]:hi[i]] for lo, hi in ranges if hi[i] > lo[i]]
        if not cand:
            continue
        cand = np.concatenate(cand)
        dist = np.abs(P[cand] - L[i])
        k = int(np.argmin(dist))
        if dist[k] < 0.75 * d:
            j = cand[k]
            arrows.append((float(P[j].real), float(P[j].imag), float(np.angle(T[j]))))
    return arrows
