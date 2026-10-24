"""
streamlines.py — evenly spaced streamlines with direction arrows
(Jobard & Lefer, "Creating evenly-spaced streamlines of arbitrary density", 1997; vectorised).

How it works
1. d is the desired distance between neighbouring streamlines (smaller d = higher density).
2. Candidate seed points cover the view in a shuffled (but repeatable) order. A seed is used only
   if it is at least d away from every streamline drawn so far.
3. A batch of seeds is integrated at once with RK4, forwards and backwards along the direction
   field V/|V| (step = arc length h), which gives the geometric streamline.
4. A line stops when it comes closer than d/2 to another streamline, leaves the view, comes close
   to a singular point, leaves the fluid region, reaches a stagnation point, or closes on itself
   (e.g. circles around a vortex).

"Distance to existing streamlines" is looked up in two fine rasters (cell size d/4) in which every
accepted line is stamped with a disk of radius d/2 (stop test) and d (seed test).

The velocity always comes from the analytic superposition (field.py), never from a picture,
so the streamlines are exact up to the integration error.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .base import FlowElement
from .field import active, complex_velocity, fluid_mask, singular_points

BASE_LINES_ACROSS = 26          # ~ number of line spacings across the view at density 1
STOP_RATIO = 0.5                # a line stops at STOP_RATIO * d from another line


@dataclass
class StreamlineSet:
    lines: list[np.ndarray] = field(default_factory=list)       # each (N, 2), ordered in flow direction
    arrows: list[tuple[float, float, float]] = field(default_factory=list)   # (x, y, angle_rad)
    separation: float = 0.0                                     # line spacing d used


class _Raster:
    """Boolean raster over the (extended) view used for 'is there a line within radius r?' tests."""

    def __init__(self, x0, y0, W, H, cell):
        self.x0, self.y0, self.c = x0, y0, cell
        self.nx, self.ny = max(1, math.ceil(W / cell)), max(1, math.ceil(H / cell))
        self.a = np.zeros((self.ny, self.nx), dtype=bool)

    def index(self, z):
        ix = np.clip(((z.real - self.x0) / self.c).astype(int), 0, self.nx - 1)
        iy = np.clip(((z.imag - self.y0) / self.c).astype(int), 0, self.ny - 1)
        return iy, ix

    def test(self, z):
        iy, ix = self.index(z)
        return self.a[iy, ix]

    def stamp(self, z, radius):
        r = int(math.ceil(radius / self.c))
        oy, ox = np.mgrid[-r:r + 1, -r:r + 1]
        keep = (ox**2 + oy**2) * self.c**2 <= radius**2
        oy, ox = oy[keep], ox[keep]
        iy, ix = self.index(z)
        yy = np.clip(iy[:, None] + oy[None, :], 0, self.ny - 1)
        xx = np.clip(ix[:, None] + ox[None, :], 0, self.nx - 1)
        self.a[yy, xx] = True


def trace_streamlines(elements: Sequence[FlowElement], xlim, ylim, density: float = 1.0,
                      arrows_per_line: int = 1, seed: int = 0, batch_size: int = 48,
                      max_length_factor: float = 4.0) -> StreamlineSet:
    els = active(elements)
    x0, x1 = map(float, xlim)
    y0, y1 = map(float, ylim)
    W, H = x1 - x0, y1 - y0
    out = StreamlineSet()
    if not els or W <= 0 or H <= 0:
        return out

    d = math.sqrt(W * H) / (BASE_LINES_ACROSS * max(density, 0.05))
    d_stop = STOP_RATIO * d
    h = d / 3.0                                   # integration step (arc length) far from singularities
    out.separation = d

    sing = np.array(singular_points(els), dtype=np.complex128)
    r_sing = 0.5 * d

    # typical speed in the view -> threshold for stagnation points
    gx, gy = np.meshgrid(np.linspace(x0, x1, 17), np.linspace(y0, y1, 17))
    with np.errstate(invalid="ignore"):
        sp = np.abs(complex_velocity(els, gx + 1j * gy))
    sp = sp[np.isfinite(sp)]
    if sp.size == 0 or np.nanmedian(sp) == 0:
        return out
    v_min = 1e-4 * float(np.nanmedian(sp))

    margin = 0.02 * max(W, H)
    bx0, bx1, by0, by1 = x0 - margin, x1 + margin, y0 - margin, y1 + margin
    n_max = int(max_length_factor * (W + H) / h) + 1

    near_stop = _Raster(bx0, by0, bx1 - bx0, by1 - by0, d / 4.0)    # lines within d/2
    near_seed = _Raster(bx0, by0, bx1 - bx0, by1 - by0, d / 4.0)    # lines within d

    def direction(z):
        """Unit direction (complex) and speed of the flow at z."""
        vel = np.conj(complex_velocity(els, z))          # u + i v
        speed = np.abs(vel)
        with np.errstate(divide="ignore", invalid="ignore"):
            return vel / speed, speed

    def blocked(z):
        """Points where a line must stop without including the point."""
        bad = ~fluid_mask(els, z)
        if sing.size:
            bad |= np.min(np.abs(z[:, None] - sing[None, :]), axis=1) < r_sing
        return bad

    def local_step(z):
        """Arc-length step: h far away, smaller near singular points (where curvature ~ 1/r)."""
        if not sing.size:
            return np.full(z.shape, h)
        dist = np.min(np.abs(z[:, None] - sing[None, :]), axis=1)
        return np.clip(0.2 * dist, h / 8.0, h)

    def integrate(seeds: np.ndarray, sign: float):
        """Integrate all seeds; returns list of point arrays (complex) and closed flags."""
        B = seeds.size
        traj = np.full((n_max + 1, B), np.nan + 0j)
        traj[0] = seeds
        cur = seeds.copy()
        alive = np.ones(B, dtype=bool)
        length = np.zeros(B)
        closed = np.zeros(B, dtype=bool)
        alive &= np.isfinite(direction(seeds)[0])
        for step in range(n_max):
            idx = np.nonzero(alive)[0]
            if idx.size == 0:
                break
            z = cur[idx]
            hz = local_step(z)
            k1 = direction(z)[0] * sign
            k2 = direction(z + 0.5 * hz * k1)[0] * sign
            k3 = direction(z + 0.5 * hz * k2)[0] * sign
            k4 = direction(z + hz * k3)[0] * sign
            z_new = z + hz * (k1 + 2 * k2 + 2 * k3 + k4) / 6.0
            k_new, speed_new = direction(z_new)
            k_new = k_new * sign

            stop_before = ~np.isfinite(z_new) | ~np.isfinite(k_new) | blocked(z_new)
            stop_before |= speed_new < v_min                                     # stagnation point
            stop_before |= (k1.real * k_new.real + k1.imag * k_new.imag) < 0     # direction reversal
            stop_before |= np.abs(z_new - z) < 0.5 * hz                          # no progress (trapped
            #                                                                      at a stagnation point)
            stop_before |= near_stop.test(z_new)                                 # too close to a line
            ok = ~stop_before
            ok_idx = idx[ok]
            zn = z_new[ok]
            traj[step + 1, ok_idx] = zn
            cur[ok_idx] = zn
            length[ok_idx] += hz[ok]

            outside = (zn.real < bx0) | (zn.real > bx1) | (zn.imag < by0) | (zn.imag > by1)
            back_home = (length[ok_idx] > 3.0 * d) & (np.abs(zn - seeds[ok_idx]) < 0.75 * hz[ok])
            closed[ok_idx[back_home]] = True
            alive[idx[stop_before]] = False
            alive[ok_idx[outside | back_home]] = False

        lines = []
        for j in range(B):
            col = traj[:, j]
            finite = np.isfinite(col)
            n = col.size if finite.all() else int(np.argmax(~finite))
            pts = col[:n]
            if closed[j]:
                pts = np.append(pts, seeds[j])           # close the loop exactly
            lines.append(pts)
        return lines, closed

    # candidate seeds on a grid of spacing d/2, jittered and shuffled (repeatable)
    rng = np.random.default_rng(seed)
    gs = d / 2.0
    cx = np.arange(x0 + 0.5 * gs, x1, gs)
    cy = np.arange(y0 + 0.5 * gs, y1, gs)
    CX, CY = np.meshgrid(cx, cy)
    cand = (CX + 1j * CY).ravel()
    cand = cand + gs * 0.3 * (rng.uniform(-1, 1, cand.size) + 1j * rng.uniform(-1, 1, cand.size))
    cand = cand[rng.permutation(cand.size)]
    # priority seeds on a small ring around every singular point inside the view: guarantees at least
    # one closed circle around a vortex and radial lines out of a source / into a sink
    ring = 1.5 * r_sing * np.exp(2j * np.pi * np.arange(8) / 8)
    inside = sing[(sing.real > x0) & (sing.real < x1) & (sing.imag > y0) & (sing.imag < y1)]
    if inside.size:
        cand = np.concatenate([(inside[:, None] + ring[None, :]).ravel(), cand])
    cand = cand[~blocked(cand)]

    pos = 0
    while pos < cand.size:
        # next batch of seeds that are still at least d away from every accepted line
        free = ~near_seed.test(cand[pos:])
        take = np.nonzero(free)[0][:batch_size] + pos
        if take.size == 0:
            break
        pos = take[-1] + 1
        seeds = cand[take]
        fwd, closed = integrate(seeds, +1.0)
        bwd = [np.array([s]) for s in seeds]
        need_back = np.nonzero(~closed)[0]
        if need_back.size:
            back_lines, _ = integrate(seeds[need_back], -1.0)
            for k, j in enumerate(need_back):
                bwd[j] = back_lines[k]

        for j in range(seeds.size):
            if near_seed.test(seeds[j:j + 1])[0]:
                continue                                          # a line from this batch passed nearby
            pts = np.concatenate([bwd[j][::-1], fwd[j][1:]])       # ordered along the flow
            s = bwd[j].size - 1                                    # index of the seed
            if pts.size < 3:
                continue
            hit = near_stop.test(pts)                             # lines accepted earlier in this batch
            after = np.nonzero(hit[s + 1:])[0]
            end = s + 1 + after[0] if after.size else pts.size
            before = np.nonzero(hit[:s])[0]
            start = before[-1] + 1 if before.size else 0
            seg = pts[start:end]
            if seg.size < 3 or float(np.sum(np.abs(np.diff(seg)))) < d:
                continue
            near_stop.stamp(seg, d_stop)
            near_seed.stamp(seg, d)
            out.lines.append(np.column_stack([seg.real, seg.imag]))
            # golden-ratio offset so that arrows of neighbouring lines are not all in one column
            shift = ((len(out.lines) * 0.618034) % 1.0 - 0.5) * 0.6
            out.arrows.extend(_arrows_on(seg, arrows_per_line, d, shift))
    return out


def _arrows_on(seg: np.ndarray, n_arrows: int, d: float, shift: float = 0.0) -> list[tuple[float, float, float]]:
    """Arrow positions at equal arc-length fractions along a line, pointing in the flow direction.
    `shift` (between −0.5 and 0.5) moves all arrows of this line by a fraction of their spacing."""
    if n_arrows <= 0:
        return []
    ds = np.abs(np.diff(seg))
    s = np.concatenate([[0.0], np.cumsum(ds)])
    total = s[-1]
    if total < 2.0 * d:
        return []
    arrows = []
    for i in range(n_arrows):
        target = (i + 0.5 + shift) / n_arrows * total
        k = int(np.clip(np.searchsorted(s, target), 1, seg.size - 1))
        p = seg[k]
        t = seg[k] - seg[k - 1]
        arrows.append((float(p.real), float(p.imag), float(np.angle(t))))
    return arrows
